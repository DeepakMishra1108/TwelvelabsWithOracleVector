#!/usr/bin/env python3
"""Enhanced video embeddings storage with Oracle VECTOR support

This module creates TwelveLabs embeddings for videos and stores them using
Oracle VECTOR type for improved search performance and native similarity operations.
"""
import os
import sys
import argparse
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task
from utils.db_utils_vector import (
    get_db_connection, 
    insert_vector_embedding, 
    batch_insert_vector_embeddings,
    get_health_status
)
import oci
import json
import time

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
TWELVELABS_API_KEY = os.getenv('TWELVE_LABS_API_KEY')
PEGASUS_API_KEY = os.getenv('PEGASUS_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'Marengo-retrieval-2.7')
SEGMENT_DURATION = int(os.getenv('SEGMENT_DURATION', '10'))
BATCH_SIZE = int(os.getenv('EMBEDDING_BATCH_SIZE', '100'))

# Initialize TwelveLabs client
if TWELVELABS_API_KEY:
    twelvelabs_client = TwelveLabs(api_key=TWELVELABS_API_KEY)
else:
    logger.warning("TWELVE_LABS_API_KEY not set")
    twelvelabs_client = None


def create_video_embeddings_enhanced(client: TwelveLabs, video_url: str, 
                                   model_name: str = None, 
                                   clip_length: int = None) -> Optional[str]:
    """Create video embeddings using TwelveLabs with enhanced error handling
    
    Args:
        client: TwelveLabs client instance
        video_url: URL of the video to process
        model_name: Embedding model name (default: Marengo-retrieval-2.7)
        clip_length: Segment duration in seconds (default: 10)
        
    Returns:
        str: Task ID if successful, None otherwise
    """
    if not client:
        logger.error("TwelveLabs client not initialized")
        return None
    
    try:
        if model_name is None:
            model_name = EMBEDDING_MODEL
        if clip_length is None:
            clip_length = SEGMENT_DURATION
            
        logger.info(f"Creating embeddings for video: {video_url}")
        logger.info(f"Model: {model_name}, Clip length: {clip_length}s")
        
        # Create embedding task
        task = client.embed.task.create(
            model_name=model_name,
            video_url=video_url,
            video_clip_length=clip_length
        )
        
        if task and task.id:
            logger.info(f"Created embedding task: {task.id}")
            return task.id
        else:
            logger.error("Failed to create embedding task")
            return None
            
    except Exception as e:
        logger.error(f"Error creating video embeddings: {e}")
        return None


def wait_for_task_completion(client: TwelveLabs, task_id: str, 
                           timeout: int = 1800, 
                           poll_interval: int = 30) -> Optional[Task]:
    """Wait for embedding task to complete with enhanced monitoring
    
    Args:
        client: TwelveLabs client instance
        task_id: Task ID to monitor
        timeout: Maximum wait time in seconds (default: 30 minutes)
        poll_interval: Polling interval in seconds (default: 30s)
        
    Returns:
        Task: Completed task object, None if failed/timeout
    """
    if not client:
        logger.error("TwelveLabs client not initialized")
        return None
    
    try:
        start_time = time.time()
        logger.info(f"Waiting for task {task_id} to complete...")
        
        while time.time() - start_time < timeout:
            try:
                task = client.embed.task.retrieve(task_id)
                
                if task.status == 'ready':
                    logger.info(f"Task {task_id} completed successfully")
                    return task
                elif task.status == 'failed':
                    logger.error(f"Task {task_id} failed")
                    return None
                elif task.status in ['validating', 'pending', 'indexing']:
                    logger.info(f"Task {task_id} status: {task.status}")
                    time.sleep(poll_interval)
                else:
                    logger.warning(f"Unknown task status: {task.status}")
                    time.sleep(poll_interval)
                    
            except Exception as e:
                logger.error(f"Error checking task status: {e}")
                time.sleep(poll_interval)
        
        logger.error(f"Task {task_id} timed out after {timeout} seconds")
        return None
        
    except Exception as e:
        logger.error(f"Error waiting for task completion: {e}")
        return None


def extract_embeddings_from_task(client: TwelveLabs, task_id: str) -> List[Dict[str, Any]]:
    """Extract embeddings from completed task with enhanced data validation
    
    Args:
        client: TwelveLabs client instance
        task_id: Completed task ID
        
    Returns:
        List[Dict]: List of embedding segments with metadata
    """
    embeddings_data = []
    
    if not client:
        logger.error("TwelveLabs client not initialized")
        return embeddings_data
    
    try:
        logger.info(f"Extracting embeddings from task {task_id}")
        
        # Retrieve embeddings
        embeddings_iter = client.embed.task.list_video_embeddings(task_id)
        
        for embedding_page in embeddings_iter:
            if hasattr(embedding_page, 'video_embeddings') and embedding_page.video_embeddings:
                for segment in embedding_page.video_embeddings:
                    try:
                        # Validate embedding data
                        if (hasattr(segment, 'start_offset_sec') and 
                            hasattr(segment, 'end_offset_sec') and 
                            hasattr(segment, 'embedding_scope') and
                            hasattr(segment, 'float')):
                            
                            # Extract embedding vector
                            embedding_vector = segment.float
                            
                            # Validate vector dimensions
                            if not embedding_vector or len(embedding_vector) == 0:
                                logger.warning(f"Empty embedding vector in segment {segment.start_offset_sec}-{segment.end_offset_sec}")
                                continue
                            
                            # Ensure consistent dimension (1024 for Marengo)
                            expected_dim = 1024
                            if len(embedding_vector) != expected_dim:
                                logger.warning(f"Unexpected embedding dimension: {len(embedding_vector)}, expected {expected_dim}")
                                # Truncate or pad as needed
                                if len(embedding_vector) > expected_dim:
                                    embedding_vector = embedding_vector[:expected_dim]
                                else:
                                    # Pad with zeros if needed
                                    embedding_vector.extend([0.0] * (expected_dim - len(embedding_vector)))
                            
                            embeddings_data.append({
                                'start_time': float(segment.start_offset_sec),
                                'end_time': float(segment.end_offset_sec),
                                'embedding_vector': embedding_vector,
                                'scope': getattr(segment, 'embedding_scope', 'clip')
                            })
                            
                        else:
                            logger.warning(f"Invalid segment data structure: {segment}")
                            
                    except Exception as e:
                        logger.error(f"Error processing segment: {e}")
                        continue
            else:
                logger.warning("No video embeddings found in page")
        
        logger.info(f"Extracted {len(embeddings_data)} embedding segments")
        return embeddings_data
        
    except Exception as e:
        logger.error(f"Error extracting embeddings: {e}")
        return embeddings_data


def store_video_embeddings_vector(video_file: str, embeddings_data: List[Dict[str, Any]], 
                                batch_size: int = None) -> bool:
    """Store video embeddings using Oracle VECTOR type with batch processing
    
    Args:
        video_file: Video file path/URL
        embeddings_data: List of embedding segments
        batch_size: Batch size for database operations
        
    Returns:
        bool: Success status
    """
    if not embeddings_data:
        logger.warning("No embeddings data to store")
        return False
    
    if batch_size is None:
        batch_size = BATCH_SIZE
    
    try:
        connection = get_db_connection()
        
        # Prepare data for batch insertion
        batch_data = []
        for segment in embeddings_data:
            batch_data.append({
                'video_file': video_file,
                'start_time': segment['start_time'],
                'end_time': segment['end_time'],
                'embedding_vector': segment['embedding_vector']
            })
        
        # Process in batches
        total_success = 0
        total_failed = 0
        
        for i in range(0, len(batch_data), batch_size):
            batch = batch_data[i:i + batch_size]
            success_count, failed_count = batch_insert_vector_embeddings(
                connection, 'video_embeddings', batch
            )
            total_success += success_count
            total_failed += failed_count
            
            logger.info(f"Processed batch {i//batch_size + 1}: {success_count} success, {failed_count} failed")
        
        connection.close()
        
        logger.info(f"Storage completed: {total_success} stored, {total_failed} failed")
        return total_failed == 0
        
    except Exception as e:
        logger.error(f"Error storing video embeddings: {e}")
        return False


def process_video_complete(video_path_or_url: str, 
                         model_name: str = None, 
                         clip_length: int = None) -> bool:
    """Complete video processing pipeline with Oracle VECTOR storage
    
    Args:
        video_path_or_url: Video file path or URL
        model_name: Embedding model name
        clip_length: Segment duration in seconds
        
    Returns:
        bool: Success status
    """
    if not twelvelabs_client:
        logger.error("TwelveLabs client not available")
        return False
    
    try:
        logger.info(f"Starting video processing pipeline for: {video_path_or_url}")
        
        # Step 1: Create embeddings task
        task_id = create_video_embeddings_enhanced(
            twelvelabs_client, video_path_or_url, model_name, clip_length
        )
        
        if not task_id:
            logger.error("Failed to create embeddings task")
            return False
        
        # Step 2: Wait for completion
        completed_task = wait_for_task_completion(twelvelabs_client, task_id)
        
        if not completed_task:
            logger.error("Task did not complete successfully")
            return False
        
        # Step 3: Extract embeddings
        embeddings_data = extract_embeddings_from_task(twelvelabs_client, task_id)
        
        if not embeddings_data:
            logger.error("No embeddings extracted")
            return False
        
        # Step 4: Store in Oracle with VECTOR type
        success = store_video_embeddings_vector(video_path_or_url, embeddings_data)
        
        if success:
            logger.info(f"✅ Successfully processed video: {video_path_or_url}")
            logger.info(f"   - Task ID: {task_id}")
            logger.info(f"   - Segments: {len(embeddings_data)}")
            logger.info(f"   - Storage: Oracle VECTOR")
        else:
            logger.error(f"❌ Failed to store embeddings for: {video_path_or_url}")
        
        return success
        
    except Exception as e:
        logger.error(f"Video processing pipeline failed: {e}")
        return False


def verify_embeddings_storage(video_file: str) -> Dict[str, Any]:
    """Verify embeddings were stored correctly
    
    Args:
        video_file: Video file path/URL to check
        
    Returns:
        Dict: Verification results
    """
    results = {
        'video_file': video_file,
        'segments_count': 0,
        'vector_dimensions': [],
        'time_range': None,
        'storage_verified': False
    }
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check stored segments
        cursor.execute("""
            SELECT COUNT(*), 
                   MIN(start_time), MAX(end_time),
                   embedding_vector
            FROM video_embeddings 
            WHERE video_file = :video_file
        """, {'video_file': video_file})
        
        row = cursor.fetchone()
        if row:
            results['segments_count'] = row[0]
            if row[1] is not None and row[2] is not None:
                results['time_range'] = {'start': float(row[1]), 'end': float(row[2])}
            
            # Check vector dimensions (sample first few)
            cursor.execute("""
                SELECT embedding_vector 
                FROM video_embeddings 
                WHERE video_file = :video_file 
                AND ROWNUM <= 3
            """, {'video_file': video_file})
            
            vectors = cursor.fetchall()
            for vector_row in vectors:
                if vector_row[0]:
                    # Oracle VECTOR type returns as string, parse dimensions
                    vector_str = str(vector_row[0])
                    if vector_str.startswith('[') and vector_str.endswith(']'):
                        vector_elements = vector_str[1:-1].split(',')
                        results['vector_dimensions'].append(len(vector_elements))
            
            results['storage_verified'] = results['segments_count'] > 0
        
        cursor.close()
        connection.close()
        
        logger.info(f"Verification for {video_file}: {results['segments_count']} segments stored")
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enhanced video embeddings with Oracle VECTOR')
    parser.add_argument('video_path', help='Path to video file or URL')
    parser.add_argument('--model', default=EMBEDDING_MODEL, help='Embedding model name')
    parser.add_argument('--clip-length', type=int, default=SEGMENT_DURATION, help='Segment duration in seconds')
    parser.add_argument('--verify', action='store_true', help='Verify storage after processing')
    parser.add_argument('--health-check', action='store_true', help='Check system health')
    
    args = parser.parse_args()
    
    if args.health_check:
        print("Checking system health...")
        health = get_health_status()
        for key, value in health.items():
            print(f"  {key}: {value}")
        sys.exit(0)
    
    if not args.video_path:
        print("Video path required")
        sys.exit(1)
    
    print(f"Processing video: {args.video_path}")
    print(f"Model: {args.model}")
    print(f"Clip length: {args.clip_length}s")
    print("Using Oracle VECTOR storage for enhanced performance")
    print("-" * 60)
    
    success = process_video_complete(
        args.video_path, 
        args.model, 
        args.clip_length
    )
    
    if success:
        print("\n" + "="*60)
        print("✅ VIDEO PROCESSING COMPLETED SUCCESSFULLY")
        print("="*60)
        
        if args.verify:
            print("\nVerifying storage...")
            verification = verify_embeddings_storage(args.video_path)
            print(f"Segments stored: {verification['segments_count']}")
            if verification['time_range']:
                print(f"Time range: {verification['time_range']['start']:.2f}s - {verification['time_range']['end']:.2f}s")
            if verification['vector_dimensions']:
                print(f"Vector dimensions: {set(verification['vector_dimensions'])}")
            print(f"Storage verified: {verification['storage_verified']}")
    else:
        print("\n" + "="*60)
        print("❌ VIDEO PROCESSING FAILED")
        print("="*60)
        sys.exit(1)