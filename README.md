# VideoEncodeTwelveLabs

**Last Updated:** November 6, 2025

Video and photo AI platform with TwelveLabs Marengo embeddings, unified search, GPS metadata extraction, and Oracle DB storage.

## ✨ Features

- 🎥 **Video Embeddings**: Store and search video segments using TwelveLabs embeddings
- 📷 **Photo Albums**: Upload photos, organize in albums, create Marengo embeddings
- 🔍 **Unified Search**: Search across both photos and videos simultaneously
- 📊 **Real-time Progress**: Live upload progress with Server-Sent Events (SSE)
- 📍 **GPS Metadata**: Automatic EXIF extraction with GPS coordinates and location
- 🗺️ **Location Tracking**: City, state, country information from reverse geocoding
- 🎬 **Pegasus Integration**: Generate AI-powered edit plans and summaries
- 💾 **Oracle Vector Storage**: TwelveLabs embeddings in Oracle Vector DB (VECTOR 1024, FLOAT32)
- 🌐 **Modern Web UI**: Beautiful browser interface with progress tracking

## 🚀 Quick Start

### 1. Install Dependencies

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Ensure your `.env` file contains:

```bash
# TwelveLabs API
TWELVE_LABS_API_KEY=tlk_...
PEGASUS_API_KEY=tlk_...

# Oracle Database
ORACLE_DB_USERNAME=...
ORACLE_DB_PASSWORD=...
ORACLE_DB_CONNECT_STRING=...
ORACLE_DB_WALLET_PATH=...
ORACLE_DB_WALLET_PASSWORD=...

# OCI (for uploads)
OCI_BUCKET=Media
DEFAULT_OCI_BUCKET=Media
```

### 3. Create Database Schemas

```sh
cd twelvelabvideoai/src

# Create unified albums table with GPS metadata support
python create_schema_unified_albums.py

# Run migration to add GPS/location columns (if upgrading)
python migrate_add_location_metadata.py

# Create video embeddings table
python create_schema_video_embeddings.py

# Create photo embeddings table
python create_schema_photo_embeddings.py
```

### 4. Start Flask Server

```sh
PYTHONPATH=twelvelabvideoai/src python -m flask --app agent_playback_app run --port 8080
```

### 5. Open Web UI

Visit http://localhost:8080 in your browser.

## Project Structure

```
twelvelabvideoai/
├── src/
│   ├── agent_playback_app.py          # Main Flask application
│   ├── store_video_embeddings.py      # Video embedding creation
│   ├── query_video_embeddings.py      # Video search
│   ├── store_photo_embeddings.py      # Photo embedding creation
│   ├── query_photo_embeddings.py      # Photo search
│   ├── unified_search.py              # Unified photo+video search
│   ├── pegasus_client.py              # Pegasus AI integration
│   ├── utils/                         # Helper modules
│   │   ├── oci_utils.py              # OCI/PAR management
│   │   ├── ffmpeg_utils.py           # Video processing
│   │   └── http_utils.py             # Download helpers
│   └── templates/
│       └── index.html                 # Web UI
├── scripts/
│   ├── test_photo_albums.py          # Test suite
│   ├── clean_caches.sh               # Cache cleanup
│   └── refresh_environment.py        # Full environment reset
└── PHOTO_ALBUMS_README.md            # Detailed photo docs
```

## Usage Examples

### Upload and Search Photos

```bash
# Upload photos via web UI at http://localhost:8080
# Or via CLI:
cd twelvelabvideoai/src
python store_photo_embeddings.py "vacation2024" \
    "https://example.com/photo1.jpg" \
    "https://example.com/photo2.jpg"

# Search photos
python query_photo_embeddings.py "sunset beach"
```

### Unified Search (Photos + Videos)

```bash
# Search across both photos and videos
python unified_search.py "inspection tower" "safety equipment"

# Or use the web UI "Unified Search" section
```

### Video Embeddings

```bash
# Create video embeddings
python store_video_embeddings.py "path/to/video.mp4"

# Search videos
python query_video_embeddings.py "inspection tower"
```

## Documentation

- **[PHOTO_ALBUMS_README.md](./PHOTO_ALBUMS_README.md)** - Complete photo album feature documentation
- **API Endpoints** - See Flask app routes in `agent_playback_app.py`
- **TwelveLabs Docs** - https://docs.twelvelabs.io/

## OCI Configuration

This project uses OCI for photo/video storage. Config file precedence:

1. `OCI_CONFIG_PATH` environment variable (if set)
2. `twelvelabvideoai/.oci/config` (repository-local)
3. `~/.oci/config` (default SDK location)

## Testing

Run the photo album test suite:

```sh
python scripts/test_photo_albums.py
```

## Utilities

**Clean all caches:**

```sh
./scripts/clean_caches.sh           # Dry-run
./scripts/clean_caches.sh --yes     # Actually delete
```

**Full environment reset:**

```sh
python scripts/refresh_environment.py --help
```

## Notes

- Photo and video embeddings are stored as float32 BLOBs (not Oracle VECTOR type)
- Client-side cosine similarity search implemented
- PAR URLs cached for OCI object access
- All search results ranked by similarity score
- Web UI supports drag/drop for Pegasus plan editing

## Production Considerations

- Add authentication and authorization
- Implement rate limiting for API calls
- Use connection pooling for Oracle DB
- Add pagination for large result sets
- Cache frequently searched queries
- Use production WSGI server (gunicorn/uwsgi)
- Enable HTTPS and CORS policies
