#!/usr/bin/env python3
"""
Add FACE_TAGS column to ALBUM_MEDIA table for manual face tags
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
def add_face_tags_column():
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        logger.info("🔧 Adding FACE_TAGS column to ALBUM_MEDIA table...")
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_tab_columns 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND column_name = 'FACE_TAGS'
            """)
            exists = cursor.fetchone()[0] > 0
            if exists:
                logger.info("✅ FACE_TAGS column already exists")
                return True
            cursor.execute("""
                ALTER TABLE album_media 
                ADD (FACE_TAGS CLOB)
            """)
            logger.info("✅ Added FACE_TAGS column")
            conn.commit()
            logger.info("✅ Migration completed successfully!")
            return True
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False
if __name__ == "__main__":
    success = add_face_tags_column()
    sys.exit(0 if success else 1)
