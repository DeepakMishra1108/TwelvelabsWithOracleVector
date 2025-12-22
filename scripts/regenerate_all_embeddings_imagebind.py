#!/usr/bin/env python3
"""
Regenerate ALL photo and video embeddings using ImageBind
This replaces old TwelveLabs embeddings with ImageBind embeddings
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add paths
current_dir = Path(__file__).parent
project_root = current_dir.parent
src_dir = project_root / 'src'
twelvelabs_src = project_root / 'twelvelabvideoai' / 'src'

sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(twelvelabs_src))

from dotenv import load_dotenv
load_dotenv()

import oci
from datetime import datetime, timedelta
import uuid

from utils.db_utils_flask_safe import get_flask_safe_connection
from utils.imagebind_helper import get_imagebind_embedder
import json
import tempfile
import requests

logger = logging.getLogger(__name__)

def get_oci_config():
    """Load OCI configuration"""
    try:
        config_path = os.path.expanduser(os.getenv('OCI_CONFIG_PATH', '~/.oci/config'))
        config = oci.config.from_file(config_path)
        return config
    except Exception as e:
        logger.error(f"Failed to load OCI config: {e}")
        return None

def create_presigned_url(oci_object_path):
    """Create presigned URL for OCI object"""
    try:
        config = get_oci_config()
        if not config:
            return None
        
        bucket_name = os.getenv('OCI_BUCKET_NAME', 'Media')
        obj_client = oci.object_storage.ObjectStorageClient(config)
        namespace = obj_client.get_namespace().data
        
        # Create PAR for 1 hour
        expiry_time = datetime.utcnow() + timedelta(hours=1)
        
        create_par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name=f"regenerate-{uuid.uuid4().hex[:8]}",
            access_type="ObjectRead",
            time_expires=expiry_time.isoformat() + 'Z',
            object_name=oci_object_path
        )
        
        par_response = obj_client.create_preauthenticated_request(
            namespace, bucket_name, create_par_details
        )
        
        base_url = f"https://objectstorage.{config['region']}.oraclecloud.com"
        full_url = f"{base_url}{par_response.data.access_uri}"
        return full_url
        
    except Exception as e:
        logger.error(f"Failed to create presigned URL: {e}")
        return None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def regenerate_photo_embeddings():
    """Regenerate embeddings for all photos"""
    try:
        logger.info("=" * 80)
        logger.info("🖼️  REGENERATING PHOTO EMBEDDINGS WITH IMAGEBIND")
        logger.info("=" * 80)
        
        # Get embedder
        embedder = get_imagebind_embedder()
        logger.info("✅ ImageBind model loaded")
        
        # Get all photos with file_path and oci_object_path
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, file_name, file_path, album_name, oci_object_path 
                FROM album_media 
                WHERE file_type = 'photo'
                ORDER BY id
            """)
            photos = cursor.fetchall()
        
        total = len(photos)
        logger.info(f"📊 Found {total} photos to process")
        
        success_count = 0
        error_count = 0
        
        for idx, (media_id, file_name, file_path, album_name, oci_object_path) in enumerate(photos, 1):
            try:
                logger.info(f"\n[{idx}/{total}] Processing: {file_name}")
                
                # Download image to temp file
                temp_file = None
                try:
                    # Get presigned URL for OCI object
                    if oci_object_path:
                        download_url = create_presigned_url(oci_object_path)
                        if download_url:
                            logger.info(f"  📥 Downloading from OCI...")
                            response = requests.get(download_url, timeout=30)
                            response.raise_for_status()
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                            temp_file.write(response.content)
                            temp_file.close()
                            local_path = temp_file.name
                        else:
                            logger.error(f"  ❌ Failed to create presigned URL")
                            error_count += 1
                            continue
                    elif file_path and file_path.startswith('http'):
                        response = requests.get(file_path, timeout=30)
                        response.raise_for_status()
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                        temp_file.write(response.content)
                        temp_file.close()
                        local_path = temp_file.name
                        logger.info(f"  📥 Downloaded from URL")
                    elif file_path and os.path.exists(file_path):
                        local_path = file_path
                    else:
                        logger.warning(f"  ⚠️  No valid path found")
                        error_count += 1
                        continue
                except Exception as download_error:
                    logger.error(f"  ❌ Download failed: {download_error}")
                    error_count += 1
                    continue
                
                # Generate ImageBind embedding
                embedding_vector = embedder.generate_image_embedding(local_path)
                
                # Cleanup temp file
                if temp_file:
                    os.unlink(temp_file.name)
                
                if embedding_vector is not None:
                    # Update database with new ImageBind embedding
                    with get_flask_safe_connection() as conn:
                        cursor = conn.cursor()
                        # Convert numpy float32 to Python float
                        embedding_list = [float(x) for x in embedding_vector]
                        embedding_json = json.dumps(embedding_list)
                        cursor.execute(
                            "UPDATE album_media SET embedding_vector = TO_VECTOR(:embedding) WHERE id = :id",
                            {'embedding': embedding_json, 'id': media_id}
                        )
                        conn.commit()
                    
                    success_count += 1
                    logger.info(f"  ✅ Updated embedding (dim: {len(embedding_vector)})")
                else:
                    logger.error(f"  ❌ Failed to generate embedding")
                    error_count += 1
                
                # Progress update every 10 photos
                if idx % 10 == 0:
                    logger.info(f"\n📊 Progress: {idx}/{total} ({success_count} success, {error_count} errors)")
                
            except Exception as e:
                logger.error(f"  ❌ Error processing {file_name}: {e}")
                error_count += 1
                continue
        
        logger.info("\n" + "=" * 80)
        logger.info(f"📊 PHOTO EMBEDDING REGENERATION COMPLETE")
        logger.info(f"   ✅ Success: {success_count}/{total}")
        logger.info(f"   ❌ Errors: {error_count}/{total}")
        logger.info("=" * 80)
        
        return success_count, error_count
        
    except Exception as e:
        logger.error(f"❌ Fatal error in photo regeneration: {e}")
        raise

def regenerate_video_embeddings():
    """Regenerate embeddings for all videos"""
    try:
        logger.info("\n" + "=" * 80)
        logger.info("🎬 REGENERATING VIDEO EMBEDDINGS WITH IMAGEBIND")
        logger.info("=" * 80)
        
        # Get embedder
        embedder = get_imagebind_embedder()
        logger.info("✅ ImageBind model loaded")
        
        # Get all videos with file_path and oci_object_path
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, file_name, file_path, album_name, oci_object_path 
                FROM album_media 
                WHERE file_type = 'video'
                ORDER BY id
            """)
            videos = cursor.fetchall()
        
        total = len(videos)
        logger.info(f"📊 Found {total} videos to process")
        
        success_count = 0
        error_count = 0
        
        for idx, (media_id, file_name, file_path, album_name, oci_object_path) in enumerate(videos, 1):
            try:
                logger.info(f"\n[{idx}/{total}] Processing: {file_name}")
                
                # Download video to temp file
                temp_file = None
                try:
                    # Get presigned URL for OCI object
                    if oci_object_path:
                        download_url = create_presigned_url(oci_object_path)
                        if download_url:
                            logger.info(f"  📥 Downloading from OCI...")
                            response = requests.get(download_url, timeout=60)
                            response.raise_for_status()
                            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                            temp_file.write(response.content)
                            temp_file.close()
                            local_path = temp_file.name
                        else:
                            logger.error(f"  ❌ Failed to create presigned URL")
                            error_count += 1
                            continue
                    elif file_path and file_path.startswith('http'):
                        response = requests.get(file_path, timeout=60)
                        response.raise_for_status()
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                        temp_file.write(response.content)
                        temp_file.close()
                        local_path = temp_file.name
                        logger.info(f"  📥 Downloaded from URL")
                    elif file_path and os.path.exists(file_path):
                        local_path = file_path
                    else:
                        logger.warning(f"  ⚠️  No valid path found")
                        error_count += 1
                        continue
                except Exception as download_error:
                    logger.error(f"  ❌ Download failed: {download_error}")
                    error_count += 1
                    continue
                
                # Generate ImageBind video embedding
                embedding_vector = embedder.generate_video_embedding(local_path)
                
                # Cleanup temp file
                if temp_file:
                    os.unlink(temp_file.name)
                
                if embedding_vector is not None:
                    # Update database with new ImageBind embedding
                    with get_flask_safe_connection() as conn:
                        cursor = conn.cursor()
                        # Convert numpy float32 to Python float
                        embedding_list = [float(x) for x in embedding_vector]
                        embedding_json = json.dumps(embedding_list)
                        cursor.execute(
                            "UPDATE album_media SET embedding_vector = TO_VECTOR(:embedding) WHERE id = :id",
                            {'embedding': embedding_json, 'id': media_id}
                        )
                        conn.commit()
                    
                    success_count += 1
                    logger.info(f"  ✅ Updated embedding (dim: {len(embedding_vector)})")
                else:
                    logger.error(f"  ❌ Failed to generate embedding")
                    error_count += 1
                
                # Progress update every 5 videos
                if idx % 5 == 0:
                    logger.info(f"\n📊 Progress: {idx}/{total} ({success_count} success, {error_count} errors)")
                
            except Exception as e:
                logger.error(f"  ❌ Error processing {file_name}: {e}")
                error_count += 1
                continue
        
        logger.info("\n" + "=" * 80)
        logger.info(f"📊 VIDEO EMBEDDING REGENERATION COMPLETE")
        logger.info(f"   ✅ Success: {success_count}/{total}")
        logger.info(f"   ❌ Errors: {error_count}/{total}")
        logger.info("=" * 80)
        
        return success_count, error_count
        
    except Exception as e:
        logger.error(f"❌ Fatal error in video regeneration: {e}")
        raise

if __name__ == "__main__":
    start_time = time.time()
    
    try:
        logger.info("\n" + "=" * 80)
        logger.info("🚀 STARTING IMAGEBIND EMBEDDING REGENERATION")
        logger.info("=" * 80)
        
        # Regenerate photo embeddings
        photo_success, photo_errors = regenerate_photo_embeddings()
        
        # Regenerate video embeddings
        video_success, video_errors = regenerate_video_embeddings()
        
        elapsed = time.time() - start_time
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 ALL EMBEDDINGS REGENERATED WITH IMAGEBIND")
        logger.info(f"   📸 Photos: {photo_success} success, {photo_errors} errors")
        logger.info(f"   🎬 Videos: {video_success} success, {video_errors} errors")
        logger.info(f"   ⏱️  Total time: {elapsed:.1f} seconds")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"\n❌ FATAL ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
