#!/usr/bin/env python3
"""Unified Flask-safe vector search for both photos and video segments"""
import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

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
        # Use 0 as default user_id for global/guest cache entries
        effective_user_id = user_id if user_id is not None else 0
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check user-specific cache first, then fall back to global cache
            if user_id:
                cursor.execute("""
                    SELECT embedding_vector 
                    FROM query_embedding_cache 
                    WHERE query_text = :query
                    AND (user_id = :user_id OR user_id = 0)
                    ORDER BY user_id DESC
                    FETCH FIRST 1 ROW ONLY
                """, {"query": query_text, "user_id": user_id})
            else:
                cursor.execute("""
                    SELECT embedding_vector 
                    FROM query_embedding_cache 
                    WHERE query_text = :query
                    AND user_id = 0
                """, {"query": query_text})
            
            result = cursor.fetchone()
            if result and result[0]:
                # Update usage stats
                cursor.execute("""
                    UPDATE query_embedding_cache 
                    SET last_used_at = CURRENT_TIMESTAMP, 
                        usage_count = usage_count + 1
                    WHERE query_text = :query
                    AND user_id = :user_id
                """, {"query": query_text, "user_id": effective_user_id})
                conn.commit()
                
                logger.info(f"💾 Using cached embedding for query: '{query_text}'" + (f" (user {user_id})" if user_id else " (global)"))
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
        user_id: Optional user ID for user-specific caching (defaults to 0 for global/guest)
    """
    try:
        # Use 0 as default user_id for global/guest cache entries
        effective_user_id = user_id if user_id is not None else 0
        vector_json = json.dumps(embedding_list)
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO query_embedding_cache (query_text, embedding_vector, user_id)
                VALUES (:query, TO_VECTOR(:vector), :user_id)
            """, {"query": query_text, "vector": vector_json, "user_id": effective_user_id})
            
            if user_id:
                logger.info(f"💾 Saved embedding to cache for: '{query_text}' (user {user_id})")
            else:
                logger.info(f"💾 Saved embedding to cache for: '{query_text}' (global)")
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to save to cache (may already exist): {e}")

def search_unified_flask_safe(query_text: str, user_id: int = None, album_name: str = None, top_k: int = 20, min_similarity: float = 0.30) -> List[Dict]:
    """Search both photos and video segments using ImageBind embedding and Oracle VECTOR similarity
    
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
        # Check cache first (with user_id for isolation)
        vector_json = get_cached_embedding(query_text, user_id) if user_id else get_cached_embedding(query_text)
        
        if not vector_json:
            # Cache miss - get embedding from ImageBind (free, instant)
            from utils.imagebind_helper import get_imagebind_embedder
            
            logger.info(f"🔍 Creating ImageBind embedding for query: '{query_text}'")
            embedder = get_imagebind_embedder()
            embedding_array = embedder.generate_text_embedding(query_text)
            
            if embedding_array is None:
                raise ValueError("Failed to generate text embedding")
            
            # Convert to JSON format for Oracle VECTOR
            vector_json = json.dumps(embedding_array.tolist())
            
            # Convert to list and save to cache
            query_vector_list = embedding_array.tolist()
            logger.info(f"✅ Query vector has {len(query_vector_list)} dimensions")
            
            # Save to cache for future use (with user_id for isolation)
            save_embedding_to_cache(query_text, query_vector_list, user_id)
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
            NULL as ai_tags
        FROM album_media
        WHERE file_type = 'photo'
        AND embedding_vector IS NOT NULL
        """
        
        # Add user_id filter if provided
        if user_id:
            photo_sql += " AND user_id = :user_id"
        
        if album_name:
            photo_sql += " AND album_name = :album_name"
        
        # Fetch more initially for face matching boost, then limit later
        photo_sql += """
        ORDER BY distance
        FETCH FIRST :top_k_initial ROWS ONLY
        """
        
        photo_params = {'query_vector': vector_json, 'top_k_initial': min(top_k * 2, 50)}
        if user_id:
            photo_params['user_id'] = user_id
        if album_name:
            photo_params['album_name'] = album_name
        
        photo_results = flask_safe_execute_query(photo_sql, photo_params)
        
        # Log top results for debugging
        if photo_results:
            logger.info(f"🔍 Top photo search results (showing similarity scores):")
            for i, row in enumerate(photo_results[:5]):
                distance = row[6]
                similarity = 1.0 - distance
                logger.info(f"  {i+1}. {row[2]} - similarity: {similarity:.3f} (threshold: {min_similarity:.3f})")
        
        for row in photo_results:
            distance = row[6]
            similarity = 1.0 - distance
            
            # Apply minimum similarity threshold
            if similarity < min_similarity:
                continue
            
            media_id = row[0]
            file_name = row[2]
            
            # Extract key concepts from query for verification
            query_lower = query_text.lower()
            query_words = set(w.strip().lower() for w in query_text.split() if len(w.strip()) > 2)
            
            # Get rich_metadata to verify semantic match
            boost = 1.0
            verification_passed = True
            
            try:
                # Fetch rich_metadata for this photo to verify concepts
                with get_flask_safe_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT rich_metadata
                        FROM album_media
                        WHERE id = :media_id
                    """, {"media_id": media_id})
                    
                    metadata_row = cursor.fetchone()
                    if metadata_row and metadata_row[0]:
                        # Parse metadata
                        import json as json_module
                        try:
                            metadata = json_module.loads(metadata_row[0]) if isinstance(metadata_row[0], str) else metadata_row[0]
                        except:
                            metadata = {}
                        
                        # Check if key query concepts exist in metadata
                        metadata_str = json_module.dumps(metadata).lower()
                        
                        # Count how many query words appear in metadata
                        matches = sum(1 for word in query_words if word in metadata_str)
                        match_ratio = matches / len(query_words) if query_words else 0
                        
                        # Boost score if metadata confirms the query concepts
                        if match_ratio >= 0.5:  # At least half the query words match
                            boost = 1.2
                            logger.debug(f"  ✓ {file_name}: {matches}/{len(query_words)} query words found in metadata")
                        elif match_ratio < 0.3 and similarity < 0.6:  # Low match and low similarity
                            # Skip results with poor semantic match
                            verification_passed = False
                            logger.debug(f"  ✗ {file_name}: Only {matches}/{len(query_words)} query words found, skipping")
            except Exception as e:
                logger.debug(f"  Metadata check skipped for {file_name}: {e}")
            
            if not verification_passed:
                continue
            
            # AI_TAGS is already converted from CLOB to string by flask_safe_execute_query
            ai_tags = row[9] if len(row) > 9 else None
            
            all_results.append({
                'media_id': media_id,
                'album_name': row[1],
                'file_name': file_name,
                'file_path': row[3],
                'file_type': 'photo',
                'created_at': row[5],
                'similarity': similarity * boost,
                'score': similarity * boost,
                'segment_start': None,
                'segment_end': None,
                'ai_tags': None
            })
        
        logger.info(f"✅ Found {len([r for r in all_results if r['file_type']=='photo'])} photos")
        
        # 1b. Search by FACE NAMES (e.g., "Rahul with smile")
        # Extract potential person names from query and search face_tags
        logger.info("👤 Searching by face names...")
        
        # Simple approach: check if query contains known names or search face_tags directly
        face_search_sql = """
        SELECT DISTINCT
            am.id as media_id,
            am.album_name,
            am.file_name,
            am.file_path,
            'photo' as file_type,
            am.created_at,
            ft.face_name,
            ft.confidence
        FROM face_tags ft
        JOIN album_media am ON ft.media_id = am.id
        WHERE LOWER(ft.face_name) LIKE LOWER(:face_query)
        AND ft.face_name != 'Unknown'
        """
        
        if user_id:
            face_search_sql += " AND am.user_id = :user_id"
        
        if album_name:
            face_search_sql += " AND am.album_name = :album_name"
        
        face_search_sql += " FETCH FIRST 20 ROWS ONLY"
        
        # Try to extract name from query - search for each word separately
        face_results = []
        words = [w.strip() for w in query_text.split() if len(w.strip()) > 2]  # Skip short words like "a", "in", "with"
        
        try:
            for word in words:
                face_params = {'face_query': f"%{word}%"}
                if user_id:
                    face_params['user_id'] = user_id
                if album_name:
                    face_params['album_name'] = album_name
                
                word_results = flask_safe_execute_query(face_search_sql, face_params)
                if word_results:
                    face_results.extend(word_results)
            
            # Remove duplicates based on media_id
            seen_ids = set()
            unique_results = []
            for row in face_results:
                if row[0] not in seen_ids:
                    seen_ids.add(row[0])
                    unique_results.append(row)
            face_results = unique_results
            
            for row in face_results:
                # High similarity for face name matches
                similarity = 0.95  # Strong match for face names
                
                # Check if already in results
                existing = next((r for r in all_results if r['media_id'] == row[0]), None)
                if existing:
                    # Boost score if face name matches
                    existing['similarity'] = max(existing['similarity'], similarity)
                    existing['score'] = existing['similarity']
                    existing['face_name'] = row[6]
                else:
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
                        'ai_tags': None,
                        'face_name': row[6],
                        'face_confidence': float(row[7]) if row[7] else None
                    })
            
            logger.info(f"✅ Found {len(face_results)} photos with matching face names")
        except Exception as e:
            logger.error(f"Face name search failed: {e}")
        
        # 1c. Search by RICH METADATA (GPT-extracted tags, objects, activities, etc.)
        logger.info("🏷️  Searching rich metadata...")
        
        try:
            # Search for query words in metadata using native JSON functions
            metadata_results = []
            for word in words:
                if len(word) > 3:  # Only search meaningful words
                    # Use JSON_TEXTCONTAINS for efficient JSON search (works with native JSON or CLOB with JSON constraint)
                    metadata_search_sql = f"""
                    SELECT 
                        id as media_id,
                        album_name,
                        file_name,
                        file_path,
                        'photo' as file_type,
                        created_at,
                        rich_metadata
                    FROM album_media
                    WHERE file_type = 'photo'
                    AND rich_metadata IS NOT NULL
                    AND JSON_TEXTCONTAINS(rich_metadata, '$', :search_word)
                    """
                    
                    if user_id:
                        metadata_search_sql += " AND user_id = :user_id"
                    
                    if album_name:
                        metadata_search_sql += " AND album_name = :album_name"
                    
                    metadata_search_sql += " FETCH FIRST 30 ROWS ONLY"
                    
                    metadata_params = {'search_word': word.lower()}
                    if user_id:
                        metadata_params['user_id'] = user_id
                    if album_name:
                        metadata_params['album_name'] = album_name
                    
                    word_results = flask_safe_execute_query(metadata_search_sql, metadata_params)
                    if word_results:
                        metadata_results.extend(word_results)
            
            # Remove duplicates
            seen_metadata_ids = set()
            unique_metadata = []
            for row in metadata_results:
                if row[0] not in seen_metadata_ids:
                    seen_metadata_ids.add(row[0])
                    unique_metadata.append(row)
            metadata_results = unique_metadata
            
            for row in metadata_results:
                # Good similarity for metadata matches
                similarity = 0.85
                
                # Check if already in results
                existing = next((r for r in all_results if r['media_id'] == row[0]), None)
                if existing:
                    # Boost score for metadata match
                    existing['similarity'] = max(existing['similarity'], similarity)
                    existing['score'] = existing['similarity']
                else:
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
                        'ai_tags': None,
                        'metadata_match': True
                    })
            
            logger.info(f"✅ Found {len(metadata_results)} photos from metadata search")
        except Exception as e:
            logger.error(f"Metadata search failed: {e}")
        
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
            NULL as ai_tags
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
        FETCH FIRST :top_k_initial ROWS ONLY
        """
        
        video_params = {'query_vector': vector_json, 'top_k_initial': min(top_k, 30)}
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
        # Note: AI_TAGS might be CLOB or JSON depending on schema
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
            OR (AI_TAGS IS NOT NULL AND 
                (JSON_TEXTCONTAINS(AI_TAGS, '$', :search_text) OR 
                 DBMS_LOB.INSTR(LOWER(AI_TAGS), LOWER(:search_text), 1, 1) > 0))
        )
        """
        
        if user_id:
            photo_sql += " AND user_id = :user_id"
        if album_name:
            photo_sql += " AND album_name = :album_name"
        
        photo_sql += " FETCH FIRST :top_k ROWS ONLY"
        
        # Build search parameters
        keyword_pattern = f"%{query_text.lower()}%"
        
        photo_params = {
            'keyword': keyword_pattern, 
            'search_text': query_text.lower(),
            'top_k': top_k
        }
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
        
        # Search photos by face tag names (person names)
        # Detect if query contains multiple person names (using "and" or "&")
        person_names = []
        if ' and ' in query_text.lower():
            person_names = [name.strip() for name in query_text.lower().split(' and ')]
        elif ' & ' in query_text:
            person_names = [name.strip() for name in query_text.split(' & ')]
        else:
            # Single name search
            person_names = [query_text.lower()]
        
        # Remove common words that aren't names
        person_names = [name for name in person_names if name not in ['smile', 'with', 'at', 'in', 'the', 'a', 'an']]
        
        if len(person_names) > 1:
            # Multiple names: Find photos that have ALL these people (AND logic)
            logger.info(f"   👥 Searching for photos with multiple people: {person_names}")
            
            # Build a query that finds media_ids with all specified face names
            face_sql = f"""
            SELECT 
                am.id,
                am.album_name,
                am.file_name,
                am.file_path,
                'photo' as file_type,
                am.created_at,
                am.AI_TAGS
            FROM album_media am
            WHERE am.file_type = 'photo'
            AND am.id IN (
                SELECT media_id
                FROM face_tags
                WHERE LOWER(face_name) LIKE :name1
            )
            """
            
            # Add conditions for each additional name
            for i in range(1, len(person_names)):
                face_sql += f"""
                AND am.id IN (
                    SELECT media_id
                    FROM face_tags
                    WHERE LOWER(face_name) LIKE :name{i+1}
                )
                """
            
            if user_id:
                face_sql += " AND am.user_id = :user_id"
            if album_name:
                face_sql += " AND am.album_name = :album_name"
            
            face_sql += " FETCH FIRST :top_k ROWS ONLY"
            
            # Build parameters for each name
            face_params = {'top_k': top_k}
            for i, name in enumerate(person_names, 1):
                face_params[f'name{i}'] = f"%{name}%"
            
            if user_id:
                face_params['user_id'] = user_id
            if album_name:
                face_params['album_name'] = album_name
            
        else:
            # Single name: Standard search
            face_sql = """
            SELECT DISTINCT
                am.id,
                am.album_name,
                am.file_name,
                am.file_path,
                'photo' as file_type,
                am.created_at,
                am.AI_TAGS
            FROM album_media am
            INNER JOIN face_tags ft ON am.id = ft.media_id
            WHERE am.file_type = 'photo'
            AND LOWER(ft.face_name) LIKE :keyword
            """
            
            if user_id:
                face_sql += " AND am.user_id = :user_id"
            if album_name:
                face_sql += " AND am.album_name = :album_name"
            
            face_sql += " FETCH FIRST :top_k ROWS ONLY"
            
            face_params = {'keyword': keyword_pattern, 'top_k': top_k}
            if user_id:
                face_params['user_id'] = user_id
            if album_name:
                face_params['album_name'] = album_name
        
        face_results = flask_safe_execute_query(face_sql, face_params)
        
        for row in face_results:
            # Check if this media_id is already in results
            if any(r['media_id'] == row[0] for r in all_results):
                continue  # Skip duplicates
            
            ai_tags = row[6] if len(row) > 6 else None
            
            # Higher score for multi-person matches (more specific query)
            score = 0.9 if len(person_names) > 1 else 0.8
            
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
                'match_type': 'face_tag_multi' if len(person_names) > 1 else 'face_tag'
            })
        
        logger.info(f"   👤 Found {len([r for r in all_results if r.get('match_type') in ['face_tag', 'face_tag_multi']])} photos via face tags")
        
        # Search videos by filename and AI tags
        video_sql = """
        SELECT
            am.id,
            am.album_name,
            am.file_name,
            am.file_path,
            'video' as file_type,
            am.created_at,
            am.AI_TAGS
        FROM album_media am
        WHERE am.file_type = 'video'
        AND (
            LOWER(am.file_name) LIKE :keyword
            OR (am.AI_TAGS IS NOT NULL AND 
                (JSON_TEXTCONTAINS(am.AI_TAGS, '$', :search_text) OR 
                 DBMS_LOB.INSTR(LOWER(am.AI_TAGS), LOWER(:search_text), 1, 1) > 0))
        )
        """
        
        if user_id:
            video_sql += " AND am.user_id = :user_id"
        if album_name:
            video_sql += " AND am.album_name = :album_name"
        
        video_sql += " FETCH FIRST :top_k ROWS ONLY"
        
        video_params = {
            'keyword': f"%{query_text.lower()}%",
            'search_text': query_text.lower(),
            'top_k': top_k
        }
        if user_id:
            video_params['user_id'] = user_id
        if album_name:
            video_params['album_name'] = album_name
        
        video_results = flask_safe_execute_query(video_sql, video_params)
        
        for row in video_results:
            ai_tags = row[6] if len(row) > 6 else None
            
            # Calculate relevance score
            file_name_lower = row[2].lower() if row[2] else ""
            tags_lower = (ai_tags or "").lower()
            
            score = 0.0
            for keyword in keywords:
                if keyword in file_name_lower:
                    score += 0.5
                if keyword in tags_lower:
                    score += 0.5
            
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
