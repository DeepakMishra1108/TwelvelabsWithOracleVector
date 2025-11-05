#!/usr/bin/env python3
"""Enhanced photo embeddings query with Oracle VECTOR similarity search

This module provides high-performance semantic search for photos using Oracle VECTOR
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


def search_photos_vector(query_text: str, 
                        album_name: str = None,
                        top_k: int = None,
                        similarity_type: str = 'COSINE',
                        min_similarity: float = None) -> List[Dict[str, Any]]:
    """Search photos using Oracle VECTOR similarity search
    
    Args:
        query_text: Text query to search for
        album_name: Optional album name to filter results
        top_k: Number of top results to return
        similarity_type: 'COSINE', 'DOT', or 'EUCLIDEAN'
        min_similarity: Minimum similarity threshold
        
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
        if album_name:
            filters.append(f"album_name = '{album_name}'")
        
        additional_filters = " AND ".join(filters) if filters else None
        
        # Perform vector similarity search
        results = vector_similarity_search(
            connection=connection,
            table='photo_embeddings',
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
        
        logger.info(f"Found {len(results)} photos for query: {query_text}")
        return results
        
    except Exception as e:
        logger.error(f"Photo search failed: {e}")
        return []


def search_photos_multiple_enhanced(query_texts: List[str], 
                                   album_name: str = None,
                                   top_k: int = None,
                                   similarity_type: str = 'COSINE') -> Dict[str, List[Dict[str, Any]]]:
    """Search photos for multiple queries with enhanced performance
    
    Args:
        query_texts: List of text queries
        album_name: Optional album name to filter results
        top_k: Number of top results per query
        similarity_type: Similarity metric to use
        
    Returns:
        Dict: Results keyed by query text
    """
    if top_k is None:
        top_k = DEFAULT_TOP_K
    
    results = {}
    
    for query in query_texts:
        logger.info(f"Searching photos for: {query}")
        query_results = search_photos_vector(query, album_name, top_k, similarity_type)
        results[query] = query_results
    
    return results


def search_photos_by_album(album_name: str, 
                          query_text: str,
                          top_k: int = None) -> List[Dict[str, Any]]:
    """Search within a specific album
    
    Args:
        album_name: Album name to search within
        query_text: Text query
        top_k: Number of results to return
        
    Returns:
        List[Dict]: Search results within the specified album
    """
    return search_photos_vector(query_text, album_name, top_k)


def get_similar_photos(photo_file: str, 
                      top_k: int = None,
                      same_album_only: bool = False) -> List[Dict[str, Any]]:
    """Find photos similar to a given photo using its stored embedding
    
    Args:
        photo_file: Photo file path/URL to find similar photos for
        top_k: Number of similar photos to return
        same_album_only: Whether to search only within the same album
        
    Returns:
        List[Dict]: Similar photos with similarity scores
    """
    if top_k is None:
        top_k = DEFAULT_TOP_K
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get the embedding for the reference photo
        cursor.execute("""
            SELECT album_name, embedding_vector
            FROM photo_embeddings 
            WHERE photo_file = :photo_file
        """, {'photo_file': photo_file})
        
        row = cursor.fetchone()
        if not row:
            logger.error(f"Photo not found: {photo_file}")
            return []
        
        album_name, vector_data = row
        
        # Convert Oracle VECTOR back to list (simplified approach)
        if vector_data:
            vector_str = str(vector_data)
            if vector_str.startswith('[') and vector_str.endswith(']'):
                try:
                    vector_elements = [float(x.strip()) for x in vector_str[1:-1].split(',')]
                except:
                    logger.error("Failed to parse stored vector")
                    return []
            else:
                logger.error("Invalid vector format")
                return []
        else:
            logger.error("No vector data found")
            return []
        
        # Build filters
        filters = [f"photo_file != '{photo_file}'"]  # Exclude the reference photo itself
        if same_album_only:
            filters.append(f"album_name = '{album_name}'")
        
        additional_filters = " AND ".join(filters)
        
        # Find similar photos
        results = vector_similarity_search(
            connection=connection,
            table='photo_embeddings',
            query_vector=vector_elements,
            top_k=top_k,
            similarity_type='COSINE',
            additional_filters=additional_filters
        )
        
        cursor.close()
        connection.close()
        
        logger.info(f"Found {len(results)} similar photos to: {photo_file}")
        return results
        
    except Exception as e:
        logger.error(f"Similar photo search failed: {e}")
        return []


def get_album_list() -> List[Dict[str, Any]]:
    """Get list of all albums with photo counts
    
    Returns:
        List[Dict]: Album information
    """
    albums = []
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT album_name, 
                   COUNT(*) as photo_count,
                   MIN(created_at) as first_photo,
                   MAX(created_at) as last_photo
            FROM photo_embeddings
            GROUP BY album_name
            ORDER BY album_name
        """)
        
        rows = cursor.fetchall()
        for row in rows:
            albums.append({
                'name': row[0],
                'photo_count': row[1],
                'first_photo': row[2],
                'last_photo': row[3]
            })
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"Failed to get album list: {e}")
    
    return albums


def get_photo_statistics() -> Dict[str, Any]:
    """Get statistics about stored photo embeddings
    
    Returns:
        Dict: Statistics about photo embeddings
    """
    stats = {
        'total_photos': 0,
        'unique_albums': 0,
        'albums': []
    }
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get basic statistics
        cursor.execute("""
            SELECT COUNT(*) as total_photos,
                   COUNT(DISTINCT album_name) as unique_albums
            FROM photo_embeddings
        """)
        
        row = cursor.fetchone()
        if row:
            stats['total_photos'] = row[0]
            stats['unique_albums'] = row[1]
        
        # Get album details
        cursor.execute("""
            SELECT album_name, 
                   COUNT(*) as photo_count
            FROM photo_embeddings
            GROUP BY album_name
            ORDER BY COUNT(*) DESC
        """)
        
        albums = cursor.fetchall()
        for album in albums:
            stats['albums'].append({
                'name': album[0],
                'photo_count': album[1]
            })
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
    
    return stats


def benchmark_photo_search_performance(query_text: str, iterations: int = 10) -> Dict[str, Any]:
    """Benchmark photo search performance with Oracle VECTOR
    
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
        search_results = search_photos_vector(query_text, top_k=10)
        end_time = time.time()
        
        execution_time = end_time - start_time
        results['times'].append(execution_time)
        results['result_counts'].append(len(search_results))
        
        results['min_time'] = min(results['min_time'], execution_time)
        results['max_time'] = max(results['max_time'], execution_time)
    
    results['avg_time'] = sum(results['times']) / len(results['times'])
    
    logger.info(f"Photo search benchmark completed: avg {results['avg_time']:.3f}s, "
                f"min {results['min_time']:.3f}s, max {results['max_time']:.3f}s")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced photo search with Oracle VECTOR')
    parser.add_argument('query', nargs='?', help='Search query text')
    parser.add_argument('--album', help='Search within specific album')
    parser.add_argument('--top-k', type=int, default=DEFAULT_TOP_K, help='Number of results')
    parser.add_argument('--similarity', choices=['COSINE', 'DOT', 'EUCLIDEAN'], 
                       default='COSINE', help='Similarity metric')
    parser.add_argument('--min-similarity', type=float, help='Minimum similarity threshold')
    parser.add_argument('--similar-to', help='Find photos similar to given photo file')
    parser.add_argument('--same-album-only', action='store_true', help='Search similar photos in same album only')
    parser.add_argument('--list-albums', action='store_true', help='List all albums')
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
    
    if args.list_albums:
        print("Photo Albums:")
        albums = get_album_list()
        for album in albums:
            print(f"  {album['name']}: {album['photo_count']} photos")
        sys.exit(0)
    
    if args.stats:
        print("Photo Embeddings Statistics:")
        stats = get_photo_statistics()
        print(f"  Total photos: {stats['total_photos']}")
        print(f"  Unique albums: {stats['unique_albums']}")
        print(f"  Albums: {len(stats['albums'])}")
        sys.exit(0)
    
    if args.similar_to:
        print(f"Finding photos similar to: {args.similar_to}")
        if args.same_album_only:
            print("(searching within same album only)")
        results = get_similar_photos(args.similar_to, args.top_k, args.same_album_only)
        
        if results:
            print(f"Found {len(results)} similar photos:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. Album: {result['album_name']}")
                print(f"   Photo: {result['photo_file']}")
                print(f"   Similarity: {result['similarity_score']:.4f}")
        else:
            print("No similar photos found.")
        sys.exit(0)
    
    if args.benchmark and args.query:
        print(f"Benchmarking photo search performance for: {args.query}")
        benchmark = benchmark_photo_search_performance(args.query)
        print(f"Average time: {benchmark['avg_time']:.3f}s")
        print(f"Min time: {benchmark['min_time']:.3f}s")
        print(f"Max time: {benchmark['max_time']:.3f}s")
        print(f"Avg results: {sum(benchmark['result_counts'])/len(benchmark['result_counts']):.1f}")
        sys.exit(0)
    
    if not args.query:
        print("Query required (or use --list-albums, --stats, --similar-to, etc.)")
        sys.exit(1)
    
    print(f"Searching photos for: {args.query}")
    if args.album:
        print(f"Album filter: {args.album}")
    print(f"Using Oracle VECTOR similarity search ({args.similarity})")
    print("-" * 60)
    
    results = search_photos_vector(
        args.query, 
        args.album,
        args.top_k, 
        args.similarity, 
        args.min_similarity
    )
    
    if results:
        print(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Album: {result['album_name']}")
            print(f"   Photo: {result['photo_file']}")
            print(f"   Similarity: {result['similarity_score']:.4f}")
    else:
        print("No results found.")