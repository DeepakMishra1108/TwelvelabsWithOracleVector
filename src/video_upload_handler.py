#!/usr/bin/env python3
"""
Video Upload Handler with Auto-Slicing
Handles video uploads with automatic slicing for videos exceeding duration limits
"""

import os
import logging
from pathlib import Path
from video_slicer import VideoSlicer, slice_video_file

logger = logging.getLogger(__name__)

# Configuration
MAX_VIDEO_DURATION_MINUTES = 110  # 10-minute buffer from 120-minute limit
CHUNK_OVERLAP_SECONDS = 5


def check_video_duration(video_path):
    """
    Check if video needs slicing
    
    Args:
        video_path: Path to video file
        
    Returns:
        dict: {
            'needs_slicing': bool,
            'duration_seconds': float,
            'duration_formatted': str,
            'estimated_chunks': int
        }
    """
    try:
        slicer = VideoSlicer(video_path)
        
        # Get duration (this returns seconds as float)
        duration = slicer.get_video_duration()
        
        if duration is None:
            raise ValueError("Could not determine video duration")
        
        # Check if slicing is needed
        needs_slicing = slicer.needs_slicing(MAX_VIDEO_DURATION_MINUTES)
        
        # Calculate estimated chunks if slicing is needed
        estimated_chunks = 1
        if needs_slicing:
            chunks_info = slicer.calculate_chunks()
            if chunks_info:
                estimated_chunks = chunks_info['num_chunks']
        
        result = {
            'needs_slicing': needs_slicing,
            'duration_seconds': duration,
            'duration_formatted': slicer.format_duration(duration),
            'estimated_chunks': estimated_chunks
        }
        
        logger.info(f"📹 Video duration check: {result['duration_formatted']} - "
                   f"Needs slicing: {needs_slicing}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error checking video duration: {e}")
        return {
            'needs_slicing': False,
            'duration_seconds': 0,
            'duration_formatted': 'Unknown',
            'estimated_chunks': 1,
            'error': str(e)
        }


def prepare_video_for_upload(video_path, output_dir=None, progress_callback=None):
    """
    Prepare video for upload - slice if necessary
    
    Args:
        video_path: Path to video file
        output_dir: Directory for output chunks (optional)
        progress_callback: Function to call with progress updates (optional)
                          callback(stage, percent, message)
        
    Returns:
        dict: {
            'success': bool,
            'files': [list of file paths to upload],
            'is_chunked': bool,
            'chunk_count': int,
            'error': str (if error)
        }
    """
    
    def send_progress(stage, percent, message):
        """Helper to send progress updates"""
        if progress_callback:
            try:
                progress_callback(stage, percent, message)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    try:
        send_progress('validate', 0, 'Checking video duration...')
        
        # Check if video needs slicing
        duration_info = check_video_duration(video_path)
        
        if 'error' in duration_info:
            return {
                'success': False,
                'files': [],
                'is_chunked': False,
                'chunk_count': 0,
                'error': duration_info['error']
            }
        
        if not duration_info['needs_slicing']:
            # Video is short enough - return as-is
            send_progress('validate', 100, 'Video within duration limits')
            logger.info(f"✅ Video {Path(video_path).name} is within limits - no slicing needed")
            
            return {
                'success': True,
                'files': [video_path],
                'is_chunked': False,
                'chunk_count': 1,
                'duration': duration_info['duration_formatted']
            }
        
        # Video needs slicing
        estimated_chunks = duration_info['estimated_chunks']
        send_progress('slice', 10, f'Slicing video into {estimated_chunks} chunks...')
        logger.info(f"✂️ Video exceeds {MAX_VIDEO_DURATION_MINUTES} minutes - slicing into chunks")
        
        # Slice the video
        chunk_files = slice_video_file(
            video_path,
            output_dir=output_dir,
            max_chunk_minutes=MAX_VIDEO_DURATION_MINUTES,
            overlap_seconds=CHUNK_OVERLAP_SECONDS
        )
        
        if not chunk_files or len(chunk_files) == 0:
            send_progress('error', 0, 'Failed to slice video')
            return {
                'success': False,
                'files': [],
                'is_chunked': False,
                'chunk_count': 0,
                'error': 'Failed to slice video into chunks'
            }
        
        send_progress('slice', 100, f'Successfully created {len(chunk_files)} chunks')
        logger.info(f"✅ Video sliced into {len(chunk_files)} chunks")
        
        return {
            'success': True,
            'files': chunk_files,
            'is_chunked': True,
            'chunk_count': len(chunk_files),
            'original_duration': duration_info['duration_formatted'],
            'chunk_directory': str(Path(chunk_files[0]).parent)
        }
        
    except Exception as e:
        logger.error(f"❌ Error preparing video for upload: {e}")
        send_progress('error', 0, f'Error: {str(e)}')
        return {
            'success': False,
            'files': [],
            'is_chunked': False,
            'chunk_count': 0,
            'error': str(e)
        }


def create_video_metadata(video_path, is_chunk=False, chunk_index=None, total_chunks=None):
    """
    Create metadata for video file
    
    Args:
        video_path: Path to video file
        is_chunk: Whether this is a chunk of a larger video
        chunk_index: Index of this chunk (1-based)
        total_chunks: Total number of chunks
        
    Returns:
        dict: Metadata for video
    """
    path = Path(video_path)
    
    metadata = {
        'filename': path.name,
        'file_size_mb': round(path.stat().st_size / (1024 * 1024), 2),
        'is_chunk': is_chunk
    }
    
    if is_chunk:
        metadata.update({
            'chunk_index': chunk_index,
            'total_chunks': total_chunks,
            'original_filename': path.stem.rsplit('_chunk_', 1)[0] + path.suffix
        })
    
    # Get duration
    try:
        slicer = VideoSlicer(video_path)
        duration = slicer.get_video_duration()
        if duration:
            metadata['duration'] = slicer.format_duration(duration)
            metadata['duration_seconds'] = duration
    except Exception as e:
        logger.warning(f"Could not get video duration for {path.name}: {e}")
    
    return metadata


def cleanup_chunks(chunk_directory):
    """
    Clean up temporary chunk files
    
    Args:
        chunk_directory: Directory containing chunks
        
    Returns:
        bool: Success status
    """
    try:
        chunk_dir = Path(chunk_directory)
        if not chunk_dir.exists():
            logger.warning(f"Chunk directory does not exist: {chunk_directory}")
            return False
        
        # Remove all chunk files
        chunk_count = 0
        for chunk_file in chunk_dir.glob("*.mp4"):
            chunk_file.unlink()
            chunk_count += 1
        
        # Remove directory if empty
        if not any(chunk_dir.iterdir()):
            chunk_dir.rmdir()
            logger.info(f"🗑️ Cleaned up {chunk_count} chunks and removed directory")
        else:
            logger.info(f"🗑️ Cleaned up {chunk_count} chunks (directory not empty)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up chunks: {e}")
        return False


# Example usage
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python video_upload_handler.py <video_file>")
        sys.exit(1)
    
    video_file = sys.argv[1]
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Check video
    print(f"\n🎬 Checking video: {video_file}")
    duration_info = check_video_duration(video_file)
    print(f"Duration: {duration_info['duration_formatted']}")
    print(f"Needs slicing: {duration_info['needs_slicing']}")
    if duration_info['needs_slicing']:
        print(f"Estimated chunks: {duration_info['estimated_chunks']}")
    
    # Prepare for upload
    print(f"\n📦 Preparing video for upload...")
    
    def progress(stage, percent, message):
        print(f"[{stage.upper()}] {percent}% - {message}")
    
    result = prepare_video_for_upload(video_file, progress_callback=progress)
    
    if result['success']:
        print(f"\n✅ Success!")
        print(f"Files to upload: {result['chunk_count']}")
        if result['is_chunked']:
            print(f"Chunks directory: {result['chunk_directory']}")
        
        for i, file_path in enumerate(result['files'], 1):
            metadata = create_video_metadata(
                file_path, 
                is_chunk=result['is_chunked'],
                chunk_index=i,
                total_chunks=result['chunk_count']
            )
            print(f"\n  File {i}/{result['chunk_count']}:")
            print(f"    Name: {metadata['filename']}")
            print(f"    Size: {metadata['file_size_mb']} MB")
            if 'duration' in metadata:
                print(f"    Duration: {metadata['duration']}")
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
