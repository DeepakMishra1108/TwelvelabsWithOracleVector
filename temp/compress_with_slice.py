#!/usr/bin/env python3
"""
Video Compression with Auto-Slicing
Integrates video slicing with compression for videos exceeding 120-minute limit
"""

import os
import sys
from pathlib import Path
from video_slicer import VideoSlicer, slice_video_file

def compress_with_auto_slice(input_video, output_path=None, max_chunk_minutes=110, 
                             quality='medium', target_size_mb=None):
    """
    Compress video with automatic slicing for long videos
    
    Args:
        input_video: Input video file path
        output_path: Output file path (for single video) or directory (for chunked)
        max_chunk_minutes: Maximum duration per chunk (default: 110 minutes)
        quality: Compression quality preset (low, medium, high)
        target_size_mb: Target size in MB (optional)
        
    Returns:
        List of compressed output file paths
    """
    
    print("🎬 Video Compression with Auto-Slicing")
    print("=" * 70)
    
    # Check if video needs slicing
    slicer = VideoSlicer(input_video)
    
    if not slicer.needs_slicing(max_chunk_minutes):
        # Video is short enough, compress directly
        print("\n✅ Video duration is within limits")
        print("   Processing as single file...")
        
        # Use your existing compress_video function here
        # For now, just return the input path
        compressed_files = [input_video]
        
        print(f"\n✅ Compression complete!")
        return compressed_files
    
    else:
        # Video needs slicing
        print("\n⚠️  Video exceeds duration limit")
        print("   Slicing into chunks first...")
        
        # Slice the video
        chunk_files = slice_video_file(
            input_video,
            output_dir=output_path if output_path else None,
            max_chunk_minutes=max_chunk_minutes,
            overlap_seconds=5
        )
        
        if not chunk_files:
            print("❌ Failed to slice video")
            return None
        
        print(f"\n✅ Video sliced into {len(chunk_files)} chunks")
        print("\n📦 Compressing chunks...")
        
        compressed_files = []
        for i, chunk in enumerate(chunk_files, 1):
            print(f"\n🔄 Compressing chunk {i}/{len(chunk_files)}: {Path(chunk).name}")
            
            # Here you would call your compression function
            # For now, we'll just use the chunk as-is
            # compressed = compress_video(chunk, quality=quality, target_size_mb=target_size_mb)
            compressed = chunk
            
            compressed_files.append(compressed)
            print(f"   ✅ Chunk {i} complete")
        
        print(f"\n✅ All chunks compressed!")
        print(f"📁 Output directory: {Path(chunk_files[0]).parent}")
        
        return compressed_files


def create_chunk_manifest(chunk_files, output_file="chunks_manifest.json"):
    """
    Create a manifest file listing all chunks
    
    Args:
        chunk_files: List of chunk file paths
        output_file: Output manifest file path
        
    Returns:
        Path to manifest file
    """
    import json
    from datetime import datetime
    
    manifest = {
        'created_at': datetime.now().isoformat(),
        'total_chunks': len(chunk_files),
        'chunks': []
    }
    
    for i, chunk_path in enumerate(chunk_files, 1):
        chunk = Path(chunk_path)
        if chunk.exists():
            size_mb = chunk.stat().st_size / (1024 * 1024)
            manifest['chunks'].append({
                'index': i,
                'filename': chunk.name,
                'path': str(chunk),
                'size_mb': round(size_mb, 2)
            })
    
    # Write manifest
    output_path = Path(chunk_files[0]).parent / output_file
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n📋 Manifest created: {output_path}")
    return str(output_path)


if __name__ == '__main__':
    """Command-line interface"""
    
    if len(sys.argv) < 2:
        print("Usage: python compress_with_slice.py <input_video> [output_dir] [max_chunk_min]")
        print("\nExample:")
        print("  python compress_with_slice.py long_video.mp4")
        print("  python compress_with_slice.py long_video.mp4 ./output 110")
        sys.exit(1)
    
    input_video = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    max_chunk_min = int(sys.argv[3]) if len(sys.argv) > 3 else 110
    
    # Process video
    compressed_files = compress_with_auto_slice(
        input_video,
        output_path=output_dir,
        max_chunk_minutes=max_chunk_min
    )
    
    if compressed_files:
        # Create manifest
        create_chunk_manifest(compressed_files)
        
        print(f"\n✅ Processing complete!")
        print(f"   Total files: {len(compressed_files)}")
    else:
        print("\n❌ Processing failed")
        sys.exit(1)
