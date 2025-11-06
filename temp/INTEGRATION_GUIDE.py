"""
Video Slicing Integration Example for Flask Upload

This shows how to integrate the video slicing capability into the existing
Flask upload workflow (localhost_only_flask.py).

INTEGRATION STEPS:
==================

1. Import the video upload handler at the top of localhost_only_flask.py:
   
   from video_upload_handler import prepare_video_for_upload, create_video_metadata

2. In the upload_unified() function, after file type detection and before
   OCI upload, add video duration check and slicing:

   # After line: file_type, mime_type = flask_safe_album_manager.detect_file_type(file.filename)
   # Add:
   
   if file_type == 'video':
       # Save video temporarily to check duration
       import tempfile
       with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
           file.save(tmp.name)
           tmp_path = tmp.name
       
       # Check and prepare video (slice if needed)
       def progress_callback(stage, percent, message):
           send_file_progress(stage, percent, message)
       
       prep_result = prepare_video_for_upload(
           tmp_path, 
           progress_callback=progress_callback
       )
       
       if not prep_result['success']:
           os.unlink(tmp_path)
           file_result['error'] = prep_result.get('error', 'Video preparation failed')
           failed_count += 1
           results.append(file_result)
           continue
       
       # Get list of files to upload (original or chunks)
       video_files = prep_result['files']
       is_chunked = prep_result['is_chunked']
       
       logger.info(f"📹 Video prepared: {len(video_files)} file(s) to upload "
                  f"(chunked: {is_chunked})")
   
   else:
       # Not a video - proceed with original file
       video_files = [file]
       is_chunked = False

3. Replace the single file upload logic with a loop over video_files:

   for video_idx, video_file_path in enumerate(video_files, 1):
       # If chunked, generate chunk-specific object name
       if is_chunked:
           base_name = Path(file.filename).stem
           ext = Path(file.filename).suffix
           chunk_name = f"{base_name}_chunk_{video_idx:03d}_of_{len(video_files):03d}{ext}"
           object_name = f"albums/{album_name}/{file_type}s/{chunk_name}"
       else:
           object_name = f"albums/{album_name}/{file_type}s/{file.filename}"
       
       # Upload to OCI
       if isinstance(video_file_path, str):
           # It's a file path (from slicing)
           with open(video_file_path, 'rb') as video_file:
               obj_client.put_object(namespace, bucket, object_name, video_file)
       else:
           # It's the original FileStorage object
           obj_client.put_object(namespace, bucket, object_name, video_file_path)
       
       # Create metadata for this chunk
       chunk_metadata = create_video_metadata(
           video_file_path if isinstance(video_file_path, str) else tmp_path,
           is_chunk=is_chunked,
           chunk_index=video_idx if is_chunked else None,
           total_chunks=len(video_files) if is_chunked else None
       )
       
       # Store in database with chunk information
       # ... (existing database storage logic)

4. Add cleanup after all chunks are processed:

   # After all video files are uploaded
   if is_chunked and 'chunk_directory' in prep_result:
       from video_upload_handler import cleanup_chunks
       cleanup_chunks(prep_result['chunk_directory'])
   
   # Clean up temp file
   if os.path.exists(tmp_path):
       os.unlink(tmp_path)


USAGE EXAMPLE:
==============

When uploading a video >120 minutes:
1. System detects video duration
2. Automatically slices into 110-minute chunks
3. Uploads each chunk separately to OCI
4. Creates embeddings for each chunk
5. Stores metadata linking chunks together
6. Cleans up temporary chunk files


TESTING:
========

1. Test with short video (<120 min):
   - Should upload normally without slicing
   
2. Test with long video (>120 min):
   - Should automatically slice
   - Each chunk should be uploaded
   - Metadata should indicate chunking

3. Check the error from your last upload:
   Video duration: 10852.3 seconds (181 minutes)
   This would be sliced into 2 chunks:
   - Chunk 1: 0-110 minutes
   - Chunk 2: 105-181 minutes (with 5-second overlap)


CONFIGURATION:
==============

Adjust settings in video_upload_handler.py:
- MAX_VIDEO_DURATION_MINUTES: Default 110 (10-min buffer)
- CHUNK_OVERLAP_SECONDS: Default 5 seconds


DATABASE SCHEMA UPDATE:
========================

Consider adding chunk information to your metadata:
- is_chunk: BOOLEAN
- chunk_index: INTEGER
- total_chunks: INTEGER  
- original_filename: VARCHAR
- parent_video_id: INTEGER (foreign key to link chunks)

This allows:
- Querying all chunks of a video
- Displaying chunk information in UI
- Reconstructing full video if needed
"""

# Quick Test Script
if __name__ == '__main__':
    print(__doc__)
    
    print("\n" + "="*70)
    print("REAL-WORLD EXAMPLE FROM YOUR ERROR:")
    print("="*70)
    
    video_duration = 10852.3  # seconds
    video_minutes = video_duration / 60
    chunk_duration = 110 * 60  # 110 minutes
    
    print(f"\nOriginal Video:")
    print(f"  Duration: {video_duration} seconds ({video_minutes:.1f} minutes)")
    print(f"  Problem: Exceeds 120-minute (7200 seconds) limit")
    
    import math
    num_chunks = math.ceil(video_duration / chunk_duration)
    chunk_size = video_duration / num_chunks
    
    print(f"\nWith Auto-Slicing:")
    print(f"  Number of chunks: {num_chunks}")
    print(f"  Chunk duration: ~{chunk_size/60:.1f} minutes each")
    print(f"  Overlap: 5 seconds between chunks")
    
    print(f"\nChunks would be:")
    for i in range(num_chunks):
        start = max(0, i * chunk_size - 5)
        end = min(video_duration, (i + 1) * chunk_size + 5)
        print(f"  Chunk {i+1}: {start/60:.1f} - {end/60:.1f} minutes "
              f"({(end-start)/60:.1f} min)")
    
    print(f"\nResult:")
    print(f"  ✅ All chunks are under 120-minute limit")
    print(f"  ✅ 5-second overlap prevents missing content")
    print(f"  ✅ Fast processing (codec copy, no re-encoding)")
