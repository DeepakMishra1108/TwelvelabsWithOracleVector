"""
Selfie-Based Photo Search
Allows users to upload a selfie and find all photos containing that person
"""

import logging
import tempfile
import os
from typing import Dict, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

def search_photos_by_selfie(
    selfie_image_path: str,
    connection,
    similarity_threshold: float = 0.6,
    max_results: int = 100
) -> Dict:
    """
    Search for all photos containing the person in the selfie
    
    Args:
        selfie_image_path: Path to the uploaded selfie image
        connection: Database connection
        similarity_threshold: Maximum distance for a match (lower = more similar)
        max_results: Maximum number of photos to return
        
    Returns:
        Dict with search results and statistics
    """
    try:
        from utils.face_detection_helper import (
            detect_faces_deepface,
            embedding_to_oracle_vector
        )
        from utils.imagebind_helper import ImageBindEmbedder
        import json
        
        logger.info(f"🔍 Starting selfie-based search using ImageBind...")
        
        # Step 1: Detect face in selfie
        faces = detect_faces_deepface(selfie_image_path)
        
        if not faces or len(faces) == 0:
            logger.warning("⚠️  No face detected in selfie")
            return {
                'success': False,
                'error': 'No face detected in the selfie. Please upload a clear photo of your face.',
                'faces_detected': 0,
                'matches_found': 0,
                'photos': []
            }
        
        if len(faces) > 1:
            logger.warning(f"⚠️  Multiple faces detected ({len(faces)}), using the largest one")
        
        # Use the first/largest face
        face = faces[0]
        face_bbox = face.get('facial_area', {})
        
        logger.info(f"✅ Detected face in selfie: {face_bbox}")
        
        # Step 2: Generate embedding for the selfie face using ImageBind (1024D)
        try:
            embedder = ImageBindEmbedder()
            selfie_embedding = embedder.generate_face_embedding(selfie_image_path, face_bbox)
            
            if selfie_embedding is None:
                raise Exception("ImageBind returned None embedding")
            
            logger.info(f"✅ Generated ImageBind embedding for selfie (dimension: {len(selfie_embedding)})")
        except Exception as e:
            logger.error(f"❌ ImageBind embedding failed: {e}")
            return {
                'success': False,
                'error': 'Failed to process the face in your selfie',
                'faces_detected': 1,
                'matches_found': 0,
                'photos': []
            }
        
        # Step 3: Convert embedding to Oracle VECTOR format
        vector_bytes = embedding_to_oracle_vector(selfie_embedding)
        
        # Step 4: Search for similar faces in the database using vector similarity
        cursor = connection.cursor()
        
        # First, check how many face tags exist with embeddings
        cursor.execute("SELECT COUNT(*) FROM face_tags WHERE face_embedding IS NOT NULL")
        total_tags = cursor.fetchone()[0]
        logger.info(f"📊 Total face tags with embeddings in database: {total_tags}")
        
        # Check a sample of distances to see what range we're getting
        logger.info(f"🔍 Searching for faces with similarity threshold {similarity_threshold}...")
        cursor.execute("""
            SELECT 
                ft.face_name,
                VECTOR_DISTANCE(ft.face_embedding, :query_embedding, COSINE) as distance
            FROM face_tags ft
            WHERE ft.face_embedding IS NOT NULL
            ORDER BY distance ASC
            FETCH FIRST 10 ROWS ONLY
        """, {'query_embedding': vector_bytes})
        
        sample_distances = cursor.fetchall()
        logger.info(f"📏 Top 10 closest faces:")
        for name, dist in sample_distances:
            logger.info(f"   {name}: distance={dist:.4f} (threshold={similarity_threshold})")
        
        # Now do the actual search
        cursor.execute("""
            SELECT 
                ft.id as face_tag_id,
                ft.media_id,
                ft.face_name,
                ft.bounding_box,
                VECTOR_DISTANCE(ft.face_embedding, :query_embedding, COSINE) as distance,
                am.file_name,
                am.file_path,
                am.oci_object_path,
                am.created_at,
                am.file_type
            FROM face_tags ft
            JOIN album_media am ON ft.media_id = am.id
            WHERE ft.face_embedding IS NOT NULL
            AND VECTOR_DISTANCE(ft.face_embedding, :query_embedding, COSINE) < :threshold
            ORDER BY distance ASC
            FETCH FIRST :max_results ROWS ONLY
        """, {
            'query_embedding': vector_bytes,
            'threshold': similarity_threshold,
            'max_results': max_results
        })
        
        matches = cursor.fetchall()
        
        logger.info(f"✅ Found {len(matches)} matching face tags (threshold < {similarity_threshold})")
        
        if len(matches) == 0:
            return {
                'success': True,
                'message': f'No faces found within distance {similarity_threshold}. Closest match was {sample_distances[0][1]:.4f} for {sample_distances[0][0]}. Try increasing the Match Sensitivity slider.',
                'faces_detected': 1,
                'matches_found': 0,
                'photos': []
            }
        
        # Step 5: Group results by photo (media_id) and aggregate face matches
        photos_dict = {}
        
        for row in matches:
            face_tag_id, media_id, face_name, bbox_json, distance, file_name, file_path, oci_object_path, created_at, file_type = row
            
            if media_id not in photos_dict:
                # Generate URLs from file paths
                # Use OCI object path if available, otherwise file_path
                object_path = oci_object_path if oci_object_path else file_path
                stream_url = f"/media_stream/{media_id}" if object_path else None
                thumbnail_url = f"/media_thumbnail/{media_id}" if object_path else None
                
                photos_dict[media_id] = {
                    'media_id': media_id,
                    'file_name': file_name,
                    'thumbnail_url': thumbnail_url,
                    'stream_url': stream_url,
                    'created_at': created_at.isoformat() if created_at else None,
                    'file_type': file_type,
                    'matched_faces': [],
                    'best_match_distance': distance,
                    'match_count': 0
                }
            
            # Parse bounding box
            try:
                bbox = json.loads(bbox_json.read()) if hasattr(bbox_json, 'read') else json.loads(bbox_json)
            except:
                bbox = None
            
            photos_dict[media_id]['matched_faces'].append({
                'face_tag_id': face_tag_id,
                'face_name': face_name,
                'distance': float(distance),
                'confidence': 1.0 - float(distance),
                'bounding_box': bbox
            })
            photos_dict[media_id]['match_count'] += 1
            
            # Update best match distance (lowest)
            if distance < photos_dict[media_id]['best_match_distance']:
                photos_dict[media_id]['best_match_distance'] = distance
        
        # Convert to list and sort by best match
        photos_list = sorted(
            photos_dict.values(),
            key=lambda x: x['best_match_distance']
        )
        
        logger.info(f"✅ Selfie search complete: {len(photos_list)} unique photos with {len(matches)} face matches")
        
        return {
            'success': True,
            'message': f'Found {len(photos_list)} photos containing similar faces',
            'faces_detected': 1,
            'matches_found': len(matches),
            'unique_photos': len(photos_list),
            'similarity_threshold': similarity_threshold,
            'photos': photos_list
        }
        
    except Exception as e:
        logger.error(f"❌ Selfie search failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            'success': False,
            'error': str(e),
            'faces_detected': 0,
            'matches_found': 0,
            'photos': []
        }


def cleanup_temp_file(file_path: str):
    """Safely delete temporary file"""
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug(f"🗑️  Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to cleanup temp file {file_path}: {e}")


if __name__ == "__main__":
    print("Selfie-Based Photo Search Module")
    print("=" * 60)
    print("Upload a selfie and find all photos containing that person")
