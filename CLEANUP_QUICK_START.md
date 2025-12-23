# Album Cleanup & Refresh - Quick Reference

## What This Does
- ✅ Deletes photos/videos from **database** (album_media table)
- ✅ Deletes actual files from **OCI Object Storage** (not just database records)
- ✅ **Preserves face_tags** (your 90 trained faces for auto-tagging)
- ✅ Creates backup before deletion
- ✅ Supports selective deletion (photos only, specific albums, etc.)

## Quick Start

### 1. Dry Run (See What Would Be Deleted)
```bash
cd /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI
python scripts/cleanup_albums_and_oci.py --dry-run
```

### 2. Delete Photos Only (Keep Videos)
```bash
python scripts/cleanup_albums_and_oci.py --type photo --backup --yes
```

### 3. Nuclear Option (Delete Everything)
```bash
python scripts/cleanup_albums_and_oci.py --type all --backup --yes
```

### 4. Delete Specific Album
```bash
python scripts/cleanup_albums_and_oci.py --album "OldPhotos" --backup
```

## Options Explained

| Flag | Description | Example |
|------|-------------|---------|
| `--dry-run` | Preview without deleting | `--dry-run` |
| `--yes` | Skip confirmation | `--yes` |
| `--type` | What to delete | `--type photo` or `--type video` or `--type all` |
| `--album` | Specific album only | `--album "Vacation2024"` |
| `--backup` | Create JSON backup | `--backup` |
| `--backup-file` | Custom backup path | `--backup-file backup_20251222.json` |

## What Gets Preserved

✅ **face_tags table** - Your trained faces (Deepak, Sheetal, Rahul, etc.)
✅ **Face embeddings** - 1024-dim ImageBind vectors
✅ **imagebind_processed flags** - Tracking which faces are trained
✅ **users table** - Login credentials
✅ **User sessions** - No need to re-login

## What Gets Deleted

❌ **album_media records** - Photo/video database entries
❌ **OCI objects** - Actual files in Object Storage bucket
❌ **Old metadata** - Any legacy metadata
❌ **Face tag links** - Connections between deleted photos and face_tags
   - Note: The face_tag entries stay, just media_id becomes orphaned
   - **OR** use `ON DELETE CASCADE` to auto-remove orphaned tags

## Workflow After Cleanup

### Step 1: Run Cleanup
```bash
# Full cleanup with backup
python scripts/cleanup_albums_and_oci.py --type all --backup --yes

# Output will show:
# ✅ Backed up 287 media records
# ✅ Deleted 287 objects from OCI
# ✅ Deleted 287 records from database
# ✅ Face tags preserved: 90
```

### Step 2: Upload New Photos
1. Go to https://150.136.235.189:8443
2. Login as admin
3. Click "Upload Photos"
4. Select photos
5. ✅ Enable "Detect Faces"
6. ✅ Enable "Extract Metadata"
7. Album name: "FreshStart2025"
8. Upload

### Step 3: Verify Auto-Tagging
```sql
-- Check if new photos got auto-tagged
SELECT ft.face_name, COUNT(DISTINCT ft.media_id) as photos_tagged
FROM face_tags ft
INNER JOIN album_media am ON ft.media_id = am.id
WHERE am.created_at > SYSDATE - 1  -- Last 24 hours
GROUP BY ft.face_name;

-- Expected output:
-- Deepak: 15 new photos
-- Sheetal: 10 new photos
-- Unknown: 5 new faces
```

### Step 4: Test Features
```bash
# Camera Search
# Upload selfie → Should find matching photos

# Person Search
# Search "Deepak" → Should return auto-tagged photos

# Unified Search
# "Deepak and Sheetal" → Photos with both people
```

## Cleanup Orphaned Face Tags (Optional)

If you want to remove face_tags that no longer have photos:

```sql
-- Find orphaned face tags
SELECT COUNT(*) FROM face_tags 
WHERE media_id NOT IN (SELECT id FROM album_media);

-- Delete orphaned tags (BE CAREFUL!)
DELETE FROM face_tags 
WHERE media_id NOT IN (SELECT id FROM album_media);
COMMIT;

-- This removes face tag records but KEEPS the learned embeddings
-- If you want to keep the embeddings for future matching, DON'T run this
```

## Emergency Recovery

If something goes wrong, restore from backup:

```python
import json
import oracledb

# Load backup
with open('backup_20251222.json') as f:
    backup = json.load(f)

# Restore database records
conn = oracledb.connect(...)
cursor = conn.cursor()

for record in backup['media_records']:
    cursor.execute("""
        INSERT INTO album_media 
        (id, file_name, file_type, file_path, oci_namespace, 
         oci_bucket, oci_object_path, album_name, file_size, user_id)
        VALUES 
        (:id, :file_name, :file_type, :file_path, :oci_namespace,
         :oci_bucket, :oci_object_path, :album_name, :file_size, :user_id)
    """, record)

conn.commit()
```

**Note**: OCI objects are not backed up by this script. Make sure you have OCI backups or alternative copies before deletion.

## Safety Checks

Before running cleanup:

1. ✅ Check backup created successfully
2. ✅ Verify face_tags count is preserved
3. ✅ Confirm you have new photos ready to upload
4. ✅ Test on a small album first (--album "TestAlbum")
5. ✅ Run with --dry-run first

## Common Scenarios

### Scenario 1: Fresh Start with New Photos
```bash
# 1. Backup and delete everything
python scripts/cleanup_albums_and_oci.py --type all --backup --yes

# 2. Upload new photos (20-30 for testing)
# 3. Verify auto-tagging works
# 4. Upload remaining photos
```

### Scenario 2: Keep Videos, Refresh Photos
```bash
# 1. Delete only photos
python scripts/cleanup_albums_and_oci.py --type photo --backup --yes

# 2. Upload new photos
```

### Scenario 3: Delete Specific Old Album
```bash
# 1. Delete one album
python scripts/cleanup_albums_and_oci.py --album "OldVacation2023" --backup

# 2. Keep other albums intact
```

## Troubleshooting

### "Failed to connect to database"
- Check DB_USER, DB_PASSWORD, DB_DSN in .env
- Test connection: `sqlplus username/password@database`

### "Failed to connect to OCI"
- Check OCI_CONFIG_PATH in .env (default: ~/.oci/config)
- Verify config file exists: `ls ~/.oci/config`
- Test OCI CLI: `oci os ns get`

### "Permission denied"
- Make script executable: `chmod +x scripts/cleanup_albums_and_oci.py`

### "OCI objects not found"
- Check oci_namespace, oci_bucket in album_media records
- Verify bucket exists in OCI Console

## Final Checklist

Before cleanup:
- [ ] Backup created
- [ ] Dry-run tested
- [ ] Face tags count confirmed
- [ ] New photos ready to upload

After cleanup:
- [ ] Database empty (or reduced)
- [ ] Face tags preserved (90 entries)
- [ ] New photos uploaded
- [ ] Auto-tagging verified
- [ ] Camera search works
- [ ] Person search works
- [ ] Unified search works

## Current Status

As of 2025-12-22 07:20 UTC:
- ✅ Cleanup script created and tested
- ✅ Face embeddings: 90/965 complete (9.3%)
- ✅ Camera search: WORKING (images display)
- ✅ Person search: WORKING (ORA-22848 fixed)
- ✅ Unified search: WORKING (multi-person AND logic)
- ✅ Cultural metadata: Enhanced GPT-4o prompts
- ⚠️ Backfill: 875 faces remaining

Recommended: Run cleanup, upload fresh photos, complete backfill on new dataset.
