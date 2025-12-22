#!/usr/bin/env python3
import sys
import logging
import tempfile
import os
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")
logger = logging.getLogger()

from utils.db_utils_flask_safe import get_flask_safe_connection
from utils.face_detection_helper import extract_face_embedding
from utils.face_utils import embedding_to_oracle_vector
import oci
from oci_config import load_oci_config

logger.info("Starting face embedding backfill...")

with get_flask_safe_connection() as conn:
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ft.id, ft.media_id, ft.face_name, ft.bounding_box,
               am.oci_namespace, am.oci_bucket, am.oci_object_path
        FROM face_tags ft
        JOIN album_media am ON ft.media_id = am.id
        WHERE ft.face_embedding IS NULL
        AND ft.bounding_box IS NOT NULL
        AND am.file_type = 'photo'
        ORDER BY ft.id
        FETCH FIRST 100 ROWS ONLY
    """)
    
    tags = cursor.fetchall()
    logger.info(f"Processing first 100 face tags without embeddings")
    
    config = load_oci_config()
    obj_client = oci.object_storage.ObjectStorageClient(config)
    
    success = 0
    for i, (tag_id, media_id, name, bbox_json, ns, bucket, obj_path) in enumerate(tags, 1):
        try:
            logger.info(f"[{i}/{len(tags)}] Processing {name} (tag {tag_id})")
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            get_response = obj_client.get_object(ns, bucket, obj_path)
            with open(temp_file.name, 'wb') as f:
                for chunk in get_response.data.raw.stream(1024*1024, decode_content=False):
                    f.write(chunk)
            temp_file.close()
            
            bbox = json.loads(bbox_json.read()) if hasattr(bbox_json, 'read') else json.loads(bbox_json)
            
            embedding = extract_face_embedding(temp_file.name, bbox)
            
            if embedding is not None:
                vector_bytes = embedding_to_oracle_vector(embedding)
                cursor.execute("UPDATE face_tags SET face_embedding = :emb WHERE id = :id",
                             {'emb': vector_bytes, 'id': tag_id})
                conn.commit()
                success += 1
                logger.info(f"  ✅ Success ({success}/{i})")
            
            os.unlink(temp_file.name)
        except Exception as e:
            logger.error(f"  ❌ Failed: {e}")
    
    logger.info(f"✅ Backfilled {success}/100 embeddings")

logger.info("Backfill complete!")
