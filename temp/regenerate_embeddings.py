#!/usr/bin/env python3
"""
Regenerate TwelveLabs embeddings for existing photos in the database.
This is needed after fixing the embedding storage format.
"""

import sys
import json
sys.path.insert(0, 'twelvelabvideoai/src')

from dotenv import load_dotenv
load_dotenv()

from utils.db_utils_flask_safe import get_flask_safe_connection, flask_safe_execute_query
from twelvelabs import TwelveLabs
import os

def regenerate_embeddings_for_album(album_name: str):
    """Regenerate embeddings for all photos in an album"""
    
    # Get TwelveLabs client
    api_key = os.getenv('TWELVE_LABS_API_KEY')
    if not api_key:
        print("❌ TWELVE_LABS_API_KEY not found in environment")
        return
    
    client = TwelveLabs(api_key=api_key)
    
    # Get photos without embeddings
    sql = """
    SELECT id, file_name, file_path, oci_namespace, oci_bucket, oci_object_path
    FROM album_media
    WHERE album_name = :album_name
    AND file_type = 'photo'
    AND embedding_vector IS NULL
    ORDER BY id
    """
    
    photos = flask_safe_execute_query(sql, {'album_name': album_name})
    
    if not photos:
        print(f"✅ All photos in '{album_name}' already have embeddings!")
        return
    
    print(f"📸 Found {len(photos)} photos without embeddings in '{album_name}'")
    
    success_count = 0
    error_count = 0
    
    for photo in photos:
        photo_id, file_name, file_path, oci_namespace, oci_bucket, oci_object_path = photo
        
        print(f"\n🔄 Processing: {file_name} (ID: {photo_id})")
        
        try:
            # Use local file path if available, otherwise use OCI URL
            if file_path and os.path.exists(file_path):
                image_url = f"file://{file_path}"
            elif oci_namespace and oci_bucket and oci_object_path:
                # Construct OCI URL
                image_url = f"https://objectstorage.us-ashburn-1.oraclecloud.com/n/{oci_namespace}/b/{oci_bucket}/o/{oci_object_path}"
            else:
                print(f"  ⚠️  No valid path found, skipping")
                error_count += 1
                continue
            
            # Generate embedding
            print(f"  📡 Calling TwelveLabs API...")
            task = client.embed.create(
                model_name="Marengo-retrieval-2.7",
                image_url=image_url
            )
            
            # Extract embedding
            if hasattr(task, 'image_embedding') and hasattr(task.image_embedding, 'float_'):
                embedding_vector = task.image_embedding.float_
            elif hasattr(task, 'image_embedding') and hasattr(task.image_embedding, 'segments'):
                embedding_vector = task.image_embedding.segments[0].float_
            else:
                print(f"  ❌ Could not extract embedding")
                error_count += 1
                continue
            
            # Store embedding
            print(f"  💾 Storing embedding ({len(embedding_vector)} dimensions)...")
            embedding_json = json.dumps(list(embedding_vector))
            
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE album_media SET embedding_vector = TO_VECTOR(:embedding) WHERE id = :id",
                    {'embedding': embedding_json, 'id': photo_id}
                )
                conn.commit()
            
            print(f"  ✅ Success!")
            success_count += 1
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            error_count += 1
    
    print(f"\n{'='*60}")
    print(f"✅ Successfully processed: {success_count}")
    print(f"❌ Errors: {error_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    album_name = sys.argv[1] if len(sys.argv) > 1 else "Isha"
    print(f"🎯 Regenerating embeddings for album: {album_name}\n")
    regenerate_embeddings_for_album(album_name)
