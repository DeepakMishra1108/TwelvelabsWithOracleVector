# Quick Reference: Face Tag Search & Embedding Regeneration

## ✅ What Was Done

### 1. Regenerated Embeddings for "Rahul Wedding" Album
- **Status:** 99/109 photos completed ✅
- **Remaining:** 10 photos (waiting for API rate limit reset)
- **Reset Time:** 2025-12-20 00:02:50Z UTC

### 2. Added Face Tag Search Feature
- **Location:** Main search bar area (below album filter)
- **How to Use:**
  1. Enter person name in "Search by person name..." field
  2. Click "Find Person" or press Enter
  3. View all photos with that person

---

## 🚀 How to Use Face Search

### From the Web UI:
1. Go to: https://150.136.235.189:8443
2. Login with your credentials
3. Look for the search field with person icon (👤)
4. Type a name (e.g., "Rahul", "John")
5. Press Enter or click "Find Person"

### Features:
- **Case-insensitive:** "RAHUL" = "Rahul" = "rahul"
- **Partial match:** "Rah" finds "Rahul"
- **Fast:** Uses local database (no API calls)
- **Private:** Only shows your own photos

---

## 🔄 Complete Remaining Embeddings

### Run After Rate Limit Resets (Dec 20, 2025):
```bash
# SSH into server
ssh ubuntu@150.136.235.189

# Run regeneration script
sudo -u dataguardian \
  /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/python \
  /home/dataguardian/TwelvelabsWithOracleVector/scripts/regenerate_album_embeddings.py \
  "Rahul Wedding"
```

### Expected Output:
```
============================================================
🔄 Album-Specific Embeddings Regeneration Script
============================================================

📊 Checking for photos in album: Rahul Wedding...
📷 Found 10 photos in album: Rahul Wedding

[1/10] Processing: WhatsApp Image...
🧠 Creating embedding...
✅ Embedding created and stored

...

============================================================
📊 Summary:
   Album: Rahul Wedding
   ✅ Successfully processed: 10
   ❌ Failed: 0
   📷 Total: 10
============================================================
```

---

## 📊 Current Status

### Service Status:
```bash
# Check if service is running
sudo systemctl status dataguardian.service

# Should show:
# Active: active (running)
# Memory: ~322MB
# Workers: 6 gunicorn processes
```

### Database Status:
- **Rahul Wedding Album:** 99/109 photos with embeddings
- **Face Tags:** All stored with OpenCV embeddings (512-dim)
- **Search:** Fully functional for name-based queries

---

## 🎯 Testing Checklist

### Test Face Search:
- [ ] Navigate to application URL
- [ ] Login successfully
- [ ] See face search input field
- [ ] Enter a person name
- [ ] Press Enter or click "Find Person"
- [ ] See relevant photos displayed
- [ ] Click photo to view full size
- [ ] See face bounding boxes on photo

### Test Embedding Regeneration (After Dec 20):
- [ ] SSH into server
- [ ] Run regeneration script
- [ ] See progress for all 10 remaining photos
- [ ] Verify 100% completion (10/10)
- [ ] No API rate limit errors

---

## 🛠️ Troubleshooting

### Face Search Not Working:
```bash
# Check logs
sudo journalctl -u dataguardian.service -f

# Restart service
sudo systemctl restart dataguardian.service
```

### Embedding Script Fails:
```bash
# Check Python environment
/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/python --version
# Should show: Python 3.11.14

# Check environment variables
sudo -u dataguardian printenv | grep TWELVE_LABS_API_KEY
# Should show: tlk_0QMJEF93SQEJ4125DJH8N3VW65BF
```

### Rate Limit Error:
**Error Message:**
```json
{
  "code": "too_many_requests",
  "message": "You have exceeded the rate limit (100req/1day). Please try again later after 2025-12-20T00:02:50Z."
}
```

**Solution:** Wait until the reset time, then run script again.

---

## 📝 Files Modified

1. **Backend:** `/home/dataguardian/TwelvelabsWithOracleVector/src/localhost_only_flask.py`
   - Added `/search/faces` endpoint

2. **Frontend:** `/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src/templates/index.html`
   - Added face search input field
   - Added `searchByFace()` JavaScript function

3. **Script:** `/home/dataguardian/TwelvelabsWithOracleVector/scripts/regenerate_album_embeddings.py`
   - New album-specific embedding regeneration script

---

## 💡 Tips

### For Best Results:
- Use specific names (e.g., "Rahul" instead of "R")
- Check tagged faces first (use "Faces" button on photos)
- Tag faces consistently with same name format
- Use Enter key for faster searches

### Performance:
- Face search is instant (uses database index)
- No TwelveLabs API calls during search
- Results load as fast as regular search

### Privacy:
- You only see your own photos
- Face tags are private to your account
- Admins can see all photos (RBAC applies)

---

## 📞 Need Help?

**Service Issues:**
- Check: `sudo systemctl status dataguardian.service`
- Logs: `sudo journalctl -u dataguardian.service -n 100`

**Database Issues:**
- Check connectivity: Test from Flask app
- Verify wallet: `/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet`

**API Issues:**
- Rate Limit: Wait for reset time
- Invalid API Key: Check `.env` file for TWELVE_LABS_API_KEY

---

## 🎉 What's New

### Face Tag Search:
- ✅ Search photos by person name
- ✅ Instant results from local database
- ✅ No API usage during search
- ✅ Private and secure (RBAC-aware)

### Embedding Regeneration:
- ✅ Album-specific regeneration
- ✅ Auto file size optimization
- ✅ Progress tracking
- ✅ Error handling

### User Experience:
- ✅ Clean search interface
- ✅ Enter key support
- ✅ Clear status messages
- ✅ Integrated with existing UI
