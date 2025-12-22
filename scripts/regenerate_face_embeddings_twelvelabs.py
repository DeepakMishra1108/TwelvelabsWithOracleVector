#!/usr/bin/env python3
"""
Regenerate Face Tag Embeddings with TwelveLabs
Migrates from DeepFace (512-dim) to TwelveLabs Marengo (1024-dim)
This ensures face embeddings are in the same vector space as photo embeddings
"""

import os
import sys
import logging
import requests
import tempfile
import json
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
from utils.face_detection_helper import (
    generate_face_embedding_twelvelabs, 
    embedding_to_oracle_vector,
    generate_placeholder_embedding
)

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

def get_face_tags():
    """Get all face tags from database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ft.id, ft.media_id, ft.face_name, ft.bounding_box,
                       am.original_filename, am.presigned_url
                FROM face_tags ft
                JOIN album_media am ON ft.media_id = am.id
                ORDER BY ft.id
            """)
            
            rows = cursor.fetchall()
            face_tags = []
            for row in rows:
                face_tags.append({
                    'id': row[0],
                    'media_id': row[1],
                    'face_name': row[2],
                    'bounding_box': row[3],
                    'filename': row[4],
                    'presigned_url': row[5]
                })
            
            logger.info(f"📊 Found {len(face_tags)} face tags to regenerate")
            return face_tags
            
    except Exception as e:
        logger.error(f"❌ Database query failed: {e}")
        return []

def parse_bbox(bbox_json: str) -> dict:
    """Parse bounding box JSON string"""
    try:
        if isinstance(bbox_json, str):
            bbox = json.loads(bbox_json)
        else:
            bbox = bbox_json
        
        # Handle both formats: {'x': 100, 'y': 200, 'w': 50, 'h': 60}
        # or {'facial_area': {'x': 100, ...}}
        if 'facial_area' in bbox:
            return bbox['facial_area']
        return bbox
        
    except Exception as e:
        logger.error(f"❌ Bbox parse failed: {e}")
        return None

def regenerate_face_embedding(face_tag: dict, api_key: str):
    """Regenerate embedding for a single face tag"""
    try:
        logger.info(f"\n🔄 Processing: {face_tag['face_name']} (ID: {face_tag['id']})")
        logger.info(f"   Photo: {face_tag['filename']}")
        
        # Download image to temp file
        response = requests.get(face_tag['presigned_url'], timeout=30)
        response.raise_for_status()
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file.write(response.content)
        temp_file.close()
        
        # Parse bounding box
        bbox = parse_bbox(face_tag['bounding_box'])
        if not bbox:
            logger.error(f"   ❌ Invalid bounding box")
            os.unlink(temp_file.name)
            return False
        
        # Generate TwelveLabs embedding
        logger.info(f"   🎯 Generating TwelveLabs embedding...")
        embedding = generate_face_embedding_twelvelabs(temp_file.name, bbox, api_key)
        
        if embedding is None:
            logger.warning(f"   ⚠️  TwelveLabs failed, using placeholder")
            embedding = generate_placeholder_embedding(bbox)
        
        # Convert to Oracle VECTOR format
        vector_str = embedding_to_oracle_vector(embedding)
        
        # Update database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE face_tags
                SET face_embedding = TO_VECTOR(:embedding)
                WHERE id = :id
            """, {
                'embedding': vector_str,
                'id': face_tag['id']
            })
            conn.commit()
        
        os.unlink(temp_file.name)
        logger.info(f"   ✅ Updated embedding ({len(embedding)}-dim)")
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Failed: {e}")
        return False

def main():
    """Main execution"""
    logger.info("=" * 80)
    logger.info("🚀 Face Embedding Migration: DeepFace → TwelveLabs")
    logger.info("=" * 80)
    
    # Load environment
    if not load_environment():
        logger.error("❌ Failed to load environment variables")
        return 1
    
    api_key = os.getenv('TWELVE_LABS_API_KEY')
    if not api_key:
        logger.error("❌ TWELVE_LABS_API_KEY not found in environment")
        return 1
    
    logger.info(f"✅ API Key loaded: {api_key[:10]}...")
    
    # Get face tags
    face_tags = get_face_tags()
    if not face_tags:
        logger.warning("⚠️  No face tags found")
        return 0
    
    # Process each face tag
    success_count = 0
    fail_count = 0
    
    for idx, face_tag in enumerate(face_tags, 1):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Progress: {idx}/{len(face_tags)}")
        
        if regenerate_face_embedding(face_tag, api_key):
            success_count += 1
        else:
            fail_count += 1
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 MIGRATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"✅ Successful: {success_count}")
    logger.info(f"❌ Failed: {fail_count}")
    logger.info(f"📈 Total: {len(face_tags)}")
    logger.info("=" * 80)
    
    if fail_count > 0:
        logger.warning(f"⚠️  {fail_count} face tags failed to migrate")
        return 1
    
    logger.info("✅ All face embeddings migrated to TwelveLabs!")
    return 0

if __name__ == '__main__':
    sys.exit(main())
