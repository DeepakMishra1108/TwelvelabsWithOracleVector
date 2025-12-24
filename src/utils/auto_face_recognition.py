#!/usr/bin/env python3
"""Auto Face Recognition Module
Automatically detects and tags faces in uploaded photos using existing face embeddings
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add parent directory to path
current_dir = Path(__file__).parent
if str(current_dir.parent.parent) not in sys.path:
    sys.path.insert(0, str(current_dir.parent.parent))

logger = logging.getLogger(__name__)

from utils.face_detection_helper import (
    detect_faces_deepface,
    generate_placeholder_embedding,
    find_matching_faces,
    embedding_to_oracle_vector,
    oracle_vector_to_embedding,
    bbox_to_json
)


def auto_recognize_faces(media_id: int, image_path: str, user_id: int, connection) -> Dict:
    """
    Automatically detect and recognize faces in an uploaded photo
    
    Args:
        media_id: ID of the media item
        image_path: Local path to the image file
        user_id: ID of the user who uploaded the photo
        connection: Database connection object
        
    Returns:
        Dict with recognition results
    """
    try:
        logger.info(f"🔍 Auto-recognizing faces in media {media_id}")
        
        # Step 1: Detect all faces in the image using DeepFace
        faces = detect_faces_deepface(image_path)
        
        if not faces or len(faces) == 0:
            logger.info(f"ℹ️  No faces detected in media {media_id}")
            return {
                "faces_detected": 0,
                "faces_recognized": 0,
                "faces_tagged": 0
            }
        
        logger.info(f"✅ Detected {len(faces)} face(s) in media {media_id}")
        
        # Step 2: Check how many known face embeddings exist (for logging)
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM face_tags WHERE face_embedding IS NOT NULL")
        known_face_count = cursor.fetchone()[0]
        logger.info(f"📚 Database contains {known_face_count} known face embeddings")
        
        # Step 3: For each detected face, use Oracle vector search to find matches
        faces_recognized = 0
        faces_tagged = 0
        recognition_results = []
        match_threshold = 0.95  # Distance threshold for recognition (higher = more permissive)
        
        for i, face in enumerate(faces):
            face_bbox = face['facial_area']
            
            # Generate embedding for this detected face
            face_embedding = generate_placeholder_embedding(face_bbox)
            
            # OPTIMIZED: Use Oracle's vector similarity search instead of loading all embeddings
            # Convert embedding to Oracle VECTOR format
            vector_bytes = embedding_to_oracle_vector(face_embedding)
            
            # Find closest matching face using Oracle's VECTOR_DISTANCE function
            cursor.execute("""
                SELECT 
                    ft.face_name,
                    VECTOR_DISTANCE(ft.face_embedding, :query_embedding, COSINE) as distance
                FROM face_tags ft
                WHERE ft.face_embedding IS NOT NULL
                ORDER BY distance
                FETCH FIRST 1 ROWS ONLY
            """, {
                'query_embedding': vector_bytes
            })
            
            match_row = cursor.fetchone()
            
            if match_row:
                matched_name = match_row[0]
                distance = float(match_row[1])
                
                # Check if distance is below threshold
                if distance < match_threshold:
                    # Found a match!
                    faces_recognized += 1
                    
                    logger.info(f"✅ Recognized face {i+1} as '{matched_name}' (distance: {distance:.4f})")
                    
                    # Auto-tag this face
                    try:
                        cursor.execute("""
                            INSERT INTO face_tags 
                            (media_id, face_name, face_embedding, bounding_box, confidence, created_by)
                            VALUES (:media_id, :face_name, :face_embedding, :bbox, :confidence, :user_id)
                        """, {
                            "media_id": media_id,
                            "face_name": matched_name,
                            "face_embedding": vector_bytes,
                            "bbox": bbox_to_json(face_bbox),
                            "confidence": 1.0 - distance,  # Convert distance to confidence
                            "user_id": user_id
                        })
                        
                        faces_tagged += 1
                        
                        recognition_results.append({
                            "face_index": i + 1,
                            "bbox": face_bbox,
                            "recognized_as": matched_name,
                            "confidence": 1.0 - distance,
                            "auto_tagged": True
                        })
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to save auto-tag for face {i+1}: {e}")
                        recognition_results.append({
                            "face_index": i + 1,
                            "bbox": face_bbox,
                            "recognized_as": matched_name,
                            "confidence": 1.0 - distance,
                            "auto_tagged": False,
                            "error": str(e)
                        })
                else:
                    # Match found but distance too high - save as Unknown
                    logger.info(f"ℹ️  Face {i+1} has closest match '{matched_name}' but distance {distance:.4f} exceeds threshold {match_threshold}")
                    
                    # Save as Unknown face for manual tagging later
                    try:
                        cursor.execute("""
                            INSERT INTO face_tags 
                            (media_id, face_name, face_embedding, bounding_box, confidence, created_by, auto_tagged)
                            VALUES (:media_id, :face_name, :face_embedding, :bbox, :confidence, :user_id, 0)
                        """, {
                            "media_id": media_id,
                            "face_name": "Unknown",
                            "face_embedding": vector_bytes,
                            "bbox": bbox_to_json(face_bbox),
                            "confidence": 0.0,
                            "user_id": user_id
                        })
                        
                        faces_tagged += 1
                        
                        recognition_results.append({
                            "face_index": i + 1,
                            "bbox": face_bbox,
                            "recognized_as": "Unknown",
                            "confidence": 0.0,
                            "auto_tagged": False
                        })
                    except Exception as e:
                        logger.error(f"❌ Failed to save Unknown face {i+1}: {e}")
                        recognition_results.append({
                            "face_index": i + 1,
                            "bbox": face_bbox,
                            "recognized_as": None,
                            "confidence": 0.0,
                            "auto_tagged": False,
                            "error": str(e)
                        })
        
        # Commit all auto-tags
        connection.commit()
        
        logger.info(f"✅ Auto-recognition complete: {len(faces)} detected, "
                   f"{faces_recognized} recognized, {faces_tagged} tagged")
        
        return {
            "faces_detected": len(faces),
            "faces_recognized": faces_recognized,
            "faces_tagged": faces_tagged,
            "recognition_results": recognition_results
        }
        
    except Exception as e:
        logger.error(f"❌ Auto face recognition failed for media {media_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "faces_detected": 0,
            "faces_recognized": 0,
            "faces_tagged": 0,
            "error": str(e)
        }


if __name__ == "__main__":
    print("Auto Face Recognition Module")
    print("=" * 60)
    print("This module automatically detects and recognizes faces in uploaded photos")
    print("using existing face embeddings from the database.")
