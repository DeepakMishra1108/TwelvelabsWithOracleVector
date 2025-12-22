# Face Embedding Migration - Quick Reference

## ✅ What's Done (Dec 19, 2025 18:00 PST)

### Code Changes
- `src/utils/face_detection_helper.py` - TwelveLabs embedding generation (1024-dim)
- `src/localhost_only_flask.py` - Updated face tagging endpoint
- Deployed to production: ubuntu@150.136.235.189

### Database Migration
- Schema updated: `face_tags.face_embedding` VECTOR(512) → VECTOR(1024)
- All existing face embeddings cleared (will regenerate)
- Service running: 347MB memory, 6 gunicorn workers

---

## ⏳ What's Pending

### WAIT FOR: TwelveLabs API Rate Limit Reset
**Time**: Dec 20, 2025 00:02:50 UTC (approx 6 hours from now)  
**Current**: 100/100 requests used  

### Run After Reset:
```bash
ssh ubuntu@150.136.235.189
sudo -u dataguardian /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/python \
  /home/dataguardian/TwelvelabsWithOracleVector/scripts/regenerate_faces_standalone.py
```

**Expected**:
- Regenerate 13+ face tags
- Uses ~13-15 API requests
- Takes ~2-3 minutes

---

## 🎯 Architecture Change

### Before (BROKEN)
```
Photos:   TwelveLabs → 1024-dim ────┐
                                      ├─ Cannot compare!
Faces:    DeepFace   → 512-dim  ────┘
```

### After (UNIFIED) ✅
```
Photos:   TwelveLabs → 1024-dim ────┐
                                      ├─ Same vector space!
Faces:    TwelveLabs → 1024-dim ────┘
```

---

## 📁 Key Files

### Production Server
```
/home/dataguardian/TwelvelabsWithOracleVector/
├── src/
│   ├── localhost_only_flask.py (219KB, updated)
│   └── utils/
│       └── face_detection_helper.py (18KB, updated)
├── scripts/
│   ├── migrate_schema_standalone.py (✅ executed)
│   └── regenerate_faces_standalone.py (ready to run)
└── twelvelabvideoai/.env (API key)
```

### Local Development
```
/Users/deepamis/Documents/GitHub/TwelvelabsVideoAI/
├── FACE_EMBEDDING_MIGRATION.md (full documentation)
├── FACE_EMBEDDING_MIGRATION_QUICK.md (this file)
└── scripts/
    ├── test_twelvelabs_face_embedding.py (tested ✅)
    ├── migrate_schema_standalone.py (deployed ✅)
    └── regenerate_faces_standalone.py (deployed ✅)
```

---

## 🔍 Verification

### After Regeneration
```sql
-- Check embeddings
SELECT id, face_name, 
       LENGTH(face_embedding) as embedding_size,
       created_at
FROM face_tags
ORDER BY id;

-- Should show embedding_size = 8200 (1024 floats)
```

### Test Face Search
1. Navigate to: http://150.136.235.189:8080
2. Click on a photo
3. Tag a face or search existing face tags
4. Should return results in ~1-2 seconds

---

## 📊 Benefits Achieved

✅ Unified vector space for photos and faces  
✅ Face similarity search uses same model as photo search  
✅ Can do cross-modal semantic + face search (future)  
✅ Simpler architecture (one embedding model)  
✅ Better quality embeddings from TwelveLabs SOTA model  

---

## 🚨 Rollback (if needed)

### Restore Previous Code
```bash
cd /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI
git checkout HEAD~2 src/localhost_only_flask.py src/utils/face_detection_helper.py
scp src/*.py src/utils/*.py ubuntu@150.136.235.189:/tmp/
ssh ubuntu@150.136.235.189 "sudo mv /tmp/*.py /home/dataguardian/... && sudo systemctl restart dataguardian"
```

### Restore Schema
```sql
ALTER TABLE face_tags DROP COLUMN face_embedding;
ALTER TABLE face_tags ADD face_embedding VECTOR(512, FLOAT32);
-- Then regenerate with old DeepFace method
```

---

**Status**: Ready for face embedding regeneration after rate limit reset  
**Last Updated**: Dec 19, 2025 18:00 PST  
**Next Action**: Wait for Dec 20 00:02:50 UTC, then run regeneration script
