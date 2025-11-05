#!/usr/bin/env python3
"""
Metadata extraction utilities for media files
Extracts EXIF data, GPS coordinates, and performs reverse geocoding
"""
import os
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

logger = logging.getLogger(__name__)

def convert_to_degrees(value):
    """Convert GPS coordinates to degrees"""
    try:
        d = float(value[0])
        m = float(value[1])
        s = float(value[2])
        return d + (m / 60.0) + (s / 3600.0)
    except (IndexError, TypeError, ValueError) as e:
        logger.error(f"Error converting GPS value {value}: {e}")
        return None

def get_gps_coordinates(gps_info: dict) -> Optional[Tuple[float, float]]:
    """Extract latitude and longitude from GPS info"""
    try:
        lat = None
        lon = None
        
        # Get latitude
        if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info:
            lat = convert_to_degrees(gps_info['GPSLatitude'])
            if lat and gps_info['GPSLatitudeRef'] != 'N':
                lat = -lat
        
        # Get longitude
        if 'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
            lon = convert_to_degrees(gps_info['GPSLongitude'])
            if lon and gps_info['GPSLongitudeRef'] != 'E':
                lon = -lon
        
        if lat is not None and lon is not None:
            return (lat, lon)
        
        return None
    except Exception as e:
        logger.error(f"Error extracting GPS coordinates: {e}")
        return None

def extract_exif_metadata(file_path_or_stream) -> Dict:
    """Extract EXIF metadata from image file
    
    Args:
        file_path_or_stream: Either a file path string or a file-like object
        
    Returns:
        Dictionary with metadata including GPS coordinates, capture date, camera model
    """
    metadata = {
        'latitude': None,
        'longitude': None,
        'capture_date': None,
        'camera_make': None,
        'camera_model': None,
        'orientation': None,
        'width': None,
        'height': None,
        'gps_altitude': None,
        'has_gps': False
    }
    
    try:
        # Open image
        if isinstance(file_path_or_stream, str):
            image = Image.open(file_path_or_stream)
        else:
            # For file-like objects (e.g., Flask file upload)
            image = Image.open(file_path_or_stream)
        
        # Get image dimensions
        metadata['width'], metadata['height'] = image.size
        
        # Extract EXIF data
        exifdata = image.getexif()
        if not exifdata:
            logger.info("No EXIF data found in image")
            return metadata
        
        # Process standard EXIF tags
        for tag_id, value in exifdata.items():
            tag = TAGS.get(tag_id, tag_id)
            
            if tag == 'DateTime' or tag == 'DateTimeOriginal':
                try:
                    metadata['capture_date'] = datetime.strptime(str(value), '%Y:%m:%d %H:%M:%S')
                except ValueError:
                    logger.warning(f"Could not parse date: {value}")
            
            elif tag == 'Make':
                metadata['camera_make'] = str(value).strip()
            
            elif tag == 'Model':
                metadata['camera_model'] = str(value).strip()
            
            elif tag == 'Orientation':
                metadata['orientation'] = int(value)
        
        # Process GPS data
        gps_info = {}
        if 0x8825 in exifdata:  # GPS IFD tag
            gps_ifd = exifdata.get_ifd(0x8825)
            
            for tag_id, value in gps_ifd.items():
                tag = GPSTAGS.get(tag_id, tag_id)
                gps_info[tag] = value
            
            if gps_info:
                metadata['has_gps'] = True
                
                # Extract coordinates
                coords = get_gps_coordinates(gps_info)
                if coords:
                    metadata['latitude'], metadata['longitude'] = coords
                    logger.info(f"GPS coordinates extracted: {coords}")
                
                # Extract altitude
                if 'GPSAltitude' in gps_info:
                    try:
                        altitude = float(gps_info['GPSAltitude'])
                        altitude_ref = gps_info.get('GPSAltitudeRef', 0)
                        if altitude_ref == 1:  # Below sea level
                            altitude = -altitude
                        metadata['gps_altitude'] = altitude
                    except (TypeError, ValueError) as e:
                        logger.warning(f"Could not parse GPS altitude: {e}")
        
        logger.info(f"Metadata extracted successfully: GPS={metadata['has_gps']}, "
                   f"Date={metadata['capture_date']}, Camera={metadata['camera_model']}")
        
    except Exception as e:
        logger.error(f"Error extracting EXIF metadata: {e}")
    
    return metadata

def reverse_geocode(latitude: float, longitude: float) -> Optional[Dict]:
    """Convert GPS coordinates to location information
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        Dictionary with city, state, country information
    """
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
        
        geolocator = Nominatim(user_agent="twelvelabs-video-ai")
        
        try:
            location = geolocator.reverse(f"{latitude}, {longitude}", timeout=10)
            
            if location and location.raw:
                address = location.raw.get('address', {})
                
                return {
                    'city': address.get('city') or address.get('town') or address.get('village'),
                    'state': address.get('state'),
                    'country': address.get('country'),
                    'country_code': address.get('country_code', '').upper(),
                    'formatted_address': location.address
                }
        
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.warning(f"Geocoding service error: {e}")
            return None
            
    except ImportError:
        logger.warning("geopy not installed - reverse geocoding not available")
        return None
    except Exception as e:
        logger.error(f"Error in reverse geocoding: {e}")
        return None

def get_full_metadata(file_path_or_stream) -> Dict:
    """Get complete metadata including EXIF and location information
    
    Args:
        file_path_or_stream: Either a file path string or a file-like object
        
    Returns:
        Complete metadata dictionary
    """
    metadata = extract_exif_metadata(file_path_or_stream)
    
    # Add location information if GPS coordinates available
    if metadata['latitude'] and metadata['longitude']:
        location = reverse_geocode(metadata['latitude'], metadata['longitude'])
        if location:
            metadata.update({
                'city': location.get('city'),
                'state': location.get('state'),
                'country': location.get('country'),
                'country_code': location.get('country_code'),
                'formatted_address': location.get('formatted_address')
            })
    
    return metadata

if __name__ == '__main__':
    # Test with sample image
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        print(f"\nExtracting metadata from: {test_file}")
        metadata = get_full_metadata(test_file)
        
        print("\n=== Metadata ===")
        for key, value in metadata.items():
            if value is not None:
                print(f"{key}: {value}")
    else:
        print("Usage: python metadata_extractor.py <image_file>")
