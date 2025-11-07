# OCI Path Isolation Testing Guide

## Overview

This document provides comprehensive testing procedures for verifying user-specific OCI storage path isolation in the multi-tenant TwelveLabs Video AI system.

## 🎯 Testing Objectives

1. ✅ **Path Generation**: Verify path functions generate correct user-specific paths
2. ✅ **Code Implementation**: Confirm upload handlers use isolation functions
3. 🔄 **OCI Configuration**: Validate OCI is properly configured
4. 🔄 **Database Setup**: Ensure test users exist
5. 🔄 **Actual Uploads**: Test real file uploads go to correct paths
6. 🔄 **Access Control**: Verify users cannot access other users' files

## 📋 Prerequisites

### Local Development Testing
- Python 3.8+
- Project dependencies installed
- `.env` file configured
- OCI SDK installed: `pip install oci`

### Production VM Testing
- SSH access to OCI VM: `ssh ubuntu@150.136.235.189`
- OCI configured with `~/.oci/config`
- Environment variables in `.env`:
  ```bash
  OCI_NAMESPACE=your_namespace
  OCI_BUCKET_NAME=video-ai-storage
  OCI_CONFIG_FILE=~/.oci/config
  OCI_PROFILE=DEFAULT
  ```

## 🧪 Automated Tests

### Test 1: Path Generation Functions ✅

**Status**: PASSED (Local)

**What it tests**:
- `get_user_upload_path()` generates correct paths
- `get_user_generated_path()` generates correct paths
- User IDs are properly isolated

**Expected Results**:
```
User 1:
  users/1/uploads/photos/vacation.jpg
  users/1/uploads/videos/beach.mp4
  users/1/uploads/chunks/video_chunk_0.mp4
  users/1/generated/montages/summer_2024.mp4
  users/1/generated/slideshows/photos_show.mp4

User 2:
  users/2/uploads/photos/test.jpg
  users/2/generated/montages/test.mp4
```

**Run Test**:
```bash
python scripts/test_oci_path_isolation.py
```

### Test 2: OCI Configuration ⏳

**Status**: Pending (Requires production VM)

**What it tests**:
- `OCI_NAMESPACE` environment variable set
- `OCI_BUCKET_NAME` environment variable set
- `~/.oci/config` file exists
- OCI client can initialize
- Can connect to OCI namespace

**Setup on VM**:
```bash
# 1. Setup OCI CLI (if not done)
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"

# 2. Configure OCI
oci setup config

# 3. Add to .env
echo "OCI_NAMESPACE=your_namespace" >> .env
echo "OCI_BUCKET_NAME=video-ai-storage" >> .env

# 4. Test connection
oci os ns get
```

### Test 3: Database Users ⏳

**Status**: Pending

**What it tests**:
- Users table has at least 2 users for isolation testing
- User data is accessible

**Create Test Users**:
```bash
# Create admin user (if not exists)
python scripts/create_admin_user.py

# Create additional test editor user
python -c "
from twelvelabvideoai.utils.db_utils import get_flask_safe_connection
import bcrypt

with get_flask_safe_connection() as conn:
    cursor = conn.cursor()
    hashed = bcrypt.hashpw('TestPass123!'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute('''
        INSERT INTO users (username, email, hashed_password, role)
        VALUES ('test_editor', 'editor@test.com', :pwd, 'editor')
    ''', {'pwd': hashed})
    conn.commit()
    print('✅ Test editor user created')
"
```

### Test 4: Code Inspection ✅

**Status**: PASSED (Local)

**What it tests**:
- `localhost_only_flask.py` uses `get_user_upload_path()`
- `localhost_only_flask.py` uses `get_user_generated_path()`
- Upload routes exist: `upload_unified`, `create_montage`, `create_slideshow`

**Results**:
```
✅ get_user_upload_path: Found 4 occurrence(s)
✅ get_user_generated_path: Found 3 occurrence(s)
✅ upload_unified route: Found 1 occurrence(s)
✅ create_montage route: Found 1 occurrence(s)
✅ create_slideshow route: Found 1 occurrence(s)
```

### Test 5: OCI Bucket Structure ⏳

**Status**: Pending (Requires uploads)

**What it tests**:
- OCI bucket contains `users/` prefix
- User directories exist: `users/1/`, `users/2/`, etc.
- Files are in correct subdirectories

**Manual Check**:
```bash
# List all user directories
oci os object list --bucket-name video-ai-storage --prefix users/ --delimiter /

# List user 1's uploads
oci os object list --bucket-name video-ai-storage --prefix users/1/uploads/

# List user 1's generated content
oci os object list --bucket-name video-ai-storage --prefix users/1/generated/
```

## 🔬 Manual Testing Procedures

### Procedure 1: Photo Upload Isolation

**Objective**: Verify photos upload to user-specific paths

**Steps**:

1. **Start Flask Application**:
   ```bash
   cd /home/ubuntu/TwelvelabsVideoAI
   sudo systemctl start dataguardian
   # Or: python src/localhost_only_flask.py
   ```

2. **Test User 1 Upload**:
   - Open browser: `https://mishras.online`
   - Login as user 1 (e.g., admin user)
   - Navigate to Upload page
   - Upload a test photo: `test_photo_user1.jpg`
   - Note the success message

3. **Verify User 1 Path in OCI**:
   ```bash
   oci os object list \
     --bucket-name video-ai-storage \
     --prefix users/1/uploads/photos/ \
     | grep test_photo_user1.jpg
   ```
   
   **Expected**: File found at `users/1/uploads/photos/test_photo_user1.jpg`

4. **Test User 2 Upload**:
   - Logout from user 1
   - Login as user 2 (e.g., test_editor)
   - Upload a test photo: `test_photo_user2.jpg`

5. **Verify User 2 Path in OCI**:
   ```bash
   oci os object list \
     --bucket-name video-ai-storage \
     --prefix users/2/uploads/photos/ \
     | grep test_photo_user2.jpg
   ```
   
   **Expected**: File found at `users/2/uploads/photos/test_photo_user2.jpg`

6. **Verify Isolation**:
   ```bash
   # User 1's photo should NOT be in user 2's directory
   oci os object list \
     --bucket-name video-ai-storage \
     --prefix users/2/uploads/photos/ \
     | grep test_photo_user1.jpg
   # Expected: No results
   ```

### Procedure 2: Video Upload Isolation

**Objective**: Verify videos upload to user-specific paths

**Steps**:

1. **Test User 1 Video Upload**:
   - Login as user 1
   - Upload test video: `test_video_user1.mp4`
   
2. **Verify Path**:
   ```bash
   oci os object list \
     --bucket-name video-ai-storage \
     --prefix users/1/uploads/videos/ \
     | grep test_video_user1.mp4
   ```
   
   **Expected**: `users/1/uploads/videos/test_video_user1.mp4`

3. **Test User 2 Video Upload**:
   - Login as user 2
   - Upload test video: `test_video_user2.mp4`
   
4. **Verify Path**:
   ```bash
   oci os object list \
     --bucket-name video-ai-storage \
     --prefix users/2/uploads/videos/ \
     | grep test_video_user2.mp4
   ```
   
   **Expected**: `users/2/uploads/videos/test_video_user2.mp4`

### Procedure 3: Generated Content Isolation (Slideshow)

**Objective**: Verify generated slideshows go to user-specific paths

**Steps**:

1. **Create Slideshow as User 1**:
   - Login as user 1
   - Navigate to Albums or Photo Gallery
   - Select multiple photos
   - Click "Create Slideshow"
   - Wait for generation to complete
   - Note the slideshow filename (e.g., `slideshow_20251107_123456.mp4`)

2. **Verify Path in OCI**:
   ```bash
   oci os object list \
     --bucket-name video-ai-storage \
     --prefix users/1/generated/slideshows/ \
     | grep slideshow_20251107_123456.mp4
   ```
   
   **Expected**: File at `users/1/generated/slideshows/slideshow_20251107_123456.mp4`

3. **Create Slideshow as User 2**:
   - Logout, login as user 2
   - Upload some photos
   - Create slideshow
   
4. **Verify Path in OCI**:
   ```bash
   oci os object list \
     --bucket-name video-ai-storage \
     --prefix users/2/generated/slideshows/
   ```
   
   **Expected**: User 2's slideshow in `users/2/generated/slideshows/`

### Procedure 4: Generated Content Isolation (Montage)

**Objective**: Verify generated montages go to user-specific paths

**Steps**:

1. **Create Montage as User 1**:
   - Login as user 1
   - Upload videos or use existing
   - Navigate to video selection page
   - Select multiple videos or clips
   - Click "Create Montage"
   - Wait for generation
   - Note the montage filename

2. **Verify Path in OCI**:
   ```bash
   oci os object list \
     --bucket-name video-ai-storage \
     --prefix users/1/generated/montages/
   ```
   
   **Expected**: Montage at `users/1/generated/montages/{filename}`

3. **Repeat for User 2**

### Procedure 5: Access Control Testing

**Objective**: Verify users cannot access other users' files

**Steps**:

1. **Get User 1's File URL**:
   - Login as user 1
   - Upload a photo
   - Right-click on the photo in gallery
   - Copy image URL or download URL
   - Example: `https://objectstorage.region.oraclecloud.com/n/namespace/b/video-ai-storage/o/users/1/uploads/photos/private.jpg?signature=...`

2. **Attempt Access as User 2**:
   - Logout from user 1
   - Login as user 2
   - Paste user 1's file URL in browser
   
   **Expected Result**: 
   - HTTP 403 Forbidden, OR
   - Redirect to login/error page, OR
   - "Access Denied" message

3. **Attempt Direct OCI Access** (if presigned URLs not used):
   - Copy user 1's file path: `users/1/uploads/photos/private.jpg`
   - Try to access via user 2's session
   
   **Expected**: Application-level access control prevents viewing

4. **Check Application Logs**:
   ```bash
   sudo journalctl -u dataguardian -n 50 | grep -i "access denied\|forbidden"
   ```
   
   **Expected**: Log entries showing denied access attempts

## 📊 Test Results Template

### Run Date: [DATE]
### Tester: [NAME]

| Test | Status | Notes |
|------|--------|-------|
| Path Generation | ✅ / ❌ | |
| OCI Configuration | ✅ / ❌ | |
| Database Users | ✅ / ❌ | |
| Code Inspection | ✅ / ❌ | |
| OCI Bucket Structure | ✅ / ❌ | |
| Photo Upload - User 1 | ✅ / ❌ | Path: |
| Photo Upload - User 2 | ✅ / ❌ | Path: |
| Video Upload - User 1 | ✅ / ❌ | Path: |
| Video Upload - User 2 | ✅ / ❌ | Path: |
| Slideshow Generation - User 1 | ✅ / ❌ | Path: |
| Slideshow Generation - User 2 | ✅ / ❌ | Path: |
| Montage Generation - User 1 | ✅ / ❌ | Path: |
| Montage Generation - User 2 | ✅ / ❌ | Path: |
| Access Control Test | ✅ / ❌ | |

### Issues Found:
[List any issues discovered]

### Screenshots:
[Attach relevant screenshots]

## 🚀 Quick Start Commands

### On Production VM (150.136.235.189):

```bash
# 1. SSH to VM
ssh ubuntu@150.136.235.189

# 2. Navigate to project
cd /home/ubuntu/TwelvelabsVideoAI

# 3. Pull latest changes
git pull origin main

# 4. Run automated tests
python3 scripts/test_oci_path_isolation.py

# 5. Check OCI bucket
oci os object list --bucket-name video-ai-storage --prefix users/

# 6. Monitor application logs
sudo journalctl -u dataguardian -f
```

## 🔍 Debugging Tips

### Issue: OCI Configuration Not Found

**Solution**:
```bash
# Check if config exists
ls -la ~/.oci/config

# Setup if missing
oci setup config

# Test connection
oci os ns get
```

### Issue: Users Not Found in Database

**Solution**:
```bash
# Create admin user
python scripts/create_admin_user.py

# Or manually via SQL
sqlplus TELCOVIDEOENCODE/password@ocdmrealtime_high
SELECT id, username, role FROM users;
```

### Issue: Files Not Appearing in OCI

**Check**:
```bash
# 1. Check Flask logs for upload errors
sudo journalctl -u dataguardian -n 100 | grep -i "upload\|oci"

# 2. Check if OCI_AVAILABLE is True
python -c "
import sys
sys.path.insert(0, '/home/ubuntu/TwelvelabsVideoAI/src')
from localhost_only_flask import OCI_AVAILABLE
print(f'OCI Available: {OCI_AVAILABLE}')
"

# 3. Test OCI client manually
python -c "
from twelvelabvideoai.src.oci_storage import get_oci_client
client = get_oci_client()
print('✅ OCI client works')
"
```

### Issue: Wrong Paths in OCI

**Check Code**:
```bash
# Verify path functions are being called
grep -n "get_user_upload_path\|get_user_generated_path" src/localhost_only_flask.py

# Check actual usage in upload route
grep -A 20 "@app.route('/upload_unified'" src/localhost_only_flask.py
```

## ✅ Success Criteria

All tests pass when:

1. ✅ Automated tests show: `2 passed, 0 failed`
2. ✅ User 1's files in `users/1/uploads/` and `users/1/generated/`
3. ✅ User 2's files in `users/2/uploads/` and `users/2/generated/`
4. ✅ No cross-contamination (User 1's files not in User 2's directories)
5. ✅ Access control prevents unauthorized file access
6. ✅ Application logs show no permission errors
7. ✅ OCI bucket shows proper folder structure

## 📝 Next Steps After Testing

Once all tests pass:

1. **Document Results**: Fill in test results template
2. **Update Production**: Ensure VM has latest code
3. **Monitor**: Watch logs for any isolation issues
4. **Move to Rate Limiting Tests**: Proceed to test rate limiting enforcement

## 📚 Related Documentation

- `RATE_LIMITING_OCI_STORAGE.md` - Overall multi-tenant implementation
- `OCI_INTEGRATION_SUMMARY.md` - Original OCI integration
- `MULTI_TENANT_OCI_INTEGRATION.md` - Multi-tenant OCI design
- `ADMIN_DASHBOARD_COMPLETE.md` - Admin monitoring dashboard
