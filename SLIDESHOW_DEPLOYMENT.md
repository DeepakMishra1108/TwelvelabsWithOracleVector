# Photo Slideshow Enhancement - Deployment Instructions

## Changes Made

### 1. Modified Files
- `twelvelabvideoai/src/templates/index.html`

### 2. Features Added
- **Photo Selection**: Checkboxes on photo search results for selection
- **Dynamic Button**: "Create Slideshow from Selected" button that shows only when photos are selected
- **Selection Counter**: Shows count of selected photos
- **Selection-Based Slideshow**: Creates slideshow from selected photos instead of requiring album navigation

### 3. Implementation Details

**Added Global Variable:**
```javascript
let selectedPhotos = new Set(); // Track selected photo media IDs
```

**Added Checkboxes to Photo Results:**
- Only appears on photos (not videos)
- Positioned at top-left with 20x20px size
- Uses `data-media-id` attribute for tracking

**Added Functions:**
- `updatePhotoSelection()`: Tracks checkbox state, updates button visibility and counter
- `createSlideshowFromSelected()`: Shows modal with slideshow options for selected photos
- `submitSlideshowCreation()`: Submits to `/create_slideshow` endpoint with selected photo IDs

### 4. User Workflow
1. User searches for photos (e.g., "sunset", "portraits")
2. Results display with checkboxes on photos
3. User selects desired photos by clicking checkboxes
4. "Create Slideshow from Selected (N)" button appears
5. User clicks button to configure slideshow (transition, duration, resolution)
6. Slideshow is created with selected photos

## Deployment Steps

### Option 1: Manual Upload (Requires SSH Key)
```bash
scp /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI/twelvelabvideoai/src/templates/index.html \
    dataguardian@150.136.235.189:/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src/templates/index.html
```

### Option 2: Remote Deployment via Ubuntu User
```bash
# 1. SSH to VM as ubuntu user
ssh ubuntu@150.136.235.189

# 2. Become dataguardian user
sudo su - dataguardian

# 3. Navigate to project
cd /home/dataguardian/TwelvelabsWithOracleVector

# 4. Backup current index.html
cp twelvelabvideoai/src/templates/index.html twelvelabvideoai/src/templates/index.html.backup

# 5. Download updated file from GitHub (after pushing changes)
# OR manually edit the file with the changes

# 6. Restart service
sudo systemctl restart dataguardian

# 7. Verify service
sudo systemctl status dataguardian

# 8. Check logs
sudo journalctl -u dataguardian -n 50
```

### Option 3: Git Push and Pull
```bash
# 1. On local machine
cd /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI
git add twelvelabvideoai/src/templates/index.html
git commit -m "feat: Enable photo slideshow creation from search results with selection"
git push origin main

# 2. On server
ssh ubuntu@150.136.235.189
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector
git pull origin main
sudo systemctl restart dataguardian
sudo systemctl status dataguardian
```

## Testing

### Test Checklist
1. ✅ Login to application (admin / 1tMslvkY9TrCSeQH)
2. ✅ Search for photos (e.g., "Isha", "Taylor Swift")
3. ✅ Verify checkboxes appear on photo results (not videos)
4. ✅ Select multiple photos
5. ✅ Verify "Create Slideshow from Selected" button appears with count
6. ✅ Click button and configure slideshow options
7. ✅ Submit and verify slideshow creation success
8. ✅ Check that selections clear after creation

### Expected Behavior
- Checkboxes only on photos
- Button hidden when no selections
- Button shows with count when selections exist
- Modal displays with transition, duration, resolution, filename options
- Backend receives array of photo IDs
- Success message with estimated duration
- Selections auto-clear after creation

## Backend Endpoint

**Endpoint:** `POST /create_slideshow`

**Request Body:**
```json
{
  "photo_ids": [1, 2, 3, 4, 5],
  "duration_per_photo": 3.0,
  "transition": "fade",
  "resolution": "1920x1080",
  "output_filename": "slideshow.mp4"
}
```

**Response:**
```json
{
  "message": "Slideshow creation started successfully",
  "estimated_duration": 120,
  "photo_count": 5,
  "output_file": "slideshow.mp4"
}
```

## Rollback Instructions

If issues occur:
```bash
# On server
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector
cp twelvelabvideoai/src/templates/index.html.backup twelvelabvideoai/src/templates/index.html
sudo systemctl restart dataguardian
```

## Server Details
- **IP**: 150.136.235.189
- **Service**: dataguardian.service
- **Process**: Gunicorn (5 workers)
- **Current PID**: 36396
- **Admin**: admin / 1tMslvkY9TrCSeQH
- **Database**: Oracle Autonomous (48 media items across 2 albums)
