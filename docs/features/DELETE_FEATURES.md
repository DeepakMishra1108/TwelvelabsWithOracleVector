# Delete Features Documentation

## Overview
The Media Intelligence Platform now includes comprehensive delete capabilities for managing your media library. You can delete individual images, videos, or entire albums with proper safety confirmations.

## Features Added

### 1. Delete Individual Media Items
- **Location**: Search Results tab and Album browsing
- **Button**: Small red trash icon button in the top-right corner of each media card
- **Confirmation**: Single confirmation dialog showing:
  - File name
  - Media type (photo/video)
  - Album name
  - Warning that action cannot be undone

**What Gets Deleted:**
- ✅ Database record (metadata, embeddings)
- ✅ OCI Object Storage file
- ✅ All associated AI embeddings

**Visual Feedback:**
- Card fades out smoothly after deletion
- Success message displayed
- Album list automatically refreshes

### 2. Delete Complete Albums
- **Location**: Browse Albums tab
- **Button**: Red trash icon button in the top-right corner of each album card
- **Two-Step Confirmation**:
  1. Initial warning dialog with detailed information
  2. Type album name to confirm (prevents accidental deletion)

**What Gets Deleted:**
- ✅ All photos in the album
- ✅ All videos in the album
- ✅ All files from OCI Object Storage
- ✅ All AI embeddings and metadata
- ✅ Complete album data from database

**Safety Features:**
- Double confirmation required
- User must type exact album name to proceed
- Clear warnings about permanent deletion
- Lists what will be deleted before action

## API Endpoints

### Delete Media Item
```
DELETE /delete_media/<media_id>
```

**Response Success:**
```json
{
  "success": true,
  "message": "Deleted video 'example.mp4' from Taylor Swift Era",
  "media_id": 61
}
```

**Response Error:**
```json
{
  "error": "Media not found"
}
```

### Delete Album
```
DELETE /delete_album/<album_name>
```

**Response Success:**
```json
{
  "success": true,
  "message": "Deleted album 'Taylor Swift Era' with 25 items",
  "deleted_count": 25,
  "oci_errors": []
}
```

**Response Error:**
```json
{
  "error": "Album not found or empty"
}
```

## Usage Guide

### Deleting a Single Photo/Video

1. Navigate to the Search Results or Browse Albums tab
2. Find the media item you want to delete
3. Click the red trash icon (🗑️) in the top-right corner of the media card
4. Review the confirmation dialog:
   - File name
   - Media type
   - Album name
5. Click "OK" to confirm deletion or "Cancel" to abort
6. The item will fade out and disappear
7. A success message will appear at the top

### Deleting an Entire Album

1. Navigate to the "Browse Albums" tab
2. Find the album you want to delete
3. Click the red trash icon (🗑️) in the top-right corner of the album card
4. Read the detailed warning dialog carefully
5. Click "OK" to proceed or "Cancel" to abort
6. Type the exact album name in the confirmation prompt
7. Press "OK" to complete the deletion
8. An alert will show how many items were deleted
9. The album will disappear from the list

## Safety Features

### For Individual Media
- ✅ Single confirmation dialog
- ✅ Shows file details before deletion
- ✅ Cannot be undone warning
- ✅ Smooth visual feedback

### For Albums
- ✅ Double confirmation (two-step process)
- ✅ Must type exact album name
- ✅ Detailed warning about what gets deleted
- ✅ Prevents accidental deletion
- ✅ Shows count of deleted items

## Technical Details

### Database Operations
- Deletes records from `album_media` table
- Removes all embeddings (TwelveLabs AI vectors)
- Removes all metadata (GPS, timestamps, etc.)

### OCI Object Storage
- Parses OCI path: `oci://namespace/bucket/object`
- Calls OCI API to delete file
- Handles errors gracefully (logs warning if OCI deletion fails)

### Error Handling
- Database errors: Returns HTTP 500 with error message
- OCI errors: Logs warning but continues (allows cleanup even if file already gone)
- Missing items: Returns HTTP 404 with clear error message
- Partial failures: For albums, reports which files had OCI errors

## Testing Instructions

### Test Delete Individual Media
```bash
# Open browser
open http://localhost:8080

# 1. Go to Browse Albums tab
# 2. Click on any album to view its contents
# 3. Click the trash icon on any media item
# 4. Confirm deletion
# 5. Verify item disappears
```

### Test Delete Album
```bash
# Open browser
open http://localhost:8080

# 1. Go to Browse Albums tab
# 2. Click trash icon on any album
# 3. Confirm in first dialog
# 4. Type album name in second prompt
# 5. Verify album disappears
```

### Test via API
```bash
# Delete media item
curl -X DELETE http://localhost:8080/delete_media/123

# Delete album
curl -X DELETE http://localhost:8080/delete_album/TestAlbum
```

## Current Database Status

As of now, you have:
- **Isha Album**: 17 photos, 0 videos

You can test the delete functionality with this album or upload new test content.

## Important Notes

⚠️ **Permanent Deletion**: All delete operations are permanent and cannot be undone. Make sure you want to delete before confirming.

⚠️ **OCI Storage**: Files are deleted from OCI Object Storage. If OCI deletion fails (network issues, permissions), the database record is still removed, and a warning is logged.

⚠️ **No Recycle Bin**: There is no trash/recycle bin. Deleted content is gone permanently.

✅ **Safe Operations**: Double confirmations for albums prevent accidental deletion of large collections.

## Future Enhancements (Optional)

- [ ] Bulk delete: Select multiple items at once
- [ ] Trash/Recycle bin: Temporary holding for deleted items (30 days)
- [ ] Delete history log: Track what was deleted and when
- [ ] Undo capability: Restore recently deleted items
- [ ] Export before delete: Download items before deletion
- [ ] Soft delete: Mark as deleted without removing from storage

## Troubleshooting

### Delete button not appearing
- Check that Flask app is running: `lsof -i :8080`
- Clear browser cache and reload page
- Check browser console for JavaScript errors

### Deletion fails with error
- Check Flask logs: `tail -50 flask_output.log`
- Verify OCI credentials are valid
- Check database connection

### OCI deletion fails
- Check OCI credentials and permissions
- Verify bucket and namespace are correct
- Database will still be cleaned up (partial success)

## Access the Application

🌐 **Web Interface**: http://localhost:8080

The delete buttons are now visible on:
1. Each media card in search results
2. Each album card in the albums view
