"""
Video compression utility for TwelveLabs embedding compatibility

TwelveLabs has a 2GB limit for video files. This utility compresses videos
that exceed a target size (e.g., 1.5GB) to stay within limits while preserving quality.
"""

import os
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)


def get_video_info(video_path):
    """
    Get video file information using ffprobe
    
    Returns:
        dict: Video information including duration, bitrate, codec, resolution
    """
    try:
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"ffprobe failed: {result.stderr}")
            return None
        
        import json
        info = json.loads(result.stdout)
        
        # Extract key information
        format_info = info.get('format', {})
        video_stream = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
        audio_stream = next((s for s in info.get('streams', []) if s.get('codec_type') == 'audio'), None)
        
        return {
            'duration': float(format_info.get('duration', 0)),
            'bitrate': int(format_info.get('bit_rate', 0)),
            'size': int(format_info.get('size', 0)),
            'video_codec': video_stream.get('codec_name') if video_stream else None,
            'width': video_stream.get('width') if video_stream else None,
            'height': video_stream.get('height') if video_stream else None,
            'fps': eval(video_stream.get('r_frame_rate', '0/1')) if video_stream else None,
            'audio_codec': audio_stream.get('codec_name') if audio_stream else None,
            'audio_bitrate': int(audio_stream.get('bit_rate', 128000)) if audio_stream else 128000
        }
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None


def compress_video_for_embedding(video_path, max_size_gb=1.5, preserve_original=True):
    """
    Compress video to be under TwelveLabs size limit (2 GB)
    
    Args:
        video_path: Path to input video file
        max_size_gb: Target maximum size in GB (default 1.5GB for safety margin)
        preserve_original: If True, don't modify the original file
    
    Returns:
        tuple: (compressed_path, was_compressed, orig_size_bytes, new_size_bytes)
    """
    try:
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("ffmpeg not found. Install with: brew install ffmpeg")
            return (video_path, False, os.path.getsize(video_path), os.path.getsize(video_path))
        
        orig_size = os.path.getsize(video_path)
        max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)
        
        logger.info(f"Original video size: {orig_size/(1024**3):.2f}GB")
        
        # If already under limit, return original
        if orig_size <= max_size_bytes:
            logger.info(f"Video already under {max_size_gb}GB limit, no compression needed")
            return (video_path, False, orig_size, orig_size)
        
        # Get video information
        video_info = get_video_info(video_path)
        if not video_info:
            logger.warning("Could not get video info, skipping compression")
            return (video_path, False, orig_size, orig_size)
        
        duration = video_info['duration']
        if duration == 0:
            logger.warning("Video duration is 0, skipping compression")
            return (video_path, False, orig_size, orig_size)
        
        # Calculate target bitrate to achieve desired file size
        # Formula: target_size_bits = bitrate * duration
        # Leave 10% margin for container overhead
        target_size_bits = max_size_bytes * 8 * 0.9
        target_total_bitrate = int(target_size_bits / duration)
        
        # Reserve bitrate for audio (128k for stereo)
        audio_bitrate = min(video_info.get('audio_bitrate', 128000), 128000)
        target_video_bitrate = target_total_bitrate - audio_bitrate
        
        # Ensure minimum quality (don't go below 500k video bitrate)
        if target_video_bitrate < 500000:
            logger.warning(f"Target bitrate too low ({target_video_bitrate}), using 500k minimum")
            target_video_bitrate = 500000
        
        logger.info(f"Compressing video: target bitrate {target_video_bitrate/1000:.0f}k")
        
        # Create temporary output file
        file_ext = os.path.splitext(video_path)[1]
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
        temp_output.close()
        
        # Compression settings:
        # - H.264 codec (widely compatible)
        # - CRF mode with target bitrate
        # - Fast preset for reasonable speed
        # - Scale down resolution if very large (>1080p)
        
        video_filter = []
        if video_info.get('height', 0) > 1080:
            video_filter.append('scale=-2:1080')  # Scale to 1080p, maintain aspect ratio
            logger.info("Scaling video to 1080p")
        
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-c:v', 'libx264',  # H.264 video codec
            '-b:v', f'{target_video_bitrate}',  # Target video bitrate
            '-maxrate', f'{int(target_video_bitrate * 1.2)}',  # Max bitrate (20% buffer)
            '-bufsize', f'{int(target_video_bitrate * 2)}',  # Buffer size
            '-preset', 'medium',  # Encoding speed/quality tradeoff
            '-c:a', 'aac',  # AAC audio codec
            '-b:a', f'{audio_bitrate}',  # Audio bitrate
            '-movflags', '+faststart',  # Enable streaming
            '-y',  # Overwrite output
            temp_output.name
        ]
        
        # Add video filter if needed
        if video_filter:
            cmd.insert(-2, '-vf')
            cmd.insert(-2, ','.join(video_filter))
        
        logger.info(f"Running ffmpeg compression...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout for large videos
        )
        
        if result.returncode != 0:
            logger.error(f"ffmpeg compression failed: {result.stderr}")
            os.unlink(temp_output.name)
            return (video_path, False, orig_size, orig_size)
        
        new_size = os.path.getsize(temp_output.name)
        compression_ratio = (1 - new_size / orig_size) * 100
        
        logger.info(f"Compression complete: {orig_size/(1024**3):.2f}GB → {new_size/(1024**3):.2f}GB ({compression_ratio:.1f}% reduction)")
        
        # Verify compressed size is under limit
        if new_size > max_size_bytes:
            logger.warning(f"Compressed video still over limit ({new_size/(1024**3):.2f}GB), but returning it anyway")
        
        return (temp_output.name, True, orig_size, new_size)
        
    except subprocess.TimeoutExpired:
        logger.error("Video compression timed out (>10 minutes)")
        return (video_path, False, orig_size, orig_size)
    except Exception as e:
        logger.exception(f"Error compressing video: {e}")
        return (video_path, False, os.path.getsize(video_path), os.path.getsize(video_path))


def check_ffmpeg_available():
    """Check if ffmpeg is installed and available"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


if __name__ == "__main__":
    # Test video compression
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python video_compressor.py <video_path>")
        sys.exit(1)
    
    logging.basicConfig(level=logging.INFO)
    
    video_path = sys.argv[1]
    
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    print(f"Testing video compression for: {video_path}")
    print(f"Original size: {os.path.getsize(video_path)/(1024**3):.2f}GB")
    
    compressed_path, was_compressed, orig_size, new_size = compress_video_for_embedding(
        video_path,
        max_size_gb=1.5
    )
    
    if was_compressed:
        print(f"✅ Compressed: {orig_size/(1024**3):.2f}GB → {new_size/(1024**3):.2f}GB")
        print(f"Compressed file: {compressed_path}")
    else:
        print("ℹ️ No compression needed or compression failed")
