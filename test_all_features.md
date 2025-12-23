# Comprehensive Feature Test Plan
**Date:** 2025-12-22
**Server:** https://150.136.235.189:8443

## Test Checklist

### 1. Authentication & User Management
- [ ] **Login** - User can log in successfully
- [ ] **Logout** - User can log out
- [ ] **Session persistence** - Session stays active across page refreshes
- [ ] **Admin access** - Admin users see Admin Tools menu

### 2. Photo Upload & Display
- [ ] **Upload photo** - Single photo upload works
- [ ] **Bulk upload** - Multiple photos upload works
- [ ] **View album** - Photos display in gallery view
- [ ] **Image URLs** - Thumbnails and full images load from OCI
- [ ] **Photo metadata** - File name, date, size display correctly

### 3. Face Recognition (ImageBind - Priority Fix)
- [ ] **Camera Search (Selfie)** - Upload selfie and find matching photos
  - Status: ✅ FIXED - Images now display
  - Backend: 100 matches, 63 photos, distances 0.26-0.45
  - Backfill: 90/965 faces complete (9.3%)
- [ ] **Person Search** - Search by person name
  - Status: ⚠️ BROKEN - ORA-22848 VECTOR in DISTINCT (FIXED - needs testing)
- [ ] **Face Tagging** - Manual face tagging works
- [ ] **Face Detection** - Auto-detect faces in uploaded photos
- [ ] **Admin: Backfill Embeddings** - Regenerate face embeddings
  - Status: ✅ WORKING - 20 faces/batch, ~50 seconds

### 4. Video Features
- [ ] **Video upload** - Upload video file
- [ ] **Video playback** - Stream video from OCI
- [ ] **Video thumbnails** - Generate and display thumbnails
- [ ] **Video segments** - TwelveLabs segment detection

### 5. Search Features
- [ ] **Unified Search** - Natural language search across photos/videos
  - Status: ⚠️ NEEDS TESTING
- [ ] **Metadata Search** - Search by filename, date, album
- [ ] **Tag Search** - Search by tags
- [ ] **Vector Search** - Semantic search using embeddings

### 6. Album Management
- [ ] **Create album** - Create new album
- [ ] **Rename album** - Change album name
- [ ] **Delete album** - Remove album and contents
- [ ] **Move photos** - Move photos between albums
- [ ] **Album filtering** - Filter view by album

### 7. Admin Features
- [ ] **Admin Tools page** - Access at /admin_tools
- [ ] **User management** - Create/edit/delete users
- [ ] **System stats** - View database counts
- [ ] **Init Tracking** - Initialize face embedding tracking
- [ ] **Start Backfill** - Regenerate face embeddings (batch)

## Known Issues to Fix

### High Priority (Blocking)
1. ✅ **FIXED** - Camera search images not displaying (media_stream endpoint missing)
2. ✅ **FIXED** - Wrong deployment directory (ubuntu vs dataguardian)
3. ⚠️ **Person search ORA-22848** - FIXED but needs testing
4. ⚠️ **Unified search** - Reported broken, needs investigation

### Medium Priority
5. **Backfill incomplete** - 875/965 faces remaining (~2-3 hours manual clicking)
6. **Threshold too high** - selfie_search.py line 17: 1.5 → should reset to 0.6 after backfill
7. **Worker count low** - gunicorn: 1 worker (should increase to 2 after backfill)
8. **HTTP service disabled** - Only HTTPS running (may need HTTP for internal)

### Low Priority
9. **Placeholder image** - 1x1 pixel (should be proper placeholder)
10. **Static folder** - Created manually (should be in git)
11. **PAR URL caching** - 63 sequential OCI calls (could batch/cache)

## Test Execution Steps

### Quick Smoke Test (5 minutes)
```bash
1. Open https://150.136.235.189:8443
2. Login as admin
3. Upload 1 test photo → verify displays
4. Camera search with selfie → verify images load
5. Person search for "Deepak" → verify results
6. Unified search for "people" → verify results
```

### Full Feature Test (30 minutes)
Run through all checkboxes above systematically

### Performance Test
```bash
# Check memory usage
ssh ubuntu@150.136.235.189 'ps aux | grep gunicorn'

# Check logs for errors
ssh ubuntu@150.136.235.189 'sudo journalctl -u dataguardian-https.service -n 100 --no-pager | grep -E "ERROR|Error|Failed"'

# Check database
sqlplus username/password@database << EOF
SELECT COUNT(*) FROM face_tags WHERE imagebind_processed = 1;
SELECT COUNT(*) FROM face_tags WHERE imagebind_processed = 0;
SELECT COUNT(*) FROM album_media WHERE file_type = 'photo';
EOF
```

## Critical Files Status

### Deployed to Production
- ✅ `/home/dataguardian/TwelvelabsWithOracleVector/src/localhost_only_flask.py`
  - media_stream endpoint added ✅
  - media_thumbnail endpoint fixed ✅
  - Person search DISTINCT removed ✅
- ✅ `/home/dataguardian/TwelvelabsWithOracleVector/src/static/placeholder.jpg`
  - 1x1 pixel placeholder created

### Needs Deployment
- ⚠️ `src/utils/selfie_search.py` - threshold 1.5 → 0.6 (AFTER backfill)
- ⚠️ `gunicorn_config_https.py` - workers 1 → 2 (AFTER backfill)

### Git Status
- ⚠️ Local changes not committed
- ⚠️ Production code differs from git

## Next Steps

### Immediate (Now)
1. Test person search (verify ORA-22848 fix)
2. Test unified search (investigate error)
3. Fix any blocking issues found

### Short Term (Today)
4. Complete backfill (875 faces remaining)
5. Reset threshold to 0.6
6. Increase workers to 2
7. Test end-to-end face search workflow

### Medium Term (This Week)
8. Commit and push all fixes to git
9. Create proper placeholder image
10. Add automated backfill script
11. Document all API endpoints
12. Create monitoring dashboard

## Success Criteria

**Minimal Viable:**
- ✅ Login works
- ✅ Photos upload and display
- ✅ Camera search finds and displays photos
- ✅ Person search works without errors
- ⚠️ Unified search returns results

**Full Production Ready:**
- All 965 faces have ImageBind embeddings
- All search types work correctly
- No 500 errors in logs
- Response times < 5 seconds
- Memory stable < 1GB per worker
- 24-hour uptime without crashes
