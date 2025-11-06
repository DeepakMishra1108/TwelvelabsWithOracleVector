#!/usr/bin/env python3
"""
Retrieve embeddings from existing TwelveLabs tasks and store in database
Uses task IDs from previous successful embedding generation
"""

import os
import sys
import logging

# Add the src directory to path to import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'twelvelabvideoai', 'src'))

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
env_path = os.path.join(os.path.dirname(__file__), 'twelvelabvideoai', '.env')
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(__file__), '.env')
if not os.path.exists(env_path):
    env_path = None

if env_path:
    load_dotenv(env_path)
    logger.info(f"✅ Loaded .env from {env_path}")
else:
    load_dotenv()
    logger.info(f"✅ Loaded .env from environment")

# Import database utils
try:
    from utils.db_utils_flask_safe import get_flask_safe_connection
    logger.info("✅ Database utils imported")
except ImportError as e:
    logger.error(f"❌ Failed to import database utils: {e}")
    sys.exit(1)

# Import TwelveLabs
try:
    from twelvelabs import TwelveLabs
    logger.info("✅ TwelveLabs SDK imported")
except ImportError:
    logger.error("❌ TwelveLabs SDK not found. Install: pip install twelvelabs-py")
    sys.exit(1)

def get_db_connection():
    """Create database connection using Flask-safe utils"""
    try:
        return get_flask_safe_connection()
    except Exception as e:
        logger.exception(f"❌ Database connection error: {e}")
        return None


def store_embeddings_for_chunk(media_id, file_name, task_id):
    """Retrieve task results and store embeddings"""
    try:
        logger.info(f"🎬 Processing chunk {media_id}: {file_name}")
        logger.info(f"📥 Retrieving task {task_id}")
        
        # Create TwelveLabs client
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        # Retrieve task
        final = client.embed.tasks.retrieve(task_id=task_id)
        
        # Check response structure
        logger.info(f"📦 Task status: {getattr(final, 'status', 'unknown')}")
        
        if not hasattr(final, 'video_embedding') or not final.video_embedding:
            logger.warning(f"❌ No video_embedding in response")
            return False
        
        if not hasattr(final.video_embedding, 'segments') or not final.video_embedding.segments:
            logger.warning(f"❌ No segments in video_embedding")
            return False
        
        segments = final.video_embedding.segments
        logger.info(f"✅ Retrieved {len(segments)} segments")
        
        # Inspect first segment
        if len(segments) > 0:
            first_seg = segments[0]
            logger.info(f"📦 First segment: start={first_seg.start_offset_sec}, end={first_seg.end_offset_sec}")
            
            if hasattr(first_seg, 'embedding_scope') and first_seg.embedding_scope:
                logger.info(f"✅ embedding_scope = '{first_seg.embedding_scope}'")
            
            if hasattr(first_seg, 'float_'):
                logger.info(f"✅ Has float_ attribute, type: {type(first_seg.float_)}, length: {len(first_seg.float_)}")
                logger.info(f"📦 First 5 values: {first_seg.float_[:5]}")
            else:
                logger.warning(f"❌ No float_ attribute on segment")
        
        # Now store embeddings
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            embedding_count = 0
            representative_embedding = None
            
            for segment in segments:
                start_time = segment.start_offset_sec
                end_time = segment.end_offset_sec
                
                # Extract embedding vector - it's directly on the segment as float_
                embedding_vector = None
                if hasattr(segment, 'float_') and segment.float_:
                    embedding_vector = segment.float_
                
                if embedding_vector:
                    # Convert to list if needed
                    if not isinstance(embedding_vector, list):
                        embedding_vector = list(embedding_vector)
                    
                    # Store in database
                    cursor.execute("""
                        INSERT INTO video_embeddings 
                        (video_file, start_time, end_time, embedding_vector)
                        VALUES (:video_file, :start_time, :end_time, TO_VECTOR(:embedding))
                    """, {
                        'video_file': file_name,
                        'start_time': start_time,
                        'end_time': end_time,
                        'embedding': str(embedding_vector)
                    })
                    
                    embedding_count += 1
                    
                    # Save first embedding as representative
                    if representative_embedding is None:
                        representative_embedding = embedding_vector
            
            # Update album_media with representative embedding
            if representative_embedding:
                cursor.execute("""
                    UPDATE album_media 
                    SET embedding_vector = TO_VECTOR(:embedding)
                    WHERE id = :media_id
                """, {
                    'embedding': str(representative_embedding),
                    'media_id': media_id
                })
            
            conn.commit()
            cursor.close()
        
        logger.info(f"✅ Stored {embedding_count} embeddings for chunk {media_id}")
        return True
        
    except Exception as e:
        logger.exception(f"❌ Error processing chunk {media_id}: {e}")
        return False


def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🚀 Retrieving embeddings from existing tasks")
    logger.info("=" * 60)
    
    # Task IDs from previous successful runs
    tasks = [
        {
            'media_id': 64,
            'file_name': 'tmp2xpsrppr_chunk_002_of_002.mp4',
            'task_id': '690bf246952dd95fc6e2631f'
        },
        {
            'media_id': 63,
            'file_name': 'tmp2xpsrppr_chunk_001_of_002.mp4',
            'task_id': '690bf2463d0db4ad094891b4'
        }
    ]
    
    success_count = 0
    fail_count = 0
    
    for task_info in tasks:
        if store_embeddings_for_chunk(**task_info):
            success_count += 1
        else:
            fail_count += 1
    
    logger.info("=" * 60)
    logger.info("📊 SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✅ Successful: {success_count}/{len(tasks)}")
    logger.info(f"❌ Failed: {fail_count}/{len(tasks)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
