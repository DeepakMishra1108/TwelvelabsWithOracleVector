#!/usr/bin/env python3
"""
Create JSON search indexes on AI_TAGS and rich_metadata for optimized performance
Oracle JSON search indexes dramatically improve JSON_TEXTCONTAINS query performance
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_json_search_indexes():
    """Create JSON search indexes for optimized JSON queries"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info("🚀 Creating JSON search indexes for performance optimization...")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if AI_TAGS index exists
            logger.info("📋 Checking existing indexes...")
            cursor.execute("""
                SELECT index_name 
                FROM user_indexes 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND index_name = 'AI_TAGS_SEARCH_IDX'
            """)
            
            ai_tags_exists = cursor.fetchone() is not None
            
            # Check if rich_metadata index exists
            cursor.execute("""
                SELECT index_name 
                FROM user_indexes 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND index_name = 'RICH_METADATA_SEARCH_IDX'
            """)
            
            rich_metadata_exists = cursor.fetchone() is not None
            
            # Create AI_TAGS search index
            if not ai_tags_exists:
                logger.info("📝 Creating JSON search index on AI_TAGS...")
                try:
                    cursor.execute("""
                        CREATE SEARCH INDEX ai_tags_search_idx 
                        ON album_media (AI_TAGS) 
                        FOR JSON
                    """)
                    logger.info("✅ Created ai_tags_search_idx")
                except Exception as e:
                    if 'ORA-29879' in str(e):  # Index already exists
                        logger.info("ℹ️  ai_tags_search_idx already exists")
                    else:
                        raise
            else:
                logger.info("✅ ai_tags_search_idx already exists")
            
            # Create rich_metadata search index
            if not rich_metadata_exists:
                logger.info("📝 Creating JSON search index on rich_metadata...")
                try:
                    cursor.execute("""
                        CREATE SEARCH INDEX rich_metadata_search_idx 
                        ON album_media (rich_metadata) 
                        FOR JSON
                    """)
                    logger.info("✅ Created rich_metadata_search_idx")
                except Exception as e:
                    if 'ORA-29879' in str(e):  # Index already exists
                        logger.info("ℹ️  rich_metadata_search_idx already exists")
                    else:
                        raise
            else:
                logger.info("✅ rich_metadata_search_idx already exists")
            
            conn.commit()
            
            # Verify indexes
            logger.info("🔍 Verifying indexes...")
            cursor.execute("""
                SELECT index_name, index_type, status
                FROM user_indexes 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND index_name IN ('AI_TAGS_SEARCH_IDX', 'RICH_METADATA_SEARCH_IDX')
                ORDER BY index_name
            """)
            
            indexes = cursor.fetchall()
            if indexes:
                logger.info(f"✅ Found {len(indexes)} JSON search index(es):")
                for idx in indexes:
                    logger.info(f"   - {idx[0]}: {idx[1]} ({idx[2]})")
            
            logger.info("✅ JSON search index optimization completed!")
            logger.info("")
            logger.info("📊 Performance Benefits:")
            logger.info("   • 10-100x faster JSON_TEXTCONTAINS queries")
            logger.info("   • Efficient full-text search in JSON documents")
            logger.info("   • Optimized metadata and tag searches")
            logger.info("   • Lower CPU usage for JSON operations")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Index creation failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = create_json_search_indexes()
    sys.exit(0 if success else 1)
