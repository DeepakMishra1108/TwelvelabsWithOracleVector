#!/usr/bin/env python3
"""AI-Powered Features Module

This module provides advanced AI features including:
- Video highlights extraction
- Auto-tagging for media
- Similar media finder
- Content moderation
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import httpx
from utils.db_utils_vector import get_db_connection

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TWELVE_LABS_API_KEY = os.getenv('TWELVE_LABS_API_KEY')
TWELVE_LABS_API_URL = "https://api.twelvelabs.io/v1.2"


class VideoHighlightsExtractor:
    """Extract key moments and highlights from videos using TwelveLabs"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or TWELVE_LABS_API_KEY
        self.base_url = TWELVE_LABS_API_URL
        
    async def extract_highlights(self, video_id: str, max_highlights: int = 5) -> Dict[str, Any]:
        """Extract key highlights from a video
        
        Args:
            video_id: TwelveLabs video ID
            max_highlights: Maximum number of highlights to extract
            
        Returns:
            Dict containing highlights with timestamps and descriptions
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Use TwelveLabs generate API to create highlights
                response = await client.post(
                    f"{self.base_url}/generate",
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "video_id": video_id,
                        "types": ["highlight"]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Extracted highlights for video {video_id}")
                    return {
                        "success": True,
                        "video_id": video_id,
                        "highlights": data.get("highlights", [])[:max_highlights]
                    }
                else:
                    logger.error(f"❌ Failed to extract highlights: {response.text}")
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            logger.error(f"❌ Error extracting highlights: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_video_chapters(self, video_id: str) -> Dict[str, Any]:
        """Get video chapters with timestamps
        
        Args:
            video_id: TwelveLabs video ID
            
        Returns:
            Dict containing chapters with timestamps and descriptions
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/generate",
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "video_id": video_id,
                        "types": ["chapter"]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Got chapters for video {video_id}")
                    return {
                        "success": True,
                        "video_id": video_id,
                        "chapters": data.get("chapters", [])
                    }
                else:
                    logger.error(f"❌ Failed to get chapters: {response.text}")
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            logger.error(f"❌ Error getting chapters: {str(e)}")
            return {"success": False, "error": str(e)}


class AutoTagger:
    """Automatically generate tags and labels for media"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or TWELVE_LABS_API_KEY
        self.base_url = TWELVE_LABS_API_URL
        
    async def generate_tags(self, video_id: str) -> Dict[str, Any]:
        """Generate tags, topics, and hashtags for a video
        
        Args:
            video_id: TwelveLabs video ID
            
        Returns:
            Dict containing generated tags, topics, hashtags, and title
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Generate title, topics, and hashtags
                response = await client.post(
                    f"{self.base_url}/generate",
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "video_id": video_id,
                        "types": ["title", "topic", "hashtag"]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ Generated tags for video {video_id}")
                    
                    return {
                        "success": True,
                        "video_id": video_id,
                        "title": data.get("title", ""),
                        "topics": data.get("topics", []),
                        "hashtags": data.get("hashtags", []),
                        "tags": data.get("topics", []) + data.get("hashtags", [])
                    }
                else:
                    logger.error(f"❌ Failed to generate tags: {response.text}")
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            logger.error(f"❌ Error generating tags: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def save_tags_to_db(self, media_id: int, tags: List[str], media_type: str = "video"):
        """Save generated tags to database
        
        Args:
            media_id: Media ID in album_media table
            tags: List of tags to save
            media_type: Type of media (video or photo)
        """
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Create tags table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media_tags (
                    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    media_id NUMBER NOT NULL,
                    media_type VARCHAR2(20) NOT NULL,
                    tag VARCHAR2(200) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT uk_media_tag UNIQUE (media_id, media_type, tag)
                )
            """)
            
            # Insert tags
            for tag in tags:
                try:
                    cursor.execute("""
                        INSERT INTO media_tags (media_id, media_type, tag)
                        VALUES (:media_id, :media_type, :tag)
                    """, {
                        "media_id": media_id,
                        "media_type": media_type,
                        "tag": tag
                    })
                except Exception as e:
                    # Skip duplicates
                    logger.debug(f"Tag '{tag}' already exists for media {media_id}")
                    
            connection.commit()
            cursor.close()
            connection.close()
            
            logger.info(f"✅ Saved {len(tags)} tags for media {media_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving tags: {str(e)}")
            return False


class SimilarMediaFinder:
    """Find similar photos and videos using vector similarity"""
    
    def find_similar_photos(self, photo_id: int, top_k: int = 10, 
                           min_similarity: float = 0.7) -> List[Dict[str, Any]]:
        """Find photos similar to the given photo
        
        Args:
            photo_id: ID of the photo in album_media table
            top_k: Number of similar photos to return
            min_similarity: Minimum similarity threshold (0-1)
            
        Returns:
            List of similar photos with similarity scores
        """
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Get the embedding of the source photo
            cursor.execute("""
                SELECT embedding_vector
                FROM album_media
                WHERE id = :photo_id AND file_type = 'photo'
            """, {"photo_id": photo_id})
            
            row = cursor.fetchone()
            if not row:
                logger.error(f"❌ Photo {photo_id} not found")
                return []
            
            source_embedding = row[0]
            
            # Find similar photos using VECTOR_DISTANCE
            cursor.execute("""
                SELECT 
                    id,
                    album_name,
                    file_name,
                    VECTOR_DISTANCE(embedding_vector, :source_embedding, COSINE) as distance
                FROM album_media
                WHERE file_type = 'photo'
                  AND id != :photo_id
                ORDER BY distance ASC
                FETCH FIRST :top_k ROWS ONLY
            """, {
                "source_embedding": source_embedding,
                "photo_id": photo_id,
                "top_k": top_k
            })
            
            results = []
            for row in cursor.fetchall():
                similarity = 1.0 - float(row[3])  # Convert distance to similarity
                if similarity >= min_similarity:
                    results.append({
                        "media_id": row[0],
                        "id": row[0],  # Keep for backwards compatibility
                        "album_name": row[1],
                        "file_name": row[2],
                        "score": similarity,
                        "similarity": similarity,  # Keep for backwards compatibility
                        "file_type": "photo",
                        "type": "photo",  # Keep for backwards compatibility
                        "segment_start": None,
                        "segment_end": None
                    })
            
            cursor.close()
            connection.close()
            
            logger.info(f"✅ Found {len(results)} similar photos to {photo_id}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error finding similar photos: {str(e)}")
            return []
    
    def find_similar_videos(self, video_id: int, top_k: int = 10,
                           min_similarity: float = 0.7) -> List[Dict[str, Any]]:
        """Find videos similar to the given video
        
        Args:
            video_id: ID of the video in album_media table
            top_k: Number of similar videos to return
            min_similarity: Minimum similarity threshold (0-1)
            
        Returns:
            List of similar videos with similarity scores
        """
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Get the embedding of the source video (average of all segments)
            cursor.execute("""
                SELECT embedding_vector
                FROM album_media
                WHERE id = :video_id AND file_type = 'video'
                FETCH FIRST 1 ROWS ONLY
            """, {"video_id": video_id})
            
            row = cursor.fetchone()
            if not row:
                logger.error(f"❌ Video {video_id} not found")
                return []
            
            source_embedding = row[0]
            
            # Find similar videos using VECTOR_DISTANCE
            # Group by parent video (same file_name) and use min distance
            cursor.execute("""
                SELECT 
                    id,
                    album_name,
                    file_name,
                    MIN(VECTOR_DISTANCE(embedding_vector, :source_embedding, COSINE)) as distance
                FROM album_media
                WHERE file_type = 'video'
                  AND file_name != (SELECT file_name FROM album_media WHERE id = :video_id)
                GROUP BY id, album_name, file_name
                ORDER BY distance ASC
                FETCH FIRST :top_k ROWS ONLY
            """, {
                "source_embedding": source_embedding,
                "video_id": video_id,
                "top_k": top_k
            })
            
            results = []
            for row in cursor.fetchall():
                similarity = 1.0 - float(row[3])  # Convert distance to similarity
                if similarity >= min_similarity:
                    results.append({
                        "media_id": row[0],
                        "id": row[0],  # Keep for backwards compatibility
                        "album_name": row[1],
                        "file_name": row[2],
                        "score": similarity,
                        "similarity": similarity,  # Keep for backwards compatibility
                        "file_type": "video",
                        "type": "video",  # Keep for backwards compatibility
                        "segment_start": None,
                        "segment_end": None
                    })
            
            cursor.close()
            connection.close()
            
            logger.info(f"✅ Found {len(results)} similar videos to {video_id}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error finding similar videos: {str(e)}")
            return []


class ContentModerator:
    """Detect and flag inappropriate content"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or TWELVE_LABS_API_KEY
        self.base_url = TWELVE_LABS_API_URL
        
    async def analyze_content(self, video_id: str) -> Dict[str, Any]:
        """Analyze video content for moderation
        
        Args:
            video_id: TwelveLabs video ID
            
        Returns:
            Dict containing moderation analysis results
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Use TwelveLabs to generate summary which can indicate content type
                response = await client.post(
                    f"{self.base_url}/generate",
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "video_id": video_id,
                        "types": ["summary", "topic"]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    summary = data.get("summary", "")
                    topics = data.get("topics", [])
                    
                    # Simple keyword-based moderation (can be enhanced with ML models)
                    sensitive_keywords = [
                        "violence", "violent", "graphic", "explicit",
                        "weapon", "blood", "injury", "accident"
                    ]
                    
                    flags = []
                    for keyword in sensitive_keywords:
                        if keyword in summary.lower() or any(keyword in t.lower() for t in topics):
                            flags.append(keyword)
                    
                    result = {
                        "success": True,
                        "video_id": video_id,
                        "is_safe": len(flags) == 0,
                        "flags": flags,
                        "confidence": 1.0 - (len(flags) * 0.2),  # Simple confidence score
                        "summary": summary,
                        "topics": topics
                    }
                    
                    logger.info(f"✅ Content analysis for {video_id}: {'Safe' if result['is_safe'] else 'Flagged'}")
                    return result
                else:
                    logger.error(f"❌ Failed content analysis: {response.text}")
                    return {"success": False, "error": response.text}
                    
        except Exception as e:
            logger.error(f"❌ Error analyzing content: {str(e)}")
            return {"success": False, "error": str(e)}


# Convenience functions for easy imports
async def extract_video_highlights(video_id: str, max_highlights: int = 5) -> Dict[str, Any]:
    """Extract highlights from a video"""
    extractor = VideoHighlightsExtractor()
    return await extractor.extract_highlights(video_id, max_highlights)


async def generate_auto_tags(video_id: str) -> Dict[str, Any]:
    """Generate automatic tags for a video"""
    tagger = AutoTagger()
    return await tagger.generate_tags(video_id)


def find_similar_media(media_id: int, media_type: str = "photo", 
                      top_k: int = 10, min_similarity: float = 0.7) -> List[Dict[str, Any]]:
    """Find similar media items"""
    finder = SimilarMediaFinder()
    if media_type == "photo":
        return finder.find_similar_photos(media_id, top_k, min_similarity)
    else:
        return finder.find_similar_videos(media_id, top_k, min_similarity)


async def moderate_content(video_id: str) -> Dict[str, Any]:
    """Analyze content for moderation"""
    moderator = ContentModerator()
    return await moderator.analyze_content(video_id)


if __name__ == "__main__":
    import asyncio
    
    # Example usage
    async def main():
        print("🎬 AI Features Module")
        print("=" * 50)
        
        # Test with a sample video ID (replace with actual ID)
        video_id = "sample_video_id"
        
        print("\n1. Extracting video highlights...")
        highlights = await extract_video_highlights(video_id)
        print(f"Results: {highlights}")
        
        print("\n2. Generating auto-tags...")
        tags = await generate_auto_tags(video_id)
        print(f"Tags: {tags}")
        
        print("\n3. Finding similar media...")
        similar = find_similar_media(1, "photo", top_k=5)
        print(f"Similar items: {len(similar)}")
        
        print("\n4. Content moderation...")
        moderation = await moderate_content(video_id)
        print(f"Safe: {moderation.get('is_safe', 'Unknown')}")
    
    asyncio.run(main())
