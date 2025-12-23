#!/usr/bin/env python3
"""
Regenerate all face tag embeddings using ImageBind
This ensures consistency between camera search and stored embeddings
"""

import sys
import os
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def regenerate_embeddings():
    """Regenerate all face tag embeddings using ImageBind"""
    
    # Add src to path
    script_dir = Path(__file__).parent
    src_dir = script_dir.parent / 'src'
    sys.path.insert(0, str(src_dir))
    
    try:
        from utils.imagebind_helper import ImageBindEmbedder
        from utils.face_detection_helper import embedding_to_oracle_vector
        import oracledb
        from dotenv import load_dotenv
        
        # Load environment - try multiple locations
        env_path = script_dir.parent / '.env'
        if not env_path.exists():
            # Try current directory
            env_path = Path('.env')
        
        if env_path.exists():
            logger.info(f"📄 Loading environment from {env_path}")
            load_dotenv(env_path)
        else:
            logger.warning("⚠️ .env file not found, using system environment")
        
        # Connect to database
        logger.info("🔌 Connecting to database...")
        
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_dsn = os.getenv('DB_DSN')
        
        if not all([db_user, db_password, db_dsn]):
            raise ValueError(f"Missing database credentials: USER={bool(db_user)}, PASSWORD={bool(db_password)}, DSN={bool(db_dsn)}")
        
        conn = oracledb.connect(
            user=db_user,
            password=db_password,
            dsn=db_dsn
        )
        cursor = conn.cursor()
        
        # Get all face tags
        logger.info("📊 Fetching face tags...")
        cursor.execute("""
            SELECT ft.id, ft.media_id, ft.bounding_box, ft.face_name,
                   am.file_path, am.oci_object_path
            FROM face_tags ft
            JOIN album_media am ON ft.media_id = am.id
            ORDER BY ft.id
        """)
        
        face_tags = cursor.fetchall()
        total = len(face_tags)
        logger.info(f"📋 Found {total} face tags to process")
        
        if total == 0:
            logger.warning("⚠️ No face tags found!")
            return
        
        # Initialize ImageBind embedder
        logger.info("🚀 Initializing ImageBind model (this may take 30-60 seconds)...")
        embedder = ImageBindEmbedder()
        logger.info("✅ ImageBind model loaded")
        
        # Process each face tag
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for idx, (tag_id, media_id, bbox_json, face_name, file_path, oci_path) in enumerate(face_tags, 1):
            try:
                # Determine image path
                if file_path and os.path.exists(file_path):
                    image_path = file_path
                elif oci_path:
                    # For OCI paths, we'll need to download - skip for now
                    logger.warning(f"⏭️  [{idx}/{total}] Skipping {face_name} (tag_id={tag_id}) - OCI storage not yet supported")
                    skipped_count += 1
                    continue
                else:
                    logger.warning(f"⏭️  [{idx}/{total}] Skipping {face_name} (tag_id={tag_id}) - no valid path")
                    skipped_count += 1
                    continue
                
                # Parse bounding box
                import json
                bbox = json.loads(bbox_json) if bbox_json else None
                
                if not bbox:
                    logger.warning(f"⏭️  [{idx}/{total}] Skipping {face_name} (tag_id={tag_id}) - no bounding box")
                    skipped_count += 1
                    continue
                
                # Generate embedding
                logger.info(f"🔄 [{idx}/{total}] Processing {face_name} (tag_id={tag_id})...")
                
                face_bbox = (bbox['x'], bbox['y'], bbox['w'], bbox['h'])
                embedding = embedder.generate_face_embedding(image_path, face_bbox)
                
                if embedding is None:
                    logger.error(f"❌ [{idx}/{total}] Failed to generate embedding for {face_name}")
                    error_count += 1
                    continue
                
                # Convert to Oracle VECTOR format
                vector_bytes = embedding_to_oracle_vector(embedding)
                
                # Update database
                cursor.execute("""
                    UPDATE face_tags 
                    SET face_embedding = :embedding
                    WHERE id = :tag_id
                """, {
                    'embedding': vector_bytes,
                    'tag_id': tag_id
                })
                
                conn.commit()
                success_count += 1
                
                if idx % 10 == 0:
                    logger.info(f"📈 Progress: {idx}/{total} processed ({success_count} success, {error_count} errors, {skipped_count} skipped)")
                
            except Exception as e:
                logger.error(f"❌ [{idx}/{total}] Error processing tag_id={tag_id}: {e}")
                error_count += 1
                continue
        
        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 Regeneration Complete!")
        logger.info(f"{'='*60}")
        logger.info(f"✅ Success: {success_count}/{total}")
        logger.info(f"❌ Errors: {error_count}/{total}")
        logger.info(f"⏭️  Skipped: {skipped_count}/{total}")
        logger.info(f"{'='*60}\n")
        
        cursor.close()
        conn.close()
        
        return success_count
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == '__main__':
    print("\n" + "="*60)
    print("ImageBind Face Embedding Regeneration")
    print("="*60 + "\n")
    print("⚠️  WARNING: This will regenerate ALL face tag embeddings")
    print("⚠️  This may take several minutes for large datasets")
    print("⚠️  ImageBind model will be loaded (30-60 seconds)\n")
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Cancelled")
        sys.exit(0)
    
    print("\n🚀 Starting regeneration...\n")
    success = regenerate_embeddings()
    
    if success > 0:
        print(f"\n✅ Successfully regenerated {success} embeddings")
        sys.exit(0)
    else:
        print("\n❌ Regeneration failed")
        sys.exit(1)
