#!/usr/bin/env python3
"""Video thumbnail generation at specific timestamps using FFmpeg"""
import os
import subprocess
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def generate_video_thumbnail(video_path: str, timestamp_seconds: float, output_path: str = None) -> str:
    """Generate a thumbnail from a video at a specific timestamp
    
    Args:
        video_path: Path to the video file (local)
        timestamp_seconds: Timestamp in seconds where to extract the frame
        output_path: Optional output path for the thumbnail. If None, creates temp file
        
    Returns:
        Path to the generated thumbnail image
    """
    try:
        # Create output path if not provided
        if output_path is None:
            temp_dir = tempfile.gettempdir()
            video_name = Path(video_path).stem
            output_path = os.path.join(temp_dir, f"{video_name}_t{int(timestamp_seconds)}.jpg")
        
        # FFmpeg command to extract frame at specific timestamp
        # -ss: seek to timestamp
        # -i: input file
        # -vframes 1: extract only 1 frame
        # -q:v 2: quality (2 is high quality, 1-31 scale)
        # -vf scale: resize to reasonable thumbnail size (width=320, height=-1 preserves aspect ratio)
        cmd = [
            'ffmpeg',
            '-ss', str(timestamp_seconds),  # Seek to timestamp
            '-i', video_path,                # Input file
            '-vframes', '1',                 # Extract 1 frame
            '-q:v', '2',                     # High quality
            '-vf', 'scale=320:-1',           # Resize to 320px width
            '-y',                            # Overwrite output file
            output_path
        ]
        
        # Run FFmpeg
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10  # 10 second timeout
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"✅ Generated thumbnail at {timestamp_seconds}s: {output_path}")
            return output_path
        else:
            logger.error(f"❌ FFmpeg failed: {result.stderr.decode()}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ Thumbnail generation timed out for {video_path}")
        return None
    except Exception as e:
        logger.exception(f"❌ Failed to generate thumbnail: {e}")
        return None


def format_timestamp(seconds: float) -> str:
    """Format seconds to MM:SS or HH:MM:SS"""
    if seconds is None:
        return "00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"
