#!/usr/bin/env python3
"""
Regenerate all face embeddings using DeepFace (512D Facenet512 model)
This replaces placeholder embeddings with real face embeddings
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.db_utils_flask_safe import get_flask_safe_connection
from deepface import DeepFace
import tempfile
import logging
import json
import numpy as np
import struct

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def embedding_to_oracle_vector(embedding):
    """Convert numpy array to Oracle VECTOR format"""
    if isinstance(embedding, list):
        embedding = np.array(embedding, dtype=np.float32)
    elif not isinstance(embedding, np.ndarray):
        raise ValueError("Embedding must be a numpy array or list")
    
    if embedding.dtype != np.float32:
        embedding = embedding.astype(np.float32)
    
    return embedding.tobytes()

def regenerate_embeddings(limit=None):
    """Regenerate face embeddings using DeepFace"""
    try:
        # Load OCI config
        import oci
        config_path = os.path.expanduser("~/.oci/config")
        config = oci.config.from_file(config_path, "DEFAULT")
        obj_client = oci.object_storage.ObjectStorageClient(config)
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Get all face tags with their image locations
            query = """
                SELECT ft.id, ft.face_name, ft.media_id, ft.bounding_box,
                       am.oci_namespace, am.oci_bucket, am.oci_object_path,
                       am.file_name
                FROM face_tags ft
                JOIN album_media am ON ft.media_id = am.id
                WHERE am.file_type = 'photo'
                AND ft.bounding_box IS NOT NULL
                ORDER BY ft.id
            """
            
            if limit:
                query += f" FETCH FIRST {limit} ROWS ONLY"
            
            cursor.execute(query)
            tags = cursor.fetchall()
            
            logger.info(f"📊 Found {len(tags)} face tags to process")
            
            success = 0
            failed = 0
            
            for i, (tag_id, face_name, media_id, bbox_json, ns, bucket, obj_path, file_name) in enumerate(tags, 1):
                try:
                    logger.info(f"[{i}/{len(tags)}] Processing {face_name} in {file_name}")
                    
                    # Download image
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                    get_response = obj_client.get_object(ns, bucket, obj_path)
                    with open(temp_file.name, 'wb') as f:
                        for chunk in get_response.data.raw.stream(1024*1024, decode_content=False):
                            f.write(chunk)
                    temp_file.close()
                    
                    # Generate DeepFace embedding (512D Facenet512)
                    embeddings = DeepFace.represent(
                        img_path=temp_file.name,
                        model_name='Facenet512',
                        enforce_detection=False
                    )
                    
                    if embeddings and len(embeddings) > 0:
                        embedding = np.array(embeddings[0]['embedding'], dtype=np.float32)
                        
                        # Store in database
                        vector_bytes = embedding_to_oracle_vector(embedding)
                        cursor.execute(
                            "UPDATE face_tags SET face_embedding = :emb WHERE id = :id",
                            {'emb': vector_bytes, 'id': tag_id}
                        )
                        conn.commit()
                        
                        success += 1
                        logger.info(f"  ✅ Updated {face_name} with 512D DeepFace embedding")
                    else:
                        failed += 1
                        logger.warning(f"  ⚠️  No embedding generated")
                    
                    # Cleanup
                    os.unlink(temp_file.name)
                    
                except Exception as e:
                    failed += 1
                    logger.error(f"  ❌ Error: {e}")
            
            logger.info(f"\n✅ Complete: {success} successful, {failed} failed")
            return success, failed
            
    except Exception as e:
        logger.error(f"❌ Script failed: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0

if __name__ == '__main__':
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    regenerate_embeddings(limit)
