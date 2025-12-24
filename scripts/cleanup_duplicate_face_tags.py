#!/usr/bin/env python3
"""
Cleanup duplicate face tags by keeping only the highest confidence/most recent tag
for each unique face name per media.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

import logging
from utils.db_utils_flask_safe import get_flask_safe_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_duplicates(cursor):
    """Find all media with duplicate face names."""
    cursor.execute("""
        SELECT media_id, face_name, COUNT(*) as cnt
        FROM face_tags
        GROUP BY media_id, face_name
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """)
    return cursor.fetchall()


def get_tags_to_keep(cursor, media_id, face_name):
    """
    Get the best tag to keep for a face name (highest confidence, most recent).
    Returns the tag ID to keep.
    """
    cursor.execute("""
        SELECT id, confidence, created_at, auto_tagged
        FROM face_tags
        WHERE media_id = :media_id AND face_name = :face_name
        ORDER BY confidence DESC, created_at DESC
    """, {"media_id": media_id, "face_name": face_name})
    
    tags = cursor.fetchall()
    if not tags:
        return None
    
    # Return the first one (highest confidence, most recent)
    best_tag = tags[0]
    logger.debug(f"   Keeping tag {best_tag[0]} (confidence: {best_tag[1]:.2f}, created: {best_tag[2]})")
    
    # Log what we're deleting
    for tag in tags[1:]:
        logger.debug(f"   Deleting tag {tag[0]} (confidence: {tag[1]:.2f}, created: {tag[2]})")
    
    return best_tag[0]


def cleanup_duplicates(connection, cursor, dry_run=True):
    """
    Clean up duplicate face tags.
    
    Args:
        connection: Database connection
        cursor: Database cursor
        dry_run: If True, don't actually delete anything
    """
    logger.info("🔍 Finding duplicate face tags...")
    
    duplicates = find_duplicates(cursor)
    
    if not duplicates:
        logger.info("✅ No duplicate face tags found!")
        return
    
    logger.info(f"❌ Found {len(duplicates)} duplicate face name entries")
    
    total_tags_before = cursor.execute("SELECT COUNT(*) FROM face_tags").fetchone()[0]
    logger.info(f"📊 Total face tags before cleanup: {total_tags_before}")
    
    if dry_run:
        logger.info("\n🧪 DRY RUN MODE - No changes will be made\n")
    else:
        logger.info("\n⚠️  LIVE MODE - Changes will be committed!\n")
    
    tags_to_delete = []
    
    for media_id, face_name, count in duplicates:
        logger.info(f"Processing media {media_id}, face '{face_name}' ({count} duplicates)")
        
        # Get the tag ID to keep
        tag_to_keep = get_tags_to_keep(cursor, media_id, face_name)
        
        if tag_to_keep:
            # Find all other tags for this media/face combo
            cursor.execute("""
                SELECT id FROM face_tags
                WHERE media_id = :media_id 
                AND face_name = :face_name 
                AND id != :keep_id
            """, {
                "media_id": media_id,
                "face_name": face_name,
                "keep_id": tag_to_keep
            })
            
            duplicate_ids = [row[0] for row in cursor.fetchall()]
            tags_to_delete.extend(duplicate_ids)
            logger.info(f"   Will delete {len(duplicate_ids)} duplicate tags")
    
    logger.info(f"\n📊 Summary:")
    logger.info(f"   Tags before: {total_tags_before}")
    logger.info(f"   Tags to delete: {len(tags_to_delete)}")
    logger.info(f"   Tags after: {total_tags_before - len(tags_to_delete)}")
    
    if not dry_run and tags_to_delete:
        logger.info("\n🗑️  Deleting duplicate tags...")
        
        # Delete in batches
        batch_size = 100
        for i in range(0, len(tags_to_delete), batch_size):
            batch = tags_to_delete[i:i + batch_size]
            placeholders = ','.join([':id' + str(j) for j in range(len(batch))])
            params = {f'id{j}': tag_id for j, tag_id in enumerate(batch)}
            
            cursor.execute(f"DELETE FROM face_tags WHERE id IN ({placeholders})", params)
            logger.info(f"   Deleted batch {i//batch_size + 1}/{(len(tags_to_delete)-1)//batch_size + 1}")
        
        connection.commit()
        
        total_tags_after = cursor.execute("SELECT COUNT(*) FROM face_tags").fetchone()[0]
        logger.info(f"\n✅ Cleanup complete!")
        logger.info(f"   Tags deleted: {total_tags_before - total_tags_after}")
        logger.info(f"   Total tags now: {total_tags_after}")
    else:
        logger.info("\n⏭️  Skipping deletion (dry run mode)")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Cleanup duplicate face tags')
    parser.add_argument(
        '--live',
        action='store_true',
        help='Actually delete duplicates (default is dry run)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    try:
        with get_flask_safe_connection() as connection:
            cursor = connection.cursor()
            
            cleanup_duplicates(connection, cursor, dry_run=not args.live)
            
            cursor.close()
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
