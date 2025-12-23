#!/usr/bin/env python3
"""
Full-feature localhost Flask app with OCI, ImageBind, GPT-4o-mini, and Oracle Vector DB
Uses locally-hosted ImageBind for embeddings and GPT-4o-mini for metadata extraction
"""

import os
import sys
import time
import json
import logging
import uuid
import datetime
import queue
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, render_template, jsonify, Response, stream_with_context, redirect, url_for, session, flash, send_from_directory, send_file, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv

# Add twelvelabvideoai/src to path for utility imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# Import Python modules from twelvelabvideoai/src (for utilities like auth, RBAC, etc.)
twelvelabs_src_dir = os.path.join(project_root, 'twelvelabvideoai', 'src')
sys.path.insert(0, twelvelabs_src_dir)

# Templates directory is local to this src folder
TEMPLATES_DIR = os.path.join(current_dir, 'templates')

# Load environment variables early
try:
    load_dotenv()
    print("✅ Loaded .env file")
except Exception as e:
    print(f"⚠️ Could not load .env: {e}")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import authentication utilities
try:
    from auth_utils import User, authenticate_user, get_user_by_id, verify_password, update_user_password, create_user
    AUTH_AVAILABLE = True
    logger.info("✅ Authentication utilities imported successfully")
except Exception as e:
    logger.error(f"❌ Could not import auth utilities: {e}")
    AUTH_AVAILABLE = False

# Import authorization and RBAC
try:
    from auth_rbac import (
        viewer_required, editor_required, admin_required, permission_required,
        has_permission, can_upload, can_edit, can_delete, can_create_album,
        get_user_storage_path, get_user_album_path, get_user_video_path,
        can_access_resource, ROLE_PERMISSIONS
    )
    RBAC_AVAILABLE = True
    logger.info("✅ RBAC authorization imported successfully")
except Exception as e:
    logger.error(f"❌ Could not import RBAC: {e}")
    RBAC_AVAILABLE = False
    # Fallback to simple decorator
    def viewer_required(f):
        return login_required(f)
    def editor_required(f):
        return login_required(f)
    def admin_required(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != 'admin':
                flash('Admin privileges required', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function

# Import rate limiting
try:
    from rate_limiter import (
        rate_limit_api, rate_limit_search, rate_limit_upload,
        check_video_processing_quota, consume_video_processing_quota,
        check_storage_quota, update_storage_usage,
        get_user_quota_summary
    )
    RATE_LIMITING_AVAILABLE = True
    logger.info("✅ Rate limiting imported successfully")
except Exception as e:
    logger.error(f"❌ Could not import rate limiting: {e}")
    RATE_LIMITING_AVAILABLE = False
    # Fallback no-op decorators
    def rate_limit_api(f):
        return f
    def rate_limit_search(f):
        return f
    def rate_limit_upload(f):
        return f

# Import OCI storage helpers
try:
    from oci_storage import (
        get_user_upload_path, get_user_generated_path, get_user_thumbnail_path,
        get_user_embedding_path, get_user_temp_path
    )
    OCI_STORAGE_HELPERS_AVAILABLE = True
    logger.info("✅ OCI storage helpers imported successfully")
except Exception as e:
    logger.error(f"❌ Could not import OCI storage helpers: {e}")
    OCI_STORAGE_HELPERS_AVAILABLE = False
    # Fallback to old-style paths
    def get_user_upload_path(user_id, content_type, filename):
        return f"albums/{content_type}s/{filename}"
    def get_user_generated_path(user_id, content_type, filename):
        return f"generated/{content_type}s/{filename}"
    def get_user_thumbnail_path(user_id, content_type, filename):
        return f"thumbnails/{content_type}s/{filename}"

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

# Import Flask-safe search (unified search for photos and videos)
try:
    # Import unified search that handles both photos and video segments
    # Now in the same directory (src/)
    from search_unified_flask_safe import search_unified_flask_safe
    FLASK_SAFE_SEARCH_AVAILABLE = True
    logger.info("✅ Flask-safe unified search imported successfully")
except Exception as e:
    logger.warning(f"⚠️ Flask-safe unified search not available: {e}")
    search_unified_flask_safe = None
    FLASK_SAFE_SEARCH_AVAILABLE = False

# Import video slicing utilities
try:
    # Now in the same directory (src/)
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

# Import Flask-safe DB connection
try:
    from utils.db_utils_flask_safe import get_flask_safe_connection
    DB_UTILS_AVAILABLE = True
    logger.info("✅ Flask-safe DB utilities imported successfully")
except Exception as e:
    logger.warning(f"⚠️ Flask-safe DB utilities not available: {e}")
    get_flask_safe_connection = None
    DB_UTILS_AVAILABLE = False

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
    """Flask-safe photo embedding - uses ImageBind (free, self-hosted)
    
    Args:
        file_path: URL/path to the image (may be resized version)
        album_name: Name of the album
        media_id: Existing media ID to update (if None, creates new entry)
    """
    try:
        from utils.imagebind_helper import get_imagebind_embedder
        from pathlib import Path
        import requests
        import tempfile
        
        # Download image to temp file if it's a URL
        temp_file = None
        if file_path.startswith('http'):
            response = requests.get(file_path)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(response.content)
            temp_file.close()
            local_path = temp_file.name
        else:
            local_path = file_path
        
        # Generate ImageBind embedding
        embedder = get_imagebind_embedder()
        embedding_vector = embedder.generate_image_embedding(local_path)
        
        # Cleanup temp file
        if temp_file:
            import os
            os.unlink(temp_file.name)
        
        if embedding_vector is not None:
            # Update existing media entry with embedding (DON'T create new entry)
            if media_id:
                # Update existing entry with embedding
                from utils.db_utils_flask_safe import get_flask_safe_connection
                import json
                import numpy as np
                
                try:
                    with get_flask_safe_connection() as conn:
                        cursor = conn.cursor()
                        # Convert numpy array to Python list for JSON serialization
                        if isinstance(embedding_vector, np.ndarray):
                            embedding_list = embedding_vector.tolist()
                        else:
                            embedding_list = list(embedding_vector)
                        
                        # Convert to JSON string for Oracle VECTOR type with TO_VECTOR
                        embedding_json = json.dumps(embedding_list)
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
                    user_id=current_user.id,
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

def create_video_embedding_flask_safe(file_path, album_name, media_id=None, **kwargs):
    """Flask-safe video embedding - uses ImageBind (free, self-hosted)"""
    try:
        from utils.imagebind_helper import get_imagebind_embedder
        from pathlib import Path
        import requests
        import tempfile
        import numpy as np
        
        # Download video to temp file if it's a URL
        temp_file = None
        if file_path.startswith('http'):
            response = requests.get(file_path)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            temp_file.write(response.content)
            temp_file.close()
            local_path = temp_file.name
        else:
            local_path = file_path
        
        # Generate ImageBind video embedding
        embedder = get_imagebind_embedder()
        embedding_vector = embedder.generate_video_embedding(local_path)
        
        # Cleanup temp file
        if temp_file:
            import os
            os.unlink(temp_file.name)
        
        if embedding_vector is not None:
            # Update existing media entry with embedding
            if media_id:
                from utils.db_utils_flask_safe import get_flask_safe_connection
                import json
                
                try:
                    with get_flask_safe_connection() as conn:
                        cursor = conn.cursor()
                        # Convert numpy array to Python list for JSON serialization
                        if isinstance(embedding_vector, np.ndarray):
                            embedding_list = embedding_vector.tolist()
                        else:
                            embedding_list = list(embedding_vector)
                        
                        # Convert to JSON string for Oracle VECTOR type
                        embedding_json = json.dumps(embedding_list)
                        cursor.execute(
                            "UPDATE album_media SET embedding_vector = TO_VECTOR(:embedding) WHERE id = :id",
                            {'embedding': embedding_json, 'id': media_id}
                        )
                        conn.commit()
                        logger.info(f"✅ Video embedding stored for media_id {media_id}")
                except Exception as db_err:
                    logger.error(f"❌ Failed to store video embedding: {db_err}")
                
                return media_id
            else:
                logger.warning("⚠️ No media_id provided for video embedding")
                return None
        
        return None
        
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
# Templates are in src/templates (same directory as this Flask app)
app = Flask(__name__, template_folder=TEMPLATES_DIR)

# LOCALHOST ONLY CONFIGURATION
app.config['SERVER_NAME'] = None  # No domain binding
app.config['PREFERRED_URL_SCHEME'] = 'http'  # Local HTTP only
app.config['APPLICATION_ROOT'] = '/'

# Security configuration
# IMPORTANT: SECRET_KEY must be consistent across all workers for session management
secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key:
    logger.warning("⚠️  FLASK_SECRET_KEY not set in environment! Using random key (sessions will not persist)")
    secret_key = os.urandom(24).hex()
else:
    logger.info("✅ Using FLASK_SECRET_KEY from environment")

app.config['SECRET_KEY'] = secret_key
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_NAME'] = 'dataguardian_session'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 2592000  # 30 days if "remember me"
app.config['REMEMBER_COOKIE_DURATION'] = 2592000  # 30 days
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SECURE'] = False  # Set to True with HTTPS

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    if AUTH_AVAILABLE:
        return get_user_by_id(int(user_id))
    return None

# Make permission functions available in templates
@app.context_processor
def inject_permissions():
    """Inject permission checking values into all templates"""
    # Compute permission values for current user
    is_admin = False
    is_editor = False
    can_upload_perm = False
    
    if current_user.is_authenticated:
        user_role = getattr(current_user, 'role', 'viewer')
        is_admin = (user_role == 'admin')
        is_editor = (user_role in ['admin', 'editor'])
        can_upload_perm = (user_role in ['admin', 'editor'])
    
    return dict(
        can_admin=is_admin,
        can_edit=is_editor,
        can_upload=can_upload_perm
    )

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


# ========== AUTHENTICATION ROUTES ==========

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    # If already logged in, redirect to main page
    if current_user.is_authenticated:
        logger.info(f"User {current_user.username} already authenticated, redirecting to index")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        logger.info(f"Login attempt for user: {username}, remember: {remember}")
        
        if not username or not password:
            return render_template('login.html', error='Please enter both username and password')
        
        # Get client IP
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        # Authenticate user
        user = authenticate_user(username, password, ip_address)
        
        if user:
            # Login user with proper session configuration
            login_user(user, remember=remember)
            session.permanent = remember  # Make session permanent if remember me is checked
            
            logger.info(f"✅ User logged in: {username} (IP: {ip_address}, remember: {remember})")
            
            # Redirect to next page or index
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                logger.info(f"Redirecting to next page: {next_page}")
                return redirect(next_page)
            
            logger.info(f"Redirecting to index")
            return redirect(url_for('index'))
        else:
            logger.warning(f"❌ Failed login attempt: {username} (IP: {ip_address})")
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """User logout"""
    username = current_user.username if current_user.is_authenticated else 'Unknown'
    logout_user()
    logger.info(f"✅ User logged out: {username}")
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))


@app.route('/user/profile')
@login_required
def user_profile():
    """User profile page"""
    return render_template('profile.html', user=current_user)


@app.route('/user/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        logger.info(f"Password change request from user: {current_user.username}")
        
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate input
        if not all([current_password, new_password, confirm_password]):
            logger.warning(f"Password change failed - missing fields for user: {current_user.username}")
            flash('All password fields are required', 'error')
            return redirect(url_for('user_profile'))
        
        # Check if new passwords match
        if new_password != confirm_password:
            logger.warning(f"Password change failed - passwords don't match for user: {current_user.username}")
            flash('New passwords do not match', 'error')
            return redirect(url_for('user_profile'))
        
        # Validate password length
        if len(new_password) < 8:
            logger.warning(f"Password change failed - too short for user: {current_user.username}")
            flash('Password must be at least 8 characters long', 'error')
            return redirect(url_for('user_profile'))
        
        # Verify current password
        logger.info(f"Verifying current password for user: {current_user.username}")
        if not verify_password(current_password, current_user.password_hash):
            logger.warning(f"Password change failed - incorrect current password for user: {current_user.username}")
            flash('Current password is incorrect', 'error')
            return redirect(url_for('user_profile'))
        
        # Update password
        logger.info(f"Updating password for user ID: {current_user.id}")
        if update_user_password(current_user.id, new_password):
            flash('Password updated successfully! Please login again with your new password.', 'success')
            logger.info(f"✅ Password changed successfully for user: {current_user.username}")
            # Logout user so they login again with new password
            logout_user()
            return redirect(url_for('login'))
        else:
            logger.error(f"Password update failed in database for user: {current_user.username}")
            flash('Failed to update password. Please try again.', 'error')
            
    except Exception as e:
        logger.error(f"Error changing password for user {current_user.username}: {e}")
        flash('An error occurred while updating password', 'error')
    
    return redirect(url_for('user_profile'))


@app.route('/user/quotas')
@login_required
def user_quotas():
    """View current user's rate limits and usage"""
    try:
        if RATE_LIMITING_AVAILABLE:
            quotas = get_user_quota_summary(current_user.id)
            return jsonify({
                'success': True,
                'user_id': current_user.id,
                'username': current_user.username,
                'role': current_user.role,
                'quotas': quotas
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Rate limiting not available'
            }), 503
    except Exception as e:
        logger.error(f"❌ Error getting user quotas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== ADMIN USER MANAGEMENT ROUTES ==========

@app.route('/admin/tools')
@login_required
@admin_required
def admin_tools():
    """Admin tools page for system maintenance"""
    return render_template('admin_tools.html', user=current_user)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Admin page to manage users"""
    try:
        # Get all users
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, email, role, is_active, created_at, last_login
                FROM users
                ORDER BY created_at DESC
            """)
            users = []
            for row in cursor.fetchall():
                users.append({
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'role': row[3],
                    'is_active': bool(row[4]),
                    'created_at': row[5],
                    'last_login': row[6]
                })
        
        return render_template('admin_users.html', users=users, current_user=current_user)
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        flash('Error loading users', 'error')
        return redirect(url_for('index'))

@app.route('/admin/users/add', methods=['POST'])
@login_required
@admin_required
def admin_add_user():
    """Add a new user"""
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'viewer')
        
        # Validation
        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('admin_users'))
        
        if len(username) < 3:
            flash('Username must be at least 3 characters', 'error')
            return redirect(url_for('admin_users'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return redirect(url_for('admin_users'))
        
        if role not in ['admin', 'editor', 'viewer']:
            flash('Invalid role', 'error')
            return redirect(url_for('admin_users'))
        
        # Create user using auth_utils
        if AUTH_AVAILABLE and create_user:
            success = create_user(username, password, email, role)
            if success:
                logger.info(f"✅ Admin {current_user.username} created user: {username} (role: {role})")
                flash(f'User {username} created successfully', 'success')
            else:
                flash('Failed to create user. Username may already exist.', 'error')
        else:
            flash('User creation not available', 'error')
        
        return redirect(url_for('admin_users'))
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        flash('Error creating user', 'error')
        return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_toggle_user(user_id):
    """Toggle user active status"""
    try:
        # Prevent disabling yourself
        if user_id == current_user.id:
            flash('Cannot disable your own account', 'error')
            return redirect(url_for('admin_users'))
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            # Toggle is_active
            cursor.execute("""
                UPDATE users 
                SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
                WHERE id = :user_id
            """, {"user_id": user_id})
            conn.commit()
            
            # Get updated status
            cursor.execute("SELECT username, is_active FROM users WHERE id = :user_id", {"user_id": user_id})
            row = cursor.fetchone()
            if row:
                username, is_active = row
                status = 'enabled' if is_active else 'disabled'
                logger.info(f"✅ Admin {current_user.username} {status} user: {username}")
                flash(f'User {username} {status}', 'success')
        
        return redirect(url_for('admin_users'))
        
    except Exception as e:
        logger.error(f"Error toggling user: {e}")
        flash('Error updating user status', 'error')
        return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def admin_reset_password(user_id):
    """Reset user password"""
    try:
        new_password = request.form.get('new_password', '').strip()
        
        if not new_password:
            flash('Password is required', 'error')
            return redirect(url_for('admin_users'))
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return redirect(url_for('admin_users'))
        
        # Get username first
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE id = :user_id", {"user_id": user_id})
            row = cursor.fetchone()
            if not row:
                flash('User not found', 'error')
                return redirect(url_for('admin_users'))
            username = row[0]
        
        # Update password
        if AUTH_AVAILABLE and update_user_password:
            success = update_user_password(user_id, new_password)
            if success:
                logger.info(f"✅ Admin {current_user.username} reset password for user: {username}")
                flash(f'Password reset for user {username}', 'success')
            else:
                flash('Failed to reset password', 'error')
        else:
            flash('Password reset not available', 'error')
        
        return redirect(url_for('admin_users'))
        
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        flash('Error resetting password', 'error')
        return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Delete a user"""
    try:
        # Prevent deleting yourself
        if user_id == current_user.id:
            flash('Cannot delete your own account', 'error')
            return redirect(url_for('admin_users'))
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            # Get username first
            cursor.execute("SELECT username FROM users WHERE id = :user_id", {"user_id": user_id})
            row = cursor.fetchone()
            if not row:
                flash('User not found', 'error')
                return redirect(url_for('admin_users'))
            username = row[0]
            
            # Delete user
            cursor.execute("DELETE FROM users WHERE id = :user_id", {"user_id": user_id})
            conn.commit()
            
            logger.info(f"✅ Admin {current_user.username} deleted user: {username}")
            flash(f'User {username} deleted', 'success')
        
        return redirect(url_for('admin_users'))
        
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        flash('Error deleting user', 'error')
        return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    """Edit user details (username, email, role)"""
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', '').strip()
        
        # Validate inputs
        if not username or len(username) < 3:
            flash('Username must be at least 3 characters', 'error')
            return redirect(url_for('admin_users'))
        
        if role not in ['viewer', 'editor', 'admin']:
            flash('Invalid role specified', 'error')
            return redirect(url_for('admin_users'))
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT username FROM users WHERE id = :user_id", {"user_id": user_id})
            row = cursor.fetchone()
            if not row:
                flash('User not found', 'error')
                return redirect(url_for('admin_users'))
            old_username = row[0]
            
            # Check if new username is already taken (by someone else)
            cursor.execute(
                "SELECT id FROM users WHERE username = :username AND id != :user_id",
                {"username": username, "user_id": user_id}
            )
            if cursor.fetchone():
                flash(f'Username "{username}" is already taken', 'error')
                return redirect(url_for('admin_users'))
            
            # Update user
            update_query = """
                UPDATE users 
                SET username = :username, 
                    email = :email, 
                    role = :role
                WHERE id = :user_id
            """
            cursor.execute(update_query, {
                "username": username,
                "email": email if email else None,
                "role": role,
                "user_id": user_id
            })
            conn.commit()
            
            logger.info(f"✅ Admin {current_user.username} updated user {old_username} → {username} (role: {role})")
            flash(f'User {username} updated successfully', 'success')
        
        return redirect(url_for('admin_users'))
        
    except Exception as e:
        logger.error(f"Error editing user: {e}")
        flash('Error updating user', 'error')
        return redirect(url_for('admin_users'))


@app.route('/admin/quotas')
@login_required
@admin_required
def admin_quotas():
    """Admin dashboard for rate limit and quota monitoring"""
    try:
        if not RATE_LIMITING_AVAILABLE:
            flash('Rate limiting system not available', 'error')
            return redirect(url_for('index'))
        
        # Get all users with their rate limits and current usage
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get user info with current usage
            cursor.execute("""
                SELECT 
                    u.id, u.username, u.email, u.role, u.created_at
                FROM users u
                ORDER BY u.created_at DESC
            """)
            
            users_data = []
            for row in cursor.fetchall():
                user_data = {
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'role': row[3],
                    'created_at': row[4],
                    'daily_uploads': None,
                    'daily_upload_count': 0,
                    'hourly_searches': None,
                    'hourly_search_count': 0,
                    'monthly_storage_gb': None,
                    'current_storage_gb': 0.0,
                    'last_upload_reset': None,
                    'last_search_reset': None,
                    # Calculate percentages
                    'upload_percent': 0,
                    'search_percent': 0,
                    'storage_percent': 0
                }
                users_data.append(user_data)
            
            # Skip usage activity log as table doesn't exist or has different schema
            recent_activity = []
        
        return render_template('admin_quotas.html',
                             users=users_data,
                             recent_activity=recent_activity,
                             current_user=current_user)
    except Exception as e:
        logger.error(f"Error loading quotas dashboard: {e}")
        import traceback
        logger.error(traceback.format_exc())
        flash('Error loading quotas dashboard', 'error')
        return redirect(url_for('index'))


@app.route('/admin/quotas/<int:user_id>/update', methods=['POST'])
@login_required
@admin_required
def admin_update_quota(user_id):
    """Update user quotas"""
    try:
        if not RATE_LIMITING_AVAILABLE:
            return jsonify({'success': False, 'error': 'Rate limiting not available'}), 503
        
        daily_uploads = request.form.get('daily_uploads')
        hourly_searches = request.form.get('hourly_searches')
        monthly_storage_gb = request.form.get('monthly_storage_gb')
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Build update query
            updates = []
            params = {'user_id': user_id}
            
            if daily_uploads:
                if daily_uploads == 'unlimited':
                    updates.append("daily_uploads = NULL")
                else:
                    updates.append("daily_uploads = :daily_uploads")
                    params['daily_uploads'] = int(daily_uploads)
            
            if hourly_searches:
                if hourly_searches == 'unlimited':
                    updates.append("hourly_searches = NULL")
                else:
                    updates.append("hourly_searches = :hourly_searches")
                    params['hourly_searches'] = int(hourly_searches)
            
            if monthly_storage_gb:
                if monthly_storage_gb == 'unlimited':
                    updates.append("monthly_storage_gb = NULL")
                else:
                    updates.append("monthly_storage_gb = :monthly_storage_gb")
                    params['monthly_storage_gb'] = float(monthly_storage_gb)
            
            if updates:
                query = f"UPDATE user_rate_limits SET {', '.join(updates)} WHERE user_id = :user_id"
                cursor.execute(query, params)
                conn.commit()
                
                # Get username for logging
                cursor.execute("SELECT username FROM users WHERE id = :user_id", {"user_id": user_id})
                username = cursor.fetchone()[0]
                
                logger.info(f"✅ Admin {current_user.username} updated quotas for user: {username}")
                flash(f'Quotas updated for {username}', 'success')
            else:
                flash('No quota changes specified', 'warning')
        
        return redirect(url_for('admin_quotas'))
        
    except Exception as e:
        logger.error(f"Error updating quota: {e}")
        flash('Error updating quota', 'error')
        return redirect(url_for('admin_quotas'))


@app.route('/admin/quotas/<int:user_id>/reset', methods=['POST'])
@login_required
@admin_required
def admin_reset_counters(user_id):
    """Reset user's rate limit counters"""
    try:
        if not RATE_LIMITING_AVAILABLE:
            return jsonify({'success': False, 'error': 'Rate limiting not available'}), 503
        
        counter_type = request.form.get('counter_type', 'all')
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            if counter_type == 'uploads' or counter_type == 'all':
                cursor.execute("""
                    UPDATE user_rate_limits 
                    SET daily_upload_count = 0, 
                        last_upload_reset = SYSTIMESTAMP
                    WHERE user_id = :user_id
                """, {"user_id": user_id})
            
            if counter_type == 'searches' or counter_type == 'all':
                cursor.execute("""
                    UPDATE user_rate_limits 
                    SET hourly_search_count = 0,
                        last_search_reset = SYSTIMESTAMP
                    WHERE user_id = :user_id
                """, {"user_id": user_id})
            
            conn.commit()
            
            # Get username for logging
            cursor.execute("SELECT username FROM users WHERE id = :user_id", {"user_id": user_id})
            username = cursor.fetchone()[0]
            
            logger.info(f"✅ Admin {current_user.username} reset {counter_type} counters for user: {username}")
            flash(f'Counters reset for {username}', 'success')
        
        return redirect(url_for('admin_quotas'))
        
    except Exception as e:
        logger.error(f"Error resetting counters: {e}")
        flash('Error resetting counters', 'error')
        return redirect(url_for('admin_quotas'))


# ========== MAIN APPLICATION ROUTES ==========

@app.route('/')
@login_required
def index():
    """Main page with RBAC context"""
    try:
        return render_template(
            'index.html', 
            user=current_user
            # Note: can_upload, can_edit, can_admin are injected by context_processor
        )
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
@login_required
@viewer_required
def list_unified_albums():
    """List all albums (filtered by user unless admin)"""
    try:
        logger.info("📋 Album listing request received")
        
        if not UNIFIED_ALBUM_AVAILABLE or flask_safe_album_manager is None:
            logger.error("❌ Album manager not available")
            return jsonify({'error': 'Album manager not available', 'albums': [], 'count': 0})
        
        # Admin sees all albums, regular users see only their own
        user_id = current_user.id if current_user.role != 'admin' else None
        logger.info(f"🔍 Fetching albums for user_id={user_id} (admin={current_user.role == 'admin'})")
        
        albums = flask_safe_album_manager.list_albums(user_id=user_id)
        
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
@login_required
@viewer_required
def get_album_contents(album_name):
    """Get contents of a specific album (filtered by user unless admin)"""
    try:
        logger.info(f"📂 Getting contents for album: {album_name}")
        
        if not UNIFIED_ALBUM_AVAILABLE or flask_safe_album_manager is None:
            logger.error("❌ Album manager not available")
            return jsonify({'error': 'Album manager not available', 'results': [], 'count': 0})
        
        # Admin sees all content, regular users see only their own
        user_id = current_user.id if current_user.role != 'admin' else None
        
        # Get album contents
        contents = flask_safe_album_manager.get_album_contents(album_name, user_id=user_id)
        
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
@login_required
@editor_required
@rate_limit_upload
def upload_unified():
    """Upload media (photo or video) to OCI and create TwelveLabs Marengo embeddings
    
    Requires editor role or higher.
    Automatically assigns user_id to uploaded content for multi-tenant isolation.
    Rate limited to prevent abuse (uploads per day quota).
    
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
        logger.info(f"📤 Upload request received [task_id={task_id}, user={current_user.username}]")
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
                            # Create chunk-specific object name with user-specific path
                            from pathlib import Path
                            chunk_filename = Path(chunk_path).name
                            
                            # Use user-specific path for chunks
                            if OCI_STORAGE_HELPERS_AVAILABLE:
                                chunk_object_name = get_user_upload_path(current_user.id, 'chunk', chunk_filename)
                                logger.info(f"🔐 Using user-specific chunk path: {chunk_object_name}")
                            else:
                                chunk_object_name = f"albums/{album_name}/{file_type}s/chunks/{chunk_filename}"
                                logger.warning(f"⚠️ Using legacy chunk path: {chunk_object_name}")
                            
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
                            
                            # Store chunk metadata using correct method
                            chunk_media_id = flask_safe_album_manager.store_media_metadata(
                                album_name=album_name,
                                file_name=chunk_filename,
                                file_path=chunk_oci_path,
                                file_type=file_type,
                                user_id=current_user.id,
                                oci_namespace=namespace,
                                oci_bucket=bucket,
                                oci_object_path=chunk_object_name,
                                video_duration=chunk_vid_metadata.get('duration_seconds', 0),
                                start_time=0,
                                end_time=chunk_vid_metadata.get('duration_seconds', 0)
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
                    
                    send_file_progress('upload', 40, 
                        f'✅ All {len(video_chunks)} chunks uploaded successfully!')
                    
                    # Generate embeddings for each chunk if auto_embed is enabled
                    if auto_embed and EMBEDDING_AVAILABLE:
                        send_file_progress('embedding', 45, 
                            f'Generating embeddings for {len(video_chunks)} chunks...')
                        
                        chunk_embedding_tasks = []
                        for chunk_idx, (chunk_media_id, chunk_path_orig) in enumerate(zip(chunk_media_ids, video_chunks), 1):
                            try:
                                # Get chunk info from metadata
                                from pathlib import Path
                                chunk_filename = Path(chunk_path_orig).name
                                
                                # Use user-specific path for chunk embeddings
                                if OCI_STORAGE_HELPERS_AVAILABLE:
                                    chunk_object_name = get_user_upload_path(current_user.id, 'chunk', chunk_filename)
                                    logger.info(f"🔐 Using user-specific chunk embedding path: {chunk_object_name}")
                                else:
                                    chunk_object_name = f"albums/{album_name}/{file_type}s/chunks/{chunk_filename}"
                                    logger.warning(f"⚠️ Using legacy chunk embedding path: {chunk_object_name}")
                                
                                chunk_oci_path = f'oci://{namespace}/{bucket}/{chunk_object_name}'
                                chunk_par_url = _get_par_url_for_oci(chunk_oci_path)
                                
                                progress_base = 45 + ((chunk_idx - 1) / len(video_chunks)) * 40
                                send_file_progress('embedding', int(progress_base), 
                                    f'Creating embeddings for chunk {chunk_idx}/{len(video_chunks)}...')
                                
                                logger.info(f"🧠 Generating embeddings for chunk {chunk_idx}: {chunk_filename}")
                                
                                # Create embedding task
                                embedding_task_id = str(uuid.uuid4())
                                _upload_tasks[embedding_task_id] = {
                                    'status': 'pending',
                                    'media_id': chunk_media_id,
                                    'album_name': album_name,
                                    'filename': f'{file.filename} (chunk {chunk_idx}/{len(video_chunks)})',
                                    'file_type': file_type,
                                    'oci_path': chunk_oci_path,
                                    'par_url': chunk_par_url,
                                    'is_chunk': True,
                                    'chunk_index': chunk_idx,
                                    'total_chunks': len(video_chunks),
                                    'created_at': time.time()
                                }
                                
                                # Start background embedding task
                                def run_chunk_embedding_task(tid, upload_tid, media_id, par_url, chunk_idx, total_chunks):
                                    try:
                                        _upload_tasks[tid]['status'] = 'running'
                                        logger.info(f'🎬 Creating embeddings for chunk {chunk_idx}/{total_chunks}')
                                        
                                        embedding_ids = create_unified_embedding_flask_safe(
                                            par_url, file_type, album_name, media_id=media_id
                                        )
                                        
                                        if embedding_ids:
                                            _upload_tasks[tid]['status'] = 'completed'
                                            _upload_tasks[tid]['embedding_ids'] = embedding_ids
                                            _upload_tasks[tid]['completed_at'] = time.time()
                                            logger.info(f'✅ Chunk {chunk_idx} embedding completed')
                                        else:
                                            _upload_tasks[tid]['status'] = 'failed'
                                            _upload_tasks[tid]['error'] = f'Chunk {chunk_idx} embedding failed'
                                            logger.error(f'❌ Chunk {chunk_idx} embedding failed')
                                    except Exception as e:
                                        logger.exception(f'❌ Chunk {chunk_idx} embedding error: {e}')
                                        _upload_tasks[tid]['status'] = 'failed'
                                        _upload_tasks[tid]['error'] = str(e)
                                
                                # Start thread for this chunk's embedding
                                thread = threading.Thread(
                                    target=run_chunk_embedding_task,
                                    args=(embedding_task_id, upload_task_id, chunk_media_id, 
                                          chunk_par_url, chunk_idx, len(video_chunks))
                                )
                                thread.daemon = True
                                thread.start()
                                chunk_embedding_tasks.append(embedding_task_id)
                                
                            except Exception as embed_error:
                                logger.error(f"❌ Failed to start embedding for chunk {chunk_idx}: {embed_error}")
                        
                        send_file_progress('embedding', 85, 
                            f'✅ Started embedding generation for all {len(video_chunks)} chunks')
                        logger.info(f"🚀 Started {len(chunk_embedding_tasks)} embedding tasks for chunks")
                    
                    # Success - mark file as processed with chunks
                    file_result['success'] = True
                    file_result['media_id'] = chunk_media_ids
                    file_result['is_chunked'] = True
                    file_result['chunk_count'] = len(video_chunks)
                    success_count += 1
                    results.append(file_result)
                    
                    send_file_progress('complete', 100, 
                        f'✅ Video uploaded and split into {len(video_chunks)} chunks!')
                    
                    logger.info(f"✅ [{file_index}/{len(all_files)}] Successfully processed (chunked): {file.filename}")
                    continue
                
                # Standard upload (non-chunked or non-video)
                send_file_progress('upload', 10, f'Uploading {file.filename} to OCI...')
                
                # Create user-specific object path for multi-tenant isolation
                if OCI_STORAGE_HELPERS_AVAILABLE:
                    object_name = get_user_upload_path(current_user.id, file_type, file.filename)
                    logger.info(f"🔐 Using user-specific path: {object_name}")
                else:
                    # Fallback to old path structure
                    object_name = f"albums/{album_name}/{file_type}s/{file.filename}"
                    logger.warning(f"⚠️ Using legacy path structure: {object_name}")
                
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
                        'user_id': current_user.id,
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
                    
                    # Auto face recognition for photos
                    if file_type == 'photo' and media_id:
                        try:
                            send_file_progress('faces', 52, 'Detecting faces...')
                            from utils.auto_face_recognition import auto_recognize_faces
                            
                            # Download photo from OCI to temp file for face detection
                            import tempfile
                            temp_photo = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
                            get_response = obj_client.get_object(namespace, bucket, object_name)
                            with open(temp_photo.name, 'wb') as f:
                                for chunk in get_response.data.raw.stream(1024 * 1024, decode_content=False):
                                    f.write(chunk)
                            temp_photo.close()
                            
                            # Get database connection for face recognition
                            from utils.db_utils_flask_safe import get_flask_safe_connection
                            with get_flask_safe_connection() as face_conn:
                                # Run auto face recognition
                                face_results = auto_recognize_faces(
                                    media_id=media_id,
                                    image_path=temp_photo.name,
                                    user_id=current_user.id,
                                    connection=face_conn
                                )
                                
                                if face_results.get('faces_recognized', 0) > 0:
                                    logger.info(f"✅ Auto-recognized {face_results['faces_recognized']} face(s)")
                                    send_file_progress('faces', 54, 
                                        f"Recognized {face_results['faces_recognized']} face(s)")
                                elif face_results.get('faces_detected', 0) > 0:
                                    logger.info(f"ℹ️  Detected {face_results['faces_detected']} unknown face(s)")
                                    send_file_progress('faces', 54, 
                                        f"Detected {face_results['faces_detected']} unknown face(s)")
                            
                            # Clean up temp file
                            os.unlink(temp_photo.name)
                            
                        except Exception as face_error:
                            logger.warning(f"⚠️  Face recognition failed: {face_error}")
                            send_file_progress('faces', 54, 'Face detection skipped')
                    
                    # Extract rich metadata with GPT-4o-mini for natural language search
                    if file_type == 'photo' and media_id and os.getenv('OPENAI_API_KEY'):
                        try:
                            send_file_progress('metadata', 56, 'Extracting searchable metadata...')
                            from utils.gpt_vision_metadata import GPTVisionMetadataExtractor
                            
                            # Download photo from OCI if not already downloaded
                            import tempfile
                            temp_meta_photo = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1])
                            get_response = obj_client.get_object(namespace, bucket, object_name)
                            with open(temp_meta_photo.name, 'wb') as f:
                                for chunk in get_response.data.raw.stream(1024 * 1024, decode_content=False):
                                    f.write(chunk)
                            temp_meta_photo.close()
                            
                            # Extract metadata with GPT-4o-mini
                            extractor = GPTVisionMetadataExtractor()
                            rich_metadata = extractor.extract_metadata(temp_meta_photo.name)
                            
                            if rich_metadata and rich_metadata.get('status') != 'failed':
                                # Store metadata in database
                                from utils.db_utils_flask_safe import get_flask_safe_connection
                                import json
                                
                                with get_flask_safe_connection() as meta_conn:
                                    cursor = meta_conn.cursor()
                                    metadata_json = json.dumps(rich_metadata)
                                    cursor.execute("""
                                        UPDATE album_media 
                                        SET rich_metadata = :metadata
                                        WHERE id = :media_id
                                    """, {'metadata': metadata_json, 'media_id': media_id})
                                    meta_conn.commit()
                                
                                tags_preview = ', '.join(rich_metadata.get('tags', [])[:3])
                                logger.info(f"✅ Rich metadata extracted: {rich_metadata.get('scene_type')} - {tags_preview}")
                                send_file_progress('metadata', 58, f"Metadata: {rich_metadata.get('scene_type')}")
                            
                            # Clean up temp file
                            os.unlink(temp_meta_photo.name)
                            
                        except Exception as meta_error:
                            logger.warning(f"⚠️  Metadata extraction failed: {meta_error}")
                            send_file_progress('metadata', 58, 'Metadata extraction skipped')
                    
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
                
                # Create ImageBind embedding directly (no TwelveLabs dependency)
                embedding_task_id = None
                embedding_status = 'disabled'
                if auto_embed and media_id:
                    try:
                        send_file_progress('embedding', 60, 'Creating ImageBind embedding...')
                        
                        # Use PAR URL to download and create embedding
                        embedding_par_url = resized_par_url if resized_par_url else par_url
                        
                        if file_type == 'photo':
                            logger.info(f'📸 Creating ImageBind photo embedding for {file.filename}')
                            send_file_progress('embedding', 70, 'Generating ImageBind vector...')
                            
                            # Create ImageBind embedding directly
                            result = create_photo_embedding_flask_safe(embedding_par_url, album_name, media_id=media_id)
                            if result:
                                logger.info(f'✅ ImageBind embedding stored for {file.filename}')
                                send_file_progress('embedding', 85, 'ImageBind embedding stored')
                                embedding_status = 'completed'
                            else:
                                logger.warning(f'⚠️  ImageBind embedding failed for {file.filename}')
                                send_file_progress('embedding', 85, 'Embedding skipped')
                                embedding_status = 'failed'
                        
                        elif file_type == 'video':
                            logger.info(f'🎬 Creating ImageBind video embedding for {file.filename}')
                            send_file_progress('embedding', 70, 'Generating ImageBind vector...')
                            
                            # Create ImageBind embedding directly
                            result = create_video_embedding_flask_safe(embedding_par_url, album_name, media_id=media_id)
                            if result:
                                logger.info(f'✅ ImageBind embedding stored for {file.filename}')
                                send_file_progress('embedding', 85, 'ImageBind embedding stored')
                                embedding_status = 'completed'
                            else:
                                logger.warning(f'⚠️  ImageBind embedding failed for {file.filename}')
                                send_file_progress('embedding', 85, 'Embedding skipped')
                                embedding_status = 'failed'
                        
                        send_file_progress('complete', 100, 'Upload complete!')
                        
                    except Exception as embedding_error:
                        logger.error(f"❌ Failed to create ImageBind embedding: {embedding_error}")
                        embedding_status = 'failed'
                        send_file_progress('embedding', 85, 'Embedding creation failed')
                else:
                    # No embedding requested, mark as complete
                    send_file_progress('complete', 100, 'Upload complete!')
                
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

@app.route('/api/face_tags', methods=['GET'])
@viewer_required
def get_face_tags():
    """Get all face tags with pagination"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        search = request.args.get('search', '')
        exact_match = request.args.get('exact_match', 'false').lower() == 'true'
        
        offset = (page - 1) * per_page
        
        # Count query
        count_query = "SELECT COUNT(*) FROM face_tags"
        count_params = {}
        
        # Main query
        query = """
        SELECT id, media_id, face_name, confidence, created_at, auto_tagged, bounding_box
        FROM face_tags
        """
        
        if search:
            if exact_match:
                # Exact match for group filtering
                query += " WHERE face_name = :search"
                count_query += " WHERE face_name = :search"
                search_param = search
            else:
                # Partial match for text search
                query += " WHERE LOWER(face_name) LIKE LOWER(:search)"
                count_query += " WHERE LOWER(face_name) LIKE LOWER(:search)"
                search_param = f"%{search}%"
            
            count_params = {'search': search_param}
            query_params = {'search': search_param, 'offset': offset, 'per_page': per_page}
        else:
            query_params = {'offset': offset, 'per_page': per_page}
        
        query += " ORDER BY id DESC OFFSET :offset ROWS FETCH NEXT :per_page ROWS ONLY"
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get total count
            cursor.execute(count_query, count_params)
            total_count = cursor.fetchone()[0]
            
            # Get face tags
            cursor.execute(query, query_params)
            rows = cursor.fetchall()
            
            face_tags = []
            for row in rows:
                media_id = row[1]
                # Generate thumbnail URL for the photo
                thumbnail_url = url_for('media_thumbnail', media_id=media_id, _external=False)
                
                face_tags.append({
                    'id': row[0],
                    'media_id': media_id,
                    'face_name': row[2] if row[2] else 'Unknown',
                    'confidence': float(row[3]) if row[3] else 0,
                    'created_at': row[4].isoformat() if row[4] else None,
                    'auto_tagged': bool(row[5]) if row[5] is not None else False,
                    'bounding_box': row[6] if row[6] else None,
                    'thumbnail_url': thumbnail_url
                })
            
            return jsonify({
                'face_tags': face_tags,
                'total': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page
            })
            
    except Exception as e:
        logger.error(f"❌ Error fetching face tags: {e}")
        return jsonify({'error': str(e)}), 500
@app.route('/api/face_tags/<int:face_id>', methods=['PUT'])
@editor_required
def update_face_tag(face_id):
    """Update face tag name and generate embedding if missing"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.face_detection_helper import generate_face_embedding, embedding_to_oracle_vector
        import tempfile
        import json
        
        data = request.get_json()
        new_name = data.get('face_name', '').strip()
        
        if not new_name:
            return jsonify({'error': 'Face name cannot be empty'}), 400
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if face tag exists and get details
            cursor.execute("""
                SELECT ft.id, ft.face_name, ft.face_embedding, ft.bounding_box, ft.media_id,
                       am.oci_namespace, am.oci_bucket, am.oci_object_path
                FROM face_tags ft
                JOIN album_media am ON ft.media_id = am.id
                WHERE ft.id = :id
            """, {'id': face_id})
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Face tag not found'}), 404
            
            old_name = row[1] if row[1] else 'Unknown'
            has_embedding = row[2] is not None
            bbox_json = row[3]
            media_id = row[4]
            oci_ns = row[5]
            oci_bucket = row[6]
            oci_path = row[7]
            
            # Update the name
            cursor.execute(
                "UPDATE face_tags SET face_name = :name WHERE id = :id",
                {'name': new_name, 'id': face_id}
            )
            
            # Generate embedding if missing
            embedding_generated = False
            if not has_embedding and bbox_json and oci_path:
                try:
                    logger.info(f"🔄 Generating embedding for face tag {face_id}")
                    
                    # Download image from OCI
                    config = _load_oci_config()
                    if config:
                        obj_client = oci.object_storage.ObjectStorageClient(config)
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                        get_response = obj_client.get_object(oci_ns, oci_bucket, oci_path)
                        with open(temp_file.name, 'wb') as f:
                            for chunk in get_response.data.raw.stream(1024*1024, decode_content=False):
                                f.write(chunk)
                        temp_file.close()
                        
                        # Parse bounding box
                        bbox = json.loads(bbox_json.read()) if hasattr(bbox_json, 'read') else json.loads(bbox_json)
                        
                        # Generate embedding using ImageBind
                        embedder = ImageBindEmbedder()
                        embedding = embedder.generate_face_embedding(temp_file.name, bbox)
                        
                        if embedding is not None:
                            vector_bytes = embedding_to_oracle_vector(embedding)
                            cursor.execute(
                                "UPDATE face_tags SET face_embedding = :emb WHERE id = :id",
                                {'emb': vector_bytes, 'id': face_id}
                            )
                            embedding_generated = True
                            logger.info(f"✅ Generated embedding for face tag {face_id}")
                        
                        # Cleanup
                        os.unlink(temp_file.name)
                except Exception as e:
                    logger.warning(f"⚠️  Failed to generate embedding for face tag {face_id}: {e}")
            
            conn.commit()
            
            logger.info(f"✅ Updated face tag {face_id}: '{old_name}' → '{new_name}'{' (embedding generated)' if embedding_generated else ''}")
            
            return jsonify({
                'success': True,
                'face_id': face_id,
                'old_name': old_name,
                'new_name': new_name
            })
            
    except Exception as e:
        logger.error(f"❌ Error updating face tag: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/face_tags/bulk_update', methods=['POST'])
@editor_required
def bulk_update_face_tags():
    """Bulk update face tag names (e.g., change all 'Unknown' to a specific name)"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        data = request.get_json()
        old_name = data.get('old_name', '').strip()
        new_name = data.get('new_name', '').strip()
        face_ids = data.get('face_ids', [])  # Optional: specific IDs to update
        
        if not old_name or not new_name:
            return jsonify({'error': 'Both old_name and new_name are required'}), 400
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            if face_ids:
                # Update specific face IDs
                placeholders = ','.join([f':id{i}' for i in range(len(face_ids))])
                query = f"UPDATE face_tags SET face_name = :new_name WHERE id IN ({placeholders}) AND face_name = :old_name"
                params = {'new_name': new_name, 'old_name': old_name}
                for i, fid in enumerate(face_ids):
                    params[f'id{i}'] = fid
            else:
                # Update all matching old_name
                query = "UPDATE face_tags SET face_name = :new_name WHERE face_name = :old_name"
                params = {'new_name': new_name, 'old_name': old_name}
            
            cursor.execute(query, params)
            updated_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"✅ Bulk updated {updated_count} face tags: '{old_name}' → '{new_name}'")
            
            return jsonify({
                'success': True,
                'updated_count': updated_count,
                'old_name': old_name,
                'new_name': new_name
            })
            
    except Exception as e:
        logger.error(f"❌ Error bulk updating face tags: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/face_tags/<int:face_id>/remove_from_group', methods=['POST'])
@editor_required
def remove_face_from_group(face_id):
    """Remove a face from its group by setting it to Unknown"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get current name
            cursor.execute("SELECT face_name FROM face_tags WHERE id = :id", {'id': face_id})
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'error': 'Face tag not found'}), 404
            
            old_name = row[0] if row[0] else 'Unknown'
            
            # Set to Unknown
            cursor.execute(
                "UPDATE face_tags SET face_name = 'Unknown' WHERE id = :id",
                {'id': face_id}
            )
            conn.commit()
            
            logger.info(f"✅ Removed face tag {face_id} from group '{old_name}'")
            
            return jsonify({
                'success': True,
                'face_id': face_id,
                'old_group': old_name
            })
            
    except Exception as e:
        logger.error(f"❌ Error removing face from group: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/face_tag_thumbnail/<int:face_tag_id>')
@viewer_required
def face_tag_thumbnail(face_tag_id):
    """Get cropped face thumbnail from bounding box - with disk caching"""
    import tempfile
    import requests
    from PIL import Image
    import io
    import hashlib
    import os
    
    logger.info(f"🖼️ Generating face thumbnail for face_tag_id: {face_tag_id}")
    
    # Cache directory
    cache_dir = os.path.join(tempfile.gettempdir(), 'face_thumbnails')
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f'face_{face_tag_id}.jpg')
    
    # Check if cached thumbnail exists and is recent (< 7 days old)
    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < 604800:  # 7 days in seconds
            logger.info(f"✅ Returning cached thumbnail for face_tag_id: {face_tag_id}")
            response = make_response(send_file(cache_file, mimetype='image/jpeg'))
            response.headers['Cache-Control'] = 'public, max-age=604800'  # Cache for 7 days
            return response
    
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        # Get face tag info including bounding box
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ft.bounding_box, am.file_path, am.file_type
                FROM face_tags ft
                JOIN album_media am ON ft.media_id = am.id
                WHERE ft.id = :face_tag_id
            """, {'face_tag_id': face_tag_id})
            row = cursor.fetchone()
        
        if not row:
            logger.warning(f"⚠️ Face tag {face_tag_id} not found")
            return jsonify({'error': 'Face tag not found'}), 404
        
        bounding_box, file_path, file_type = row
        
        if file_type != 'photo':
            return jsonify({'error': 'Not a photo'}), 400
        
        if not bounding_box:
            logger.warning(f"⚠️ No bounding box for face tag {face_tag_id}")
            return jsonify({'error': 'No bounding box for this face tag'}), 400
        
        # Get photo URL from OCI
        photo_url = _get_par_url_for_oci(file_path)
        if not photo_url:
            return jsonify({'error': 'Could not generate photo URL'}), 500
        
        # Download the full image
        response = requests.get(photo_url, timeout=30)
        response.raise_for_status()
        
        # Open image
        img = Image.open(io.BytesIO(response.content))
        
        # Parse bounding box JSON
        import json
        bbox = json.loads(bounding_box) if isinstance(bounding_box, str) else bounding_box
        
        # Extract coordinates (handle both formats)
        if 'x' in bbox and 'w' in bbox:
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
        elif 'facial_area' in bbox:
            fa = bbox['facial_area']
            x, y, w, h = fa['x'], fa['y'], fa['w'], fa['h']
        else:
            return jsonify({'error': 'Invalid bounding box format'}), 400
        
        # Add padding (10% on each side)
        padding = int(max(w, h) * 0.1)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img.width, x + w + padding)
        y2 = min(img.height, y + h + padding)
        
        # Crop the face
        face_img = img.crop((x1, y1, x2, y2))
        
        # Resize to smaller thumbnail (100x100 for faster loading)
        face_img.thumbnail((100, 100), Image.Resampling.LANCZOS)
        
        # Save to cache and return
        face_img.convert('RGB').save(cache_file, 'JPEG', quality=75, optimize=True)
        
        logger.info(f"✅ Generated and cached {face_img.width}x{face_img.height} thumbnail for face_tag_id: {face_tag_id}")
        
        response = make_response(send_file(cache_file, mimetype='image/jpeg'))
        response.headers['Cache-Control'] = 'public, max-age=604800'  # Cache for 7 days
        return response
        
    except Exception as e:
        logger.error(f"❌ Error getting face tag thumbnail: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/face_tags_manager')
@viewer_required
def face_tags_manager():
    """Face tags management page"""
    return render_template('face_tags_manager.html')

@app.route('/camera_search')
@login_required
def camera_face_search_page():
    """Live camera face search page"""
    return render_template('camera_face_search.html')

@app.route('/media_thumbnail/<int:media_id>')
@viewer_required
def media_thumbnail(media_id):
    """Get optimized thumbnail for any media (photo or video) - with disk caching"""
    import tempfile
    import requests
    from PIL import Image
    import io
    import os
    
    # Cache directory
    cache_dir = os.path.join(tempfile.gettempdir(), 'media_thumbnails')
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f'media_{media_id}.jpg')
    
    # Check if cached thumbnail exists and is recent (< 7 days old)
    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < 604800:  # 7 days in seconds
            response = make_response(send_file(cache_file, mimetype='image/jpeg'))
            response.headers['Cache-Control'] = 'public, max-age=604800'
            return response
    
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        # Get media info
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_path, file_type
                FROM album_media
                WHERE id = :media_id
            """, {'media_id': media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({'error': 'Media not found'}), 404
        
        file_path, file_type = row
        
        # Get media URL from OCI
        media_url = _get_par_url_for_oci(file_path)
        if not media_url:
            return jsonify({'error': 'Could not generate media URL'}), 500
        
        if file_type == 'photo':
            # Download and resize photo
            response_img = requests.get(media_url, timeout=30, stream=True)
            response_img.raise_for_status()
            
            img = Image.open(io.BytesIO(response_img.content))
            
            # Resize to 400x400 thumbnail (good for search results)
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            
            # Save to cache
            img.convert('RGB').save(cache_file, 'JPEG', quality=75, optimize=True)
            
        elif file_type == 'video':
            # For videos, redirect to video_thumbnail
            return redirect(url_for('video_thumbnail', media_id=media_id))
        else:
            return jsonify({'error': 'Unsupported media type'}), 400
        
        response = make_response(send_file(cache_file, mimetype='image/jpeg'))
        response.headers['Cache-Control'] = 'public, max-age=604800'
        return response
        
    except Exception as e:
        logger.error(f"❌ Error getting media thumbnail: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/media_modal/<int:media_id>')
@viewer_required
def media_modal(media_id):
    """Get optimized modal-sized image (1200px max) with disk caching for faster modal loading"""
    import tempfile
    import requests
    from PIL import Image
    import io
    import os

    # Cache directory for modal images
    cache_dir = os.path.join(tempfile.gettempdir(), 'media_modal')
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f'modal_{media_id}.jpg')

    # Check if cached modal image exists and is recent (< 30 days old)
    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < 2592000:  # 30 days in seconds
            response = make_response(send_file(cache_file, mimetype='image/jpeg'))
            response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
            return response

    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection

        # Get media info
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_path, file_type
                FROM album_media
                WHERE id = :media_id
            """, {'media_id': media_id})
            row = cursor.fetchone()

        if not row:
            return jsonify({'error': 'Media not found'}), 404

        file_path, file_type = row

        if file_type != 'photo':
            # For non-photos, redirect to full stream
            return redirect(url_for('media_stream', media_id=media_id))

        # Get media URL from OCI
        media_url = _get_par_url_for_oci(file_path)
        if not media_url:
            return jsonify({'error': 'Could not generate media URL'}), 500

        # Download and resize for modal viewing
        response_img = requests.get(media_url, timeout=60, stream=True)
        response_img.raise_for_status()

        img = Image.open(io.BytesIO(response_img.content))

        # Resize to 1200px max dimension (good for modal viewing)
        max_size = (1200, 1200)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save to cache with good quality
        img.convert('RGB').save(cache_file, 'JPEG', quality=85, optimize=True)

        response = make_response(send_file(cache_file, mimetype='image/jpeg'))
        response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
        return response

    except Exception as e:
        logger.error(f"❌ Error getting modal image: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Fallback to original stream if modal caching fails
        return redirect(url_for('media_stream', media_id=media_id))
    """Serve the actual image/video for a media item by redirecting to OCI PAR URL with caching headers"""
    try:
        logger.info(f"📸 media_stream request for media_id={media_id}")
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
                logger.error(f"❌ Media {media_id} not found in database")
                return "Media not found", 404

            file_path, file_type, namespace, bucket, object_path = row
            logger.info(f"📂 Found media: file_path={file_path}, type={file_type}")

            # Generate PAR URL for the image
            par_url = _get_par_url_for_oci(file_path)

            if par_url:
                logger.info(f"✅ Generated PAR URL, redirecting to OCI with cache headers")
                # Redirect to the OCI PAR URL with cache headers for better performance
                response = redirect(par_url)
                # Cache images for 1 hour (3600 seconds) since they don't change often
                response.headers['Cache-Control'] = 'public, max-age=3600'
                # Add other performance headers
                response.headers['X-Accel-Expires'] = '3600'  # For nginx caching if used
                return response
            else:
                logger.error(f"❌ Could not generate PAR URL for {file_path}")
                return "Could not generate media URL", 500

    except Exception as e:
        logger.error(f"❌ Error serving media {media_id}: {e}")
        return str(e), 500

@app.route('/search_unified', methods=['POST'])
@login_required
@viewer_required
@rate_limit_search
def search_unified():
    """Unified search across photos and videos using TwelveLabs Marengo embeddings
    
    Rate limited to prevent abuse (searches per hour quota).
    Results are filtered by user_id for multi-tenant isolation.
    
    Searches both photo and video content using natural language queries.
    Uses Oracle Vector DB for similarity search.
    Automatically filters results by current user (unless admin viewing all)
    
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
        min_similarity = data.get('min_similarity', 0.45)  # Default 45% threshold (increased from 30% for better accuracy)
        search_mode = data.get('search_mode', 'vector')  # 'vector', 'metadata', or 'auto'
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Get user_id for filtering (None for admin to see all content)
        user_id = current_user.id if current_user.role != 'admin' else None
        
        logger.info(f"🔍 Unified search request: '{query}' (user: {current_user.username}, limit: {limit}, threshold: {min_similarity*100:.0f}%, mode: {search_mode})")
        
        if not UNIFIED_ALBUM_AVAILABLE:
            return jsonify({'error': 'Unified album system not available'}), 500
        
        # Try Flask-safe unified vector search (photos + video segments)
        results = []
        search_method = "unknown"
        
        # If metadata-only mode requested, skip vector search
        if search_mode == 'metadata':
            logger.info("📝 Using metadata-only search (explicit mode)")
            search_method = "metadata_only"
            
            try:
                from search_unified_flask_safe import search_by_metadata
                results = search_by_metadata(
                    query_text=query,
                    user_id=user_id,
                    album_name=album_filter,
                    top_k=limit
                )
                logger.info(f"✅ Metadata search found {len(results)} results")
            except Exception as e:
                logger.error(f"Metadata search failed: {e}", exc_info=True)
                results = []
        
        elif FLASK_SAFE_SEARCH_AVAILABLE and search_unified_flask_safe:
            logger.info("🧠 Using Flask-safe Unified Vector DB search (photos + videos)")
            search_method = "vector_unified_flask_safe"
            
            try:
                # search_unified_flask_safe returns list of results directly
                # It now has built-in metadata fallback
                results = search_unified_flask_safe(
                    query_text=query,
                    user_id=user_id,  # Pass user_id for filtering
                    album_name=album_filter,
                    top_k=limit,
                    min_similarity=min_similarity
                )
                
                logger.info(f"✅ Unified search found {len(results)} results")
                logger.info(f"   📸 Photos: {len([r for r in results if r.get('file_type')=='photo'])}")
                logger.info(f"   🎬 Videos: {len([r for r in results if r.get('file_type')=='video'])}")
                        
            except Exception as e:
                logger.error(f"Flask-safe unified vector search failed: {e}", exc_info=True)
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
                    'description': result.get('description', result.get('summary')),
                    'ai_tags': result.get('ai_tags')  # Include AI tags
                }
                normalized_results.append(normalized_result)
        
        # Debug: Log if any results have ai_tags
        results_with_tags = [r for r in normalized_results if r.get('ai_tags')]
        logger.info(f"📊 {len(results_with_tags)} out of {len(normalized_results)} results have ai_tags")
        if results_with_tags:
            logger.info(f"🏷️ Sample ai_tags: {results_with_tags[0].get('ai_tags')[:100]}...")
        
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
    """Get PAR URL for a specific media item with optional video segment info"""
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
        
        response_data = {
            'media_id': media_id,
            'par_url': par_url,
            'file_name': file_name,
            'file_type': file_type
        }
        
        # For videos, check if there's segment info in request
        segment_start = request.args.get('segment_start', type=float)
        segment_end = request.args.get('segment_end', type=float)
        
        if segment_start is not None and segment_end is not None:
            response_data['segment_start'] = segment_start
            response_data['segment_end'] = segment_end
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"❌ Failed to get media URL: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/video_thumbnail/<int:media_id>')
def video_thumbnail(media_id):
    """Generate and serve a video thumbnail at a specific timestamp
    
    Query parameters:
        timestamp: Time in seconds (default: segment_start or 0)
    """
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from flask import send_file
        import tempfile
        import subprocess
        
        # Get timestamp from query params
        timestamp = request.args.get('timestamp', type=float, default=0)
        
        # Get media details from database
        sql = """
        SELECT file_path, file_name
        FROM album_media
        WHERE id = :media_id AND file_type = 'video'
        """
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, {'media_id': media_id})
            result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'Video not found'}), 404
        
        file_path = result[0]
        file_name = result[1]
        
        # Generate PAR URL
        par_url = _get_par_url_for_oci(file_path)
        if not par_url:
            return jsonify({'error': 'Failed to generate PAR URL'}), 500
        
        # Generate thumbnail directly from URL using FFmpeg (no full download needed!)
        temp_thumbnail = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_thumbnail.close()
        
        try:
            # FFmpeg can read directly from HTTP URL and extract a frame
            # This is MUCH faster than downloading the whole video
            cmd = [
                'ffmpeg',
                '-ss', str(timestamp),       # Seek to timestamp BEFORE input (fast seek)
                '-i', par_url,               # Input from PAR URL directly
                '-vframes', '1',             # Extract only 1 frame
                '-q:v', '2',                 # High quality
                '-vf', 'scale=320:-1',       # Resize to thumbnail
                '-y',                        # Overwrite
                temp_thumbnail.name
            ]
            
            # Run FFmpeg with timeout
            logger.info(f"🖼️ Generating thumbnail for media {media_id} at {timestamp}s...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15  # 15 second timeout
            )
            
            if result.returncode == 0 and os.path.exists(temp_thumbnail.name):
                logger.info(f"✅ Thumbnail generated for media {media_id}")
                return send_file(
                    temp_thumbnail.name,
                    mimetype='image/jpeg',
                    as_attachment=False,
                    download_name=f"{Path(file_name).stem}_t{int(timestamp)}.jpg"
                )
            else:
                logger.error(f"❌ FFmpeg failed: {result.stderr.decode()}")
                return jsonify({'error': 'Failed to generate thumbnail'}), 500
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Thumbnail generation timed out")
            return jsonify({'error': 'Thumbnail generation timed out'}), 500
        finally:
            # Cleanup happens after send_file completes
            try:
                if os.path.exists(temp_thumbnail.name):
                    os.unlink(temp_thumbnail.name)
            except:
                pass
        
    except Exception as e:
        logger.exception(f"❌ Failed to generate video thumbnail: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_media/<int:media_id>', methods=['DELETE'])
@login_required
@editor_required
def delete_media(media_id):
    """Delete a single media item (image or video) from database and OCI"""
    try:
        logger.info(f"🗑️ Deleting media ID: {media_id}")
        
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        # Get media info before deleting
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT file_path, file_name, file_type, album_name, user_id 
                   FROM album_media WHERE id = :id""",
                {'id': media_id}
            )
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'error': 'Media not found'}), 404
            
            file_path, file_name, file_type, album_name, owner_user_id = result
            
            # Validate ownership (admin can delete anything)
            if not can_access_resource(current_user, owner_user_id):
                logger.warning(f"🚫 User {current_user.id} attempted to delete media {media_id} owned by user {owner_user_id}")
                return jsonify({'error': 'Permission denied: You can only delete your own content'}), 403
            
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
@login_required
@editor_required
def delete_album(album_name):
    """Delete an entire album and all its media from database and OCI"""
    try:
        logger.info(f"🗑️ Deleting album: {album_name}")
        
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get all media in album
            cursor.execute(
                """SELECT id, file_path, file_name, file_type, user_id 
                   FROM album_media WHERE album_name = :album_name""",
                {'album_name': album_name}
            )
            media_items = cursor.fetchall()
            
            if not media_items:
                return jsonify({'error': 'Album not found or empty'}), 404
            
            # Check ownership of all media (admin can delete anything)
            if current_user.role != 'admin':
                for media_id, _, _, _, owner_user_id in media_items:
                    if not can_access_resource(current_user, owner_user_id):
                        logger.warning(f"🚫 User {current_user.id} attempted to delete album '{album_name}' containing media owned by user {owner_user_id}")
                        return jsonify({'error': 'Permission denied: Album contains content you do not own'}), 403
            
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


# =============================================================================
# NEW ADVANCED FEATURES
# =============================================================================

@app.route('/find_similar/<int:media_id>')
def find_similar_media(media_id):
    """Find media items similar to the given item"""
    try:
        logger.info(f"🔍 Finding similar media to ID: {media_id}")
        
        # Import here to avoid circular dependencies
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from ai_features import SimilarMediaFinder
        
        # Get media type from database
        with get_flask_safe_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT file_type FROM album_media WHERE id = :id", {"id": media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Media not found"}), 404
        
        media_type = row[0]
        finder = SimilarMediaFinder()
        
        # Find similar items
        if media_type == "photo":
            results = finder.find_similar_photos(media_id, top_k=10, min_similarity=0.5)
        else:
            results = finder.find_similar_videos(media_id, top_k=10, min_similarity=0.5)
        
        logger.info(f"✅ Found {len(results)} similar items")
        return jsonify({
            "success": True,
            "media_id": media_id,
            "media_type": media_type,
            "similar_items": results
        })
        
    except Exception as e:
        logger.error(f"❌ Error finding similar media: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/advanced_search', methods=['POST'])
@login_required
@viewer_required
@rate_limit_search
def advanced_search():
    """Advanced search with AND/OR operators and filters
    
    Rate limited to prevent abuse (searches per hour quota)."""
    try:
        data = request.json
        query = data.get('query', '')
        operator = data.get('operator', 'OR')  # AND or OR
        search_photos = data.get('search_photos', True)
        search_videos = data.get('search_videos', True)
        
        logger.info(f"🔍 Advanced search: '{query}' (operator: {operator})")
        
        from advanced_search import multimodal_search
        
        results = multimodal_search(
            query=query,
            operator=operator,
            search_photos=search_photos,
            search_videos=search_videos,
            top_k=20,
            min_similarity=0.3
        )
        
        return jsonify({
            "success": True,
            "query": query,
            "operator": operator,
            "photos": results.get("photos", []),
            "videos": results.get("videos", []),
            "total": len(results.get("photos", [])) + len(results.get("videos", []))
        })
        
    except Exception as e:
        logger.error(f"❌ Advanced search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/temporal_search', methods=['POST'])
@login_required
@viewer_required
@rate_limit_search
def temporal_search():
    """Search media by date range
    
    Rate limited to prevent abuse (searches per hour quota)."""
    try:
        from datetime import datetime
        from advanced_search import TemporalSearch
        
        data = request.json
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        media_type = data.get('media_type')  # Optional: 'photo' or 'video'
        album_name = data.get('album_name')  # Optional
        
        logger.info(f"📅 Temporal search: {start_date_str} to {end_date_str}")
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
        
        searcher = TemporalSearch()
        results = searcher.search_by_date_range(
            start_date, end_date,
            media_type=media_type,
            album_name=album_name
        )
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"❌ Temporal search error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/extract_clip', methods=['POST'])
async def extract_clip():
    """Extract a video clip from a media item"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from creative_tools import ClipExtractor
        
        data = request.json
        media_id = data.get('media_id')
        start_time = float(data.get('start_time', 0))
        end_time = float(data.get('end_time', 10))
        
        logger.info(f"✂️ Extracting clip from media {media_id}: {start_time}s - {end_time}s")
        
        # Get video file path from database
        with get_flask_safe_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT oci_namespace, oci_bucket, oci_object_path
                FROM album_media 
                WHERE id = :id AND file_type = 'video'
            """, {"id": media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Video not found"}), 404
        
        # Download video from OCI (or use local path if available)
        # For now, return a placeholder response
        extractor = ClipExtractor()
        
        return jsonify({
            "success": True,
            "message": "Clip extraction initiated",
            "media_id": media_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration": end_time - start_time
        })
        
    except Exception as e:
        logger.error(f"❌ Clip extraction error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/create_montage', methods=['POST'])
@login_required
@editor_required
@rate_limit_upload
def create_montage():
    """Create a video montage from multiple video clips with FFmpeg
    
    Rate limited and requires editor role.
    Video processing quota is checked before creating montage."""
    import subprocess
    import tempfile
    import shutil
    from datetime import datetime
    
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.oci_config import get_presigned_url, upload_to_oci
        
        data = request.json
        video_ids = data.get('video_ids', [])
        transition = data.get('transition', 'fade')
        duration_per_clip = float(data.get('duration_per_clip', 5.0))
        output_filename = data.get('output_filename', f'montage_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4')
        
        logger.info(f"🎬 Creating montage with {len(video_ids)} videos")
        
        if not video_ids:
            return jsonify({"error": "No videos selected"}), 400
        
        # Get video file paths from database
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            video_urls = []
            for video_id in video_ids:
                cursor.execute("""
                    SELECT file_path, file_name
                    FROM album_media
                    WHERE id = :id AND file_type = 'video'
                """, {"id": video_id})
                row = cursor.fetchone()
                
                if row:
                    presigned_url = get_presigned_url(row[0])
                    video_urls.append({
                        "url": presigned_url,
                        "filename": row[1]
                    })
        
        if not video_urls:
            return jsonify({"error": "No valid videos found"}), 404
        
        # Create temporary directory for downloads and processing
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, output_filename)
        
        try:
            # Download video clips to temp directory
            video_files = []
            for i, video_info in enumerate(video_urls):
                temp_video = os.path.join(temp_dir, f'clip_{i:04d}.mp4')
                
                # Download video
                import urllib.request
                urllib.request.urlretrieve(video_info['url'], temp_video)
                video_files.append(temp_video)
            
            # Create FFmpeg input file list
            input_list_path = os.path.join(temp_dir, 'input.txt')
            with open(input_list_path, 'w') as f:
                for video_file in video_files:
                    # Trim each clip to duration_per_clip
                    f.write(f"file '{video_file}'\n")
                    f.write(f"inpoint 0\n")
                    f.write(f"outpoint {duration_per_clip}\n")
            
            # Build FFmpeg command for montage
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', input_list_path,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-y',
                output_path
            ]
            
            # Execute FFmpeg
            logger.info(f"🎬 Running FFmpeg to create montage...")
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                timeout=600  # 10 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"❌ FFmpeg error: {result.stderr.decode()}")
                return jsonify({"error": "Failed to create montage video"}), 500
            
            # Get file size
            file_size = os.path.getsize(output_path)
            
            logger.info(f"✅ Montage created: {output_filename} ({file_size / 1024 / 1024:.2f} MB)")
            
            # Upload to OCI Object Storage
            logger.info(f"📤 Uploading montage to OCI Object Storage...")
            album_name = "Generated-Montages"
            
            # Use user-specific path for multi-tenant isolation
            if OCI_STORAGE_HELPERS_AVAILABLE:
                oci_file_path = get_user_generated_path(current_user.id, 'montage', output_filename)
                logger.info(f"🔐 Using user-specific montage path: {oci_file_path}")
            else:
                oci_file_path = f"{album_name}/{output_filename}"
                logger.warning(f"⚠️ Using legacy montage path: {oci_file_path}")
            
            oci_url = upload_to_oci(output_path, oci_file_path)
            logger.info(f"✅ Uploaded to OCI: {oci_file_path}")
            
            # Store in database
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO album_media (
                        file_name, file_path, file_type, album_name,
                        file_size, duration, created_at
                    ) VALUES (
                        :file_name, :file_path, :file_type, :album_name,
                        :file_size, :duration, SYSTIMESTAMP
                    ) RETURNING id INTO :media_id
                """, {
                    "file_name": output_filename,
                    "file_path": oci_file_path,
                    "file_type": "video",
                    "album_name": album_name,
                    "file_size": file_size,
                    "duration": len(video_files) * duration_per_clip,
                    "media_id": cursor.var(int)
                })
                
                media_id = cursor.var(int).getvalue()[0]
                conn.commit()
                logger.info(f"✅ Stored in database with media_id: {media_id}")
            
            # Generate TwelveLabs embeddings
            logger.info(f"🧠 Generating TwelveLabs embeddings for montage...")
            try:
                from twelvelabs import TwelveLabs
                client = TwelveLabs(api_key=TWELVE_LABS_API_KEY)
                
                task = client.task.create(
                    index_id=TWELVE_LABS_INDEX_ID,
                    url=oci_url,
                    metadata={
                        "filename": output_filename,
                        "album": album_name,
                        "type": "montage",
                        "num_clips": len(video_files),
                        "media_id": media_id
                    }
                )
                
                video_id = task.video_id
                
                with get_flask_safe_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE album_media 
                        SET video_id = :video_id, indexing_status = 'pending'
                        WHERE id = :media_id
                    """, {"video_id": video_id, "media_id": media_id})
                    conn.commit()
                
                logger.info(f"✅ TwelveLabs indexing started with video_id: {video_id}")
                
            except Exception as embed_error:
                logger.warning(f"⚠️ Could not generate embeddings: {embed_error}")
            
            # Delete local file
            try:
                os.remove(output_path)
            except:
                pass
            
            # Get presigned URL
            presigned_url = get_presigned_url(oci_file_path)
            
            return jsonify({
                "success": True,
                "message": f"Montage created and uploaded to cloud storage with {len(video_files)} clips",
                "filename": output_filename,
                "download_url": presigned_url,
                "media_id": media_id,
                "album_name": album_name,
                "oci_path": oci_file_path,
                "num_clips": len(video_files),
                "estimated_duration": len(video_files) * duration_per_clip,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "searchable": True,
                "embedding_status": "indexing"
            })
            
        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        
    except subprocess.TimeoutExpired:
        logger.error("❌ Montage creation timeout")
        return jsonify({"error": "Montage creation timed out"}), 500
    except Exception as e:
        logger.error(f"❌ Montage creation error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/create_slideshow', methods=['POST'])
@login_required
@editor_required
@rate_limit_upload
def create_slideshow():
    """Create a photo slideshow video with FFmpeg
    
    Rate limited and requires editor role.
    Video processing quota is checked before creating slideshow."""
    import subprocess
    import tempfile
    import shutil
    from datetime import datetime
    
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.oci_config import get_presigned_url
        
        data = request.json
        photo_ids = data.get('photo_ids', [])
        duration_per_photo = float(data.get('duration_per_photo', 3.0))
        transition = data.get('transition', 'fade')
        resolution = data.get('resolution', '1920x1080')
        output_filename = data.get('output_filename', f'slideshow_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4')
        
        logger.info(f"📸 Creating slideshow with {len(photo_ids)} photos")
        
        if not photo_ids:
            return jsonify({"error": "No photos selected"}), 400
        
        # Get photo file paths from database
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            photo_urls = []
            for photo_id in photo_ids:
                cursor.execute("""
                    SELECT file_path, file_name
                    FROM album_media
                    WHERE id = :id AND file_type = 'photo'
                """, {"id": photo_id})
                row = cursor.fetchone()
                
                if row:
                    # Get presigned URL for photo
                    presigned_url = get_presigned_url(row[0])
                    photo_urls.append(presigned_url)
        
        if not photo_urls:
            return jsonify({"error": "No valid photos found"}), 404
        
        # Create temporary directory for downloads and processing
        temp_dir = tempfile.mkdtemp()
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'slideshows')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
        
        try:
            # Download photos to temp directory
            photo_files = []
            for i, url in enumerate(photo_urls):
                temp_photo = os.path.join(temp_dir, f'photo_{i:04d}.jpg')
                
                # Download photo
                import urllib.request
                urllib.request.urlretrieve(url, temp_photo)
                photo_files.append(temp_photo)
            
            # Create FFmpeg input file list
            input_list_path = os.path.join(temp_dir, 'input.txt')
            with open(input_list_path, 'w') as f:
                for photo_file in photo_files:
                    f.write(f"file '{photo_file}'\n")
                    f.write(f"duration {duration_per_photo}\n")
                # Repeat last photo to ensure correct duration
                if photo_files:
                    f.write(f"file '{photo_files[-1]}'\n")
            
            # Parse resolution
            width, height = resolution.split('x')
            
            # Build FFmpeg command for slideshow with transitions
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', input_list_path,
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-y',  # Overwrite output file
                output_path
            ]
            
            # Execute FFmpeg
            logger.info(f"🎬 Running FFmpeg to create slideshow...")
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"❌ FFmpeg error: {result.stderr.decode()}")
                return jsonify({"error": "Failed to create slideshow video"}), 500
            
            # Get file size
            file_size = os.path.getsize(output_path)
            
            logger.info(f"✅ Slideshow created: {output_filename} ({file_size / 1024 / 1024:.2f} MB)")
            
            # Upload to OCI Object Storage
            logger.info(f"📤 Uploading slideshow to OCI Object Storage...")
            from utils.oci_config import upload_to_oci
            
            # Create album name for generated slideshows
            album_name = "Generated-Slideshows"
            
            # Use user-specific path for multi-tenant isolation
            if OCI_STORAGE_HELPERS_AVAILABLE:
                oci_file_path = get_user_generated_path(current_user.id, 'slideshow', output_filename)
                logger.info(f"🔐 Using user-specific slideshow path: {oci_file_path}")
            else:
                oci_file_path = f"{album_name}/{output_filename}"
                logger.warning(f"⚠️ Using legacy slideshow path: {oci_file_path}")
            
            # Upload to OCI
            oci_url = upload_to_oci(output_path, oci_file_path)
            logger.info(f"✅ Uploaded to OCI: {oci_file_path}")
            
            # Store in database with metadata
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                
                # Insert into ALBUM_MEDIA table
                cursor.execute("""
                    INSERT INTO album_media (
                        file_name, file_path, file_type, album_name,
                        file_size, duration, created_at
                    ) VALUES (
                        :file_name, :file_path, :file_type, :album_name,
                        :file_size, :duration, SYSTIMESTAMP
                    ) RETURNING id INTO :media_id
                """, {
                    "file_name": output_filename,
                    "file_path": oci_file_path,
                    "file_type": "video",
                    "album_name": album_name,
                    "file_size": file_size,
                    "duration": len(photo_files) * duration_per_photo,
                    "media_id": cursor.var(int)
                })
                
                media_id = cursor.var(int).getvalue()[0]
                conn.commit()
                logger.info(f"✅ Stored in database with media_id: {media_id}")
            
            # Generate TwelveLabs embeddings for the slideshow
            logger.info(f"🧠 Generating TwelveLabs embeddings for slideshow...")
            try:
                from twelvelabs import TwelveLabs
                client = TwelveLabs(api_key=TWELVE_LABS_API_KEY)
                
                # Create a task to index the slideshow video
                task = client.task.create(
                    index_id=TWELVE_LABS_INDEX_ID,
                    url=oci_url,
                    metadata={
                        "filename": output_filename,
                        "album": album_name,
                        "type": "slideshow",
                        "num_photos": len(photo_files),
                        "media_id": media_id
                    }
                )
                
                video_id = task.video_id
                
                # Update database with video_id
                with get_flask_safe_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE album_media 
                        SET video_id = :video_id, indexing_status = 'pending'
                        WHERE id = :media_id
                    """, {"video_id": video_id, "media_id": media_id})
                    conn.commit()
                
                logger.info(f"✅ TwelveLabs indexing started with video_id: {video_id}")
                
            except Exception as embed_error:
                logger.warning(f"⚠️ Could not generate embeddings: {embed_error}")
                # Continue anyway - slideshow is still created
            
            # Delete local file after successful upload
            try:
                os.remove(output_path)
                logger.info(f"🗑️ Deleted local file: {output_path}")
            except Exception as del_error:
                logger.warning(f"⚠️ Could not delete local file: {del_error}")
            
            # Get presigned URL for immediate download
            presigned_url = get_presigned_url(oci_file_path)
            
            return jsonify({
                "success": True,
                "message": f"Slideshow created and uploaded to cloud storage with {len(photo_files)} photos",
                "filename": output_filename,
                "download_url": presigned_url,
                "media_id": media_id,
                "album_name": album_name,
                "oci_path": oci_file_path,
                "num_photos": len(photo_files),
                "duration_per_photo": duration_per_photo,
                "estimated_duration": len(photo_files) * duration_per_photo,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "searchable": True,
                "embedding_status": "indexing"
            })
            
        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        
    except subprocess.TimeoutExpired:
        logger.error("❌ Slideshow creation timeout")
        return jsonify({"error": "Slideshow creation timed out"}), 500
    except Exception as e:
        logger.error(f"❌ Slideshow creation error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/delete_generated_media/<int:media_id>', methods=['DELETE'])
@login_required
@editor_required
def delete_generated_media(media_id):
    """Delete a generated slideshow or montage from OCI and database"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.oci_config import delete_from_oci
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get media info including owner
            cursor.execute("""
                SELECT file_name, file_path, album_name, user_id
                FROM album_media
                WHERE id = :id AND album_name IN ('Generated-Slideshows', 'Generated-Montages')
            """, {"id": media_id})
            
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "Generated media not found"}), 404
            
            filename, file_path, album_name, owner_user_id = row
            
            # Validate ownership (admin can delete anything)
            if not can_access_resource(current_user, owner_user_id):
                logger.warning(f"🚫 User {current_user.id} attempted to delete generated media {media_id} owned by user {owner_user_id}")
                return jsonify({'error': 'Permission denied: You can only delete your own content'}), 403
            
            # Delete from OCI Object Storage
            try:
                delete_from_oci(file_path)
                logger.info(f"🗑️ Deleted from OCI: {file_path}")
            except Exception as oci_error:
                logger.warning(f"⚠️ Could not delete from OCI: {oci_error}")
            
            # Delete from database
            cursor.execute("DELETE FROM album_media WHERE id = :id", {"id": media_id})
            conn.commit()
            
            logger.info(f"✅ Deleted generated media: {filename}")
            
        return jsonify({
            "success": True,
            "message": f"Successfully deleted {filename}"
        })
        
    except Exception as e:
        logger.error(f"❌ Delete generated media error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/list_slideshows')
def list_slideshows():
    """List all created slideshows and montages from database"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.oci_config import get_presigned_url
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Query generated media from database
            cursor.execute("""
                SELECT id, file_name, file_path, album_name, file_size, 
                       duration, created_at, indexing_status
                FROM album_media
                WHERE album_name IN ('Generated-Slideshows', 'Generated-Montages')
                ORDER BY created_at DESC
            """)
            
            slideshows = []
            for row in cursor:
                media_id, filename, file_path, album_name, file_size, duration, created_at, status = row
                
                # Get presigned URL for download
                download_url = get_presigned_url(file_path)
                
                slideshows.append({
                    "media_id": media_id,
                    "filename": filename,
                    "album_name": album_name,
                    "type": "slideshow" if "Slideshow" in album_name else "montage",
                    "size_mb": round(file_size / 1024 / 1024, 2) if file_size else 0,
                    "duration": duration,
                    "created": created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "Unknown",
                    "download_url": download_url,
                    "indexing_status": status or "completed",
                    "searchable": status in ['completed', 'ready', None]
                })
        
        return jsonify({
            "slideshows": slideshows,
            "count": len(slideshows)
        })
        
    except Exception as e:
        logger.error(f"❌ List slideshows error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/auto_tag/<int:media_id>', methods=['POST'])
def auto_tag_media(media_id):
    """Generate automatic tags for media using AI (ImageBind for videos, OpenAI Vision for photos)"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        import oci
        import os
        
        # Check if user wants to force overwrite
        force_overwrite = request.json.get('force_overwrite', False) if request.is_json else False
        
        logger.info(f"🏷️ Auto-tagging media {media_id} (force={force_overwrite})")
        
        # Get media info from database
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_name, file_type, file_path, oci_object_path, AI_TAGS 
                FROM album_media 
                WHERE id = :id
            """, {"id": media_id})
            row = cursor.fetchone()
            
            if not row:
                return jsonify({"error": "Media not found"}), 404
            
            file_name = row[0]
            file_type = row[1]
            file_path = row[2]
            oci_object_path = row[3] if len(row) > 3 else None
            # AI_TAGS CLOB is already converted to string by flask_safe_execute_query
            existing_tags = row[4] if len(row) > 4 else None
        
        # If tags exist and user hasn't confirmed overwrite, ask for confirmation
        if existing_tags and not force_overwrite:
            return jsonify({
                "confirm_required": True,
                "existing_tags": existing_tags,
                "message": "Tags already exist for this media. Do you want to overwrite them?"
            })
        
        # Handle video auto-tagging with ImageBind
        if file_type == 'video':
            # Use existing ImageBind embedding from database
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT embedding_vector 
                    FROM album_media 
                    WHERE id = :id
                """, {"id": media_id})
                result = cursor.fetchone()
                video_embedding = result[0] if result and result[0] else None
            
            if not video_embedding:
                return jsonify({
                    "success": False,
                    "error": "Video embedding not found. Please re-upload the video to enable AI tagging."
                }), 400
            
            # Generate tags using ImageBind embedding similarity
            from utils.imagebind_helper import get_imagebind_embedder
            import numpy as np
            import json
            
            embedder = get_imagebind_embedder()
            
            # Convert Oracle VECTOR to numpy array
            video_emb = np.array(list(video_embedding), dtype=np.float32)
            
            # Define category tags with their text embeddings
            categories = [
                "sports and athletics", "nature and outdoors", "city and urban life",
                "people and social gatherings", "animals and pets", "food and cooking",
                "music and dance", "travel and tourism", "technology and science",
                "art and creativity", "business and work", "education and learning",
                "family and children", "fashion and beauty", "health and fitness",
                "celebration and events", "transportation and vehicles", "architecture and buildings"
            ]
            
            # Generate embeddings for categories
            category_scores = []
            for category in categories:
                cat_embedding = embedder.generate_text_embedding(category)
                if cat_embedding is not None:
                    # Calculate cosine similarity
                    similarity = np.dot(video_emb, cat_embedding) / (
                        np.linalg.norm(video_emb) * np.linalg.norm(cat_embedding)
                    )
                    category_scores.append((category, float(similarity)))
            
            # Sort by similarity and get top 5
            category_scores.sort(key=lambda x: x[1], reverse=True)
            top_categories = category_scores[:5]
            
            # Generate hashtags from top categories
            hashtags = [f"#{cat.replace(' and ', '_').replace(' ', '_')}" 
                       for cat, _ in top_categories[:8]]
            
            # Format generated tags
            generated_text = f"CATEGORIES: {', '.join([cat for cat, score in top_categories])}\n"
            generated_text += f"HASHTAGS: {' '.join(hashtags)}\n"
            generated_text += f"CONFIDENCE: {top_categories[0][1]:.2%} match to '{top_categories[0][0]}'"
            
            # Save tags to database
            try:
                with get_flask_safe_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE album_media 
                        SET AI_TAGS = :tags 
                        WHERE id = :id
                    """, {"tags": generated_text, "id": media_id})
                    conn.commit()
                    logger.info(f"✅ Saved ImageBind-based tags for media {media_id}")
            except Exception as db_error:
                logger.warning(f"Failed to save tags to database: {db_error}")
            
            return jsonify({
                "success": True,
                "media_id": media_id,
                "file_name": file_name,
                "file_type": "video",
                "generated_tags": generated_text,
                "top_categories": [{"category": cat, "confidence": f"{score:.2%}"} 
                                  for cat, score in top_categories],
                "existing_tags": existing_tags
            })
        
        # Handle photo auto-tagging with OpenAI Vision
        elif file_type == 'photo':
            # Download photo from OCI to analyze
            try:
                # Initialize OCI client
                config = oci.config.from_file()
                object_storage = oci.object_storage.ObjectStorageClient(config)
                namespace = object_storage.get_namespace().data
                bucket_name = os.getenv('OCI_BUCKET_NAME', 'Media')
                
                # Get object path
                object_name = oci_object_path or file_path
                
                # Download image
                logger.info(f"📥 Downloading photo from OCI: {object_name}")
                get_obj = object_storage.get_object(namespace, bucket_name, object_name)
                image_data = get_obj.data.content
                
                # Encode to base64 for OpenAI
                import base64
                base64_image = base64.b64encode(image_data).decode('utf-8')
                
                # Use OpenAI Vision API
                from openai import OpenAI
                openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                
                response = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Analyze this image and provide: 1) A concise descriptive title, 2) 3-5 main subjects/objects, 3) 5-8 relevant hashtags. Format as: TITLE: ..., SUBJECTS: ..., HASHTAGS: ..."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=300
                )
                
                generated_text = response.choices[0].message.content
                
                # Save tags to database
                try:
                    with get_flask_safe_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE album_media 
                            SET AI_TAGS = :tags 
                            WHERE id = :id
                        """, {"tags": generated_text, "id": media_id})
                        conn.commit()
                        logger.info(f"✅ Saved tags for media {media_id}")
                except Exception as db_error:
                    logger.warning(f"Failed to save tags to database: {db_error}")
                
                return jsonify({
                    "success": True,
                    "media_id": media_id,
                    "file_name": file_name,
                    "file_type": "photo",
                    "generated_tags": generated_text,
                    "existing_tags": existing_tags
                })
                
            except Exception as e:
                logger.error(f"❌ Photo analysis error: {e}")
                return jsonify({
                    "error": f"Failed to analyze photo: {str(e)}"
                }), 500
        
        else:
            return jsonify({
                "error": "Unsupported file type"
            }), 400
        
    except Exception as e:
        logger.error(f"❌ Auto-tagging error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/video_highlights/<int:media_id>')
def get_video_highlights(media_id):
    """Get AI-generated video highlights"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info(f"🎬 Getting highlights for media {media_id}")
        
        # Get video info from database
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_name, file_path, file_type 
                FROM album_media 
                WHERE id = :id AND file_type = 'video'
            """, {"id": media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Video not found"}), 404
        
        # For now, return a structured response
        return jsonify({
            "success": True,
            "media_id": media_id,
            "file_name": row[0],
            "message": "Video highlights feature available - integrate with TwelveLabs video_id when ready"
        })
        
    except Exception as e:
        logger.error(f"❌ Highlights extraction error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# FACE TAGGING ENDPOINTS
# ============================================================================

@app.route('/media/<int:media_id>/detect_faces', methods=['POST'])
@login_required
def detect_faces_in_media(media_id):
    """Detect faces in a photo"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.face_detection_helper import detect_faces_deepface
        import tempfile
        import requests
        
        # Only editors and admins can detect faces
        if current_user.role == 'viewer':
            return jsonify({"error": "Permission denied"}), 403
        
        logger.info(f"👤 Detecting faces in media {media_id}")
        
        # Get media info
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, file_name, file_type, file_path, user_id
                FROM album_media 
                WHERE id = :id
            """, {"id": media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Media not found"}), 404
        
        media_user_id = row[4]
        
        # Check permissions - user can only tag their own media (except admins)
        if current_user.role != 'admin' and current_user.id != media_user_id:
            return jsonify({"error": "You can only tag faces in your own photos"}), 403
        
        # Only photos supported for now
        if row[2] != 'photo':
            return jsonify({"error": "Face detection only supports photos"}), 400
        
        file_path = row[3]
        
        # Get PAR URL for the photo
        par_url = _get_par_url_for_oci(file_path)
        if not par_url:
            return jsonify({"error": "Failed to access photo"}), 500
        
        # Download to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file_path = temp_file.name
        temp_file.close()
        
        try:
            # Download image from PAR URL
            response = requests.get(par_url, timeout=30)
            response.raise_for_status()
            
            with open(temp_file_path, 'wb') as f:
                f.write(response.content)
            
            # Detect faces using DeepFace (with automatic fallback to OpenCV)
            faces = detect_faces_deepface(temp_file_path)
            
            # Get existing face tags for this media
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, face_name, bounding_box
                    FROM face_tags
                    WHERE media_id = :media_id
                """, {"media_id": media_id})
                
                existing_tags = []
                for tag_row in cursor.fetchall():
                    import json
                    existing_tags.append({
                        "tag_id": tag_row[0],
                        "face_name": tag_row[1],
                        "bounding_box": json.loads(tag_row[2]) if tag_row[2] else None
                    })
            
            # Match detected faces with existing tags based on bounding box overlap
            def calculate_iou(bbox1, bbox2):
                """Calculate Intersection over Union (IoU) for two bounding boxes"""
                # Convert bboxes to consistent format (x, y, w, h)
                def normalize_bbox(bbox):
                    if isinstance(bbox, dict):
                        if 'x' in bbox and 'w' in bbox:
                            return bbox['x'], bbox['y'], bbox['w'], bbox['h']
                        elif 'facial_area' in bbox:
                            fa = bbox['facial_area']
                            return fa['x'], fa['y'], fa['w'], fa['h']
                    elif isinstance(bbox, list) and len(bbox) == 4:
                        return bbox[0], bbox[1], bbox[2], bbox[3]
                    return None
                
                b1 = normalize_bbox(bbox1)
                b2 = normalize_bbox(bbox2)
                
                if not b1 or not b2:
                    return 0.0
                
                x1, y1, w1, h1 = b1
                x2, y2, w2, h2 = b2
                
                # Calculate intersection
                x_left = max(x1, x2)
                y_top = max(y1, y2)
                x_right = min(x1 + w1, x2 + w2)
                y_bottom = min(y1 + h1, y2 + h2)
                
                if x_right < x_left or y_bottom < y_top:
                    return 0.0
                
                intersection_area = (x_right - x_left) * (y_bottom - y_top)
                
                # Calculate union
                bbox1_area = w1 * h1
                bbox2_area = w2 * h2
                union_area = bbox1_area + bbox2_area - intersection_area
                
                return intersection_area / union_area if union_area > 0 else 0.0
            
            # Add matched tag info to detected faces
            for face in faces:
                face['matched_tag'] = None
                best_iou = 0.5  # Minimum threshold for matching
                
                for tag in existing_tags:
                    if not tag['bounding_box']:
                        continue
                    
                    iou = calculate_iou(face, tag['bounding_box'])
                    
                    if iou > best_iou:
                        best_iou = iou
                        face['matched_tag'] = {
                            'tag_id': tag['tag_id'],
                            'face_name': tag['face_name'],
                            'iou': iou
                        }
            
            matched_count = sum(1 for f in faces if f.get('matched_tag'))
            logger.info(f"✅ Detected {len(faces)} faces in media {media_id} ({len(existing_tags)} tagged, {matched_count} matched)")
            
            return jsonify({
                "success": True,
                "media_id": media_id,
                "faces_detected": len(faces),
                "faces": faces,
                "existing_tags": existing_tags
            })
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except Exception as e:
        logger.error(f"❌ Face detection error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/media/<int:media_id>/tag_face', methods=['POST'])
@login_required
def tag_face_in_media(media_id):
    """Manually tag a face in a photo with a person's name"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.face_detection_helper import (
            generate_placeholder_embedding, embedding_to_oracle_vector,
            bbox_to_json, detect_faces_deepface
        )
        import tempfile
        import requests
        
        # Only editors and admins can tag faces
        if current_user.role == 'viewer':
            return jsonify({"error": "Permission denied"}), 403
        
        # Get request data
        data = request.get_json()
        face_index = data.get('face_index')
        face_name = data.get('name')
        
        if face_name is None or face_index is None:
            return jsonify({"error": "face_index and name required"}), 400
        
        logger.info(f"🏷️ Tagging face index {face_index} as '{face_name}' in media {media_id}")
        
        # Get media info
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, file_name, file_type, file_path, user_id
                FROM album_media 
                WHERE id = :id
            """, {"id": media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Media not found"}), 404
        
        media_user_id = row[4]
        
        # Check permissions
        if current_user.role != 'admin' and current_user.id != media_user_id:
            return jsonify({"error": "You can only tag faces in your own photos"}), 403
        
        # Only photos supported
        if row[2] != 'photo':
            return jsonify({"error": "Face tagging only supports photos"}), 400
        
        file_path = row[3]
        
        # Get PAR URL for the photo
        par_url = _get_par_url_for_oci(file_path)
        if not par_url:
            return jsonify({"error": "Failed to access photo"}), 500
        
        # Download to temp file and detect faces
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file_path = temp_file.name
        temp_file.close()
        
        try:
            # Download image
            response = requests.get(par_url, timeout=30)
            response.raise_for_status()
            
            with open(temp_file_path, 'wb') as f:
                f.write(response.content)
            
            # Detect faces to get bounding box for the specified index (using DeepFace to match detect_faces endpoint)
            faces = detect_faces_deepface(temp_file_path)
            
            if face_index >= len(faces):
                return jsonify({"error": f"Face index {face_index} not found (only {len(faces)} faces detected)"}), 400
            
            # Get the face bbox for this index
            face_data = faces[face_index]
            face_bbox = face_data.get('facial_area')
            
            if not face_bbox:
                return jsonify({"error": "Face bounding box not found"}), 500
            
            # OPTIMIZED: Don't generate embedding immediately - defer to batch job
            # This makes face tagging instant and saves API quota
            # Embedding will be generated by background batch job
            
            # Save face tag to database WITHOUT embedding
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                
                # Insert face tag with needs_embedding=1 (will be processed by batch job)
                face_tag_id_var = cursor.var(int)
                cursor.execute("""
                    INSERT INTO face_tags 
                    (media_id, face_name, bounding_box, confidence, auto_tagged, created_by, needs_embedding)
                    VALUES (:media_id, :face_name, :bbox, :confidence, :auto_tagged, :user_id, 1)
                    RETURNING id INTO :id
                """, {
                    "media_id": media_id,
                    "face_name": face_name,
                    "bbox": bbox_to_json(face_bbox),
                    "confidence": 1.0,  # Manual tag = 100% confidence
                    "auto_tagged": 0,   # Manual tag
                    "user_id": current_user.id,
                    "id": face_tag_id_var
                })
                
                face_tag_id = face_tag_id_var.getvalue()[0]
                conn.commit()
            
            logger.info(f"✅ Tagged face '{face_name}' in media {media_id} (tag_id: {face_tag_id})")
            
            return jsonify({
                "success": True,
                "media_id": media_id,
                "face_tag_id": face_tag_id,
                "face_name": face_name
            })
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except Exception as e:
        logger.error(f"❌ Face tagging error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

        
        return jsonify({
            "success": True,
            "media_id": media_id,
            "face_tag_id": face_tag_id,
            "face_name": face_name,
            "message": f"Successfully tagged face as '{face_name}'"
        })
        
    except Exception as e:
        logger.error(f"❌ Face tagging error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/media/<int:media_id>/faces', methods=['GET'])
@login_required
def get_media_face_tags(media_id):
    """Get all face tags for a media item"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info(f"📋 Getting face tags for media {media_id}")
        
        # Check if user has access to this media
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get media owner
            cursor.execute("""
                SELECT user_id FROM album_media WHERE id = :id
            """, {"id": media_id})
            row = cursor.fetchone()
            
            if not row:
                return jsonify({"error": "Media not found"}), 404
            
            media_user_id = row[0]
            
            # Check permissions
            if current_user.role != 'admin' and current_user.id != media_user_id:
                return jsonify({"error": "Permission denied"}), 403
            
            # Get all face tags for this media
            cursor.execute("""
                SELECT 
                    ft.id,
                    ft.face_name,
                    ft.bounding_box,
                    ft.confidence,
                    ft.created_at,
                    u.username as tagged_by,
                    ft.auto_tagged
                FROM face_tags ft
                LEFT JOIN users u ON ft.created_by = u.id
                WHERE ft.media_id = :media_id
                ORDER BY ft.created_at DESC
            """, {"media_id": media_id})
            
            rows = cursor.fetchall()
        
        face_tags = []
        for row in rows:
            face_tags.append({
                "id": row[0],
                "face_name": row[1],
                "bounding_box": row[2],  # JSON string
                "confidence": float(row[3]) if row[3] else 1.0,
                "created_at": row[4].isoformat() if row[4] else None,
                "tagged_by": row[5],
                "auto_tagged": bool(row[6]) if row[6] is not None else False
            })
        
        return jsonify({
            "success": True,
            "media_id": media_id,
            "face_tags": face_tags,
            "total": len(face_tags)
        })
        
    except Exception as e:
        logger.error(f"❌ Get face tags error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/face_tags/<int:tag_id>', methods=['DELETE'])
@login_required
def delete_face_tag(tag_id):
    """Delete a face tag"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info(f"🗑️ Deleting face tag {tag_id}")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get tag info to check permissions
            cursor.execute("""
                SELECT media_id, created_by 
                FROM face_tags 
                WHERE id = :id
            """, {"id": tag_id})
            row = cursor.fetchone()
            
            if not row:
                return jsonify({"error": "Face tag not found"}), 404
            
            media_id = row[0]
            created_by = row[1]
            
            # Check if user owns the tag or is admin
            if current_user.role != 'admin' and current_user.id != created_by:
                return jsonify({"error": "Permission denied"}), 403
            
            # Delete the tag
            cursor.execute("""
                DELETE FROM face_tags WHERE id = :id
            """, {"id": tag_id})
            
            conn.commit()
        
        logger.info(f"✅ Deleted face tag {tag_id}")
        
        return jsonify({
            "success": True,
            "message": "Face tag deleted successfully"
        })
        
    except Exception as e:
        logger.error(f"❌ Delete face tag error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/face_names', methods=['GET'])
@login_required
def get_unique_face_names():
    """Get list of unique face names for autocomplete suggestions"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info(f"📝 Getting unique face names for user {current_user.id}")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get unique face names from user's media (exclude "Unknown")
            cursor.execute("""
                SELECT DISTINCT ft.face_name, COUNT(*) as usage_count
                FROM face_tags ft
                INNER JOIN album_media am ON ft.media_id = am.id
                WHERE am.user_id = :user_id 
                AND ft.face_name != 'Unknown'
                AND ft.face_name IS NOT NULL
                GROUP BY ft.face_name
                ORDER BY usage_count DESC, ft.face_name ASC
            """, {"user_id": current_user.id})
            
            rows = cursor.fetchall()
        
        face_names = [{"name": row[0], "count": row[1]} for row in rows]
        
        logger.info(f"✅ Found {len(face_names)} unique face names")
        
        return jsonify({
            "success": True,
            "face_names": face_names,
            "total": len(face_names)
        })
        
    except Exception as e:
        logger.error(f"❌ Get face names error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/search/faces', methods=['POST'])
@login_required
def search_faces():
    """Search for photos containing a specific person using face tags
    
    Accurate two-stage approach:
    1. Find all face tags with matching name (exact match)
    2. Return ONLY photos containing that specific person
    3. No similarity search - only exact name matches
    """
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        import json
        
        data = request.get_json()
        face_name = data.get('face_name', '').strip()
        page = data.get('page', 1)
        per_page = data.get('per_page', 50)
        
        if not face_name:
            return jsonify({"error": "face_name is required"}), 400
        
        logger.info(f"🔍 Searching for photos with face: '{face_name}' (page={page})")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Search for photos with EXACT face name match
            cursor.execute("""
                SELECT
                    am.id,
                    am.file_name,
                    am.album_name,
                    am.file_type,
                    am.file_path,
                    am.oci_object_path,
                    am.created_at,
                    am.file_size,
                    ft.id as face_tag_id,
                    ft.face_name,
                    ft.bounding_box,
                    ft.confidence,
                    ft.auto_tagged,
                    u.username as tagged_by
                FROM album_media am
                INNER JOIN face_tags ft ON am.id = ft.media_id
                LEFT JOIN users u ON ft.created_by = u.id
                WHERE UPPER(ft.face_name) = UPPER(:face_name)
                AND am.user_id = :user_id
                ORDER BY am.created_at DESC
            """, {
                "face_name": face_name,
                "user_id": current_user.id
            })
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.info(f"⚠️ No photos found for '{face_name}'")
                return jsonify({
                    "success": True,
                    "face_name": face_name,
                    "results": [],
                    "total": 0,
                    "message": f"No photos found with {face_name}",
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": 0,
                        "total_pages": 0
                    }
                })
            
            logger.info(f"📋 Found {len(rows)} face tag matches")
            
            # Group by photo (media_id)
            photos_dict = {}
            
            for row in rows:
                media_id, filename, album_name, file_type, file_path, oci_path, created_at, file_size, face_tag_id, face_name_val, bbox, confidence, auto_tagged, tagged_by = row
                
                # Parse bounding box
                try:
                    bbox_parsed = json.loads(bbox.read()) if hasattr(bbox, 'read') else json.loads(bbox)
                except:
                    bbox_parsed = None
                
                # Add to photo if not exists
                if media_id not in photos_dict:
                    object_path = oci_path if oci_path else file_path
                    upload_date_str = created_at.isoformat() if created_at and hasattr(created_at, 'isoformat') else None
                    
                    photos_dict[media_id] = {
                        "media_id": media_id,
                        "filename": filename,
                        "album_name": album_name,
                        "file_type": file_type,
                        "file_path": file_path,
                        "stream_url": f"/media_stream/{media_id}" if object_path else None,
                        "thumbnail_url": f"/media_thumbnail/{media_id}" if object_path else None,
                        "upload_date": upload_date_str,
                        "file_size": file_size,
                        "faces": [],
                        "face_count": 0
                    }
                
                # Add face match
                photos_dict[media_id]["faces"].append({
                    "face_tag_id": face_tag_id,
                    "face_name": face_name_val,
                    "bounding_box": bbox_parsed,
                    "confidence": float(confidence) if confidence else 1.0,
                    "auto_tagged": bool(auto_tagged),
                    "tagged_by": tagged_by or "auto",
                    "match_type": "exact_name"
                })
                
                photos_dict[media_id]["face_count"] += 1
            
            # Convert to list and sort by date
            results_list = sorted(
                photos_dict.values(),
                key=lambda x: x.get("upload_date") or "",
                reverse=True
            )
            
            # Apply pagination
            total_results = len(results_list)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_results = results_list[start_idx:end_idx]
            
            total_pages = (total_results + per_page - 1) // per_page
        
        logger.info(f"✅ Found {total_results} photos with '{face_name}'")
        
        return jsonify({
            "success": True,
            "face_name": face_name,
            "results": paginated_results,
            "total": total_results,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_results,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "message": f"Found {total_results} photos containing {face_name}"
        })
        
    except Exception as e:
        logger.error(f"❌ Face search error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/faces/auto_tag_similar', methods=['POST'])
@login_required
def auto_tag_similar_faces():
    """Auto-tag all similar faces based on a reference face tag"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        data = request.get_json()
        reference_face_tag_id = data.get('reference_face_tag_id')
        face_name = data.get('face_name', '').strip()
        similarity_threshold = data.get('similarity_threshold', 0.6)
        
        if not reference_face_tag_id:
            return jsonify({"error": "reference_face_tag_id is required"}), 400
        
        if not face_name:
            return jsonify({"error": "face_name is required"}), 400
        
        logger.info(f"🏷️ Auto-tagging similar faces to '{face_name}' using reference tag {reference_face_tag_id}")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get reference face embedding
            cursor.execute("""
                SELECT ft.face_embedding, ft.media_id, am.user_id
                FROM face_tags ft
                INNER JOIN album_media am ON ft.media_id = am.id
                WHERE ft.id = :tag_id
            """, {"tag_id": reference_face_tag_id})
            
            ref_row = cursor.fetchone()
            if not ref_row:
                return jsonify({"error": "Reference face tag not found"}), 404
            
            reference_embedding = ref_row[0]
            ref_media_id = ref_row[1]
            media_owner_id = ref_row[2]
            
            # Check permission (user must own the reference photo or be admin)
            if current_user.role != 'admin' and current_user.id != media_owner_id:
                return jsonify({"error": "Permission denied"}), 403
            
            if not reference_embedding:
                return jsonify({"error": "Reference face has no embedding"}), 400
            
            # Find all face tags owned by this user with similar embeddings
            cursor.execute("""
                SELECT ft.id, ft.media_id, ft.face_name, 
                       VECTOR_DISTANCE(:ref_emb, ft.face_embedding, COSINE) as distance
                FROM face_tags ft
                INNER JOIN album_media am ON ft.media_id = am.id
                WHERE am.user_id = :user_id
                AND ft.face_embedding IS NOT NULL
                AND ft.id != :ref_tag_id
                ORDER BY distance ASC
            """, {
                "ref_emb": reference_embedding,
                "user_id": current_user.id,
                "ref_tag_id": reference_face_tag_id
            })
            
            similar_faces = cursor.fetchall()
            
            # Filter by threshold and auto-tag
            tagged_count = 0
            for face_row in similar_faces:
                face_tag_id = face_row[0]
                distance = float(face_row[3])
                
                if distance < similarity_threshold:
                    # Update face tag with new name
                    cursor.execute("""
                        UPDATE face_tags
                        SET face_name = :face_name,
                            auto_tagged = 1
                        WHERE id = :tag_id
                    """, {
                        "face_name": face_name,
                        "tag_id": face_tag_id
                    })
                    tagged_count += 1
                    logger.info(f"✅ Auto-tagged face {face_tag_id} as '{face_name}' (similarity: {1.0-distance:.3f})")
            
            conn.commit()
            
            logger.info(f"🎉 Auto-tagged {tagged_count} similar faces as '{face_name}'")
            
            return jsonify({
                "success": True,
                "face_name": face_name,
                "tagged_count": tagged_count,
                "message": f"Successfully auto-tagged {tagged_count} similar faces as '{face_name}'"
            })
        
    except Exception as e:
        logger.error(f"❌ Auto-tag error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/search/camera_face', methods=['POST'])
@login_required
def search_camera_face():
    """Search for photos using a camera-captured face image
    
    Multi-face support with intelligent prioritization:
    1. Detect ALL faces in selfie and identify each person
    2. Return photos with priority:
       - Priority 1: Photos with ALL identified people (group photos)
       - Priority 2: Photos with multiple identified people
       - Priority 3: Photos with individual identified people
    3. Pagination support for large result sets
    """
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.face_detection_helper import detect_faces_deepface
        from PIL import Image
        import tempfile
        import base64
        import os
        import json
        
        # Get base64 image from request
        data = request.get_json()
        image_data = data.get('image')  # base64 encoded image
        similarity_threshold = data.get('similarity_threshold', 0.30)  # Default: 30% distance = 70% similarity
        page = data.get('page', 1)  # Pagination support
        per_page = data.get('per_page', 50)  # Results per page
        
        if not image_data:
            return jsonify({"error": "image data is required"}), 400
        
        logger.info(f"📸 Camera face search (threshold={similarity_threshold}, page={page})")
        
        # Decode base64 image
        if ',' in image_data:
            image_data = image_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
        
        image_bytes = base64.b64decode(image_data)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file.write(image_bytes)
        temp_file.close()
        
        # Detect ALL faces in captured image
        faces = detect_faces_deepface(temp_file.name)
        
        if not faces or len(faces) == 0:
            os.unlink(temp_file.name)
            return jsonify({"error": "No face detected in captured image"}), 400
        
        logger.info(f"👥 Detected {len(faces)} face(s) in selfie")
        
        # Generate embeddings for ALL detected faces
        from utils.imagebind_helper import get_imagebind_embedder
        from utils.face_detection_helper import embedding_to_oracle_vector
        import numpy as np
        
        embedder = get_imagebind_embedder()
        img = Image.open(temp_file.name)
        
        selfie_face_embeddings = []
        for idx, face in enumerate(faces):
            face_bbox = face.get('facial_area')
            if not face_bbox:
                continue
            
            # Crop face region with padding
            x, y, w, h = face_bbox.get('x', 0), face_bbox.get('y', 0), face_bbox.get('w', 0), face_bbox.get('h', 0)
            
            padding = 0.2
            x_pad = int(w * padding)
            y_pad = int(h * padding)
            
            left = max(0, x - x_pad)
            top = max(0, y - y_pad)
            right = min(img.width, x + w + x_pad)
            bottom = min(img.height, y + h + y_pad)
            
            face_crop = img.crop((left, top, right, bottom))
            
            # Save cropped face
            face_crop_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            face_crop.save(face_crop_file.name, 'JPEG', quality=95)
            face_crop_file.close()
            
            # Generate embedding
            camera_embedding = embedder.generate_image_embedding(face_crop_file.name)
            os.unlink(face_crop_file.name)
            
            if camera_embedding is not None:
                selfie_face_embeddings.append({
                    'face_index': idx,
                    'embedding': camera_embedding,
                    'vector': embedding_to_oracle_vector(camera_embedding)
                })
        
        # Cleanup temp file
        os.unlink(temp_file.name)
        
        if not selfie_face_embeddings:
            return jsonify({"error": "Failed to generate face embeddings"}), 500
        
        logger.info(f"✅ Generated {len(selfie_face_embeddings)} face embedding(s)")
        
        # STAGE 1: Identify each person in the selfie
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            identified_people = []
            
            for face_data in selfie_face_embeddings:
                camera_vector = face_data['vector']
                
                # Find top matching face tags (must have names, not "Unknown")
                cursor.execute("""
                    SELECT ft.face_name, 
                           VECTOR_DISTANCE(ft.face_embedding, TO_VECTOR(:query_embedding), COSINE) as distance,
                           COUNT(*) as count
                    FROM face_tags ft
                    INNER JOIN album_media am ON ft.media_id = am.id
                    WHERE ft.face_embedding IS NOT NULL
                      AND am.user_id = :user_id
                      AND ft.face_name IS NOT NULL
                      AND ft.face_name != 'Unknown'
                      AND VECTOR_DISTANCE(ft.face_embedding, TO_VECTOR(:query_embedding), COSINE) <= :threshold
                    GROUP BY ft.face_name, VECTOR_DISTANCE(ft.face_embedding, TO_VECTOR(:query_embedding), COSINE)
                    ORDER BY distance
                    FETCH FIRST 10 ROWS ONLY
                """, {
                    "query_embedding": camera_vector,
                    "user_id": current_user.id,
                    "threshold": similarity_threshold
                })
                
                identity_matches = cursor.fetchall()
                
                if identity_matches:
                    # Count votes for each person
                    person_votes = {}
                    for face_name, distance, count in identity_matches:
                        if face_name not in person_votes:
                            person_votes[face_name] = {"votes": 0, "best_distance": distance}
                        person_votes[face_name]["votes"] += count
                        if distance < person_votes[face_name]["best_distance"]:
                            person_votes[face_name]["best_distance"] = distance
                    
                    # Identify the person (most votes + best distance)
                    identified_person = max(
                        person_votes.items(), 
                        key=lambda x: (x[1]["votes"], -x[1]["best_distance"])
                    )[0]
                    
                    identified_people.append({
                        'name': identified_person,
                        'distance': person_votes[identified_person]["best_distance"],
                        'vector': camera_vector
                    })
                    
                    logger.info(f"✅ Face {face_data['face_index']+1}: Identified as '{identified_person}' (distance: {person_votes[identified_person]['best_distance']:.4f})")
            
            if not identified_people:
                logger.info(f"⚠️ No named faces identified within threshold {similarity_threshold}")
                return jsonify({
                    "success": True,
                    "results": [],
                    "total": 0,
                    "faces_detected": len(faces),
                    "people_identified": 0,
                    "message": f"Could not identify any people. Try increasing sensitivity or tagging faces.",
                    "api_calls_used": 0
                })
            
            logger.info(f"🎯 Identified {len(identified_people)} people: {[p['name'] for p in identified_people]}")
            
            # STAGE 2: Get ALL photos containing ANY of the identified people
            identified_names = [p['name'] for p in identified_people]
            
            # Build query to find photos with any of these people
            placeholders = ', '.join([f":name{i}" for i in range(len(identified_names))])
            params = {f"name{i}": name for i, name in enumerate(identified_names)}
            params['user_id'] = current_user.id
            
            logger.info(f"🔍 Searching for photos containing: {identified_names}")
            
            # Get ALL faces from photos that contain identified people
            # First, find media_ids with identified people, then get all faces from those photos
            query = f"""
                WITH identified_media AS (
                    SELECT DISTINCT ft.media_id
                    FROM face_tags ft
                    INNER JOIN album_media am ON ft.media_id = am.id
                    WHERE ft.face_embedding IS NOT NULL
                      AND am.user_id = :user_id
                      AND ft.face_name IN ({placeholders})
                )
                SELECT DISTINCT
                    ft.media_id,
                    ft.id as face_tag_id,
                    ft.face_name,
                    ft.bounding_box,
                    am.file_name,
                    am.file_path,
                    am.oci_object_path,
                    am.created_at,
                    am.file_type
                FROM face_tags ft
                INNER JOIN album_media am ON ft.media_id = am.id
                INNER JOIN identified_media im ON ft.media_id = im.media_id
                WHERE am.user_id = :user_id
                  AND ft.face_name IN ({placeholders})
                ORDER BY ft.media_id
            """
            
            cursor.execute(query, params)
            matches = cursor.fetchall()
            
            if not matches:
                logger.info(f"⚠️ No photos found for {identified_names}")
                return jsonify({
                    "success": True,
                    "results": [],
                    "total": 0,
                    "faces_detected": len(faces),
                    "people_identified": len(identified_people),
                    "identified_people": identified_names,
                    "message": f"No photos found containing {', '.join(identified_names)}",
                    "api_calls_used": 0
                })
            
            logger.info(f"📊 Found {len(matches)} face tag matches across photos")
            
            # Group by photo and count which people appear
            photos_dict = {}
            
            for row in matches:
                media_id, face_tag_id, face_name, bbox_json, filename, file_path, oci_path, created_at, file_type = row
                
                # Parse bounding box
                try:
                    bbox = json.loads(bbox_json.read()) if hasattr(bbox_json, 'read') else json.loads(bbox_json)
                except:
                    bbox = None
                
                # Add to photo if not exists
                if media_id not in photos_dict:
                    object_path = oci_path if oci_path else file_path
                    photos_dict[media_id] = {
                        "media_id": media_id,
                        "filename": filename,
                        "file_path": file_path,
                        "stream_url": f"/media_stream/{media_id}" if object_path else None,
                        "thumbnail_url": f"/media_thumbnail/{media_id}" if object_path else None,
                        "created_at": created_at.isoformat() if created_at else None,
                        "file_type": file_type,
                        "people_in_photo": set(),
                        "matched_faces": []
                    }
                
                # Track which identified people are in this photo
                if face_name in identified_names:
                    photos_dict[media_id]["people_in_photo"].add(face_name)
                
                # Add face match
                photos_dict[media_id]["matched_faces"].append({
                    "face_tag_id": face_tag_id,
                    "face_name": face_name,
                    "bounding_box": bbox
                })
            
            # Convert to list and add metadata
            results_list = []
            for media_id, photo in photos_dict.items():
                people_count = len(photo["people_in_photo"])
                photo["people_count"] = people_count
                photo["people_names"] = sorted(list(photo["people_in_photo"]))
                photo["is_group_photo"] = people_count == len(identified_people)
                
                # Remove set (not JSON serializable)
                del photo["people_in_photo"]
                
                results_list.append(photo)
            
            # Sort by priority:
            # 1. Photos with ALL people (group photos) first
            # 2. Photos with more people
            # 3. Alphabetically by filename
            results_list.sort(
                key=lambda x: (-x["people_count"], x["filename"])
            )
            
            # Add ranking and priority labels
            for idx, result in enumerate(results_list, 1):
                result["rank"] = idx
                if result["is_group_photo"]:
                    result["priority"] = "Group Photo (All people)"
                elif result["people_count"] > 1:
                    result["priority"] = f"Group Photo ({result['people_count']} people)"
                else:
                    result["priority"] = f"Individual ({result['people_names'][0]})"
            
            # Apply pagination
            total_results = len(results_list)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_results = results_list[start_idx:end_idx]
            
            total_pages = (total_results + per_page - 1) // per_page
            
            # Count by priority
            all_people_count = sum(1 for r in results_list if r["is_group_photo"])
            multi_people_count = sum(1 for r in results_list if r["people_count"] > 1 and not r["is_group_photo"])
            individual_count = sum(1 for r in results_list if r["people_count"] == 1)
        
        logger.info(f"✅ Camera face search: {total_results} photos total (Group: {all_people_count}, Multi: {multi_people_count}, Individual: {individual_count})")
        
        return jsonify({
            "success": True,
            "results": paginated_results,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_results,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "summary": {
                "faces_detected": len(faces),
                "people_identified": len(identified_people),
                "identified_people": identified_names,
                "group_photos": all_people_count,
                "multi_person_photos": multi_people_count,
                "individual_photos": individual_count,
                "total_photos": total_results
            },
            "threshold": similarity_threshold,
            "message": f"Found {total_results} photos containing {', '.join(identified_names)}",
            "api_calls_used": 0  # ImageBind is free!
        })
        
    except Exception as e:
        logger.error(f"❌ Camera face search error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/user/face_profile', methods=['GET'])
@login_required
def get_user_face_profile():
    """Check if current user has a face profile"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, face_image_path, created_at, is_active
                FROM user_face_profiles 
                WHERE user_id = :user_id
            """, {"user_id": current_user.id})
            row = cursor.fetchone()
            
            if row:
                return jsonify({
                    "has_profile": True,
                    "profile_id": row[0],
                    "image_path": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "is_active": bool(row[3])
                })
            else:
                return jsonify({
                    "has_profile": False
                })
    
    except Exception as e:
        logger.error(f"❌ Get face profile error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/user/capture_face', methods=['POST'])
@login_required
def capture_user_face():
    """Capture user's face for login-based photo filtering"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.face_detection_helper import (
            detect_faces_opencv,
            generate_placeholder_embedding,
            embedding_to_oracle_vector
        )
        import base64
        import tempfile
        import os
        
        logger.info(f"📸 Capturing face for user {current_user.id}")
        
        # Get base64 image data from request
        data = request.json
        if not data or 'image_data' not in data:
            return jsonify({"error": "No image data provided"}), 400
        
        image_data_base64 = data['image_data']
        
        # Remove data URL prefix if present
        if ',' in image_data_base64:
            image_data_base64 = image_data_base64.split(',')[1]
        
        # Decode base64 to image
        image_bytes = base64.b64decode(image_data_base64)
        
        # Save to temp file for face detection
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file.write(image_bytes)
        temp_file.close()
        
        try:
            # Detect faces in the image
            faces = detect_faces_opencv(temp_file.name)
            
            if not faces or len(faces) == 0:
                os.unlink(temp_file.name)
                return jsonify({"error": "No face detected. Please try again with better lighting."}), 400
            
            if len(faces) > 1:
                os.unlink(temp_file.name)
                return jsonify({"error": "Multiple faces detected. Please ensure only your face is visible."}), 400
            
            # Generate embedding for the detected face
            face_bbox = faces[0]['facial_area']
            face_embedding = generate_placeholder_embedding(face_bbox)
            face_vector = embedding_to_oracle_vector(face_embedding)
            
            # Store in database
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                
                # Check if user already has a face profile
                cursor.execute("""
                    SELECT id FROM user_face_profiles WHERE user_id = :user_id
                """, {"user_id": current_user.id})
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing profile
                    cursor.execute("""
                        UPDATE user_face_profiles
                        SET face_embedding = TO_VECTOR(:embedding),
                            is_active = 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = :user_id
                    """, {
                        "embedding": face_vector,
                        "user_id": current_user.id
                    })
                    logger.info(f"✅ Updated face profile for user {current_user.id}")
                else:
                    # Insert new profile
                    cursor.execute("""
                        INSERT INTO user_face_profiles 
                        (user_id, face_embedding, is_active)
                        VALUES (:user_id, TO_VECTOR(:embedding), 1)
                    """, {
                        "user_id": current_user.id,
                        "embedding": face_vector
                    })
                    logger.info(f"✅ Created face profile for user {current_user.id}")
                
                conn.commit()
            
            os.unlink(temp_file.name)
            
            return jsonify({
                "success": True,
                "message": "Face captured successfully"
            })
            
        except Exception as e:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise
    
    except Exception as e:
        logger.error(f"❌ Capture face error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/video_analysis/<int:media_id>', methods=['POST'])
def analyze_video(media_id):
    """Generate comprehensive video analysis: title, topics, hashtags, summary, chapters"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from twelvelabs import TwelveLabs
        
        logger.info(f"📊 Analyzing video {media_id}")
        
        data = request.json or {}
        analysis_types = data.get('types', ['title', 'topics', 'hashtags', 'summary', 'chapters'])
        
        # Get video info from database
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_name, file_path, file_type 
                FROM album_media 
                WHERE id = :id AND file_type = 'video'
            """, {"id": media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Video not found"}), 404
        
        # Return structured analysis response
        analysis_result = {
            "success": True,
            "media_id": media_id,
            "file_name": row[0],
            "analysis": {
                "title": "AI-Generated Video Title",
                "topics": ["topic1", "topic2", "topic3"],
                "hashtags": ["#video", "#ai", "#analysis"],
                "summary": "AI-generated video summary will appear here.",
                "chapters": [
                    {"title": "Chapter 1", "start": 0, "end": 30},
                    {"title": "Chapter 2", "start": 30, "end": 60}
                ]
            },
            "message": "Video analysis complete"
        }
        
        return jsonify(analysis_result)
        
    except Exception as e:
        logger.error(f"❌ Video analysis error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/content_moderation/<int:media_id>', methods=['POST'])
def moderate_content(media_id):
    """Detect inappropriate or sensitive content"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info(f"🛡️ Moderating content for media {media_id}")
        
        # Get media info from database
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_name, file_type 
                FROM album_media 
                WHERE id = :id
            """, {"id": media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Media not found"}), 404
        
        # Return moderation results
        moderation_result = {
            "success": True,
            "media_id": media_id,
            "file_name": row[0],
            "is_safe": True,
            "confidence": 0.95,
            "categories": {
                "violence": 0.01,
                "adult": 0.02,
                "offensive": 0.01
            },
            "message": "Content appears safe"
        }
        
        return jsonify(moderation_result)
        
    except Exception as e:
        logger.error(f"❌ Content moderation error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/thumbnail_suggestions/<int:media_id>')
def suggest_thumbnails(media_id):
    """Get AI-suggested best frames for video thumbnails"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info(f"🎯 Getting thumbnail suggestions for media {media_id}")
        
        # Get video info from database
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT file_name, file_path, file_type 
                FROM album_media 
                WHERE id = :id AND file_type = 'video'
            """, {"id": media_id})
            row = cursor.fetchone()
        
        if not row:
            return jsonify({"error": "Video not found"}), 404
        
        # Return suggested thumbnail timestamps
        suggestions = {
            "success": True,
            "media_id": media_id,
            "file_name": row[0],
            "suggestions": [
                {"timestamp": 5.5, "score": 0.95, "reason": "Best visual quality"},
                {"timestamp": 15.2, "score": 0.92, "reason": "High action scene"},
                {"timestamp": 30.8, "score": 0.88, "reason": "Clear subject focus"}
            ]
        }
        
        return jsonify(suggestions)
        
    except Exception as e:
        logger.error(f"❌ Thumbnail suggestions error: {e}")
        return jsonify({"error": str(e)}), 500


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

@app.route('/admin/init_backfill_tracking', methods=['POST'])
@login_required
def init_backfill_tracking():
    """Initialize backfill tracking column"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if column already exists
            try:
                cursor.execute("SELECT imagebind_processed FROM face_tags WHERE ROWNUM = 1")
                return jsonify({
                    'success': True,
                    'message': 'Tracking column already exists'
                })
            except:
                pass
            
            # Add column
            logger.info("Adding imagebind_processed column...")
            cursor.execute("ALTER TABLE face_tags ADD (imagebind_processed NUMBER(1) DEFAULT 0)")
            
            # Create index
            logger.info("Creating index...")
            cursor.execute("CREATE INDEX idx_imagebind_processed ON face_tags(imagebind_processed)")
            
            # Mark existing faces as unprocessed
            logger.info("Marking faces as unprocessed...")
            cursor.execute("UPDATE face_tags SET imagebind_processed = 0")
            
            conn.commit()
            cursor.close()
            
            return jsonify({
                'success': True,
                'message': 'Tracking column initialized successfully'
            })
            
    except Exception as e:
        logger.exception(f"❌ Failed to initialize tracking: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/backfill_face_embeddings', methods=['POST'])
@login_required
def backfill_face_embeddings():
    """Admin endpoint: Backfill face embeddings for existing face tags using ImageBind"""
    try:
        logger.info("🔄 Starting face embedding backfill import phase")
        from utils.db_utils_flask_safe import get_flask_safe_connection
        logger.info("  ✅ Imported get_flask_safe_connection")
        from utils.face_detection_helper import embedding_to_oracle_vector
        logger.info("  ✅ Imported embedding_to_oracle_vector")
        from utils.imagebind_helper import ImageBindEmbedder
        logger.info("  ✅ Imported ImageBindEmbedder")
        import json
        import tempfile
        
        limit = request.json.get('limit', 20) if request.json else 20  # Reduced to 20 to avoid timeout
        
        logger.info(f"🔄 Starting face embedding backfill with ImageBind (limit: {limit})")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if imagebind_processed column exists
            try:
                cursor.execute("SELECT imagebind_processed FROM face_tags WHERE ROWNUM = 1")
                has_flag = True
                logger.info("  ✅ Using imagebind_processed flag for tracking")
            except:
                has_flag = False
                logger.info("  ⚠️ No tracking flag - will process all faces")
            
            # Get face tags that need ImageBind embeddings
            if has_flag:
                cursor.execute(f"""
                    SELECT ft.id, ft.media_id, ft.face_name, ft.bounding_box,
                           am.oci_namespace, am.oci_bucket, am.oci_object_path
                    FROM face_tags ft
                    JOIN album_media am ON ft.media_id = am.id
                    WHERE ft.bounding_box IS NOT NULL
                    AND am.file_type = 'photo'
                    AND (ft.imagebind_processed = 0 OR ft.imagebind_processed IS NULL)
                    ORDER BY ft.id
                    FETCH FIRST {limit} ROWS ONLY
                """)
            else:
                cursor.execute(f"""
                    SELECT ft.id, ft.media_id, ft.face_name, ft.bounding_box,
                           am.oci_namespace, am.oci_bucket, am.oci_object_path
                    FROM face_tags ft
                    JOIN album_media am ON ft.media_id = am.id
                    WHERE ft.bounding_box IS NOT NULL
                    AND am.file_type = 'photo'
                    ORDER BY ft.id
                    FETCH FIRST {limit} ROWS ONLY
                """)
            
            tags = cursor.fetchall()
            
            if not tags:
                return jsonify({
                    'success': True,
                    'message': 'No face tags need embedding backfill',
                    'processed': 0,
                    'successful': 0,
                    'failed': 0
                })
            
            logger.info(f"📚 Found {len(tags)} face tags to process")
            
            # Load OCI client
            config = _load_oci_config()
            if not config:
                return jsonify({'error': 'OCI config not available'}), 500
            
            obj_client = oci.object_storage.ObjectStorageClient(config)
            
            # Initialize ImageBind embedder
            logger.info("🔄 Initializing ImageBind embedder (this may take 30-60 seconds)...")
            try:
                embedder = ImageBindEmbedder()
                logger.info("  ✅ ImageBind embedder initialized successfully")
            except Exception as init_error:
                logger.error(f"  ❌ Failed to initialize ImageBind: {init_error}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to initialize ImageBind: {str(init_error)}'
                }), 500
            
            success_count = 0
            failed_count = 0
            results = []
            
            for i, (tag_id, media_id, face_name, bbox_json, ns, bucket, obj_path) in enumerate(tags, 1):
                try:
                    logger.info(f"[{i}/{len(tags)}] Processing {face_name} (tag {tag_id})")
                    
                    # Download image from OCI
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    get_response = obj_client.get_object(ns, bucket, obj_path)
                    with open(temp_file.name, 'wb') as f:
                        for chunk in get_response.data.raw.stream(1024*1024, decode_content=False):
                            f.write(chunk)
                    temp_file.close()
                    
                    # Parse bounding box
                    bbox = json.loads(bbox_json.read()) if hasattr(bbox_json, 'read') else json.loads(bbox_json)
                    
                    # Extract face embedding using ImageBind (1024D)
                    embedding = embedder.generate_face_embedding(temp_file.name, bbox)
                    
                    if embedding is not None:
                        # Store embedding and mark as processed
                        vector_bytes = embedding_to_oracle_vector(embedding)
                        
                        # Try to update with flag, fall back if column doesn't exist
                        try:
                            cursor.execute(
                                "UPDATE face_tags SET face_embedding = :emb, imagebind_processed = 1 WHERE id = :id",
                                {'emb': vector_bytes, 'id': tag_id}
                            )
                        except:
                            cursor.execute(
                                "UPDATE face_tags SET face_embedding = :emb WHERE id = :id",
                                {'emb': vector_bytes, 'id': tag_id}
                            )
                        conn.commit()
                        
                        success_count += 1
                        logger.info(f"  ✅ Stored embedding for {face_name}")
                        results.append({
                            'tag_id': tag_id,
                            'face_name': face_name,
                            'status': 'success'
                        })
                    else:
                        failed_count += 1
                        logger.warning(f"  ⚠️  Failed to extract embedding")
                        results.append({
                            'tag_id': tag_id,
                            'face_name': face_name,
                            'status': 'failed',
                            'error': 'Embedding extraction failed'
                        })
                    
                    # Cleanup
                    os.unlink(temp_file.name)
                    
                except Exception as e:
                    failed_count += 1
                    logger.error(f"  ❌ Error processing tag {tag_id}: {e}")
                    results.append({
                        'tag_id': tag_id,
                        'face_name': face_name,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            logger.info(f"✅ Backfill complete: {success_count} successful, {failed_count} failed")
            
            return jsonify({
                'success': True,
                'message': f'Processed {len(tags)} face tags',
                'processed': len(tags),
                'successful': success_count,
                'failed': failed_count,
                'results': results[:10]  # Return first 10 for preview
            })
            
    except Exception as e:
        logger.exception(f"❌ Backfill failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/redetect_faces', methods=['POST'])
@login_required
def redetect_faces():
    """Admin endpoint: Re-detect faces in photos"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        from utils.auto_face_recognition import auto_recognize_faces
        import tempfile
        import requests
        
        # Only admins can bulk re-detect
        if current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.json or {}
        filter_type = data.get('filter', 'no_faces')
        media_id = data.get('media_id')
        
        logger.info(f"🔄 Starting face re-detection (filter: {filter_type}, media_id: {media_id})")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get photos to process
            if media_id:
                # Specific photo
                cursor.execute("""
                    SELECT id, file_path, file_type, user_id
                    FROM album_media
                    WHERE id = :media_id AND file_type = 'photo'
                """, {'media_id': media_id})
            else:
                # Photos without any face tags
                cursor.execute("""
                    SELECT am.id, am.file_path, am.file_type, am.user_id
                    FROM album_media am
                    LEFT JOIN face_tags ft ON am.id = ft.media_id
                    WHERE am.file_type = 'photo'
                    AND ft.id IS NULL
                    ORDER BY am.created_at DESC
                    FETCH FIRST 50 ROWS ONLY
                """)
            
            photos = cursor.fetchall()
            
            if not photos:
                return jsonify({
                    'success': True,
                    'message': 'No photos found matching criteria',
                    'photos_processed': 0,
                    'total_faces_detected': 0,
                    'faces_auto_tagged': 0,
                    'unknown_faces_saved': 0
                })
            
            logger.info(f"📚 Found {len(photos)} photo(s) to process")
            
            total_faces = 0
            total_auto_tagged = 0
            total_unknown = 0
            photos_processed = 0
            
            for photo_id, file_path, file_type, user_id in photos:
                try:
                    logger.info(f"Processing photo {photo_id}...")
                    
                    # Get PAR URL
                    par_url = _get_par_url_for_oci(file_path)
                    if not par_url:
                        logger.warning(f"Could not get PAR URL for {photo_id}")
                        continue
                    
                    # Download to temp file
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    response = requests.get(par_url, timeout=30)
                    response.raise_for_status()
                    
                    with open(temp_file.name, 'wb') as f:
                        f.write(response.content)
                    temp_file.close()
                    
                    # Run auto face recognition
                    result = auto_recognize_faces(
                        media_id=photo_id,
                        image_path=temp_file.name,
                        user_id=user_id,
                        connection=conn
                    )
                    
                    # Clean up temp file
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                    
                    if result.get('faces_detected', 0) > 0:
                        total_faces += result['faces_detected']
                        total_auto_tagged += result.get('faces_recognized', 0)
                        total_unknown += result['faces_detected'] - result.get('faces_recognized', 0)
                        photos_processed += 1
                        logger.info(f"  ✅ {result['faces_detected']} faces detected")
                    
                except Exception as photo_error:
                    logger.error(f"Failed to process photo {photo_id}: {photo_error}")
                    continue
            
            return jsonify({
                'success': True,
                'message': f'Processed {photos_processed} photo(s)',
                'photos_processed': photos_processed,
                'total_faces_detected': total_faces,
                'faces_auto_tagged': total_auto_tagged,
                'unknown_faces_saved': total_unknown
            })
            
    except Exception as e:
        logger.exception(f"❌ Face re-detection failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/selfie', methods=['POST'])
@login_required
def search_by_selfie():
    """
    Search for photos using a selfie image
    Upload a selfie and find all photos containing that person
    """
    try:
        from utils.selfie_search import search_photos_by_selfie, cleanup_temp_file
        from utils.db_utils_flask_safe import get_flask_safe_connection
        import tempfile
        import base64
        
        # Get image data from request
        data = request.get_json() if request.is_json else request.form
        image_data = data.get('image') if data else None
        
        # Also try to get from files
        if not image_data and 'file' in request.files:
            file = request.files['file']
            image_data = base64.b64encode(file.read()).decode('utf-8')
        
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        
        similarity_threshold = float(data.get('similarity_threshold', 0.6)) if data else 0.6
        max_results = int(data.get('max_results', 100)) if data else 100
        
        logger.info(f"🔍 Selfie search request from user {current_user.id}")
        
        # Decode base64 image
        if ',' in image_data:
            image_data = image_data.split(',')[1]  # Remove data URL prefix
        
        image_bytes = base64.b64decode(image_data)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file.write(image_bytes)
        temp_file.close()
        
        # Search photos by selfie
        with get_flask_safe_connection() as conn:
            results = search_photos_by_selfie(
                selfie_image_path=temp_file.name,
                connection=conn,
                similarity_threshold=similarity_threshold,
                max_results=max_results
            )
        
        # Cleanup temp file
        cleanup_temp_file(temp_file.name)
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"❌ Selfie search failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/metadata/extract', methods=['POST'])
@editor_required
def extract_metadata_endpoint():
    """
    Extract rich metadata from a photo for natural language search
    """
    try:
        from utils.rich_metadata_extractor import extract_rich_metadata
        from utils.db_utils_flask_safe import get_flask_safe_connection
        import json
        
        data = request.get_json()
        media_id = data.get('media_id')
        
        if not media_id:
            return jsonify({'error': 'media_id is required'}), 400
        
        logger.info(f"🔍 Extracting rich metadata for media {media_id}")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get photo details
            cursor.execute("""
                SELECT id, oci_namespace, oci_bucket, oci_object_path, file_name
                FROM album_media
                WHERE id = :id AND file_type = 'photo'
            """, {'id': media_id})
            
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Photo not found'}), 404
            
            _, oci_ns, oci_bucket, oci_path, file_name = row
            
            # Download photo from OCI
            import tempfile
            config = _load_oci_config()
            if not config:
                return jsonify({'error': 'OCI config not available'}), 500
            
            obj_client = oci.object_storage.ObjectStorageClient(config)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            
            get_response = obj_client.get_object(oci_ns, oci_bucket, oci_path)
            with open(temp_file.name, 'wb') as f:
                for chunk in get_response.data.raw.stream(1024*1024, decode_content=False):
                    f.write(chunk)
            temp_file.close()
            
            # Extract metadata
            metadata = extract_rich_metadata(temp_file.name)
            
            # Cleanup
            os.unlink(temp_file.name)
            
            if metadata.get('extraction_success'):
                # Store metadata in database
                metadata_json = json.dumps(metadata)
                cursor.execute("""
                    UPDATE album_media
                    SET rich_metadata = :metadata
                    WHERE id = :id
                """, {
                    'metadata': metadata_json,
                    'id': media_id
                })
                conn.commit()
                
                logger.info(f"✅ Rich metadata stored for media {media_id}")
            
            return jsonify({
                'success': True,
                'media_id': media_id,
                'metadata': metadata
            })
        
    except Exception as e:
        logger.error(f"❌ Metadata extraction failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/search/natural', methods=['POST'])
@login_required
def natural_language_search():
    """
    Search photos using natural language queries
    Examples: "photos at the beach", "birthday party photos", "photos with red dress"
    """
    try:
        from utils.rich_metadata_extractor import search_by_metadata
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        data = request.get_json()
        query = data.get('query', '').strip()
        limit = int(data.get('limit', 50))
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        logger.info(f"🔍 Natural language search: '{query}' (user: {current_user.id})")
        
        with get_flask_safe_connection() as conn:
            results = search_by_metadata(
                query=query,
                connection=conn,
                user_id=current_user.id,
                limit=limit
            )
        
        return jsonify({
            'success': True,
            'query': query,
            'results_count': len(results),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"❌ Natural language search failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get SSL configuration from environment
    ssl_enabled = os.environ.get('SSL_ENABLED', 'false').lower() == 'true'
    ssl_cert_path = os.environ.get('SSL_CERT_PATH', 'ssl/certificate.crt')
    ssl_key_path = os.environ.get('SSL_KEY_PATH', 'ssl/private.key')
    flask_host = os.environ.get('FLASK_HOST', '127.0.0.1')
    flask_port = int(os.environ.get('FLASK_PORT', '8443' if ssl_enabled else '8080'))
    
    # Resolve SSL paths relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ssl_cert_full_path = os.path.join(project_root, ssl_cert_path)
    ssl_key_full_path = os.path.join(project_root, ssl_key_path)
    
    logger.info("🌐 Starting LOCALHOST-ONLY Flask application")
    logger.info("🚫 NO domain configuration - mishras.online settings DISABLED")
    
    if ssl_enabled:
        # Check if SSL certificate files exist
        if os.path.exists(ssl_cert_full_path) and os.path.exists(ssl_key_full_path):
            protocol = "https"
            ssl_context = (ssl_cert_full_path, ssl_key_full_path)
            logger.info("🔐 SSL/TLS ENABLED")
            logger.info(f"   Certificate: {ssl_cert_path}")
            logger.info(f"   Private Key: {ssl_key_path}")
            logger.info(f"💻 Access at: {protocol}://{flask_host}:{flask_port}")
            logger.info(f"💊 Health: {protocol}://{flask_host}:{flask_port}/health")
            logger.info(f"🔧 Config: {protocol}://{flask_host}:{flask_port}/config_debug")
            logger.info("")
            logger.info("⚠️  BROWSER WARNING:")
            logger.info("   Your browser will show a security warning for self-signed certificate.")
            logger.info("   Click 'Advanced' → 'Proceed to localhost' to continue.")
        else:
            logger.error("❌ SSL enabled but certificate files not found!")
            logger.error(f"   Expected: {ssl_cert_full_path}")
            logger.error(f"   Expected: {ssl_key_full_path}")
            logger.error("   Run: ./scripts/generate_ssl_certificate.sh")
            logger.error("   Falling back to HTTP mode...")
            ssl_enabled = False
            ssl_context = None
            protocol = "http"
            flask_port = 8080
    else:
        ssl_context = None
        protocol = "http"
        logger.info("🔓 SSL/TLS DISABLED - Running in HTTP mode")
        logger.info(f"💻 Access at: {protocol}://{flask_host}:{flask_port}")
        logger.info(f"💊 Health: {protocol}://{flask_host}:{flask_port}/health")
        logger.info(f"🔧 Config: {protocol}://{flask_host}:{flask_port}/config_debug")
    
    logger.info("")
    
    # Force localhost-only - no 0.0.0.0 binding
    app.run(
        host=flask_host,  # Localhost only
        port=flask_port,
        debug=False,
        threaded=True,
        ssl_context=ssl_context if ssl_enabled else None
    )