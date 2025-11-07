#!/usr/bin/env python3
"""
Add VIDEO_ID column to ALBUM_MEDIA table for TwelveLabs integration
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_video_id_column():
    """Add VIDEO_ID column to ALBUM_MEDIA table"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info("🔧 Adding VIDEO_ID column to ALBUM_MEDIA table...")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if column already exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_tab_columns 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND column_name = 'VIDEO_ID'
            """)
            
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                logger.info("✅ VIDEO_ID column already exists")
                return True
            
            # Add the column
            cursor.execute("""
                ALTER TABLE album_media 
                ADD (
                    video_id VARCHAR2(100),
                    indexing_status VARCHAR2(50) DEFAULT 'pending'
                )
            """)
            
            logger.info("✅ Added VIDEO_ID and INDEXING_STATUS columns")
            
            # Create index for performance
            try:
                cursor.execute("""
                    CREATE INDEX idx_album_media_video_id 
                    ON album_media (video_id)
                """)
                logger.info("✅ Created index on VIDEO_ID column")
            except Exception as e:
                logger.warning(f"Index creation failed (may already exist): {e}")
            
            conn.commit()
            logger.info("✅ Migration completed successfully!")
            
            # Show current structure
            cursor.execute("""
                SELECT column_name, data_type, nullable 
                FROM user_tab_columns 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND column_name IN ('VIDEO_ID', 'INDEXING_STATUS')
                ORDER BY column_id
            """)
            
            logger.info("\n📋 New columns:")
            for row in cursor:
                logger.info(f"  {row[0]}: {row[1]} (Nullable: {row[2]})")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = add_video_id_column()
    sys.exit(0 if success else 1)
