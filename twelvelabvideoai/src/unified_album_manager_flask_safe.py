#!/usr/bin/env python3
"""Flask-Safe Unified Album Media Processing

This module handles both photo and video uploads in a unified album structure,
using threading-based timeouts instead of signal-based timeouts for Flask compatibility.
"""
import os
import sys
import mimetypes
from pathlib import Path
import oracledb
from dotenv import load_dotenv
from utils.db_utils_flask_safe import get_flask_safe_connection, flask_safe_execute_query, flask_safe_insert_vector_data
import logging
import time
import uuid

load_dotenv()
logger = logging.getLogger(__name__)

class FlaskSafeUnifiedAlbumManager:
    """Flask-safe manager for unified album operations"""
    
    def __init__(self):
        self.supported_video_types = {
            'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm',
            'video/x-flv', 'video/x-ms-wmv', 'video/3gpp', 'video/x-matroska',
            'video/mpeg', 'video/mpg', 'video/x-mpeg', 'video/x-mpg',  # Added MPEG formats
            'video/mov', 'video/avi'  # Added common video formats
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
                           oci_bucket=None, oci_object_path=None, 
                           latitude=None, longitude=None, gps_altitude=None,
                           city=None, state=None, country=None, country_code=None,
                           capture_date=None, camera_make=None, camera_model=None,
                           orientation=None, start_time=None, end_time=None,
                           video_duration=None, **kwargs):
        """Store media metadata in unified album_media table using Flask-safe connection
        
        Args:
            album_name: Name of the album
            file_name: Name of the media file
            file_path: Full path to the file
            file_type: Type of media ('photo' or 'video')
            mime_type: MIME type of the file
            file_size: Size of the file in bytes
            oci_namespace: OCI namespace
            oci_bucket: OCI bucket name
            oci_object_path: Path in OCI bucket
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            gps_altitude: GPS altitude in meters
            city: City name from GPS coordinates
            state: State/province name
            country: Country name
            country_code: Country code (e.g., 'US', 'UK')
            capture_date: Date/time photo was captured
            camera_make: Camera manufacturer
            camera_model: Camera model
            orientation: Image orientation (EXIF)
            start_time: Video start time (required for videos)
            end_time: Video end time (required for videos)
            video_duration: Video duration in seconds
            **kwargs: Additional metadata fields
        """
        
        try:
            logger.info(f"📝 Storing metadata for {file_name} in album {album_name}")
            
            # For videos, ensure start_time and end_time are set (database constraint)
            if file_type == 'video':
                if start_time is None:
                    start_time = 0  # Default start at 0 seconds
                if end_time is None and video_duration:
                    end_time = video_duration  # Use duration as end time
                elif end_time is None:
                    end_time = 0  # Default if no duration available
            
            # Insert into album_media table (ID is auto-generated)
            insert_data = {
                'album_name': album_name,
                'file_name': file_name,
                'file_path': file_path,
                'file_type': file_type,
                'mime_type': mime_type or 'application/octet-stream',
                'file_size': file_size or 0,
                'oci_namespace': oci_namespace,
                'oci_bucket': oci_bucket,
                'oci_object_path': oci_object_path,
                'latitude': latitude,
                'longitude': longitude,
                'gps_altitude': gps_altitude,
                'city': city,
                'state': state,
                'country': country,
                'country_code': country_code,
                'capture_date': capture_date,
                'camera_make': camera_make,
                'camera_model': camera_model,
                'orientation': orientation,
                'start_time': start_time,
                'end_time': end_time
            }
            
            # Log GPS info if available
            if latitude and longitude:
                logger.info(f"📍 GPS: {latitude}, {longitude} | Location: {city}, {country}")
            
            # Use Flask-safe database operations
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
                
                # Build insert query
                columns = list(insert_data.keys())
                placeholders = [':' + col for col in columns]
                
                query = f"""
                INSERT INTO album_media ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id INTO :ret_id
                """
                
                # Create variable to hold returned ID
                ret_id = cursor.var(int)
                insert_data['ret_id'] = ret_id
                
                cursor.execute(query, insert_data)
                conn.commit()
                
                generated_id = ret_id.getvalue()[0]
                logger.info(f"✅ Metadata stored successfully with id: {generated_id}")
                return generated_id
                
        except Exception as e:
            logger.error(f"❌ Error storing media metadata: {e}")
            raise
    
    def list_albums(self):
        """List all albums using Flask-safe connection"""
        try:
            logger.info("📋 Listing albums...")
            
            query = """
            SELECT album_name, 
                   COUNT(*) as total_items,
                   SUM(CASE WHEN file_type = 'photo' THEN 1 ELSE 0 END) as photo_count,
                   SUM(CASE WHEN file_type = 'video' THEN 1 ELSE 0 END) as video_count,
                   MIN(created_at) as created_at
            FROM album_media 
            GROUP BY album_name 
            ORDER BY created_at DESC
            """
            
            results = flask_safe_execute_query(query)
            
            albums = []
            for row in results:
                album = {
                    'album_id': row[0],  # Using album_name as ID
                    'album_name': row[0],
                    'total_items': row[1],
                    'photo_count': row[2],
                    'video_count': row[3],
                    'created_at': row[4],
                    'description': f"{row[1]} items ({row[2]} photos, {row[3]} videos)"
                }
                albums.append(album)
            
            logger.info(f"✅ Found {len(albums)} albums")
            return albums
            
        except Exception as e:
            logger.error(f"❌ Error listing albums: {e}")
            return []
    
    def get_album_contents(self, album_name):
        """Get contents of a specific album"""
        try:
            query = """
            SELECT id, file_name, file_type, mime_type, file_size, created_at, file_path
            FROM album_media 
            WHERE album_name = :album_name
            ORDER BY created_at DESC
            """
            
            results = flask_safe_execute_query(query, {'album_name': album_name})
            
            contents = []
            for row in results:
                item = {
                    'media_id': row[0],
                    'file_name': row[1],
                    'file_type': row[2],
                    'mime_type': row[3],
                    'file_size': row[4],
                    'created_at': row[5],
                    'file_path': row[6]
                }
                contents.append(item)
            
            return contents
            
        except Exception as e:
            logger.error(f"❌ Error getting album contents: {e}")
            return []

# Create Flask-safe instance
flask_safe_album_manager = FlaskSafeUnifiedAlbumManager()

def test_flask_safe_album_manager():
    """Test the Flask-safe album manager"""
    try:
        logger.info("🧪 Testing Flask-safe album manager...")
        
        # Test album listing
        albums = flask_safe_album_manager.list_albums()
        logger.info(f"✅ Album listing test successful: {len(albums)} albums found")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Flask-safe album manager test failed: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_flask_safe_album_manager()