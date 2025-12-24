#!/usr/bin/env python3
"""
Backfill Rich Metadata for Existing Photos
Processes all photos without rich_metadata using GPT-4o-mini
"""

import sys
import os
import json
import logging
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

import oracledb
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MetadataBackfiller:
    """Backfill rich metadata for existing photos"""
    
    def __init__(self):
        """Initialize backfiller with database and GPT connections"""
        # Load DB configuration from environment
        db_user = os.getenv('ORACLE_DB_USERNAME') or os.getenv('DB_USER')
        db_password = os.getenv('ORACLE_DB_PASSWORD') or os.getenv('DB_PASSWORD')
        db_dsn = os.getenv('ORACLE_DB_CONNECT_STRING') or os.getenv('DB_DSN')
        wallet_location = os.getenv('TNS_ADMIN') or os.getenv('ORACLE_DB_WALLET_PATH')
        wallet_password = os.getenv('ORACLE_DB_WALLET_PASSWORD') or os.getenv('WALLET_PASSWORD')
        
        if not all([db_user, db_password, db_dsn, wallet_location, wallet_password]):
            missing = []
            if not db_user: missing.append('ORACLE_DB_USERNAME/DB_USER')
            if not db_password: missing.append('ORACLE_DB_PASSWORD/DB_PASSWORD')
            if not db_dsn: missing.append('ORACLE_DB_CONNECT_STRING/DB_DSN')
            if not wallet_location: missing.append('TNS_ADMIN/ORACLE_DB_WALLET_PATH')
            if not wallet_password: missing.append('ORACLE_DB_WALLET_PASSWORD/WALLET_PASSWORD')
            raise ValueError(f"Missing required database configuration: {', '.join(missing)}")
        
        logger.info(f"🔐 Connecting to database with wallet from: {wallet_location}")
        
        # Connect to database using Oracle Cloud wallet
        self.conn = oracledb.connect(
            user=db_user,
            password=db_password,
            dsn=db_dsn,
            config_dir=wallet_location,
            wallet_location=wallet_location,
            wallet_password=wallet_password
        )
        
        # Import GPT metadata extractor
        try:
            from utils.gpt_vision_metadata import GPTVisionMetadataExtractor
            self.extractor = GPTVisionMetadataExtractor()
        except ImportError:
            logger.error("❌ Failed to import GPTVisionMetadataExtractor")
            logger.info("💡 Make sure OPENAI_API_KEY is set in .env")
            raise
        
        logger.info("✅ Backfiller initialized")
    
    def get_photos_without_metadata(self):
        """Get all photos that don't have rich_metadata"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT id, file_name, file_path, album_name
            FROM media_metadata
            WHERE file_type = 'photo'
            AND (rich_metadata IS NULL OR rich_metadata = '{}')
            ORDER BY id
        """)
        
        photos = cursor.fetchall()
        cursor.close()
        
        logger.info(f"📊 Found {len(photos)} photos without metadata")
        return photos
    
    def process_photo(self, photo_id, file_name, file_path, album_name):
        """Process a single photo and store metadata"""
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"📸 Processing: {file_name} (ID: {photo_id})")
            logger.info(f"{'='*60}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.warning(f"⚠️  File not found: {file_path}")
                return False
            
            # Extract metadata using GPT-4o-mini
            metadata = self.extractor.extract_metadata(file_path)
            
            if not metadata or metadata.get('status') == 'failed':
                logger.error(f"❌ Failed to extract metadata")
                return False
            
            # Store metadata in database
            cursor = self.conn.cursor()
            metadata_json = json.dumps(metadata)
            
            cursor.execute("""
                UPDATE media_metadata
                SET rich_metadata = :metadata
                WHERE id = :photo_id
            """, {
                'metadata': metadata_json,
                'photo_id': photo_id
            })
            
            self.conn.commit()
            cursor.close()
            
            # Log summary
            logger.info(f"✅ Metadata stored successfully")
            logger.info(f"   Scene: {metadata.get('scene_type')}")
            logger.info(f"   Setting: {metadata.get('setting')}")
            logger.info(f"   People: {metadata.get('people_count')}")
            logger.info(f"   Tags: {', '.join(metadata.get('tags', [])[:3])}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing photo {photo_id}: {e}")
            self.conn.rollback()
            return False
    
    def run(self, limit=None, delay=0.2):
        """
        Run backfill process
        
        Args:
            limit: Maximum number of photos to process (None = all)
            delay: Delay between API calls in seconds (to respect rate limits)
        """
        try:
            photos = self.get_photos_without_metadata()
            
            if not photos:
                logger.info("✅ All photos already have metadata!")
                return
            
            if limit:
                photos = photos[:limit]
                logger.info(f"🎯 Processing first {limit} photos")
            
            total = len(photos)
            successful = 0
            failed = 0
            start_time = datetime.now()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🚀 Starting backfill: {total} photos")
            logger.info(f"{'='*60}\n")
            
            for idx, (photo_id, file_name, file_path, album_name) in enumerate(photos, 1):
                logger.info(f"\n[{idx}/{total}] Processing {file_name}...")
                
                if self.process_photo(photo_id, file_name, file_path, album_name):
                    successful += 1
                else:
                    failed += 1
                
                # Progress update every 10 photos
                if idx % 10 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = idx / elapsed if elapsed > 0 else 0
                    remaining = (total - idx) / rate if rate > 0 else 0
                    
                    logger.info(f"\n{'='*60}")
                    logger.info(f"📊 Progress: {idx}/{total} ({idx*100//total}%)")
                    logger.info(f"   ✅ Successful: {successful}")
                    logger.info(f"   ❌ Failed: {failed}")
                    logger.info(f"   ⏱️  Rate: {rate:.1f} photos/sec")
                    logger.info(f"   ⏰ ETA: {remaining/60:.1f} minutes")
                    logger.info(f"{'='*60}\n")
                
                # Delay to respect rate limits
                if delay > 0 and idx < total:
                    time.sleep(delay)
            
            # Final summary
            elapsed = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🎉 Backfill Complete!")
            logger.info(f"{'='*60}")
            logger.info(f"   Total processed: {total}")
            logger.info(f"   ✅ Successful: {successful}")
            logger.info(f"   ❌ Failed: {failed}")
            logger.info(f"   ⏱️  Total time: {elapsed/60:.1f} minutes")
            logger.info(f"   💰 Estimated cost: ${total * 0.00015:.4f}")
            logger.info(f"{'='*60}\n")
            
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Backfill interrupted by user")
            logger.info(f"   Processed: {successful + failed} photos")
            logger.info(f"   ✅ Successful: {successful}")
            logger.info(f"   ❌ Failed: {failed}")
        except Exception as e:
            logger.error(f"\n❌ Backfill failed: {e}")
        finally:
            if self.conn:
                self.conn.close()
                logger.info("✅ Database connection closed")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill rich metadata for existing photos')
    parser.add_argument('--limit', type=int, help='Maximum number of photos to process')
    parser.add_argument('--delay', type=float, default=0.2, help='Delay between API calls (seconds)')
    parser.add_argument('--test', action='store_true', help='Test mode: process only 5 photos')
    
    args = parser.parse_args()
    
    if args.test:
        args.limit = 5
        logger.info("🧪 Running in TEST mode: processing 5 photos only")
    
    backfiller = MetadataBackfiller()
    backfiller.run(limit=args.limit, delay=args.delay)


if __name__ == "__main__":
    main()
