#!/usr/bin/env python3
"""Face-based filtering utilities
Helper functions for filtering photos by user's face
"""

import logging
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


def get_user_face_embedding(user_id: int, connection) -> Optional[bytes]:
    """
    Get user's face embedding from user_face_profiles
    
    Args:
        user_id: User ID
        connection: Database connection
        
    Returns:
        Face embedding as bytes (Oracle VECTOR format), or None if not found
    """
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT face_embedding
            FROM user_face_profiles
            WHERE user_id = :user_id AND is_active = 1
        """, {"user_id": user_id})
        
        row = cursor.fetchone()
        if row and row[0]:
            # Read BLOB data
            face_embedding_bytes = row[0].read() if hasattr(row[0], 'read') else row[0]
            logger.debug(f"✅ Loaded face embedding for user {user_id}")
            return face_embedding_bytes
        else:
            logger.debug(f"ℹ️  No face profile found for user {user_id}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Failed to get user face embedding: {e}")
        return None


def should_filter_by_face(user_role: str, user_id: int, connection) -> Tuple[bool, Optional[bytes]]:
    """
    Determine if photos should be filtered by user's face
    
    Args:
        user_role: User's role (admin, editor, viewer)
        user_id: User ID
        connection: Database connection
        
    Returns:
        Tuple of (should_filter, face_embedding_bytes)
        - should_filter: True if filtering should be applied
        - face_embedding_bytes: User's face embedding if available
    """
    try:
        # Admins see all photos
        if user_role == 'admin':
            logger.debug("Admin user - no face filtering")
            return False, None
        
        # Editors see their uploaded photos (no face filtering)
        if user_role == 'editor':
            logger.debug("Editor user - no face filtering")
            return False, None
        
        # Viewers see only photos with their face
        if user_role == 'viewer':
            face_embedding = get_user_face_embedding(user_id, connection)
            if face_embedding:
                logger.debug(f"Viewer user {user_id} - filtering by face")
                return True, face_embedding
            else:
                logger.debug(f"Viewer user {user_id} - no face profile, no filtering")
                return False, None
        
        return False, None
        
    except Exception as e:
        logger.error(f"❌ Error in should_filter_by_face: {e}")
        return False, None


def get_photos_with_user_face(user_id: int, face_embedding_bytes: bytes, 
                              album_name: str = None, limit: int = 100) -> list:
    """
    Get all photos containing the user's face
    
    Args:
        user_id: User ID
        face_embedding_bytes: User's face embedding (Oracle VECTOR format)
        album_name: Optional album filter
        limit: Maximum number of results
        
    Returns:
        List of media IDs containing the user's face
    """
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Convert bytes to vector for Oracle
            import json
            import struct
            
            # Unpack bytes to floats
            num_floats = len(face_embedding_bytes) // 4
            embedding = list(struct.unpack(f'<{num_floats}f', face_embedding_bytes))
            vector_json = json.dumps(embedding)
            
            # Find photos with matching faces
            sql = """
            SELECT DISTINCT ft.media_id
            FROM face_tags ft
            WHERE VECTOR_DISTANCE(ft.face_embedding, TO_VECTOR(:face_vector), COSINE) < 0.6
            """
            
            params = {'face_vector': vector_json}
            
            if album_name:
                sql += """
                AND ft.media_id IN (
                    SELECT id FROM album_media WHERE album_name = :album_name
                )
                """
                params['album_name'] = album_name
            
            sql += " FETCH FIRST :limit ROWS ONLY"
            params['limit'] = limit
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            media_ids = [row[0] for row in rows]
            logger.info(f"✅ Found {len(media_ids)} photos with user {user_id}'s face")
            
            return media_ids
            
    except Exception as e:
        logger.error(f"❌ Error getting photos with user face: {e}")
        return []


if __name__ == "__main__":
    print("Face-based Filtering Utilities")
    print("=" * 60)
    print("Helper functions for filtering photos by user's face")
    print("- get_user_face_embedding(user_id, connection)")
    print("- should_filter_by_face(user_role, user_id, connection)")
    print("- get_photos_with_user_face(user_id, face_embedding_bytes)")
