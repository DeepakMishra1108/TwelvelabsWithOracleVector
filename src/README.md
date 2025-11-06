# Source Directory (Core Application)

This directory contains the core application code for the TwelvelabsVideoAI project.

## Core Files

### Main Application

- **`localhost_only_flask.py`** - Main Flask application server
  - Handles all HTTP endpoints for the web UI
  - Manages photo and video uploads
  - Integrates with OCI storage, TwelveLabs API, and Oracle Vector DB
  - Provides unified search across photos and video segments

### Search Modules

- **`search_unified_flask_safe.py`** - Unified search implementation
  - Searches both photos (from `album_media` table) and video segments (from `video_embeddings` table)
  - Uses Oracle Vector DB with COSINE similarity
  - Returns combined results sorted by similarity score
  - Includes segment timestamps for video results

- **`search_flask_safe.py`** - Original photo-only search (legacy)
  - Searches only photos from `album_media` table
  - Kept for backward compatibility

### Video Processing

- **`video_upload_handler.py`** - Video upload and processing handler
  - Checks video duration
  - Slices long videos into chunks (90-minute segments)
  - Creates metadata for video chunks
  - Manages chunk cleanup

- **`video_slicer.py`** - Video slicing utilities
  - Splits videos into time-based chunks
  - Uses FFmpeg for efficient video processing
  - Maintains video quality during slicing

- **`video_thumbnail_generator.py`** - Video thumbnail generation
  - Generates thumbnails at specific timestamps
  - Uses FFmpeg to extract frames directly from video URLs
  - Optimized for fast thumbnail generation (~15 seconds)

- **`generate_chunk_embeddings.py`** - Generate embeddings for video chunks
  - Submits video chunks to TwelveLabs API
  - Waits for embedding generation to complete
  - Stores segment-level embeddings in `video_embeddings` table
  - Each segment contains start_time, end_time, and 1024-dimensional embedding

### Placeholder

- **`main.py`** - Placeholder/entry point (currently empty)

## Running the Application

To run the Flask application:

```bash
cd /path/to/TwelvelabsVideoAI
python src/localhost_only_flask.py
```

Or with live logging:

```bash
python src/localhost_only_flask.py 2>&1 | tee flask_live.log
```

The application will start on `http://localhost:8080`

## Architecture

### Database Schema

- **`album_media`** - Stores photos and video metadata
  - `id`: Primary key
  - `album_name`: Album/collection name
  - `file_name`: Original filename
  - `file_path`: OCI storage path
  - `file_type`: 'photo' or 'video'
  - `embedding_vector`: VECTOR(1024, FLOAT32) for semantic search
  - `created_at`: Timestamp

- **`video_embeddings`** - Stores video segment embeddings
  - `id`: Primary key
  - `video_file`: Links to album_media.file_name
  - `chunk_number`: Which chunk this segment belongs to
  - `segment_index`: Segment number within video
  - `start_time`: Segment start time (seconds)
  - `end_time`: Segment end time (seconds)
  - `embedding_vector`: VECTOR(1024, FLOAT32) for segment-level search
  - `created_at`: Timestamp

### External Dependencies

- **OCI (Oracle Cloud Infrastructure)**: Object storage for media files
- **TwelveLabs API**: Video understanding and embedding generation (Marengo 2.6 model)
- **Oracle Vector DB**: Stores and searches embeddings with COSINE similarity
- **FFmpeg**: Video processing and thumbnail generation

### Key Features

1. **Unified Search**: Search across both photos and video segments in one query
2. **Video Slicing**: Automatically slices long videos into 90-minute chunks for TwelveLabs processing
3. **Segment-Level Search**: Each video segment (typically 10-30 seconds) is individually searchable
4. **Fast Thumbnails**: Direct FFmpeg extraction from URLs (no full download required)
5. **Progress Tracking**: Real-time progress updates for uploads and processing

## Related Directories

- **`../temp/`** - Temporary scripts, tests, and utilities
- **`../twelvelabvideoai/src/`** - Additional utilities (album manager, DB utils, etc.)
- **`../scripts/`** - Deployment and maintenance scripts

## Environment Variables Required

See the main project `.env` file for required configuration:

- OCI credentials (tenancy, user, fingerprint, key file, region)
- OCI Object Storage (namespace, bucket)
- Oracle DB connection details
- TwelveLabs API key
- Flask configuration

## Support

For issues or questions, refer to the main project README.md at the repository root.
