#!/usr/bin/env python3
"""Face Detection and Embedding Helper
Handles face detection using OpenCV and embedding generation
Designed to work with TwelveLabs Marengo model for face embeddings
"""

import os
import sys
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import struct
import base64
import json

# Add parent directory to path
current_dir = Path(__file__).parent
if str(current_dir.parent.parent) not in sys.path:
    sys.path.insert(0, str(current_dir.parent.parent))

logger = logging.getLogger(__name__)

try:
    import cv2
    CV2_AVAILABLE = True
    logger.info("✅ OpenCV loaded successfully")
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("⚠️  OpenCV not available. Install with: pip install opencv-python")

# Try to import DeepFace for better face detection
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    logger.info("✅ DeepFace loaded successfully")
except ImportError:
    DEEPFACE_AVAILABLE = False
    logger.warning("⚠️  DeepFace not available. Install with: pip install deepface")

# Face detection cascade classifier (fallback)
FACE_CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml' if CV2_AVAILABLE else None

# Detection parameters
MIN_FACE_SIZE = (30, 30)
SCALE_FACTOR = 1.1
MIN_NEIGHBORS = 5

# For TwelveLabs-based embeddings, use 1024-dim vectors to match Marengo model
EMBEDDING_DIM = 1024


def check_dependencies():
    """Check if all required dependencies are installed"""
    if not CV2_AVAILABLE:
        raise ImportError(
            "OpenCV is required for face detection. "
            "Install with: pip install opencv-python"
        )
    return True


def detect_faces_deepface(image_path: str) -> List[Dict]:
    """
    Detect faces using DeepFace library (modern deep learning approach)
    Much more accurate than Haar Cascade, handles various angles, lighting, and occlusions
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of face dictionaries with bounding box and confidence
    """
    if not DEEPFACE_AVAILABLE:
        logger.warning("⚠️  DeepFace not available, falling back to OpenCV")
        return detect_faces_opencv(image_path)
    
    try:
        logger.debug(f"🔍 Detecting faces with DeepFace: {image_path}")
        
        # Use RetinaFace detector (best accuracy) with enforce_detection=False to handle no-face cases
        faces = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend='retinaface',  # Best detector: retinaface > mtcnn > opencv > ssd
            enforce_detection=False,
            align=True
        )
        
        validated_faces = []
        for face_obj in faces:
            facial_area = face_obj.get('facial_area', {})
            confidence = face_obj.get('confidence', 1.0)
            
            # DeepFace returns {x, y, w, h}
            if facial_area and all(k in facial_area for k in ['x', 'y', 'w', 'h']):
                validated_faces.append({
                    'facial_area': {
                        'x': int(facial_area['x']),
                        'y': int(facial_area['y']),
                        'w': int(facial_area['w']),
                        'h': int(facial_area['h'])
                    },
                    'confidence': float(confidence),
                    'detector': 'retinaface'
                })
        
        logger.info(f"✅ DeepFace detected {len(validated_faces)} face(s) in {image_path}")
        return validated_faces
        
    except Exception as e:
        logger.warning(f"⚠️  DeepFace detection failed: {e}, falling back to OpenCV")
        return detect_faces_opencv(image_path)


def detect_faces_opencv(image_path: str) -> List[Dict]:
    """
    Detect all faces using OpenCV Haar Cascade (fallback method)
    Used when DeepFace is not available or fails
    
    Args:
        image_path: Path to the image file
        
    Returns:
        List of face dictionaries with bounding box and confidence
    """
    check_dependencies()
    
    try:
        logger.debug(f"🔍 Detecting faces with OpenCV: {image_path}")
        
        # Load the image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        # Convert to grayscale for detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Load cascade classifier
        face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
        
        # Detect faces with standard parameters
        faces_rects = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        validated_faces = []
        for (x, y, w, h) in faces_rects:
            validated_faces.append({
                'facial_area': {'x': int(x), 'y': int(y), 'w': int(w), 'h': int(h)},
                'confidence': 1.0,
                'detector': 'opencv_haar'
            })
        
        logger.info(f"✅ OpenCV detected {len(validated_faces)} face(s) in {image_path}")
        return validated_faces
        
    except Exception as e:
        logger.error(f"❌ Face detection failed for {image_path}: {e}")
        return []


def crop_face_region(image_path: str, face_bbox: Dict) -> Optional[np.ndarray]:
    """
    Crop face region from image
    
    Args:
        image_path: Path to the image file
        face_bbox: Bounding box dict {'x': int, 'y': int, 'w': int, 'h': int}
        
    Returns:
        Cropped face image as numpy array, or None if failed
    """
    check_dependencies()
    
    try:
        # Load the image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        # Extract bbox coordinates
        x = face_bbox['x']
        y = face_bbox['y']
        w = face_bbox['w']
        h = face_bbox['h']
        
        # Crop with some padding
        padding = 10
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)
        
        face_crop = image[y:y+h, x:x+w]
        
        logger.debug(f"✅ Cropped face region: {w}x{h}")
        return face_crop
        
    except Exception as e:
        logger.error(f"❌ Face crop failed: {e}")
        return None


def save_face_crop(face_image: np.ndarray, output_path: str) -> bool:
    """
    Save cropped face image to file
    
    Args:
        face_image: Face image as numpy array
        output_path: Path to save the image
        
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        success = cv2.imwrite(output_path, face_image)
        
        if success:
            logger.debug(f"✅ Saved face crop to: {output_path}")
        else:
            logger.error(f"❌ Failed to save face crop to: {output_path}")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Face save failed: {e}")
        return False


def generate_placeholder_embedding(face_bbox: Dict) -> np.ndarray:
    """
    Generate a placeholder embedding based on face bbox
    In production, this will be replaced with actual TwelveLabs embeddings
    
    Args:
        face_bbox: Bounding box dict
        
    Returns:
        1024-dimensional placeholder embedding (matches TwelveLabs Marengo)
    """
    # For now, generate a deterministic embedding based on bbox
    # This is just a placeholder - in production we'll use TwelveLabs
    np.random.seed(hash(str(face_bbox)) % 2**32)
    embedding = np.random.randn(EMBEDDING_DIM).astype(np.float32)
    # Normalize
    embedding = embedding / np.linalg.norm(embedding)
    return embedding


def generate_face_embedding_twelvelabs(image_path: str, face_bbox: Dict, api_key: str = None) -> np.ndarray:
    """
    Generate face embedding using TwelveLabs Marengo model (same as photo embeddings)
    This ensures face embeddings and photo embeddings are in the same vector space
    
    Args:
        image_path: Path to the full image
        face_bbox: Dictionary with 'x', 'y', 'w', 'h' keys for face bounding box
        api_key: TwelveLabs API key
        
    Returns:
        1024-dimensional TwelveLabs embedding vector
    """
    try:
        from PIL import Image
        import tempfile
        import os
        
        # Crop face region from image
        img = Image.open(image_path)
        x, y, w, h = face_bbox.get('x', 0), face_bbox.get('y', 0), face_bbox.get('w', 0), face_bbox.get('h', 0)
        
        # Add 20% padding around face for better context
        padding = 0.2
        x_pad = int(w * padding)
        y_pad = int(h * padding)
        
        left = max(0, x - x_pad)
        top = max(0, y - y_pad)
        right = min(img.width, x + w + x_pad)
        bottom = min(img.height, y + h + y_pad)
        
        face_crop = img.crop((left, top, right, bottom))
        
        # Save crop to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        face_crop.save(temp_file.name, 'JPEG')
        temp_file.close()
        
        # Generate embedding using TwelveLabs
        try:
            from twelvelabs import TwelveLabs
            import base64
            
            client = TwelveLabs(api_key=api_key)
            
            # Read image file as base64
            with open(temp_file.name, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Create data URL
            image_data_url = f"data:image/jpeg;base64,{img_data}"
            
            task = client.embed.create(
                model_name="Marengo-retrieval-2.7",
                image_url=image_data_url
            )
            
            # Wait for embedding to be ready
            task.wait_for_done(sleep_interval=0.5, timeout=30)
            
            if task.image_embedding and len(task.image_embedding.segments) > 0:
                embedding_list = task.image_embedding.segments[0].embeddings_float
                embedding = np.array(embedding_list, dtype=np.float32)
                
                # Normalize
                embedding = embedding / np.linalg.norm(embedding)
                
                os.unlink(temp_file.name)
                logger.info(f"✅ Generated TwelveLabs face embedding: {len(embedding)}-dim")
                return embedding
            else:
                logger.warning("No embedding returned from TwelveLabs")
                os.unlink(temp_file.name)
                return None
                
        except Exception as e:
            logger.error(f"❌ TwelveLabs embedding failed: {e}")
            os.unlink(temp_file.name)
            return None
            
    except Exception as e:
        logger.error(f"❌ Face crop failed: {e}")
        return None


def generate_face_embedding(image_path: str, face_region: Dict = None) -> np.ndarray:
    """
    DEPRECATED: Use generate_face_embedding_twelvelabs instead
    This function is kept for backward compatibility but now uses TwelveLabs
    
    Args:
        image_path: Path to the image
        face_region: Optional face region dict with 'facial_area' containing x, y, w, h
        
    Returns:
        Face embedding vector (1024-dim TwelveLabs vector)
    """
    logger.warning("⚠️  generate_face_embedding is deprecated, use generate_face_embedding_twelvelabs")
    
    if face_region and 'facial_area' in face_region:
        # Get API key from environment
        import os
        api_key = os.getenv('TWELVE_LABS_API_KEY')
        if not api_key:
            logger.error("TWELVE_LABS_API_KEY not found in environment")
            return generate_placeholder_embedding(face_region['facial_area'])
            
        return generate_face_embedding_twelvelabs(image_path, face_region['facial_area'], api_key)
    
    return generate_placeholder_embedding({})

def compare_embeddings(embedding1: np.ndarray, embedding2: np.ndarray) -> Tuple[float, bool]:
    """
    Compare two face embeddings using cosine similarity
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Tuple of (distance, is_match)
        - distance: Cosine distance (0 = identical, 2 = opposite)
        - is_match: True if distance < 0.6 (faces match)
    """
    try:
        # Cosine distance = 1 - cosine_similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        cosine_sim = dot_product / (norm1 * norm2)
        distance = 1.0 - cosine_sim
        
        # Threshold for match (lower = more similar)
        is_match = distance < 0.6
        
        logger.debug(f"Cosine distance: {distance:.4f}, Match: {is_match}")
        return float(distance), is_match
        
    except Exception as e:
        logger.error(f"❌ Embedding comparison failed: {e}")
        return 1.0, False


def find_matching_faces(query_embedding: np.ndarray, 
                       face_embeddings: List[Tuple[str, np.ndarray]],
                       threshold: float = 0.6,
                       top_k: int = 5) -> List[Tuple[str, float]]:
    """
    Find matching faces from a list of known face embeddings
    
    Args:
        query_embedding: The embedding to match against
        face_embeddings: List of (person_name, embedding) tuples
        threshold: Maximum distance to consider a match (default 0.6)
        top_k: Number of top matches to return
        
    Returns:
        List of (person_name, distance) tuples for top matches
    """
    try:
        matches = []
        
        for person_name, stored_embedding in face_embeddings:
            distance, is_match = compare_embeddings(query_embedding, stored_embedding)
            
            if distance < threshold:
                matches.append((person_name, distance))
        
        # Sort by distance (lowest first) and return top_k
        matches.sort(key=lambda x: x[1])
        return matches[:top_k]
        
    except Exception as e:
        logger.error(f"❌ Face matching failed: {e}")
        return []


def embedding_to_oracle_vector(embedding: np.ndarray):
    """
    Convert numpy embedding to Oracle VECTOR format
    
    Args:
        embedding: Numpy array of floats (512-dim)
        
    Returns:
        String representation of vector for Oracle VECTOR column
    """
    try:
        # Ensure 512 dimensions
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(f"Embedding must be {EMBEDDING_DIM}-dimensional, got {len(embedding)}")
        
        # Oracle VECTOR expects string representation: "[val1,val2,val3,...]"
        # Convert to float32 for consistency and format as string
        vector_list = embedding.astype(np.float32).tolist()
        vector_str = str(vector_list)
        
        return vector_str
        
    except Exception as e:
        logger.error(f"❌ Embedding to vector conversion failed: {e}")
        raise


def oracle_vector_to_embedding(vector_data) -> np.ndarray:
    """
    Convert Oracle VECTOR to numpy embedding
    
    Args:
        vector_data: Array or list from Oracle VECTOR column
        
    Returns:
        Numpy array of floats (512-dim)
    """
    try:
        # Oracle VECTOR returns as array/list
        if isinstance(vector_data, (list, tuple)):
            embedding = np.array(vector_data, dtype=np.float32)
        elif isinstance(vector_data, np.ndarray):
            embedding = vector_data.astype(np.float32)
        else:
            # If it's some other object, try to convert to array
            embedding = np.array(vector_data, dtype=np.float32)
        
        if len(embedding) != EMBEDDING_DIM:
            logger.warning(f"⚠️  Expected {EMBEDDING_DIM} dimensions, got {len(embedding)}")
        
        return embedding
        
    except Exception as e:
        logger.error(f"❌ Vector to embedding conversion failed: {e}")
        raise


def bbox_to_json(bbox: Dict) -> str:
    """Convert bounding box dict to JSON string"""
    return json.dumps(bbox)


def json_to_bbox(bbox_json: str) -> Dict:
    """Convert JSON string to bounding box dict"""
    return json.loads(bbox_json)


# OCI Integration for Face Crop Uploads
def _load_oci_config():
    """Load OCI configuration"""
    try:
        import oci
        
        # Check for OCI_CONFIG_PATH environment variable
        env_path = os.getenv('OCI_CONFIG_PATH')
        if env_path and os.path.exists(env_path):
            logger.info(f'Using OCI config from OCI_CONFIG_PATH: {env_path}')
            return oci.config.from_file(file_location=env_path)
        
        # Fallback to default OCI config
        logger.info('Using default OCI config')
        return oci.config.from_file()
    except Exception as e:
        logger.error(f"Failed to load OCI config: {e}")
        return None


def upload_face_crop_to_oci(face_crop_path: str):
    """Upload face crop to OCI and return presigned URL
    
    Args:
        face_crop_path: Path to face crop image file
        
    Returns:
        Tuple of (presigned_url, object_name) or (None, None) on error
    """
    try:
        import oci
        import datetime
        import uuid
        
        config = _load_oci_config()
        if not config:
            logger.error("Failed to load OCI config")
            return None, None
        
        object_storage = oci.object_storage.ObjectStorageClient(config)
        namespace = object_storage.get_namespace().data
        bucket_name = os.getenv('DEFAULT_OCI_BUCKET', 'Media')
        
        # Generate unique object name in temp folder
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
        
        logger.info(f"✅ Uploaded face crop to OCI: {object_name}")
        return par_url, object_name
        
    except Exception as e:
        logger.error(f"❌ OCI upload failed: {e}")
        return None, None


if __name__ == "__main__":
    # Test face detection
    print("Face Detection Helper - Test Mode")
    print("=" * 60)
    
    if not CV2_AVAILABLE:
        print("❌ OpenCV not available")
        print("Install with: pip install opencv-python")
        sys.exit(1)
    
    print(f"✅ Using OpenCV {cv2.__version__}")
    print(f"✅ Embedding dimension: {EMBEDDING_DIM}")
    print(f"✅ Face cascade: {FACE_CASCADE_PATH}")
    print("\nReady for face detection!")
    
    # Test with a sample if provided
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
        if os.path.exists(test_image):
            print(f"\nTesting with: {test_image}")
            faces = detect_faces_opencv(test_image)
            print(f"Found {len(faces)} faces:")
            for i, face in enumerate(faces):
                print(f"  Face {i+1}: {face['facial_area']}")
        else:
            print(f"❌ File not found: {test_image}")

