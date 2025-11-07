# Metadata-Based Search Feature

## Overview

Added metadata-based search as a fallback mechanism when vector search fails or returns no results. This provides resilience against TwelveLabs API rate limits and enables text-based searching of media content.

## Implementation Date
November 8, 2025

## Features

### 1. **Automatic Fallback**
- Vector search automatically falls back to metadata search when:
  - No results are found
  - TwelveLabs API is unavailable/rate-limited
  - Vector search encounters errors

### 2. **Explicit Metadata Search**
- Can explicitly request metadata-only search via `search_mode` parameter
- Faster than vector search (no API calls)
- Works offline (no external API dependency)

### 3. **Search Fields**
Searches across multiple metadata fields:

**For Photos:**
- File name
- AI-generated tags
- Album name

**For Videos:**
- File name
- Video title
- AI-generated tags
- Album name

## API Usage

### Unified Search Endpoint: `/search_unified`

**Method**: POST

**Request Body**:
```json
{
  "query": "search text",
  "limit": 20,
  "album_filter": "optional_album_name",
  "min_similarity": 0.30,
  "search_mode": "vector"  // NEW: 'vector', 'metadata', or 'auto'
}
```

**Search Modes**:
- `"vector"` (default): Vector search with automatic metadata fallback
- `"metadata"`: Skip vector search, use metadata-only
- `"auto"`: Intelligent selection (future enhancement)

### Example Requests

#### 1. Standard Vector Search (with fallback)
```bash
curl -X POST http://150.136.235.189/search_unified \
  -H "Content-Type: application/json" \
  -d '{
    "query": "boys playing",
    "limit": 20
  }'
```

#### 2. Explicit Metadata-Only Search
```bash
curl -X POST http://150.136.235.189/search_unified \
  -H "Content-Type: application/json" \
  -d '{
    "query": "birthday party",
    "limit": 20,
    "search_mode": "metadata"
  }'
```

## Response Format

```json
{
  "results": [
    {
      "media_id": 123,
      "album_name": "Family Events",
      "file_name": "birthday_party_2024.mp4",
      "file_path": "/path/to/file",
      "file_type": "video",
      "created_at": "2024-11-07T12:00:00",
      "similarity": 0.85,
      "score": 0.85,
      "segment_start": null,
      "segment_end": null,
      "ai_tags": "birthday, celebration, children",
      "video_title": "Birthday Party Video",
      "match_type": "metadata"  // Indicates metadata search was used
    }
  ],
  "total": 1,
  "search_method": "metadata_only"
}
```

## Relevance Scoring

Metadata search uses keyword-based relevance scoring:

### Photos
- Filename match: +0.5 per keyword
- AI tags match: +0.3 per keyword
- Max score: 1.0

### Videos
- Filename match: +0.4 per keyword
- Video title match: +0.4 per keyword
- AI tags match: +0.2 per keyword
- Max score: 1.0

## Code Changes

### Modified Files

1. **`src/search_unified_flask_safe.py`**
   - Added `search_by_metadata()` function (lines 336-497)
   - Modified `search_unified_vectors()` to include fallback logic
   - Automatic fallback on zero results
   - Error handling with metadata fallback

2. **`src/localhost_only_flask.py`**
   - Added `search_mode` parameter to `/search_unified` endpoint
   - Support for explicit metadata-only search
   - Updated logging to track search mode

### New Functions

#### `search_by_metadata(query_text, user_id, album_name, top_k)`
```python
def search_by_metadata(
    query_text: str, 
    user_id: int = None, 
    album_name: str = None, 
    top_k: int = 50
) -> List[Dict[str, Any]]:
    """Fallback search using metadata
    
    Searches:
    - Photo filenames and AI tags
    - Video filenames, titles, and AI tags
    
    Returns results with relevance scores based on keyword matches
    """
```

## Benefits

### 1. **Reliability**
- Search works even when TwelveLabs API is down/rate-limited
- No dependency on external services for basic search

### 2. **Performance**
- Faster than vector search (no API calls)
- Direct database queries with indexes
- Suitable for simple text-based searches

### 3. **Cost Savings**
- Reduces TwelveLabs API usage for simple queries
- Users can choose metadata search for basic lookups

### 4. **User Experience**
- Seamless fallback - users always get results when possible
- No "search failed" errors when API is unavailable
- Clear indication of search method used

## Limitations

### 1. **Semantic Understanding**
- No semantic/contextual understanding
- Exact keyword matching only
- Example: "happy children" won't match "joyful kids"

### 2. **Accuracy**
- Depends on quality of metadata (filenames, AI tags)
- May return less relevant results than vector search
- Score calculation is heuristic-based

### 3. **No Visual Search**
- Cannot search by visual content
- Only searches text metadata
- Example: Can't find "red car" in a video unless metadata mentions it

## Future Enhancements

### Planned Features
1. **Hybrid Search**: Combine vector and metadata scores
2. **Fuzzy Matching**: Handle typos and variations
3. **Synonym Expansion**: "kids" matches "children"
4. **Phrase Matching**: Boost exact phrase matches
5. **Date Range Filtering**: Search within time ranges
6. **Advanced Relevance**: ML-based ranking

## Testing

### Test Scenarios

#### 1. Normal Operation
```bash
# Vector search should work normally
curl -X POST http://150.136.235.189/search_unified \
  -H "Content-Type: application/json" \
  -d '{"query": "sunset beach", "limit": 10}'
```

#### 2. API Rate Limited
```bash
# Should automatically fall back to metadata
# (Test when TwelveLabs API is rate limited)
curl -X POST http://150.136.235.189/search_unified \
  -H "Content-Type: application/json" \
  -d '{"query": "family vacation", "limit": 10}'
```

#### 3. Explicit Metadata Search
```bash
# Should skip vector search entirely
curl -X POST http://150.136.235.189/search_unified \
  -H "Content-Type: application/json" \
  -d '{"query": "birthday", "limit": 10, "search_mode": "metadata"}'
```

### Expected Logs

**Vector Search with Fallback**:
```
INFO: 🔍 Unified search request: 'boys playing' (user: admin, limit: 20, mode: vector)
INFO: 🧠 Using Flask-safe Unified Vector DB search
INFO: ⚠️  No vector search results, trying metadata-based search...
INFO: 🔍 Metadata-based search for: 'boys playing'
INFO: ✅ Metadata fallback found 5 results
```

**Explicit Metadata Search**:
```
INFO: 🔍 Unified search request: 'birthday' (user: admin, limit: 20, mode: metadata)
INFO: 📝 Using metadata-only search (explicit mode)
INFO: 🔍 Metadata-based search for: 'birthday'
INFO: ✅ Metadata search found 8 results
```

## Deployment

### Prerequisites
- Oracle Database with `album_media` and `video_embeddings` tables
- AI_TAGS column populated with tags
- Video titles stored in `video_embeddings.video_title`

### Deployment Steps

1. **Copy updated files to VM**:
```bash
scp src/search_unified_flask_safe.py ubuntu@150.136.235.189:/home/dataguardian/TwelvelabsWithOracleVector/src/
scp src/localhost_only_flask.py ubuntu@150.136.235.189:/home/dataguardian/TwelvelabsWithOracleVector/src/
```

2. **Restart application**:
```bash
ssh ubuntu@150.136.235.189 "sudo systemctl restart dataguardian"
```

3. **Verify deployment**:
```bash
ssh ubuntu@150.136.235.189 "sudo journalctl -u dataguardian -f"
```

### Rollback
If issues occur, revert to previous version:
```bash
cd /home/dataguardian/TwelvelabsWithOracleVector
git checkout HEAD~1 src/search_unified_flask_safe.py src/localhost_only_flask.py
sudo systemctl restart dataguardian
```

## Monitoring

### Key Metrics to Track
1. **Search Mode Usage**: Vector vs Metadata vs Fallback
2. **Fallback Rate**: % of searches that fall back to metadata
3. **Result Counts**: Average results per search type
4. **API Error Rate**: Track when vector search fails

### Log Analysis Commands

**Count metadata fallback usage**:
```bash
ssh ubuntu@150.136.235.189 "sudo journalctl -u dataguardian --since today | grep -c 'Metadata fallback found'"
```

**Count explicit metadata searches**:
```bash
ssh ubuntu@150.136.235.189 "sudo journalctl -u dataguardian --since today | grep -c 'metadata-only search'"
```

**Track search modes**:
```bash
ssh ubuntu@150.136.235.189 "sudo journalctl -u dataguardian --since today | grep 'search request' | grep -oP 'mode: \w+' | sort | uniq -c"
```

## Support

### Common Issues

**Q: Metadata search returns no results**
- Check if AI_TAGS are populated: `SELECT COUNT(*) FROM album_media WHERE AI_TAGS IS NOT NULL`
- Verify video titles exist: `SELECT COUNT(*) FROM video_embeddings WHERE video_title IS NOT NULL`

**Q: Search always uses metadata (never vector)**
- Check TwelveLabs API status
- Verify API key is valid: Check `TWELVE_LABS_API_KEY` in `.env`
- Check rate limit status in logs

**Q: Results seem irrelevant**
- Metadata search is keyword-based, not semantic
- Improve metadata quality (better filenames, richer AI tags)
- Consider using vector search for semantic queries

## Conclusion

Metadata-based search provides a robust fallback mechanism that ensures search functionality remains available even when vector search is unavailable. It's particularly useful for:
- Simple filename/title searches
- When TwelveLabs API is rate-limited
- Offline or low-connectivity scenarios
- Cost-sensitive deployments

The automatic fallback ensures users always get results when possible, improving overall system reliability and user experience.
