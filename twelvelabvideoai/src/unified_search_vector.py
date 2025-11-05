#!/usr/bin/env python3
"""Enhanced unified search with Oracle VECTOR support

This module provides high-performance unified search across both photos and videos
using Oracle VECTOR native similarity functions for improved accuracy and speed.
"""
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from query_photo_embeddings_vector import search_photos_multiple_enhanced
from query_video_embeddings_vector import search_videos_multiple_enhanced
from utils.db_utils_vector import get_health_status
import time
import concurrent.futures

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_TOP_K = int(os.getenv('DEFAULT_TOP_K', '10'))
SEARCH_TIMEOUT = int(os.getenv('SEARCH_TIMEOUT', '30'))  # seconds
PARALLEL_SEARCH = os.getenv('PARALLEL_SEARCH', 'true').lower() == 'true'


def unified_search_enhanced(query_texts: List[str], 
                           top_k_photos: int = None,
                           top_k_videos: int = None,
                           album_name: str = None,
                           similarity_type: str = 'COSINE',
                           min_similarity: float = None,
                           timeout: int = None) -> Dict[str, Any]:
    """Enhanced unified search across photos and videos with Oracle VECTOR
    
    Args:
        query_texts: List of text queries or single query string
        top_k_photos: Number of top photo results per query
        top_k_videos: Number of top video results per query
        album_name: Optional album filter for photos (ignored for videos)
        similarity_type: 'COSINE', 'DOT', or 'EUCLIDEAN'
        min_similarity: Optional minimum similarity threshold
        timeout: Search timeout in seconds
        
    Returns:
        Dict: {
            'photo_results': {query: [results]},
            'video_results': {query: [results]},
            'summary': {query: {'photo_count': int, 'video_count': int, 'total_time': float}},
            'performance': {'total_time': float, 'photo_time': float, 'video_time': float}
        }
    """
    # Normalize inputs
    if isinstance(query_texts, str):
        query_texts = [query_texts]
    
    if top_k_photos is None:
        top_k_photos = DEFAULT_TOP_K
    if top_k_videos is None:
        top_k_videos = DEFAULT_TOP_K
    if timeout is None:
        timeout = SEARCH_TIMEOUT
    
    logger.info(f"Unified search for {len(query_texts)} queries: {query_texts}")
    logger.info(f"Photo results: {top_k_photos}, Video results: {top_k_videos}")
    logger.info(f"Similarity type: {similarity_type}, Parallel: {PARALLEL_SEARCH}")
    
    start_time = time.time()
    
    # Initialize results
    results = {
        'photo_results': {},
        'video_results': {},
        'summary': {},
        'performance': {
            'total_time': 0.0,
            'photo_time': 0.0,
            'video_time': 0.0,
            'parallel_execution': PARALLEL_SEARCH
        }
    }
    
    try:
        if PARALLEL_SEARCH:
            # Execute photo and video searches in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both search tasks
                photo_future = executor.submit(
                    _search_photos_with_timing,
                    query_texts, album_name, top_k_photos, similarity_type, min_similarity
                )
                video_future = executor.submit(
                    _search_videos_with_timing,
                    query_texts, top_k_videos, similarity_type, min_similarity
                )
                
                # Wait for completion with timeout
                try:
                    photo_results, photo_time = photo_future.result(timeout=timeout)
                    video_results, video_time = video_future.result(timeout=timeout)
                    
                    results['photo_results'] = photo_results
                    results['video_results'] = video_results
                    results['performance']['photo_time'] = photo_time
                    results['performance']['video_time'] = video_time
                    
                except concurrent.futures.TimeoutError:
                    logger.error(f"Search timed out after {timeout} seconds")
                    # Cancel pending futures
                    photo_future.cancel()
                    video_future.cancel()
                    
        else:
            # Execute searches sequentially
            photo_results, photo_time = _search_photos_with_timing(
                query_texts, album_name, top_k_photos, similarity_type, min_similarity
            )
            video_results, video_time = _search_videos_with_timing(
                query_texts, top_k_videos, similarity_type, min_similarity
            )
            
            results['photo_results'] = photo_results
            results['video_results'] = video_results
            results['performance']['photo_time'] = photo_time
            results['performance']['video_time'] = video_time
        
        # Build summary for each query
        for query in query_texts:
            photo_count = len(results['photo_results'].get(query, []))
            video_count = len(results['video_results'].get(query, []))
            
            results['summary'][query] = {
                'photo_count': photo_count,
                'video_count': video_count,
                'total_count': photo_count + video_count
            }
        
        # Calculate total time
        results['performance']['total_time'] = time.time() - start_time
        
        # Log summary
        total_photos = sum(len(results['photo_results'].get(q, [])) for q in query_texts)
        total_videos = sum(len(results['video_results'].get(q, [])) for q in query_texts)
        
        logger.info(f"Unified search completed in {results['performance']['total_time']:.3f}s")
        logger.info(f"Found {total_photos} photos and {total_videos} videos")
        
        return results
        
    except Exception as e:
        logger.error(f"Unified search failed: {e}")
        # Return empty results with error info
        for query in query_texts:
            results['photo_results'][query] = []
            results['video_results'][query] = []
            results['summary'][query] = {
                'photo_count': 0, 
                'video_count': 0, 
                'total_count': 0,
                'error': str(e)
            }
        
        results['performance']['total_time'] = time.time() - start_time
        return results


def _search_photos_with_timing(query_texts: List[str], 
                              album_name: str = None,
                              top_k: int = None,
                              similarity_type: str = 'COSINE',
                              min_similarity: float = None) -> tuple:
    """Search photos with timing measurement"""
    start_time = time.time()
    
    try:
        photo_results = search_photos_multiple_enhanced(
            query_texts, album_name, top_k, similarity_type
        )
        
        # Apply similarity filter if specified
        if min_similarity is not None:
            for query in photo_results:
                if similarity_type == 'COSINE':
                    # For cosine distance, lower values = more similar
                    photo_results[query] = [
                        r for r in photo_results[query] 
                        if r['similarity_score'] <= (1.0 - min_similarity)
                    ]
                else:
                    photo_results[query] = [
                        r for r in photo_results[query] 
                        if r['similarity_score'] >= min_similarity
                    ]
        
        search_time = time.time() - start_time
        logger.info(f"Photo search completed in {search_time:.3f}s")
        return photo_results, search_time
        
    except Exception as e:
        logger.error(f"Photo search error: {e}")
        search_time = time.time() - start_time
        return {q: [] for q in query_texts}, search_time


def _search_videos_with_timing(query_texts: List[str],
                              top_k: int = None,
                              similarity_type: str = 'COSINE',
                              min_similarity: float = None) -> tuple:
    """Search videos with timing measurement"""
    start_time = time.time()
    
    try:
        video_results = search_videos_multiple_enhanced(
            query_texts, top_k, similarity_type
        )
        
        # Apply similarity filter if specified
        if min_similarity is not None:
            for query in video_results:
                if similarity_type == 'COSINE':
                    # For cosine distance, lower values = more similar
                    video_results[query] = [
                        r for r in video_results[query] 
                        if r['similarity_score'] <= (1.0 - min_similarity)
                    ]
                else:
                    video_results[query] = [
                        r for r in video_results[query] 
                        if r['similarity_score'] >= min_similarity
                    ]
        
        search_time = time.time() - start_time
        logger.info(f"Video search completed in {search_time:.3f}s")
        return video_results, search_time
        
    except Exception as e:
        logger.error(f"Video search error: {e}")
        search_time = time.time() - start_time
        return {q: [] for q in query_texts}, search_time


def format_unified_results_enhanced(results: Dict[str, Any], 
                                   show_performance: bool = True) -> str:
    """Format unified search results for display
    
    Args:
        results: Results from unified_search_enhanced
        show_performance: Whether to include performance metrics
        
    Returns:
        str: Formatted results string
    """
    output = []
    
    # Header
    output.append("🔍 UNIFIED SEARCH RESULTS (Oracle VECTOR)")
    output.append("=" * 60)
    
    # Performance summary
    if show_performance and 'performance' in results:
        perf = results['performance']
        output.append(f"⏱️  Performance:")
        output.append(f"   Total time: {perf['total_time']:.3f}s")
        output.append(f"   Photo search: {perf['photo_time']:.3f}s")
        output.append(f"   Video search: {perf['video_time']:.3f}s")
        output.append(f"   Parallel execution: {perf.get('parallel_execution', False)}")
        output.append("")
    
    # Results by query
    for query, summary in results.get('summary', {}).items():
        output.append(f"📝 Query: \"{query}\"")
        output.append(f"   Photos: {summary['photo_count']}, Videos: {summary['video_count']}")
        
        if 'error' in summary:
            output.append(f"   ❌ Error: {summary['error']}")
        
        # Photo results
        photo_results = results.get('photo_results', {}).get(query, [])
        if photo_results:
            output.append(f"   📷 Top photos:")
            for i, photo in enumerate(photo_results[:3], 1):  # Show top 3
                output.append(f"      {i}. {photo['album_name']}: {photo['photo_file']} "
                             f"(similarity: {photo['similarity_score']:.4f})")
        
        # Video results
        video_results = results.get('video_results', {}).get(query, [])
        if video_results:
            output.append(f"   🎥 Top videos:")
            for i, video in enumerate(video_results[:3], 1):  # Show top 3
                output.append(f"      {i}. {video['video_file']} "
                             f"({video['start_time']:.1f}s-{video['end_time']:.1f}s) "
                             f"(similarity: {video['similarity_score']:.4f})")
        
        output.append("")
    
    return "\n".join(output)


def benchmark_unified_search(query_texts: List[str], iterations: int = 5) -> Dict[str, Any]:
    """Benchmark unified search performance
    
    Args:
        query_texts: Test queries
        iterations: Number of test iterations
        
    Returns:
        Dict: Benchmark results
    """
    logger.info(f"Benchmarking unified search with {iterations} iterations")
    
    benchmark_results = {
        'queries': query_texts,
        'iterations': iterations,
        'times': [],
        'photo_times': [],
        'video_times': [],
        'result_counts': [],
        'avg_total_time': 0.0,
        'avg_photo_time': 0.0,
        'avg_video_time': 0.0
    }
    
    for i in range(iterations):
        logger.info(f"Benchmark iteration {i+1}/{iterations}")
        
        results = unified_search_enhanced(query_texts, top_k_photos=5, top_k_videos=5)
        
        # Collect timing data
        perf = results.get('performance', {})
        benchmark_results['times'].append(perf.get('total_time', 0.0))
        benchmark_results['photo_times'].append(perf.get('photo_time', 0.0))
        benchmark_results['video_times'].append(perf.get('video_time', 0.0))
        
        # Collect result counts
        total_results = 0
        for query in query_texts:
            summary = results.get('summary', {}).get(query, {})
            total_results += summary.get('total_count', 0)
        benchmark_results['result_counts'].append(total_results)
    
    # Calculate averages
    if benchmark_results['times']:
        benchmark_results['avg_total_time'] = sum(benchmark_results['times']) / len(benchmark_results['times'])
        benchmark_results['avg_photo_time'] = sum(benchmark_results['photo_times']) / len(benchmark_results['photo_times'])
        benchmark_results['avg_video_time'] = sum(benchmark_results['video_times']) / len(benchmark_results['video_times'])
    
    logger.info(f"Benchmark completed: avg total time {benchmark_results['avg_total_time']:.3f}s")
    
    return benchmark_results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced unified search with Oracle VECTOR')
    parser.add_argument('queries', nargs='*', help='Search query texts')
    parser.add_argument('--top-k-photos', type=int, default=DEFAULT_TOP_K, help='Number of photo results per query')
    parser.add_argument('--top-k-videos', type=int, default=DEFAULT_TOP_K, help='Number of video results per query')
    parser.add_argument('--album', help='Filter photos by album name')
    parser.add_argument('--similarity', choices=['COSINE', 'DOT', 'EUCLIDEAN'], 
                       default='COSINE', help='Similarity metric')
    parser.add_argument('--min-similarity', type=float, help='Minimum similarity threshold')
    parser.add_argument('--timeout', type=int, default=SEARCH_TIMEOUT, help='Search timeout in seconds')
    parser.add_argument('--benchmark', action='store_true', help='Run performance benchmark')
    parser.add_argument('--iterations', type=int, default=5, help='Benchmark iterations')
    parser.add_argument('--health-check', action='store_true', help='Check system health')
    parser.add_argument('--no-performance', action='store_true', help='Hide performance metrics')
    
    args = parser.parse_args()
    
    if args.health_check:
        print("System Health Check:")
        health = get_health_status()
        for key, value in health.items():
            print(f"  {key}: {value}")
        sys.exit(0)
    
    if not args.queries:
        print("At least one query required")
        sys.exit(1)
    
    if args.benchmark:
        print(f"Benchmarking unified search with queries: {args.queries}")
        benchmark = benchmark_unified_search(args.queries, args.iterations)
        
        print(f"\nBenchmark Results:")
        print(f"  Queries: {benchmark['queries']}")
        print(f"  Iterations: {benchmark['iterations']}")
        print(f"  Average total time: {benchmark['avg_total_time']:.3f}s")
        print(f"  Average photo time: {benchmark['avg_photo_time']:.3f}s")
        print(f"  Average video time: {benchmark['avg_video_time']:.3f}s")
        print(f"  Average results: {sum(benchmark['result_counts'])/len(benchmark['result_counts']):.1f}")
        sys.exit(0)
    
    print(f"🔍 Unified Search with Oracle VECTOR")
    print(f"Queries: {args.queries}")
    print(f"Photo results: {args.top_k_photos}, Video results: {args.top_k_videos}")
    if args.album:
        print(f"Album filter: {args.album}")
    print(f"Similarity: {args.similarity}")
    print("-" * 60)
    
    # Perform unified search
    results = unified_search_enhanced(
        query_texts=args.queries,
        top_k_photos=args.top_k_photos,
        top_k_videos=args.top_k_videos,
        album_name=args.album,
        similarity_type=args.similarity,
        min_similarity=args.min_similarity,
        timeout=args.timeout
    )
    
    # Display results
    output = format_unified_results_enhanced(results, not args.no_performance)
    print(output)