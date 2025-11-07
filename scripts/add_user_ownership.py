#!/usr/bin/env python3
"""
Add user ownership columns to tables for multi-tenant security
This enables each user to have their own albums and media
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

from utils.db_utils_flask_safe import get_flask_safe_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_user_ownership():
    """Add USER_ID column to ALBUM_MEDIA and VIDEO_SEGMENTS tables"""
    
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Add USER_ID to ALBUM_MEDIA table
            logger.info("🔧 Adding USER_ID column to ALBUM_MEDIA table...")
            
            # Check if column already exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_tab_cols 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND column_name = 'USER_ID'
            """)
            
            if cursor.fetchone()[0] > 0:
                logger.info("✅ USER_ID column already exists in ALBUM_MEDIA")
            else:
                # Add USER_ID column (nullable initially for existing data)
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD (user_id NUMBER)
                """)
                logger.info("✅ Added USER_ID column to ALBUM_MEDIA")
                
                # Add foreign key constraint
                try:
                    cursor.execute("""
                        ALTER TABLE album_media 
                        ADD CONSTRAINT fk_album_media_user 
                        FOREIGN KEY (user_id) REFERENCES users(id)
                        ON DELETE CASCADE
                    """)
                    logger.info("✅ Added foreign key constraint to ALBUM_MEDIA")
                except Exception as e:
                    if "ORA-02275" in str(e) or "already exists" in str(e):
                        logger.info("✅ Foreign key constraint already exists")
                    else:
                        raise
                
                # Create index for faster lookups
                try:
                    cursor.execute("""
                        CREATE INDEX idx_album_media_user_id 
                        ON album_media (user_id)
                    """)
                    logger.info("✅ Created index on ALBUM_MEDIA.USER_ID")
                except Exception as e:
                    if "ORA-01408" in str(e) or "ORA-00955" in str(e):
                        logger.info("✅ Index already exists")
                    else:
                        raise
            
            # 2. Add USER_ID to VIDEO_SEGMENTS table (if exists)
            logger.info("🔧 Adding USER_ID column to VIDEO_SEGMENTS table...")
            
            # Check if table exists first
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_tables 
                WHERE table_name = 'VIDEO_SEGMENTS'
            """)
            
            if cursor.fetchone()[0] == 0:
                logger.info("ℹ️  VIDEO_SEGMENTS table doesn't exist yet - skipping")
            else:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM user_tab_cols 
                    WHERE table_name = 'VIDEO_SEGMENTS' 
                    AND column_name = 'USER_ID'
                """)
                
                if cursor.fetchone()[0] > 0:
                    logger.info("✅ USER_ID column already exists in VIDEO_SEGMENTS")
                else:
                    # Add USER_ID column
                    cursor.execute("""
                        ALTER TABLE video_segments 
                        ADD (user_id NUMBER)
                    """)
                    logger.info("✅ Added USER_ID column to VIDEO_SEGMENTS")
                    
                    # Add foreign key constraint
                    try:
                        cursor.execute("""
                            ALTER TABLE video_segments 
                            ADD CONSTRAINT fk_video_segments_user 
                            FOREIGN KEY (user_id) REFERENCES users(id)
                            ON DELETE CASCADE
                        """)
                        logger.info("✅ Added foreign key constraint to VIDEO_SEGMENTS")
                    except Exception as e:
                        if "ORA-02275" in str(e) or "already exists" in str(e):
                            logger.info("✅ Foreign key constraint already exists")
                        else:
                            raise
                    
                    # Create index
                    try:
                        cursor.execute("""
                            CREATE INDEX idx_video_segments_user_id 
                            ON video_segments (user_id)
                        """)
                        logger.info("✅ Created index on VIDEO_SEGMENTS.USER_ID")
                    except Exception as e:
                        if "ORA-01408" in str(e) or "ORA-00955" in str(e):
                            logger.info("✅ Index already exists")
                        else:
                            raise
            
            # 3. Add USER_ID to QUERY_EMBEDDING_CACHE table for per-user caching
            logger.info("🔧 Adding USER_ID column to QUERY_EMBEDDING_CACHE table...")
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_tab_cols 
                WHERE table_name = 'QUERY_EMBEDDING_CACHE' 
                AND column_name = 'USER_ID'
            """)
            
            if cursor.fetchone()[0] > 0:
                logger.info("✅ USER_ID column already exists in QUERY_EMBEDDING_CACHE")
            else:
                # Add USER_ID column (nullable for shared queries)
                cursor.execute("""
                    ALTER TABLE query_embedding_cache 
                    ADD (user_id NUMBER)
                """)
                logger.info("✅ Added USER_ID column to QUERY_EMBEDDING_CACHE")
                
                # Create composite index for user-specific cache lookups
                try:
                    cursor.execute("""
                        CREATE INDEX idx_qcache_user_text 
                        ON query_embedding_cache (user_id, query_text)
                    """)
                    logger.info("✅ Created composite index on QUERY_EMBEDDING_CACHE")
                except Exception as e:
                    if "ORA-01408" in str(e) or "ORA-00955" in str(e):
                        logger.info("✅ Index already exists")
                    else:
                        raise
            
            conn.commit()
            
            logger.info("\n" + "="*70)
            logger.info("✅ USER OWNERSHIP MIGRATION COMPLETED SUCCESSFULLY!")
            logger.info("="*70)
            logger.info("\n📋 Summary:")
            logger.info("   ✓ ALBUM_MEDIA.USER_ID column added")
            
            # Check if VIDEO_SEGMENTS was processed
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_tables 
                WHERE table_name = 'VIDEO_SEGMENTS'
            """)
            if cursor.fetchone()[0] > 0:
                logger.info("   ✓ VIDEO_SEGMENTS.USER_ID column added")
            else:
                logger.info("   ⊘ VIDEO_SEGMENTS table not found (will be added when table is created)")
            
            logger.info("   ✓ QUERY_EMBEDDING_CACHE.USER_ID column added")
            logger.info("   ✓ Foreign key constraints added")
            logger.info("   ✓ Indexes created for performance")
            logger.info("\n⚠️  NEXT STEPS:")
            logger.info("   1. Update existing data to assign user_id")
            logger.info("   2. Make user_id NOT NULL after data migration")
            logger.info("   3. Update application code to filter by user_id")
            logger.info("\n💡 SECURITY BENEFITS:")
            logger.info("   ✓ Users can only see their own albums/media")
            logger.info("   ✓ Automatic cleanup on user deletion (CASCADE)")
            logger.info("   ✓ Per-user cache isolation")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise

if __name__ == '__main__':
    add_user_ownership()
