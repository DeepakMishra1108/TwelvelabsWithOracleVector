# Face Tagging Feature - Implementation Summary

## Overview
Comprehensive face detection and tagging system for the TwelveLabs Video AI platform. This feature enables manual face tagging, automatic face recognition, and face-based search filtering.

**Status**: Core backend implementation completed (4/8 tasks done)  
**Date**: December 19, 2024

---

## ✅ Completed Tasks

### 1. Database Schema (✅ Completed)
**File**: `scripts/create_face_recognition_schema.py`

Created 3 tables on production Oracle 23ai database:

#### `face_tags` Table
Stores manual and auto-detected face tags with embeddings.

```sql
CREATE TABLE face_tags (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    media_id NUMBER NOT NULL,
    face_name VARCHAR2(100) NOT NULL,
    face_embedding VECTOR(512, FLOAT32),  -- 512-dim face embedding
    bounding_box VARCHAR2(200),           -- JSON: {x, y, w, h}
    confidence NUMBER(5,2),               -- 0.00-1.00
    created_by NUMBER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_face_tags_media FOREIGN KEY (media_id) REFERENCES album_media(id) ON DELETE CASCADE,
    CONSTRAINT fk_face_tags_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `user_face_profiles` Table
Stores user's face for login-based recognition.

```sql
CREATE TABLE user_face_profiles (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id NUMBER NOT NULL UNIQUE,
    face_embedding VECTOR(512, FLOAT32) NOT NULL,
    face_image_path VARCHAR2(500),
    is_active NUMBER(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_face_profile FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `face_recognition_cache` Table
Caches face detection results for performance.

```sql
CREATE TABLE face_recognition_cache (
    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    media_id NUMBER NOT NULL,
    detected_faces CLOB,                   -- JSON array of detected faces
    processing_status VARCHAR2(20) DEFAULT 'pending',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_face_cache_media FOREIGN KEY (media_id) REFERENCES album_media(id) ON DELETE CASCADE
);
```

#### Indexes
- `idx_face_tags_media` - Fast lookup by media ID
- `idx_face_tags_name` - Search by person name
- `idx_user_face_user` - User face profile lookup
- `idx_face_cache_media` - Cache lookup by media

#### Additional Column
- `album_media.face_recognition_status` - Track processing status

**Deployment**: ✅ Successfully deployed to production VM

---

### 2. Face Detection Module (✅ Completed)
**File**: `src/utils/face_detection_helper.py`

OpenCV-based face detection and embedding utilities.

#### Key Functions

```python
detect_faces_opencv(image_path: str) -> List[Dict]
```
- Detects all faces in an image using Haar Cascade classifier
- Returns list of bounding boxes with confidence scores
- Format: `{'facial_area': {'x': int, 'y': int, 'w': int, 'h': int}, 'confidence': float}`

```python
crop_face_region(image_path: str, face_bbox: Dict) -> Optional[np.ndarray]
```
- Extracts face region from image
- Adds padding around face for better recognition
- Returns cropped face as numpy array

```python
generate_placeholder_embedding(face_bbox: Dict) -> np.ndarray
```
- Generates 512-dimensional face embedding
- Current: Placeholder implementation (deterministic based on bbox)
- Future: Will integrate TwelveLabs Marengo for actual face embeddings

```python
compare_embeddings(embedding1, embedding2) -> Tuple[float, bool]
```
- Compares two face embeddings using cosine similarity
- Returns (distance, is_match) tuple
- Threshold: 0.6 (configurable)

```python
find_matching_faces(query_embedding, face_embeddings, threshold=0.6, top_k=5)
```
- Finds matching faces from known embeddings
- Returns top K matches sorted by similarity
- Used for auto-recognition

```python
embedding_to_oracle_vector(embedding: np.ndarray) -> bytes
oracle_vector_to_embedding(vector_bytes: bytes) -> np.ndarray
```
- Converts between numpy arrays and Oracle VECTOR format
- Little-endian FLOAT32 packing/unpacking
- Compatible with Oracle 23ai VECTOR(512, FLOAT32)

#### Dependencies
- OpenCV 4.9.0+ (`opencv-python`)
- NumPy for array operations
- Haar Cascade: `haarcascade_frontalface_default.xml`

**Testing**: ✅ Module loads successfully, face detection functional

---

### 3. Manual Face Tagging API (✅ Completed)
**File**: `src/localhost_only_flask.py` (lines 3650-4010)

Four REST endpoints for face tagging operations.

#### POST `/media/<int:media_id>/detect_faces`
**Purpose**: Detect all faces in a photo  
**Auth**: Login required (Editor/Admin only)  
**Permissions**: Can only detect faces in own photos (unless admin)

**Request**: Empty POST  
**Response**:
```json
{
    "success": true,
    "media_id": 123,
    "faces_detected": 3,
    "faces": [
        {
            "facial_area": {"x": 100, "y": 150, "w": 80, "h": 80},
            "confidence": 1.0
        },
        ...
    ]
}
```

**Process**:
1. Validates permissions (user owns photo or is admin)
2. Downloads photo from OCI if needed
3. Runs OpenCV face detection
4. Returns bounding boxes for all detected faces
5. Cleans up temp files

#### POST `/media/<int:media_id>/tag_face`
**Purpose**: Manually tag a detected face with a person's name  
**Auth**: Login required (Editor/Admin only)  
**Permissions**: Can only tag faces in own photos (unless admin)

**Request**:
```json
{
    "face_name": "John Doe",
    "face_bbox": {"x": 100, "y": 150, "w": 80, "h": 80}
}
```

**Response**:
```json
{
    "success": true,
    "media_id": 123,
    "face_tag_id": 456,
    "face_name": "John Doe",
    "message": "Successfully tagged face as 'John Doe'"
}
```

**Process**:
1. Validates input (face_name and face_bbox required)
2. Checks permissions
3. Downloads photo from OCI
4. Crops face region from image
5. Generates face embedding (512-dim vector)
6. Stores in `face_tags` table with:
   - Face embedding as VECTOR(512, FLOAT32)
   - Bounding box as JSON
   - Confidence = 1.0 (manual tag)
   - Created by current user

#### GET `/media/<int:media_id>/faces`
**Purpose**: Get all face tags for a media item  
**Auth**: Login required  
**Permissions**: Can only view tags on own photos (unless admin)

**Response**:
```json
{
    "success": true,
    "media_id": 123,
    "total": 2,
    "face_tags": [
        {
            "id": 456,
            "face_name": "John Doe",
            "bounding_box": "{\"x\": 100, \"y\": 150, \"w\": 80, \"h\": 80}",
            "confidence": 1.0,
            "created_at": "2024-12-19T09:30:00",
            "tagged_by": "alice"
        },
        ...
    ]
}
```

#### DELETE `/face_tags/<int:tag_id>`
**Purpose**: Delete a face tag  
**Auth**: Login required  
**Permissions**: Can delete own tags or admin can delete any

**Response**:
```json
{
    "success": true,
    "message": "Face tag deleted successfully"
}
```

---

### 4. Auto Face Recognition (✅ Completed)
**Files**: 
- `src/utils/auto_face_recognition.py` - Auto-recognition module
- `src/localhost_only_flask.py` (lines 1973-2015) - Upload integration

#### Auto-Recognition Module
**Function**: `auto_recognize_faces(media_id, image_path, user_id, connection)`

**Process**:
1. **Detect Faces**: Run OpenCV face detection on uploaded photo
2. **Load Known Faces**: Query all existing face_tags from database
3. **Generate Embeddings**: Create embedding for each detected face
4. **Match Faces**: Compare against known faces using cosine similarity
5. **Auto-Tag**: If match found (distance < 0.6), create face_tag automatically
6. **Return Results**: Summary of detected, recognized, and tagged faces

**Returns**:
```python
{
    "faces_detected": 3,
    "faces_recognized": 2,
    "faces_tagged": 2,
    "recognition_results": [
        {
            "face_index": 1,
            "bbox": {"x": 100, "y": 150, "w": 80, "h": 80},
            "recognized_as": "John Doe",
            "confidence": 0.85,
            "auto_tagged": True
        },
        ...
    ]
}
```

#### Upload Integration
Auto face recognition runs automatically during photo upload:

1. Photo uploaded to OCI
2. Metadata stored in database (media_id created)
3. **Face recognition triggered** (lines 1973-2015)
4. Photo downloaded to temp file
5. `auto_recognize_faces()` called with connection
6. Progress updates sent to client
7. Temp file cleaned up
8. Upload continues with embedding generation

**Progress Events**:
- `faces:52` - "Detecting faces..."
- `faces:54` - "Recognized X face(s)" or "Detected X unknown face(s)"

**Error Handling**: Non-blocking - if face recognition fails, upload continues

---

## 🔄 Pending Tasks

### 5. Face Capture at Login (Not Started)
**Requirement**: Non-admin users capture their face at first login for photo filtering

**Implementation Plan**:
1. Check if `user_face_profiles.user_id` exists for current user
2. If not, show camera capture modal after login
3. Use HTML5 `getUserMedia()` to access webcam
4. Capture photo when user clicks "Take Photo"
5. Send to `/capture_user_face` endpoint
6. Detect face, generate embedding
7. Store in `user_face_profiles` table
8. Set `is_active = 1`

**UI Flow**:
```
Login → Check face profile → If missing → Show camera modal
                                           ↓
                                   Capture face photo
                                           ↓
                                   Upload to backend
                                           ↓
                                   Store in DB → Continue to dashboard
```

**Security**: 
- Only capture for non-admin users
- Skip if user already has profile
- Allow re-capture via settings page

---

### 6. Face-Based Photo Filtering (Not Started)
**Requirement**: Non-admin users only see photos containing their face

**Implementation Plan**:

#### Modify Search Endpoints
**Files**: `src/search_unified_flask_safe.py`, `src/localhost_only_flask.py`

**Logic**:
```python
if current_user.role != 'admin':
    # Load user's face embedding from user_face_profiles
    user_face_embedding = get_user_face_profile(current_user.id)
    
    if user_face_embedding:
        # Join with face_tags
        # Filter photos where face_tags.face_embedding matches user's face
        # Using VECTOR_DISTANCE(face_embedding, user_face) < threshold
        
        query += """
        JOIN face_tags ft ON am.id = ft.media_id
        WHERE VECTOR_DISTANCE(ft.face_embedding, :user_face_vector, COSINE) < 0.6
        """
```

#### Modified Queries
1. **Photo Gallery** (`/photos`): Filter by user face
2. **Search** (`/search_unified`): Filter results by user face
3. **Album View** (`/album/<name>`): Filter album photos by user face

#### Admin Override
- Admins see all photos (no face filtering)
- Editors see only their uploaded photos
- Viewers see only photos with their face

**Performance**: 
- Add index on `face_tags.face_embedding` for fast vector search
- Cache user face embedding in session
- Consider materialized view for frequent queries

---

### 7. Face Tagging UI Components (Not Started)
**Requirement**: Frontend UI for face tagging workflow

**Components to Build**:

#### A. Face Detection Overlay
**Location**: Photo detail page

```html
<div class="face-detection-panel">
    <button onclick="detectFaces()">🔍 Detect Faces</button>
    <div id="face-boxes-container">
        <!-- Overlay bounding boxes on photo -->
        <div class="face-box" style="left: 100px; top: 150px; width: 80px; height: 80px">
            <input type="text" placeholder="Name this person" />
            <button onclick="tagFace(...)">Tag</button>
        </div>
    </div>
</div>
```

#### B. Tagged Faces List
```html
<div class="tagged-faces-list">
    <h3>Tagged Faces (3)</h3>
    <ul>
        <li>
            <span class="face-name">John Doe</span>
            <span class="confidence">100%</span>
            <button onclick="deleteFaceTag(456)">🗑️</button>
        </li>
        ...
    </ul>
</div>
```

#### C. Camera Capture Modal
**For login face capture**

```html
<div id="face-capture-modal" class="modal">
    <h2>Capture Your Face</h2>
    <p>We'll use this to show you photos you're in.</p>
    
    <video id="camera-preview" autoplay></video>
    <canvas id="capture-canvas" style="display:none"></canvas>
    
    <button onclick="capturePhoto()">📸 Take Photo</button>
    <button onclick="skipCapture()">Skip for Now</button>
</div>
```

#### D. Face Search Filter
**In search interface**

```html
<div class="search-options">
    <label>
        <input type="checkbox" id="filter-my-face" checked />
        Only show photos I'm in
    </label>
</div>
```

**JavaScript Functions**:
- `detectFaces(mediaId)` - Call `/media/<id>/detect_faces`
- `tagFace(mediaId, faceName, bbox)` - Call `/media/<id>/tag_face`
- `getFaceTags(mediaId)` - Call `/media/<id>/faces`
- `deleteFaceTag(tagId)` - Call `/face_tags/<id>` DELETE
- `capturePhoto()` - Capture from webcam, upload to `/capture_user_face`

---

### 8. End-to-End Testing (Not Started)
**Requirement**: Test complete face tagging workflow

**Test Scenarios**:

#### Test 1: Manual Face Tagging
1. Upload photo with 2 people
2. Click "Detect Faces" - verify 2 faces detected
3. Tag first face as "Alice" - verify success
4. Tag second face as "Bob" - verify success
5. View photo - verify both tags shown
6. Delete one tag - verify deletion

#### Test 2: Auto Face Recognition
1. Upload photo with Alice (already tagged in another photo)
2. Wait for upload to complete
3. Check photo - verify Alice auto-tagged
4. Check confidence score < 1.0 (auto vs manual)

#### Test 3: Face Capture at Login
1. Create new non-admin user
2. Login - verify camera modal shown
3. Capture face - verify stored in `user_face_profiles`
4. Logout and login again - verify modal not shown

#### Test 4: Face-Based Filtering
1. Login as Alice (non-admin)
2. View photo gallery - verify only photos with Alice shown
3. Search for "beach" - verify results filtered by Alice's face
4. Login as admin - verify all photos shown

#### Test 5: Cross-User Recognition
1. Alice uploads photo with Bob and Charlie
2. Alice tags Bob in photo A
3. Charlie uploads photo with Bob
4. Verify Bob auto-recognized in Charlie's photo
5. Verify both Alice and Charlie can see their own photos

#### Test 6: Performance
1. Upload 100 photos with faces
2. Measure face detection time per photo
3. Measure auto-recognition time with 1000+ known faces
4. Test search query performance with face filtering
5. Verify vector index usage in query plan

**Expected Results**:
- Face detection: < 2s per photo
- Auto-recognition: < 3s per photo (with 1000 known faces)
- Search with face filter: < 500ms
- Vector index hit rate: > 95%

---

## 📋 Technical Details

### Face Embedding Strategy
**Current**: Placeholder embeddings (deterministic based on bounding box)  
**Future**: TwelveLabs Marengo image embeddings

**Why Placeholder?**:
- Rapid prototyping without model dependencies
- Establishes database schema and API contracts
- Enables testing of search/match logic
- Easy to swap with production embeddings

**Upgrade Path**:
1. Replace `generate_placeholder_embedding()` with TwelveLabs API call
2. Send face crop to TwelveLabs Marengo
3. Receive 512-dim embedding
4. Store in same VECTOR column (no schema change)
5. No changes needed to search/match logic

### Oracle VECTOR Integration
**Format**: VECTOR(512, FLOAT32)  
**Storage**: Binary BLOB, little-endian packed floats  
**Indexing**: Oracle's native vector index for fast similarity search

**Distance Function**:
```sql
SELECT media_id, face_name,
       VECTOR_DISTANCE(face_embedding, :query_vector, COSINE) as distance
FROM face_tags
WHERE VECTOR_DISTANCE(face_embedding, :query_vector, COSINE) < 0.6
ORDER BY distance
```

**Index Creation** (for production):
```sql
CREATE VECTOR INDEX idx_face_embedding_vector 
ON face_tags(face_embedding)
ORGANIZATION INMEMORY NEIGHBOR GRAPH
DISTANCE COSINE
WITH TARGET ACCURACY 95;
```

### Security & Privacy
**RBAC Integration**:
- Viewers: Can view face tags on accessible photos
- Editors: Can tag faces in own photos, view own tags
- Admins: Full access to all face tags, can manage any user's tags

**Data Ownership**:
- Each face tag has `created_by` user ID
- Users can only delete their own tags (unless admin)
- Face embeddings stored per-user in `user_face_profiles`

**Privacy Controls** (future):
- Opt-out of face recognition
- Delete all face tags for a user
- Disable cross-user face matching
- Face data retention policies

---

## 🚀 Deployment Instructions

### Prerequisites
- Oracle Autonomous Database 23ai (already deployed)
- Python 3.11+ with OpenCV
- OCI SDK configured
- Production VM: ubuntu@150.136.235.189

### Step 1: Database Schema
✅ Already deployed to production

```bash
# Verify tables exist
ssh ubuntu@150.136.235.189
cd /home/dataguardian/TwelvelabsWithOracleVector
python scripts/create_face_recognition_schema.py
```

### Step 2: Install Dependencies
```bash
# On production VM
pip install opencv-python

# Verify
python -c "import cv2; print('OpenCV:', cv2.__version__)"
```

### Step 3: Deploy Code
```bash
# From local machine
scp src/utils/face_detection_helper.py \
    src/utils/auto_face_recognition.py \
    ubuntu@150.136.235.189:/home/dataguardian/TwelvelabsWithOracleVector/src/utils/

scp src/localhost_only_flask.py \
    ubuntu@150.136.235.189:/home/dataguardian/TwelvelabsWithOracleVector/src/
```

### Step 4: Restart Application
```bash
ssh ubuntu@150.136.235.189
sudo systemctl restart dataguardian
sudo systemctl status dataguardian
```

### Step 5: Test Endpoints
```bash
# Test face detection
curl -X POST https://localhost:8443/media/123/detect_faces \
  -H "Authorization: Bearer $TOKEN"

# Test manual tagging
curl -X POST https://localhost:8443/media/123/tag_face \
  -H "Content-Type: application/json" \
  -d '{"face_name": "Test User", "face_bbox": {"x": 100, "y": 100, "w": 50, "h": 50}}'

# Test get tags
curl https://localhost:8443/media/123/faces
```

---

## 📊 Database Stats

**Tables Created**: 3  
**Indexes Created**: 4  
**Columns Added**: 1 (album_media.face_recognition_status)

**Storage Estimates**:
- Face embedding (VECTOR 512 FLOAT32): ~2KB per face
- 1000 photos with avg 2 faces: ~4MB embeddings
- Metadata + indexes: ~1MB
- **Total**: ~5MB for 2000 face tags

**Query Performance** (estimated):
- Face detection: O(n) on image pixels
- Embedding match: O(1) with vector index
- Cross-user recognition: O(log n) on known faces
- Search with face filter: O(log n) on indexed vectors

---

## 🔧 Configuration

### Environment Variables
No new variables needed - uses existing:
- `ORACLE_DB_*` - Database connection
- `OCI_*` - Object storage access
- `TWELVELABS_API_KEY` - For future embedding upgrades

### Feature Flags (future)
```python
ENABLE_AUTO_FACE_RECOGNITION = True
ENABLE_FACE_CAPTURE_AT_LOGIN = True  
ENABLE_FACE_BASED_FILTERING = True
FACE_RECOGNITION_THRESHOLD = 0.6
```

---

## 📝 Next Steps

### Immediate (Required for MVP)
1. **Face Capture UI** - Camera modal for login face capture
2. **Face-Based Filtering** - Modify search queries to filter by user face
3. **Face Tagging UI** - Overlay and tag interface on photo detail page

### Short-term (Production Ready)
4. **TwelveLabs Integration** - Replace placeholder embeddings with Marengo
5. **End-to-End Testing** - All test scenarios above
6. **Performance Optimization** - Vector indexes, query tuning
7. **Documentation** - User guide, API docs

### Long-term (Enhancements)
8. **Face Clustering** - Group similar unknown faces together
9. **Batch Tagging** - Tag person across multiple photos at once
10. **Face Recognition Analytics** - Track recognition accuracy, popular faces
11. **Privacy Controls** - User opt-out, data deletion, retention policies
12. **Mobile App** - Face capture and tagging on mobile devices

---

## 🐛 Known Issues & Limitations

### Current Limitations
1. **Placeholder Embeddings**: Not production-ready for actual face matching
2. **OpenCV Haar Cascade**: Less accurate than deep learning models (70-80% vs 95%+)
3. **No UI Yet**: Backend-only implementation, needs frontend
4. **No Face Filtering**: Search doesn't filter by user face yet
5. **No Face Capture**: Login face capture not implemented

### Future Improvements
1. **Switch to DeepFace or FaceNet**: Better detection accuracy
2. **TwelveLabs Embeddings**: Production-grade face embeddings
3. **Face Quality Scoring**: Reject blurry or low-quality faces
4. **Multi-face per User**: Handle users with different hairstyles, ages
5. **Face Aging**: Update embeddings as users age

---

## 📚 References

### Documentation
- [Oracle VECTOR Data Type](https://docs.oracle.com/en/database/oracle/oracle-database/23/vecse/overview-ai-vector-search.html)
- [OpenCV Face Detection](https://docs.opencv.org/4.x/db/d28/tutorial_cascade_classifier.html)
- [TwelveLabs Marengo API](https://docs.twelvelabs.io/)

### Code Files
- `/scripts/create_face_recognition_schema.py` - Database setup
- `/src/utils/face_detection_helper.py` - Detection module
- `/src/utils/auto_face_recognition.py` - Auto-recognition
- `/src/localhost_only_flask.py` - API endpoints (lines 3650-4215)

### Related Features
- Multi-tenant RBAC (`twelvelabvideoai/src/auth_rbac.py`)
- Vector Search (`src/search_unified_flask_safe.py`)
- Upload Handler (`src/localhost_only_flask.py:upload_unified`)

---

## ✅ Deployment Checklist

- [x] Database schema created on production
- [x] Face detection module implemented
- [x] Face tagging API endpoints created
- [x] Auto-recognition on upload integrated
- [x] Code reviewed and tested locally
- [ ] Dependencies installed on production VM
- [ ] Code deployed to production VM
- [ ] Service restarted
- [ ] Endpoints tested on production
- [ ] UI components built
- [ ] Face capture at login implemented
- [ ] Face-based filtering implemented
- [ ] End-to-end testing completed
- [ ] User documentation written
- [ ] Production monitoring setup

---

**Last Updated**: December 19, 2024  
**Author**: GitHub Copilot + Development Team  
**Version**: 1.0 (Backend Core Complete)
