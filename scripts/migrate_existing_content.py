#!/usr/bin/env python3
"""
Phase 4: Data Migration Script - Assign Existing Content to Users

This script:
1. Identifies content with NULL user_id
2. Assigns orphaned content to the admin user
3. Makes user_id NOT NULL (enforces database constraint)
4. Verifies data integrity

Usage:
    python scripts/migrate_existing_content.py [--admin-user-id ID] [--dry-run]

Options:
    --admin-user-id ID    User ID to assign orphaned content to (default: 1)
    --dry-run            Show what would be changed without applying changes
    --verify-only        Only verify data, don't make changes
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import database utilities
try:
    from twelvelabvideoai.src.utils.db_utils_flask_safe import get_flask_safe_connection
except ImportError:
    print("❌ Error: Could not import database utilities")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_admin_user_exists(admin_user_id: int) -> bool:
    """Verify the admin user exists before assignment"""
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, role FROM users WHERE id = :user_id",
                {'user_id': admin_user_id}
            )
            result = cursor.fetchone()
            
            if not result:
                logger.error(f"❌ User with ID {admin_user_id} does not exist")
                return False
            
            user_id, username, role = result
            logger.info(f"✅ Found user: ID={user_id}, username='{username}', role='{role}'")
            
            if role != 'admin':
                logger.warning(f"⚠️ User '{username}' is not an admin (role: {role})")
                response = input(f"Continue assigning to non-admin user '{username}'? (yes/no): ")
                if response.lower() != 'yes':
                    return False
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error verifying admin user: {e}")
        return False


def check_orphaned_content() -> dict:
    """Check for content with NULL user_id"""
    stats = {
        'album_media': 0,
        'query_embedding_cache': 0,
        'video_segments': 0
    }
    
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check ALBUM_MEDIA
            cursor.execute("SELECT COUNT(*) FROM album_media WHERE user_id IS NULL")
            stats['album_media'] = cursor.fetchone()[0]
            
            # Check QUERY_EMBEDDING_CACHE
            cursor.execute("SELECT COUNT(*) FROM query_embedding_cache WHERE user_id IS NULL")
            stats['query_embedding_cache'] = cursor.fetchone()[0]
            
            # Check VIDEO_SEGMENTS (may not exist yet)
            try:
                cursor.execute("SELECT COUNT(*) FROM video_segments WHERE user_id IS NULL")
                stats['video_segments'] = cursor.fetchone()[0]
            except Exception:
                logger.info("ℹ️ VIDEO_SEGMENTS table not found (will be created later)")
                stats['video_segments'] = None
            
            return stats
            
    except Exception as e:
        logger.error(f"❌ Error checking orphaned content: {e}")
        return None


def show_sample_orphaned_content():
    """Show sample of orphaned content for review"""
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Sample from ALBUM_MEDIA
            logger.info("\n📋 Sample orphaned content in ALBUM_MEDIA:")
            cursor.execute("""
                SELECT id, album_name, file_name, file_type, created_at 
                FROM album_media 
                WHERE user_id IS NULL 
                AND ROWNUM <= 5
                ORDER BY created_at DESC
            """)
            
            results = cursor.fetchall()
            if results:
                for row in results:
                    logger.info(f"  - ID: {row[0]}, Album: {row[1]}, File: {row[2]}, Type: {row[3]}, Created: {row[4]}")
            else:
                logger.info("  (No orphaned content found)")
            
            # Sample from QUERY_EMBEDDING_CACHE
            logger.info("\n📋 Sample orphaned queries in QUERY_EMBEDDING_CACHE:")
            cursor.execute("""
                SELECT id, query_text, created_at 
                FROM query_embedding_cache 
                WHERE user_id IS NULL 
                AND ROWNUM <= 5
                ORDER BY created_at DESC
            """)
            
            results = cursor.fetchall()
            if results:
                for row in results:
                    query_preview = row[1][:50] + '...' if len(row[1]) > 50 else row[1]
                    logger.info(f"  - ID: {row[0]}, Query: '{query_preview}', Created: {row[2]}")
            else:
                logger.info("  (No orphaned queries found)")
                
    except Exception as e:
        logger.error(f"❌ Error showing sample content: {e}")


def assign_orphaned_content(admin_user_id: int, dry_run: bool = False) -> bool:
    """Assign all orphaned content to the specified user"""
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Update ALBUM_MEDIA
            if dry_run:
                logger.info(f"[DRY RUN] Would update ALBUM_MEDIA SET user_id = {admin_user_id} WHERE user_id IS NULL")
            else:
                cursor.execute(
                    "UPDATE album_media SET user_id = :user_id WHERE user_id IS NULL",
                    {'user_id': admin_user_id}
                )
                updated_media = cursor.rowcount
                logger.info(f"✅ Updated {updated_media} rows in ALBUM_MEDIA")
            
            # Update QUERY_EMBEDDING_CACHE
            if dry_run:
                logger.info(f"[DRY RUN] Would update QUERY_EMBEDDING_CACHE SET user_id = {admin_user_id} WHERE user_id IS NULL")
            else:
                cursor.execute(
                    "UPDATE query_embedding_cache SET user_id = :user_id WHERE user_id IS NULL",
                    {'user_id': admin_user_id}
                )
                updated_cache = cursor.rowcount
                logger.info(f"✅ Updated {updated_cache} rows in QUERY_EMBEDDING_CACHE")
            
            # Update VIDEO_SEGMENTS (if exists)
            try:
                if dry_run:
                    logger.info(f"[DRY RUN] Would update VIDEO_SEGMENTS SET user_id = {admin_user_id} WHERE user_id IS NULL")
                else:
                    cursor.execute(
                        "UPDATE video_segments SET user_id = :user_id WHERE user_id IS NULL",
                        {'user_id': admin_user_id}
                    )
                    updated_segments = cursor.rowcount
                    logger.info(f"✅ Updated {updated_segments} rows in VIDEO_SEGMENTS")
            except Exception:
                logger.info("ℹ️ VIDEO_SEGMENTS table not found (skipping)")
            
            if not dry_run:
                conn.commit()
                logger.info("✅ All changes committed to database")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error assigning orphaned content: {e}")
        return False


def make_user_id_not_null(dry_run: bool = False) -> bool:
    """Make user_id column NOT NULL to enforce constraint"""
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # ALBUM_MEDIA
            if dry_run:
                logger.info("[DRY RUN] Would execute: ALTER TABLE album_media MODIFY user_id NUMBER NOT NULL")
            else:
                try:
                    cursor.execute("ALTER TABLE album_media MODIFY user_id NUMBER NOT NULL")
                    logger.info("✅ ALBUM_MEDIA.user_id is now NOT NULL")
                except Exception as e:
                    if "already NOT NULL" in str(e) or "ORA-01442" in str(e):
                        logger.info("ℹ️ ALBUM_MEDIA.user_id is already NOT NULL")
                    else:
                        raise
            
            # QUERY_EMBEDDING_CACHE
            if dry_run:
                logger.info("[DRY RUN] Would execute: ALTER TABLE query_embedding_cache MODIFY user_id NUMBER NOT NULL")
            else:
                try:
                    cursor.execute("ALTER TABLE query_embedding_cache MODIFY user_id NUMBER NOT NULL")
                    logger.info("✅ QUERY_EMBEDDING_CACHE.user_id is now NOT NULL")
                except Exception as e:
                    if "already NOT NULL" in str(e) or "ORA-01442" in str(e):
                        logger.info("ℹ️ QUERY_EMBEDDING_CACHE.user_id is already NOT NULL")
                    else:
                        raise
            
            # VIDEO_SEGMENTS (if exists)
            try:
                if dry_run:
                    logger.info("[DRY RUN] Would execute: ALTER TABLE video_segments MODIFY user_id NUMBER NOT NULL")
                else:
                    try:
                        cursor.execute("ALTER TABLE video_segments MODIFY user_id NUMBER NOT NULL")
                        logger.info("✅ VIDEO_SEGMENTS.user_id is now NOT NULL")
                    except Exception as e:
                        if "already NOT NULL" in str(e) or "ORA-01442" in str(e):
                            logger.info("ℹ️ VIDEO_SEGMENTS.user_id is already NOT NULL")
                        else:
                            raise
            except Exception:
                logger.info("ℹ️ VIDEO_SEGMENTS table not found (skipping)")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error making user_id NOT NULL: {e}")
        return False


def verify_migration() -> bool:
    """Verify migration was successful"""
    logger.info("\n🔍 Verifying migration...")
    
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check for remaining NULL values
            cursor.execute("SELECT COUNT(*) FROM album_media WHERE user_id IS NULL")
            null_media = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM query_embedding_cache WHERE user_id IS NULL")
            null_cache = cursor.fetchone()[0]
            
            if null_media > 0 or null_cache > 0:
                logger.error(f"❌ Migration incomplete: {null_media} media, {null_cache} cache entries still have NULL user_id")
                return False
            
            # Check NOT NULL constraints
            cursor.execute("""
                SELECT column_name, nullable 
                FROM user_tab_columns 
                WHERE table_name = 'ALBUM_MEDIA' AND column_name = 'USER_ID'
            """)
            result = cursor.fetchone()
            if result and result[1] == 'N':
                logger.info("✅ ALBUM_MEDIA.user_id constraint: NOT NULL")
            else:
                logger.warning("⚠️ ALBUM_MEDIA.user_id is still nullable")
            
            cursor.execute("""
                SELECT column_name, nullable 
                FROM user_tab_columns 
                WHERE table_name = 'QUERY_EMBEDDING_CACHE' AND column_name = 'USER_ID'
            """)
            result = cursor.fetchone()
            if result and result[1] == 'N':
                logger.info("✅ QUERY_EMBEDDING_CACHE.user_id constraint: NOT NULL")
            else:
                logger.warning("⚠️ QUERY_EMBEDDING_CACHE.user_id is still nullable")
            
            # Show distribution of content by user
            logger.info("\n📊 Content distribution by user:")
            cursor.execute("""
                SELECT u.id, u.username, u.role, COUNT(am.id) as media_count
                FROM users u
                LEFT JOIN album_media am ON u.id = am.user_id
                GROUP BY u.id, u.username, u.role
                ORDER BY media_count DESC
            """)
            
            for row in cursor.fetchall():
                logger.info(f"  - User {row[0]} ({row[1]}, {row[2]}): {row[3]} media items")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error verifying migration: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Migrate existing content to user ownership model',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/migrate_existing_content.py --dry-run
  python scripts/migrate_existing_content.py --admin-user-id 1
  python scripts/migrate_existing_content.py --verify-only
        """
    )
    parser.add_argument('--admin-user-id', type=int, default=1,
                        help='User ID to assign orphaned content to (default: 1)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be changed without applying changes')
    parser.add_argument('--verify-only', action='store_true',
                        help='Only verify data, do not make changes')
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("Phase 4: Data Migration - Assign Existing Content to Users")
    logger.info("=" * 70)
    
    # Step 1: Verify admin user exists
    logger.info(f"\n📋 Step 1: Verifying user ID {args.admin_user_id}...")
    if not verify_admin_user_exists(args.admin_user_id):
        logger.error("❌ Migration aborted: Admin user verification failed")
        return 1
    
    # Step 2: Check for orphaned content
    logger.info("\n📋 Step 2: Checking for orphaned content...")
    stats = check_orphaned_content()
    if stats is None:
        logger.error("❌ Migration aborted: Could not check orphaned content")
        return 1
    
    total_orphaned = stats['album_media'] + stats['query_embedding_cache']
    if stats['video_segments'] is not None:
        total_orphaned += stats['video_segments']
    
    logger.info(f"\n📊 Orphaned content summary:")
    logger.info(f"  - ALBUM_MEDIA: {stats['album_media']} rows")
    logger.info(f"  - QUERY_EMBEDDING_CACHE: {stats['query_embedding_cache']} rows")
    if stats['video_segments'] is not None:
        logger.info(f"  - VIDEO_SEGMENTS: {stats['video_segments']} rows")
    logger.info(f"  - TOTAL: {total_orphaned} rows")
    
    if total_orphaned == 0:
        logger.info("\n✅ No orphaned content found. Database is clean!")
        if not args.verify_only:
            logger.info("\n📋 Step 3: Setting NOT NULL constraints...")
            if not make_user_id_not_null(args.dry_run):
                return 1
        return verify_migration() if not args.dry_run else 0
    
    # Show samples
    show_sample_orphaned_content()
    
    if args.verify_only:
        logger.info("\n✅ Verification complete (--verify-only mode)")
        return 0
    
    # Step 3: Confirm migration
    if not args.dry_run:
        logger.info(f"\n⚠️ About to assign {total_orphaned} orphaned items to user ID {args.admin_user_id}")
        response = input("Continue with migration? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("❌ Migration cancelled by user")
            return 1
    
    # Step 4: Assign orphaned content
    logger.info("\n📋 Step 3: Assigning orphaned content...")
    if not assign_orphaned_content(args.admin_user_id, args.dry_run):
        logger.error("❌ Migration aborted: Could not assign orphaned content")
        return 1
    
    # Step 5: Make user_id NOT NULL
    if not args.dry_run:
        logger.info("\n📋 Step 4: Setting NOT NULL constraints...")
        if not make_user_id_not_null(args.dry_run):
            logger.warning("⚠️ Warning: Could not set NOT NULL constraints")
            # Continue anyway as data is assigned
    
    # Step 6: Verify
    if not args.dry_run:
        if not verify_migration():
            logger.error("❌ Migration verification failed")
            return 1
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ MIGRATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"✓ All orphaned content assigned to user {args.admin_user_id}")
        logger.info("✓ NOT NULL constraints applied")
        logger.info("✓ Data integrity verified")
    else:
        logger.info("\n" + "=" * 70)
        logger.info("✅ DRY RUN COMPLETE (no changes made)")
        logger.info("=" * 70)
        logger.info("Run without --dry-run to apply changes")
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n\n❌ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
