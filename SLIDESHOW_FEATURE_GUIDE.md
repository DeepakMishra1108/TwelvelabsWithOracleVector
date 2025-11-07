# Photo Slideshow Feature - Complete Guide

## Overview

The Photo Slideshow feature allows you to create professional video slideshows from your photo collection using natural language search and selection. Slideshows are created using FFmpeg with customizable transitions, durations, and resolutions.

## How It Works

### Architecture

```
Search Photos → Select with Checkboxes → Configure Options → FFmpeg Creates Video → Download/Manage
```

**Backend Flow:**
1. User selects photos from search results
2. Frontend sends photo IDs to `/create_slideshow` endpoint
3. Backend retrieves photo file paths from `ALBUM_MEDIA` table
4. Downloads photos from OCI Object Storage to temp directory
5. Creates FFmpeg input file with durations
6. Runs FFmpeg to generate slideshow video
7. Saves video to `static/slideshows/` directory
8. Returns download URL and metadata

**Storage Location:**
- **Server Path:** `/home/dataguardian/TwelvelabsWithOracleVector/static/slideshows/`
- **URL Access:** `http://150.136.235.189/download_slideshow/<filename>`

## User Guide

### Creating a Slideshow

1. **Search for Photos**
   - Navigate to the main search page
   - Enter search query (e.g., "sunset", "family photos", "Isha")
   - Results display with thumbnails

2. **Select Photos**
   - Check the checkboxes on desired photos
   - Only photos have checkboxes (videos are excluded)
   - Counter shows number of selected photos

3. **Create Slideshow**
   - Click "Create Slideshow from Selected (N)" button
   - Configure options in modal:
     - **Transition Effect:** Fade, Dissolve, or Slide
     - **Duration per Photo:** 1-10 seconds (default: 3s)
     - **Resolution:** 
       - 1280x720 (HD)
       - 1920x1080 (Full HD) - Default
       - 3840x2160 (4K)
     - **Filename:** Custom name (default: `slideshow_YYYYMMDD_HHMMSS.mp4`)

4. **Download**
   - Success message shows download link
   - File size displayed (e.g., "5.23 MB")
   - Click download button to save video

### Viewing Created Slideshows

1. **Navigate to Slideshows Tab**
   - Click "Created Slideshows" tab in navigation
   - Lists all previously created slideshows

2. **Slideshow Information**
   - **Filename:** Generated name or custom name
   - **Created Date:** When slideshow was created
   - **File Size:** Size in MB
   - **Actions:**
     - Download button (green)
     - Delete button (red)

3. **Download Slideshow**
   - Click "Download" button
   - Browser downloads the MP4 file
   - File can be played in any video player

4. **Delete Slideshow**
   - Click trash icon
   - Confirm deletion
   - Permanently removes file from server

## Technical Specifications

### Slideshow Creation

**FFmpeg Command Structure:**
```bash
ffmpeg -f concat -safe 0 -i input.txt \
  -vf scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p \
  -c:v libx264 -preset medium -crf 23 -y output.mp4
```

**Input File Format (input.txt):**
```
file '/tmp/photo_0001.jpg'
duration 3.0
file '/tmp/photo_0002.jpg'
duration 3.0
...
file '/tmp/photo_0005.jpg'
```

**Video Encoding:**
- Codec: H.264 (libx264)
- Preset: Medium (balance of speed/quality)
- CRF: 23 (constant rate factor - good quality)
- Color Space: YUV420P (universal compatibility)
- Aspect Ratio: Maintains original, pads to target resolution

### API Endpoints

#### 1. Create Slideshow
**Endpoint:** `POST /create_slideshow`

**Request Body:**
```json
{
  "photo_ids": [1, 2, 3, 4, 5],
  "duration_per_photo": 3.0,
  "transition": "fade",
  "resolution": "1920x1080",
  "output_filename": "my_slideshow.mp4"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Slideshow created successfully with 5 photos",
  "filename": "my_slideshow.mp4",
  "download_url": "/download_slideshow/my_slideshow.mp4",
  "num_photos": 5,
  "duration_per_photo": 3.0,
  "estimated_duration": 15.0,
  "file_size_mb": 5.23
}
```

**Error Response:**
```json
{
  "error": "No photos selected"
}
```

**Process:**
1. Validates photo_ids array is not empty
2. Retrieves photo records from `ALBUM_MEDIA` table
3. Gets presigned URLs for photos from OCI
4. Downloads photos to temporary directory
5. Creates FFmpeg input file list
6. Executes FFmpeg with 5-minute timeout
7. Saves output to `static/slideshows/`
8. Returns metadata and download URL
9. Cleans up temporary files

#### 2. Download Slideshow
**Endpoint:** `GET /download_slideshow/<filename>`

**Response:** MP4 video file (application/octet-stream)

**Example:**
```bash
curl -O http://150.136.235.189/download_slideshow/slideshow_20251107_045500.mp4
```

#### 3. Delete Slideshow
**Endpoint:** `DELETE /download_slideshow/<filename>`

**Response:**
```json
{
  "success": true,
  "message": "Slideshow deleted"
}
```

#### 4. List Slideshows
**Endpoint:** `GET /list_slideshows`

**Response:**
```json
{
  "slideshows": [
    {
      "filename": "slideshow_20251107_045500.mp4",
      "size_mb": 5.23,
      "created": "2025-11-07 04:55:00",
      "download_url": "/download_slideshow/slideshow_20251107_045500.mp4"
    }
  ],
  "count": 1
}
```

## File Management

### Storage Structure

```
TwelvelabsWithOracleVector/
├── static/
│   └── slideshows/              # Created slideshows
│       ├── slideshow_20251107_045500.mp4
│       ├── vacation_memories.mp4
│       └── family_2024.mp4
├── temp/                        # Temporary photo downloads (auto-cleaned)
└── src/
    └── localhost_only_flask.py  # Main application
```

### Automatic Cleanup

**Temporary Files:**
- Photos downloaded to `/tmp/` directory during creation
- Automatically deleted after slideshow generation
- Uses `shutil.rmtree(temp_dir)` in finally block

**Permanent Files:**
- Slideshows stored in `static/slideshows/` permanently
- Must be manually deleted via UI or API
- No automatic expiration

### Disk Space Management

**Photo Downloads:**
- Typical photo: 2-5 MB
- 10 photos: ~30 MB temp space
- Cleaned after creation

**Slideshow Output:**
- Depends on resolution, duration, and photo count
- Typical: 1-10 MB per slideshow
- Example: 5 photos at Full HD = ~5 MB

**Server Capacity:**
- Monitor `static/slideshows/` directory size
- Delete old slideshows via UI as needed
- Consider implementing automatic cleanup after X days (future enhancement)

## Troubleshooting

### Common Issues

**1. "Failed to create slideshow video" Error**

**Causes:**
- FFmpeg not installed on server
- FFmpeg timeout (>5 minutes)
- Photo download failures from OCI
- Insufficient disk space

**Solutions:**
```bash
# Check FFmpeg installation
ssh ubuntu@150.136.235.189
which ffmpeg
ffmpeg -version

# Install FFmpeg if missing
sudo apt update
sudo apt install -y ffmpeg

# Check disk space
df -h /home/dataguardian/TwelvelabsWithOracleVector/static

# Check logs
sudo journalctl -u dataguardian -n 100 | grep slideshow
```

**2. "No valid photos found" Error**

**Causes:**
- Invalid photo IDs
- Photos deleted from database
- Database connection issues

**Solutions:**
- Verify photos exist in ALBUM_MEDIA table
- Check database connection
- Re-search for photos

**3. Slideshow Creation Timeout**

**Causes:**
- Too many photos (>50)
- Large photo files (>10 MB each)
- Slow OCI download speeds
- Server resource constraints

**Solutions:**
- Limit selection to 20-30 photos
- Use lower resolution (720p instead of 4K)
- Check OCI network connectivity
- Monitor server CPU/memory usage

**4. Download Link Not Working**

**Causes:**
- File not created successfully
- Incorrect file path
- Nginx configuration issues

**Solutions:**
```bash
# Check file exists
ls -lh /home/dataguardian/TwelvelabsWithOracleVector/static/slideshows/

# Check Nginx serving static files
sudo nginx -t
sudo systemctl restart nginx

# Verify permissions
sudo chown -R dataguardian:www-data /home/dataguardian/TwelvelabsWithOracleVector/static/slideshows/
sudo chmod -R 755 /home/dataguardian/TwelvelabsWithOracleVector/static/slideshows/
```

### Debugging

**Enable Detailed Logging:**
```python
# In localhost_only_flask.py
logger.setLevel(logging.DEBUG)
```

**Check FFmpeg Output:**
```bash
# Manual test
cd /home/dataguardian/TwelvelabsWithOracleVector
source twelvelabvideoai/bin/activate
python3 -c "
from src.localhost_only_flask import *
# Test slideshow creation manually
"
```

**View Real-time Logs:**
```bash
# Terminal 1: Tail application logs
sudo journalctl -u dataguardian -f

# Terminal 2: Test slideshow creation from UI
# Watch for errors in Terminal 1
```

## Performance Considerations

### Creation Time Estimates

| Photos | Resolution | Duration/Photo | Est. Creation Time |
|--------|------------|----------------|-------------------|
| 5      | HD         | 3s            | 10-15 seconds     |
| 10     | Full HD    | 3s            | 20-30 seconds     |
| 20     | Full HD    | 3s            | 40-60 seconds     |
| 30     | 4K         | 5s            | 2-3 minutes       |

**Factors Affecting Speed:**
- Photo resolution and file size
- Server CPU performance
- OCI download bandwidth
- Number of photos
- Target resolution

### Optimization Tips

**For Faster Creation:**
- Use HD (720p) instead of 4K
- Shorter duration per photo (2s vs 5s)
- Limit selection to 10-15 photos
- Ensure good OCI network connectivity

**For Better Quality:**
- Use 4K resolution for large displays
- Longer duration per photo (5s)
- Source photos should be high quality
- Use lossless source photos if available

## Security Considerations

### Access Control

**Authentication Required:**
- All endpoints require login
- Uses Flask-Login session management
- Admin credentials: admin / 1tMslvkY9TrCSeQH

**File Access:**
- Slideshows stored in application directory
- Served through Flask (not direct file access)
- Filename validation to prevent directory traversal

### Input Validation

**Photo IDs:**
```python
# Validates photo_ids are integers
photo_ids = [int(id) for id in data.get('photo_ids', [])]
```

**Filename Sanitization:**
```python
# Default filename with timestamp prevents injection
output_filename = f'slideshow_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
```

**SQL Injection Prevention:**
```python
# Uses parameterized queries
cursor.execute("""SELECT file_path FROM album_media WHERE id = :id""", {"id": photo_id})
```

## Future Enhancements

### Planned Features

- [ ] **Custom Transitions:** More transition effects (wipe, zoom, rotate)
- [ ] **Background Music:** Add audio track to slideshow
- [ ] **Text Overlays:** Captions, dates, or titles on photos
- [ ] **Preview:** Preview slideshow before final creation
- [ ] **Templates:** Pre-configured slideshow styles
- [ ] **Batch Creation:** Create multiple slideshows at once
- [ ] **Auto-Cleanup:** Delete slideshows older than X days
- [ ] **Cloud Storage:** Upload finished slideshows to OCI
- [ ] **Share Links:** Generate shareable URLs for slideshows
- [ ] **Progress Bar:** Real-time creation progress

### Implementation Ideas

**Background Music:**
```python
ffmpeg_cmd += ['-i', music_file, '-c:a', 'aac', '-b:a', '192k']
```

**Text Overlays:**
```python
drawtext = f"drawtext=text='{caption}':fontsize=48:x=(w-text_w)/2:y=h-100"
```

**Progress Tracking:**
```python
# Use FFmpeg progress output parsing
# Send updates via WebSocket or SSE
```

## Support

### Getting Help

**Check Logs:**
```bash
sudo journalctl -u dataguardian -n 100 | grep slideshow
```

**Test FFmpeg:**
```bash
ffmpeg -version
```

**Database Query:**
```sql
SELECT COUNT(*) FROM album_media WHERE file_type = 'photo';
```

**Contact:**
- GitHub Issues: https://github.com/DeepakMishra1108/TwelvelabsWithOracleVector/issues
- Server: 150.136.235.189
- Service: dataguardian.service

---

**Last Updated:** November 7, 2025  
**Version:** 1.0  
**Status:** Production Ready ✅
