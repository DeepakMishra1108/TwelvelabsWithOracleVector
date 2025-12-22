#!/usr/bin/env python3
"""
Regenerate Face Tag Embeddings with ImageBind
Standalone version that doesn't require Flask imports
Uses Meta's ImageBind (free, self-hosted, no rate limits)
"""

import os
import sys
import logging
import requests
import tempfile
import json
import numpy as np
import oracledb
from PIL import Image
from pathlib import Path
from dotenv import load_dotenv
import datetime
import uuid

# Import OCI SDK
try:
    import oci
    OCI_AVAILABLE = True
except ImportError:
    oci = None
    OCI_AVAILABLE = False

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.imagebind_helper import get_imagebind_embedder, embedding_to_oracle_vector

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables"""
    # Change to project directory to ensure .checkpoints is accessible
    project_dir = '/home/dataguardian/TwelvelabsWithOracleVector'
    if os.path.exists(project_dir):
        os.chdir(project_dir)
    
    env_path = '/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/.env'
    load_dotenv(env_path)
    logger.info(f"✅ Loaded environment from: {env_path}")
    return True

def get_db_connection():
    """Get Oracle database connection"""
    username = os.getenv('ORACLE_DB_USERNAME')
    password = os.getenv('ORACLE_DB_PASSWORD')
    dsn = os.getenv('ORACLE_DB_CONNECT_STRING')
    wallet_location = os.getenv('ORACLE_DB_WALLET_PATH')
    wallet_password = os.getenv('ORACLE_DB_WALLET_PASSWORD')
    
    return oracledb.connect(
        user=username,
        password=password,
        dsn=dsn,
        config_dir=wallet_location,
        wallet_location=wallet_location,
        wallet_password=wallet_password
    )

def _load_oci_config():
    """Load OCI configuration"""
    if not OCI_AVAILABLE or not oci:
        logger.warning("OCI SDK not available")
        return None
    
    try:
        # Check for OCI_CONFIG_PATH environment variable
        env_path = os.getenv('OCI_CONFIG_PATH')
        if env_path and os.path.exists(env_path):
            logger.info(f'Using OCI config from OCI_CONFIG_PATH: {env_path}')
            return oci.config.from_file(file_location=env_path)
        
        # Check for repository-local .oci/config
        script_dir = os.path.dirname(__file__)
        repo_root = os.path.abspath(os.path.join(script_dir, '..'))
        repo_cfg = os.path.join(repo_root, '.oci', 'config')
        
        if os.path.exists(repo_cfg):
            logger.info(f'Using repository-local OCI config: {repo_cfg}')
            return oci.config.from_file(file_location=repo_cfg)
        
        # Fallback to default OCI config
        logger.info('Falling back to default OCI config lookup')
        return oci.config.from_file()
    except Exception as e:
        logger.error(f"Failed to load OCI config: {e}")
        return None

def get_presigned_url_from_oci(oci_path):
    """Generate presigned URL for OCI object"""
    try:
        if not OCI_AVAILABLE or not oci:
            logger.error("OCI SDK not available - cannot generate presigned URLs")
            return None
            
        # Parse OCI path: oci://namespace/bucket/object
        if not oci_path.startswith('oci://'):
            return None
            
        path_parts = oci_path[6:].split('/', 2)
        if len(path_parts) != 3:
            logger.error(f"Invalid OCI path format: {oci_path}")
            return None
            
        namespace, bucket, object_name = path_parts
        
        config = _load_oci_config()
        if not config:
            logger.error("Failed to load OCI configuration")
            return None
            
        obj_client = oci.object_storage.ObjectStorageClient(config)
        
        # Create PAR (Pre-authenticated Request) for 7 days
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
        
        base_url = f"https://objectstorage.{config['region']}.oraclecloud.com"
        presigned_url = f"{base_url}{par_response.data.access_uri}"
        
        logger.debug(f"Generated presigned URL for {object_name}")
        return presigned_url
        
    except Exception as e:
        logger.error(f"Failed to create presigned URL for {oci_path}: {e}")
        return None


def upload_face_crop_to_oci(face_crop_path: str):
    """Upload face crop to OCI and return presigned URL"""
    try:
        config = _load_oci_config()
        if not config:
            logger.error("   ❌ Failed to load OCI config")
            return None
        
        object_storage = oci.object_storage.ObjectStorageClient(config)
        namespace = object_storage.get_namespace().data
        bucket_name = os.getenv('DEFAULT_OCI_BUCKET', 'Media')
        
        # Generate unique object name
        object_name = f"temp/face_crops/{uuid.uuid4()}.jpg"
        
        # Upload file
        with open(face_crop_path, 'rb') as f:
            object_storage.put_object(
                namespace_name=namespace,
                bucket_name=bucket_name,
                object_name=object_name,
                put_object_body=f
            )
        
        # Create PAR (valid for 1 hour)
        par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name=f"face_crop_{uuid.uuid4().hex[:8]}",
            access_type="ObjectRead",
            time_expires=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            object_name=object_name
        )
        
        par_response = object_storage.create_preauthenticated_request(
            namespace_name=namespace,
            bucket_name=bucket_name,
            create_preauthenticated_request_details=par_details
        )
        
        # Construct full URL
        region = config.get('region', 'us-ashburn-1')
        par_url = f"https://objectstorage.{region}.oraclecloud.com{par_response.data.access_uri}"
        
        logger.info(f"   📤 Uploaded face crop to OCI")
        return par_url, object_name
        
    except Exception as e:
        logger.error(f"   ❌ OCI upload failed: {e}")
        return None, None

def generate_face_embedding_imagebind(image_path: str, face_bbox: dict):
    """Generate ImageBind embedding for face crop (FREE, no rate limits!)"""
    try:
        # Get ImageBind embedder
        embedder = get_imagebind_embedder()
        
        # Generate embedding using face_bbox
        embedding = embedder.generate_face_embedding(image_path, face_bbox)
        
        if embedding is not None:
            logger.info(f"   ✅ Generated ImageBind embedding: {len(embedding)}-dim")
            return embedding
        else:
            logger.error("   ❌ No embedding returned from ImageBind")
            return None
            
    except Exception as e:
        logger.error(f"   ❌ Embedding failed: {e}")
        return None

def parse_bbox(bbox_json):
    """Parse bounding box JSON"""
    try:
        if isinstance(bbox_json, str):
            bbox = json.loads(bbox_json)
        else:
            bbox = bbox_json
        
        if 'facial_area' in bbox:
            return bbox['facial_area']
        return bbox
    except Exception as e:
        logger.error(f"   ❌ Bbox parse failed: {e}")
        return None

def main():
    """Main execution"""
    logger.info("=" * 80)
    logger.info("🚀 Regenerating Face Tag Embeddings with ImageBind (FREE!)")
    logger.info("=" * 80)
    
    # Load environment
    if not load_environment():
        return 1
    
    logger.info("✅ Using Meta ImageBind - No API costs, No rate limits!")
    
    # Get face tags
    logger.info("\n📊 Fetching face tags from database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ft.id, ft.media_id, ft.face_name, ft.bounding_box,
               am.file_name, am.file_path
        FROM face_tags ft
        JOIN album_media am ON ft.media_id = am.id
        WHERE ft.needs_embedding = 1
        ORDER BY ft.id
    """)
    
    face_tags = []
    for row in cursor.fetchall():
        face_tags.append({
            'id': row[0],
            'media_id': row[1],
            'face_name': row[2],
            'bounding_box': row[3],
            'filename': row[4],
            'file_path': row[5]
        })
    
    logger.info(f"   Found {len(face_tags)} face tags")
    
    if not face_tags:
        logger.warning("⚠️  No face tags found")
        conn.close()
        return 0
    
    # Process each face tag
    success_count = 0
    fail_count = 0
    
    for idx, face_tag in enumerate(face_tags, 1):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🔄 Processing {idx}/{len(face_tags)}: {face_tag['face_name']}")
        logger.info(f"   Photo: {face_tag['filename']}")
        
        try:
            # Get file URL - convert OCI path to presigned URL if needed
            file_path = face_tag['file_path']
            
            if file_path and file_path.startswith('oci://'):
                logger.info(f"   Converting OCI path to presigned URL...")
                file_url = get_presigned_url_from_oci(file_path)
                if not file_url:
                    logger.error(f"   ❌ Failed to generate presigned URL for {file_path}")
                    fail_count += 1
                    continue
            else:
                file_url = file_path
            
            # Download image
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(response.content)
            temp_file.close()
            
            # Parse bbox
            bbox = parse_bbox(face_tag['bounding_box'])
            if not bbox:
                logger.error("   ❌ Invalid bounding box")
                os.unlink(temp_file.name)
                fail_count += 1
                continue
            
            # Generate embedding with ImageBind
            embedding = generate_face_embedding_imagebind(temp_file.name, bbox)
            
            if embedding is None:
                logger.error("   ❌ Failed to generate embedding")
                os.unlink(temp_file.name)
                fail_count += 1
                continue
            
            # Update database
            vector_str = embedding_to_oracle_vector(embedding)
            cursor.execute("""
                UPDATE face_tags
                SET face_embedding = TO_VECTOR(:embedding),
                    needs_embedding = 0
                WHERE id = :id
            """, {
                'embedding': vector_str,
                'id': face_tag['id']
            })
            conn.commit()
            
            os.unlink(temp_file.name)
            success_count += 1
            
        except Exception as e:
            logger.error(f"   ❌ Failed: {e}")
            fail_count += 1
    
    conn.close()
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 REGENERATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"✅ Successful: {success_count}")
    logger.info(f"❌ Failed: {fail_count}")
    logger.info(f"📈 Total: {len(face_tags)}")
    logger.info("=" * 80)
    
    if fail_count > 0:
        logger.warning(f"⚠️  {fail_count} face tags failed")
        return 1
    
    logger.info("✅ All face embeddings regenerated!")
    return 0

if __name__ == '__main__':
    sys.exit(main())
