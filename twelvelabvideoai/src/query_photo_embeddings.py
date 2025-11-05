#!/usr/bin/env python3
"""Query photo embeddings from Oracle DB using semantic search

This module searches for photos using text queries by creating embeddings
and comparing them with stored photo embeddings using cosine similarity.
"""
import os
import struct
import oracledb
from dotenv import load_dotenv
from twelvelabs import TwelveLabs
from utils.db_utils import get_db_connection

load_dotenv()

# Constants
TOP_K = 10  # Number of top results to return
EMBEDDING_MODEL = "Marengo-retrieval-2.7"


def create_query_embedding(query_text):
    """Create a Marengo embedding for a text query
    
    Args:
        query_text: Search query string
        
    Returns:
        list: Embedding vector as list of floats, or None on error
    """
    api_key = os.getenv('TWELVE_LABS_API_KEY')
    if not api_key:
        print("TWELVE_LABS_API_KEY not set")
        return None
    
    try:
        client = TwelveLabs(api_key=api_key)
        
        # Create text embedding using Marengo
        response = client.embed.create(
            model_name=EMBEDDING_MODEL,
            text=query_text,
            text_truncate="start",
        )
        
        if response.text_embedding and response.text_embedding.segments:
            if len(response.text_embedding.segments) > 1:
                print(f"Warning: Query generated {len(response.text_embedding.segments)} segments. Using only the first segment.")
            
            embedding = response.text_embedding.segments[0].float_
            return embedding
        else:
            print(f"Query embedding failed - no segments returned")
            return None
            
    except Exception as e:
        print(f"Error creating query embedding: {e}")
        return None


def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors
    
    Args:
        vec1: First embedding vector
        vec2: Second embedding vector
        
    Returns:
        float: Cosine similarity score (0-1)
    """
    # Handle dimension mismatch by truncating to minimum length
    min_len = min(len(vec1), len(vec2))
    vec1 = vec1[:min_len]
    vec2 = vec2[:min_len]
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def search_photos(query_text, album_name=None, top_k=TOP_K):
    """Search for photos using semantic search
    
    Args:
        query_text: Text query to search for
        album_name: Optional album name to filter results
        top_k: Number of top results to return
        
    Returns:
        list: List of dicts with photo_file, album_name, similarity_score
    """
    # Create query embedding
    query_embedding = create_query_embedding(query_text)
    if not query_embedding:
        return []
    
    try:
        connection = get_db_connection()
        
        cursor = connection.cursor()
        
        # Fetch all photo embeddings (optionally filtered by album)
        if album_name:
            select_sql = """
            SELECT id, album_name, photo_file, embedding_vector
            FROM photo_embeddings
            WHERE album_name = :1
            """
            cursor.execute(select_sql, (album_name,))
        else:
            select_sql = """
            SELECT id, album_name, photo_file, embedding_vector
            FROM photo_embeddings
            """
            cursor.execute(select_sql)
        
        # Calculate similarity for each photo
        results = []
        for row in cursor:
            photo_id, album, photo_file, embedding_blob = row
            
            # Deserialize embedding from BLOB
            embedding_bytes = bytes(embedding_blob.read() if hasattr(embedding_blob, 'read') else embedding_blob)
            num_floats = len(embedding_bytes) // 4
            photo_embedding = list(struct.unpack(f'{num_floats}f', embedding_bytes))
            
            # Calculate similarity
            similarity = cosine_similarity(query_embedding, photo_embedding)
            
            results.append({
                'id': photo_id,
                'album_name': album,
                'photo_file': photo_file,
                'similarity_score': similarity
            })
        
        cursor.close()
        connection.close()
        
        # Sort by similarity (descending) and return top_k
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results[:top_k]
        
    except Exception as e:
        print(f"Error searching photos: {e}")
        return []


def search_photos_multiple(query_texts, album_name=None, top_k=TOP_K):
    """Search for photos using multiple queries
    
    Args:
        query_texts: List of text queries
        album_name: Optional album name to filter results
        top_k: Number of top results per query
        
    Returns:
        dict: Results keyed by query text
    """
    results_by_query = {}
    
    for query in query_texts:
        results = search_photos(query, album_name, top_k)
        results_by_query[query] = results
    
    return results_by_query


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python query_photo_embeddings.py <query> [album_name]")
        sys.exit(1)
    
    query = sys.argv[1]
    album = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Searching for: '{query}'" + (f" in album '{album}'" if album else ""))
    print()
    
    results = search_photos(query, album)
    
    print(f"Found {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['photo_file']}")
        print(f"   Album: {result['album_name']}")
        print(f"   Similarity: {result['similarity_score']:.4f}")
        print()
