#!/usr/bin/env python3
"""Unified search across photos and videos

This module provides a unified search interface that searches both
photo_embeddings and video_embeddings tables and returns separate results.
"""
import os
from dotenv import load_dotenv

# Import existing search modules
from query_photo_embeddings import search_photos_multiple
from query_video_embeddings import query_video_embeddings_multiple

load_dotenv()


def unified_search(query_texts, top_k_photos=10, top_k_videos=10, album_name=None):
    """Search across both photos and videos
    
    Args:
        query_texts: List of text queries or single query string
        top_k_photos: Number of top photo results per query
        top_k_videos: Number of top video results per query
        album_name: Optional album filter for photos (ignored for videos)
        
    Returns:
        dict: {
            'photos': {query: [results]},
            'videos': {query: [results]},
            'summary': {query: {'photo_count': int, 'video_count': int}}
        }
    """
    # Normalize to list
    if isinstance(query_texts, str):
        query_texts = [query_texts]
    
    print(f"Unified search for queries: {query_texts}")
    
    # Search photos
    photo_results = {}
    try:
        photo_results = search_photos_multiple(query_texts, album_name=album_name, top_k=top_k_photos)
        print(f"Photo search completed: {len(photo_results)} queries")
    except Exception as e:
        print(f"Photo search error: {e}")
        # Initialize empty results for each query
        photo_results = {q: [] for q in query_texts}
    
    # Search videos
    video_results = {}
    try:
        video_results = query_video_embeddings_multiple(query_texts, top_k=top_k_videos)
        print(f"Video search completed: {len(video_results)} queries")
    except Exception as e:
        print(f"Video search error: {e}")
        # Initialize empty results for each query
        video_results = {q: [] for q in query_texts}
    
    # Build summary
    summary = {}
    for query in query_texts:
        photo_count = len(photo_results.get(query, []))
        video_count = len(video_results.get(query, []))
        summary[query] = {
            'photo_count': photo_count,
            'video_count': video_count,
            'total_count': photo_count + video_count
        }
    
    return {
        'photos': photo_results,
        'videos': video_results,
        'summary': summary
    }


def format_unified_results(results):
    """Format unified search results for display
    
    Args:
        results: Output from unified_search()
        
    Returns:
        str: Formatted string representation
    """
    output = []
    
    for query, stats in results['summary'].items():
        output.append(f"\n{'='*60}")
        output.append(f"Query: '{query}'")
        output.append(f"Total results: {stats['total_count']} ({stats['photo_count']} photos, {stats['video_count']} videos)")
        output.append(f"{'='*60}")
        
        # Photos
        if stats['photo_count'] > 0:
            output.append(f"\n📷 PHOTOS ({stats['photo_count']}):")
            output.append("-" * 60)
            for i, photo in enumerate(results['photos'][query], 1):
                output.append(f"{i}. {photo['photo_file']}")
                output.append(f"   Album: {photo['album_name']}")
                output.append(f"   Similarity: {photo['similarity_score']:.4f}")
        else:
            output.append("\n📷 PHOTOS: No results found")
        
        # Videos
        if stats['video_count'] > 0:
            output.append(f"\n🎥 VIDEOS ({stats['video_count']}):")
            output.append("-" * 60)
            for i, video in enumerate(results['videos'][query], 1):
                output.append(f"{i}. {video['video_file']}")
                output.append(f"   Time: {video['start_time']:.2f}s - {video['end_time']:.2f}s")
                output.append(f"   Similarity: {video['similarity_score']:.4f}")
        else:
            output.append("\n🎥 VIDEOS: No results found")
    
    return '\n'.join(output)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python unified_search.py <query1> [query2 ...]")
        sys.exit(1)
    
    queries = sys.argv[1:]
    
    print(f"Performing unified search for: {queries}")
    print()
    
    results = unified_search(queries)
    
    print(format_unified_results(results))
