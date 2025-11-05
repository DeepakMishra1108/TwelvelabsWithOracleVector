#!/usr/bin/env python3
"""Enhanced video embeddings query with Oracle VECTOR similarity search

This module provides high-performance semantic search for videos using Oracle VECTOR
native similarity functions for improved accuracy and speed.
"""
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from twelvelabs import TwelveLabs
from utils.db_utils_vector import (
    get_db_connection, 
    vector_similarity_search,
    create_vector_from_list,
    get_health_status
)

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TWELVELABS_API_KEY = os.getenv('TWELVE_LABS_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'Marengo-retrieval-2.7')
DEFAULT_TOP_K = int(os.getenv('DEFAULT_TOP_K', '10'))

# Initialize TwelveLabs client
if TWELVELABS_API_KEY:
    twelvelabs_client = TwelveLabs(api_key=TWELVELABS_API_KEY)
else:
    logger.warning("TWELVE_LABS_API_KEY not set")
    twelvelabs_client = None


def create_query_embedding_enhanced(query_text: str) -> Optional[List[float]]:
    """Create query embedding using TwelveLabs with enhanced error handling
    
    Args:
        query_text: Text query to embed
        
    Returns:
        List[float]: Query embedding vector, None if failed
    """
    if not twelvelabs_client:
        logger.error("TwelveLabs client not initialized")
        return None
    
    try:
        logger.debug(f"Creating embedding for query: {query_text}")
        
        # Create text embedding using current API
        response = twelvelabs_client.embed.create(
            model_name=EMBEDDING_MODEL,
            text=query_text,
            text_truncate='end'
        )
        
        if hasattr(response, 'text_embedding') and response.text_embedding:
            if hasattr(response.text_embedding, 'segments') and response.text_embedding.segments:
                # Extract embedding from first segment
                segment = response.text_embedding.segments[0]
                if hasattr(segment, 'float_') and segment.float_:
                    embedding = segment.float_
                    
                    # Ensure consistent dimension (1024 for Marengo)
                    expected_dim = 1024
                    if len(embedding) != expected_dim:
                        logger.warning(f"Query embedding dimension mismatch: {len(embedding)}, expected {expected_dim}")
                        # Adjust dimension
                        if len(embedding) > expected_dim:
                            embedding = embedding[:expected_dim]
                        else:
                            embedding.extend([0.0] * (expected_dim - len(embedding)))
                    
                    logger.debug(f"Created query embedding with {len(embedding)} dimensions")
                    return embedding
        
        logger.error("Failed to extract embedding from TwelveLabs response")
        return None
        
    except Exception as e:
        logger.error(f"Error creating query embedding: {e}")
        return None


def search_videos_vector(query_text: str, 
                        top_k: int = None,
                        similarity_type: str = 'COSINE',
                        min_similarity: float = None,
                        time_filter: Dict[str, float] = None) -> List[Dict[str, Any]]:
    """Search videos using Oracle VECTOR similarity search
    
    Args:
        query_text: Text query to search for
        top_k: Number of top results to return
        similarity_type: 'COSINE', 'DOT', or 'EUCLIDEAN'
        min_similarity: Minimum similarity threshold
        time_filter: Optional time range filter {'start': float, 'end': float}
        
    Returns:
        List[Dict]: Search results with similarity scores
    """
    if top_k is None:
        top_k = DEFAULT_TOP_K
    
    # Create query embedding
    query_embedding = create_query_embedding_enhanced(query_text)
    if not query_embedding:
        logger.error("Failed to create query embedding")
        return []
    
    try:
        connection = get_db_connection()
        
        # Build additional filters
        filters = []
        if time_filter:
            if 'start' in time_filter:
                filters.append(f"start_time >= {time_filter['start']}")
            if 'end' in time_filter:
                filters.append(f"end_time <= {time_filter['end']}")
        
        additional_filters = " AND ".join(filters) if filters else None
        
        # Perform vector similarity search
        results = vector_similarity_search(
            connection=connection,
            table='video_embeddings',
            query_vector=query_embedding,
            top_k=top_k,
            similarity_type=similarity_type,
            additional_filters=additional_filters
        )
        
        # Apply similarity threshold if specified
        if min_similarity is not None:
            if similarity_type == 'COSINE':
                # For cosine distance, lower values = more similar
                results = [r for r in results if r['similarity_score'] <= (1.0 - min_similarity)]
            else:
                # For other metrics, adapt as needed
                results = [r for r in results if r['similarity_score'] >= min_similarity]
        
        connection.close()
        
        logger.info(f"Found {len(results)} video segments for query: {query_text}")
        return results
        
    except Exception as e:
        logger.error(f"Video search failed: {e}")
        return []


def search_videos_multiple_enhanced(query_texts: List[str], 
                                   top_k: int = None,
                                   similarity_type: str = 'COSINE') -> Dict[str, List[Dict[str, Any]]]:
    """Search videos for multiple queries with enhanced performance
    
    Args:
        query_texts: List of text queries
        top_k: Number of top results per query
        similarity_type: Similarity metric to use
        
    Returns:
        Dict: Results keyed by query text
    """
    if top_k is None:
        top_k = DEFAULT_TOP_K
    
    results = {}
    
    for query in query_texts:
        logger.info(f"Searching for: {query}")
        query_results = search_videos_vector(query, top_k, similarity_type)
        results[query] = query_results
    
    return results


def search_videos_by_video_file(video_file: str, 
                               query_text: str,
                               top_k: int = None) -> List[Dict[str, Any]]:
    """Search within a specific video file
    
    Args:
        video_file: Video file path/URL to search within
        query_text: Text query
        top_k: Number of results to return
        
    Returns:
        List[Dict]: Search results within the specified video
    """
    if top_k is None:
        top_k = DEFAULT_TOP_K
    
    # Create query embedding
    query_embedding = create_query_embedding_enhanced(query_text)
    if not query_embedding:
        return []
    
    try:
        connection = get_db_connection()
        
        # Search within specific video file
        results = vector_similarity_search(
            connection=connection,
            table='video_embeddings',
            query_vector=query_embedding,
            top_k=top_k,
            similarity_type='COSINE',
            additional_filters=f"video_file = '{video_file}'"
        )
        
        connection.close()
        return results
        
    except Exception as e:
        logger.error(f"Video-specific search failed: {e}")
        return []


def get_video_statistics() -> Dict[str, Any]:
    """Get statistics about stored video embeddings
    
    Returns:
        Dict: Statistics about video embeddings
    """
    stats = {
        'total_segments': 0,
        'unique_videos': 0,
        'total_duration': 0.0,
        'avg_segment_duration': 0.0,
        'video_files': []
    }
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get basic statistics
        cursor.execute("""
            SELECT COUNT(*) as total_segments,
                   COUNT(DISTINCT video_file) as unique_videos,
                   SUM(end_time - start_time) as total_duration,
                   AVG(end_time - start_time) as avg_duration
            FROM video_embeddings
        """)
        
        row = cursor.fetchone()
        if row:
            stats['total_segments'] = row[0]
            stats['unique_videos'] = row[1]
            stats['total_duration'] = float(row[2]) if row[2] else 0.0
            stats['avg_segment_duration'] = float(row[3]) if row[3] else 0.0
        
        # Get video file list with segment counts
        cursor.execute("""
            SELECT video_file, 
                   COUNT(*) as segments,
                   MIN(start_time) as first_segment,
                   MAX(end_time) as last_segment
            FROM video_embeddings
            GROUP BY video_file
            ORDER BY COUNT(*) DESC
        """)
        
        videos = cursor.fetchall()
        for video in videos:
            stats['video_files'].append({
                'file': video[0],
                'segments': video[1],
                'duration': float(video[3] - video[2]) if video[2] and video[3] else 0.0
            })
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
    
    return stats


def benchmark_search_performance(query_text: str, iterations: int = 10) -> Dict[str, Any]:
    """Benchmark search performance with Oracle VECTOR
    
    Args:
        query_text: Test query
        iterations: Number of test iterations
        
    Returns:
        Dict: Performance metrics
    """
    import time
    
    results = {
        'query': query_text,
        'iterations': iterations,
        'times': [],
        'avg_time': 0.0,
        'min_time': float('inf'),
        'max_time': 0.0,
        'result_counts': []
    }
    
    for i in range(iterations):
        start_time = time.time()
        search_results = search_videos_vector(query_text, top_k=10)
        end_time = time.time()
        
        execution_time = end_time - start_time
        results['times'].append(execution_time)
        results['result_counts'].append(len(search_results))
        
        results['min_time'] = min(results['min_time'], execution_time)
        results['max_time'] = max(results['max_time'], execution_time)
    
    results['avg_time'] = sum(results['times']) / len(results['times'])
    
    logger.info(f"Benchmark completed: avg {results['avg_time']:.3f}s, "
                f"min {results['min_time']:.3f}s, max {results['max_time']:.3f}s")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced video search with Oracle VECTOR')
    parser.add_argument('query', help='Search query text')
    parser.add_argument('--top-k', type=int, default=DEFAULT_TOP_K, help='Number of results')
    parser.add_argument('--similarity', choices=['COSINE', 'DOT', 'EUCLIDEAN'], 
                       default='COSINE', help='Similarity metric')
    parser.add_argument('--min-similarity', type=float, help='Minimum similarity threshold')
    parser.add_argument('--video-file', help='Search within specific video file')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--benchmark', action='store_true', help='Run performance benchmark')
    parser.add_argument('--health-check', action='store_true', help='Check system health')
    
    args = parser.parse_args()
    
    if args.health_check:
        print("System Health Check:")
        health = get_health_status()
        for key, value in health.items():
            print(f"  {key}: {value}")
        sys.exit(0)
    
    if args.stats:
        print("Video Embeddings Statistics:")
        stats = get_video_statistics()
        print(f"  Total segments: {stats['total_segments']}")
        print(f"  Unique videos: {stats['unique_videos']}")
        print(f"  Total duration: {stats['total_duration']:.2f} seconds")
        print(f"  Avg segment: {stats['avg_segment_duration']:.2f} seconds")
        print(f"  Videos: {len(stats['video_files'])}")
        sys.exit(0)
    
    if args.benchmark:
        print(f"Benchmarking search performance for: {args.query}")
        benchmark = benchmark_search_performance(args.query)
        print(f"Average time: {benchmark['avg_time']:.3f}s")
        print(f"Min time: {benchmark['min_time']:.3f}s")
        print(f"Max time: {benchmark['max_time']:.3f}s")
        print(f"Avg results: {sum(benchmark['result_counts'])/len(benchmark['result_counts']):.1f}")
        sys.exit(0)
    
    print(f"Searching videos for: {args.query}")
    print(f"Using Oracle VECTOR similarity search ({args.similarity})")
    print("-" * 60)
    
    if args.video_file:
        results = search_videos_by_video_file(args.video_file, args.query, args.top_k)
    else:
        results = search_videos_vector(
            args.query, 
            args.top_k, 
            args.similarity, 
            args.min_similarity
        )
    
    if results:
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Video: {result['video_file']}")
            print(f"   Time: {result['start_time']:.2f}s - {result['end_time']:.2f}s")
            print(f"   Similarity: {result['similarity_score']:.4f}")
    else:
        print("No results found.")