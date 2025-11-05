#!/usr/bin/env python3
"""
Video Slicer Utility
Splits long videos into smaller chunks to handle processing limitations
Maximum duration per chunk: 110 minutes (with 10-minute buffer from 120-minute limit)
"""

import subprocess
import json
import os
import sys
from pathlib import Path
import math

class VideoSlicer:
    """Handles splitting long videos into manageable chunks"""
    
    # Maximum duration per chunk in minutes (buffer from 120-minute limit)
    MAX_CHUNK_DURATION_MINUTES = 110
    MAX_CHUNK_DURATION_SECONDS = MAX_CHUNK_DURATION_MINUTES * 60
    
    def __init__(self, input_video_path, output_dir=None):
        """
        Initialize video slicer
        
        Args:
            input_video_path: Path to input video file
            output_dir: Directory for output chunks (default: same as input)
        """
        self.input_path = Path(input_video_path)
        if not self.input_path.exists():
            raise FileNotFoundError(f"Video file not found: {input_video_path}")
        
        # Set output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.input_path.parent / f"{self.input_path.stem}_chunks"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Video info
        self.duration = None
        self.video_info = None
        
    def get_video_duration(self):
        """Get video duration using ffprobe"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                str(self.input_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            duration = float(data['format']['duration'])
            self.duration = duration
            
            print(f"📹 Video duration: {self.format_duration(duration)}")
            return duration
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error getting video duration: {e}")
            print(f"   stderr: {e.stderr}")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def get_video_info(self):
        """Get detailed video information"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'stream=codec_name,codec_type,width,height,bit_rate',
                '-show_entries', 'format=duration,size,bit_rate',
                '-of', 'json',
                str(self.input_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.video_info = json.loads(result.stdout)
            
            return self.video_info
            
        except Exception as e:
            print(f"⚠️  Could not get detailed video info: {e}")
            return None
    
    def format_duration(self, seconds):
        """Format duration in human-readable format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    def calculate_chunks(self):
        """Calculate how many chunks are needed"""
        if self.duration is None:
            self.get_video_duration()
        
        if self.duration is None:
            return None
        
        # Calculate number of chunks needed
        num_chunks = math.ceil(self.duration / self.MAX_CHUNK_DURATION_SECONDS)
        
        # Calculate actual chunk duration (evenly distribute)
        chunk_duration = self.duration / num_chunks
        
        return {
            'num_chunks': num_chunks,
            'chunk_duration': chunk_duration,
            'total_duration': self.duration
        }
    
    def slice_video(self, chunk_duration=None, overlap_seconds=5):
        """
        Slice video into chunks
        
        Args:
            chunk_duration: Duration of each chunk in seconds (default: MAX_CHUNK_DURATION_SECONDS)
            overlap_seconds: Overlap between chunks to avoid missing content at boundaries
            
        Returns:
            List of output chunk file paths
        """
        if self.duration is None:
            self.get_video_duration()
        
        if self.duration is None:
            print("❌ Cannot slice video without duration information")
            return None
        
        # Use default chunk duration if not specified
        if chunk_duration is None:
            chunk_info = self.calculate_chunks()
            chunk_duration = chunk_info['chunk_duration']
            num_chunks = chunk_info['num_chunks']
        else:
            num_chunks = math.ceil(self.duration / chunk_duration)
        
        print(f"\n📊 Slicing Plan:")
        print(f"   Total duration: {self.format_duration(self.duration)}")
        print(f"   Number of chunks: {num_chunks}")
        print(f"   Chunk duration: {self.format_duration(chunk_duration)}")
        print(f"   Overlap: {overlap_seconds}s")
        print(f"   Output directory: {self.output_dir}")
        
        chunk_files = []
        
        for i in range(num_chunks):
            # Calculate start time (with overlap for chunks after the first)
            if i == 0:
                start_time = 0
            else:
                start_time = max(0, i * chunk_duration - overlap_seconds)
            
            # Calculate duration for this chunk
            if i == num_chunks - 1:
                # Last chunk: go to end
                duration = self.duration - start_time
            else:
                # Regular chunk: chunk_duration + overlap
                duration = chunk_duration + overlap_seconds
            
            # Generate output filename
            output_file = self.output_dir / f"{self.input_path.stem}_chunk_{i+1:03d}_of_{num_chunks:03d}.mp4"
            
            print(f"\n✂️  Chunk {i+1}/{num_chunks}:")
            print(f"   Start: {self.format_duration(start_time)}")
            print(f"   Duration: {self.format_duration(duration)}")
            print(f"   Output: {output_file.name}")
            
            # FFmpeg command to extract chunk
            cmd = [
                'ffmpeg',
                '-i', str(self.input_path),
                '-ss', str(start_time),
                '-t', str(duration),
                '-c:v', 'copy',  # Copy video codec (fast, no re-encoding)
                '-c:a', 'copy',  # Copy audio codec (fast, no re-encoding)
                '-y',  # Overwrite output file
                str(output_file)
            ]
            
            try:
                # Run ffmpeg with minimal output
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Check if file was created
                if output_file.exists():
                    file_size = output_file.stat().st_size / (1024 * 1024)  # MB
                    print(f"   ✅ Created: {file_size:.2f} MB")
                    chunk_files.append(str(output_file))
                else:
                    print(f"   ❌ File not created")
                    
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Error creating chunk: {e}")
                print(f"   stderr: {e.stderr}")
                continue
        
        print(f"\n✅ Slicing complete! Created {len(chunk_files)} chunks")
        print(f"📁 Output directory: {self.output_dir}")
        
        return chunk_files
    
    def needs_slicing(self, max_duration_minutes=None):
        """
        Check if video needs to be sliced
        
        Args:
            max_duration_minutes: Maximum duration in minutes (default: MAX_CHUNK_DURATION_MINUTES)
            
        Returns:
            Boolean indicating if slicing is needed
        """
        if max_duration_minutes is None:
            max_duration_minutes = self.MAX_CHUNK_DURATION_MINUTES
        
        if self.duration is None:
            self.get_video_duration()
        
        if self.duration is None:
            return False
        
        duration_minutes = self.duration / 60
        needs_slice = duration_minutes > max_duration_minutes
        
        if needs_slice:
            print(f"⚠️  Video duration ({duration_minutes:.1f} min) exceeds limit ({max_duration_minutes} min)")
            print(f"   Slicing is required")
        else:
            print(f"✅ Video duration ({duration_minutes:.1f} min) is within limit ({max_duration_minutes} min)")
            print(f"   No slicing needed")
        
        return needs_slice


def slice_video_file(input_path, output_dir=None, max_chunk_minutes=110, overlap_seconds=5):
    """
    Convenience function to slice a video file
    
    Args:
        input_path: Path to input video
        output_dir: Output directory for chunks
        max_chunk_minutes: Maximum duration per chunk in minutes
        overlap_seconds: Overlap between chunks
        
    Returns:
        List of chunk file paths, or None if video doesn't need slicing
    """
    try:
        slicer = VideoSlicer(input_path, output_dir)
        
        # Check if slicing is needed
        if not slicer.needs_slicing(max_chunk_minutes):
            print(f"ℹ️  Video can be processed as-is")
            return [str(input_path)]
        
        # Slice the video
        chunk_files = slicer.slice_video(
            chunk_duration=max_chunk_minutes * 60,
            overlap_seconds=overlap_seconds
        )
        
        return chunk_files
        
    except Exception as e:
        print(f"❌ Error slicing video: {e}")
        return None


if __name__ == '__main__':
    """Command-line interface for video slicing"""
    
    if len(sys.argv) < 2:
        print("Usage: python video_slicer.py <input_video> [output_dir] [max_chunk_minutes]")
        print("\nExample:")
        print("  python video_slicer.py long_video.mp4")
        print("  python video_slicer.py long_video.mp4 ./chunks 110")
        sys.exit(1)
    
    input_video = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    max_chunk_minutes = int(sys.argv[3]) if len(sys.argv) > 3 else 110
    
    print("🎬 Video Slicer")
    print("=" * 60)
    print(f"Input: {input_video}")
    print(f"Max chunk duration: {max_chunk_minutes} minutes")
    print("=" * 60)
    
    # Slice the video
    chunk_files = slice_video_file(
        input_video,
        output_dir=output_dir,
        max_chunk_minutes=max_chunk_minutes,
        overlap_seconds=5
    )
    
    if chunk_files:
        print(f"\n✅ Success! Created {len(chunk_files)} file(s)")
        print("\n📄 Chunk files:")
        for i, chunk in enumerate(chunk_files, 1):
            print(f"  {i}. {chunk}")
    else:
        print("\n❌ Failed to slice video")
        sys.exit(1)
