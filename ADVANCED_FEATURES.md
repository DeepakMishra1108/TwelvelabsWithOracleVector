# 🚀 Advanced Features Guide

**Last Updated:** November 6, 2025

This document describes the advanced AI-powered features, search capabilities, and creative tools available in the Data Guardian platform.

---

## 📋 Table of Contents

1. [AI-Powered Features](#ai-powered-features)
2. [Advanced Search](#advanced-search)
3. [Creative Tools](#creative-tools)
4. [API Endpoints](#api-endpoints)
5. [Usage Examples](#usage-examples)

---

## 🤖 AI-Powered Features

### 1. Video Highlights Extractor

Automatically identifies and extracts key moments from videos using TwelveLabs AI.

**Features:**
- Detects important scenes and highlights
- Generates chapter markers with timestamps
- Extracts memorable moments for quick previews

**Backend Module:** `twelvelabvideoai/src/ai_features.py`

**API Endpoint:** `GET /video_highlights/<media_id>`

**Usage:**
```python
from ai_features import VideoHighlightsExtractor

extractor = VideoHighlightsExtractor()
highlights = await extractor.extract_highlights(video_id, max_highlights=5)

# Returns:
# {
#     "success": True,
#     "video_id": "...",
#     "highlights": [
#         {"timestamp": 45.2, "description": "Key moment"},
#         ...
#     ]
# }
```

---

### 2. Auto-Tagging System

Automatically generates tags, topics, hashtags, and titles for media using AI.

**Features:**
- Generates descriptive titles
- Extracts relevant topics
- Creates hashtags for social media
- Saves tags to database for future filtering

**Backend Module:** `twelvelabvideoai/src/ai_features.py`

**API Endpoint:** `POST /auto_tag/<media_id>`

**Usage:**
```python
from ai_features import AutoTagger

tagger = AutoTagger()
result = await tagger.generate_tags(video_id)

# Returns:
# {
#     "success": True,
#     "title": "Summer Vacation at the Beach",
#     "topics": ["vacation", "beach", "summer"],
#     "hashtags": ["#BeachLife", "#SummerVibes"],
#     "tags": ["vacation", "beach", "summer", "#BeachLife"]
# }

# Save tags to database
tagger.save_tags_to_db(media_id, result['tags'], media_type="video")
```

---

### 3. Similar Media Finder

Find photos and videos similar to a given item using Oracle VECTOR similarity search.

**Features:**
- Finds visually similar photos
- Discovers related video content
- Uses native Oracle VECTOR_DISTANCE
- Configurable similarity threshold

**Backend Module:** `twelvelabvideoai/src/ai_features.py`

**API Endpoint:** `GET /find_similar/<media_id>`

**Usage:**
```python
from ai_features import SimilarMediaFinder

finder = SimilarMediaFinder()

# Find similar photos
similar_photos = finder.find_similar_photos(
    photo_id=42,
    top_k=10,
    min_similarity=0.7
)

# Find similar videos
similar_videos = finder.find_similar_videos(
    video_id=63,
    top_k=10,
    min_similarity=0.7
)

# Each result includes:
# {
#     "id": 123,
#     "album_name": "Vacation 2024",
#     "file_name": "beach.jpg",
#     "similarity": 0.85,
#     "type": "photo"
# }
```

**Example Response:**
```json
{
    "success": true,
    "media_id": 42,
    "media_type": "photo",
    "similar_items": [
        {
            "id": 45,
            "album_name": "Summer 2024",
            "file_name": "sunset.jpg",
            "similarity": 0.92,
            "type": "photo"
        }
    ]
}
```

---

### 4. Content Moderation

Analyze video content for potentially sensitive material.

**Features:**
- Detects violence, graphic content, etc.
- Keyword-based analysis
- Confidence scoring
- Can be enhanced with custom ML models

**Backend Module:** `twelvelabvideoai/src/ai_features.py`

**Usage:**
```python
from ai_features import ContentModerator

moderator = ContentModerator()
result = await moderator.analyze_content(video_id)

# Returns:
# {
#     "success": True,
#     "is_safe": True,
#     "flags": [],
#     "confidence": 1.0,
#     "summary": "Family picnic in the park",
#     "topics": ["family", "outdoor", "picnic"]
# }
```

---

## 🔍 Advanced Search

### 1. Multi-Modal Search with Boolean Operators

Search across photos and videos with AND/OR logic.

**Features:**
- Boolean operators (AND/OR)
- Search photos only, videos only, or both
- Combines results intelligently
- Configurable result limits

**Backend Module:** `twelvelabvideoai/src/advanced_search.py`

**API Endpoint:** `POST /advanced_search`

**Usage:**
```python
from advanced_search import MultiModalSearch

searcher = MultiModalSearch()

# AND search - items must match ALL terms
results = searcher.search(
    query="sunset AND beach",
    operator="AND",
    search_photos=True,
    search_videos=True,
    top_k=20,
    min_similarity=0.3
)

# OR search - items can match ANY term
results = searcher.search(
    query="sunset OR sunrise",
    operator="OR",
    top_k=20
)
```

**Request Example:**
```bash
curl -X POST http://localhost:8080/advanced_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "beach AND sunset",
    "operator": "AND",
    "search_photos": true,
    "search_videos": true
  }'
```

**Response:**
```json
{
    "success": true,
    "query": "beach AND sunset",
    "operator": "AND",
    "photos": [...],
    "videos": [...],
    "total": 15
}
```

---

### 2. Temporal/Date-Based Search

Search media by date ranges, recent items, or specific time periods.

**Features:**
- Date range search
- Recent media (last N days)
- Search by year or month
- Optional album/type filters

**Backend Module:** `twelvelabvideoai/src/advanced_search.py`

**API Endpoint:** `POST /temporal_search`

**Usage:**
```python
from datetime import datetime
from advanced_search import TemporalSearch

searcher = TemporalSearch()

# Search by date range
results = searcher.search_by_date_range(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
    media_type="photo"  # Optional
)

# Search recent media
recent = searcher.search_recent(days=7)

# Search by year
year_2024 = searcher.search_by_year(2024)

# Search by month
january = searcher.search_by_month(2024, 1)
```

**Request Example:**
```bash
curl -X POST http://localhost:8080/temporal_search \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01T00:00:00",
    "end_date": "2024-12-31T23:59:59",
    "media_type": "photo",
    "album_name": "Vacation 2024"
  }'
```

---

### 3. Semantic Search with Context

Advanced search that considers additional context like location, time, and album.

**Features:**
- Natural language queries
- Context-aware filtering
- Location-based search (with GPS data)
- Album filtering

**Backend Module:** `twelvelabvideoai/src/advanced_search.py`

**Usage:**
```python
from advanced_search import SemanticSearch

searcher = SemanticSearch()

results = searcher.search_with_context(
    query="sunset on the beach",
    context={
        "date_range": {
            "start": datetime(2024, 6, 1),
            "end": datetime(2024, 8, 31)
        },
        "album": "Summer Vacation",
        "location": {"city": "San Diego"}
    },
    top_k=20
)
```

---

## 🎨 Creative Tools

### 1. Video Montage Generator

Create professional video compilations from multiple clips.

**Features:**
- Combine multiple video clips
- Add transitions (fade, dissolve, wipe)
- Optional background music
- Configurable clip duration
- Exports as MP4

**Backend Module:** `twelvelabvideoai/src/creative_tools.py`

**Usage:**
```python
from creative_tools import VideoMontageGenerator

generator = VideoMontageGenerator(output_dir="/path/to/output")

clips = [
    {"file_path": "/path/to/video1.mp4", "start_time": 10, "end_time": 15},
    {"file_path": "/path/to/video2.mp4", "start_time": 20, "end_time": 25},
    {"file_path": "/path/to/video3.mp4", "start_time": 5, "end_time": 10}
]

result = generator.create_montage(
    video_clips=clips,
    output_filename="my_montage.mp4",
    transition="fade",
    duration_per_clip=5.0,
    add_music=True,
    music_file="/path/to/music.mp3"
)

# Returns:
# {
#     "success": True,
#     "output_path": "/path/to/output/my_montage.mp4",
#     "duration": 15.0,
#     "num_clips": 3
# }
```

---

### 2. Photo Slideshow Creator

Convert photos into a video slideshow with transitions.

**Features:**
- Creates video from static images
- Smooth transitions between photos
- Configurable display duration
- Optional background music
- Custom resolution support
- Exports as MP4

**Backend Module:** `twelvelabvideoai/src/creative_tools.py`

**API Endpoint:** `POST /create_slideshow`

**Usage:**
```python
from creative_tools import SlideshowCreator

creator = SlideshowCreator(output_dir="/path/to/output")

photo_paths = [
    "/path/to/photo1.jpg",
    "/path/to/photo2.jpg",
    "/path/to/photo3.jpg"
]

result = creator.create_slideshow(
    photo_paths=photo_paths,
    output_filename="vacation_slideshow.mp4",
    duration_per_photo=3.0,
    transition="fade",
    add_music=True,
    music_file="/path/to/music.mp3",
    resolution=(1920, 1080)
)

# Returns:
# {
#     "success": True,
#     "output_path": "/path/to/output/vacation_slideshow.mp4",
#     "duration": 9.0,
#     "num_photos": 3,
#     "resolution": [1920, 1080]
# }
```

**Request Example:**
```bash
curl -X POST http://localhost:8080/create_slideshow \
  -H "Content-Type: application/json" \
  -d '{
    "photo_ids": [1, 2, 3, 4, 5],
    "duration_per_photo": 3.0
  }'
```

---

### 3. Video Clip Extractor

Extract specific segments from videos with precise timestamps.

**Features:**
- Extract clips by time range
- Re-encodes for accuracy
- Preserves video quality
- Batch extraction support
- Exports individual MP4 files

**Backend Module:** `twelvelabvideoai/src/creative_tools.py`

**API Endpoint:** `POST /extract_clip`

**Usage:**
```python
from creative_tools import ClipExtractor

extractor = ClipExtractor()

# Extract single clip
result = extractor.extract_clip(
    video_path="/path/to/video.mp4",
    start_time=120.5,  # 2 minutes 0.5 seconds
    end_time=135.0,    # 2 minutes 15 seconds
    output_filename="my_clip.mp4",
    output_dir="/path/to/output"
)

# Extract multiple clips
time_ranges = [(10, 20), (30, 45), (60, 75)]
results = extractor.extract_multiple_clips(
    video_path="/path/to/video.mp4",
    time_ranges=time_ranges,
    output_dir="/path/to/output"
)
```

**Request Example:**
```bash
curl -X POST http://localhost:8080/extract_clip \
  -H "Content-Type: application/json" \
  -d '{
    "media_id": 63,
    "start_time": 120.5,
    "end_time": 135.0
  }'
```

---

### 4. AI Thumbnail Suggester

Get AI-powered suggestions for best video thumbnail frames.

**Features:**
- Analyzes video content
- Identifies key moments
- Suggests best frames for thumbnails
- Uses TwelveLabs chapter/highlight analysis
- Returns timestamps with descriptions

**Backend Module:** `twelvelabvideoai/src/creative_tools.py`

**Usage:**
```python
from creative_tools import ThumbnailSuggester

suggester = ThumbnailSuggester()

result = await suggester.suggest_thumbnails(
    video_id="twelvelabs_video_id",
    num_suggestions=5
)

# Returns:
# {
#     "success": True,
#     "video_id": "...",
#     "suggestions": [
#         {
#             "timestamp": 45.2,
#             "reason": "Chapter start",
#             "description": "Beach scene begins"
#         },
#         {
#             "timestamp": 120.5,
#             "reason": "Key moment",
#             "description": "Sunset over ocean"
#         }
#     ]
# }
```

---

## 📡 API Endpoints Reference

### AI-Powered Features

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/find_similar/<media_id>` | GET | Find similar media items |
| `/auto_tag/<media_id>` | POST | Generate auto-tags for media |
| `/video_highlights/<media_id>` | GET | Get AI-generated highlights |

### Advanced Search

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/advanced_search` | POST | Multi-modal search with AND/OR |
| `/temporal_search` | POST | Search by date range |

### Creative Tools

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/extract_clip` | POST | Extract video clip |
| `/create_slideshow` | POST | Create photo slideshow |

---

## 💡 Usage Examples

### Example 1: Find Similar Photos and Create Slideshow

```python
import asyncio
from ai_features import SimilarMediaFinder
from creative_tools import SlideshowCreator

# Find similar vacation photos
finder = SimilarMediaFinder()
similar = finder.find_similar_photos(photo_id=42, top_k=10)

# Get file paths
photo_paths = [item['file_path'] for item in similar]

# Create slideshow
creator = SlideshowCreator()
slideshow = creator.create_slideshow(
    photo_paths=photo_paths,
    output_filename="similar_vacation_photos.mp4",
    duration_per_photo=4.0,
    add_music=True,
    music_file="vacation_music.mp3"
)

print(f"Created slideshow: {slideshow['output_path']}")
```

### Example 2: Advanced Search and Montage Creation

```python
from advanced_search import MultiModalSearch
from creative_tools import VideoMontageGenerator

# Search for beach videos
searcher = MultiModalSearch()
results = searcher.search(
    query="beach AND sunset",
    operator="AND",
    search_videos=True,
    search_photos=False,
    top_k=5
)

# Prepare clips from search results
clips = []
for video in results['videos'][:5]:
    clips.append({
        "file_path": video['file_path'],
        "start_time": video.get('start_time', 0),
        "end_time": video.get('end_time', 10)
    })

# Create montage
generator = VideoMontageGenerator()
montage = generator.create_montage(
    video_clips=clips,
    output_filename="beach_sunset_montage.mp4",
    transition="fade"
)

print(f"Created montage: {montage['output_path']}")
```

### Example 3: Temporal Search with Auto-Tagging

```python
from datetime import datetime
from advanced_search import TemporalSearch
from ai_features import AutoTagger

# Find recent videos
searcher = TemporalSearch()
recent = searcher.search_recent(days=30, media_type="video")

# Auto-tag all recent videos
tagger = AutoTagger()
for video in recent['results']:
    tags = await tagger.generate_tags(video['twelvelabs_id'])
    if tags['success']:
        tagger.save_tags_to_db(
            video['id'],
            tags['tags'],
            media_type="video"
        )
        print(f"Tagged {video['file_name']}: {tags['tags'][:3]}")
```

---

## 🛠️ Technical Requirements

### Dependencies

```bash
# Python packages
pip install flask httpx python-dotenv oracledb oci

# System requirements
- ffmpeg (for video/slideshow generation)
- Oracle Autonomous Database (for vector search)
- TwelveLabs API key
- OCI credentials (for object storage)
```

### Environment Variables

```bash
# TwelveLabs
TWELVE_LABS_API_KEY=your_api_key

# Oracle Database
ORACLE_DB_USERNAME=ADMIN
ORACLE_DB_PASSWORD=your_password
ORACLE_DB_CONNECT_STRING=your_connection_string
ORACLE_DB_WALLET_PATH=/path/to/wallet
ORACLE_DB_WALLET_PASSWORD=wallet_password

# OCI Object Storage
OCI_BUCKET=Media
OCI_NAMESPACE=your_namespace
OCI_REGION=us-phoenix-1
```

---

## 🚀 Getting Started

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure ffmpeg is installed:**
   ```bash
   # macOS
   brew install ffmpeg
   
   # Linux
   sudo apt-get install ffmpeg
   ```

3. **Start the Flask server:**
   ```bash
   python src/localhost_only_flask.py
   ```

4. **Access the application:**
   - Main UI: http://localhost:8080
   - API Documentation: http://localhost:8080/config_debug

---

## 📚 Additional Resources

- **Main README:** [README.md](./README.md)
- **TwelveLabs API Docs:** https://docs.twelvelabs.io/
- **Oracle Vector Search:** https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/
- **FFmpeg Documentation:** https://ffmpeg.org/documentation.html

---

## 🤝 Contributing

Contributions are welcome! Please ensure:
- Code follows existing style patterns
- New features include documentation
- Tests pass before submitting PRs

---

**Built with ❤️ using Oracle Cloud Infrastructure, TwelveLabs AI, and Python**
