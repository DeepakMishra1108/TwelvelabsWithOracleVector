#!/usr/bin/env python3
"""
Test TwelveLabs Face Embedding Generation
Verify that we can generate 1024-dim embeddings for face crops
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
import tempfile
import numpy as np
from PIL import Image, ImageDraw

# Add src to path
current_dir = Path(__file__).parent
src_dir = current_dir.parent / 'src'
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from utils.face_detection_helper import (
    generate_face_embedding_twelvelabs,
    detect_faces_deepface
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_image_with_face():
    """Create a simple test image with a fake face region"""
    # Create a 400x400 white image
    img = Image.new('RGB', (400, 400), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw a simple "face" - circle for head, rectangles for eyes
    # Head
    draw.ellipse([150, 100, 250, 200], fill='peachpuff', outline='black')
    # Eyes
    draw.rectangle([170, 130, 180, 140], fill='black')
    draw.rectangle([220, 130, 230, 140], fill='black')
    # Mouth
    draw.arc([180, 160, 220, 180], 0, 180, fill='black', width=2)
    
    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
    img.save(temp_file.name, 'JPEG')
    temp_file.close()
    
    logger.info(f"✅ Created test image: {temp_file.name}")
    
    # Face bbox for the drawn face
    face_bbox = {'x': 150, 'y': 100, 'w': 100, 'h': 100}
    
    return temp_file.name, face_bbox

def test_twelvelabs_embedding():
    """Test TwelveLabs face embedding generation"""
    logger.info("=" * 80)
    logger.info("🧪 Testing TwelveLabs Face Embedding Generation")
    logger.info("=" * 80)
    
    # Load environment
    env_path = current_dir.parent / 'twelvelabvideoai' / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"✅ Loaded environment from: {env_path}")
    else:
        logger.error("❌ .env file not found")
        return False
    
    api_key = os.getenv('TWELVE_LABS_API_KEY')
    if not api_key:
        logger.error("❌ TWELVE_LABS_API_KEY not found")
        return False
    
    logger.info(f"✅ API Key: {api_key[:10]}...")
    
    # Create test image
    logger.info("\n📸 Creating test image with face...")
    image_path, face_bbox = create_test_image_with_face()
    
    # Generate embedding
    logger.info(f"\n🎯 Generating TwelveLabs embedding for face crop...")
    logger.info(f"   Face bbox: {face_bbox}")
    
    embedding = generate_face_embedding_twelvelabs(image_path, face_bbox, api_key)
    
    if embedding is None:
        logger.error("❌ Embedding generation failed")
        os.unlink(image_path)
        return False
    
    # Check embedding
    logger.info(f"\n✅ Embedding generated successfully!")
    logger.info(f"   Dimensions: {len(embedding)}")
    logger.info(f"   Type: {type(embedding)}")
    logger.info(f"   Min: {np.min(embedding):.4f}")
    logger.info(f"   Max: {np.max(embedding):.4f}")
    logger.info(f"   Mean: {np.mean(embedding):.4f}")
    logger.info(f"   Norm: {np.linalg.norm(embedding):.4f}")
    
    # Cleanup
    os.unlink(image_path)
    
    # Verify dimensions
    if len(embedding) != 1024:
        logger.error(f"❌ Expected 1024 dimensions, got {len(embedding)}")
        return False
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Test PASSED - TwelveLabs face embeddings working!")
    logger.info("=" * 80)
    return True

if __name__ == '__main__':
    success = test_twelvelabs_embedding()
    sys.exit(0 if success else 1)
