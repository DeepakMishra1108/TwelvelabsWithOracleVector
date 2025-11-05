#!/usr/bin/env python3
"""Flask-safe vector search using TwelveLabs embeddings and Oracle VECTOR"""
import os
import sys
import array
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'twelvelabvideoai', 'src'))

from utils.db_utils_flask_safe import flask_safe_execute_query

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_photos_flask_safe(query_text: str, album_name: str = None, top_k: int = 10, min_similarity: float = 0.30) -> List[Dict]:
    """Search photos using TwelveLabs embedding and Oracle VECTOR similarity
    
    Args:
        query_text: Natural language search query
        album_name: Optional album filter
        top_k: Number of results to return
        min_similarity: Minimum similarity threshold (0.0-1.0). Default 0.30 (30%)
        
    Returns:
        List of photo results with similarity scores above threshold
    """
    try:
        # Get TwelveLabs embedding for the query
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        task = client.embed.create(
            model_name="Marengo-retrieval-2.7",
            text=query_text
        )
        
        # Wait for embedding
        task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
        if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
            client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
            final = client.embed.tasks.retrieve(task_id=task_id)
        elif hasattr(task, 'wait_for_done'):
            task.wait_for_done(sleep_interval=2)
            final = task
        else:
            final = task
        
        # Extract embedding
        query_embedding = None
        
        # Debug: log the final object structure
        logger.info(f"Task result type: {type(final)}")
        
        if hasattr(final, 'text_embedding'):
            text_emb = final.text_embedding
            logger.info(f"text_embedding type: {type(text_emb)}")
            
            # TextEmbeddingResult has 'segments' which is a list of embeddings
            if hasattr(text_emb, 'segments') and text_emb.segments:
                logger.info(f"Found {len(text_emb.segments)} segments")
                # Take the first segment's embedding
                first_segment = text_emb.segments[0]
                logger.info(f"First segment type: {type(first_segment)}")
                logger.info(f"First segment attributes: {dir(first_segment)}")
                
                # Segment should have 'embedding_scope' and 'embeddings_float' or similar
                if hasattr(first_segment, 'embeddings_float'):
                    query_embedding = first_segment.embeddings_float
                elif hasattr(first_segment, 'embedding'):
                    query_embedding = first_segment.embedding
                elif hasattr(first_segment, 'float_'):
                    query_embedding = first_segment.float_
                    logger.info(f"Extracted embedding with {len(query_embedding)} dimensions")
            elif hasattr(text_emb, 'float_'):
                query_embedding = text_emb.float_
            elif hasattr(text_emb, 'float'):
                query_embedding = text_emb.float
            else:
                # Try direct access
                query_embedding = text_emb
        
        if not query_embedding:
            logger.error("Failed to extract embedding from query")
            logger.error(f"Final object: {final}")
            return []
        
        # Convert to Oracle VECTOR format (as a string for SQL)
        query_vector_list = list(query_embedding)
        logger.info(f"Query vector has {len(query_vector_list)} dimensions")
        
        # Convert vector to JSON string for Oracle TO_VECTOR function
        import json
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
