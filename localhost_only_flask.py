#!/usr/bin/env python3
"""
Full-feature localhost Flask app with OCI, TwelveLabs Marengo, and Oracle Vector DB
This version includes complete production functionality while running on localhost
"""

import os
import sys
import time
import json
import logging
import uuid
import datetime
import queue
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, render_template, jsonify, Response, stream_with_context
from dotenv import load_dotenv

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'twelvelabvideoai', 'src')
sys.path.insert(0, src_dir)

# Load environment variables early
try:
    load_dotenv()
    print("✅ Loaded .env file")
except Exception as e:
    print(f"⚠️ Could not load .env: {e}")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import OCI
try:
    import oci
    OCI_AVAILABLE = True
    logger.info("✅ OCI SDK imported successfully")
except Exception as e:
    logger.error(f"❌ Could not import OCI: {e}")
    oci = None
    OCI_AVAILABLE = False

# Import Flask-safe album manager and embedding functions
try:
    from unified_album_manager_flask_safe import flask_safe_album_manager
    # For backwards compatibility, also try the original create_unified_embedding
    try:
        from unified_album_manager import create_unified_embedding
    except ImportError:
        create_unified_embedding = None
    
    UNIFIED_ALBUM_AVAILABLE = True
    EMBEDDING_AVAILABLE = create_unified_embedding is not None
    logger.info("✅ Flask-safe album manager imported successfully")
    if EMBEDDING_AVAILABLE:
        logger.info("✅ Embedding functions available")
    else:
        logger.warning("⚠️ Embedding functions not available")
except Exception as e:
    logger.error(f"❌ Could not import Flask-safe album manager: {e}")
    flask_safe_album_manager = None
    create_unified_embedding = None
    UNIFIED_ALBUM_AVAILABLE = False
    EMBEDDING_AVAILABLE = False

# Import metadata extractor
try:
    from utils.metadata_extractor import get_full_metadata
    METADATA_EXTRACTOR_AVAILABLE = True
    logger.info("✅ Metadata extractor imported successfully")
except Exception as e:
    logger.warning(f"⚠️ Metadata extractor not available: {e}")
    get_full_metadata = None
    METADATA_EXTRACTOR_AVAILABLE = False

# Import Flask-safe search
try:
    # Add parent directory to path to import search_flask_safe
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from search_flask_safe import search_photos_flask_safe
    FLASK_SAFE_SEARCH_AVAILABLE = True
    logger.info("✅ Flask-safe search imported successfully")
except Exception as e:
    logger.warning(f"⚠️ Flask-safe search not available: {e}")
    search_photos_flask_safe = None
    FLASK_SAFE_SEARCH_AVAILABLE = False

# Import video slicing utilities
try:
    from video_upload_handler import (
        check_video_duration, 
        prepare_video_for_upload, 
        create_video_metadata,
        cleanup_chunks
    )
    VIDEO_SLICING_AVAILABLE = True
    logger.info("✅ Video slicing utilities imported successfully")
except Exception as e:
    logger.warning(f"⚠️ Video slicing not available: {e}")
    VIDEO_SLICING_AVAILABLE = False

# No longer need wrapper - using Flask-safe album manager directly
# flask_safe_album_manager is imported from unified_album_manager_flask_safe
if UNIFIED_ALBUM_AVAILABLE and flask_safe_album_manager:
    logger.info("✅ Flask-safe album manager ready")
else:
    logger.warning("⚠️ No album manager available")

# Flask-safe embedding functions - DO NOT use signal-based timeouts
def create_unified_embedding_flask_safe(file_path, file_type, album_name, media_id=None, **kwargs):
    """Flask-safe version - create embedding without signal timeouts
    
    Args:
        file_path: URL/path to the media file
        file_type: 'photo' or 'video'
        album_name: Name of the album
        media_id: Existing media ID to update (if None, creates new entry)
    """
    try:
        if file_type == 'photo':
            return create_photo_embedding_flask_safe(file_path, album_name, media_id=media_id, **kwargs)
        elif file_type == 'video':
            return create_video_embedding_flask_safe(file_path, album_name, media_id=media_id, **kwargs)
        else:
            logger.error(f"Unsupported file type: {file_type}")
            return None
    except Exception as e:
        logger.error(f"❌ Error creating unified embedding: {e}")
        return None

def create_photo_embedding_flask_safe(file_path, album_name, media_id=None, **kwargs):
    """Flask-safe photo embedding - uses flask_safe_album_manager
    
    Args:
        file_path: URL/path to the image (may be resized version)
        album_name: Name of the album
        media_id: Existing media ID to update (if None, creates new entry)
    """
    try:
        from twelvelabs import TwelveLabs
        from pathlib import Path
        
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        # Create embedding task
        task = client.embed.tasks.create(
            model_name="Marengo-retrieval-2.7",
            image_url=file_path
        )
        
        # Wait for completion
        task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
        
        if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
            status = client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
            final = client.embed.tasks.retrieve(task_id=task_id)
        elif hasattr(task, 'wait_for_done'):
            task.wait_for_done(sleep_interval=2)
            final = task
        else:
            final = task
        
        # Extract embedding
        embedding_vector = None
        if hasattr(final, 'image_embedding') and getattr(final.image_embedding, 'float', None) is not None:
            embedding_vector = final.image_embedding.float
        elif getattr(final, 'image_embedding', None) is not None and hasattr(final.image_embedding, 'float_'):
            embedding_vector = final.image_embedding.float_
        elif getattr(final, 'image_embedding', None) is not None and getattr(final.image_embedding, 'segments', None):
            seg0 = final.image_embedding.segments[0]
            if hasattr(seg0, 'float_'):
                embedding_vector = seg0.float_
            elif hasattr(seg0, 'float'):
                embedding_vector = seg0.float
        
        if embedding_vector:
            # Update existing media entry with embedding (DON'T create new entry)
            if media_id:
                # Update existing entry with embedding
                from utils.db_utils_flask_safe import get_flask_safe_connection
                import json
                
                try:
                    with get_flask_safe_connection() as conn:
                        cursor = conn.cursor()
                        # Convert to JSON string for Oracle VECTOR type with TO_VECTOR
                        embedding_json = json.dumps(list(embedding_vector))
                        cursor.execute(
                            "UPDATE album_media SET embedding_vector = TO_VECTOR(:embedding) WHERE id = :id",
                            {'embedding': embedding_json, 'id': media_id}
                        )
                        conn.commit()
                        logger.info(f"✅ Photo embedding stored for existing media_id {media_id}")
                except Exception as db_err:
                    logger.error(f"❌ Failed to store photo embedding: {db_err}")
                
                return media_id
            else:
                # Legacy path: Store new metadata (only if media_id not provided)
                logger.warning("⚠️ Creating new media entry for embedding - this should not happen during upload")
                media_id = flask_safe_album_manager.store_media_metadata(
                    album_name=album_name,
                    file_name=Path(file_path).name,
                    file_path=file_path,
                    file_type='photo',
                    **kwargs
                )
                
                if media_id:
                    # Update with embedding
                    from utils.db_utils_flask_safe import get_flask_safe_connection
                    import json
                    
                    try:
                        with get_flask_safe_connection() as conn:
                            cursor = conn.cursor()
                            # Convert to JSON string for Oracle VECTOR type with TO_VECTOR
                            embedding_json = json.dumps(list(embedding_vector))
                            cursor.execute(
                                "UPDATE album_media SET embedding_vector = TO_VECTOR(:embedding) WHERE id = :id",
                                {'embedding': embedding_json, 'id': media_id}
                            )
                            conn.commit()
                            logger.info(f"✅ Photo embedding stored for new media_id {media_id}")
                    except Exception as db_err:
                        logger.error(f"❌ Failed to store photo embedding: {db_err}")
                    
                    return media_id
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Error creating photo embedding: {e}")
        return None

def create_video_embedding_flask_safe(file_path, album_name, **kwargs):
    """Flask-safe video embedding - uses flask_safe_album_manager"""
    try:
        from twelvelabs import TwelveLabs
        from pathlib import Path
        
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        # Create embedding task - TwelveLabs API correct format
        task = client.embed.tasks.create(
            model_name="Marengo-retrieval-2.7",
            video_url=file_path,
            video_clip_length=kwargs.get('clip_length', 10)
        )
        
        # Wait for completion
        task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
        
        if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
            status = client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
            final = client.embed.tasks.retrieve(task_id=task_id, embedding_option=["visual-text", "audio"])
        elif hasattr(task, 'wait_for_done'):
            task.wait_for_done(sleep_interval=2)
            final = task
        else:
            final = task
        
        media_ids = []
        
        # Process each segment
        for segment in final.segments:
            if hasattr(segment, 'embedding_scope') and segment.embedding_scope:
                for scope in segment.embedding_scope:
                    if hasattr(scope, 'embedding') and scope.embedding:
                        embedding_vector = scope.embedding.float
                        
                        # Store metadata using Flask-safe manager
                        media_id = flask_safe_album_manager.store_media_metadata(
                            album_name=album_name,
                            file_name=f"{Path(file_path).stem}_seg_{segment.start_time}_{segment.end_time}.mp4",
                            file_path=file_path,
                            file_type='video',
                            start_time=segment.start_time,
                            end_time=segment.end_time,
                            duration=segment.end_time - segment.start_time,
                            **kwargs
                        )
                        
                        if media_id:
                            # Update with embedding using Flask-safe connection
                            from utils.db_utils_flask_safe import get_flask_safe_connection
                            import json
                            
                            try:
                                with get_flask_safe_connection() as conn:
                                    cursor = conn.cursor()
                                    # Convert to JSON string for Oracle VECTOR type with TO_VECTOR
                                    embedding_json = json.dumps(list(embedding_vector))
                                    cursor.execute(
                                        "UPDATE album_media SET embedding_vector = TO_VECTOR(:embedding) WHERE id = :id",
                                        {'embedding': embedding_json, 'id': media_id}
                                    )
                                    conn.commit()
                                    logger.info(f"✅ Video embedding stored for media_id {media_id}")
                            except Exception as db_err:
                                logger.error(f"❌ Failed to store video embedding: {db_err}")
                            
                            media_ids.append(media_id)
        
        return media_ids
        
    except Exception as e:
        logger.error(f"❌ Error creating video embedding: {e}")
        return None

# Import search functions
try:
    from unified_search_vector import unified_search_enhanced
    VECTOR_SEARCH_AVAILABLE = True
    logger.info("✅ Vector search imported successfully")
except Exception as e:
    logger.warning(f"⚠️ Vector search not available: {e}")
    try:
        from unified_search import unified_search
        BASIC_SEARCH_AVAILABLE = True
        logger.info("✅ Basic unified search imported successfully")
    except Exception as e2:
        logger.error(f"❌ No search functions available: {e2}")
        VECTOR_SEARCH_AVAILABLE = False
        BASIC_SEARCH_AVAILABLE = False

# Import OCI config
try:
    from oci_config import load_oci_config as _central_load_oci_config
    OCI_CONFIG_AVAILABLE = True
    logger.info("✅ OCI config loader imported successfully")
except Exception as e:
    logger.warning(f"⚠️ OCI config loader not available: {e}")
    _central_load_oci_config = None
    OCI_CONFIG_AVAILABLE = False

# Create Flask app - LOCALHOST ONLY CONFIGURATION
TEMPLATES_DIR = os.path.join(src_dir, 'templates')
app = Flask(__name__, template_folder=TEMPLATES_DIR)

# LOCALHOST ONLY CONFIGURATION
app.config['SERVER_NAME'] = None  # No domain binding
app.config['PREFERRED_URL_SCHEME'] = 'http'  # Local HTTP only
app.config['APPLICATION_ROOT'] = '/'

# Task tracking for background embedding jobs
_upload_tasks = {}
# Progress tracking for real-time updates
_progress_queues = {}
EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix='embedding-')

# Multipart upload threshold (100MB)
MULTIPART_THRESHOLD = 100 * 1024 * 1024

def _load_oci_config():
    """Load OCI configuration"""
    if _central_load_oci_config:
        try:
            # Try calling with oci module parameter first
            return _central_load_oci_config(oci)
        except TypeError:
            try:
                # Fallback to no parameters
                return _central_load_oci_config()
            except Exception as e:
                logger.warning(f"Central OCI config failed: {e}")
                return None
    else:
        # Fallback to default OCI config
        try:
            return oci.config.from_file() if oci else None
        except Exception as e:
            logger.warning(f"Default OCI config failed: {e}")
            return None

def _get_par_url_for_oci(oci_path):
    """Generate PAR URL for OCI object"""
    try:
        if not oci or not OCI_AVAILABLE:
            return None
            
        # Parse OCI path: oci://namespace/bucket/object
        if not oci_path.startswith('oci://'):
            return None
            
        path_parts = oci_path[6:].split('/', 2)
        if len(path_parts) != 3:
            return None
            
        namespace, bucket, object_name = path_parts
        
        config = _load_oci_config()
        if not config:
            return None
            
        obj_client = oci.object_storage.ObjectStorageClient(config)
        
        # Create PAR for 7 days - fix timestamp format issue
        import datetime
        expiry_time = datetime.datetime.utcnow() + datetime.timedelta(days=7)
        expiry_string = expiry_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        create_par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name=f"par-{uuid.uuid4().hex[:8]}",
            access_type="ObjectRead",
            time_expires=expiry_string,  # Use string format instead of timestamp
            object_name=object_name
        )
        
        par_response = obj_client.create_preauthenticated_request(
            namespace, bucket, create_par_details
        )
        
        base_url = f"https://objectstorage.{config['region']}.oraclecloud.com"
        return f"{base_url}{par_response.data.access_uri}"
        
    except Exception as e:
        logger.error(f"Failed to create PAR URL: {e}")
        return None
@app.route('/')
def index():
    """Main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Template error: {e}")
        return f"Template error: {e}", 500

@app.route('/health')
def health_check():
    """Simple localhost health check"""
    return jsonify({
        'status': 'healthy',
        'mode': 'localhost-only',
        'albums_available': UNIFIED_ALBUM_AVAILABLE,
        'host': request.host,
        'timestamp': int(time.time())
    })

def send_progress(task_id, stage, percent, message):
    """Send progress update to client via SSE queue"""
    if task_id in _progress_queues:
        try:
            progress_data = {
                'stage': stage,
                'percent': percent,
                'message': message,
                'timestamp': time.time()
            }
            _progress_queues[task_id].put(progress_data)
            logger.info(f"📊 Progress [{task_id}]: {stage} - {percent}% - {message}")
        except Exception as e:
            logger.error(f"❌ Error sending progress: {e}")

@app.route('/progress/<task_id>')
def progress_stream(task_id):
    """Server-Sent Events endpoint for upload progress"""
    def generate():
        # Create progress queue for this task
        _progress_queues[task_id] = queue.Queue()
        
        try:
            while True:
                try:
                    # Wait for progress update with timeout
                    progress = _progress_queues[task_id].get(timeout=30)
                    
                    # Format as SSE
                    yield f"data: {json.dumps(progress)}\n\n"
                    
                    # Check if task is complete
                    if progress.get('stage') == 'complete' or progress.get('stage') == 'error':
                        break
                        
                except queue.Empty:
                    # Send keep-alive
                    yield f": keep-alive\n\n"
                    
        except GeneratorExit:
            pass
        finally:
            # Clean up queue
            if task_id in _progress_queues:
                del _progress_queues[task_id]
    
    return Response(stream_with_context(generate()), 
                   mimetype='text/event-stream',
                   headers={
                       'Cache-Control': 'no-cache',
                       'X-Accel-Buffering': 'no'
                   })

@app.route('/list_unified_albums')
def list_unified_albums():
    """List all albums"""
    try:
        logger.info("📋 Album listing request received")
        
        if not UNIFIED_ALBUM_AVAILABLE or flask_safe_album_manager is None:
            logger.error("❌ Album manager not available")
            return jsonify({'error': 'Album manager not available', 'albums': [], 'count': 0})
        
        logger.info("🔍 Fetching albums...")
        albums = flask_safe_album_manager.list_albums()
        
        # Convert to proper format
        album_list = []
        for album in albums:
            album_data = {
                'album_id': album.get('album_id'),
                'album_name': album.get('album_name'),
                'description': album.get('description', ''),
                'created_at': album.get('created_at'),
                'total_items': album.get('total_items', 0),
                'photo_count': album.get('photo_count', 0),
                'video_count': album.get('video_count', 0)
            }
            album_list.append(album_data)
        
        logger.info(f"✅ Found {len(album_list)} albums")
        return jsonify({'albums': album_list, 'count': len(album_list)})
        
    except Exception as e:
        logger.error(f"❌ Error listing albums: {e}")
        return jsonify({'error': str(e), 'albums': [], 'count': 0})

@app.route('/album_contents/<album_name>')
def get_album_contents(album_name):
    """Get contents of a specific album"""
    try:
        logger.info(f"📂 Getting contents for album: {album_name}")
        
        if not UNIFIED_ALBUM_AVAILABLE or flask_safe_album_manager is None:
            logger.error("❌ Album manager not available")
            return jsonify({'error': 'Album manager not available', 'results': [], 'count': 0})
        
        # Get album contents
        contents = flask_safe_album_manager.get_album_contents(album_name)
        
        # Format results
        results = []
        for item in contents:
            result = {
                'media_id': item.get('media_id'),
                'album_name': album_name,
                'file_name': item.get('file_name'),
                'file_type': item.get('file_type'),
                'mime_type': item.get('mime_type'),
                'file_size': item.get('file_size'),
                'oci_path': item.get('file_path'),
                'created_at': item.get('created_at'),
                'par_url': None  # Will be generated on demand
            }
            results.append(result)
        
        logger.info(f"✅ Found {len(results)} items in album '{album_name}'")
        return jsonify({
            'album_name': album_name,
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting album contents: {e}")
        return jsonify({'error': str(e), 'results': [], 'count': 0})

@app.route('/upload_unified', methods=['POST'])
def upload_unified():
    """Upload media (photo or video) to OCI and create TwelveLabs Marengo embeddings
    
    Accepts multipart/form-data with:
    - 'mediaFile': photo or video file(s) - supports multiple files
    - 'album_name': album name (required)
    - 'auto_embed': whether to auto-create embeddings (default: true)
    
    Returns: { 
        task_id: unique identifier for tracking progress,
        success_count, 
        failed_count, 
        results: [{ success: true/false, filename, media_id, error, ... }] 
    }
    """
    # Generate task ID for progress tracking
    task_id = str(uuid.uuid4())
    
    try:
        logger.info(f"📤 Upload request received [task_id={task_id}]")
        logger.info(f"Files: {list(request.files.keys())}")
        logger.info(f"Form: {dict(request.form)}")
        
        # Send initial progress
        send_progress(task_id, 'init', 0, 'Starting upload...')
        
        # Get all files from the request
        all_files = request.files.getlist('mediaFile')
        logger.info(f"🔍 Processing {len(all_files)} file(s)")
        
        # Validate preconditions
        if not UNIFIED_ALBUM_AVAILABLE or flask_safe_album_manager is None:
            send_progress(task_id, 'error', 0, 'Album manager not available')
            return jsonify({'error': 'Album manager not available', 'task_id': task_id}), 500
        
        if not OCI_AVAILABLE:
            send_progress(task_id, 'error', 0, 'OCI SDK not available')
            return jsonify({'error': 'OCI SDK not available - check configuration', 'task_id': task_id}), 500
        
        if not all_files or len(all_files) == 0:
            send_progress(task_id, 'error', 0, 'No files provided')
            return jsonify({'error': 'No files provided', 'task_id': task_id}), 400
        
        album_name = request.form.get('album_name')
        auto_embed = request.form.get('auto_embed', 'true').lower() in ('true', '1', 'yes')
        
        if not album_name:
            send_progress(task_id, 'error', 0, 'Album name required')
            return jsonify({'error': 'album_name is required', 'task_id': task_id}), 400
        
        # Load OCI configuration once for all files
        config = _load_oci_config()
        if not config:
            send_progress(task_id, 'error', 0, 'OCI configuration not available')
            return jsonify({'error': 'OCI configuration not available', 'task_id': task_id}), 500
        
        obj_client = oci.object_storage.ObjectStorageClient(config)
        namespace = obj_client.get_namespace().data
        bucket = os.getenv('DEFAULT_OCI_BUCKET', 'Media')
        
        # Process ALL files, tracking success/failure for each
        results = []
        success_count = 0
        failed_count = 0
        
        send_progress(task_id, 'init', 5, f'Processing {len(all_files)} file(s)...')
        
        # Process each file with individual error handling
        for file_index, file in enumerate(all_files, start=1):
            file_result = {
                'filename': file.filename if file else 'unknown',
                'success': False,
                'error': None,
                'media_id': None,
                'file_type': None,
                'embedding_task_id': None
            }
            
            try:
                # Validate file
                if not file or not file.filename:
                    file_result['error'] = 'Invalid file or filename'
                    failed_count += 1
                    results.append(file_result)
                    logger.warning(f"⚠️ [{file_index}/{len(all_files)}] Skipping invalid file")
                    continue
                
                # Calculate progress range for this file (each file gets equal % of total)
                base_progress = 5 + ((file_index - 1) / len(all_files)) * 90  # 5-95% for file processing
                file_progress_range = 90 / len(all_files)
                
                def send_file_progress(stage, percent, message):
                    """Send progress for individual file within overall progress"""
                    overall_percent = base_progress + (percent * file_progress_range / 100)
                    send_progress(task_id, stage, int(overall_percent), f'[{file_index}/{len(all_files)}] {message}')
                
                send_file_progress('validate', 5, f'Validating {file.filename}...')
                
                # Detect file type
                file_type, mime_type = flask_safe_album_manager.detect_file_type(file.filename)
                file_result['file_type'] = file_type
                
                if file_type == 'unknown':
                    file_result['error'] = f'Unsupported file type: {mime_type}'
                    failed_count += 1
                    results.append(file_result)
                    logger.warning(f"⚠️ [{file_index}/{len(all_files)}] Skipping unsupported file: {file.filename} ({mime_type})")
                    continue
                
                # For videos, check duration and slice if needed
                video_chunks = []
                original_video_path = None
                is_chunked_video = False
                
                if file_type == 'video' and VIDEO_SLICING_AVAILABLE:
                    try:
                        import tempfile
                        from pathlib import Path
                        
                        send_file_progress('validate', 6, 'Checking video duration...')
                        
                        # Save video to temp file for duration check
                        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix)
                        file.stream.seek(0)
                        file.save(temp_video.name)
                        temp_video.close()
                        original_video_path = temp_video.name
                        
                        # Check duration
                        duration_info = check_video_duration(temp_video.name)
                        
                        if duration_info.get('needs_slicing'):
                            # Video exceeds duration limit - slice it
                            estimated_chunks = duration_info.get('estimated_chunks', 2)
                            send_file_progress('slice', 7, 
                                f'⚠️ Video duration: {duration_info["duration_formatted"]} exceeds 120-min limit. '
                                f'Slicing into {estimated_chunks} chunks...')
                            
                            logger.info(f"✂️ Video {file.filename} needs slicing: {duration_info['duration_formatted']}")
                            
                            def slice_progress_callback(stage, percent, message):
                                # Map slicing progress to 7-9% of overall progress
                                overall_slice_percent = 7 + (percent * 0.02)
                                send_file_progress('slice', int(overall_slice_percent), message)
                            
                            prep_result = prepare_video_for_upload(
                                temp_video.name,
                                progress_callback=slice_progress_callback
                            )
                            
                            if not prep_result['success']:
                                file_result['error'] = f'Video slicing failed: {prep_result.get("error", "Unknown error")}'
                                failed_count += 1
                                results.append(file_result)
                                if os.path.exists(temp_video.name):
                                    os.unlink(temp_video.name)
                                continue
                            
                            video_chunks = prep_result['files']
                            is_chunked_video = True
                            
                            send_file_progress('slice', 9, 
                                f'✅ Sliced into {len(video_chunks)} chunks - uploading each chunk...')
                            logger.info(f"✅ Video sliced into {len(video_chunks)} chunks")
                        else:
                            # Video is within limits
                            send_file_progress('validate', 7, 
                                f'✅ Video duration: {duration_info["duration_formatted"]} - within limits')
                            logger.info(f"✅ Video {file.filename} duration OK: {duration_info['duration_formatted']}")
                            video_chunks = [temp_video.name]
                            is_chunked_video = False
                        
                        # Reset file stream since we saved it
                        file.stream.seek(0)
                        
                    except Exception as slice_error:
                        logger.error(f"❌ Error checking/slicing video: {slice_error}")
                        send_file_progress('validate', 7, f'⚠️ Could not check video duration: {str(slice_error)}')
                        # Continue with original file
                        video_chunks = []
                        is_chunked_video = False
                        if original_video_path and os.path.exists(original_video_path):
                            os.unlink(original_video_path)
                        original_video_path = None
                
                # Extract metadata from photos (EXIF, GPS, etc.)
                extracted_metadata = None
                if file_type == 'photo' and METADATA_EXTRACTOR_AVAILABLE:
                    try:
                        send_file_progress('validate', 8, 'Extracting EXIF/GPS metadata...')
                        file.stream.seek(0)
                        extracted_metadata = get_full_metadata(file.stream)
                        file.stream.seek(0)
                        logger.info(f"📍 Metadata extracted: GPS={extracted_metadata.get('has_gps')}, "
                                   f"Location={extracted_metadata.get('city')}, {extracted_metadata.get('country')}")
                    except Exception as meta_error:
                        logger.warning(f"⚠️ Could not extract metadata: {meta_error}")
                        extracted_metadata = None
                
                # If video was sliced, upload chunks separately
                if file_type == 'video' and is_chunked_video and video_chunks:
                    send_file_progress('upload', 10, f'Uploading {len(video_chunks)} video chunks to OCI...')
                    
                    chunk_media_ids = []
                    chunk_upload_errors = []
                    
                    for chunk_idx, chunk_path in enumerate(video_chunks, 1):
                        try:
                            # Create chunk-specific object name
                            from pathlib import Path
                            chunk_filename = Path(chunk_path).name
                            chunk_object_name = f"albums/{album_name}/{file_type}s/chunks/{chunk_filename}"
                            
                            chunk_progress_start = 10 + ((chunk_idx - 1) / len(video_chunks)) * 30
                            chunk_progress_range = 30 / len(video_chunks)
                            
                            send_file_progress('upload', int(chunk_progress_start), 
                                f'Uploading chunk {chunk_idx}/{len(video_chunks)}: {chunk_filename}...')
                            
                            logger.info(f"🚀 Uploading chunk {chunk_idx}/{len(video_chunks)}: {chunk_filename}")
                            
                            # Upload chunk
                            with open(chunk_path, 'rb') as chunk_file:
                                obj_client.put_object(namespace, bucket, chunk_object_name, chunk_file)
                            
                            # Create PAR URL for chunk
                            chunk_oci_path = f'oci://{namespace}/{bucket}/{chunk_object_name}'
                            chunk_par_url = _get_par_url_for_oci(chunk_oci_path)
                            
                            send_file_progress('upload', int(chunk_progress_start + chunk_progress_range * 0.5), 
                                f'✅ Chunk {chunk_idx} uploaded, storing metadata...')
                            
                            # Store metadata for chunk
                            chunk_metadata_dict = {
                                'file_name': chunk_filename,
                                'file_type': file_type,
                                'album_name': album_name,
                                'oci_path': chunk_oci_path,
                                'par_url': chunk_par_url,
                                'is_chunk': True,
                                'chunk_index': chunk_idx,
                                'total_chunks': len(video_chunks),
                                'original_filename': file.filename
                            }
                            
                            # Get chunk metadata (duration, size)
                            chunk_vid_metadata = create_video_metadata(
                                chunk_path,
                                is_chunk=True,
                                chunk_index=chunk_idx,
                                total_chunks=len(video_chunks)
                            )
                            chunk_metadata_dict.update(chunk_vid_metadata)
                            
                            chunk_media_id = flask_safe_album_manager.store_metadata(
                                file_name=chunk_filename,
                                file_type=file_type,
                                album_name=album_name,
                                oci_path=chunk_oci_path,
                                par_url=chunk_par_url,
                                metadata=chunk_metadata_dict
                            )
                            
                            chunk_media_ids.append(chunk_media_id)
                            logger.info(f"✅ Chunk {chunk_idx} metadata stored with media_id: {chunk_media_id}")
                            
                        except Exception as chunk_error:
                            error_msg = f'Chunk {chunk_idx} upload failed: {str(chunk_error)}'
                            logger.error(f"❌ {error_msg}")
                            chunk_upload_errors.append(error_msg)
                            send_file_progress('upload', int(chunk_progress_start), 
                                f'⚠️ Chunk {chunk_idx} failed: {str(chunk_error)}')
                    
                    # Cleanup temp files
                    if original_video_path and os.path.exists(original_video_path):
                        os.unlink(original_video_path)
                    for chunk_path in video_chunks:
                        if os.path.exists(chunk_path):
                            os.unlink(chunk_path)
                    
                    # Check if all chunks uploaded successfully
                    if chunk_upload_errors:
                        file_result['error'] = f'Some chunks failed: {"; ".join(chunk_upload_errors[:3])}'
                        failed_count += 1
                        results.append(file_result)
                        continue
                    
                    # Success - mark file as processed with chunks
                    file_result['success'] = True
                    file_result['media_id'] = chunk_media_ids
                    file_result['is_chunked'] = True
                    file_result['chunk_count'] = len(video_chunks)
                    success_count += 1
                    results.append(file_result)
                    
                    send_file_progress('upload', 40, 
                        f'✅ All {len(video_chunks)} chunks uploaded successfully!')
                    
                    logger.info(f"✅ [{file_index}/{len(all_files)}] Successfully processed (chunked): {file.filename}")
                    continue
                
                # Standard upload (non-chunked or non-video)
                send_file_progress('upload', 10, f'Uploading {file.filename} to OCI...')
                
                # Create album-specific object path
                object_name = f"albums/{album_name}/{file_type}s/{file.filename}"
                logger.info(f"🚀 Uploading {file.filename} to OCI: {namespace}/{bucket}/{object_name}")
                
                # Handle large files with multipart upload if needed
                file_size = getattr(file, 'content_length', None) or request.content_length
                
                if file_size and file_size > MULTIPART_THRESHOLD:
                    logger.info(f'📦 Using multipart upload for {file.filename} (size={file_size})')
                    send_file_progress('upload', 15, f'Starting multipart upload ({file_size} bytes)...')
                    
                    create_details = oci.object_storage.models.CreateMultipartUploadDetails(object=object_name)
                    mpu = obj_client.create_multipart_upload(namespace, bucket, create_details)
                    upload_id = mpu.data.upload_id
                    part_num = 1
                    parts = []
                    
                    chunk_size = 10 * 1024 * 1024  # 10MB parts
                    total_parts = (file_size // chunk_size) + (1 if file_size % chunk_size else 0)
                    
                    while True:
                        chunk = file.stream.read(chunk_size)
                        if not chunk:
                            break
                        
                        upload_percent = 15 + int((part_num / total_parts) * 25)
                        send_file_progress('upload', upload_percent, f'Uploading part {part_num}/{total_parts}...')
                        
                        resp = obj_client.upload_part(namespace, bucket, object_name, upload_id, part_num, chunk)
                        etag = resp.headers.get('etag') if resp and hasattr(resp, 'headers') else None
                        part_detail = oci.object_storage.models.CommitMultipartUploadPartDetails(part_num=part_num, etag=etag)
                        parts.append(part_detail)
                        part_num += 1
                    
                    send_file_progress('upload', 40, 'Finalizing multipart upload...')
                    commit_details = oci.object_storage.models.CommitMultipartUploadDetails(parts_to_commit=parts)
                    obj_client.commit_multipart_upload(namespace, bucket, object_name, upload_id, commit_details)
                else:
                    logger.info(f'📄 Using single PUT for {file.filename} (size={file_size})')
                    send_file_progress('upload', 20, 'Uploading file to OCI...')
                    obj_client.put_object(namespace, bucket, object_name, file.stream)
                    send_file_progress('upload', 40, 'File uploaded successfully')
                
                # Create OCI path and PAR URL
                oci_path = f'oci://{namespace}/{bucket}/{object_name}'
                par_url = _get_par_url_for_oci(oci_path)
                logger.info(f"✅ File uploaded successfully to: {oci_path}")
                
                # For photos, create resized version for TwelveLabs (5.2MB limit)
                resized_oci_path = None
                resized_par_url = None
                if file_type == 'photo':
                    try:
                        send_file_progress('metadata', 43, 'Creating resized version for embedding...')
                        logger.info(f"📐 Creating optimized version for TwelveLabs embedding")
                        
                        from utils.image_resizer import resize_image_for_embedding
                        import tempfile
                        
                        # Download original from OCI to temp file
                        temp_original = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
                        get_response = obj_client.get_object(namespace, bucket, object_name)
                        with open(temp_original.name, 'wb') as f:
                            for chunk in get_response.data.raw.stream(1024 * 1024, decode_content=False):
                                f.write(chunk)
                        temp_original.close()
                        
                        actual_size = os.path.getsize(temp_original.name)
                        logger.info(f"Downloaded file size: {actual_size/(1024*1024):.2f}MB")
                        
                        # Resize image
                        resized_path, was_resized, orig_size, new_size = resize_image_for_embedding(
                            temp_original.name, 
                            max_size_mb=5.0,
                            preserve_original=True
                        )
                        
                        if was_resized:
                            # Upload resized version to OCI
                            resized_filename = f"resized_{file.filename}"
                            if not resized_filename.lower().endswith('.jpg'):
                                resized_filename = os.path.splitext(resized_filename)[0] + '.jpg'
                            
                            resized_object_name = f"albums/{album_name}/{file_type}s/resized/{resized_filename}"
                            with open(resized_path, 'rb') as f:
                                obj_client.put_object(namespace, bucket, resized_object_name, f)
                            
                            resized_oci_path = f'oci://{namespace}/{bucket}/{resized_object_name}'
                            resized_par_url = _get_par_url_for_oci(resized_oci_path)
                            
                            logger.info(f"✅ Resized version created: {orig_size/(1024*1024):.2f}MB → {new_size/(1024*1024):.2f}MB")
                            logger.info(f"📍 Resized OCI path: {resized_oci_path}")
                            logger.info(f"🔗 Resized PAR URL: {resized_par_url[:100] if resized_par_url else 'None'}...")
                            send_file_progress('metadata', 45, f'Optimized for embedding: {new_size/(1024*1024):.1f}MB')
                            
                            os.unlink(resized_path)
                        else:
                            logger.info(f"Image already optimal size ({new_size/(1024*1024):.2f}MB), no resize needed")
                            send_file_progress('metadata', 45, 'Image size optimal')
                        
                        os.unlink(temp_original.name)
                        
                    except Exception as resize_error:
                        logger.warning(f"⚠️ Could not create resized version: {resize_error}")
                        send_file_progress('metadata', 45, 'Warning: Could not optimize image size')
                
                # For videos, compress if larger than 1.5GB (TwelveLabs has 2GB limit)
                elif file_type == 'video':
                    try:
                        actual_size = file_size or 0
                        size_gb = actual_size / (1024**3)
                        
                        if size_gb > 1.5:
                            send_file_progress('metadata', 43, f'Compressing video ({size_gb:.1f}GB > 1.5GB)...')
                            logger.info(f"🎬 Video size {size_gb:.2f}GB exceeds threshold, compressing for TwelveLabs")
                            
                            from utils.video_compressor import compress_video_for_embedding, check_ffmpeg_available
                            import tempfile
                            
                            if not check_ffmpeg_available():
                                logger.warning("⚠️ ffmpeg not available, skipping video compression")
                                send_file_progress('metadata', 45, 'Warning: ffmpeg not available for compression')
                            else:
                                # Download original from OCI to temp file
                                temp_original = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
                                get_response = obj_client.get_object(namespace, bucket, object_name)
                                with open(temp_original.name, 'wb') as f:
                                    for chunk in get_response.data.raw.stream(1024 * 1024, decode_content=False):
                                        f.write(chunk)
                                temp_original.close()
                                
                                logger.info(f"Downloaded video size: {os.path.getsize(temp_original.name)/(1024**3):.2f}GB")
                                
                                # Compress video
                                compressed_path, was_compressed, orig_size, new_size = compress_video_for_embedding(
                                    temp_original.name,
                                    max_size_gb=1.5,
                                    preserve_original=True
                                )
                                
                                if was_compressed:
                                    # Upload compressed version to OCI
                                    compressed_filename = f"compressed_{file.filename}"
                                    compressed_object_name = f"albums/{album_name}/{file_type}s/compressed/{compressed_filename}"
                                    
                                    with open(compressed_path, 'rb') as f:
                                        obj_client.put_object(namespace, bucket, compressed_object_name, f)
                                    
                                    resized_oci_path = f'oci://{namespace}/{bucket}/{compressed_object_name}'
                                    resized_par_url = _get_par_url_for_oci(resized_oci_path)
                                    
                                    logger.info(f"✅ Compressed version created: {orig_size/(1024**3):.2f}GB → {new_size/(1024**3):.2f}GB")
                                    send_file_progress('metadata', 45, f'Compressed for embedding: {new_size/(1024**3):.1f}GB')
                                    
                                    os.unlink(compressed_path)
                                else:
                                    logger.info(f"Video compression skipped or failed")
                                    send_file_progress('metadata', 45, 'Video size acceptable')
                                
                                os.unlink(temp_original.name)
                        else:
                            logger.info(f"Video size {size_gb:.2f}GB is under 1.5GB threshold, no compression needed")
                            send_file_progress('metadata', 45, 'Video size optimal')
                            
                    except Exception as compress_error:
                        logger.warning(f"⚠️ Could not compress video: {compress_error}")
                        send_file_progress('metadata', 45, 'Warning: Could not optimize video size')
                
                send_file_progress('metadata', 48, 'Storing metadata in database...')
                
                # Store metadata in database
                media_id = None
                try:
                    metadata_params = {
                        'album_name': album_name,
                        'file_name': file.filename,
                        'file_path': oci_path,
                        'file_type': file_type,
                        'mime_type': mime_type,
                        'file_size': file_size,
                        'oci_namespace': namespace,
                        'oci_bucket': bucket,
                        'oci_object_path': object_name
                    }
                    
                    # Add GPS and location data if available
                    if extracted_metadata:
                        metadata_params.update({
                            'latitude': extracted_metadata.get('latitude'),
                            'longitude': extracted_metadata.get('longitude'),
                            'gps_altitude': extracted_metadata.get('gps_altitude'),
                            'city': extracted_metadata.get('city'),
                            'state': extracted_metadata.get('state'),
                            'country': extracted_metadata.get('country'),
                            'country_code': extracted_metadata.get('country_code'),
                            'capture_date': extracted_metadata.get('capture_date'),
                            'camera_make': extracted_metadata.get('camera_make'),
                            'camera_model': extracted_metadata.get('camera_model'),
                            'orientation': extracted_metadata.get('orientation')
                        })
                    
                    media_id = flask_safe_album_manager.store_media_metadata(**metadata_params)
                    logger.info(f"✅ Metadata stored with media_id: {media_id}")
                    send_file_progress('metadata', 50, f'Metadata stored (ID: {media_id})')
                except Exception as db_error:
                    error_msg = str(db_error)
                    if 'unique constraint' in error_msg.lower() or 'ORA-00001' in error_msg:
                        logger.warning(f"⚠️ File already exists in database (duplicate): {file.filename}")
                        media_id = f"duplicate_{int(time.time())}"
                        send_file_progress('metadata', 50, 'File already exists (using duplicate ID)')
                    else:
                        logger.error(f"❌ Failed to store metadata in database: {db_error}")
                        media_id = f"upload_{int(time.time())}"
                        send_file_progress('metadata', 50, 'Database error (using fallback ID)')
                    logger.info(f"🔄 Using fallback media_id: {media_id}")
                
                # Start embedding task if requested
                embedding_task_id = None
                embedding_status = 'disabled'
                if auto_embed and media_id and EMBEDDING_AVAILABLE:
                    try:
                        send_file_progress('embedding', 55, 'Creating TwelveLabs embedding...')
                        
                        # Use resized/compressed version for embedding if available
                        embedding_par_url = resized_par_url if resized_par_url else par_url
                        embedding_oci_path = resized_oci_path if resized_oci_path else oci_path
                        
                        if resized_par_url:
                            logger.info(f"🔹 Using optimized version for TwelveLabs embedding")
                            logger.info(f"🔗 Embedding PAR URL: {embedding_par_url[:100] if embedding_par_url else 'None'}...")
                        else:
                            logger.info(f"📄 Using original version for TwelveLabs embedding")
                            logger.info(f"🔗 Embedding PAR URL: {embedding_par_url[:100] if embedding_par_url else 'None'}...")
                        
                        embedding_task_id = str(uuid.uuid4())
                        _upload_tasks[embedding_task_id] = {
                            'status': 'pending',
                            'media_id': media_id,
                            'album_name': album_name,
                            'filename': file.filename,
                            'file_type': file_type,
                            'oci_path': embedding_oci_path,
                            'par_url': embedding_par_url,
                            'created_at': time.time()
                        }
                        embedding_status = 'pending'
                        
                        # Background task definition (kept inside to capture variables)
                        def run_embedding_task(tid, upload_tid, media_id, oci_path, par_url, file_type, album_name, filename):
                            """Background task to create TwelveLabs Marengo embeddings"""
                            logger.info(f'🧠 Starting TwelveLabs embedding task {tid} for {filename}')
                            _upload_tasks[tid]['status'] = 'running'
                            
                            try:
                                send_progress(upload_tid, 'embedding', 60, f'TwelveLabs processing {file_type}...')
                                
                                if file_type == 'video':
                                    logger.info(f'🎬 Creating video embeddings with TwelveLabs Marengo for {filename}')
                                    send_progress(upload_tid, 'embedding', 70, 'Generating video embeddings...')
                                    
                                    embedding_ids = create_unified_embedding_flask_safe(par_url, file_type, album_name, media_id=media_id)
                                    if embedding_ids:
                                        _upload_tasks[tid]['status'] = 'completed'
                                        _upload_tasks[tid]['embedding_ids'] = embedding_ids
                                        _upload_tasks[tid]['completed_at'] = time.time()
                                        logger.info(f'✅ Video embedding completed for {filename}')
                                        send_progress(upload_tid, 'embedding', 80, 'Video embeddings created')
                                        
                                        # Clean up compressed video from OCI
                                        if oci_path and '/compressed/' in oci_path:
                                            try:
                                                config = _load_oci_config()
                                                if config:
                                                    cleanup_client = oci.object_storage.ObjectStorageClient(config)
                                                    oci_parts = oci_path.replace('oci://', '').split('/', 2)
                                                    if len(oci_parts) == 3:
                                                        ns, bkt, obj_name = oci_parts
                                                        cleanup_client.delete_object(ns, bkt, obj_name)
                                                        logger.info(f'🧹 Deleted compressed video from OCI: {obj_name}')
                                            except Exception as cleanup_err:
                                                logger.warning(f'⚠️ Could not delete compressed video: {cleanup_err}')
                                    else:
                                        _upload_tasks[tid]['status'] = 'failed'
                                        _upload_tasks[tid]['error'] = 'Video embedding creation failed'
                                
                                elif file_type == 'photo':
                                    logger.info(f'📸 Creating photo embeddings with TwelveLabs Marengo for {filename}')
                                    send_progress(upload_tid, 'embedding', 70, 'Generating photo embeddings...')
                                    
                                    embedding_id = create_unified_embedding_flask_safe(par_url, file_type, album_name, media_id=media_id)
                                    if embedding_id:
                                        _upload_tasks[tid]['status'] = 'completed'
                                        _upload_tasks[tid]['embedding_id'] = embedding_id
                                        _upload_tasks[tid]['completed_at'] = time.time()
                                        logger.info(f'✅ Photo embedding completed for {filename}')
                                        send_progress(upload_tid, 'embedding', 80, 'Photo embeddings created')
                                        
                                        # Clean up resized image from OCI
                                        if oci_path and '/resized/' in oci_path:
                                            try:
                                                config = _load_oci_config()
                                                if config:
                                                    cleanup_client = oci.object_storage.ObjectStorageClient(config)
                                                    oci_parts = oci_path.replace('oci://', '').split('/', 2)
                                                    if len(oci_parts) == 3:
                                                        ns, bkt, obj_name = oci_parts
                                                        cleanup_client.delete_object(ns, bkt, obj_name)
                                                        logger.info(f'🧹 Deleted resized image from OCI: {obj_name}')
                                            except Exception as cleanup_err:
                                                logger.warning(f'⚠️ Could not delete resized image: {cleanup_err}')
                                    else:
                                        _upload_tasks[tid]['status'] = 'failed'
                                        _upload_tasks[tid]['error'] = 'Photo embedding creation failed'
                                
                                send_progress(upload_tid, 'db_store', 85, 'Storing embeddings in Vector DB...')
                                logger.info(f'🎉 Embedding task {tid} completed successfully')
                                send_progress(upload_tid, 'db_store', 95, 'Embeddings stored in database')
                                
                            except Exception as e:
                                logger.exception(f'❌ Embedding task {tid} failed: {e}')
                                _upload_tasks[tid]['status'] = 'failed'
                                _upload_tasks[tid]['error'] = str(e)
                                _upload_tasks[tid]['failed_at'] = time.time()
                                send_progress(upload_tid, 'error', 0, f'Embedding failed: {str(e)}')
                        
                        # Submit background task
                        EXECUTOR.submit(run_embedding_task, embedding_task_id, task_id, media_id, embedding_oci_path, embedding_par_url, file_type, album_name, file.filename)
                        logger.info(f"🚀 Background embedding task {embedding_task_id} submitted")
                        
                    except Exception as embedding_error:
                        logger.error(f"❌ Failed to start embedding task: {embedding_error}")
                        embedding_status = 'failed'
                        send_file_progress('error', 0, f'Failed to start embedding: {str(embedding_error)[:50]}')
                
                # File processed successfully
                file_result['success'] = True
                file_result['media_id'] = media_id
                file_result['embedding_task_id'] = embedding_task_id
                file_result['embedding_status'] = embedding_status
                file_result['oci_path'] = oci_path
                success_count += 1
                results.append(file_result)
                
                logger.info(f"✅ [{file_index}/{len(all_files)}] Successfully processed: {file.filename}")
                
            except Exception as file_error:
                # File processing failed - log and continue to next file
                logger.error(f"❌ [{file_index}/{len(all_files)}] Failed to process {file.filename}: {file_error}")
                file_result['error'] = str(file_error)
                failed_count += 1
                results.append(file_result)
                send_progress(task_id, 'error', int(base_progress + file_progress_range), f'[{file_index}/{len(all_files)}] Error: {str(file_error)[:50]}...')
                # Continue to next file
        
        # All files processed - send final summary
        send_progress(task_id, 'complete', 100, f'Completed: {success_count} succeeded, {failed_count} failed')
        
        logger.info(f"📊 Upload batch complete: {success_count}/{len(all_files)} succeeded, {failed_count}/{len(all_files)} failed")
        
        return jsonify({
            'status': 'success' if success_count > 0 else 'failed',
            'message': f'Processed {len(all_files)} files: {success_count} succeeded, {failed_count} failed',
            'task_id': task_id,
            'album_name': album_name,
            'total_files': len(all_files),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results,
            'auto_embed': auto_embed,
            'upload_time': time.time()
        })
        
    except Exception as e:
        logger.exception(f"❌ Upload failed: {e}")
        send_progress(task_id if 'task_id' in locals() else 'unknown', 'error', 0, f'Upload failed: {str(e)}')
        return jsonify({'error': f'Upload failed: {str(e)}', 'task_id': task_id if 'task_id' in locals() else None}), 500

@app.route('/media_with_gps')
def media_with_gps():
    """Get all media items that have GPS coordinates for map visualization"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        query = """
        SELECT id, album_name, file_name, file_type, latitude, longitude, 
               city, state, country, capture_date, camera_model,
               oci_namespace, oci_bucket, oci_object_path, file_path
        FROM album_media
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY capture_date DESC NULLS LAST
        """
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            
            media_items = []
            for row in cursor:
                media_items.append({
                    'id': row[0],
                    'album_name': row[1],
                    'file_name': row[2],
                    'file_type': row[3],
                    'latitude': float(row[4]) if row[4] else None,
                    'longitude': float(row[5]) if row[5] else None,
                    'city': row[6],
                    'state': row[7],
                    'country': row[8],
                    'capture_date': row[9].isoformat() if row[9] else None,
                    'camera_model': row[10],
                    'thumbnail_url': f'/media_thumbnail/{row[0]}',
                    'full_url': row[13]  # file_path
                })
        
        logger.info(f"📍 Found {len(media_items)} media items with GPS coordinates")
        return jsonify({'media': media_items, 'count': len(media_items)})
        
    except Exception as e:
        logger.error(f"❌ Error fetching GPS media: {e}")
        return jsonify({'error': str(e), 'media': [], 'count': 0}), 500

@app.route('/media_thumbnail/<int:media_id>')
def media_thumbnail(media_id):
    """Generate thumbnail URL for media item (placeholder for now)"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        query = """
        SELECT file_path, file_type, oci_namespace, oci_bucket, oci_object_path
        FROM album_media
        WHERE id = :media_id
        """
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, {'media_id': media_id})
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Media not found'}), 404
            
            # For now, return a placeholder or the full image
            # In production, you'd generate actual thumbnails
            file_path, file_type, namespace, bucket, object_path = row
            
            # Generate PAR URL for the image
            par_url = _get_par_url_for_oci(file_path)
            
            if par_url:
                return jsonify({'url': par_url, 'type': file_type})
            else:
                return jsonify({'error': 'Could not generate thumbnail URL'}), 500
                
    except Exception as e:
        logger.error(f"❌ Error generating thumbnail: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/search_unified', methods=['POST'])
def search_unified():
    """Unified search across photos and videos using TwelveLabs Marengo embeddings
    
    Searches both photo and video content using natural language queries.
    Uses Oracle Vector DB for similarity search.
    
    JSON body: { 
        "query": "search text", 
        "limit": 20, 
        "album_filter": "optional",
        "min_similarity": 0.30  (optional, default 30%)
    }
    Returns: { "results": [{"type": "photo/video", "media_id": "...", "score": 0.95, ...}] }
    """
    try:
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        limit = data.get('limit', 20)
        album_filter = data.get('album_filter')
        min_similarity = data.get('min_similarity', 0.30)  # Default 30% threshold
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        logger.info(f"🔍 Unified search request: '{query}' (limit: {limit}, threshold: {min_similarity*100:.0f}%)")
        
        if not UNIFIED_ALBUM_AVAILABLE:
            return jsonify({'error': 'Unified album system not available'}), 500
        
        # Try Flask-safe vector search first (Oracle Vector DB), fall back to basic search
        results = []
        search_method = "unknown"
        
        if FLASK_SAFE_SEARCH_AVAILABLE and search_photos_flask_safe:
            logger.info("🧠 Using Flask-safe Vector DB search")
            search_method = "vector_flask_safe"
            
            try:
                # search_photos_flask_safe returns list of results directly
                photo_results = search_photos_flask_safe(
                    query_text=query,
                    album_name=album_filter,
                    top_k=limit,
                    min_similarity=min_similarity
                )
                
                # Results are already in the correct format
                results = photo_results if photo_results else []
                logger.info(f"✅ Flask-safe search found {len(results)} photos")
                        
            except Exception as e:
                logger.error(f"Flask-safe vector search failed: {e}", exc_info=True)
                results = []
        
        elif 'unified_search' in globals() and BASIC_SEARCH_AVAILABLE:
            logger.info("📋 Using basic unified search")
            search_method = "basic"
            
            try:
                results = unified_search(
                    query=query,
                    limit=limit,
                    album_filter=album_filter
                )
                
                # Convert basic search result to consistent format
                if isinstance(results, dict) and 'results' in results:
                    results = results['results']
                elif not isinstance(results, list):
                    results = []
                    
            except Exception as e:
                logger.error(f"Basic search failed: {e}")
                results = []
        else:
            return jsonify({'error': 'No search functionality available'}), 500
        
        # Normalize results format
        normalized_results = []
        for result in results:
            if isinstance(result, dict):
                normalized_result = {
                    'media_id': result.get('media_id'),
                    'album_name': result.get('album_name'),
                    'file_name': result.get('file_name'),
                    'file_type': result.get('file_type'),
                    'score': result.get('score', result.get('similarity', 0.0)),
                    'oci_path': result.get('oci_path', result.get('file_path')),
                    'par_url': result.get('par_url'),
                    'created_at': result.get('created_at'),
                    'segment_start': result.get('segment_start'),  # For videos
                    'segment_end': result.get('segment_end'),      # For videos
                    'description': result.get('description', result.get('summary'))
                }
                normalized_results.append(normalized_result)
        
        logger.info(f"✅ Found {len(normalized_results)} results using {search_method} search")
        
        return jsonify({
            'query': query,
            'results': normalized_results,
            'count': len(normalized_results),
            'search_method': search_method,
            'limit': limit,
            'album_filter': album_filter
        })
        
    except Exception as e:
        logger.exception(f"❌ Search failed: {e}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

@app.route('/embedding_status/<task_id>')
def embedding_status(task_id):
    """Check status of background embedding task"""
    try:
        if task_id not in _upload_tasks:
            return jsonify({'error': 'Task not found'}), 404
        
        task = _upload_tasks[task_id]
        return jsonify({
            'task_id': task_id,
            'status': task.get('status'),
            'media_id': task.get('media_id'),
            'filename': task.get('filename'),
            'file_type': task.get('file_type'),
            'album_name': task.get('album_name'),
            'created_at': task.get('created_at'),
            'completed_at': task.get('completed_at'),
            'failed_at': task.get('failed_at'),
            'error': task.get('error'),
            'embedding_id': task.get('embedding_id'),
            'embedding_ids': task.get('embedding_ids')
        })
        
    except Exception as e:
        logger.error(f"❌ Status check failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_media_url/<int:media_id>')
def get_media_url(media_id):
    """Get PAR URL for a specific media item"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        # Get media details from database
        sql = """
        SELECT file_path, file_type, file_name
        FROM album_media
        WHERE id = :media_id
        """
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, {'media_id': media_id})
            result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'Media not found'}), 404
        
        file_path = result[0]
        file_type = result[1]
        file_name = result[2]
        
        # Generate PAR URL
        par_url = _get_par_url_for_oci(file_path)
        
        if not par_url:
            return jsonify({'error': 'Failed to generate PAR URL'}), 500
        
        return jsonify({
            'media_id': media_id,
            'par_url': par_url,
            'file_name': file_name,
            'file_type': file_type
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to get media URL: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_media/<int:media_id>', methods=['DELETE'])
def delete_media(media_id):
    """Delete a single media item (image or video) from database and OCI"""
    try:
        logger.info(f"🗑️ Deleting media ID: {media_id}")
        
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        # Get media info before deleting
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT file_path, file_name, file_type, album_name 
                   FROM album_media WHERE id = :id""",
                {'id': media_id}
            )
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'error': 'Media not found'}), 404
            
            file_path, file_name, file_type, album_name = result
            
            # Delete from OCI if path exists
            if file_path and file_path.startswith('oci://'):
                try:
                    # Parse OCI path: oci://namespace/bucket/object
                    path_parts = file_path[6:].split('/', 2)
                    if len(path_parts) == 3:
                        namespace, bucket, object_name = path_parts
                        
                        config = _load_oci_config()
                        if config and oci:
                            obj_client = oci.object_storage.ObjectStorageClient(config)
                            obj_client.delete_object(
                                namespace_name=namespace,
                                bucket_name=bucket,
                                object_name=object_name
                            )
                            logger.info(f"✅ Deleted from OCI: {object_name}")
                except Exception as oci_err:
                    logger.warning(f"⚠️ Could not delete from OCI: {oci_err}")
            
            # Delete from database
            cursor.execute("DELETE FROM album_media WHERE id = :id", {'id': media_id})
            conn.commit()
            
            logger.info(f"✅ Deleted media ID {media_id}: {file_name}")
            return jsonify({
                'success': True,
                'message': f'Deleted {file_type} "{file_name}" from {album_name}',
                'media_id': media_id
            })
            
    except Exception as e:
        logger.error(f"❌ Failed to delete media: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_album/<album_name>', methods=['DELETE'])
def delete_album(album_name):
    """Delete an entire album and all its media from database and OCI"""
    try:
        logger.info(f"🗑️ Deleting album: {album_name}")
        
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get all media in album
            cursor.execute(
                """SELECT id, file_path, file_name, file_type 
                   FROM album_media WHERE album_name = :album_name""",
                {'album_name': album_name}
            )
            media_items = cursor.fetchall()
            
            if not media_items:
                return jsonify({'error': 'Album not found or empty'}), 404
            
            deleted_count = 0
            oci_errors = []
            
            # Delete each media item from OCI
            for media_id, file_path, file_name, file_type in media_items:
                if file_path and file_path.startswith('oci://'):
                    try:
                        # Parse OCI path: oci://namespace/bucket/object
                        path_parts = file_path[6:].split('/', 2)
                        if len(path_parts) == 3:
                            namespace, bucket, object_name = path_parts
                            
                            config = _load_oci_config()
                            if config and oci:
                                obj_client = oci.object_storage.ObjectStorageClient(config)
                                obj_client.delete_object(
                                    namespace_name=namespace,
                                    bucket_name=bucket,
                                    object_name=object_name
                                )
                                logger.info(f"✅ Deleted from OCI: {object_name}")
                    except Exception as oci_err:
                        logger.warning(f"⚠️ Could not delete {file_name} from OCI: {oci_err}")
                        oci_errors.append(file_name)
                
                deleted_count += 1
            
            # Delete all media from database
            cursor.execute(
                "DELETE FROM album_media WHERE album_name = :album_name",
                {'album_name': album_name}
            )
            conn.commit()
            
            message = f'Deleted album "{album_name}" with {deleted_count} items'
            if oci_errors:
                message += f' (OCI errors for {len(oci_errors)} files)'
            
            logger.info(f"✅ {message}")
            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': deleted_count,
                'oci_errors': oci_errors
            })
            
    except Exception as e:
        logger.error(f"❌ Failed to delete album: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/config_debug')
def config_debug():
    """Debug endpoint to show configuration and capabilities"""
    return jsonify({
        'message': 'Full-feature localhost Flask app with OCI, TwelveLabs, and Oracle Vector DB',
        'capabilities': {
            'oci_available': OCI_AVAILABLE,
            'album_manager': UNIFIED_ALBUM_AVAILABLE,
            'embedding_creation': EMBEDDING_AVAILABLE,
            'vector_search': VECTOR_SEARCH_AVAILABLE,
            'basic_search': BASIC_SEARCH_AVAILABLE,
            'oci_config': OCI_CONFIG_AVAILABLE
        },
        'app_config': {
            'SERVER_NAME': app.config.get('SERVER_NAME'),
            'PREFERRED_URL_SCHEME': app.config.get('PREFERRED_URL_SCHEME'),
            'APPLICATION_ROOT': app.config.get('APPLICATION_ROOT'),
        },
        'environment_check': {
            'DEFAULT_OCI_BUCKET': os.environ.get('DEFAULT_OCI_BUCKET', 'Not set'),
            'TWELVE_LABS_API_KEY': 'Set' if os.environ.get('TWELVE_LABS_API_KEY') else 'Not set',
            'SERVER_NAME': os.environ.get('SERVER_NAME', 'Not set'),
            'FLASK_HOST': os.environ.get('FLASK_HOST', 'Not set'),
        },
        'request_info': {
            'host': request.host,
            'url': request.url,
        },
        'active_tasks': len(_upload_tasks)
    })

if __name__ == '__main__':
    logger.info("🌐 Starting LOCALHOST-ONLY Flask application")
    logger.info("🚫 NO domain configuration - mishras.online settings DISABLED")
    logger.info("💻 Access at: http://localhost:8080")
    logger.info("💊 Health: http://localhost:8080/health")
    logger.info("🔧 Config: http://localhost:8080/config_debug")
    
    # Force localhost-only - no 0.0.0.0 binding
    app.run(
        host='127.0.0.1',  # Localhost only
        port=8080,
        debug=False,
        threaded=True
    )