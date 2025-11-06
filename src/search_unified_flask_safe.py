#!/usr/bin/env python3
"""Unified Flask-safe vector search for both photos and video segments"""
import os
import sys
import json
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

def search_unified_flask_safe(query_text: str, album_name: str = None, top_k: int = 20, min_similarity: float = 0.30) -> List[Dict]:
    """Search both photos and video segments using TwelveLabs embedding and Oracle VECTOR similarity
    
    Args:
        query_text: Natural language search query
        album_name: Optional album filter
        top_k: Number of results to return (split between photos and videos)
        min_similarity: Minimum similarity threshold (0.0-1.0). Default 0.30 (30%)
        
    Returns:
        Combined list of photo and video segment results with similarity scores above threshold
    """
    try:
        # Get TwelveLabs embedding for the query
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        logger.info(f"🔍 Creating embedding for query: '{query_text}'")
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
        
        if hasattr(final, 'text_embedding'):
            text_emb = final.text_embedding
            
            if hasattr(text_emb, 'segments') and text_emb.segments:
                first_segment = text_emb.segments[0]
                
                if hasattr(first_segment, 'embeddings_float'):
                    query_embedding = first_segment.embeddings_float
                elif hasattr(first_segment, 'embedding'):
                    query_embedding = first_segment.embedding
                elif hasattr(first_segment, 'float_'):
                    query_embedding = first_segment.float_
            elif hasattr(text_emb, 'float_'):
                query_embedding = text_emb.float_
            elif hasattr(text_emb, 'float'):
                query_embedding = text_emb.float
        
        if not query_embedding:
            logger.error("❌ Failed to extract embedding from query")
            return []
        
        # Convert to Oracle VECTOR format
        query_vector_list = list(query_embedding)
        vector_json = json.dumps(query_vector_list)
        logger.info(f"✅ Query vector has {len(query_vector_list)} dimensions")
        
        # Search photos and videos separately, then combine
        all_results = []
        
        # 1. Search PHOTOS from album_media table
        logger.info("📸 Searching photos...")
        photo_sql = """
        SELECT 
            id as media_id,
            album_name,
            file_name,
            file_path,
            file_type,
            created_at,
            VECTOR_DISTANCE(embedding_vector, TO_VECTOR(:query_vector), COSINE) as distance,
            NULL as segment_start,
            NULL as segment_end
        FROM album_media
        WHERE file_type = 'photo'
        AND embedding_vector IS NOT NULL
        """
        
        if album_name:
            photo_sql += " AND album_name = :album_name"
        
        photo_sql += """
        ORDER BY distance
        FETCH FIRST :top_k ROWS ONLY
        """
        
        photo_params = {'query_vector': vector_json, 'top_k': top_k}
        if album_name:
            photo_params['album_name'] = album_name
        
        photo_results = flask_safe_execute_query(photo_sql, photo_params)
        
        for row in photo_results:
            distance = row[6]
            similarity = 1.0 - distance
            
            if similarity >= min_similarity:
                all_results.append({
                    'media_id': row[0],
                    'album_name': row[1],
                    'file_name': row[2],
                    'file_path': row[3],
                    'file_type': 'photo',
                    'created_at': row[5],
                    'similarity': similarity,
                    'score': similarity,
                    'segment_start': None,
                    'segment_end': None
                })
        
        logger.info(f"✅ Found {len([r for r in all_results if r['file_type']=='photo'])} photos")
        
        # 2. Search VIDEO SEGMENTS from video_embeddings table
        logger.info("🎬 Searching video segments...")
        
        # Join video_embeddings with album_media to get album and file info
        video_sql = """
        SELECT 
            ve.id as embedding_id,
            am.album_name,
            ve.video_file,
            am.file_path,
            'video' as file_type,
            am.created_at,
            VECTOR_DISTANCE(ve.embedding_vector, TO_VECTOR(:query_vector), COSINE) as distance,
            ve.start_time,
            ve.end_time,
            am.id as media_id
        FROM video_embeddings ve
        JOIN album_media am ON ve.video_file = am.file_name
        WHERE ve.embedding_vector IS NOT NULL
        """
        
        if album_name:
            video_sql += " AND am.album_name = :album_name"
        
        video_sql += """
        ORDER BY distance
        FETCH FIRST :top_k ROWS ONLY
        """
        
        video_params = {'query_vector': vector_json, 'top_k': top_k}
        if album_name:
            video_params['album_name'] = album_name
        
        video_results = flask_safe_execute_query(video_sql, video_params)
        
        for row in video_results:
            distance = row[6]
            similarity = 1.0 - distance
            
            if similarity >= min_similarity:
                all_results.append({
                    'media_id': row[9],  # album_media.id
                    'embedding_id': row[0],  # video_embeddings.id
                    'album_name': row[1],
                    'file_name': row[2],  # video_file
                    'file_path': row[3],
                    'file_type': 'video',
                    'created_at': row[5],
                    'similarity': similarity,
                    'score': similarity,
                    'segment_start': float(row[7]) if row[7] else None,
                    'segment_end': float(row[8]) if row[8] else None
                })
        
        logger.info(f"✅ Found {len([r for r in all_results if r['file_type']=='video'])} video segments")
        
        # Sort all results by similarity score (highest first)
        all_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Limit to top_k total results
        all_results = all_results[:top_k]
        
        logger.info(f"🎯 Returning {len(all_results)} total results (threshold: {min_similarity*100:.0f}%)")
        logger.info(f"   📸 Photos: {len([r for r in all_results if r['file_type']=='photo'])}")
        logger.info(f"   🎬 Videos: {len([r for r in all_results if r['file_type']=='video'])}")
        
        return all_results
        
    except Exception as e:
        logger.exception(f"❌ Unified search failed: {e}")
        return []


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS"""
    if seconds is None:
        return "N/A"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"
