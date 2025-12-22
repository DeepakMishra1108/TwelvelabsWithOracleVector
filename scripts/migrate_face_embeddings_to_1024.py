#!/usr/bin/env python3
"""
Migrate Face Tags Table: 512-dim → 1024-dim
Updates face_embedding column to support TwelveLabs Marengo embeddings
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
current_dir = Path(__file__).parent
src_dir = current_dir.parent / 'src'
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# Also try production path
prod_path = '/home/dataguardian/TwelvelabsWithOracleVector/src'
if os.path.exists(prod_path) and prod_path not in sys.path:
    sys.path.insert(0, prod_path)

try:
    from utils.db_utils_flask_safe import get_flask_safe_connection as get_db_connection
except ImportError:
    from utils.database_helper import get_db_connection

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables"""
    env_paths = [
        current_dir.parent / 'twelvelabvideoai' / '.env',
        current_dir.parent / '.env',
        Path.home() / 'TwelvelabsWithOracleVector' / 'twelvelabvideoai' / '.env'
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"✅ Loaded environment from: {env_path}")
            return True
    
    logger.error("❌ No .env file found")
    return False

def migrate_schema():
    """Migrate face_tags table to 1024-dim embeddings"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check current schema
            logger.info("📊 Checking current schema...")
            cursor.execute("""
                SELECT column_name, data_type, data_length
                FROM user_tab_columns
                WHERE table_name = 'FACE_TAGS'
                AND column_name = 'FACE_EMBEDDING'
            """)
            
            result = cursor.fetchone()
            if result:
                logger.info(f"   Current: {result[0]} {result[1]} ({result[2]})")
            else:
                logger.error("   ❌ face_embedding column not found!")
                return False
            
            # Drop and recreate the column with new dimensions
            logger.info("\n🔄 Migrating face_embedding column to 1024 dimensions...")
            
            # Step 1: Drop the column
            logger.info("   1️⃣  Dropping old column...")
            cursor.execute("ALTER TABLE face_tags DROP COLUMN face_embedding")
            
            # Step 2: Add new column with 1024 dimensions
            logger.info("   2️⃣  Adding new column (1024-dim)...")
            cursor.execute("""
                ALTER TABLE face_tags 
                ADD face_embedding VECTOR(1024, FLOAT32)
            """)
            
            conn.commit()
            
            # Verify
            logger.info("\n✅ Verifying new schema...")
            cursor.execute("""
                SELECT column_name, data_type, data_length
                FROM user_tab_columns
                WHERE table_name = 'FACE_TAGS'
                AND column_name = 'FACE_EMBEDDING'
            """)
            
            result = cursor.fetchone()
            if result:
                logger.info(f"   New: {result[0]} {result[1]} ({result[2]})")
            
            logger.info("\n✅ Schema migration complete!")
            logger.info("⚠️  Note: All existing face embeddings have been cleared")
            logger.info("   Run regenerate_face_embeddings_twelvelabs.py to regenerate")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

def main():
    """Main execution"""
    logger.info("=" * 80)
    logger.info("🚀 Face Tags Schema Migration: 512-dim → 1024-dim")
    logger.info("=" * 80)
    
    # Load environment
    if not load_environment():
        logger.error("❌ Failed to load environment variables")
        return 1
    
    # Confirm with user
    print("\n⚠️  WARNING: This will DROP the face_embedding column and all data!")
    print("   You will need to regenerate all face embeddings after this.")
    response = input("\nContinue? (yes/no): ").strip().lower()
    
    if response != 'yes':
        logger.info("❌ Migration cancelled by user")
        return 0
    
    # Run migration
    if migrate_schema():
        logger.info("\n✅ Migration successful!")
        logger.info("\n📋 Next steps:")
        logger.info("   1. Run: python scripts/regenerate_face_embeddings_twelvelabs.py")
        logger.info("   2. Restart the application")
        return 0
    else:
        logger.error("\n❌ Migration failed!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
