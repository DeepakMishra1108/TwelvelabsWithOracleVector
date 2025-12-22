#!/usr/bin/env python3
"""
Group Similar Faces using DeepFace Embeddings
Clusters similar faces together for batch tagging
"""

import os
import sys
import logging
import requests
import tempfile
import json
import oracledb
import numpy as np
from PIL import Image
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from sklearn.cluster import DBSCAN
from collections import defaultdict
import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import DeepFace
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("❌ DeepFace not available. Install with: pip install deepface")
    sys.exit(1)

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
        env_path = os.getenv('OCI_CONFIG_PATH')
        if env_path and os.path.exists(env_path):
            config = oci.config.from_file(file_location=env_path)
        else:
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

def get_presigned_url(oci_client, file_path):
    """Get presigned URL for file - handles oci:// paths"""
    try:
        # If file_path is already oci:// format, parse it
        if file_path.startswith('oci://'):
            path_parts = file_path[6:].split('/', 2)
            if len(path_parts) != 3:
                logger.error(f"Invalid OCI path format: {file_path}")
                return None
            namespace, bucket, object_name = path_parts
        else:
            # Build from env vars
            namespace = os.getenv('OCI_NAMESPACE')
            bucket = os.getenv('OCI_BUCKET_NAME')
            if not namespace or not bucket:
                logger.error("Missing OCI_NAMESPACE or OCI_BUCKET_NAME")
                return None
            object_name = file_path.lstrip('/')
        
        if not oci_client:
            return None
        
        # Create PAR for 1 hour
        import datetime
        expiry_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        expiry_string = expiry_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        par_response = oci_client.create_preauthenticated_request(
            namespace_name=namespace,
            bucket_name=bucket,
            create_preauthenticated_request_details=oci.object_storage.models.CreatePreauthenticatedRequestDetails(
                name=f"temp_{object_name.replace('/', '_')[:20]}",
                access_type="ObjectRead",
                time_expires=expiry_string,
                object_name=object_name
            )
        )
        
        region = os.getenv('OCI_REGION', 'us-ashburn-1')
        base_url = f"https://objectstorage.{region}.oraclecloud.com"
        return f"{base_url}{par_response.data.access_uri}"
    except Exception as e:
        logger.error(f"Failed to get presigned URL for {file_path}: {e}")
        return None

def download_image(url):
    """Download image from URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        from io import BytesIO
        return Image.open(BytesIO(response.content))
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {e}")
        return None

def crop_face_from_image(image, bbox):
    """Crop face from image using bounding box"""
    try:
        x = int(bbox.get('x', 0))
        y = int(bbox.get('y', 0))
        w = int(bbox.get('w', 100))
        h = int(bbox.get('h', 100))
        
        # Add 20% padding
        padding_x = int(w * 0.2)
        padding_y = int(h * 0.2)
        
        x1 = max(0, x - padding_x)
        y1 = max(0, y - padding_y)
        x2 = min(image.width, x + w + padding_x)
        y2 = min(image.height, y + h + padding_y)
        
        return image.crop((x1, y1, x2, y2))
    except Exception as e:
        logger.error(f"Failed to crop face: {e}")
        return None

def generate_face_embedding(face_image):
    """Generate embedding for a face image using DeepFace"""
    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            face_image.save(tmp.name, 'JPEG')
            tmp_path = tmp.name
        
        # Generate embedding using DeepFace
        embedding_objs = DeepFace.represent(
            img_path=tmp_path,
            model_name='Facenet512',  # 512-dimensional embeddings
            enforce_detection=False
        )
        
        # Clean up
        os.unlink(tmp_path)
        
        if embedding_objs and len(embedding_objs) > 0:
            return np.array(embedding_objs[0]['embedding'])
        return None
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None

def cluster_faces(embeddings, face_ids, eps=0.15, min_samples=3):
    """Cluster faces using DBSCAN with strict parameters
    
    Args:
        embeddings: List of face embeddings
        face_ids: List of corresponding face IDs
        eps: Maximum distance for faces to be in same cluster (lower = stricter). 
             For cosine distance with normalized vectors, typical values:
             - 0.10-0.15: Very strict (same person, similar angle/lighting)
             - 0.20-0.30: Moderate (same person, different conditions)
             - 0.40+: Loose (may group different people)
        min_samples: Minimum faces required to form a cluster
    """
    try:
        if len(embeddings) < min_samples:
            logger.warning(f"Not enough faces to cluster: {len(embeddings)}")
            return {}
        
        # Convert to numpy array
        X = np.array(embeddings)
        
        # Normalize embeddings (for cosine distance)
        X = X / np.linalg.norm(X, axis=1, keepdims=True)
        
        # Cluster using DBSCAN (using cosine distance)
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
        labels = clustering.fit_predict(X)
        
        # Group faces by cluster
        clusters = defaultdict(list)
        noise_count = 0
        for face_id, label in zip(face_ids, labels):
            if label != -1:  # -1 is noise/outliers
                clusters[int(label)].append(face_id)
            else:
                noise_count += 1
        
        logger.info(f"   Found {len(clusters)} clusters with {noise_count} faces as outliers")
        
        return dict(clusters)
    except Exception as e:
        logger.error(f"Failed to cluster faces: {e}")
        return {}

def main():
    """Main function"""
    if not DEEPFACE_AVAILABLE:
        logger.error("DeepFace is not available")
        return
    
    logger.info("🚀 Starting face grouping...")
    load_environment()
    
    oci_client = get_oci_client()
    if not oci_client:
        logger.warning("⚠️ OCI client not available, will use local files")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get all face tags (not just Unknown, since we want to re-cluster everything)
        cursor.execute("""
            SELECT ft.id, ft.media_id, ft.bounding_box, am.file_path
            FROM face_tags ft
            JOIN album_media am ON ft.media_id = am.id
            ORDER BY ft.id
        """)
        
        rows = cursor.fetchall()
        total_faces = len(rows)
        
        logger.info(f"📊 Found {total_faces} faces to process")
        
        if total_faces == 0:
            logger.info("No faces found")
            return
        
        # First, reset ALL faces to Unknown before re-clustering
        logger.info("🔄 Resetting all faces to Unknown...")
        cursor.execute("UPDATE face_tags SET face_name = 'Unknown'")
        conn.commit()
        
        # Generate embeddings for all faces
        face_ids = []
        embeddings = []
        processed = 0
        skipped = 0
        
        for face_id, media_id, bbox_json, file_path in rows:
            processed += 1
            
            try:
                # Parse bounding box
                bbox = json.loads(bbox_json) if bbox_json else None
                if not bbox:
                    skipped += 1
                    continue
                
                # Get image URL
                url = get_presigned_url(oci_client, file_path)
                if not url:
                    skipped += 1
                    continue
                
                # Download image
                image = download_image(url)
                if not image:
                    skipped += 1
                    continue
                
                # Crop face
                face_img = crop_face_from_image(image, bbox)
                if not face_img:
                    skipped += 1
                    continue
                
                # Generate embedding
                embedding = generate_face_embedding(face_img)
                if embedding is not None:
                    face_ids.append(face_id)
                    embeddings.append(embedding)
                    
                    if processed % 10 == 0:
                        logger.info(f"⏳ Processed {processed}/{total_faces} faces ({len(embeddings)} successful)")
                else:
                    skipped += 1
                    
            except Exception as e:
                logger.error(f"❌ Error processing face {face_id}: {e}")
                skipped += 1
                continue
        
        logger.info(f"✅ Generated embeddings for {len(embeddings)}/{total_faces} faces ({skipped} skipped)")
        
        # Cluster faces with STRICT parameters
        logger.info("🔍 Clustering similar faces with strict threshold...")
        # Use eps=0.15 for very strict matching (lower = more strict)
        # min_samples=3 means at least 3 similar faces to form a group
        clusters = cluster_faces(embeddings, face_ids, eps=0.15, min_samples=3)
        
        if not clusters:
            logger.info("No clusters found. Try adjusting eps parameter.")
            return
        
        logger.info(f"📦 Found {len(clusters)} groups of similar faces")
        
        # Store cluster assignments in database
        for cluster_id, cluster_face_ids in clusters.items():
            logger.info(f"   Group {cluster_id + 1}: {len(cluster_face_ids)} faces")
            
            # Update face_tags with cluster_id (stored in a JSON metadata field or separate column)
            for face_id in cluster_face_ids:
                cursor.execute("""
                    UPDATE face_tags 
                    SET face_name = :group_name
                    WHERE id = :face_id
                """, {
                    'group_name': f'Group_{cluster_id + 1}',
                    'face_id': face_id
                })
        
        conn.commit()
        logger.info(f"✅ Updated {sum(len(v) for v in clusters.values())} faces with group assignments")
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("📊 GROUPING SUMMARY")
        logger.info(f"Total faces processed: {total_faces}")
        logger.info(f"Embeddings generated: {len(embeddings)}")
        logger.info(f"Groups created: {len(clusters)}")
        logger.info(f"Faces grouped: {sum(len(v) for v in clusters.values())}")
        logger.info(f"Ungrouped faces: {len(embeddings) - sum(len(v) for v in clusters.values())}")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
    
    logger.info("\n✅ Face grouping complete!")

if __name__ == "__main__":
    main()
