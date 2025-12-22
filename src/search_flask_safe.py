#!/usr/bin/env python3
"""Flask-safe vector search using ImageBind embeddings and Oracle VECTOR"""
import os
import sys
import array
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'twelvelabvideoai', 'src'))

from utils.db_utils_flask_safe import flask_safe_execute_query

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_photos_flask_safe(query_text: str, album_name: str = None, top_k: int = 10, min_similarity: float = 0.30) -> List[Dict]:
    """Search photos using ImageBind embedding and Oracle VECTOR similarity
    
    Args:
        query_text: Natural language search query
        album_name: Optional album filter
        top_k: Number of results to return
        min_similarity: Minimum similarity threshold (0.0-1.0). Default 0.30 (30%)
        
    Returns:
        List of photo results with similarity scores above threshold
    """
    try:
        # Get ImageBind embedding for the query (free, instant)
        from utils.imagebind_helper import get_imagebind_embedder
        import json
        
        embedder = get_imagebind_embedder()
        query_embedding = embedder.generate_text_embedding(query_text)
        
        if query_embedding is None:
            logger.error("❌ Failed to generate text embedding")
            return []
        
        # Convert to Oracle VECTOR format (as a string for SQL)
        query_vector_list = query_embedding.tolist()
        logger.info(f"✅ Query vector has {len(query_vector_list)} dimensions")
        
        # Convert vector to JSON string for Oracle TO_VECTOR function
        vector_json = json.dumps(query_vector_list)
        
        # Build SQL query with VECTOR similarity
        if album_name:
            sql = """
            SELECT 
                id,
                album_name,
                file_name,
                file_path,
                file_type,
                created_at,
                VECTOR_DISTANCE(embedding_vector, TO_VECTOR(:query_vector), COSINE) as distance
            FROM album_media
            WHERE file_type = 'photo'
            AND album_name = :album_name
            AND embedding_vector IS NOT NULL
            ORDER BY distance
            FETCH FIRST :top_k ROWS ONLY
            """
            # Pass as JSON string instead of array.array
            params = {
                'query_vector': vector_json,
                'album_name': album_name,
                'top_k': top_k
            }
        else:
            sql = """
            SELECT 
                id,
                album_name,
                file_name,
                file_path,
                file_type,
                created_at,
                VECTOR_DISTANCE(embedding_vector, TO_VECTOR(:query_vector), COSINE) as distance
            FROM album_media
            WHERE file_type = 'photo'
            AND embedding_vector IS NOT NULL
            ORDER BY distance
            FETCH FIRST :top_k ROWS ONLY
            """
            params = {
                'query_vector': vector_json,
                'top_k': top_k
            }
        
        # Execute query
        results = flask_safe_execute_query(sql, params)
        
        # Format results
        photo_results = []
        for row in results:
            distance = row[6]
            similarity = 1.0 - distance  # Convert distance to similarity
            
            # Filter by minimum similarity threshold
            if similarity < min_similarity:
                continue
            
            photo_results.append({
                'media_id': row[0],
                'album_name': row[1],
                'file_name': row[2],
                'file_path': row[3],
                'file_type': row[4],
                'created_at': row[5],
                'similarity': similarity,
                'score': similarity
            })
        
        logger.info(f"✅ Found {len(photo_results)} photo results for query: '{query_text}' (threshold: {min_similarity*100:.0f}%)")
        return photo_results
        
    except Exception as e:
        logger.error(f"❌ Photo search failed: {e}")
        return []
