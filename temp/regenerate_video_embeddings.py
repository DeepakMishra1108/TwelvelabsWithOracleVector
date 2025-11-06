#!/usr/bin/env python3
"""
Regenerate video embeddings for a specific media ID
Usage: python3 regenerate_video_embeddings.py <media_id>
"""

import sys
import os
import json

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'twelvelabvideoai', 'src')
sys.path.insert(0, src_dir)

from dotenv import load_dotenv
load_dotenv()

from utils.db_utils_flask_safe import get_flask_safe_connection, flask_safe_insert_vector_data
from twelvelabs import TwelveLabs
import oci
from oci_config import load_oci_config

def generate_par_url(oci_object_path, namespace, bucket):
    """Generate Pre-Authenticated Request URL for OCI object"""
    try:
        config = load_oci_config(oci)
        object_storage = oci.object_storage.ObjectStorageClient(config)
        
        # Remove 'Media/' prefix if present
        object_name = oci_object_path.replace('Media/', '', 1) if oci_object_path.startswith('Media/') else oci_object_path
        
        from datetime import datetime, timedelta
        expiration = datetime.utcnow() + timedelta(days=7)
        
        par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name=f"embedding_{os.path.basename(object_name)}_{int(datetime.utcnow().timestamp())}",
            access_type="ObjectRead",
            time_expires=expiration.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            object_name=object_name
        )
        
        par_response = object_storage.create_preauthenticated_request(
            namespace_name=namespace,
            bucket_name=bucket,
            create_preauthenticated_request_details=par_details
        )
        
        region = config.get('region', 'us-ashburn-1')
        par_url = f"https://objectstorage.{region}.oraclecloud.com{par_response.data.access_uri}"
        
        print(f"✅ Generated PAR URL (valid 7 days)")
        return par_url
        
    except Exception as e:
        print(f"❌ Error generating PAR URL: {e}")
        return None

def create_video_embeddings(media_id, par_url, file_name):
    """Create video embeddings using TwelveLabs Marengo"""
    try:
        print(f"🧠 Creating embeddings for {file_name}...")
        
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        # Create embedding task with correct API
        print(f"📤 Submitting to TwelveLabs...")
        task = client.embed.tasks.create(
            model_name="Marengo-retrieval-2.7",
            video_url=par_url,
            video_clip_length=10
        )
        
        print(f"⏳ Waiting for embedding generation...")
        task.wait_for_done(sleep_interval=5)
        
        print(f"✅ Embeddings generated successfully")
        
        # Extract embeddings
        embeddings_list = []
        if hasattr(task, 'video_embedding') and task.video_embedding:
            for segment in task.video_embedding.segments:
                if hasattr(segment, 'embeddings_float'):
                    embeddings_list.append({
                        'start_offset_sec': segment.start_offset_sec,
                        'end_offset_sec': segment.end_offset_sec,
                        'embedding_scope': segment.embedding_scope,
                        'embedding': segment.embeddings_float
                    })
        
        print(f"📊 Extracted {len(embeddings_list)} embedding segments")
        return embeddings_list
        
    except Exception as e:
        print(f"❌ Error creating embeddings: {e}")
        import traceback
        traceback.print_exc()
        return None

def store_embeddings_in_db(media_id, embeddings_list):
    """Store embeddings in database"""
    try:
        print(f"💾 Storing embeddings in database...")
        
        # Convert embeddings to JSON format for TO_VECTOR
        for emb_data in embeddings_list:
            embedding_json = json.dumps(emb_data['embedding'])
            
            # Use flask_safe_insert_vector_data for the first segment
            # (this will update the main embedding_vector column)
            if emb_data == embeddings_list[0]:
                flask_safe_insert_vector_data(
                    media_id=media_id,
                    embedding_json=embedding_json,
                    start_time=emb_data['start_offset_sec'],
                    end_time=emb_data['end_offset_sec']
                )
                print(f"   ✅ Stored main embedding (segment 1/{len(embeddings_list)})")
            
        print(f"✅ All embeddings stored successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error storing embeddings: {e}")
        import traceback
        traceback.print_exc()
        return False

def regenerate_embeddings(media_id):
    """Main function to regenerate embeddings for a media ID"""
    print("="*70)
    print(f"🔄 REGENERATING VIDEO EMBEDDINGS FOR MEDIA ID: {media_id}")
    print("="*70)
    
    # Get media info from database
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            sql = """
            SELECT file_name, file_type, oci_object_path, oci_namespace, oci_bucket
            FROM album_media 
            WHERE id = :media_id
            """
            cursor.execute(sql, {'media_id': media_id})
            result = cursor.fetchone()
            
            if not result:
                print(f"❌ Media ID {media_id} not found in database")
                return False
            
            file_name, file_type, oci_object_path, oci_namespace, oci_bucket = result
            
            if file_type != 'video':
                print(f"❌ Media ID {media_id} is not a video (type: {file_type})")
                return False
            
            print(f"\n📹 Video Information:")
            print(f"   File: {file_name}")
            print(f"   OCI Path: {oci_object_path}")
            print(f"   Namespace: {oci_namespace}")
            print(f"   Bucket: {oci_bucket}")
            
    except Exception as e:
        print(f"❌ Error fetching media info: {e}")
        return False
    
    # Generate PAR URL
    print(f"\n🔗 Generating access URL...")
    par_url = generate_par_url(oci_object_path, oci_namespace, oci_bucket)
    if not par_url:
        return False
    
    # Create embeddings
    print(f"\n🎬 Generating embeddings with TwelveLabs...")
    embeddings_list = create_video_embeddings(media_id, par_url, file_name)
    if not embeddings_list:
        return False
    
    # Store in database
    print(f"\n💾 Storing in database...")
    success = store_embeddings_in_db(media_id, embeddings_list)
    
    if success:
        print("\n" + "="*70)
        print("🎉 EMBEDDING REGENERATION COMPLETE!")
        print("="*70)
        print(f"\n✅ Video {file_name} now has {len(embeddings_list)} embedding segments")
        print(f"✅ Ready for natural language search")
    else:
        print("\n❌ Failed to store embeddings")
    
    return success

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 regenerate_video_embeddings.py <media_id>")
        print("Example: python3 regenerate_video_embeddings.py 48")
        sys.exit(1)
    
    try:
        media_id = int(sys.argv[1])
        regenerate_embeddings(media_id)
    except ValueError:
        print("❌ Invalid media_id. Must be a number.")
        sys.exit(1)
