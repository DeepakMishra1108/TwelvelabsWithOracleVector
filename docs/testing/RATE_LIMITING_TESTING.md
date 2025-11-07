# Rate Limiting Testing Guide

## Quick Testing Steps

### 1. Check Rate Limiting is Working

```bash
# On server
ssh ubuntu@150.136.235.189
cd /home/ubuntu/TwelvelabsVideoAI
git pull origin main
sudo systemctl restart dataguardian
sudo systemctl status dataguardian
```

### 2. Test User Quotas Endpoint

```bash
# Get current user's quotas
curl -X GET http://localhost:5000/user/quotas \
  -H "Cookie: session=YOUR_SESSION_COOKIE"

# Expected response:
{
  "success": true,
  "user_id": 1,
  "username": "admin",
  "role": "admin",
  "quotas": {
    "uploads": {
      "current": 0,
      "max": null,
      "display": "0/∞",
      "period": "day"
    },
    "searches": {
      "current": 0,
      "max": null,
      "display": "0/∞",
      "period": "hour"
    },
    "api_calls": {
      "current": 0,
      "max": null,
      "display": "0/∞",
      "period": "minute"
    },
    "video_processing": {
      "current": 0,
      "max": null,
      "display": "0/∞",
      "period": "day",
      "unit": "minutes"
    },
    "storage": {
      "current": 0,
      "max": null,
      "display": "0/∞",
      "unit": "GB"
    }
  }
}
```

### 3. Test Rate Limit Enforcement

#### Create Test Editor User

```sql
-- Connect to Oracle database
sqlplus TELCOVIDEOENCODE/password@ocdmrealtime_high

-- Create test editor
INSERT INTO users (username, email, password_hash, role) VALUES (
  'test_editor',
  'editor@test.com',
  '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5ND2JL5.ksqyG', -- password: testpass123
  'editor'
);
COMMIT;
```

#### Test Upload Quota

```bash
# As editor user (100 uploads/day limit)
# Make 101 upload requests

for i in {1..101}; do
  echo "Upload $i"
  curl -X POST http://localhost:5000/upload_unified \
    -H "Cookie: session=EDITOR_SESSION" \
    -F "mediaFile=@test.jpg" \
    -F "album_name=test"
done

# Upload #101 should return:
{
  "error": "Rate limit exceeded",
  "message": "Daily upload limit: 100/100. Please try tomorrow.",
  "retry_after": 86400,
  "limit_type": "uploads_per_day"
}
```

#### Test Search Quota

```bash
# As editor user (1000 searches/hour limit)
# Make 1001 search requests

for i in {1..1001}; do
  echo "Search $i"
  curl -X POST http://localhost:5000/search_unified \
    -H "Cookie: session=EDITOR_SESSION" \
    -H "Content-Type: application/json" \
    -d '{"query": "test search"}'
done

# Search #1001 should return:
{
  "error": "Rate limit exceeded",
  "message": "Search limit: 1000/1000 per hour. Please wait.",
  "retry_after": 3600,
  "limit_type": "searches_per_hour"
}
```

### 4. Monitor Usage Logs

```sql
-- View recent uploads
SELECT user_id, action_type, action_details, timestamp 
FROM user_usage_log 
WHERE action_type = 'upload' 
ORDER BY timestamp DESC 
FETCH FIRST 20 ROWS ONLY;

-- View recent searches
SELECT user_id, action_type, action_details, timestamp 
FROM user_usage_log 
WHERE action_type = 'search' 
ORDER BY timestamp DESC 
FETCH FIRST 20 ROWS ONLY;

-- Get user activity summary
SELECT 
    u.username,
    u.role,
    COUNT(*) as total_actions,
    COUNT(CASE WHEN l.action_type = 'upload' THEN 1 END) as uploads,
    COUNT(CASE WHEN l.action_type = 'search' THEN 1 END) as searches
FROM users u
LEFT JOIN user_usage_log l ON u.id = l.user_id
WHERE l.timestamp > SYSTIMESTAMP - INTERVAL '24' HOUR
GROUP BY u.username, u.role
ORDER BY total_actions DESC;
```

### 5. View Current Rate Limits

```sql
-- Check all users' rate limits
SELECT 
    u.id,
    u.username,
    u.role,
    r.max_uploads_per_day,
    r.max_searches_per_hour,
    r.max_api_calls_per_minute,
    r.uploads_today,
    r.searches_this_hour,
    r.api_calls_this_minute
FROM users u
LEFT JOIN user_rate_limits r ON u.id = r.user_id
ORDER BY u.id;
```

### 6. Manually Adjust User Quotas

```sql
-- Give user more upload quota
UPDATE user_rate_limits 
SET max_uploads_per_day = 200 
WHERE user_id = 2;
COMMIT;

-- Reset daily counters for user
UPDATE user_rate_limits 
SET uploads_today = 0,
    video_minutes_today = 0,
    last_daily_reset = SYSTIMESTAMP
WHERE user_id = 2;
COMMIT;

-- Give user unlimited searches
UPDATE user_rate_limits 
SET max_searches_per_hour = NULL
WHERE user_id = 2;
COMMIT;
```

### 7. Test Counter Auto-Reset

```sql
-- Check when counters will reset
SELECT 
    user_id,
    uploads_today,
    last_daily_reset,
    SYSTIMESTAMP - last_daily_reset as time_since_daily_reset,
    CASE 
        WHEN SYSTIMESTAMP - last_daily_reset >= INTERVAL '1' DAY 
        THEN 'Will reset on next request'
        ELSE 'No reset needed'
    END as daily_status
FROM user_rate_limits
WHERE user_id = 2;
```

## Expected Behavior

### Role-Based Quotas

| Role | Uploads/Day | Searches/Hour | API Calls/Min | Video Min/Day | Storage |
|------|-------------|---------------|---------------|---------------|---------|
| **Admin** | ∞ | ∞ | ∞ | ∞ | ∞ |
| **Editor** | 100 | 1000 | 60 | 120 | 50 GB |
| **Viewer** | 0 | 500 | 30 | 0 | 0 GB |

### HTTP Status Codes

- **200 OK** - Request within quota
- **429 Too Many Requests** - Quota exceeded
  - Response includes `retry_after` in seconds
  - Response includes `limit_type` (uploads_per_day, searches_per_hour, etc.)

### Counter Reset Times

- **Daily (24 hours)**: uploads_today, video_minutes_today
- **Hourly (60 minutes)**: searches_this_hour
- **Minute (60 seconds)**: api_calls_this_minute

Counters reset automatically on next request after time window expires.

## Troubleshooting

### Rate Limiting Not Working

```bash
# Check if rate_limiter.py can be imported
python3 -c "import sys; sys.path.insert(0, '/home/ubuntu/TwelvelabsVideoAI/twelvelabvideoai/src'); from rate_limiter import rate_limit_api; print('✅ Import successful')"

# Check logs
sudo journalctl -u dataguardian -n 100 | grep -i "rate"
```

### Check Database Tables Exist

```sql
-- Verify tables exist
SELECT table_name FROM user_tables 
WHERE table_name IN ('USER_RATE_LIMITS', 'USER_USAGE_LOG');

-- Check foreign keys
SELECT constraint_name, constraint_type 
FROM user_constraints 
WHERE table_name IN ('USER_RATE_LIMITS', 'USER_USAGE_LOG');
```

### Reset Everything for a User

```sql
-- Complete reset for user 2
UPDATE user_rate_limits 
SET uploads_today = 0,
    searches_this_hour = 0,
    api_calls_this_minute = 0,
    video_minutes_today = 0,
    storage_used_gb = 0,
    last_daily_reset = SYSTIMESTAMP,
    last_hourly_reset = SYSTIMESTAMP,
    last_minute_reset = SYSTIMESTAMP
WHERE user_id = 2;
COMMIT;

-- Delete usage log
DELETE FROM user_usage_log WHERE user_id = 2;
COMMIT;
```

## Integration with Frontend

### Display User Quotas in UI

Add to user dropdown or profile page:

```javascript
// Fetch user quotas
fetch('/user/quotas')
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      const quotas = data.quotas;
      console.log('Uploads:', quotas.uploads.display);
      console.log('Searches:', quotas.searches.display);
      console.log('Storage:', quotas.storage.display);
      
      // Update UI
      document.getElementById('quota-uploads').textContent = quotas.uploads.display;
      document.getElementById('quota-searches').textContent = quotas.searches.display;
      document.getElementById('quota-storage').textContent = quotas.storage.display;
    }
  });
```

### Handle 429 Errors

```javascript
// In your upload/search functions
fetch('/upload_unified', {
  method: 'POST',
  body: formData
})
.then(response => {
  if (response.status === 429) {
    return response.json().then(data => {
      alert(data.message); // Show user-friendly message
      throw new Error('Rate limit exceeded');
    });
  }
  return response.json();
})
.then(data => {
  // Handle success
})
.catch(error => {
  console.error('Error:', error);
});
```

## Success Criteria

✅ Rate limiting decorators imported successfully  
✅ All 7 routes protected with rate limits  
✅ /user/quotas endpoint returns valid JSON  
✅ 429 responses when quota exceeded  
✅ Usage logged to USER_USAGE_LOG  
✅ Counters increment correctly  
✅ Counters reset automatically after time window  
✅ Admin has unlimited quotas  
✅ Editor has configured quotas  
✅ Viewer has restricted quotas  

## Next Steps

1. **Test in Production** - Deploy and verify rate limiting works
2. **Add Video Quota Checks** - Check video processing minutes before montage/slideshow
3. **Update OCI Paths** - Use user-specific storage paths
4. **Create Admin UI** - Dashboard to manage user quotas
5. **Monitor & Adjust** - Review usage patterns and adjust quotas as needed

---

**Status:** ✅ Rate limiting core implementation complete and ready for testing!
