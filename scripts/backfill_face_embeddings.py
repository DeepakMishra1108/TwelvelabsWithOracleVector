#!/usr/bin/env python3
"""
Backfill face embeddings for existing face tags
This script extracts face embeddings from tagged faces and stores them for auto-recognition
"""

import sys
import os
import logging
import tempfile
import requests

# Add src to path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(script_dir), 'src')
sys.path.insert(0, src_dir)

from utils.db_utils_flask_safe import get_flask_safe_connection
from utils.face_detection_helper import detect_faces, extract_face_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill_face_embeddings():
    """Generate and store face embeddings for existing face tags that don't have them"""
    
    try:
        # Get face tags without embeddings
        conn = get_flask_safe_connection()
        cursor = conn.cursor()
        
        # Find face tags that have bounding boxes but no embeddings
        cursor.execute("""
            SELECT 
                ft.id,
                ft.media_id,
                ft.face_name,
                ft.bounding_box,
                am.file_path,
                am.oci_namespace,
                am.oci_bucket,
                am.oci_object_path
            FROM face_tags ft
            JOIN album_media am ON ft.media_id = am.id
            WHERE ft.face_embedding IS NULL
            AND ft.bounding_box IS NOT NULL
            AND am.file_type = 'photo'
            ORDER BY ft.face_name, ft.id
        """)
        
        tags_to_process = cursor.fetchall()
        
        if not tags_to_process:
            logger.info("✅ No face tags need embedding backfill")
            return
        
        logger.info(f"🔄 Found {len(tags_to_process)} face tags to backfill")
        
        # Load OCI client for downloading images
        try:
            import oci
            from oci_config import load_oci_config
            
            config = load_oci_config()
            obj_client = oci.object_storage.ObjectStorageClient(config)
            logger.info("✅ OCI client loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load OCI client: {e}")
            return
        
        success_count = 0
        failed_count = 0
        
        # Process each face tag
        for row in tags_to_process:
            tag_id, media_id, face_name, bbox_json, file_path, namespace, bucket, object_path = row
            
            try:
                logger.info(f"Processing tag {tag_id}: {face_name} in media {media_id}")
                
                # Download image from OCI
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                
                try:
                    # Get object from OCI
                    get_response = obj_client.get_object(namespace, bucket, object_path)
                    with open(temp_file.name, 'wb') as f:
                        for chunk in get_response.data.raw.stream(1024 * 1024, decode_content=False):
                            f.write(chunk)
                    temp_file.close()
                    
                    # Parse bounding box
                    import json
                    if isinstance(bbox_json, str):
                        bbox = json.loads(bbox_json)
                    else:
                        bbox = json.loads(bbox_json.read()) if hasattr(bbox_json, 'read') else bbox_json
                    
                    # Extract face embedding using the bounding box
                    face_embedding = extract_face_embedding(temp_file.name, bbox)
                    
                    if face_embedding is not None:
                        # Convert embedding to Oracle VECTOR format
                        from utils.face_utils import embedding_to_oracle_vector
                        vector_bytes = embedding_to_oracle_vector(face_embedding)
                        
                        # Update face tag with embedding
                        update_cursor = conn.cursor()
                        update_cursor.execute("""
                            UPDATE face_tags
                            SET face_embedding = :embedding
                            WHERE id = :tag_id
                        """, {
                            'embedding': vector_bytes,
                            'tag_id': tag_id
                        })
                        conn.commit()
                        
                        logger.info(f"  ✅ Stored embedding for '{face_name}' (tag {tag_id})")
                        success_count += 1
                    else:
                        logger.warning(f"  ⚠️  Failed to extract embedding for tag {tag_id}")
                        failed_count += 1
                    
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                    
            except Exception as e:
                logger.error(f"  ❌ Failed to process tag {tag_id}: {e}")
                failed_count += 1
                continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Backfill complete!")
        logger.info(f"   Successfully processed: {success_count}")
        logger.info(f"   Failed: {failed_count}")
        logger.info(f"{'='*60}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        raise

if __name__ == "__main__":
    backfill_face_embeddings()
