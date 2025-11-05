#!/usr/bin/env python3
"""
Download video from OCI, compress it locally, and prepare for re-upload
Usage: python3 compress_video_local.py <media_id>
"""

import sys
import os
import subprocess
import shutil
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'twelvelabvideoai', 'src')
sys.path.insert(0, src_dir)

from dotenv import load_dotenv
load_dotenv()

from utils.db_utils_flask_safe import get_flask_safe_connection
import oci
from oci_config import load_oci_config

def check_ffmpeg():
    """Check if ffmpeg is installed"""
    if not shutil.which('ffmpeg'):
        print("❌ ffmpeg is not installed")
        print("\n📥 To install ffmpeg on macOS:")
        print("   brew install ffmpeg")
        print("\nOr download from: https://ffmpeg.org/download.html")
        return False
    
    # Get ffmpeg version
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        version_line = result.stdout.split('\n')[0]
        print(f"✅ {version_line}")
        return True
    except Exception as e:
        print(f"⚠️  ffmpeg found but error checking version: {e}")
        return True

def download_from_oci(namespace, bucket, object_path, output_file):
    """Download video from OCI to local file"""
    try:
        config = load_oci_config(oci)
        client = oci.object_storage.ObjectStorageClient(config)
        
        # Remove 'Media/' prefix if present
        object_name = object_path.replace('Media/', '', 1) if object_path.startswith('Media/') else object_path
        
        print(f"📥 Downloading from OCI...")
        print(f"   Object: {object_name}")
        
        response = client.get_object(namespace_name=namespace, bucket_name=bucket, object_name=object_name)
        
        # Stream download to file
        with open(output_file, 'wb') as f:
            for chunk in response.data.raw.stream(1024 * 1024, decode_content=False):  # 1MB chunks
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(output_file)
        print(f"✅ Downloaded: {file_size:,} bytes ({file_size/1024/1024/1024:.2f} GB)")
        return True
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False

def compress_video(input_file, output_file, target_size_mb=900):
    """
    Compress video to target size using ffmpeg
    
    Strategy:
    1. Use H.264 codec (widely compatible)
    2. Two-pass encoding for better quality
    3. Target bitrate calculated based on duration and target size
    """
    try:
        print(f"\n🎬 Analyzing video...")
        
        # Get video duration
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_file
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        duration = float(result.stdout.strip())
        
        print(f"   Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        
        # Calculate target bitrate (in kbps)
        # Formula: (target_size_MB * 8192) / duration_seconds
        target_bitrate = int((target_size_mb * 8192) / duration)
        audio_bitrate = 128  # 128kbps for audio
        video_bitrate = target_bitrate - audio_bitrate
        
        print(f"   Target size: {target_size_mb} MB")
        print(f"   Target video bitrate: {video_bitrate} kbps")
        print(f"   Audio bitrate: {audio_bitrate} kbps")
        
        print(f"\n🔄 Compressing video (this may take several minutes)...")
        
        # FFmpeg command for compression
        # Using CRF (Constant Rate Factor) mode with max bitrate
        compress_cmd = [
            'ffmpeg', '-i', input_file,
            '-c:v', 'libx264',           # H.264 video codec
            '-crf', '28',                 # Quality (18-28, higher = smaller file)
            '-preset', 'medium',          # Encoding speed/quality tradeoff
            '-maxrate', f'{video_bitrate}k',  # Max bitrate
            '-bufsize', f'{video_bitrate * 2}k',  # Buffer size
            '-c:a', 'aac',                # AAC audio codec
            '-b:a', f'{audio_bitrate}k',  # Audio bitrate
            '-movflags', '+faststart',    # Enable streaming
            '-y',                         # Overwrite output
            output_file
        ]
        
        # Run compression
        process = subprocess.run(
            compress_cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        if process.returncode != 0:
            print(f"❌ Compression failed:")
            print(process.stderr[-500:])  # Last 500 chars of error
            return False
        
        # Check output file
        output_size = os.path.getsize(output_file)
        output_size_mb = output_size / (1024 * 1024)
        
        print(f"\n✅ Compression complete!")
        print(f"   Output size: {output_size:,} bytes ({output_size_mb:.1f} MB)")
        
        # Calculate compression ratio
        input_size = os.path.getsize(input_file)
        ratio = (1 - output_size / input_size) * 100
        print(f"   Compression: {ratio:.1f}% reduction")
        
        if output_size_mb > 1000:
            print(f"\n⚠️  Warning: Output file is still > 1GB ({output_size_mb:.1f} MB)")
            print(f"   You may need to compress further or use a shorter video clip")
        
        return True
        
    except subprocess.TimeoutExpired:
        print(f"❌ Compression timed out after 30 minutes")
        return False
    except Exception as e:
        print(f"❌ Compression error: {e}")
        import traceback
        traceback.print_exc()
        return False

def compress_video_local(media_id):
    """Main function to compress video from database"""
    print("="*70)
    print(f"🎥 COMPRESSING VIDEO (MEDIA ID: {media_id})")
    print("="*70)
    
    # Check ffmpeg
    if not check_ffmpeg():
        return False
    
    # Get video info from database
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            sql = """
            SELECT file_name, oci_namespace, oci_bucket, oci_object_path, file_size
            FROM album_media 
            WHERE id = :media_id
            """
            cursor.execute(sql, {'media_id': media_id})
            result = cursor.fetchone()
            
            if not result:
                print(f"❌ Media ID {media_id} not found in database")
                return False
            
            file_name, namespace, bucket, object_path, file_size = result
            
            print(f"\n📹 Video Information:")
            print(f"   File: {file_name}")
            print(f"   Original size: {file_size:,} bytes ({file_size/1024/1024/1024:.2f} GB)")
            print(f"   OCI: {namespace}/{bucket}/{object_path}")
    
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    # Create temp directory
    temp_dir = Path('/tmp/video_compression')
    temp_dir.mkdir(exist_ok=True)
    
    input_file = temp_dir / f"original_{file_name}"
    output_file = temp_dir / f"compressed_{file_name}"
    
    try:
        # Download from OCI
        print(f"\n📦 Step 1: Download from OCI")
        if not download_from_oci(namespace, bucket, object_path, str(input_file)):
            return False
        
        # Compress
        print(f"\n🔧 Step 2: Compress video")
        if not compress_video(str(input_file), str(output_file), target_size_mb=900):
            return False
        
        # Success
        print("\n" + "="*70)
        print("✅ COMPRESSION COMPLETE!")
        print("="*70)
        print(f"\n📁 Compressed video saved to:")
        print(f"   {output_file}")
        print(f"\n📤 Next steps:")
        print(f"   1. Delete video ID {media_id} using: python3 delete_video_48.py")
        print(f"   2. Upload compressed video through web interface (http://localhost:8080)")
        print(f"   3. Or move compressed file to a permanent location:")
        print(f"      mv {output_file} ~/Downloads/")
        
        return True
        
    finally:
        # Cleanup original download (keep compressed)
        if input_file.exists():
            input_file.unlink()
            print(f"\n🧹 Cleaned up temporary download")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 compress_video_local.py <media_id>")
        print("Example: python3 compress_video_local.py 48")
        sys.exit(1)
    
    try:
        media_id = int(sys.argv[1])
        success = compress_video_local(media_id)
        sys.exit(0 if success else 1)
    except ValueError:
        print("❌ Invalid media_id. Must be a number.")
        sys.exit(1)
