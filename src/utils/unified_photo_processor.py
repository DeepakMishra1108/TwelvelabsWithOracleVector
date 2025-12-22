"""
Unified Photo Processor
Orchestrates ImageBind, DeepFace, and GPT-4o-mini for complete photo analysis
"""

import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

class UnifiedPhotoProcessor:
    """
    Unified processor that runs 3 AI models in parallel:
    1. ImageBind: Visual embedding for similarity search
    2. DeepFace: Face detection and recognition
    3. GPT-4o-mini: Rich metadata extraction for natural language search
    """
    
    def __init__(self, db_connection=None):
        """Initialize the unified processor"""
        self.db_conn = db_connection
        logger.info("✅ Unified Photo Processor initialized")
    
    def process_photo(self, 
                     image_path: str, 
                     media_id: int,
                     album_name: str = None,
                     user_id: int = None) -> Dict:
        """
        Process a photo with all 3 AI models in parallel
        
        Args:
            image_path: Path to the image file
            media_id: Database ID of the media
            album_name: Album name for organization
            user_id: User ID for ownership
            
        Returns:
            Dict with results from all 3 models
        """
        logger.info(f"🔄 Processing photo: {image_path} (media_id={media_id})")
        
        results = {
            'media_id': media_id,
            'image_path': image_path,
            'album_name': album_name,
            'user_id': user_id,
            'imagebind_embedding': None,
            'faces': [],
            'rich_metadata': None,
            'errors': []
        }
        
        # Run 3 processes in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                'imagebind': executor.submit(self._process_imagebind, image_path),
                'deepface': executor.submit(self._process_deepface, image_path, media_id),
                'gpt_metadata': executor.submit(self._process_gpt_metadata, image_path)
            }
            
            # Collect results as they complete
            for task_name, future in futures.items():
                try:
                    result = future.result(timeout=60)  # 60s timeout per task
                    
                    if task_name == 'imagebind':
                        results['imagebind_embedding'] = result
                    elif task_name == 'deepface':
                        results['faces'] = result
                    elif task_name == 'gpt_metadata':
                        results['rich_metadata'] = result
                        
                    logger.info(f"   ✅ {task_name} completed")
                    
                except Exception as e:
                    logger.error(f"   ❌ {task_name} failed: {e}")
                    results['errors'].append({'task': task_name, 'error': str(e)})
        
        # Store results in database
        if self.db_conn:
            self._store_results(results)
        
        logger.info(f"✅ Photo processing complete: {len(results['faces'])} faces, metadata={results['rich_metadata'] is not None}")
        
        return results
    
    def _process_imagebind(self, image_path: str) -> Optional[list]:
        """
        Process image with ImageBind to create visual embedding
        Returns: 1024-dimensional embedding vector
        """
        try:
            from imagebind_embedding import create_embedding_from_image
            
            logger.info("   🎨 Creating ImageBind embedding...")
            embedding = create_embedding_from_image(image_path)
            
            if embedding is not None and len(embedding) == 1024:
                return embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
            else:
                raise ValueError(f"Invalid embedding dimension: {len(embedding) if embedding else 0}")
                
        except Exception as e:
            logger.error(f"ImageBind processing failed: {e}")
            raise
    
    def _process_deepface(self, image_path: str, media_id: int) -> list:
        """
        Process image with DeepFace to detect and recognize faces
        Returns: List of face detections with embeddings and bounding boxes
        """
        try:
            from deepface import DeepFace
            
            logger.info("   👤 Detecting faces with DeepFace...")
            
            # Detect faces
            faces = DeepFace.extract_faces(
                img_path=image_path,
                detector_backend='retinaface',
                enforce_detection=False,
                align=True
            )
            
            if not faces:
                logger.info("   No faces detected")
                return []
            
            # Get embeddings for each face
            face_results = []
            for idx, face_data in enumerate(faces):
                try:
                    # Generate embedding
                    embedding = DeepFace.represent(
                        img_path=image_path,
                        model_name='Facenet512',
                        detector_backend='retinaface',
                        enforce_detection=False
                    )
                    
                    if embedding and len(embedding) > 0:
                        face_results.append({
                            'media_id': media_id,
                            'face_index': idx,
                            'bounding_box': face_data.get('facial_area', {}),
                            'confidence': face_data.get('confidence', 0.0),
                            'embedding': embedding[0]['embedding'],
                            'face_name': 'Unknown'  # Will be matched against existing faces
                        })
                        
                except Exception as e:
                    logger.warning(f"   Failed to process face {idx}: {e}")
                    continue
            
            logger.info(f"   Found {len(face_results)} faces")
            return face_results
            
        except Exception as e:
            logger.error(f"DeepFace processing failed: {e}")
            raise
    
    def _process_gpt_metadata(self, image_path: str) -> Optional[Dict]:
        """
        Process image with GPT-4o-mini to extract rich metadata
        Returns: Structured metadata dict
        """
        try:
            from utils.gpt_vision_metadata import GPTVisionMetadataExtractor
            
            logger.info("   🤖 Extracting metadata with GPT-4o-mini...")
            
            extractor = GPTVisionMetadataExtractor()
            metadata = extractor.extract_metadata(image_path)
            
            return metadata
            
        except Exception as e:
            logger.error(f"GPT metadata extraction failed: {e}")
            raise
    
    def _store_results(self, results: Dict):
        """Store processing results in database"""
        try:
            cursor = self.db_conn.cursor()
            media_id = results['media_id']
            
            # 1. Update ImageBind embedding
            if results['imagebind_embedding']:
                try:
                    vector_json = json.dumps(results['imagebind_embedding'])
                    cursor.execute("""
                        UPDATE album_media 
                        SET embedding_vector = TO_VECTOR(:vector)
                        WHERE id = :media_id
                    """, {'vector': vector_json, 'media_id': media_id})
                    logger.info(f"   ✅ Stored ImageBind embedding")
                except Exception as e:
                    logger.error(f"   ❌ Failed to store ImageBind embedding: {e}")
            
            # 2. Store rich metadata
            if results['rich_metadata']:
                try:
                    metadata_json = json.dumps(results['rich_metadata'])
                    cursor.execute("""
                        UPDATE album_media 
                        SET rich_metadata = :metadata
                        WHERE id = :media_id
                    """, {'metadata': metadata_json, 'media_id': media_id})
                    logger.info(f"   ✅ Stored rich metadata")
                except Exception as e:
                    logger.error(f"   ❌ Failed to store rich metadata: {e}")
            
            # 3. Store face detections
            if results['faces']:
                try:
                    for face in results['faces']:
                        # Check if similar face exists (auto-tagging)
                        face_name = self._match_face_to_existing(face['embedding'], cursor)
                        face['face_name'] = face_name
                        
                        # Insert face tag
                        cursor.execute("""
                            INSERT INTO face_tags 
                            (media_id, bounding_box, confidence, face_embedding, face_name)
                            VALUES (:media_id, :bbox, :conf, TO_VECTOR(:embedding), :name)
                        """, {
                            'media_id': media_id,
                            'bbox': json.dumps(face['bounding_box']),
                            'conf': face['confidence'],
                            'embedding': json.dumps(face['embedding']),
                            'name': face['face_name']
                        })
                    
                    logger.info(f"   ✅ Stored {len(results['faces'])} face detections")
                except Exception as e:
                    logger.error(f"   ❌ Failed to store faces: {e}")
            
            self.db_conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to store results: {e}")
            self.db_conn.rollback()
            raise
    
    def _match_face_to_existing(self, face_embedding: list, cursor, threshold: float = 0.85) -> str:
        """
        Match detected face against existing tagged faces
        Returns: Face name if match found, otherwise 'Unknown'
        """
        try:
            embedding_json = json.dumps(face_embedding)
            
            # Find most similar existing face
            cursor.execute("""
                SELECT face_name, 
                       VECTOR_DISTANCE(face_embedding, TO_VECTOR(:embedding), COSINE) as distance
                FROM face_tags
                WHERE face_name != 'Unknown'
                AND face_embedding IS NOT NULL
                ORDER BY distance
                FETCH FIRST 1 ROWS ONLY
            """, {'embedding': embedding_json})
            
            result = cursor.fetchone()
            
            if result and result[1] < (1 - threshold):  # Convert similarity to distance
                logger.info(f"   🎯 Matched face to: {result[0]} (distance: {result[1]:.3f})")
                return result[0]
            else:
                return 'Unknown'
                
        except Exception as e:
            logger.warning(f"Face matching failed: {e}")
            return 'Unknown'


def process_photo_unified(image_path: str, media_id: int, db_connection=None, **kwargs):
    """Convenience function to process a single photo"""
    processor = UnifiedPhotoProcessor(db_connection)
    return processor.process_photo(image_path, media_id, **kwargs)


if __name__ == "__main__":
    # Test the unified processor
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 3:
        print("Usage: python unified_photo_processor.py <image_path> <media_id>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    media_id = int(sys.argv[2])
    
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    print(f"\n🔄 Processing photo: {image_path}\n")
    
    # Process without database connection (test mode)
    results = process_photo_unified(image_path, media_id, db_connection=None)
    
    print("\n" + "="*60)
    print("📊 Processing Results:")
    print("="*60)
    print(f"✅ ImageBind embedding: {len(results['imagebind_embedding'])} dimensions" if results['imagebind_embedding'] else "❌ ImageBind: Failed")
    print(f"✅ Faces detected: {len(results['faces'])}")
    print(f"✅ Metadata extracted: {results['rich_metadata'] is not None}")
    print(f"❌ Errors: {len(results['errors'])}")
    
    if results['errors']:
        for error in results['errors']:
            print(f"   - {error['task']}: {error['error']}")
    
    if results['rich_metadata']:
        print("\n📝 Metadata Tags:", ", ".join(results['rich_metadata'].get('tags', [])))
    
    print("\n")
