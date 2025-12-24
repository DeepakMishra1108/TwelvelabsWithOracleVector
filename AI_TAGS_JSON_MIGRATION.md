# AI_TAGS CLOB to JSON Migration

## Overview
Successfully migrated AI_TAGS column from CLOB (Character Large Object) to native JSON format, aligning it with the rich_metadata column implementation.

## Problem
- **Error**: "Object of type LOB is not JSON serializable" when generating auto-tags
- **Root Cause**: AI_TAGS stored as CLOB, which returns LOB objects that can't be directly JSON serialized
- **Performance**: CLOB requires reading entire object, slower than native JSON operations
- **Inconsistency**: rich_metadata was already JSON, but AI_TAGS was still CLOB

## Solution

### 1. Migration Script (`scripts/migrate_ai_tags_to_json.py`)
Converts existing AI_TAGS data from CLOB to JSON format:
- Reads existing CLOB data (20 records migrated)
- Parses structured text format (TITLE, CATEGORIES, SUBJECTS, HASHTAGS, CONFIDENCE)
- Creates JSON structure with metadata
- Atomic column swap (ai_tags_new → AI_TAGS)

### 2. Updated Auto-Tagging Logic

#### Video Tags (ImageBind)
**Old Format** (Plain Text):
```
CATEGORIES: sports and athletics, nature and outdoors
HASHTAGS: #sports_and_athletics #nature_and_outdoors
CONFIDENCE: 87.50% match to 'sports and athletics'
```

**New Format** (JSON):
```json
{
  "categories": ["sports and athletics", "nature and outdoors"],
  "hashtags": ["#sports_and_athletics", "#nature_and_outdoors"],
  "confidence": "87.50%",
  "top_match": "sports and athletics",
  "generated_by": "imagebind",
  "version": "2.0",
  "raw_text": "CATEGORIES: ..."
}
```

#### Photo Tags (OpenAI Vision)
**New Format** (JSON):
```json
{
  "title": "Mountain Landscape at Sunset",
  "subjects": ["mountain", "sunset", "landscape"],
  "hashtags": ["#mountain", "#sunset", "#nature"],
  "raw_text": "TITLE: Mountain Landscape...",
  "generated_by": "openai_vision",
  "version": "2.0"
}
```

### 3. Code Changes

#### LOB Handling Fix
```python
# Before: Assumed CLOB was auto-converted
existing_tags = row[4] if len(row) > 4 else None

# After: Handle LOB objects properly
existing_tags_raw = row[4] if len(row) > 4 else None
if existing_tags_raw:
    if hasattr(existing_tags_raw, 'read'):
        existing_tags = existing_tags_raw.read()  # Read LOB
    else:
        existing_tags = str(existing_tags_raw)
```

#### JSON Storage
```python
import json
tags_json = {
    "categories": [...],
    "hashtags": [...],
    "generated_by": "imagebind",
    "version": "2.0"
}

cursor.execute("""
    UPDATE album_media 
    SET AI_TAGS = :tags 
    WHERE id = :id
""", {"tags": json.dumps(tags_json), "id": media_id})
```

## Benefits

### 1. **Performance**
- ✅ Native JSON operations (JSON_TEXTCONTAINS, JSON_VALUE)
- ✅ Faster queries and indexing
- ✅ No CLOB read overhead

### 2. **Consistency**
- ✅ Both AI_TAGS and rich_metadata use JSON
- ✅ Unified GPT model usage across features
- ✅ Same data structure for natural language search

### 3. **Maintainability**
- ✅ Structured data instead of parsing text
- ✅ Easy to extend with new fields
- ✅ Type-safe JSON validation

### 4. **Functionality**
- ✅ Fixed LOB serialization error
- ✅ Searchable tags using JSON functions
- ✅ Better integration with search_unified_flask_safe

## GPT Model Optimization

### Current Usage
1. **Natural Language Search** (rich_metadata):
   - Uses GPT-4o Vision API
   - Generates structured metadata on upload
   - Stored as JSON in rich_metadata column
   - Used by search_unified_flask_safe for semantic search

2. **Auto-Tagging** (AI_TAGS):
   - **Photos**: GPT-4o Vision API (title, subjects, hashtags)
   - **Videos**: ImageBind embeddings (categories, confidence)
   - Now stored as JSON in AI_TAGS column
   - Used by tag generation modal

### Unified Approach
Both features now:
- ✅ Store data as JSON
- ✅ Use similar structured formats
- ✅ Support JSON-based search operations
- ✅ Share GPT-4o Vision for photos
- ✅ Use ImageBind for video analysis

### Cost Optimization
- Rich metadata generated once on upload
- Auto-tags generated on-demand (user request)
- ImageBind used for videos (free, local)
- GPT-4o Vision only for photos when requested

## Migration Results
```
📋 Current AI_TAGS type: CLOB
📝 Step 1: Creating temporary ai_tags_new JSON column...
📝 Step 2: Converting text tags to JSON format...
   Found 20 records with AI_TAGS
✅ Converted 20 records to JSON
📝 Step 3: Swapping columns...
✅ Migration completed successfully!
✅ Verified: AI_TAGS is now JSON
```

## Database Schema

### Before
```sql
AI_TAGS CLOB
```

### After
```sql
AI_TAGS JSON
```

## Testing
- ✅ Migration script tested on production (20 records)
- ✅ Service restarted successfully
- ✅ No serialization errors
- ✅ Auto-tagging works for both photos and videos
- ✅ Search functionality maintained

## Files Modified
1. `scripts/migrate_ai_tags_to_json.py` - Migration script
2. `src/localhost_only_flask.py` - Updated auto_tag endpoint
3. `src/search_unified_flask_safe.py` - Already uses JSON operations

## Rollback Plan
If issues occur:
1. Stop services
2. Restore from backup
3. Re-run migration with data preservation

## Future Enhancements
- [ ] Add JSON schema validation
- [ ] Create JSON indexes for faster search
- [ ] Unified GPT prompt for both features
- [ ] Batch auto-tagging for albums
- [ ] Tag confidence scoring
