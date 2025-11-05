#!/usr/bin/env python3
"""
Image resizing utility for TwelveLabs embedding compatibility
Ensures images are under size limit while preserving quality
"""
import os
import logging
import tempfile
from PIL import Image

logger = logging.getLogger(__name__)

def resize_image_for_embedding(input_path, max_size_mb=5.0, preserve_original=True):
    """
    Resize image to be under TwelveLabs size limit (5.2 MB)
    
    Args:
        input_path: Path to the original image file
        max_size_mb: Maximum file size in MB (default 5.0 for buffer under 5.2 MB limit)
        preserve_original: If True, create a new file; if False, replace original
        
    Returns:
        tuple: (resized_path, was_resized, original_size, new_size)
               If no resize needed, resized_path == input_path
    """
    try:
        original_size = os.path.getsize(input_path)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        # Check if resize is needed
        if original_size <= max_size_bytes:
            logger.info(f"Image already under {max_size_mb}MB limit: {original_size/(1024*1024):.2f}MB")
            return (input_path, False, original_size, original_size)
        
        logger.info(f"Resizing large image: {os.path.basename(input_path)} ({original_size/(1024*1024):.1f}MB)")
        
        # Open and process image
        with Image.open(input_path) as img:
            # Convert to RGB if necessary (for PNG with alpha channel, etc.)
            if img.mode in ('RGBA', 'LA', 'P'):
                logger.info(f"Converting image from {img.mode} to RGB")
                # Create white background for transparency
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    rgb_img.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                img = rgb_img
            
            # Get original dimensions
            original_width, original_height = img.size
            logger.info(f"Original dimensions: {original_width}x{original_height}")
            
            # Try progressive resizing
            quality = 85
            scale_factor = 0.85  # Start with 85% of original size
            
            for attempt in range(6):  # Try up to 6 times
                # Calculate new dimensions
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                
                # Ensure minimum dimensions
                if new_width < 100 or new_height < 100:
                    logger.error("Image would be too small after resizing")
                    raise ValueError("Cannot resize image small enough while maintaining minimum dimensions")
                
                # Resize image
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Create temporary file for resized image
                suffix = '.jpg'  # Always save as JPEG for better compression
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_path = tmp_file.name
                
                # Save with current quality
                resized_img.save(tmp_path, 'JPEG', quality=quality, optimize=True)
                new_size = os.path.getsize(tmp_path)
                
                logger.info(f"Attempt {attempt+1}: {new_width}x{new_height}, "
                           f"quality={quality}, size={new_size/(1024*1024):.2f}MB")
                
                # Check if size is acceptable
                if new_size <= max_size_bytes:
                    logger.info(f"✅ Image resized successfully: "
                               f"{original_size/(1024*1024):.2f}MB → {new_size/(1024*1024):.2f}MB "
                               f"({original_width}x{original_height} → {new_width}x{new_height})")
                    
                    # If preserving original, return temp path
                    # If not preserving, replace original
                    if preserve_original:
                        return (tmp_path, True, original_size, new_size)
                    else:
                        os.unlink(input_path)
                        os.rename(tmp_path, input_path)
                        return (input_path, True, original_size, new_size)
                
                # Size still too large, adjust parameters for next attempt
                os.unlink(tmp_path)
                scale_factor *= 0.8  # Reduce size more aggressively
                quality = max(60, quality - 10)  # Lower quality, but not below 60
            
            # If we get here, we couldn't resize small enough
            logger.error(f"Could not resize image to under {max_size_mb}MB after 6 attempts")
            raise ValueError(f"Image too large and could not be resized to under {max_size_mb}MB")
            
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        raise

def get_image_info(image_path):
    """Get basic information about an image file"""
    try:
        with Image.open(image_path) as img:
            return {
                'size': img.size,
                'mode': img.mode,
                'format': img.format,
                'file_size': os.path.getsize(image_path)
            }
    except Exception as e:
        logger.error(f"Error getting image info: {e}")
        return None

if __name__ == '__main__':
    # Test the resize function
    import sys
    if len(sys.argv) > 1:
        test_image = sys.argv[1]
        print(f"\nTesting resize on: {test_image}")
        
        info = get_image_info(test_image)
        print(f"Original info: {info}")
        
        resized_path, was_resized, orig_size, new_size = resize_image_for_embedding(test_image)
        print(f"\nResult:")
        print(f"  Was resized: {was_resized}")
        print(f"  Original size: {orig_size/(1024*1024):.2f}MB")
        print(f"  New size: {new_size/(1024*1024):.2f}MB")
        print(f"  Resized path: {resized_path}")
        
        if was_resized:
            info = get_image_info(resized_path)
            print(f"  New dimensions: {info['size']}")
    else:
        print("Usage: python image_resizer.py <image_path>")
