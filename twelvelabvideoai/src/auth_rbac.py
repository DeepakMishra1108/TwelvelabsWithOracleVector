#!/usr/bin/env python3
"""
Authorization and Role-Based Access Control (RBAC) for Data Guardian
Defines permissions for different user roles and provides decorators for route protection
"""

from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

# ==================== ROLE DEFINITIONS ====================
"""
ROLE HIERARCHY AND PERMISSIONS:

1. VIEWER (Read-Only User)
   - View albums and media (only their own)
   - Search photos and videos (only their content)
   - Generate AI tags for existing media
   - View their profile
   - Change their password
   
   CANNOT:
   - Upload new media
   - Create/delete albums
   - Edit/delete media
   - Access other users' content
   - Access admin functions

2. EDITOR (Regular User / Content Creator)
   - All VIEWER permissions
   - Upload photos and videos
   - Create and manage albums (only their own)
   - Edit and delete media (only their own)
   - Create video montages from their content
   - Generate embeddings for their media
   
   CANNOT:
   - Access other users' content
   - Manage users
   - Access admin functions

3. ADMIN (System Administrator)
   - All EDITOR permissions
   - Manage users (create, edit, disable, delete)
   - View all content (for moderation)
   - Access system statistics
   - Manage system settings
   - View audit logs
"""

ROLE_PERMISSIONS = {
    'viewer': {
        'can_view': True,
        'can_search': True,
        'can_tag': True,
        'can_upload': False,
        'can_create_album': False,
        'can_edit': False,
        'can_delete': False,
        'can_admin': False,
        'description': 'Read-only access to own content'
    },
    'editor': {
        'can_view': True,
        'can_search': True,
        'can_tag': True,
        'can_upload': True,
        'can_create_album': True,
        'can_edit': True,
        'can_delete': True,
        'can_admin': False,
        'description': 'Full content management for own content'
    },
    'admin': {
        'can_view': True,
        'can_search': True,
        'can_tag': True,
        'can_upload': True,
        'can_create_album': True,
        'can_edit': True,
        'can_delete': True,
        'can_admin': True,
        'description': 'Full system access including user management'
    }
}


# ==================== PERMISSION CHECKS ====================

def has_permission(user, permission: str) -> bool:
    """Check if user has a specific permission"""
    if not user or not user.is_authenticated:
        return False
    
    role_perms = ROLE_PERMISSIONS.get(user.role, {})
    return role_perms.get(permission, False)


def can_view_content(user) -> bool:
    """Can view content"""
    return has_permission(user, 'can_view')


def can_search(user) -> bool:
    """Can search content"""
    return has_permission(user, 'can_search')


def can_tag(user) -> bool:
    """Can generate AI tags"""
    return has_permission(user, 'can_tag')


def can_upload(user) -> bool:
    """Can upload new media"""
    return has_permission(user, 'can_upload')


def can_create_album(user) -> bool:
    """Can create albums"""
    return has_permission(user, 'can_create_album')


def can_edit(user) -> bool:
    """Can edit media"""
    return has_permission(user, 'can_edit')


def can_delete(user) -> bool:
    """Can delete media"""
    return has_permission(user, 'can_delete')


def can_admin(user) -> bool:
    """Can access admin functions"""
    return has_permission(user, 'can_admin')


# ==================== DECORATORS ====================

def permission_required(permission: str):
    """Decorator to require a specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login'))
            
            if not has_permission(current_user, permission):
                logger.warning(
                    f"Permission denied: User {current_user.username} "
                    f"(role: {current_user.role}) tried to access {permission}"
                )
                flash(f'Access denied. Required permission: {permission}', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def viewer_required(f):
    """Require at least viewer role (all authenticated users)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def editor_required(f):
    """Require editor or admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        
        if current_user.role not in ['editor', 'admin']:
            logger.warning(
                f"Access denied: User {current_user.username} "
                f"(role: {current_user.role}) tried to access editor function"
            )
            flash('Access denied. Editor or Admin role required.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        
        if current_user.role != 'admin':
            logger.warning(
                f"Access denied: User {current_user.username} "
                f"(role: {current_user.role}) tried to access admin function"
            )
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


# ==================== OWNERSHIP CHECKS ====================

def owns_resource(user_id: int, resource_user_id: int) -> bool:
    """Check if user owns a resource"""
    return user_id == resource_user_id


def can_access_resource(user, resource_user_id: int) -> bool:
    """Check if user can access a resource (owner or admin)"""
    if not user or not user.is_authenticated:
        return False
    
    # Admin can access all resources
    if user.role == 'admin':
        return True
    
    # User can access their own resources
    return user.id == resource_user_id


# ==================== HELPER FUNCTIONS ====================

def get_user_storage_path(user_id: int, username: str) -> str:
    """
    Get storage path for user's content
    Format: users/{user_id}_{username}/
    
    This provides:
    - Isolation between users
    - Easy identification
    - Consistent structure
    """
    return f"users/{user_id}_{username}"


def get_user_album_path(user_id: int, username: str, album_name: str) -> str:
    """
    Get storage path for user's album
    Format: users/{user_id}_{username}/albums/{album_name}/
    """
    return f"{get_user_storage_path(user_id, username)}/albums/{album_name}"


def get_user_video_path(user_id: int, username: str) -> str:
    """
    Get storage path for user's videos
    Format: users/{user_id}_{username}/videos/
    """
    return f"{get_user_storage_path(user_id, username)}/videos"


def get_user_temp_path(user_id: int, username: str) -> str:
    """
    Get temporary storage path for user
    Format: users/{user_id}_{username}/temp/
    """
    return f"{get_user_storage_path(user_id, username)}/temp"


def get_role_info(role: str) -> dict:
    """Get information about a role"""
    return ROLE_PERMISSIONS.get(role, {})


def list_all_permissions() -> dict:
    """List all available permissions for each role"""
    return ROLE_PERMISSIONS
