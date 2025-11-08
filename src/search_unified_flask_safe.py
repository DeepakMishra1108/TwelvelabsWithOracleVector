#!/usr/bin/env python3
"""Unified Flask-safe vector search for both photos and video segments"""
import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'twelvelabvideoai', 'src'))

from utils.db_utils_flask_safe import flask_safe_execute_query, get_flask_safe_connection

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_cached_embedding(query_text: str, user_id: int = None) -> Optional[str]:
    """Get cached embedding for query if it exists
    
    Args:
        query_text: The search query
        user_id: Optional user ID for user-specific cache lookup
    """
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check user-specific cache first, then fall back to global cache
            if user_id:
                cursor.execute("""
                    SELECT embedding_vector 
                    FROM query_embedding_cache 
                    WHERE query_text = :query
                    AND (user_id = :user_id OR user_id IS NULL)
                    ORDER BY user_id DESC NULLS LAST
                    FETCH FIRST 1 ROW ONLY
                """, {"query": query_text, "user_id": user_id})
            else:
                cursor.execute("""
                    SELECT embedding_vector 
                    FROM query_embedding_cache 
                    WHERE query_text = :query
                    AND user_id IS NULL
                """, {"query": query_text})
            
            result = cursor.fetchone()
            if result and result[0]:
                # Update usage stats
                if user_id:
                    cursor.execute("""
                        UPDATE query_embedding_cache 
                        SET last_used_at = CURRENT_TIMESTAMP, 
                            usage_count = usage_count + 1
                        WHERE query_text = :query
                        AND (user_id = :user_id OR user_id IS NULL)
                    """, {"query": query_text, "user_id": user_id})
                else:
                    cursor.execute("""
                        UPDATE query_embedding_cache 
                        SET last_used_at = CURRENT_TIMESTAMP, 
                            usage_count = usage_count + 1
                        WHERE query_text = :query
                        AND user_id IS NULL
                    """, {"query": query_text})
                conn.commit()
                
                logger.info(f"💾 Using cached embedding for query: '{query_text}'" + (f" (user {user_id})" if user_id else ""))
                # Convert VECTOR to JSON
                return json.dumps(list(result[0]))
            return None
    except Exception as e:
        logger.warning(f"Failed to get cached embedding: {e}")
        return None

def save_embedding_to_cache(query_text: str, embedding_list: List[float], user_id: int = None):
    """Save query embedding to cache
    
    Args:
        query_text: The search query
        embedding_list: The embedding vector
        user_id: Optional user ID for user-specific caching
    """
def save_embedding_to_cache(query_text: str, embedding_list: List[float], user_id: int = None):
    """Save query embedding to cache
    
    Args:
        query_text: The search query
        embedding_list: The embedding vector
        user_id: Optional user ID for user-specific caching
    """
    try:
        vector_json = json.dumps(embedding_list)
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("""
                    INSERT INTO query_embedding_cache (query_text, embedding_vector, user_id)
                    VALUES (:query, TO_VECTOR(:vector), :user_id)
                """, {"query": query_text, "vector": vector_json, "user_id": user_id})
                logger.info(f"💾 Saved embedding to cache for: '{query_text}' (user {user_id})")
            else:
                cursor.execute("""
                    INSERT INTO query_embedding_cache (query_text, embedding_vector)
                    VALUES (:query, TO_VECTOR(:vector))
                """, {"query": query_text, "vector": vector_json})
                logger.info(f"💾 Saved embedding to cache for: '{query_text}' (global)")
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to save to cache (may already exist): {e}")

def search_unified_flask_safe(query_text: str, user_id: int = None, album_name: str = None, top_k: int = 20, min_similarity: float = 0.30) -> List[Dict]:
    """Search both photos and video segments using TwelveLabs embedding and Oracle VECTOR similarity
    
    Args:
        query_text: Natural language search query
        user_id: User ID to filter results (None for admin to see all)
        album_name: Optional album filter
        top_k: Number of results to return (split between photos and videos)
        min_similarity: Minimum similarity threshold (0.0-1.0). Default 0.30 (30%)
        
    Returns:
        Combined list of photo and video segment results with similarity scores above threshold
    """
    try:
        # For caching: if user_id is None (admin), we need the actual user_id from Flask context
        # For filtering: None means show all results
        cache_user_id = user_id
        if cache_user_id is None:
            # Try to get from Flask login context
            try:
                from flask_login import current_user
                if current_user and current_user.is_authenticated:
                    cache_user_id = current_user.id
            except:
                cache_user_id = 1  # Fallback to user 1 for global cache
        
        # Check cache first (with cache_user_id for isolation)
        vector_json = get_cached_embedding(query_text, cache_user_id)
        
        if not vector_json:
            # Cache miss - get embedding from TwelveLabs API
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
            
            # Save to cache for future use (with cache_user_id for isolation)
            save_embedding_to_cache(query_text, query_vector_list, cache_user_id)
        else:
            logger.info(f"✅ Using cached query vector")
        
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
            NULL as segment_end,
            AI_TAGS
        FROM album_media
        WHERE file_type = 'photo'
        AND embedding_vector IS NOT NULL
        """
        
        # Add user_id filter if provided
        if user_id:
            photo_sql += " AND user_id = :user_id"
        
        if album_name:
            photo_sql += " AND album_name = :album_name"
        
        photo_sql += """
        ORDER BY distance
        FETCH FIRST :top_k ROWS ONLY
        """
        
        photo_params = {'query_vector': vector_json, 'top_k': top_k}
        if user_id:
            photo_params['user_id'] = user_id
        if album_name:
            photo_params['album_name'] = album_name
        
        photo_results = flask_safe_execute_query(photo_sql, photo_params)
        
        for row in photo_results:
            distance = row[6]
            similarity = 1.0 - distance
            
            if similarity >= min_similarity:
                # AI_TAGS is already converted from CLOB to string by flask_safe_execute_query
                ai_tags = row[9] if len(row) > 9 else None
                
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
                    'segment_end': None,
                    'ai_tags': ai_tags
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
            am.id as media_id,
            am.AI_TAGS
        FROM video_embeddings ve
        JOIN album_media am ON ve.video_file = am.file_name
        WHERE ve.embedding_vector IS NOT NULL
        """
        
        # Add user_id filter if provided
        if user_id:
            video_sql += " AND am.user_id = :user_id"
        
        if album_name:
            video_sql += " AND am.album_name = :album_name"
        
        video_sql += """
        ORDER BY distance
        FETCH FIRST :top_k ROWS ONLY
        """
        
        video_params = {'query_vector': vector_json, 'top_k': top_k}
        if user_id:
            video_params['user_id'] = user_id
        if album_name:
            video_params['album_name'] = album_name
        
        video_results = flask_safe_execute_query(video_sql, video_params)
        
        for row in video_results:
            distance = row[6]
            similarity = 1.0 - distance
            
            if similarity >= min_similarity:
                # AI_TAGS is already converted from CLOB to string by flask_safe_execute_query
                ai_tags = row[10] if len(row) > 10 else None
                
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
                    'segment_end': float(row[8]) if row[8] else None,
                    'ai_tags': ai_tags
                })
        
        logger.info(f"✅ Found {len([r for r in all_results if r['file_type']=='video'])} video segments")
        
        # Sort all results by similarity score (highest first)
        all_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Limit to top_k total results
        all_results = all_results[:top_k]
        
        logger.info(f"🎯 Returning {len(all_results)} total results (threshold: {min_similarity*100:.0f}%)")
        logger.info(f"   📸 Photos: {len([r for r in all_results if r['file_type']=='photo'])}")
        logger.info(f"   🎬 Videos: {len([r for r in all_results if r['file_type']=='video'])}")
        
        # If no results from vector search, try metadata fallback
        if len(all_results) == 0:
            logger.info("⚠️  No vector search results, trying metadata-based search...")
            all_results = search_by_metadata(query_text, user_id, album_name, top_k)
            if len(all_results) > 0:
                logger.info(f"✅ Metadata fallback found {len(all_results)} results")
        
        return all_results
        
    except Exception as e:
        logger.exception(f"❌ Unified search failed: {e}")
        # Try metadata fallback on error
        logger.info("⚠️  Vector search error, trying metadata-based search...")
        try:
            fallback_results = search_by_metadata(query_text, user_id, album_name, top_k)
            if len(fallback_results) > 0:
                logger.info(f"✅ Metadata fallback found {len(fallback_results)} results")
                return fallback_results
        except Exception as fallback_error:
            logger.error(f"❌ Metadata fallback also failed: {fallback_error}")
        
        return []


def search_by_metadata(query_text: str, user_id: int = None, album_name: str = None, top_k: int = 50) -> List[Dict[str, Any]]:
    """Fallback search using metadata (filename, AI tags, titles, descriptions)
    
    Args:
        query_text: Search query text
        user_id: User ID to filter results
        album_name: Optional album filter
        top_k: Number of results to return
        
    Returns:
        List of results matching metadata search
    """
    try:
        logger.info(f"🔍 Metadata-based search for: '{query_text}'")
        
        # Split query into keywords for better matching
        keywords = query_text.lower().split()
        
        all_results = []
        
        # Search photos by filename and AI tags
        photo_sql = """
        SELECT 
            id,
            album_name,
            file_name,
            file_path,
            'photo' as file_type,
            created_at,
            AI_TAGS
        FROM album_media
        WHERE file_type = 'photo'
        AND (
            LOWER(file_name) LIKE :keyword
            OR LOWER(AI_TAGS) LIKE :keyword
        )
        """
        
        if user_id:
            photo_sql += " AND user_id = :user_id"
        if album_name:
            photo_sql += " AND album_name = :album_name"
        
        photo_sql += " FETCH FIRST :top_k ROWS ONLY"
        
        # Build OR conditions for multiple keywords
        keyword_pattern = f"%{query_text.lower()}%"
        
        photo_params = {'keyword': keyword_pattern, 'top_k': top_k}
        if user_id:
            photo_params['user_id'] = user_id
        if album_name:
            photo_params['album_name'] = album_name
        
        photo_results = flask_safe_execute_query(photo_sql, photo_params)
        
        for row in photo_results:
            ai_tags = row[6] if len(row) > 6 else None
            
            # Calculate simple relevance score based on keyword matches
            file_name_lower = row[2].lower() if row[2] else ""
            tags_lower = (ai_tags or "").lower()
            
            score = 0.0
            for keyword in keywords:
                if keyword in file_name_lower:
                    score += 0.5
                if keyword in tags_lower:
                    score += 0.3
            
            # Normalize score to 0-1 range
            score = min(score, 1.0)
            
            all_results.append({
                'media_id': row[0],
                'album_name': row[1],
                'file_name': row[2],
                'file_path': row[3],
                'file_type': 'photo',
                'created_at': row[5],
                'similarity': score,
                'score': score,
                'segment_start': None,
                'segment_end': None,
                'ai_tags': ai_tags,
                'match_type': 'metadata'
            })
        
        logger.info(f"   📸 Found {len(all_results)} photos via metadata")
        
        # Search videos by filename, AI tags, and video title
        video_sql = """
        SELECT DISTINCT
            am.id,
            am.album_name,
            am.file_name,
            am.file_path,
            'video' as file_type,
            am.created_at,
            am.AI_TAGS,
            ve.video_title
        FROM album_media am
        LEFT JOIN video_embeddings ve ON am.file_name = ve.video_file
        WHERE am.file_type = 'video'
        AND (
            LOWER(am.file_name) LIKE :keyword
            OR LOWER(am.AI_TAGS) LIKE :keyword
            OR LOWER(ve.video_title) LIKE :keyword
        )
        """
        
        if user_id:
            video_sql += " AND am.user_id = :user_id"
        if album_name:
            video_sql += " AND am.album_name = :album_name"
        
        video_sql += " FETCH FIRST :top_k ROWS ONLY"
        
        video_params = {'keyword': keyword_pattern, 'top_k': top_k}
        if user_id:
            video_params['user_id'] = user_id
        if album_name:
            video_params['album_name'] = album_name
        
        video_results = flask_safe_execute_query(video_sql, video_params)
        
        for row in video_results:
            ai_tags = row[6] if len(row) > 6 else None
            video_title = row[7] if len(row) > 7 else None
            
            # Calculate relevance score
            file_name_lower = row[2].lower() if row[2] else ""
            tags_lower = (ai_tags or "").lower()
            title_lower = (video_title or "").lower()
            
            score = 0.0
            for keyword in keywords:
                if keyword in file_name_lower:
                    score += 0.4
                if keyword in title_lower:
                    score += 0.4
                if keyword in tags_lower:
                    score += 0.2
            
            score = min(score, 1.0)
            
            all_results.append({
                'media_id': row[0],
                'album_name': row[1],
                'file_name': row[2],
                'file_path': row[3],
                'file_type': 'video',
                'created_at': row[5],
                'similarity': score,
                'score': score,
                'segment_start': None,
                'segment_end': None,
                'ai_tags': ai_tags,
                'video_title': video_title,
                'match_type': 'metadata'
            })
        
        logger.info(f"   🎬 Found {len([r for r in all_results if r['file_type']=='video'])} videos via metadata")
        
        # Sort by relevance score
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Limit to top_k
        all_results = all_results[:top_k]
        
        logger.info(f"✅ Metadata search returned {len(all_results)} results")
        
        return all_results
        
    except Exception as e:
        logger.exception(f"❌ Metadata search failed: {e}")
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
