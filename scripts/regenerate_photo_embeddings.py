#!/usr/bin/env python3
"""
Regenerate missing photo embeddings for photos that were uploaded but failed embedding creation
"""

import os
import sys
import time
import json
import tempfile
import requests
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'twelvelabvideoai' / 'src'))

from utils.db_utils_flask_safe import get_flask_safe_connection
from twelvelabs import TwelveLabs
import oci
from oci_config import load_oci_config
from PIL import Image

def get_photos_missing_embeddings():
    """Get all photos that don't have embeddings"""
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, album_name, file_name, file_path, file_type
                FROM album_media
                WHERE file_type = 'photo' 
                AND embedding_vector IS NULL
                ORDER BY id
            """)
            photos = cursor.fetchall()
            return photos
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        return []

def create_par_url(file_path):
    """Create PAR URL for OCI object storage"""
    try:
        if not file_path.startswith('oci://'):
            return file_path
        
        # Parse OCI path: oci://namespace/bucket/object
        oci_path = file_path.replace('oci://', '')
        parts = oci_path.split('/', 2)
        if len(parts) != 3:
            print(f"⚠️ Invalid OCI path format: {file_path}")
            return None
        
        namespace, bucket, object_name = parts
        
        # Load OCI config
        config = load_oci_config(oci)
        if not config:
            print("❌ Failed to load OCI config")
            return None
        
        # Create Object Storage client
        object_storage = oci.object_storage.ObjectStorageClient(config)
        
        # Create PAR URL (valid for 7 days)
        par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name=f"par-{int(time.time())}",
            access_type="ObjectRead",
            time_expires=(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 7*24*60*60))),
            object_name=object_name
        )
        
        par = object_storage.create_preauthenticated_request(
            namespace_name=namespace,
            bucket_name=bucket,
            create_preauthenticated_request_details=par_details
        )
        
        # Construct full PAR URL
        region = config.get('region', 'us-ashburn-1')
        par_url = f"https://objectstorage.{region}.oraclecloud.com{par.data.access_uri}"
        
        return par_url
        
    except Exception as e:
        print(f"❌ Error creating PAR URL: {e}")
        return None

def create_optimized_version(file_path, max_size_mb=4.5):
    """Create an optimized/resized version of a large photo
    
    Args:
        file_path: OCI path to the original photo
        max_size_mb: Target maximum size in MB
    
    Returns:
        PAR URL to the optimized version, or None if failed
    """
    try:
        # Download original from OCI
        par_url = create_par_url(file_path)
        if not par_url:
            return None
        
        print(f"   📥 Downloading original for optimization...")
        response = requests.get(par_url, timeout=30)
        if response.status_code != 200:
            print(f"   ❌ Failed to download: HTTP {response.status_code}")
            return None
        
        # Open image
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_in:
            tmp_in.write(response.content)
            tmp_in_path = tmp_in.name
        
        img = Image.open(tmp_in_path)
        original_size_mb = os.path.getsize(tmp_in_path) / (1024 * 1024)
        
        print(f"   📐 Original size: {original_size_mb:.1f} MB, resizing...")
        
        # Calculate resize factor
        target_size_mb = max_size_mb
        scale_factor = (target_size_mb / original_size_mb) ** 0.5
        new_width = int(img.width * scale_factor)
        new_height = int(img.height * scale_factor)
        
        # Resize
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save optimized version
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_out:
            tmp_out_path = tmp_out.name
        
        img_resized.save(tmp_out_path, 'JPEG', quality=85, optimize=True)
        optimized_size_mb = os.path.getsize(tmp_out_path) / (1024 * 1024)
        print(f"   ✅ Optimized to: {optimized_size_mb:.1f} MB")
        
        # Upload optimized version to OCI
        if file_path.startswith('oci://'):
            oci_path = file_path.replace('oci://', '')
            parts = oci_path.split('/', 2)
            if len(parts) == 3:
                namespace, bucket, object_name = parts
                
                # Create path for optimized version
                path_parts = object_name.rsplit('/', 1)
                if len(path_parts) == 2:
                    folder, filename = path_parts
                    optimized_object = f"{folder}/resized/{filename}"
                else:
                    optimized_object = f"resized/{object_name}"
                
                # Upload to OCI
                config = load_oci_config(oci)
                if config:
                    object_storage = oci.object_storage.ObjectStorageClient(config)
                    
                    with open(tmp_out_path, 'rb') as f:
                        object_storage.put_object(
                            namespace_name=namespace,
                            bucket_name=bucket,
                            object_name=optimized_object,
                            put_object_body=f
                        )
                    
                    print(f"   📤 Uploaded optimized version to OCI")
                    
                    # Create PAR URL for optimized version
                    oci_optimized_path = f"oci://{namespace}/{bucket}/{optimized_object}"
                    optimized_par = create_par_url(oci_optimized_path)
                    
                    # Cleanup temp files
                    os.unlink(tmp_in_path)
                    os.unlink(tmp_out_path)
                    
                    return optimized_par
        
        # Cleanup
        os.unlink(tmp_in_path)
        os.unlink(tmp_out_path)
        return None
        
    except Exception as e:
        print(f"   ❌ Error creating optimized version: {e}")
        return None

def create_photo_embedding(file_path, media_id, file_name):
    """Create embedding for a photo using TwelveLabs"""
    try:
        # Get PAR URL if needed
        if file_path.startswith('oci://'):
            par_url = create_par_url(file_path)
            if not par_url:
                print(f"❌ Failed to create PAR URL for {file_name}")
                return False
        else:
            par_url = file_path
        
        print(f"🧠 Creating embedding for {file_name}...")
        
        # Create TwelveLabs client
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        # Try with original first
        try:
            # Create embedding task using embed.create (not embed.tasks.create)
            task = client.embed.create(
                model_name="Marengo-retrieval-2.7",
                image_url=par_url
            )
            
            # Wait for completion
            task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
            
            if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
                status = client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
                final = client.embed.tasks.retrieve(task_id=task_id)
            elif hasattr(task, 'wait_for_done'):
                task.wait_for_done(sleep_interval=2)
                final = task
            else:
                final = task
                
        except Exception as e:
            error_msg = str(e)
            # Check if it's a file size error
            if 'filesize_too_large' in error_msg or 'too large' in error_msg.lower():
                print(f"   ⚠️ File too large, creating optimized version...")
                
                # Create optimized version
                optimized_par = create_optimized_version(file_path)
                if not optimized_par:
                    print(f"   ❌ Failed to create optimized version")
                    return False
                
                # Try again with optimized version
                print(f"   🔄 Retrying with optimized version...")
                task = client.embed.create(
                    model_name="Marengo-retrieval-2.7",
                    image_url=optimized_par
                )
                
                task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
                
                if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
                    status = client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
                    final = client.embed.tasks.retrieve(task_id=task_id)
                elif hasattr(task, 'wait_for_done'):
                    task.wait_for_done(sleep_interval=2)
                    final = task
                else:
                    final = task
            else:
                # Other error, re-raise
                raise
        
        # Extract embedding
        embedding_vector = None
        if hasattr(final, 'image_embedding') and getattr(final.image_embedding, 'float', None) is not None:
            embedding_vector = final.image_embedding.float
        elif getattr(final, 'image_embedding', None) is not None and hasattr(final.image_embedding, 'float_'):
            embedding_vector = final.image_embedding.float_
        elif getattr(final, 'image_embedding', None) is not None and getattr(final.image_embedding, 'segments', None):
            seg0 = final.image_embedding.segments[0]
            if hasattr(seg0, 'float_'):
                embedding_vector = seg0.float_
            elif hasattr(seg0, 'float'):
                embedding_vector = seg0.float
        
        if embedding_vector:
            # Update database with embedding
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                embedding_json = json.dumps(list(embedding_vector))
                cursor.execute(
                    "UPDATE album_media SET embedding_vector = TO_VECTOR(:embedding) WHERE id = :id",
                    {'embedding': embedding_json, 'id': media_id}
                )
                conn.commit()
            
            print(f"✅ Embedding created and stored for {file_name}")
            return True
        else:
            print(f"❌ Failed to extract embedding for {file_name}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating embedding for {file_name}: {e}")
        return False

def main():
    print("=" * 60)
    print("🔄 Photo Embeddings Regeneration Script")
    print("=" * 60)
    
    # Get photos missing embeddings
    print("\n📊 Checking for photos missing embeddings...")
    photos = get_photos_missing_embeddings()
    
    if not photos:
        print("✅ No photos missing embeddings!")
        return
    
    print(f"\n📷 Found {len(photos)} photos missing embeddings\n")
    
    # Process each photo
    success_count = 0
    failed_count = 0
    
    for i, (media_id, album_name, file_name, file_path, file_type) in enumerate(photos, 1):
        print(f"\n[{i}/{len(photos)}] Processing: {file_name}")
        print(f"   Album: {album_name}")
        print(f"   ID: {media_id}")
        
        if create_photo_embedding(file_path, media_id, file_name):
            success_count += 1
        else:
            failed_count += 1
        
        # Small delay between requests
        time.sleep(1)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary:")
    print(f"   ✅ Successfully processed: {success_count}")
    print(f"   ❌ Failed: {failed_count}")
    print(f"   📷 Total: {len(photos)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
