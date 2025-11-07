# Multi-Tenant Security Implementation Guide

## Overview
This document outlines the comprehensive multi-tenant security architecture for Data Guardian, ensuring complete isolation between users at all tiers: application, database, and storage.

---

## 1. Role-Based Access Control (RBAC)

### Role Hierarchy

#### **VIEWER (Read-Only User)**
**Purpose:** Users who need to browse and search content without modification rights

**Permissions:**
- ✅ View own albums and media
- ✅ Search within own content (photos & videos)
- ✅ Generate AI tags for own existing media
- ✅ View and update own profile
- ✅ Change own password

**Restrictions:**
- ❌ Cannot upload new media
- ❌ Cannot create or delete albums
- ❌ Cannot edit or delete media
- ❌ Cannot access other users' content
- ❌ Cannot access admin functions

**Use Cases:**
- Reviewers who need read-only access
- Auditors examining content
- Temporary access for contractors
- Limited API access for integrations

---

#### **EDITOR (Content Creator / Regular User)**
**Purpose:** Standard users who actively create and manage content

**Permissions:**
- ✅ All VIEWER permissions
- ✅ Upload photos and videos
- ✅ Create and manage own albums
- ✅ Edit and delete own media
- ✅ Create video montages from own content
- ✅ Generate embeddings for own media
- ✅ Slice videos into segments

**Restrictions:**
- ❌ Cannot access other users' content (except shared)
- ❌ Cannot manage users
- ❌ Cannot access admin functions
- ❌ Cannot view system statistics

**Use Cases:**
- Content creators managing their media library
- Photographers organizing their portfolio
- Video editors working on projects
- Standard application users

---

#### **ADMIN (System Administrator)**
**Purpose:** System administrators with full access

**Permissions:**
- ✅ All EDITOR permissions
- ✅ Manage users (create, edit, disable, delete)
- ✅ View all content (for moderation purposes)
- ✅ Access system statistics and analytics
- ✅ Manage system settings
- ✅ View audit logs and login attempts
- ✅ Reset user passwords
- ✅ Configure API keys and integrations

**Responsibilities:**
- User account management
- System monitoring and maintenance
- Content moderation
- Security administration
- Troubleshooting user issues

**Use Cases:**
- System administrators
- IT support staff
- Security team members

---

## 2. Database Security (Multi-Tenancy)

### Schema Changes

#### USER_ID Column Addition
All content tables include `USER_ID` for ownership tracking:

```sql
-- ALBUM_MEDIA table
ALTER TABLE album_media ADD (user_id NUMBER);
ALTER TABLE album_media ADD CONSTRAINT fk_album_media_user 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_album_media_user_id ON album_media (user_id);

-- VIDEO_SEGMENTS table
ALTER TABLE video_segments ADD (user_id NUMBER);
ALTER TABLE video_segments ADD CONSTRAINT fk_video_segments_user 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_video_segments_user_id ON video_segments (user_id);

-- QUERY_EMBEDDING_CACHE table (per-user caching)
ALTER TABLE query_embedding_cache ADD (user_id NUMBER);
CREATE INDEX idx_qcache_user_text ON query_embedding_cache (user_id, query_text);
```

### Row-Level Security
All queries automatically filter by `user_id`:

```python
# Example: Get user's albums
SELECT * FROM album_media 
WHERE user_id = :current_user_id 
AND album_name = :album_name;

# Example: Search user's content
SELECT * FROM album_media 
WHERE user_id = :current_user_id 
AND VECTOR_DISTANCE(embedding_vector, :query_vector, COSINE) < :threshold;
```

### Cascade Deletion
When a user is deleted, all their content is automatically removed:
- Albums and media → CASCADE DELETE
- Video segments → CASCADE DELETE
- Cached queries → Retained or optionally cleaned

---

## 3. Storage Tier Security (OCI Object Storage)

### User Storage Structure

Each user gets isolated storage paths:

```
bucket_root/
├── users/
│   ├── 1_admin/                    # User ID 1 (admin)
│   │   ├── albums/
│   │   │   ├── vacation_2024/
│   │   │   │   ├── photo1.jpg
│   │   │   │   └── photo2.jpg
│   │   │   └── family/
│   │   ├── videos/
│   │   │   ├── original/
│   │   │   │   └── video1.mp4
│   │   │   └── segments/
│   │   │       ├── video1_segment_0.mp4
│   │   │       └── video1_segment_1.mp4
│   │   └── temp/                   # Temporary uploads
│   │
│   ├── 2_john_doe/                 # User ID 2 (editor)
│   │   ├── albums/
│   │   ├── videos/
│   │   └── temp/
│   │
│   └── 3_jane_smith/               # User ID 3 (viewer)
│       ├── albums/
│       └── videos/
│
└── shared/                         # Optional: Shared resources
    └── public_assets/
```

### Path Generation Functions

```python
def get_user_storage_path(user_id: int, username: str) -> str:
    """Base path: users/{user_id}_{username}/"""
    return f"users/{user_id}_{username}"

def get_user_album_path(user_id: int, username: str, album_name: str) -> str:
    """Album path: users/{user_id}_{username}/albums/{album_name}/"""
    return f"{get_user_storage_path(user_id, username)}/albums/{album_name}"

def get_user_video_path(user_id: int, username: str) -> str:
    """Video path: users/{user_id}_{username}/videos/"""
    return f"{get_user_storage_path(user_id, username)}/videos"
```

### Storage Benefits
1. **Complete Isolation:** Users cannot accidentally access others' files
2. **Easy Backup:** Backup user data by path pattern
3. **Quota Management:** Track storage per user
4. **Audit Trail:** File paths clearly identify ownership
5. **Cleanup:** Delete user folder on account deletion
6. **Scalability:** No file naming conflicts between users

---

## 4. Application Layer Security

### Route Protection Decorators

```python
from auth_rbac import (
    viewer_required,    # Any authenticated user
    editor_required,    # Editor or Admin
    admin_required,     # Admin only
    permission_required # Specific permission
)

# Viewer-only routes (search, view)
@app.route('/search')
@viewer_required
def search():
    # Automatically filtered by current_user.id
    results = search_user_content(current_user.id, query)
    return render_template('results.html', results=results)

# Editor routes (upload, create)
@app.route('/upload', methods=['POST'])
@editor_required
def upload():
    # Store in user's path
    storage_path = get_user_storage_path(current_user.id, current_user.username)
    # ... upload logic

# Admin routes (user management)
@app.route('/admin/users')
@admin_required
def admin_users():
    # Only admins can see this
    users = get_all_users()
    return render_template('admin_users.html', users=users)
```

### Resource Ownership Validation

```python
def can_access_resource(user, resource_user_id: int) -> bool:
    """Check if user can access a resource"""
    # Admin can access everything
    if user.role == 'admin':
        return True
    
    # User can only access their own resources
    return user.id == resource_user_id

# Example usage
@app.route('/media/<int:media_id>/delete', methods=['POST'])
@login_required
def delete_media(media_id):
    media = get_media_by_id(media_id)
    
    if not can_access_resource(current_user, media.user_id):
        abort(403, "Access denied")
    
    delete_media_from_storage(media)
    delete_media_from_db(media_id)
    flash('Media deleted successfully', 'success')
    return redirect(url_for('index'))
```

---

## 5. Cache Isolation

### Per-User Query Caching

Cache entries include `user_id` to prevent cache poisoning:

```python
def get_cached_embedding(query_text: str, user_id: int) -> Optional[str]:
    """Get cached embedding for specific user's query"""
    cursor.execute("""
        SELECT embedding_vector 
        FROM query_embedding_cache 
        WHERE query_text = :query 
        AND (user_id = :user_id OR user_id IS NULL)
        ORDER BY user_id DESC NULLS LAST
    """, {"query": query_text, "user_id": user_id})
    # Prioritize user-specific cache, fallback to global
```

**Benefits:**
- Users don't see each other's search patterns
- Per-user cache statistics
- Optional global cache for common queries

---

## 6. Migration Path

### Step 1: Add USER_ID Columns
```bash
python scripts/add_user_ownership.py
```

### Step 2: Assign Ownership to Existing Data
```sql
-- Assign all existing content to admin user (ID = 1)
UPDATE album_media SET user_id = 1 WHERE user_id IS NULL;
UPDATE video_segments SET user_id = 1 WHERE user_id IS NULL;

-- Or: Prompt for assignment during migration
```

### Step 3: Make USER_ID Required
```sql
ALTER TABLE album_media MODIFY user_id NUMBER NOT NULL;
ALTER TABLE video_segments MODIFY user_id NUMBER NOT NULL;
```

### Step 4: Update Application Code
- Add `user_id` to all INSERT statements
- Add `WHERE user_id = :current_user_id` to all SELECT statements
- Update upload handlers to use user-specific paths
- Apply route decorators based on required permissions

### Step 5: Test Multi-Tenancy
```python
# Test script to verify isolation
def test_user_isolation():
    # Create test users
    user1 = create_user('test_user1', 'password', role='editor')
    user2 = create_user('test_user2', 'password', role='editor')
    
    # Upload content as user1
    login_as(user1)
    upload_photo('test1.jpg', 'album1')
    
    # Try to access as user2
    login_as(user2)
    albums = get_user_albums()  # Should be empty
    assert len(albums) == 0, "User2 should not see User1's albums"
    
    # Verify admin can see both
    login_as(admin)
    all_albums = get_all_albums_as_admin()
    assert len(all_albums) >= 2, "Admin should see all albums"
```

---

## 7. Security Best Practices

### API Rate Limiting (Per User)
```python
# Track API usage per user
@app.before_request
def check_user_rate_limit():
    if current_user.is_authenticated:
        remaining = get_user_rate_limit_remaining(current_user.id)
        if remaining <= 0:
            abort(429, "Rate limit exceeded. Please try again later.")
```

### Audit Logging
```python
def log_user_action(user_id: int, action: str, resource: str, details: dict):
    """Log all user actions for audit trail"""
    cursor.execute("""
        INSERT INTO audit_log (user_id, action, resource, details, timestamp)
        VALUES (:user_id, :action, :resource, :details, CURRENT_TIMESTAMP)
    """, {
        "user_id": user_id,
        "action": action,  # 'CREATE', 'READ', 'UPDATE', 'DELETE'
        "resource": resource,  # 'album', 'media', 'user'
        "details": json.dumps(details)
    })

# Example usage
@app.route('/album/create', methods=['POST'])
@editor_required
def create_album():
    album_name = request.form['album_name']
    create_album_for_user(current_user.id, album_name)
    
    log_user_action(
        user_id=current_user.id,
        action='CREATE',
        resource='album',
        details={'album_name': album_name}
    )
```

### Content Validation
```python
def validate_file_ownership(file_path: str, user_id: int) -> bool:
    """Verify file path belongs to user"""
    expected_prefix = get_user_storage_path(user_id, get_username(user_id))
    return file_path.startswith(expected_prefix)
```

---

## 8. UI/UX Updates

### Role-Based UI Elements

```html
<!-- Show upload button only for editors and admins -->
{% if current_user.role in ['editor', 'admin'] %}
<button class="btn btn-primary" onclick="showUploadModal()">
    <i class="bi bi-cloud-upload"></i> Upload Media
</button>
{% endif %}

<!-- Show admin panel only for admins -->
{% if current_user.role == 'admin' %}
<li><a class="dropdown-item" href="/admin/users">
    <i class="bi bi-people"></i> User Management
</a></li>
{% endif %}

<!-- Show user quota/usage -->
<div class="user-stats">
    <p>Storage Used: {{ user_storage_usage }} / {{ user_storage_quota }}</p>
    <p>API Calls Today: {{ user_api_calls }} / {{ user_api_limit }}</p>
</div>
```

---

## 9. Benefits Summary

### For Users
✅ **Privacy:** Content is completely isolated from other users
✅ **Security:** Cannot accidentally delete others' data
✅ **Performance:** Searches only scan user's own content
✅ **Clarity:** Clear ownership of all content

### For Administrators
✅ **Control:** Fine-grained permission management
✅ **Compliance:** Easy to demonstrate data isolation
✅ **Monitoring:** Track usage per user
✅ **Cleanup:** Simple user account deletion with cascade

### For System
✅ **Scalability:** Linear scaling with users
✅ **Backup:** Per-user backup and restore
✅ **Quota:** Easy storage and API quota enforcement
✅ **Audit:** Complete trail of all actions

---

## 10. Implementation Checklist

- [ ] Run database migration (`add_user_ownership.py`)
- [ ] Assign existing content to users
- [ ] Import `auth_rbac` module in Flask app
- [ ] Update all routes with appropriate decorators
- [ ] Update all queries to filter by `user_id`
- [ ] Update upload handlers for user-specific paths
- [ ] Update UI to show/hide based on permissions
- [ ] Create audit logging table
- [ ] Implement rate limiting per user
- [ ] Test isolation between users
- [ ] Document role permissions for users
- [ ] Train admins on user management

---

## Contact & Support

For questions about this implementation:
- Review code in `auth_rbac.py`
- Check migration script `add_user_ownership.py`
- Test with different user roles
- Consult Oracle documentation for RLS (Row-Level Security) advanced features
