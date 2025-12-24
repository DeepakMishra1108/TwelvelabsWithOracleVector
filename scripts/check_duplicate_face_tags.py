#!/usr/bin/env python3
"""
Check for duplicate face tags in the database
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_duplicates():
    """Check for duplicate face tags"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info("🔍 Checking for duplicate face tags...")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check for duplicate face tags (same media_id + face_name)
            cursor.execute("""
                SELECT media_id, face_name, COUNT(*) as cnt
                FROM face_tags
                GROUP BY media_id, face_name
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC
            """)
            
            duplicates = cursor.fetchall()
            
            if duplicates:
                logger.info(f"❌ Found {len(duplicates)} media items with duplicate face names:")
                for row in duplicates[:20]:
                    media_id, face_name, count = row
                    logger.info(f"   Media {media_id}: '{face_name}' appears {count} times")
                    
                    # Get details of duplicates
                    cursor.execute("""
                        SELECT id, created_at, auto_tagged, confidence, created_by
                        FROM face_tags
                        WHERE media_id = :media_id AND face_name = :face_name
                        ORDER BY created_at DESC
                    """, {"media_id": media_id, "face_name": face_name})
                    
                    details = cursor.fetchall()
                    for detail in details:
                        tag_id, created_at, auto_tagged, confidence, created_by = detail
                        tag_type = "Auto" if auto_tagged else "Manual"
                        logger.info(f"      - ID {tag_id}: {tag_type} (confidence: {confidence:.2f}, created: {created_at}, by: {created_by})")
            else:
                logger.info("✅ No duplicate face names found per media")
            
            # Check total face tags
            cursor.execute("SELECT COUNT(*) FROM face_tags")
            total = cursor.fetchone()[0]
            logger.info(f"\n📊 Total face tags in database: {total}")
            
            # Check face tags per media
            cursor.execute("""
                SELECT media_id, COUNT(*) as tag_count
                FROM face_tags
                GROUP BY media_id
                HAVING COUNT(*) > 5
                ORDER BY tag_count DESC
                FETCH FIRST 10 ROWS ONLY
            """)
            
            many_tags = cursor.fetchall()
            if many_tags:
                logger.info(f"\n📸 Media items with most tags:")
                for row in many_tags:
                    media_id, tag_count = row
                    
                    # Get media filename
                    cursor.execute("SELECT file_name FROM album_media WHERE id = :id", {"id": media_id})
                    filename_row = cursor.fetchone()
                    filename = filename_row[0] if filename_row else "Unknown"
                    
                    logger.info(f"   Media {media_id} ({filename}): {tag_count} tags")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Check failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = check_duplicates()
    sys.exit(0 if success else 1)
