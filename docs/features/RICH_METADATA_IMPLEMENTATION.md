# Rich Metadata Extraction Implementation Summary

## Overview
Implementing unified photo processing with GPT-4o-mini for natural language search capabilities.

## Architecture

### 1. Database Schema
```sql
-- New column added to album_media table
ALTER TABLE album_media ADD (
    rich_metadata CLOB CHECK (rich_metadata IS JSON)
);
```

**Status**: Schema script ready (`scripts/add_rich_metadata_column.py`)
**Issue**: Database connection timeout from server - needs to be run directly on DB server

### 2. GPT-4o-mini Vision Metadata Extractor

**File**: `src/utils/gpt_vision_metadata.py`
**Status**: ✅ COMPLETE

**Features**:
- Extracts structured JSON metadata from images
- Uses GPT-4o-mini vision model (cost: ~$0.15 per 1000 images)
- Returns: setting, objects, people_count, activities, clothing, colors, mood, time_of_day, weather, scene_type, tags

**Sample Output**:
```json
{
  "setting": "outdoor",
  "location_type": "beach",
  "objects": ["ocean", "sunset", "rocks"],
  "people_count": 2,
  "activities": ["posing", "smiling"],
  "clothing": ["red dress", "casual shirt"],
  "colors": ["orange", "blue", "red"],
  "mood": "happy",
  "time_of_day": "evening",
  "weather": "sunny",
  "scene_type": "portrait",
  "tags": ["beach sunset", "couple photo", "red dress", "golden hour"]
}
```

### 3. Next Steps

#### Phase 1: Database Setup ⏳
1. Add `rich_metadata` column to `album_media` table
   - Run on DB server directly (connection timeout issue)
   - Or run from Flask app startup

#### Phase 2: Unified Photo Processor 📝
Create `src/utils/unified_photo_processor.py`:
```python
class UnifiedPhotoProcessor:
    def process_photo(self, image_path, media_id):
        # Run 3 processes in parallel:
        # 1. ImageBind embedding (already exists)
        # 2. DeepFace face detection (already exists)  
        # 3. GPT-4o-mini metadata extraction (NEW)
        # Store all results in database
```

#### Phase 3: Integration 🔌
1. Update upload endpoint to use `UnifiedPhotoProcessor`
2. Add metadata extraction to photo upload flow
3. Async processing to avoid blocking uploads

#### Phase 4: Search Enhancement 🔍
Update `search_unified_flask_safe.py`:
```sql
-- Add metadata search
SELECT * FROM album_media
WHERE JSON_EXISTS(rich_metadata, '$.tags[*]?(@ like_regex "beach" flag "i")')
   OR JSON_EXISTS(rich_metadata, '$.clothing[*]?(@ like_regex "red" flag "i")')
```

#### Phase 5: Backfill Existing Photos 🔄
Create `scripts/backfill_rich_metadata.py`:
- Process all 242 existing photos
- Extract metadata with GPT-4o-mini
- Update database
- **Cost**: ~$0.04 (242 photos * $0.15/1000)

## Cost Analysis

**One-time Processing** (242 photos):
- GPT-4o-mini: $0.04
- Time: ~2-3 minutes (tier 1 rate limits)

**Ongoing** (per new photo):
- GPT-4o-mini: $0.00015
- ImageBind: Free (local)
- DeepFace: Free (local)
- Total per photo: ~$0.00015

**Monthly** (assuming 1000 new photos):
- GPT-4o-mini: $0.15/month

## Benefits

1. **Natural Language Search**: "Show me photos of Rahul wearing red shirt at the beach"
2. **Automatic Categorization**: By setting, mood, activity, time of day
3. **Better Face Context**: "Rahul at birthday party" vs just "Rahul"
4. **Rich Filtering**: Filter by weather, time of day, indoor/outdoor
5. **Smart Tags**: Automatically generated searchable keywords

## Files Created

1. ✅ `src/utils/gpt_vision_metadata.py` - GPT-4o-mini extractor
2. ✅ `scripts/add_rich_metadata_column.py` - Database schema update
3. ✅ `scripts/add_rich_metadata_column.sql` - SQL schema update

## Files to Create

1. 📝 `src/utils/unified_photo_processor.py` - Main processor
2. 📝 `scripts/backfill_rich_metadata.py` - Backfill existing photos
3. 🔧 Update `src/localhost_only_flask.py` - Integrate into upload
4. 🔧 Update `src/search_unified_flask_safe.py` - Add metadata search

## Ready to Proceed?

The GPT-4o-mini metadata extractor is ready. Next steps:
1. Fix database connection and add `rich_metadata` column
2. Create unified photo processor
3. Integrate into upload flow
4. Test with sample photos
5. Backfill existing 242 photos
6. Update search to use rich metadata

Estimated total implementation time: 2-3 hours
Estimated cost for all 242 photos: $0.04
