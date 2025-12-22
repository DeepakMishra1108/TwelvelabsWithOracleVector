#!/usr/bin/env python3
"""
Regenerate all face tags using DeepFace for better face detection
This will replace existing face tags with new ones detected by DeepFace
"""

import os
import sys
import json
import logging
from pathlib import Path
import requests
from io import BytesIO
from PIL import Image
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root / 'twelvelabvideoai' / 'src'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def regenerate_faces_with_deepface():
    """Regenerate all face tags using DeepFace"""
    try:
        from deepface import DeepFace
        
        # Use the existing db utility that handles connection properly
        sys.path.insert(0, str(project_root / 'src'))
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info("🔌 Connecting to Oracle database...")
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Import OCI helper to get PAR URLs
            sys.path.insert(0, str(project_root / 'src'))
            from oci_config import load_oci_config
            import oci
            import uuid
            import datetime
        
        def get_par_url(oci_path):
            """Generate PAR URL for OCI object"""
            if not oci_path.startswith('oci://'):
                return None
            
            path_parts = oci_path[6:].split('/', 2)
            if len(path_parts) != 3:
                return None
            
            namespace, bucket, object_name = path_parts
            
            config = load_oci_config()
            obj_client = oci.object_storage.ObjectStorageClient(config)
            
            expiry_time = datetime.datetime.utcnow() + datetime.timedelta(days=7)
            expiry_string = expiry_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            
            create_par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
                name=f"par-{uuid.uuid4().hex[:8]}",
                access_type="ObjectRead",
                time_expires=expiry_string,
                object_name=object_name
            )
            
            par_response = obj_client.create_preauthenticated_request(
                namespace, bucket, create_par_details
            )
            
            return par_response.data.access_uri
        
        # Get all photos from album_media
        logger.info("📸 Fetching all photos from database...")
        cursor.execute("""
            SELECT id, file_path, file_name
            FROM album_media
            WHERE file_type = 'photo'
            ORDER BY id
        """)
        
        photos = cursor.fetchall()
        logger.info(f"Found {len(photos)} photos to process")
        
        # Clear existing face tags
        logger.info("🗑️ Clearing existing face tags...")
        cursor.execute("DELETE FROM face_tags")
        conn.commit()
        logger.info(f"Deleted existing face tags")
        
        total_faces = 0
        processed_photos = 0
        failed_photos = 0
        
        for media_id, file_path, file_name in photos:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing photo {processed_photos + 1}/{len(photos)}: {file_name} (ID: {media_id})")
                
                # Get PAR URL
                par_url = get_par_url(file_path)
                if not par_url:
                    logger.warning(f"Could not generate PAR URL for {file_path}")
                    failed_photos += 1
                    continue
                
                # Download image
                logger.info(f"📥 Downloading image...")
                response = requests.get(par_url, timeout=30)
                if response.status_code != 200:
                    logger.warning(f"Failed to download image: HTTP {response.status_code}")
                    failed_photos += 1
                    continue
                
                # Save to temp file for DeepFace
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name
                
                try:
                    # Detect faces using DeepFace
                    logger.info(f"🔍 Detecting faces with DeepFace...")
                    faces = DeepFace.extract_faces(
                        img_path=tmp_path,
                        detector_backend='retinaface',  # Best accuracy
                        enforce_detection=False,
                        align=True
                    )
                    
                    logger.info(f"Found {len(faces)} face(s)")
                    
                    # Store each detected face
                    for idx, face_data in enumerate(faces):
                        facial_area = face_data['facial_area']
                        confidence = face_data['confidence']
                        
                        # facial_area contains: x, y, w, h
                        bounding_box = json.dumps({
                            'x': facial_area['x'],
                            'y': facial_area['y'],
                            'w': facial_area['w'],
                            'h': facial_area['h']
                        })
                        
                        logger.info(f"  Face {idx + 1}: bbox={bounding_box}, confidence={confidence:.3f}")
                        
                        # Insert into face_tags table
                        cursor.execute("""
                            INSERT INTO face_tags 
                            (media_id, face_name, bounding_box, confidence, auto_tagged, created_at)
                            VALUES (:media_id, :face_name, :bounding_box, :confidence, :auto_tagged, SYSTIMESTAMP)
                        """, {
                            'media_id': media_id,
                            'face_name': 'Unknown',
                            'bounding_box': bounding_box,
                            'confidence': float(confidence),
                            'auto_tagged': 1
                        })
                        
                        total_faces += 1
                    
                    conn.commit()
                    processed_photos += 1
                    
                    if processed_photos % 10 == 0:
                        logger.info(f"\n📊 Progress: {processed_photos}/{len(photos)} photos, {total_faces} faces detected")
                    
                except Exception as face_error:
                    logger.error(f"Error detecting faces: {face_error}")
                    failed_photos += 1
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
                        
            except Exception as photo_error:
                logger.error(f"Error processing photo {media_id}: {photo_error}")
                failed_photos += 1
                continue
        
        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Face detection complete!")
        logger.info(f"📊 Summary:")
        logger.info(f"  - Total photos: {len(photos)}")
        logger.info(f"  - Successfully processed: {processed_photos}")
        logger.info(f"  - Failed: {failed_photos}")
        
        logger.info(f"  - Total faces detected: {total_faces}")
        logger.info(f"  - Average faces per photo: {total_faces / max(processed_photos, 1):.2f}")
        
        return True    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    logger.info("🚀 Starting face detection with DeepFace...")
    logger.info(f"Project root: {project_root}")
    
    success = regenerate_faces_with_deepface()
    
    if success:
        logger.info("\n✅ Face regeneration completed successfully!")
        logger.info("You can now use the Face Tag Manager UI to assign names to faces")
    else:
        logger.error("\n❌ Face regeneration failed")
        sys.exit(1)
