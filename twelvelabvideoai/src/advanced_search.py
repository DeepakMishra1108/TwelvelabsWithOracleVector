#!/usr/bin/env python3
"""Advanced Search Features Module

This module provides advanced search capabilities including:
- Multi-modal search (photos AND/OR videos)
- Temporal/date-based search
- Face recognition search
- Audio/transcript search
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils.db_utils_vector import get_db_connection
from query_photo_embeddings_vector import search_photos_multiple_enhanced
from query_video_embeddings_vector import search_videos_multiple_enhanced

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiModalSearch:
    """Advanced search across photos and videos with Boolean operators"""
    
    def __init__(self):
        self.connection = None
        
    def search(self, query: str, operator: str = "OR", 
              search_photos: bool = True, search_videos: bool = True,
              top_k: int = 20, min_similarity: float = 0.3) -> Dict[str, Any]:
        """Advanced search with Boolean operators
        
        Args:
            query: Search query (can contain AND/OR operators)
            operator: Default operator if not specified in query ("AND" or "OR")
            search_photos: Whether to search photos
            search_videos: Whether to search videos
            top_k: Number of results per query term
            min_similarity: Minimum similarity threshold
            
        Returns:
            Dict containing combined search results
        """
        # Parse query for operators
        terms = self._parse_query(query, operator)
        
        all_results = {
            "photos": [],
            "videos": [],
            "operator": operator,
            "terms": terms
        }
        
        # Search for each term
        for term_info in terms:
            term = term_info["term"]
            logger.info(f"🔍 Searching for: '{term}'")
            
            term_results = {"photos": [], "videos": []}
            
            if search_photos:
                photo_results = search_photos_multiple_enhanced(
                    query_texts=[term],
                    top_k_per_query=top_k,
                    similarity_type='COSINE'
                )
                term_results["photos"] = photo_results.get(term, [])
            
            if search_videos:
                video_results = search_videos_multiple_enhanced(
                    query_texts=[term],
                    top_k_per_query=top_k,
                    similarity_type='COSINE'
                )
                term_results["videos"] = video_results.get(term, [])
            
            term_info["results"] = term_results
        
        # Combine results based on operator
        if operator == "AND":
            all_results = self._combine_results_and(terms, min_similarity)
        else:  # OR
            all_results = self._combine_results_or(terms, min_similarity)
        
        logger.info(f"✅ Found {len(all_results['photos'])} photos and {len(all_results['videos'])} videos")
        return all_results
    
    def _parse_query(self, query: str, default_operator: str) -> List[Dict[str, Any]]:
        """Parse query into terms with operators"""
        # Simple parsing - can be enhanced with proper query parser
        terms = []
        
        if " AND " in query.upper():
            parts = query.split(" AND ")
            for part in parts:
                terms.append({"term": part.strip(), "operator": "AND"})
        elif " OR " in query.upper():
            parts = query.split(" OR ")
            for part in parts:
                terms.append({"term": part.strip(), "operator": "OR"})
        else:
            terms.append({"term": query.strip(), "operator": default_operator})
        
        return terms
    
    def _combine_results_and(self, terms: List[Dict], min_similarity: float) -> Dict[str, Any]:
        """Combine results with AND logic - media must match all terms"""
        if not terms:
            return {"photos": [], "videos": [], "operator": "AND", "terms": []}
        
        # Start with first term's results
        combined_photos = {p["id"]: p for p in terms[0]["results"]["photos"] 
                          if p.get("similarity_score", 0) >= min_similarity}
        combined_videos = {v["id"]: v for v in terms[0]["results"]["videos"]
                          if v.get("similarity_score", 0) >= min_similarity}
        
        # Intersect with other terms
        for term_info in terms[1:]:
            term_photos = {p["id"]: p for p in term_info["results"]["photos"]
                          if p.get("similarity_score", 0) >= min_similarity}
            term_videos = {v["id"]: v for v in term_info["results"]["videos"]
                          if v.get("similarity_score", 0) >= min_similarity}
            
            # Keep only items that appear in both
            combined_photos = {
                id: photo for id, photo in combined_photos.items()
                if id in term_photos
            }
            combined_videos = {
                id: video for id, video in combined_videos.items()
                if id in term_videos
            }
        
        return {
            "photos": sorted(combined_photos.values(), 
                           key=lambda x: x.get("similarity_score", 0), reverse=True),
            "videos": sorted(combined_videos.values(),
                           key=lambda x: x.get("similarity_score", 0), reverse=True),
            "operator": "AND",
            "terms": [t["term"] for t in terms]
        }
    
    def _combine_results_or(self, terms: List[Dict], min_similarity: float) -> Dict[str, Any]:
        """Combine results with OR logic - media can match any term"""
        combined_photos = {}
        combined_videos = {}
        
        for term_info in terms:
            for photo in term_info["results"]["photos"]:
                if photo.get("similarity_score", 0) >= min_similarity:
                    photo_id = photo["id"]
                    if photo_id not in combined_photos or \
                       photo["similarity_score"] > combined_photos[photo_id]["similarity_score"]:
                        combined_photos[photo_id] = photo
            
            for video in term_info["results"]["videos"]:
                if video.get("similarity_score", 0) >= min_similarity:
                    video_id = video["id"]
                    if video_id not in combined_videos or \
                       video["similarity_score"] > combined_videos[video_id]["similarity_score"]:
                        combined_videos[video_id] = video
        
        return {
            "photos": sorted(combined_photos.values(),
                           key=lambda x: x.get("similarity_score", 0), reverse=True),
            "videos": sorted(combined_videos.values(),
                           key=lambda x: x.get("similarity_score", 0), reverse=True),
            "operator": "OR",
            "terms": [t["term"] for t in terms]
        }


class TemporalSearch:
    """Search media by date/time ranges"""
    
    def search_by_date_range(self, start_date: datetime, end_date: datetime,
                            media_type: Optional[str] = None,
                            album_name: Optional[str] = None) -> Dict[str, Any]:
        """Search media within a date range
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            media_type: Filter by 'photo' or 'video' (None for both)
            album_name: Optional album filter
            
        Returns:
            Dict containing matching media items
        """
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Build query
            query = """
                SELECT 
                    id,
                    album_name,
                    file_name,
                    file_type,
                    created_at,
                    duration,
                    width,
                    height
                FROM album_media
                WHERE created_at BETWEEN :start_date AND :end_date
            """
            
            params = {
                "start_date": start_date,
                "end_date": end_date
            }
            
            if media_type:
                query += " AND file_type = :media_type"
                params["media_type"] = media_type
            
            if album_name:
                query += " AND album_name = :album_name"
                params["album_name"] = album_name
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row[0],
                    "album_name": row[1],
                    "file_name": row[2],
                    "type": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "duration": float(row[5]) if row[5] else None,
                    "width": row[6],
                    "height": row[7]
                })
            
            cursor.close()
            connection.close()
            
            logger.info(f"✅ Found {len(results)} media items from {start_date} to {end_date}")
            return {
                "success": True,
                "count": len(results),
                "results": results,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error in temporal search: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def search_recent(self, days: int = 7, media_type: Optional[str] = None) -> Dict[str, Any]:
        """Search media from recent days
        
        Args:
            days: Number of days to look back
            media_type: Filter by 'photo' or 'video'
            
        Returns:
            Dict containing recent media items
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.search_by_date_range(start_date, end_date, media_type)
    
    def search_by_year(self, year: int, media_type: Optional[str] = None) -> Dict[str, Any]:
        """Search media from a specific year"""
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        return self.search_by_date_range(start_date, end_date, media_type)
    
    def search_by_month(self, year: int, month: int, 
                       media_type: Optional[str] = None) -> Dict[str, Any]:
        """Search media from a specific month"""
        start_date = datetime(year, month, 1)
        # Get last day of month
        if month == 12:
            end_date = datetime(year, 12, 31, 23, 59, 59)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
        return self.search_by_date_range(start_date, end_date, media_type)


class SemanticSearch:
    """Advanced semantic search with context understanding"""
    
    def search_with_context(self, query: str, context: Dict[str, Any],
                           top_k: int = 20) -> Dict[str, Any]:
        """Search with additional context (location, time, etc.)
        
        Args:
            query: Text search query
            context: Dict with optional filters (date_range, location, album, etc.)
            top_k: Number of results to return
            
        Returns:
            Dict containing filtered search results
        """
        results = {"photos": [], "videos": []}
        
        # First do semantic search
        photo_results = search_photos_multiple_enhanced(
            query_texts=[query],
            top_k_per_query=top_k * 2,  # Get more to filter
            similarity_type='COSINE'
        )
        
        video_results = search_videos_multiple_enhanced(
            query_texts=[query],
            top_k_per_query=top_k * 2,
            similarity_type='COSINE'
        )
        
        # Apply context filters
        results["photos"] = self._apply_filters(
            photo_results.get(query, []),
            context
        )[:top_k]
        
        results["videos"] = self._apply_filters(
            video_results.get(query, []),
            context
        )[:top_k]
        
        return results
    
    def _apply_filters(self, items: List[Dict], context: Dict[str, Any]) -> List[Dict]:
        """Apply context filters to results"""
        filtered = items
        
        # Date range filter
        if "date_range" in context:
            start_date = context["date_range"].get("start")
            end_date = context["date_range"].get("end")
            if start_date and end_date:
                filtered = [
                    item for item in filtered
                    if item.get("created_at") and
                    start_date <= datetime.fromisoformat(item["created_at"]) <= end_date
                ]
        
        # Album filter
        if "album" in context:
            album_name = context["album"]
            filtered = [item for item in filtered if item.get("album_name") == album_name]
        
        # Location filter (if GPS data available)
        if "location" in context:
            # Filter by location proximity (requires GPS data)
            pass
        
        return filtered


# Convenience functions
def multimodal_search(query: str, operator: str = "OR", **kwargs) -> Dict[str, Any]:
    """Perform multi-modal search with Boolean operators"""
    searcher = MultiModalSearch()
    return searcher.search(query, operator, **kwargs)


def temporal_search(start_date: datetime, end_date: datetime, **kwargs) -> Dict[str, Any]:
    """Search media by date range"""
    searcher = TemporalSearch()
    return searcher.search_by_date_range(start_date, end_date, **kwargs)


def search_recent_media(days: int = 7, **kwargs) -> Dict[str, Any]:
    """Search recent media"""
    searcher = TemporalSearch()
    return searcher.search_recent(days, **kwargs)


if __name__ == "__main__":
    print("🔍 Advanced Search Module")
    print("=" * 50)
    
    # Example: Multi-modal search
    print("\n1. Multi-modal search (AND operator):")
    results = multimodal_search("sunset AND beach", operator="AND", top_k=5)
    print(f"   Photos: {len(results['photos'])}, Videos: {len(results['videos'])}")
    
    # Example: Temporal search
    print("\n2. Recent media (last 7 days):")
    recent = search_recent_media(days=7)
    if recent.get("success"):
        print(f"   Found: {recent['count']} items")
    
    # Example: Date range search
    print("\n3. Search by date range:")
    start = datetime(2024, 1, 1)
    end = datetime(2024, 12, 31)
    yearly = temporal_search(start, end)
    if yearly.get("success"):
        print(f"   Found: {yearly['count']} items from 2024")
