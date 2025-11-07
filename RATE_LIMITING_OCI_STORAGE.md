# Rate Limiting & Multi-Tenant OCI Storage Implementation

**Completion Date:** 7 November 2025  
**Commit:** 87c7aa4

---

## 🎯 Implementation Summary

Successfully implemented **per-user rate limiting** and **multi-tenant OCI object storage** to control resource usage and isolate user data in the cloud.

---

## ✅ Completed Features

### 1. Rate Limiting System

#### Database Schema

**USER_RATE_LIMITS Table:**
```sql
- user_id (FK to users, CASCADE DELETE)
- max_uploads_per_day
- max_searches_per_hour
- max_api_calls_per_minute
- max_video_processing_minutes_per_day
- max_storage_gb
- uploads_today
- searches_this_hour
- api_calls_this_minute
- video_minutes_today
- storage_used_gb
- last_daily_reset
- last_hourly_reset
- last_minute_reset
```

**USER_USAGE_LOG Table:**
```sql
- user_id (FK to users)
- action_type (upload, search, api_call, video_processing)
- action_details
- resource_consumed
- timestamp
- ip_address
```

#### Role-Based Quotas

| Role | Uploads/Day | Searches/Hour | API Calls/Min | Video Min/Day | Storage (GB) |
|------|-------------|---------------|---------------|---------------|--------------|
| **Admin** | ∞ | ∞ | ∞ | ∞ | ∞ |
| **Editor** | 100 | 1000 | 60 | 120 | 50 |
| **Viewer** | 0 | 500 | 30 | 0 | 0 |

#### Flask Decorators

**`rate_limiter.py` module provides:**

1. **`@rate_limit_api`** - Enforces API calls per minute
   - Returns 429 when limit exceeded
   - Auto-resets every minute
   - Logs all API calls

2. **`@rate_limit_search`** - Enforces searches per hour
   - Returns 429 when limit exceeded
   - Auto-resets every hour
   - Logs query text

3. **`@rate_limit_upload`** - Enforces uploads per day
   - Returns 429 when limit exceeded
   - Auto-resets daily
   - Logs filename

4. **`check_video_processing_quota()`** - Video processing limits
   - Check before processing
   - Returns (allowed, message, current, max)
   - Call `consume_video_processing_quota()` after

5. **`check_storage_quota()`** - Storage limits
   - Check before upload
   - Returns (allowed, message, current, max)
   - Call `update_storage_usage()` after

6. **`get_user_quota_summary()`** - Get all quotas for display
   - Returns formatted usage/limits
   - Used in UI dashboards

#### Auto-Reset Logic

- **Daily counters**: Reset after 24 hours
  - Uploads
  - Video processing minutes

- **Hourly counters**: Reset after 1 hour
  - Search queries

- **Minute counters**: Reset after 1 minute
  - API calls

#### Usage Logging

Every action logged to `USER_USAGE_LOG`:
- Action type and details
- Resource consumed (e.g., video duration)
- Timestamp
- IP address

---

### 2. Multi-Tenant OCI Storage

#### Folder Structure

```
/users/
  /{user_id}/
    /uploads/
      /photos/          - Original uploaded photos
      /videos/          - Original uploaded videos
      /chunks/          - Video chunks from slicer
    /generated/
      /montages/        - Video montages
      /slideshows/      - Photo slideshows
      /clips/           - Extracted clips
      /compressed/      - Compressed videos
    /thumbnails/
      /videos/          - Video thumbnails
      /photos/          - Photo thumbnails
    /embeddings/        - Cached embeddings
    /temp/              - Temporary processing files
```

**Benefits:**
- Complete user isolation
- Easy CASCADE DELETE (delete all user content)
- Organized by content type
- Clear separation of originals vs generated
- Storage usage calculation per user

#### OCI Storage Functions

**`oci_storage.py` module provides:**

**Path Generators:**
- `get_user_upload_path(user_id, type, filename)` - Upload paths
- `get_user_generated_path(user_id, type, filename)` - Generated paths
- `get_user_thumbnail_path(user_id, type, filename)` - Thumbnail paths
- `get_user_embedding_path(user_id, filename)` - Embedding paths
- `get_user_temp_path(user_id, filename)` - Temp file paths

**File Operations:**
- `upload_to_oci(local_path, oci_path)` - Upload file
- `download_from_oci(oci_path, local_path)` - Download file
- `delete_from_oci(oci_path)` - Delete file

**User Management:**
- `list_user_objects(user_id, prefix)` - List all user files
- `get_user_storage_usage(user_id)` - Calculate total storage
- `delete_user_storage(user_id, dry_run)` - Delete all user files

**Convenience Functions:**
- `upload_user_photo(user_id, local_path, filename)`
- `upload_user_video(user_id, local_path, filename)`
- `upload_generated_montage(user_id, local_path, filename)`
- `upload_generated_slideshow(user_id, local_path, filename)`

---

## 📊 Database State

### Current Rate Limits

```
====================================================================
CURRENT RATE LIMITS AND USAGE
====================================================================
User ID  Username  Role   Uploads      Searches     API Calls      
--------------------------------------------------------------------
1        admin     admin  0/∞          0/∞          0/∞            
====================================================================
```

**Admin user has:**
- Unlimited uploads
- Unlimited searches
- Unlimited API calls
- Unlimited video processing
- Unlimited storage

**New users will get quotas based on their role (editor/viewer).**

---

## 🔧 Usage Examples

### Applying Rate Limits to Routes

```python
from rate_limiter import rate_limit_api, rate_limit_search, rate_limit_upload

@app.route('/api/something')
@login_required
@rate_limit_api
def api_endpoint():
    return jsonify({'result': 'success'})

@app.route('/search')
@login_required
@rate_limit_search
def search():
    query = request.args.get('query')
    results = perform_search(query)
    return jsonify(results)

@app.route('/upload', methods=['POST'])
@login_required
@rate_limit_upload
def upload():
    file = request.files['file']
    save_file(file)
    return jsonify({'success': True})
```

### Video Processing Quota

```python
from rate_limiter import check_video_processing_quota, consume_video_processing_quota

@app.route('/process_video', methods=['POST'])
@login_required
def process_video():
    video_duration = get_video_duration(video_file)
    
    # Check quota before processing
    allowed, message, current, max_quota = check_video_processing_quota(
        current_user.id, 
        video_duration
    )
    
    if not allowed:
        return jsonify({'error': message}), 429
    
    # Process video
    process_video_file(video_file)
    
    # Consume quota after successful processing
    consume_video_processing_quota(current_user.id, video_duration)
    
    return jsonify({'success': True})
```

### Storage Quota

```python
from rate_limiter import check_storage_quota, update_storage_usage

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files['file']
    file_size_gb = os.path.getsize(file) / (1024**3)
    
    # Check storage quota
    allowed, message, current, max_storage = check_storage_quota(
        current_user.id,
        file_size_gb
    )
    
    if not allowed:
        return jsonify({'error': message}), 429
    
    # Upload file
    save_file(file)
    
    # Update storage usage
    update_storage_usage(current_user.id, file_size_gb)
    
    return jsonify({'success': True})
```

### Using OCI Storage

```python
from oci_storage import upload_user_photo, get_user_upload_path

@app.route('/upload_photo', methods=['POST'])
@login_required
@rate_limit_upload
def upload_photo():
    file = request.files['photo']
    
    # Save locally first
    local_path = f'/tmp/{file.filename}'
    file.save(local_path)
    
    # Upload to OCI with user-specific path
    success, url_or_error = upload_user_photo(
        current_user.id,
        local_path,
        file.filename
    )
    
    if not success:
        return jsonify({'error': url_or_error}), 500
    
    # Clean up local file
    os.remove(local_path)
    
    return jsonify({
        'success': True,
        'url': url_or_error,
        'oci_path': get_user_upload_path(current_user.id, 'photo', file.filename)
    })
```

### Admin Dashboard - View User Quotas

```python
from rate_limiter import get_user_quota_summary

@app.route('/admin/user_quotas')
@login_required
@admin_required
def view_user_quotas():
    user_id = request.args.get('user_id')
    
    quotas = get_user_quota_summary(user_id)
    
    return render_template('admin_quotas.html', quotas=quotas)
```

**Returns:**
```json
{
  "uploads": {
    "current": 15,
    "max": 100,
    "display": "15/100 (15.0%)",
    "period": "day"
  },
  "searches": {
    "current": 234,
    "max": 1000,
    "display": "234/1000 (23.4%)",
    "period": "hour"
  },
  "storage": {
    "current": 12.5,
    "max": 50,
    "display": "12.5/50 (25.0%)",
    "unit": "GB"
  }
}
```

---

## 📈 Error Responses

### Rate Limit Exceeded (429)

```json
{
  "error": "Rate limit exceeded",
  "message": "API call limit: 60/60 per minute. Please wait.",
  "retry_after": 60,
  "limit_type": "api_calls_per_minute"
}
```

```json
{
  "error": "Rate limit exceeded",
  "message": "Daily upload limit: 100/100. Please try tomorrow.",
  "retry_after": 86400,
  "limit_type": "uploads_per_day"
}
```

### Video Processing Quota Exceeded

```json
{
  "error": "Insufficient video processing quota. Need 15 min, have 5 min remaining (Daily limit: 120 min)"
}
```

### Storage Quota Exceeded

```json
{
  "error": "Insufficient storage quota. Need 2.50 GB, have 1.20 GB remaining (Limit: 50 GB)"
}
```

---

## 🚀 Deployment Steps

### 1. Database Migration (Already Done ✅)

```bash
python scripts/create_rate_limits_table.py
```

**Output:**
```
✅ USER_RATE_LIMITS table created
✅ USER_USAGE_LOG table created
✅ Initialized rate limits for 1 users
```

### 2. Deploy to Production

```bash
ssh ubuntu@150.136.235.189
cd /home/ubuntu/TwelvelabsVideoAI
git pull origin main
sudo systemctl restart dataguardian
```

### 3. Apply Rate Limits to Routes

**Priority routes to protect:**
- `/search_unified` - Add `@rate_limit_search`
- `/upload`, `/upload_video` - Add `@rate_limit_upload`
- `/api/*` endpoints - Add `@rate_limit_api`
- Video processing routes - Use `check_video_processing_quota()`

### 4. Configure OCI

**Add to `.env`:**
```bash
OCI_NAMESPACE=your_namespace
OCI_BUCKET_NAME=video-ai-storage
OCI_CONFIG_FILE=~/.oci/config
OCI_PROFILE=DEFAULT
OCI_REGION=us-ashburn-1
```

**Create OCI bucket:**
```bash
oci os bucket create \
  --name video-ai-storage \
  --compartment-id <your_compartment_id>
```

### 5. Update Upload Handlers

Replace direct file saves with OCI uploads:

```python
# Before:
save_path = f'/var/www/uploads/{filename}'
file.save(save_path)

# After:
from oci_storage import upload_user_photo

local_temp = f'/tmp/{filename}'
file.save(local_temp)
success, url = upload_user_photo(current_user.id, local_temp, filename)
os.remove(local_temp)
```

---

## 📝 Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `scripts/create_rate_limits_table.py` | Database schema migration | 295 |
| `twelvelabvideoai/src/rate_limiter.py` | Rate limiting middleware | 620 |
| `twelvelabvideoai/src/oci_storage.py` | Multi-tenant OCI storage | 545 |
| `scripts/execute_migration.py` | Data migration helper | 86 |

**Total:** 1,546 lines of new code

---

## 🔍 Monitoring & Admin Tasks

### View Rate Limit Status

```bash
python scripts/create_rate_limits_table.py
```

### Query Usage Log

```sql
-- Recent uploads
SELECT user_id, action_details, timestamp 
FROM user_usage_log 
WHERE action_type = 'upload' 
ORDER BY timestamp DESC 
FETCH FIRST 20 ROWS ONLY;

-- User with most API calls
SELECT user_id, COUNT(*) as call_count
FROM user_usage_log
WHERE action_type = 'api_call'
AND timestamp > SYSTIMESTAMP - INTERVAL '1' HOUR
GROUP BY user_id
ORDER BY call_count DESC;
```

### Update User Quotas

```sql
-- Give user more upload quota
UPDATE user_rate_limits 
SET max_uploads_per_day = 200 
WHERE user_id = 5;

-- Reset daily counters manually
UPDATE user_rate_limits 
SET uploads_today = 0, 
    video_minutes_today = 0,
    last_daily_reset = SYSTIMESTAMP 
WHERE user_id = 5;
```

### Calculate Total Storage Usage

```python
from oci_storage import get_user_storage_usage

success, usage = get_user_storage_usage(user_id=5)
print(f"User 5 storage: {usage['total_size_gb']} GB")
print(f"Object count: {usage['object_count']}")
```

---

## 🎯 Next Steps

### Immediate (Priority 1)

1. **Apply Rate Limits to Flask Routes**
   - Add decorators to search endpoints
   - Add decorators to upload endpoints
   - Add video processing quota checks

2. **Update Upload Handlers**
   - Modify photo upload to use OCI paths
   - Modify video upload to use OCI paths
   - Update generated content saves

### Short Term (Priority 2)

3. **Create Admin Dashboard**
   - View all users' quotas
   - Adjust user limits
   - View usage logs
   - Generate usage reports

4. **Storage Quota Enforcement**
   - Calculate file sizes before upload
   - Check storage quota
   - Update storage usage after upload
   - Periodic storage audit

### Long Term (Priority 3)

5. **Enhanced Features**
   - Email notifications at 80% quota
   - Quota reset notifications
   - Usage analytics dashboard
   - Automatic quota adjustments based on user behavior

---

## ✅ Success Metrics

| Metric | Status |
|--------|--------|
| Rate limiting database schema | ✅ Created |
| User quotas initialized | ✅ Complete |
| Rate limiting middleware | ✅ Implemented |
| OCI storage structure | ✅ Designed |
| OCI storage functions | ✅ Implemented |
| Data migration | ✅ Executed |
| Documentation | ✅ Complete |

**Overall Status:** 🎉 **CORE IMPLEMENTATION COMPLETE**

---

## 📞 Support

**Database:** Oracle 23ai (FREEPDB1/TELCOVIDEOENCODE)  
**Server:** ubuntu@150.136.235.189  
**Repository:** github.com/DeepakMishra1108/TwelvelabsWithOracleVector  
**Commit:** 87c7aa4

---

**Next Action:** Apply rate limit decorators to Flask routes and update upload handlers to use OCI storage paths.
