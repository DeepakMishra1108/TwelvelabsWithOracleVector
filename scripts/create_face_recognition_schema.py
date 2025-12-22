#!/usr/bin/env python3
"""
Create Face Recognition Schema
Creates tables for face embeddings, face tags, and user face profiles
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'twelvelabvideoai' / 'src'))

import logging
from utils.db_utils_vector import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_face_recognition_schema():
    """Create all tables needed for face recognition"""
    
    try:
        logger.info("=" * 60)
        logger.info("Creating Face Recognition Schema")
        logger.info("=" * 60)
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # 1. Create face_tags table - stores manual face tags for photos
        logger.info("\n1. Creating face_tags table...")
        try:
            cursor.execute("""
                CREATE TABLE face_tags (
                    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    media_id NUMBER NOT NULL,
                    face_name VARCHAR2(100) NOT NULL,
                    face_embedding VECTOR(512, FLOAT32),
                    bounding_box VARCHAR2(200),
                    confidence NUMBER(5,2),
                    created_by NUMBER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_face_tags_media FOREIGN KEY (media_id) 
                        REFERENCES album_media(id) ON DELETE CASCADE,
                    CONSTRAINT fk_face_tags_user FOREIGN KEY (created_by) 
                        REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            logger.info("✅ Created face_tags table")
        except Exception as e:
            if 'ORA-00955' in str(e):
                logger.info("⚠️  face_tags table already exists, skipping")
            else:
                raise
        
        # 2. Create user_face_profiles table - stores user's face for login recognition
        logger.info("\n2. Creating user_face_profiles table...")
        try:
            cursor.execute("""
                CREATE TABLE user_face_profiles (
                    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    user_id NUMBER NOT NULL UNIQUE,
                    face_embedding VECTOR(512, FLOAT32) NOT NULL,
                    face_image_path VARCHAR2(500),
                    is_active NUMBER(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_user_face_profile FOREIGN KEY (user_id) 
                        REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            logger.info("✅ Created user_face_profiles table")
        except Exception as e:
            if 'ORA-00955' in str(e):
                logger.info("⚠️  user_face_profiles table already exists, skipping")
            else:
                raise
        
        # 3. Create face_recognition_cache table - cache for face recognition results
        logger.info("\n3. Creating face_recognition_cache table...")
        try:
            cursor.execute("""
                CREATE TABLE face_recognition_cache (
                    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    media_id NUMBER NOT NULL,
                    detected_faces CLOB,
                    processing_status VARCHAR2(20) DEFAULT 'pending',
                    processed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_face_cache_media FOREIGN KEY (media_id) 
                        REFERENCES album_media(id) ON DELETE CASCADE
                )
            """)
            logger.info("✅ Created face_recognition_cache table")
        except Exception as e:
            if 'ORA-00955' in str(e):
                logger.info("⚠️  face_recognition_cache table already exists, skipping")
            else:
                raise
        
        # 4. Create indexes for performance
        logger.info("\n4. Creating indexes...")
        
        # Index on media_id for fast lookup
        try:
            cursor.execute("""
                CREATE INDEX idx_face_tags_media ON face_tags(media_id)
            """)
            logger.info("✅ Created index on face_tags(media_id)")
        except Exception as e:
            if 'ORA-00955' in str(e):
                logger.info("⚠️  Index already exists, skipping")
        
        # Index on face_name for tag search
        try:
            cursor.execute("""
                CREATE INDEX idx_face_tags_name ON face_tags(face_name)
            """)
            logger.info("✅ Created index on face_tags(face_name)")
        except Exception as e:
            if 'ORA-00955' in str(e):
                logger.info("⚠️  Index already exists, skipping")
        
        # Index on user_id for face profile lookup
        try:
            cursor.execute("""
                CREATE INDEX idx_user_face_user ON user_face_profiles(user_id)
            """)
            logger.info("✅ Created index on user_face_profiles(user_id)")
        except Exception as e:
            if 'ORA-00955' in str(e):
                logger.info("⚠️  Index already exists, skipping")
        
        # Index on face_recognition_cache for fast media lookup
        try:
            cursor.execute("""
                CREATE INDEX idx_face_cache_media ON face_recognition_cache(media_id)
            """)
            logger.info("✅ Created index on face_recognition_cache(media_id)")
        except Exception as e:
            if 'ORA-00955' in str(e):
                logger.info("⚠️  Index already exists, skipping")
        
        # 5. Add column to album_media for face recognition status
        logger.info("\n5. Adding face_recognition_status column to album_media...")
        try:
            cursor.execute("""
                ALTER TABLE album_media 
                ADD (face_recognition_status VARCHAR2(20) DEFAULT 'pending')
            """)
            logger.info("✅ Added face_recognition_status column")
        except Exception as e:
            if 'ORA-01430' in str(e) or 'ORA-00957' in str(e):
                logger.info("⚠️  Column already exists, skipping")
            else:
                raise
        
        connection.commit()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Face Recognition Schema Created Successfully!")
        logger.info("=" * 60)
        logger.info("\nTables created:")
        logger.info("  1. face_tags - Manual face tags with embeddings")
        logger.info("  2. user_face_profiles - User face for login recognition")
        logger.info("  3. face_recognition_cache - Cache for face detection")
        logger.info("\nIndexes created:")
        logger.info("  - idx_face_tags_media")
        logger.info("  - idx_face_tags_name")
        logger.info("  - idx_user_face_user")
        logger.info("  - idx_face_cache_media")
        logger.info("\nColumn added:")
        logger.info("  - album_media.face_recognition_status")
        
        cursor.close()
        connection.close()
        
        return True
            
    except Exception as e:
        logger.error(f"❌ Error creating schema: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = create_face_recognition_schema()
    sys.exit(0 if success else 1)
