#!/usr/bin/env python3
"""
Detect All Faces in Photos using DeepFace
Populates face_tags table with detected faces
"""

import os
import sys
import logging
import requests
import tempfile
import json
import oracledb
from PIL import Image
from pathlib import Path
from dotenv import load_dotenv
import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import DeepFace
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

# Import OCI SDK
try:
    import oci
    OCI_AVAILABLE = True
except ImportError:
    oci = None
    OCI_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables"""
    project_dir = '/home/dataguardian/TwelvelabsWithOracleVector'
    if os.path.exists(project_dir):
        os.chdir(project_dir)
    
    env_path = '/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/.env'
    load_dotenv(env_path)

def get_db_connection():
    """Create database connection"""
    try:
        username = os.getenv('ORACLE_DB_USERNAME')
        password = os.getenv('ORACLE_DB_PASSWORD')
        dsn = os.getenv('ORACLE_DB_CONNECT_STRING')
        wallet_location = os.getenv('ORACLE_DB_WALLET_PATH')
        wallet_password = os.getenv('ORACLE_DB_WALLET_PASSWORD')
        
        connection = oracledb.connect(
            user=username,
            password=password,
            dsn=dsn,
            config_dir=wallet_location,
            wallet_location=wallet_location,
            wallet_password=wallet_password
        )
        return connection
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def get_oci_client():
    """Create OCI object storage client"""
    if not OCI_AVAILABLE:
        return None
    
    try:
        # Check for OCI_CONFIG_PATH environment variable
        env_path = os.getenv('OCI_CONFIG_PATH')
        if env_path and os.path.exists(env_path):
            config = oci.config.from_file(file_location=env_path)
        else:
            # Check for repository-local .oci/config
            script_dir = os.path.dirname(__file__)
            repo_root = os.path.abspath(os.path.join(script_dir, '..'))
            repo_cfg = os.path.join(repo_root, '.oci', 'config')
            
            if os.path.exists(repo_cfg):
                config = oci.config.from_file(file_location=repo_cfg)
            else:
                config = oci.config.from_file()
        
        return oci.object_storage.ObjectStorageClient(config)
    except Exception as e:
        logger.error(f"Failed to create OCI client: {e}")
        return None

def get_par_url(oci_path, oci_client):
    """Get PAR URL for OCI object"""
    if not oci_client or not oci_path.startswith('oci://'):
        return None
    
    try:
        # Parse OCI path: oci://namespace/bucket/object
        path_parts = oci_path[6:].split('/', 2)
        if len(path_parts) != 3:
            logger.error(f"Invalid OCI path format: {oci_path}")
            return None
        
        namespace, bucket, object_name = path_parts
        
        # Get region from OCI client config
        region = os.getenv('OCI_REGION', 'us-ashburn-1')
        
        # Create PAR for 7 days
        expiry_time = datetime.datetime.utcnow() + datetime.timedelta(days=7)
        expiry_string = expiry_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name=f"par-face-detect-{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            access_type="ObjectRead",
            time_expires=expiry_string,
            object_name=object_name
        )
        
        par = oci_client.create_preauthenticated_request(
            namespace, bucket, par_details
        )
        
        base_url = f"https://objectstorage.{region}.oraclecloud.com"
        return f"{base_url}{par.data.access_uri}"
    except Exception as e:
        logger.error(f"Failed to create PAR URL: {e}")
        return None

def download_image(url):
    """Download image from URL to temp file"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file.write(response.content)
        temp_file.close()
        
        return temp_file.name
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        return None

def detect_faces_in_image(image_path):
    """Detect faces using DeepFace"""
    if not DEEPFACE_AVAILABLE:
        logger.error("DeepFace not available")
        return []
    
    try:
        faces = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend='retinaface',
            enforce_detection=False,
            align=True
        )
        
        return faces
    except Exception as e:
        logger.error(f"Face detection failed: {e}")
        return []

def main():
    """Main function"""
    logger.info("🚀 Starting Face Detection with DeepFace")
    
    if not DEEPFACE_AVAILABLE:
        logger.error("❌ DeepFace not installed. Install with: pip install deepface")
        return
    
    # Load environment
    load_environment()
    
    # Get database connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get OCI client
    oci_client = get_oci_client()
    
    try:
        # Clear existing face tags
        logger.info("🗑️  Clearing existing face tags...")
        cursor.execute("DELETE FROM face_tags")
        conn.commit()
        
        # Get all photos
        logger.info("📊 Fetching photos from database...")
        cursor.execute("""
            SELECT id, file_path, file_name
            FROM album_media
            WHERE file_type = 'photo'
            ORDER BY id
        """)
        
        photos = cursor.fetchall()
        logger.info(f"   Found {len(photos)} photos")
        
        success_count = 0
        face_count = 0
        error_count = 0
        
        for idx, (media_id, file_path, file_name) in enumerate(photos, 1):
            logger.info(f"🔄 Processing {idx}/{len(photos)}: {file_name}")
            
            try:
                # Get image URL
                image_url = None
                if file_path.startswith('oci://'):
                    image_url = get_par_url(file_path, oci_client)
                elif file_path.startswith('http'):
                    image_url = file_path
                
                if not image_url:
                    logger.warning(f"   ⚠️  Could not get URL for {file_name}")
                    error_count += 1
                    continue
                
                # Download image
                temp_path = download_image(image_url)
                if not temp_path:
                    logger.warning(f"   ⚠️  Could not download {file_name}")
                    error_count += 1
                    continue
                
                # Detect faces
                faces = detect_faces_in_image(temp_path)
                
                if not faces:
                    logger.info(f"   ℹ️  No faces detected in {file_name}")
                    os.unlink(temp_path)
                    continue
                
                logger.info(f"   ✅ Detected {len(faces)} face(s)")
                
                # Store each face in database
                for face_idx, face_data in enumerate(faces, 1):
                    try:
                        facial_area = face_data['facial_area']
                        confidence = face_data.get('confidence', 0.0)
                        
                        bbox = {
                            'x': int(facial_area['x']),
                            'y': int(facial_area['y']),
                            'w': int(facial_area['w']),
                            'h': int(facial_area['h'])
                        }
                        
                        cursor.execute("""
                            INSERT INTO face_tags 
                            (media_id, face_name, bounding_box, confidence, auto_tagged, created_at, created_by)
                            VALUES (:media_id, :face_name, :bbox, :confidence, 1, SYSTIMESTAMP, 1)
                        """, {
                            'media_id': media_id,
                            'face_name': 'Unknown',
                            'bbox': json.dumps(bbox),
                            'confidence': float(confidence)
                        })
                        
                        face_count += 1
                    except Exception as e:
                        logger.error(f"   ❌ Failed to store face {face_idx}: {e}")
                
                # Commit every 10 photos
                if idx % 10 == 0:
                    conn.commit()
                    logger.info(f"   💾 Committed batch (total faces: {face_count})")
                
                # Cleanup temp file
                os.unlink(temp_path)
                success_count += 1
                
            except Exception as e:
                logger.error(f"   ❌ Error processing {file_name}: {e}")
                error_count += 1
                continue
        
        # Final commit
        conn.commit()
        
        logger.info("\n" + "="*60)
        logger.info("📊 DETECTION SUMMARY")
        logger.info(f"✅ Photos processed: {success_count}/{len(photos)}")
        logger.info(f"👤 Total faces detected: {face_count}")
        logger.info(f"❌ Errors: {error_count}")
        logger.info("="*60)
        logger.info("\n✅ Face detection complete!")
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    main()
