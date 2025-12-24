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
        
        # Step 1: Detect ALL faces in selfie
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
        
        logger.info(f"✅ Detected {len(faces)} face(s) in selfie")
        
        # Store embeddings for ALL detected faces
        face_embeddings = []
        for i, face in enumerate(faces):
            face_bbox = face.get('facial_area', {})
            logger.info(f"   Face {i+1}: {face_bbox}")
            
            try:
                embedder = ImageBindEmbedder()
                embedding = embedder.generate_face_embedding(selfie_image_path, face_bbox)
                
                if embedding is not None:
                    face_embeddings.append(embedding)
                    logger.info(f"✅ Generated ImageBind embedding for face {i+1} (dimension: {len(embedding)})")
                else:
                    logger.warning(f"⚠️  Failed to generate embedding for face {i+1}")
            except Exception as e:
                logger.error(f"❌ ImageBind embedding failed for face {i+1}: {e}")
        
        if len(face_embeddings) == 0:
            return {
                'success': False,
                'error': 'Failed to process faces in your selfie',
                'faces_detected': len(faces),
                'matches_found': 0,
                'photos': []
            }
        
        logger.info(f"✅ Successfully generated {len(face_embeddings)} face embeddings")
        
        # Step 3: Search for each face embedding separately and combine results
        cursor = connection.cursor()
        all_matches = []
        photos_dict = {}
        selfie_face_names = []  # Track identified names from selfie
        
        for face_idx, selfie_embedding in enumerate(face_embeddings):
            logger.info(f"🔍 Searching for matches for face {face_idx + 1}/{len(face_embeddings)}...")
            
            # Convert embedding to Oracle VECTOR format
            vector_bytes = embedding_to_oracle_vector(selfie_embedding)
            
            # Check sample distances for this face to identify who is in the selfie
            cursor.execute("""
                SELECT 
                    ft.face_name,
                    VECTOR_DISTANCE(ft.face_embedding, :query_embedding, COSINE) as distance
                FROM face_tags ft
                WHERE ft.face_embedding IS NOT NULL
                AND ft.face_name IS NOT NULL
                AND LOWER(ft.face_name) != 'unknown'
                ORDER BY distance ASC
                FETCH FIRST 1 ROW ONLY
            """, {'query_embedding': vector_bytes})
            
            top_match = cursor.fetchone()
            if top_match and top_match[1] < similarity_threshold:
                selfie_face_names.append(top_match[0])
                logger.info(f"✅ Identified face {face_idx + 1} as: {top_match[0]} (distance={top_match[1]:.4f})")
            else:
                logger.info(f"⚠️  Face {face_idx + 1} not identified (no close match)")
            
            # Execute search for this face
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
            
            face_matches = cursor.fetchall()
            logger.info(f"✅ Found {len(face_matches)} matches for face {face_idx + 1}")
            
            # Combine results from all faces
            for row in face_matches:
                face_tag_id, media_id, face_name, bbox_json, distance, file_name, file_path, oci_object_path, created_at, file_type = row
                
                if media_id not in photos_dict:
                    # Generate URLs from file paths
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
                        'match_count': 0,
                        'selfie_faces_matched': set()  # Track which selfie faces matched this photo
                    }
                
                # Parse bounding box
                try:
                    bbox = json.loads(bbox_json.read()) if hasattr(bbox_json, 'read') else json.loads(bbox_json)
                except:
                    bbox = None
                
                # Check if this exact face is already in matched_faces (avoid duplicates across multiple selfie faces)
                face_already_matched = any(
                    mf['face_tag_id'] == face_tag_id 
                    for mf in photos_dict[media_id]['matched_faces']
                )
                
                if not face_already_matched:
                    photos_dict[media_id]['matched_faces'].append({
                        'face_tag_id': face_tag_id,
                        'face_name': face_name,
                        'distance': float(distance),
                        'confidence': 1.0 - float(distance),
                        'bounding_box': bbox,
                        'selfie_face_index': face_idx  # Track which selfie face this matched
                    })
                    photos_dict[media_id]['match_count'] += 1
                    photos_dict[media_id]['selfie_faces_matched'].add(face_idx)  # Track unique selfie faces
                    
                    # Update best match distance (lowest)
                    if distance < photos_dict[media_id]['best_match_distance']:
                        photos_dict[media_id]['best_match_distance'] = distance
        
        # Convert set to count and sort by: 1) number of selfie faces matched (descending), 2) best distance (ascending)
        for photo in photos_dict.values():
            photo['selfie_faces_matched_count'] = len(photo['selfie_faces_matched'])
            del photo['selfie_faces_matched']  # Remove set (not JSON serializable)
        
        photos_list = sorted(
            photos_dict.values(),
            key=lambda x: (-x['selfie_faces_matched_count'], x['best_match_distance'])
        )
        
        total_matches = sum(p['match_count'] for p in photos_list)
        
        # Calculate statistics for better UI organization
        all_faces_photos = [p for p in photos_list if p['selfie_faces_matched_count'] == len(face_embeddings)]
        partial_match_photos = [p for p in photos_list if 0 < p['selfie_faces_matched_count'] < len(face_embeddings)]
        
        logger.info(f"✅ Selfie search complete: {len(face_embeddings)} faces searched")
        logger.info(f"   Found {len(photos_list)} unique photos with {total_matches} total face matches")
        logger.info(f"   All faces: {len(all_faces_photos)}, Partial matches: {len(partial_match_photos)}")
        
        if len(photos_list) == 0:
            return {
                'success': True,
                'message': f'No faces found within distance {similarity_threshold}. Try increasing the Match Sensitivity slider.',
                'faces_detected': len(faces),
                'matches_found': 0,
                'photos': []
            }
        
        return {
            'success': True,
            'message': f'Found {len(photos_list)} photos containing similar faces',
            'faces_detected': len(faces),
            'selfie_face_names': selfie_face_names,  # Names identified in the selfie
            'matches_found': total_matches,
            'unique_photos': len(photos_list),
            'all_faces_photos': len(all_faces_photos),
            'partial_match_photos': len(partial_match_photos),
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
