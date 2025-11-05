# Photo Album Feature - TwelveLabs Marengo Integration

This feature adds photo album management with Marengo embeddings and unified search across photos and videos.

## Features

- 📷 **Photo Upload**: Upload multiple photos organized in named albums
- 🧠 **Marengo Embeddings**: Create semantic embeddings using TwelveLabs Marengo-retrieval-2.7 model
- 🔍 **Photo Search**: Search photos using natural language queries
- 🎯 **Unified Search**: Search across both photos and videos simultaneously
- 💾 **Oracle Storage**: Store embeddings as float32 BLOBs in Oracle DB

## Architecture

### Database Schema

**Table: `photo_embeddings`**

```sql
CREATE TABLE photo_embeddings (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    album_name VARCHAR2(500),
    photo_file VARCHAR2(2000),
    embedding_vector BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Modules

1. **create_schema_photo_embeddings.py** - Create DB schema
2. **store_photo_embeddings.py** - Create and store Marengo embeddings
3. **query_photo_embeddings.py** - Search photos using embeddings
4. **unified_search.py** - Unified search across photos and videos

### Flask Endpoints

| Endpoint                   | Method | Description                          |
| -------------------------- | ------ | ------------------------------------ |
| `/upload_photo`            | POST   | Upload photo to OCI                  |
| `/create_photo_embeddings` | POST   | Create Marengo embeddings for photos |
| `/search_photos`           | POST   | Search photos by text query          |
| `/search_unified`          | POST   | Search both photos and videos        |
| `/list_albums`             | GET    | List all album names                 |

## Setup

### 1. Create Database Schema

```bash
cd twelvelabvideoai/src
python create_schema_photo_embeddings.py
```

### 2. Environment Variables

Ensure these are set in your `.env`:

```bash
# TwelveLabs API
TWELVE_LABS_API_KEY=tlk_...

# Oracle Database
ORACLE_DB_USERNAME=...
ORACLE_DB_PASSWORD=...
ORACLE_DB_CONNECT_STRING=...
ORACLE_DB_WALLET_PATH=...
ORACLE_DB_WALLET_PASSWORD=...

# OCI (for photo uploads)
OCI_BUCKET=Media
```

### 3. Start Flask Server

```bash
PYTHONPATH=twelvelabvideoai/src python -m flask --app agent_playback_app run --port 8080
```

## Usage

### Command Line

#### Upload Photos and Create Embeddings

```bash
cd twelvelabvideoai/src

# Store photo embeddings
python store_photo_embeddings.py "vacation2024" \
    "https://example.com/photo1.jpg" \
    "https://example.com/photo2.jpg"
```

#### Search Photos

```bash
# Search in all albums
python query_photo_embeddings.py "sunset beach"

# Search in specific album
python query_photo_embeddings.py "sunset beach" "vacation2024"
```

#### Unified Search

```bash
python unified_search.py "inspection tower" "safety equipment"
```

### REST API

#### Upload a Photo

```bash
curl -X POST http://localhost:8080/upload_photo \
  -F "photo=@/path/to/photo.jpg" \
  -F "album_name=vacation2024"
```

Response:

```json
{
  "photo_url": "https://objectstorage....",
  "oci_path": "oci://namespace/Media/photos/vacation2024/photo.jpg",
  "album_name": "vacation2024",
  "filename": "photo.jpg"
}
```

#### Create Photo Embeddings

```bash
curl -X POST http://localhost:8080/create_photo_embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "album_name": "vacation2024",
    "photo_urls": [
      "https://objectstorage...photo1.jpg",
      "https://objectstorage...photo2.jpg"
    ]
  }'
```

Response:

```json
{
  "success": 2,
  "failed": 0,
  "errors": []
}
```

#### Search Photos

```bash
curl -X POST http://localhost:8080/search_photos \
  -H "Content-Type: application/json" \
  -d '{
    "query": "sunset beach",
    "album_name": "vacation2024",
    "top_k": 10
  }'
```

Response:

```json
{
  "results": [
    {
      "id": 1,
      "album_name": "vacation2024",
      "photo_file": "https://..../sunset.jpg",
      "similarity_score": 0.8523
    }
  ],
  "count": 1
}
```

#### Unified Search (Photos + Videos)

```bash
curl -X POST http://localhost:8080/search_unified \
  -H "Content-Type: application/json" \
  -d '{
    "queries": ["inspection tower", "safety equipment"],
    "top_k_photos": 5,
    "top_k_videos": 5
  }'
```

Response:

```json
{
  "photos": {
    "inspection tower": [
      {
        "album_name": "site_inspection",
        "photo_file": "tower.jpg",
        "similarity_score": 0.89
      }
    ]
  },
  "videos": {
    "inspection tower": [
      {
        "video_file": "inspection.mp4",
        "start_time": 12.5,
        "end_time": 18.3,
        "similarity_score": 0.92
      }
    ]
  },
  "summary": {
    "inspection tower": {
      "photo_count": 1,
      "video_count": 1,
      "total_count": 2
    }
  }
}
```

#### List Albums

```bash
curl http://localhost:8080/list_albums
```

Response:

```json
{
  "albums": ["vacation2024", "site_inspection", "family_photos"],
  "count": 3
}
```

### Web UI

1. Open http://localhost:8080 in your browser
2. Use the **📷 Photo Albums** section:
   - Enter album name (e.g., "vacation2024")
   - Select one or more photos
   - Click "Upload Photos"
   - Click "Create Embeddings" to process uploaded photos
3. Use the **🔍 Unified Search** section:
   - Enter a search query (e.g., "sunset beach")
   - Click "Search All"
   - View separate results for photos and videos

## Testing

Run the comprehensive test suite:

```bash
python scripts/test_photo_albums.py
```

This will:

1. Create the database schema
2. Test photo embedding creation (if sample URLs provided)
3. Test photo search
4. Test unified search

## Technical Details

### Embedding Model

- **Model**: Marengo-retrieval-2.7
- **Type**: Multimodal (images + text)
- **Dimension**: Variable (typically 512-1024 floats)
- **Storage**: float32 BLOB in Oracle

### Similarity Search

- Uses **client-side cosine similarity** (same as video embeddings)
- Fetches all embeddings from DB and computes similarity in Python
- Handles dimension mismatches by truncating to minimum length
- Returns top-k results sorted by similarity score

### Performance Considerations

- Each embedding API call takes ~2-5 seconds
- Batch uploads process sequentially (avoid rate limits)
- Consider implementing caching for frequently searched queries
- For large albums (>1000 photos), consider pagination

## Troubleshooting

### "TWELVE_LABS_API_KEY not set"

- Ensure `.env` file exists in repo root
- Check key is valid: `echo $TWELVE_LABS_API_KEY`

### "ORA-51811: Dimension count exceeded"

- This occurs if trying to use Oracle's native VECTOR type
- Solution: Use BLOB storage (float32 binary) - **already implemented**

### "No results found"

- Ensure embeddings were created: Check `photo_embeddings` table
- Verify photos were uploaded successfully
- Check TwelveLabs API quota/limits

### "Failed to connect to Oracle DB"

- Verify Oracle credentials in `.env`
- Check wallet path and password
- Test connection: `python create_schema_photo_embeddings.py`

## Future Enhancements

- [ ] Batch embedding creation (parallel processing)
- [ ] Photo thumbnail generation
- [ ] Album-level metadata (description, tags)
- [ ] Pagination for large result sets
- [ ] Caching layer for embeddings
- [ ] Support for other image models
- [ ] Face detection and recognition
- [ ] Duplicate photo detection

## Related Documentation

- [TwelveLabs Marengo Documentation](https://docs.twelvelabs.io/docs/marengo)
- [Video Embeddings (existing)](./query_video_embeddings.py)
- [Unified Search](./unified_search.py)
