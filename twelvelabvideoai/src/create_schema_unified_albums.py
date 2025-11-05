#!/usr/bin/env python3
"""Create unified album embeddings table with Oracle VECTOR support

This script creates a unified album_media table that stores both photos and videos
in the same album structure with Oracle VECTOR type for improved search performance.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.db_utils_vector import get_db_connection, validate_db_config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_unified_album_table():
    """Create unified album_media table with Oracle VECTOR type for both photos and videos"""
    
    # Validate configuration first
    try:
        validate_db_config()
    except Exception as e:
        logger.error(f"Database configuration invalid: {e}")
        return False
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Drop existing table if it exists
        try:
            cursor.execute("DROP TABLE album_media")
            logger.info("Dropped existing album_media table")
        except Exception:
            pass  # Table doesn't exist
        
        # Create unified table with Oracle VECTOR type
        # Using VECTOR(1024, FLOAT32) for TwelveLabs Marengo embeddings
        create_table_sql = """
        CREATE TABLE album_media (
            id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            album_name VARCHAR2(500) NOT NULL,
            file_name VARCHAR2(2000) NOT NULL,
            file_path VARCHAR2(4000) NOT NULL,
            file_type VARCHAR2(50) NOT NULL CHECK (file_type IN ('photo', 'video')),
            mime_type VARCHAR2(100),
            file_size NUMBER,
            
            -- Video-specific fields (NULL for photos)
            start_time NUMBER(10,2),
            end_time NUMBER(10,2),
            duration NUMBER(10,2),
            
            -- Photo-specific fields (NULL for videos) 
            width NUMBER,
            height NUMBER,
            
            -- Common embedding and metadata
            embedding_vector VECTOR(1024, FLOAT32),
            embedding_model VARCHAR2(100) DEFAULT 'Marengo-retrieval-2.7',
            
            -- Object storage details
            oci_namespace VARCHAR2(200),
            oci_bucket VARCHAR2(200),
            oci_object_path VARCHAR2(4000),
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Constraints
            CONSTRAINT uk_album_media UNIQUE (album_name, file_name, file_type),
            CONSTRAINT chk_video_fields CHECK (
                (file_type = 'video' AND start_time IS NOT NULL AND end_time IS NOT NULL) OR
                (file_type = 'photo' AND start_time IS NULL AND end_time IS NULL)
            )
        )
        """
        
        cursor.execute(create_table_sql)
        logger.info("✅ Created album_media table successfully")
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX idx_album_media_album ON album_media (album_name)",
            "CREATE INDEX idx_album_media_type ON album_media (file_type)",
            "CREATE INDEX idx_album_media_album_type ON album_media (album_name, file_type)",
            "CREATE INDEX idx_album_media_created ON album_media (created_at)"
        ]
        
        for idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
                logger.info(f"✅ Created index: {idx_sql.split()[2]}")
            except Exception as e:
                logger.warning(f"⚠️ Index creation warning: {e}")
        
        # Create vector index for similarity search
        try:
            vector_index_sql = """
            CREATE VECTOR INDEX idx_album_media_vector 
            ON album_media (embedding_vector) 
            ORGANIZATION NEIGHBOR PARTITIONS
            WITH TARGET ACCURACY 95
            """
            cursor.execute(vector_index_sql)
            logger.info("✅ Created vector index for similarity search")
        except Exception as e:
            logger.warning(f"⚠️ Vector index creation warning: {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("🎉 Unified album database schema created successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating unified album schema: {e}")
        return False

def migrate_existing_data():
    """Migrate existing photo and video data to unified schema"""
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        logger.info("📦 Starting data migration...")
        
        # Migrate photo embeddings
        try:
            migrate_photos_sql = """
            INSERT INTO album_media (
                album_name, file_name, file_path, file_type, mime_type,
                embedding_vector, embedding_model, created_at, updated_at
            )
            SELECT 
                album_name,
                REGEXP_SUBSTR(photo_file, '[^/]+$') as file_name,
                photo_file as file_path,
                'photo' as file_type,
                'image/jpeg' as mime_type,
                embedding_vector,
                'Marengo-retrieval-2.7' as embedding_model,
                created_at,
                updated_at
            FROM photo_embeddings
            """
            cursor.execute(migrate_photos_sql)
            photo_count = cursor.rowcount
            logger.info(f"📷 Migrated {photo_count} photos")
        except Exception as e:
            logger.warning(f"⚠️ Photo migration warning: {e}")
        
        # Migrate video embeddings
        try:
            migrate_videos_sql = """
            INSERT INTO album_media (
                album_name, file_name, file_path, file_type, mime_type,
                start_time, end_time, embedding_vector, embedding_model, created_at, updated_at
            )
            SELECT 
                'default' as album_name,
                REGEXP_SUBSTR(video_file, '[^/]+$') as file_name,
                video_file as file_path,
                'video' as file_type,
                'video/mp4' as mime_type,
                start_time,
                end_time,
                embedding_vector,
                'Marengo-retrieval-2.7' as embedding_model,
                created_at,
                updated_at
            FROM video_embeddings
            """
            cursor.execute(migrate_videos_sql)
            video_count = cursor.rowcount
            logger.info(f"🎬 Migrated {video_count} videos")
        except Exception as e:
            logger.warning(f"⚠️ Video migration warning: {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ Data migration completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during data migration: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Creating unified album schema...")
    
    if create_unified_album_table():
        print("✅ Schema creation successful!")
        
        # Ask user if they want to migrate existing data
        migrate = input("🔄 Migrate existing photo/video data? (y/n): ").lower().strip()
        if migrate in ['y', 'yes']:
            if migrate_existing_data():
                print("✅ Migration completed!")
            else:
                print("❌ Migration failed!")
    else:
        print("❌ Schema creation failed!")
        sys.exit(1)