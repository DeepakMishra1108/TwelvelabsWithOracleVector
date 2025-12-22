#!/usr/bin/env python3
"""
ImageBind Helper - Free, self-hosted embeddings for images and videos
Replaces TwelveLabs with Meta's ImageBind (no rate limits, no API costs)
"""

import os
import logging
import tempfile
import torch
import numpy as np
from pathlib import Path
from typing import Union, Optional
from PIL import Image

# Import ImageBind
try:
    from imagebind import data
    from imagebind.models import imagebind_model
    from imagebind.models.imagebind_model import ModalityType
    IMAGEBIND_AVAILABLE = True
except ImportError:
    IMAGEBIND_AVAILABLE = False
    logging.warning("ImageBind not available - pip install git+https://github.com/facebookresearch/ImageBind.git")

logger = logging.getLogger(__name__)

class ImageBindEmbedder:
    """Singleton class for ImageBind embeddings generation"""
    
    _instance = None
    _model = None
    _device = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageBindEmbedder, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not IMAGEBIND_AVAILABLE:
            raise ImportError("ImageBind not installed")
        
        if self._model is None:
            self._initialize_model()
    
    def _initialize_model(self):
        """Initialize ImageBind model (one-time setup)"""
        try:
            logger.info("🚀 Initializing ImageBind model...")
            
            # Set torch hub directory to use the correct cache location
            cache_dir = os.path.expanduser('~/.cache/torch/hub')
            torch.hub.set_dir(cache_dir)
            
            # Change to cache directory so ImageBind can create .checkpoints there
            original_dir = os.getcwd()
            os.makedirs(cache_dir, exist_ok=True)
            os.chdir(cache_dir)
            
            try:
                # Use CPU for now (can enable GPU if available)
                self._device = "cuda:0" if torch.cuda.is_available() else "cpu"
                
                # Load model (it will use the pre-downloaded weights)
                self._model = imagebind_model.imagebind_huge(pretrained=True)
                self._model.eval()
                self._model.to(self._device)
            finally:
                # Try to change back, but don't fail if we can't
                try:
                    os.chdir(original_dir)
                except:
                    pass  # Stay in cache dir if we can't go back
            
            logger.info(f"✅ ImageBind model loaded on {self._device}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize ImageBind: {e}")
            raise
    
    def generate_image_embedding(self, image_path: str) -> Optional[np.ndarray]:
        """
        Generate embedding for an image
        
        Args:
            image_path: Path to image file or URL
            
        Returns:
            1024-dimensional numpy array (normalized)
        """
        try:
            # Load and transform image
            inputs = {
                ModalityType.VISION: data.load_and_transform_vision_data([image_path], self._device)
            }
            
            # Generate embedding
            with torch.no_grad():
                embeddings = self._model(inputs)
            
            # Extract vision embedding
            embedding = embeddings[ModalityType.VISION].cpu().numpy()[0]
            
            # Normalize
            embedding = embedding / np.linalg.norm(embedding)
            
            logger.info(f"✅ Generated image embedding: {len(embedding)}-dim")
            return embedding
            
        except Exception as e:
            logger.error(f"❌ Image embedding failed: {e}")
            return None
    
    def generate_face_embedding(self, image_path: str, bbox: dict) -> Optional[np.ndarray]:
        """
        Generate embedding for a face crop
        
        Args:
            image_path: Path to full image
            bbox: Bounding box dict with x, y, w, h
            
        Returns:
            1024-dimensional numpy array (normalized)
        """
        try:
            # Load image and crop face
            img = Image.open(image_path)
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            
            # Add padding (20%)
            padding = 0.2
            x_pad = int(w * padding)
            y_pad = int(h * padding)
            
            left = max(0, x - x_pad)
            top = max(0, y - y_pad)
            right = min(img.width, x + w + x_pad)
            bottom = min(img.height, y + h + y_pad)
            
            face_crop = img.crop((left, top, right, bottom))
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                face_crop.save(temp_file.name, 'JPEG', quality=95)
                temp_path = temp_file.name
            
            # Generate embedding
            embedding = self.generate_image_embedding(temp_path)
            
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            
            return embedding
            
        except Exception as e:
            logger.error(f"❌ Face embedding failed: {e}")
            return None
    
    def generate_video_embedding(self, video_path: str, start_time: Optional[float] = None, 
                                end_time: Optional[float] = None) -> Optional[np.ndarray]:
        """
        Generate embedding for a video or video segment
        
        Args:
            video_path: Path to video file
            start_time: Start time in seconds (optional)
            end_time: End time in seconds (optional)
            
        Returns:
            1024-dimensional numpy array (normalized)
        """
        try:
            # For now, use full video (ImageBind handles video clips internally)
            # TODO: Add segment extraction if needed
            
            # Load and transform video
            inputs = {
                ModalityType.VISION: data.load_and_transform_video_data([video_path], self._device)
            }
            
            # Generate embedding
            with torch.no_grad():
                embeddings = self._model(inputs)
            
            # Extract vision embedding
            embedding = embeddings[ModalityType.VISION].cpu().numpy()[0]
            
            # Normalize
            embedding = embedding / np.linalg.norm(embedding)
            
            logger.info(f"✅ Generated video embedding: {len(embedding)}-dim")
            return embedding
            
        except Exception as e:
            logger.error(f"❌ Video embedding failed: {e}")
            return None
    
    def generate_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate embedding for text (for text-to-image/video search)
        
        Args:
            text: Query text
            
        Returns:
            1024-dimensional numpy array (normalized)
        """
        try:
            # Load and transform text
            inputs = {
                ModalityType.TEXT: data.load_and_transform_text([text], self._device)
            }
            
            # Generate embedding
            with torch.no_grad():
                embeddings = self._model(inputs)
            
            # Extract text embedding
            embedding = embeddings[ModalityType.TEXT].cpu().numpy()[0]
            
            # Normalize
            embedding = embedding / np.linalg.norm(embedding)
            
            logger.info(f"✅ Generated text embedding: {len(embedding)}-dim")
            return embedding
            
        except Exception as e:
            logger.error(f"❌ Text embedding failed: {e}")
            return None


# Global singleton instance
_embedder = None

def get_imagebind_embedder() -> ImageBindEmbedder:
    """Get or create ImageBind embedder singleton"""
    global _embedder
    if _embedder is None:
        _embedder = ImageBindEmbedder()
    return _embedder


def embedding_to_oracle_vector(embedding: np.ndarray) -> str:
    """Convert numpy array to Oracle VECTOR format string"""
    return '[' + ','.join(str(float(x)) for x in embedding) + ']'
