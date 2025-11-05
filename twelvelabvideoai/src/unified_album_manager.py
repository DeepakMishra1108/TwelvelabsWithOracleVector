#!/usr/bin/env python3
"""Unified Album Media Processing

This module handles both photo and video uploads in a unified album structure,
automatically detecting file types and processing embeddings accordingly.
"""
import os
import sys
import mimetypes
from pathlib import Path
import oracledb
from dotenv import load_dotenv
from utils.db_utils_vector import get_db_connection
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class UnifiedAlbumManager:
    """Manages unified album operations for both photos and videos"""
    
    def __init__(self):
        self.supported_video_types = {
            'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm',
            'video/x-flv', 'video/x-ms-wmv', 'video/3gpp', 'video/x-matroska'
        }
        self.supported_photo_types = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp',
            'image/tiff', 'image/webp', 'image/heic', 'image/heif'
        }
    
    def detect_file_type(self, file_path):
        """Detect if file is photo or video based on mime type"""
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if mime_type in self.supported_photo_types:
            return 'photo', mime_type
        elif mime_type in self.supported_video_types:
            return 'video', mime_type
        else:
            return 'unknown', mime_type
    
    def store_media_metadata(self, album_name, file_name, file_path, file_type, 
                           mime_type=None, file_size=None, oci_namespace=None, 
                           oci_bucket=None, oci_object_path=None, **kwargs):
        """Store media metadata in unified album_media table"""
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Base SQL for media metadata
            base_sql = """
            INSERT INTO album_media (
                album_name, file_name, file_path, file_type, mime_type, file_size,
                oci_namespace, oci_bucket, oci_object_path
            """
            
            base_values = """
            VALUES (
                :album_name, :file_name, :file_path, :file_type, :mime_type, :file_size,
                :oci_namespace, :oci_bucket, :oci_object_path
            """
            
            params = {
                'album_name': album_name,
                'file_name': file_name,
                'file_path': file_path,
                'file_type': file_type,
                'mime_type': mime_type,
                'file_size': file_size,
                'oci_namespace': oci_namespace,
                'oci_bucket': oci_bucket,
                'oci_object_path': oci_object_path
            }
            
            # Add type-specific fields
            if file_type == 'video':
                base_sql += ", start_time, end_time, duration"
                base_values += ", :start_time, :end_time, :duration"
                params.update({
                    'start_time': kwargs.get('start_time'),
                    'end_time': kwargs.get('end_time'),
                    'duration': kwargs.get('duration')
                })
            elif file_type == 'photo':
                base_sql += ", width, height"
                base_values += ", :width, :height"
                params.update({
                    'width': kwargs.get('width'),
                    'height': kwargs.get('height')
                })
            
            sql = base_sql + ") " + base_values + ")"
            
            cursor.execute(sql, params)
            media_id = cursor.lastrowid
            
            connection.commit()
            cursor.close()
            connection.close()
            
            logger.info(f"✅ Stored {file_type} metadata: {album_name}/{file_name}")
            return media_id
            
        except Exception as e:
            logger.error(f"❌ Error storing media metadata: {e}")
            return None
    
    def update_media_embedding(self, media_id, embedding_vector, embedding_model='Marengo-retrieval-2.7'):
        """Update media record with embedding vector"""
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            sql = """
            UPDATE album_media 
            SET embedding_vector = :embedding_vector, 
                embedding_model = :embedding_model,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :media_id
            """
            
            cursor.execute(sql, {
                'embedding_vector': embedding_vector,
                'embedding_model': embedding_model,
                'media_id': media_id
            })
            
            connection.commit()
            cursor.close()
            connection.close()
            
            logger.info(f"✅ Updated embedding for media ID: {media_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating embedding: {e}")
            return False
    
    def get_album_contents(self, album_name):
        """Get all media (photos and videos) in an album"""
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            sql = """
            SELECT id, file_name, file_path, file_type, mime_type, file_size,
                   start_time, end_time, duration, width, height,
                   oci_namespace, oci_bucket, oci_object_path,
                   created_at, updated_at,
                   CASE WHEN embedding_vector IS NOT NULL THEN 'Y' ELSE 'N' END as has_embedding
            FROM album_media 
            WHERE album_name = :album_name
            ORDER BY created_at DESC
            """
            
            cursor.execute(sql, {'album_name': album_name})
            results = cursor.fetchall()
            
            # Convert to list of dictionaries
            columns = [col[0].lower() for col in cursor.description]
            media_list = [dict(zip(columns, row)) for row in results]
            
            cursor.close()
            connection.close()
            
            return media_list
            
        except Exception as e:
            logger.error(f"❌ Error getting album contents: {e}")
            return []
    
    def list_albums(self):
        """List all albums with media counts"""
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            sql = """
            SELECT album_name,
                   COUNT(*) as total_items,
                   COUNT(CASE WHEN file_type = 'photo' THEN 1 END) as photo_count,
                   COUNT(CASE WHEN file_type = 'video' THEN 1 END) as video_count,
                   COUNT(CASE WHEN embedding_vector IS NOT NULL THEN 1 END) as embedded_count,
                   MIN(created_at) as created_at,
                   MAX(updated_at) as updated_at
            FROM album_media 
            GROUP BY album_name
            ORDER BY updated_at DESC
            """
            
            cursor.execute(sql)
            results = cursor.fetchall()
            
            # Convert to list of dictionaries
            columns = [col[0].lower() for col in cursor.description]
            albums_list = [dict(zip(columns, row)) for row in results]
            
            cursor.close()
            connection.close()
            
            return albums_list
            
        except Exception as e:
            logger.error(f"❌ Error listing albums: {e}")
            return []
    
    def search_unified_album(self, query_text, album_name=None, file_type=None, top_k=10):
        """Search across unified albums using vector similarity"""
        
        try:
            from twelvelabs import TwelveLabs
            
            # Generate embedding for query
            client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
            task = client.embed.tasks.create(
                model_name="Marengo-retrieval-2.7",
                text=query_text
            )
            
            # Wait for embedding task to complete
            status = client.embed.tasks.wait_for_done(task_id=task.id)
            task_result = client.embed.tasks.retrieve(task_id=task.id)
            query_embedding = task_result.text_embedding.float
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Build dynamic WHERE clause
            where_conditions = ["embedding_vector IS NOT NULL"]
            params = {'query_embedding': query_embedding, 'top_k': top_k}
            
            if album_name:
                where_conditions.append("album_name = :album_name")
                params['album_name'] = album_name
            
            if file_type:
                where_conditions.append("file_type = :file_type")
                params['file_type'] = file_type
            
            where_clause = " AND ".join(where_conditions)
            
            sql = f"""
            SELECT id, album_name, file_name, file_path, file_type, mime_type,
                   start_time, end_time, duration, width, height,
                   oci_namespace, oci_bucket, oci_object_path,
                   created_at, embedding_model,
                   VECTOR_DISTANCE(embedding_vector, :query_embedding, COSINE) as distance
            FROM album_media 
            WHERE {where_clause}
            ORDER BY VECTOR_DISTANCE(embedding_vector, :query_embedding, COSINE)
            FETCH FIRST :top_k ROWS ONLY
            """
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            # Convert to list of dictionaries
            columns = [col[0].lower() for col in cursor.description]
            search_results = [dict(zip(columns, row)) for row in results]
            
            cursor.close()
            connection.close()
            
            return search_results
            
        except Exception as e:
            logger.error(f"❌ Error in unified album search: {e}")
            return []

# Global instance
album_manager = UnifiedAlbumManager()

def create_unified_embedding(file_path, file_type, album_name, **kwargs):
    """Create embedding for photo or video and store in unified table"""
    
    try:
        if file_type == 'photo':
            return create_photo_embedding_unified(file_path, album_name, **kwargs)
        elif file_type == 'video':
            return create_video_embedding_unified(file_path, album_name, **kwargs)
        else:
            logger.error(f"Unsupported file type: {file_type}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error creating unified embedding: {e}")
        return None

def create_photo_embedding_unified(file_path, album_name, **kwargs):
    """Create photo embedding using TwelveLabs and store in unified table"""
    
    try:
        from twelvelabs import TwelveLabs
        
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        # Create embedding task for photo using embed.create (not embed.tasks.create)
        task = client.embed.create(
            model_name="Marengo-retrieval-2.7",
            image_url=file_path
        )
        
        # Wait for completion
        task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
        
        if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
            status = client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
            final = client.embed.tasks.retrieve(task_id=task_id)
        elif hasattr(task, 'wait_for_done'):
            task.wait_for_done(sleep_interval=2)
            final = task
        else:
            final = task
        
        # Extract embedding
        embedding_vector = None
        if hasattr(final, 'image_embedding') and getattr(final.image_embedding, 'float', None) is not None:
            embedding_vector = final.image_embedding.float
        elif getattr(final, 'image_embedding', None) is not None and hasattr(final.image_embedding, 'float_'):
            embedding_vector = final.image_embedding.float_
        elif getattr(final, 'image_embedding', None) is not None and getattr(final.image_embedding, 'segments', None):
            seg0 = final.image_embedding.segments[0]
            if hasattr(seg0, 'float_'):
                embedding_vector = seg0.float_
            elif hasattr(seg0, 'float'):
                embedding_vector = seg0.float
        
        if embedding_vector:
            # Store metadata first
            media_id = album_manager.store_media_metadata(
                album_name=album_name,
                file_name=Path(file_path).name,
                file_path=file_path,
                file_type='photo',
                **kwargs
            )
            
            if media_id:
                # Update with embedding
                album_manager.update_media_embedding(media_id, embedding_vector)
                return media_id
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Error creating photo embedding: {e}")
        return None

def create_video_embedding_unified(file_path, album_name, **kwargs):
    """Create video embedding using TwelveLabs and store in unified table"""
    
    try:
        from twelvelabs import TwelveLabs
        
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        # Create embedding task for video using embed.create (not embed.tasks.create)
        task = client.embed.create(
            model_name="Marengo-retrieval-2.7",
            video_url=file_path,
            video_clip_length=kwargs.get('clip_length', 10)
        )
        
        # Wait for completion
        task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
        
        if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
            status = client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
            final = client.embed.tasks.retrieve(task_id=task_id, embedding_option=["visual-text", "audio"])
        elif hasattr(task, 'wait_for_done'):
            task.wait_for_done(sleep_interval=2)
            final = task
        else:
            final = task
        
        media_ids = []
        
        # Process each segment
        for segment in final.segments:
            if hasattr(segment, 'embedding_scope') and segment.embedding_scope:
                for scope in segment.embedding_scope:
                    if hasattr(scope, 'embedding') and scope.embedding:
                        embedding_vector = scope.embedding.float
                        
                        # Store metadata for each segment
                        media_id = album_manager.store_media_metadata(
                            album_name=album_name,
                            file_name=f"{Path(file_path).stem}_seg_{segment.start_time}_{segment.end_time}.mp4",
                            file_path=file_path,
                            file_type='video',
                            start_time=segment.start_time,
                            end_time=segment.end_time,
                            duration=segment.end_time - segment.start_time,
                            **kwargs
                        )
                        
                        if media_id:
                            # Update with embedding
                            album_manager.update_media_embedding(media_id, embedding_vector)
                            media_ids.append(media_id)
        
        return media_ids
        
    except Exception as e:
        logger.error(f"❌ Error creating video embedding: {e}")
        return None

if __name__ == "__main__":
    # Test the unified album manager
    manager = UnifiedAlbumManager()
    print("📋 Available albums:")
    albums = manager.list_albums()
    for album in albums:
        print(f"  📁 {album['album_name']}: {album['total_items']} items ({album['photo_count']} photos, {album['video_count']} videos)")