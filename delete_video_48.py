#!/usr/bin/env python3
"""
Delete video record ID 48 from database and OCI
Usage: python3 delete_video_48.py
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'twelvelabvideoai', 'src')
sys.path.insert(0, src_dir)

from dotenv import load_dotenv
load_dotenv()

from utils.db_utils_flask_safe import get_flask_safe_connection
import oci
from oci_config import load_oci_config

def delete_video_48():
    """Delete video ID 48 from database and OCI"""
    print("="*70)
    print("🗑️  DELETING VIDEO ID 48")
    print("="*70)
    
    # Get video info first
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            sql = "SELECT file_name, oci_namespace, oci_bucket, oci_object_path FROM album_media WHERE id = 48"
            cursor.execute(sql)
            result = cursor.fetchone()
            
            if not result:
                print("❌ Video ID 48 not found in database")
                return False
            
            file_name, namespace, bucket, object_path = result
            print(f"\n📹 Video to delete:")
            print(f"   File: {file_name}")
            print(f"   OCI: {namespace}/{bucket}/{object_path}")
            
            # Delete from OCI
            print(f"\n🗑️  Deleting from OCI...")
            try:
                config = load_oci_config(oci)
                client = oci.object_storage.ObjectStorageClient(config)
                
                # Remove 'Media/' prefix if present
                object_name = object_path.replace('Media/', '', 1) if object_path.startswith('Media/') else object_path
                
                client.delete_object(namespace_name=namespace, bucket_name=bucket, object_name=object_name)
                print(f"   ✅ Deleted from OCI")
            except Exception as e:
                print(f"   ⚠️  OCI deletion warning: {e}")
            
            # Delete from database
            print(f"\n🗑️  Deleting from database...")
            sql = "DELETE FROM album_media WHERE id = 48"
            cursor.execute(sql)
            conn.commit()
            print(f"   ✅ Deleted from database")
            
            print("\n" + "="*70)
            print("✅ VIDEO ID 48 DELETED SUCCESSFULLY")
            print("="*70)
            print("\nYou can now upload a compressed version of the video through the web interface.")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    delete_video_48()
