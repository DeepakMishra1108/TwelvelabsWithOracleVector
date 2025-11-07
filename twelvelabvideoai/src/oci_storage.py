"""
Multi-Tenant OCI Object Storage Module

This module provides user-specific storage paths and utilities for Oracle Cloud Infrastructure (OCI) Object Storage.
Implements a structured folder hierarchy to isolate user data and organize content by type.

Folder Structure:
/users/
  /{user_id}/
    /uploads/
      /photos/          - Original uploaded photos
      /videos/          - Original uploaded videos
      /chunks/          - Video chunks
    /generated/
      /montages/        - Generated video montages
      /slideshows/      - Generated photo slideshows
      /clips/           - Extracted video clips
      /compressed/      - Compressed videos
    /thumbnails/
      /videos/          - Video thumbnails
      /photos/          - Photo thumbnails
    /embeddings/        - Cached embeddings
    /temp/              - Temporary processing files

Usage:
    from oci_storage import get_user_upload_path, get_user_generated_path, upload_to_user_storage
    
    photo_path = get_user_upload_path(user_id, 'photo', 'vacation.jpg')
    # Returns: users/123/uploads/photos/vacation.jpg
    
    montage_path = get_user_generated_path(user_id, 'montage', 'summer_2024.mp4')
    # Returns: users/123/generated/montages/summer_2024.mp4
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple
import oci

logger = logging.getLogger(__name__)


# OCI Storage configuration
# These should be set from environment variables
OCI_NAMESPACE = os.getenv('OCI_NAMESPACE')
OCI_BUCKET_NAME = os.getenv('OCI_BUCKET_NAME', 'video-ai-storage')
OCI_CONFIG_FILE = os.getenv('OCI_CONFIG_FILE', '~/.oci/config')
OCI_PROFILE = os.getenv('OCI_PROFILE', 'DEFAULT')


def get_oci_client():
    """
    Get OCI Object Storage client.
    
    Returns:
        oci.object_storage.ObjectStorageClient
    """
    try:
        config = oci.config.from_file(
            file_location=os.path.expanduser(OCI_CONFIG_FILE),
            profile_name=OCI_PROFILE
        )
        return oci.object_storage.ObjectStorageClient(config)
    except Exception as e:
        logger.error(f"❌ Failed to create OCI client: {e}")
        raise


def get_user_base_path(user_id: int) -> str:
    """
    Get the base storage path for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        Base path string (e.g., "users/123")
    """
    return f"users/{user_id}"


def get_user_upload_path(user_id: int, content_type: str, filename: str) -> str:
    """
    Get the full OCI path for an uploaded file.
    
    Args:
        user_id: User ID
        content_type: One of: photo, video, chunk
        filename: Name of the file
        
    Returns:
        Full path string (e.g., "users/123/uploads/photos/vacation.jpg")
    """
    base = get_user_base_path(user_id)
    
    type_folders = {
        'photo': 'photos',
        'video': 'videos',
        'chunk': 'chunks'
    }
    
    folder = type_folders.get(content_type, 'other')
    return f"{base}/uploads/{folder}/{filename}"


def get_user_generated_path(user_id: int, content_type: str, filename: str) -> str:
    """
    Get the full OCI path for a generated file.
    
    Args:
        user_id: User ID
        content_type: One of: montage, slideshow, clip, compressed
        filename: Name of the file
        
    Returns:
        Full path string (e.g., "users/123/generated/montages/summer.mp4")
    """
    base = get_user_base_path(user_id)
    
    type_folders = {
        'montage': 'montages',
        'slideshow': 'slideshows',
        'clip': 'clips',
        'compressed': 'compressed'
    }
    
    folder = type_folders.get(content_type, 'other')
    return f"{base}/generated/{folder}/{filename}"


def get_user_thumbnail_path(user_id: int, content_type: str, filename: str) -> str:
    """
    Get the full OCI path for a thumbnail.
    
    Args:
        user_id: User ID
        content_type: One of: video, photo
        filename: Name of the thumbnail file
        
    Returns:
        Full path string (e.g., "users/123/thumbnails/videos/video_thumb.jpg")
    """
    base = get_user_base_path(user_id)
    
    type_folders = {
        'video': 'videos',
        'photo': 'photos'
    }
    
    folder = type_folders.get(content_type, 'other')
    return f"{base}/thumbnails/{folder}/{filename}"


def get_user_embedding_path(user_id: int, filename: str) -> str:
    """
    Get the full OCI path for an embedding file.
    
    Args:
        user_id: User ID
        filename: Name of the embedding file
        
    Returns:
        Full path string (e.g., "users/123/embeddings/video_123.npy")
    """
    base = get_user_base_path(user_id)
    return f"{base}/embeddings/{filename}"


def get_user_temp_path(user_id: int, filename: str) -> str:
    """
    Get the full OCI path for a temporary file.
    
    Args:
        user_id: User ID
        filename: Name of the temp file
        
    Returns:
        Full path string (e.g., "users/123/temp/processing_xyz.mp4")
    """
    base = get_user_base_path(user_id)
    return f"{base}/temp/{filename}"


def upload_to_oci(local_file_path: str, oci_object_name: str, 
                  namespace: Optional[str] = None,
                  bucket_name: Optional[str] = None) -> Tuple[bool, str]:
    """
    Upload a file to OCI Object Storage.
    
    Args:
        local_file_path: Path to local file
        oci_object_name: Object name in OCI (full path)
        namespace: OCI namespace (defaults to env var)
        bucket_name: Bucket name (defaults to env var)
        
    Returns:
        Tuple of (success: bool, message/url: str)
    """
    namespace = namespace or OCI_NAMESPACE
    bucket_name = bucket_name or OCI_BUCKET_NAME
    
    if not namespace:
        return (False, "OCI_NAMESPACE not configured")
    
    try:
        client = get_oci_client()
        
        with open(local_file_path, 'rb') as file_data:
            client.put_object(
                namespace_name=namespace,
                bucket_name=bucket_name,
                object_name=oci_object_name,
                put_object_body=file_data
            )
        
        # Generate pre-authenticated request URL (optional)
        # This would require additional OCI setup for public access
        url = f"https://objectstorage.{os.getenv('OCI_REGION', 'us-ashburn-1')}.oraclecloud.com/n/{namespace}/b/{bucket_name}/o/{oci_object_name}"
        
        logger.info(f"✅ Uploaded {local_file_path} to OCI: {oci_object_name}")
        return (True, url)
        
    except Exception as e:
        logger.error(f"❌ Failed to upload to OCI: {e}")
        return (False, str(e))


def download_from_oci(oci_object_name: str, local_file_path: str,
                      namespace: Optional[str] = None,
                      bucket_name: Optional[str] = None) -> Tuple[bool, str]:
    """
    Download a file from OCI Object Storage.
    
    Args:
        oci_object_name: Object name in OCI (full path)
        local_file_path: Where to save the file locally
        namespace: OCI namespace (defaults to env var)
        bucket_name: Bucket name (defaults to env var)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    namespace = namespace or OCI_NAMESPACE
    bucket_name = bucket_name or OCI_BUCKET_NAME
    
    if not namespace:
        return (False, "OCI_NAMESPACE not configured")
    
    try:
        client = get_oci_client()
        
        obj = client.get_object(
            namespace_name=namespace,
            bucket_name=bucket_name,
            object_name=oci_object_name
        )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        
        with open(local_file_path, 'wb') as file_data:
            for chunk in obj.data.raw.stream(1024 * 1024, decode_content=False):
                file_data.write(chunk)
        
        logger.info(f"✅ Downloaded {oci_object_name} from OCI to {local_file_path}")
        return (True, f"Downloaded to {local_file_path}")
        
    except Exception as e:
        logger.error(f"❌ Failed to download from OCI: {e}")
        return (False, str(e))


def delete_from_oci(oci_object_name: str,
                    namespace: Optional[str] = None,
                    bucket_name: Optional[str] = None) -> Tuple[bool, str]:
    """
    Delete a file from OCI Object Storage.
    
    Args:
        oci_object_name: Object name in OCI (full path)
        namespace: OCI namespace (defaults to env var)
        bucket_name: Bucket name (defaults to env var)
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    namespace = namespace or OCI_NAMESPACE
    bucket_name = bucket_name or OCI_BUCKET_NAME
    
    if not namespace:
        return (False, "OCI_NAMESPACE not configured")
    
    try:
        client = get_oci_client()
        
        client.delete_object(
            namespace_name=namespace,
            bucket_name=bucket_name,
            object_name=oci_object_name
        )
        
        logger.info(f"✅ Deleted {oci_object_name} from OCI")
        return (True, f"Deleted {oci_object_name}")
        
    except Exception as e:
        logger.error(f"❌ Failed to delete from OCI: {e}")
        return (False, str(e))


def list_user_objects(user_id: int, 
                      prefix: Optional[str] = None,
                      namespace: Optional[str] = None,
                      bucket_name: Optional[str] = None) -> Tuple[bool, list]:
    """
    List all objects for a specific user.
    
    Args:
        user_id: User ID
        prefix: Optional additional prefix (e.g., "uploads/photos")
        namespace: OCI namespace (defaults to env var)
        bucket_name: Bucket name (defaults to env var)
        
    Returns:
        Tuple of (success: bool, list of object names or error message)
    """
    namespace = namespace or OCI_NAMESPACE
    bucket_name = bucket_name or OCI_BUCKET_NAME
    
    if not namespace:
        return (False, "OCI_NAMESPACE not configured")
    
    try:
        client = get_oci_client()
        
        user_prefix = get_user_base_path(user_id)
        if prefix:
            user_prefix = f"{user_prefix}/{prefix}"
        
        objects = []
        next_start = None
        
        while True:
            response = client.list_objects(
                namespace_name=namespace,
                bucket_name=bucket_name,
                prefix=user_prefix,
                start=next_start
            )
            
            objects.extend([obj.name for obj in response.data.objects])
            
            next_start = response.data.next_start_with
            if not next_start:
                break
        
        logger.info(f"✅ Listed {len(objects)} objects for user {user_id}")
        return (True, objects)
        
    except Exception as e:
        logger.error(f"❌ Failed to list objects: {e}")
        return (False, str(e))


def get_user_storage_usage(user_id: int,
                           namespace: Optional[str] = None,
                           bucket_name: Optional[str] = None) -> Tuple[bool, dict]:
    """
    Calculate total storage usage for a user.
    
    Args:
        user_id: User ID
        namespace: OCI namespace (defaults to env var)
        bucket_name: Bucket name (defaults to env var)
        
    Returns:
        Tuple of (success: bool, dict with usage info or error message)
    """
    namespace = namespace or OCI_NAMESPACE
    bucket_name = bucket_name or OCI_BUCKET_NAME
    
    if not namespace:
        return (False, {"error": "OCI_NAMESPACE not configured"})
    
    try:
        client = get_oci_client()
        
        user_prefix = get_user_base_path(user_id)
        
        total_size = 0
        object_count = 0
        next_start = None
        
        while True:
            response = client.list_objects(
                namespace_name=namespace,
                bucket_name=bucket_name,
                prefix=user_prefix,
                start=next_start,
                fields="size"
            )
            
            for obj in response.data.objects:
                total_size += obj.size
                object_count += 1
            
            next_start = response.data.next_start_with
            if not next_start:
                break
        
        # Convert to GB
        total_size_gb = total_size / (1024 ** 3)
        
        usage = {
            'user_id': user_id,
            'total_size_bytes': total_size,
            'total_size_gb': round(total_size_gb, 3),
            'object_count': object_count
        }
        
        logger.info(f"✅ User {user_id} storage usage: {total_size_gb:.3f} GB ({object_count} objects)")
        return (True, usage)
        
    except Exception as e:
        logger.error(f"❌ Failed to calculate storage usage: {e}")
        return (False, {'error': str(e)})


def delete_user_storage(user_id: int,
                        namespace: Optional[str] = None,
                        bucket_name: Optional[str] = None,
                        dry_run: bool = True) -> Tuple[bool, dict]:
    """
    Delete all storage for a user (CASCADE DELETE equivalent).
    
    Args:
        user_id: User ID
        namespace: OCI namespace (defaults to env var)
        bucket_name: Bucket name (defaults to env var)
        dry_run: If True, only list what would be deleted
        
    Returns:
        Tuple of (success: bool, dict with deletion info or error message)
    """
    success, objects = list_user_objects(user_id, namespace=namespace, bucket_name=bucket_name)
    
    if not success:
        return (False, {'error': objects})
    
    if dry_run:
        return (True, {
            'dry_run': True,
            'objects_to_delete': len(objects),
            'objects': objects[:10]  # Show first 10
        })
    
    # Delete all objects
    deleted_count = 0
    errors = []
    
    for obj_name in objects:
        success, msg = delete_from_oci(obj_name, namespace=namespace, bucket_name=bucket_name)
        if success:
            deleted_count += 1
        else:
            errors.append({'object': obj_name, 'error': msg})
    
    result = {
        'user_id': user_id,
        'total_objects': len(objects),
        'deleted': deleted_count,
        'errors': len(errors)
    }
    
    if errors:
        result['error_details'] = errors[:5]  # Show first 5 errors
    
    logger.info(f"✅ Deleted {deleted_count}/{len(objects)} objects for user {user_id}")
    return (True, result)


# Utility functions for common operations

def upload_user_photo(user_id: int, local_file_path: str, filename: str) -> Tuple[bool, str]:
    """Upload a user photo to OCI."""
    oci_path = get_user_upload_path(user_id, 'photo', filename)
    return upload_to_oci(local_file_path, oci_path)


def upload_user_video(user_id: int, local_file_path: str, filename: str) -> Tuple[bool, str]:
    """Upload a user video to OCI."""
    oci_path = get_user_upload_path(user_id, 'video', filename)
    return upload_to_oci(local_file_path, oci_path)


def upload_generated_montage(user_id: int, local_file_path: str, filename: str) -> Tuple[bool, str]:
    """Upload a generated montage to OCI."""
    oci_path = get_user_generated_path(user_id, 'montage', filename)
    return upload_to_oci(local_file_path, oci_path)


def upload_generated_slideshow(user_id: int, local_file_path: str, filename: str) -> Tuple[bool, str]:
    """Upload a generated slideshow to OCI."""
    oci_path = get_user_generated_path(user_id, 'slideshow', filename)
    return upload_to_oci(local_file_path, oci_path)


# Example usage
if __name__ == "__main__":
    # Test path generation
    user_id = 123
    
    print("Path Examples:")
    print(f"Photo upload: {get_user_upload_path(user_id, 'photo', 'vacation.jpg')}")
    print(f"Video upload: {get_user_upload_path(user_id, 'video', 'family.mp4')}")
    print(f"Montage: {get_user_generated_path(user_id, 'montage', 'summer_2024.mp4')}")
    print(f"Slideshow: {get_user_generated_path(user_id, 'slideshow', 'wedding.mp4')}")
    print(f"Thumbnail: {get_user_thumbnail_path(user_id, 'video', 'thumb_001.jpg')}")
    print(f"Embedding: {get_user_embedding_path(user_id, 'embedding_456.npy')}")
    print(f"Temp file: {get_user_temp_path(user_id, 'processing_xyz.tmp')}")
