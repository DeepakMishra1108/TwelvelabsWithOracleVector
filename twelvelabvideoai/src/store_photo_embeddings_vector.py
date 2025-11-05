#!/usr/bin/env python3
"""Enhanced photo embeddings storage with Oracle VECTOR support

This module creates TwelveLabs Marengo embeddings for photos and stores them using
Oracle VECTOR type for improved search performance and native similarity operations.
"""
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from twelvelabs import TwelveLabs
from utils.db_utils_vector import (
    get_db_connection, 
    insert_vector_embedding, 
    batch_insert_vector_embeddings,
    get_health_status
)
import time

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
TWELVELABS_API_KEY = os.getenv('TWELVE_LABS_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'Marengo-retrieval-2.7')
BATCH_SIZE = int(os.getenv('EMBEDDING_BATCH_SIZE', '50'))

# Initialize TwelveLabs client
if TWELVELABS_API_KEY:
    twelvelabs_client = TwelveLabs(api_key=TWELVELABS_API_KEY)
else:
    logger.warning("TWELVE_LABS_API_KEY not set")
    twelvelabs_client = None


def create_photo_embedding_enhanced(client: TwelveLabs, image_url: str) -> Optional[List[float]]:
    """Create photo embedding using TwelveLabs with enhanced error handling
    
    Args:
        client: TwelveLabs client instance
        image_url: URL of the image to process
        
    Returns:
        List[float]: Embedding vector if successful, None otherwise
    """
    if not client:
        logger.error("TwelveLabs client not initialized")
        return None
    
    try:
        logger.debug(f"Creating embedding for image: {image_url}")
        
        # Create image embedding using current API
        response = client.embed.create(
            model_name=EMBEDDING_MODEL,
            image_url=image_url
        )
        
        if hasattr(response, 'image_embedding') and response.image_embedding:
            if hasattr(response.image_embedding, 'segments') and response.image_embedding.segments:
                # Extract embedding from first segment
                segment = response.image_embedding.segments[0]
                if hasattr(segment, 'float_') and segment.float_:
                    embedding = segment.float_
                    
                    # Ensure consistent dimension (1024 for Marengo)
                    expected_dim = 1024
                    if len(embedding) != expected_dim:
                        logger.warning(f"Photo embedding dimension mismatch: {len(embedding)}, expected {expected_dim}")
                        # Adjust dimension
                        if len(embedding) > expected_dim:
                            embedding = embedding[:expected_dim]
                        else:
                            embedding.extend([0.0] * (expected_dim - len(embedding)))
                    
                    logger.debug(f"Created photo embedding with {len(embedding)} dimensions")
                    return embedding
        
        logger.error("Failed to extract embedding from TwelveLabs response")
        return None
        
    except Exception as e:
        logger.error(f"Error creating photo embedding: {e}")
        return None


def store_photo_embedding_vector(album_name: str, photo_file: str, 
                               embedding_vector: List[float]) -> bool:
    """Store single photo embedding using Oracle VECTOR type
    
    Args:
        album_name: Album name
        photo_file: Photo file path/URL
        embedding_vector: Embedding vector
        
    Returns:
        bool: Success status
    """
    try:
        connection = get_db_connection()
        
        embedding_data = {
            'album_name': album_name,
            'photo_file': photo_file,
            'embedding_vector': embedding_vector
        }
        
        success = insert_vector_embedding(connection, 'photo_embeddings', embedding_data)
        connection.close()
        
        if success:
            logger.debug(f"Stored photo embedding: {photo_file}")
        else:
            logger.error(f"Failed to store photo embedding: {photo_file}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error storing photo embedding: {e}")
        return False


def create_photo_embeddings_for_album_enhanced(album_name: str, 
                                             photo_urls: List[str],
                                             batch_size: int = None) -> Dict[str, Any]:
    """Create and store embeddings for multiple photos with enhanced batch processing
    
    Args:
        album_name: Name of the album
        photo_urls: List of photo URLs
        batch_size: Batch size for database operations
        
    Returns:
        Dict: Results with success count and detailed errors
    """
    if not twelvelabs_client:
        return {
            'error': 'TwelveLabs client not available', 
            'success': 0, 
            'failed': 0,
            'errors': ['TWELVE_LABS_API_KEY not set']
        }
    
    if batch_size is None:
        batch_size = BATCH_SIZE
    
    results = {
        'success': 0,
        'failed': 0,
        'errors': [],
        'processing_time': 0.0,
        'embeddings_created': 0,
        'embeddings_stored': 0
    }
    
    start_time = time.time()
    
    try:
        logger.info(f"Processing {len(photo_urls)} photos for album: {album_name}")
        
        # Process photos and collect embeddings
        embeddings_batch = []
        
        for i, photo_url in enumerate(photo_urls):
            try:
                logger.info(f"Processing photo {i+1}/{len(photo_urls)}: {photo_url}")
                
                # Create embedding
                embedding = create_photo_embedding_enhanced(twelvelabs_client, photo_url)
                
                if embedding:
                    embeddings_batch.append({
                        'album_name': album_name,
                        'photo_file': photo_url,
                        'embedding_vector': embedding
                    })
                    results['embeddings_created'] += 1
                    logger.debug(f"Created embedding for: {photo_url}")
                else:
                    results['failed'] += 1
                    error_msg = f"Failed to create embedding for: {photo_url}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
                
                # Process batch when it reaches batch_size or is the last item
                if len(embeddings_batch) >= batch_size or i == len(photo_urls) - 1:
                    if embeddings_batch:
                        logger.info(f"Storing batch of {len(embeddings_batch)} embeddings...")
                        
                        connection = get_db_connection()
                        success_count, failed_count = batch_insert_vector_embeddings(
                            connection, 'photo_embeddings', embeddings_batch
                        )
                        connection.close()
                        
                        results['success'] += success_count
                        results['embeddings_stored'] += success_count
                        results['failed'] += failed_count
                        
                        if failed_count > 0:
                            results['errors'].append(f"Batch storage failed for {failed_count} embeddings")
                        
                        logger.info(f"Batch processed: {success_count} stored, {failed_count} failed")
                        embeddings_batch = []  # Reset batch
                
            except Exception as e:
                results['failed'] += 1
                error_msg = f"Error processing {photo_url}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        results['processing_time'] = time.time() - start_time
        
        logger.info(f"Album processing completed: {results['success']} success, {results['failed']} failed")
        logger.info(f"Processing time: {results['processing_time']:.2f} seconds")
        
    except Exception as e:
        error_msg = f"Album processing failed: {str(e)}"
        results['errors'].append(error_msg)
        logger.error(error_msg)
    
    return results


def verify_photo_embeddings(album_name: str) -> Dict[str, Any]:
    """Verify photo embeddings were stored correctly
    
    Args:
        album_name: Album name to verify
        
    Returns:
        Dict: Verification results
    """
    results = {
        'album_name': album_name,
        'photos_count': 0,
        'vector_dimensions': [],
        'sample_photos': [],
        'storage_verified': False
    }
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check stored photos
        cursor.execute("""
            SELECT COUNT(*), 
                   photo_file,
                   embedding_vector
            FROM photo_embeddings 
            WHERE album_name = :album_name
        """, {'album_name': album_name})
        
        rows = cursor.fetchall()
        if rows:
            results['photos_count'] = len(rows)
            
            # Sample first few photos for verification
            cursor.execute("""
                SELECT photo_file, embedding_vector
                FROM photo_embeddings 
                WHERE album_name = :album_name 
                AND ROWNUM <= 3
            """, {'album_name': album_name})
            
            samples = cursor.fetchall()
            for photo_file, vector in samples:
                results['sample_photos'].append(photo_file)
                
                if vector:
                    # Oracle VECTOR type returns as string, parse dimensions
                    vector_str = str(vector)
                    if vector_str.startswith('[') and vector_str.endswith(']'):
                        vector_elements = vector_str[1:-1].split(',')
                        results['vector_dimensions'].append(len(vector_elements))
            
            results['storage_verified'] = results['photos_count'] > 0
        
        cursor.close()
        connection.close()
        
        logger.info(f"Verification for album '{album_name}': {results['photos_count']} photos stored")
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
    
    return results


def get_album_statistics() -> Dict[str, Any]:
    """Get statistics about stored photo embeddings
    
    Returns:
        Dict: Statistics about photo albums and embeddings
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
                   COUNT(*) as photo_count,
                   MIN(created_at) as first_photo,
                   MAX(created_at) as last_photo
            FROM photo_embeddings
            GROUP BY album_name
            ORDER BY COUNT(*) DESC
        """)
        
        albums = cursor.fetchall()
        for album in albums:
            stats['albums'].append({
                'name': album[0],
                'photo_count': album[1],
                'first_photo': album[2],
                'last_photo': album[3]
            })
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"Failed to get album statistics: {e}")
    
    return stats


def migrate_album_to_vector(album_name: str) -> Dict[str, int]:
    """Migrate specific album from BLOB to VECTOR format
    
    Args:
        album_name: Album name to migrate
        
    Returns:
        Dict: Migration statistics
    """
    stats = {'migrated': 0, 'failed': 0, 'total': 0}
    
    try:
        connection = get_db_connection()
        
        # Use the migration utility from db_utils_vector
        from utils.db_utils_vector import migrate_blob_to_vector
        
        # Add album filter for photos
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM photo_embeddings WHERE album_name = :album", 
                      {'album': album_name})
        stats['total'] = cursor.fetchone()[0]
        cursor.close()
        
        if stats['total'] > 0:
            logger.info(f"Migrating {stats['total']} photos in album '{album_name}' to VECTOR format")
            
            # This would need to be enhanced to support album filtering
            # For now, log the requirement
            logger.warning("Album-specific migration not yet implemented")
            logger.info("Use the full migration script: migrate_blob_to_vector()")
        
        connection.close()
        
    except Exception as e:
        logger.error(f"Album migration failed: {e}")
    
    return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced photo embeddings with Oracle VECTOR')
    parser.add_argument('album_name', help='Album name')
    parser.add_argument('photo_urls', nargs='*', help='Photo URLs to process')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help='Batch size for processing')
    parser.add_argument('--verify', action='store_true', help='Verify storage after processing')
    parser.add_argument('--stats', action='store_true', help='Show album statistics')
    parser.add_argument('--health-check', action='store_true', help='Check system health')
    
    args = parser.parse_args()
    
    if args.health_check:
        print("System Health Check:")
        health = get_health_status()
        for key, value in health.items():
            print(f"  {key}: {value}")
        sys.exit(0)
    
    if args.stats:
        print("Photo Album Statistics:")
        stats = get_album_statistics()
        print(f"  Total photos: {stats['total_photos']}")
        print(f"  Unique albums: {stats['unique_albums']}")
        print("  Albums:")
        for album in stats['albums']:
            print(f"    {album['name']}: {album['photo_count']} photos")
        sys.exit(0)
    
    if not args.album_name:
        print("Album name required")
        sys.exit(1)
    
    if not args.photo_urls:
        print("At least one photo URL required")
        sys.exit(1)
    
    print(f"Processing album: {args.album_name}")
    print(f"Photos: {len(args.photo_urls)}")
    print(f"Batch size: {args.batch_size}")
    print("Using Oracle VECTOR storage for enhanced performance")
    print("-" * 60)
    
    results = create_photo_embeddings_for_album_enhanced(
        args.album_name, 
        args.photo_urls,
        args.batch_size
    )
    
    print(f"\nProcessing Results:")
    print(f"  Success: {results['success']}")
    print(f"  Failed: {results['failed']}")
    print(f"  Processing time: {results['processing_time']:.2f}s")
    print(f"  Embeddings created: {results['embeddings_created']}")
    print(f"  Embeddings stored: {results['embeddings_stored']}")
    
    if results['errors']:
        print(f"  Errors: {len(results['errors'])}")
        for error in results['errors'][:5]:  # Show first 5 errors
            print(f"    - {error}")
    
    if results['success'] > 0:
        print("\n" + "="*60)
        print("✅ PHOTO PROCESSING COMPLETED SUCCESSFULLY")
        print("="*60)
        
        if args.verify:
            print("\nVerifying storage...")
            verification = verify_photo_embeddings(args.album_name)
            print(f"Photos stored: {verification['photos_count']}")
            if verification['vector_dimensions']:
                print(f"Vector dimensions: {set(verification['vector_dimensions'])}")
            print(f"Storage verified: {verification['storage_verified']}")
    else:
        print("\n" + "="*60)
        print("❌ PHOTO PROCESSING FAILED")
        print("="*60)
        sys.exit(1)