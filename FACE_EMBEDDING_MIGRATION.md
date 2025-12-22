# Face Embedding Migration: DeepFace → TwelveLabs

## Overview
Migration from dual-embedding architecture to unified TwelveLabs-based system.

### Problem
- **Before**: Photos (1024-dim TwelveLabs) + Faces (512-dim DeepFace) = Incompatible vector spaces
- **After**: Photos (1024-dim TwelveLabs) + Faces (1024-dim TwelveLabs) = Unified vector space

### Benefits
✅ Unified vector space for all embeddings  
✅ Face and photo embeddings are directly comparable  
✅ Simpler architecture (one embedding model)  
✅ Can do semantic + face unified search  
✅ Better quality face embeddings from state-of-the-art model  

---

## Implementation Status

### ✅ Completed
1. **Updated `face_detection_helper.py`**
   - New function: `generate_face_embedding_twelvelabs()` (1024-dim)
   - Updated `EMBEDDING_DIM` constant: 512 → 1024
   - Updated placeholder embeddings: 512 → 1024
   - Uses TwelveLabs Marengo-retrieval-2.7 model with base64 image data

2. **Updated `localhost_only_flask.py`**
   - Face tagging now uses `generate_face_embedding_twelvelabs()`
   - Automatically falls back to placeholder if TwelveLabs fails
   - Passes API key from Flask config

3. **Created Migration Scripts**
   - `migrate_schema_standalone.py` - Updates database schema (✅ EXECUTED)
   - `regenerate_face_embeddings_twelvelabs.py` - Regenerates all face embeddings
   - `test_twelvelabs_face_embedding.py` - Test script (verified working)

4. **Deployed to Production**
   - All code files deployed to ubuntu@150.136.235.189
   - Service restarted successfully
   - Database schema migrated: VECTOR(512) → VECTOR(1024) ✅

### ⏳ Pending
1. ~~Run database migration on production~~ ✅ DONE
2. Regenerate existing face tag embeddings (13+ tags) - **AFTER RATE LIMIT RESET**
3. ~~Deploy updated code to production server~~ ✅ DONE

---

## Deployment Steps

### Prerequisites
- TwelveLabs API rate limit resets: **Dec 20, 2025 00:02:50 UTC**
- Current usage: 100/100 requests used
- Estimated requests needed: ~15 (13 face tags + 2 buffer)

### Step 1: Database Schema Migration (Production)
```bash
ssh ubuntu@150.136.235.189

# Run migration
sudo -u dataguardian /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/python \
  /home/dataguardian/TwelvelabsWithOracleVector/scripts/migrate_face_embeddings_to_1024.py
```

**What it does:**
- Drops `face_tags.face_embedding` column (512-dim)
- Recreates as VECTOR(1024, FLOAT32)
- ⚠️ **Clears all existing face embeddings**

### Step 2: Deploy Updated Code
```bash
# From local machine
cd /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI

# Copy updated files
scp src/localhost_only_flask.py ubuntu@150.136.235.189:/tmp/
scp src/utils/face_detection_helper.py ubuntu@150.136.235.189:/tmp/
scp scripts/regenerate_face_embeddings_twelvelabs.py ubuntu@150.136.235.189:/tmp/

# On server
ssh ubuntu@150.136.235.189

sudo mv /tmp/localhost_only_flask.py /home/dataguardian/TwelvelabsWithOracleVector/src/
sudo mv /tmp/face_detection_helper.py /home/dataguardian/TwelvelabsWithOracleVector/src/utils/
sudo mv /tmp/regenerate_face_embeddings_twelvelabs.py /home/dataguardian/TwelvelabsWithOracleVector/scripts/

sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/

# Restart service
sudo systemctl restart dataguardian.service
sudo systemctl status dataguardian.service --no-pager
```

### Step 3: Regenerate Face Embeddings (After Rate Limit Reset)
```bash
# Wait until: Dec 20, 2025 00:02:50 UTC
# Then run on production:

sudo -u dataguardian /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/python \
  /home/dataguardian/TwelvelabsWithOracleVector/scripts/regenerate_face_embeddings_twelvelabs.py
```

**What it does:**
- Fetches all 13+ face tags from database
- Downloads each photo from OCI Object Storage
- Crops face region with 20% padding
- Generates TwelveLabs 1024-dim embedding for each face
- Updates `face_tags` table with new embeddings

**Expected output:**
```
✅ Successful: 13
❌ Failed: 0
📈 Total: 13
```

### Step 4: Verification
```bash
# Check face tag embeddings
SELECT id, face_name, 
       LENGTH(face_embedding) as embedding_dim,
       confidence
FROM face_tags
ORDER BY id;

# Should show embedding_dim = 1024 for all rows

# Test face search
curl -X POST http://localhost:8080/search/faces \
  -H "Content-Type: application/json" \
  -d '{"face_name": "Deepak"}'
```

---

## Technical Details

### TwelveLabs Embed API
```python
# Generate face embedding
task = client.embed.create(
    model_name="Marengo-retrieval-2.7",
    image_url=f"data:image/jpeg;base64,{base64_data}"
)
task.wait_for_done(sleep_interval=0.5, timeout=30)
embedding = task.image_embedding.segments[0].embeddings_float  # 1024-dim
```

### Face Crop Strategy
- Detects faces using DeepFace with RetinaFace backend (local, free)
- Crops face region with 20% padding for context
- Embeds cropped region using TwelveLabs

### Vector Search
```sql
-- Now works because both are 1024-dim TwelveLabs vectors
SELECT ft.id, ft.face_name, 
       VECTOR_DISTANCE(ft.face_embedding, :query_embedding, COSINE) as distance
FROM face_tags ft
ORDER BY distance
LIMIT 10
```

---

## API Rate Limit Management

### Current Status
- **Limit**: 100 requests/day
- **Used**: 100/100
- **Resets**: Dec 20, 2025 00:02:50 UTC
- **Wait time**: ~6.5 hours from now

### Usage Estimate
| Task | Requests | Notes |
|------|----------|-------|
| Regenerate 13 face tags | 13 | One per tag |
| New face tagging | 1-2/tag | As users tag faces |
| Photo embedding regen | 10 | Remaining from album |
| **Buffer** | 5 | For retries/errors |
| **Total** | 28-30 | ~30% of daily quota |

### Recommendation
✅ Wait for rate limit reset before running Step 3  
✅ Run face embedding regeneration first (priority)  
✅ Complete remaining 10 photo embeddings after  

---

## Rollback Plan

If issues arise, rollback steps:

### 1. Restore Previous Code
```bash
# Restore from git
git checkout HEAD~1 src/localhost_only_flask.py
git checkout HEAD~1 src/utils/face_detection_helper.py

# Deploy
scp src/* ubuntu@150.136.235.189:/tmp/
ssh ubuntu@150.136.235.189 "sudo mv /tmp/*.py /home/dataguardian/TwelvelabsWithOracleVector/src/"
```

### 2. Restore Database Schema
```sql
-- Recreate 512-dim column
ALTER TABLE face_tags DROP COLUMN face_embedding;
ALTER TABLE face_tags ADD face_embedding VECTOR(512, FLOAT32);

-- Regenerate with DeepFace (OLD METHOD)
-- Note: This would require restoring old embedding generation code
```

---

## Files Changed

### Modified
- `src/localhost_only_flask.py` - Face tagging endpoint
- `src/utils/face_detection_helper.py` - Embedding generation

### Created
- `scripts/migrate_face_embeddings_to_1024.py` - Schema migration
- `scripts/regenerate_face_embeddings_twelvelabs.py` - Data migration
- `scripts/test_twelvelabs_face_embedding.py` - Testing

### Database Schema
- `face_tags.face_embedding`: VECTOR(512) → VECTOR(1024)

---

## Next Steps

### ✅ COMPLETED (Dec 19, 2025)
- [x] Code changes (face_detection_helper.py, localhost_only_flask.py)
- [x] Migration scripts created
- [x] Code deployed to production
- [x] Database schema migrated (512-dim → 1024-dim)
- [x] Service restarted successfully

### ⏳ WAITING FOR RATE LIMIT RESET (Dec 20, 00:02:50 UTC)

After the TwelveLabs API rate limit resets, run on production:

```bash
# SSH to production
ssh ubuntu@150.136.235.189

# Run regeneration script
sudo -u dataguardian /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/python \
  /home/dataguardian/TwelvelabsWithOracleVector/scripts/regenerate_faces_standalone.py
```

**Expected outcome:**
- 13+ face tags regenerated with 1024-dim TwelveLabs embeddings
- Face search will work with unified vector space
- Can compare face embeddings with photo embeddings

### 🎯 Final Verification

After regeneration completes:

```bash
# 1. Check database
SELECT id, face_name, LENGTH(face_embedding) as dims
FROM face_tags
ORDER BY id;

# Should show dims = 8200 (1024 floats × 8 bytes = 8192, plus header)

# 2. Test face search in browser
# http://150.136.235.189:8080
# Click on photo → Tag faces → Search by face name
```

---

## Success Metrics

✅ All face tags have 1024-dim embeddings  
✅ Face search returns results in <2 seconds  
✅ Face and photo embeddings comparable in same vector space  
✅ No DeepFace dependencies for embeddings (detection only)  
✅ Unified architecture with single embedding model  

---

**Last Updated**: Dec 19, 2025 17:15 PST  
**Status**: Ready for deployment (waiting for rate limit reset)
