#!/bin/bash
# Complete Album Reset and Re-upload Workflow
# Date: 2025-12-22

set -e  # Exit on error

echo "=========================================="
echo "Album Reset and Re-upload Workflow"
echo "=========================================="
echo ""

# Configuration
DB_USER="your_db_user"
DB_PASS="your_db_password"
DB_SERVICE="your_db_service"
UPLOAD_DIR="/path/to/new/photos"
ALBUM_NAME="FreshStart2025"

# Step 1: Backup current state
echo "Step 1: Creating backups..."
sqlplus -S ${DB_USER}/${DB_PASS}@${DB_SERVICE} <<EOF
    CREATE TABLE face_tags_backup_$(date +%Y%m%d) AS SELECT * FROM face_tags;
    CREATE TABLE album_media_backup_$(date +%Y%m%d) AS SELECT * FROM album_media;
    
    SELECT 'Backed up ' || COUNT(*) || ' face tags' FROM face_tags;
    SELECT 'Backed up ' || COUNT(*) || ' media items' FROM album_media;
    EXIT;
EOF

echo "✅ Backups created"
echo ""

# Step 2: Show current state
echo "Step 2: Current state..."
sqlplus -S ${DB_USER}/${DB_PASS}@${DB_SERVICE} <<EOF
    SET HEADING ON
    SET FEEDBACK OFF
    
    SELECT 'Face Tags by Person:' as info FROM dual;
    SELECT face_name, COUNT(*) as count,
           SUM(CASE WHEN imagebind_processed = 1 THEN 1 ELSE 0 END) as imagebind_ready
    FROM face_tags 
    GROUP BY face_name 
    ORDER BY count DESC
    FETCH FIRST 10 ROWS ONLY;
    
    SELECT 'Media by Type:' as info FROM dual;
    SELECT file_type, COUNT(*) as count
    FROM album_media
    GROUP BY file_type;
    
    EXIT;
EOF

echo ""
read -p "❓ Do you want to DELETE all album media? [yes/NO]: " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted. No changes made."
    exit 0
fi

# Step 3: Delete album media
echo ""
echo "Step 3: Deleting album media..."
sqlplus -S ${DB_USER}/${DB_PASS}@${DB_SERVICE} <<EOF
    DELETE FROM album_media;
    COMMIT;
    
    SELECT 'Deleted. Remaining media: ' || COUNT(*) FROM album_media;
    SELECT 'Face tags preserved: ' || COUNT(*) FROM face_tags;
    EXIT;
EOF

echo "✅ Album media deleted, face tags preserved"
echo ""

# Step 4: Upload new photos via API
echo "Step 4: Uploading new photos..."
echo "ℹ️  Manual step required:"
echo "   1. Go to https://150.136.235.189:8443"
echo "   2. Login as admin"
echo "   3. Click 'Upload Photos'"
echo "   4. Select photos from: ${UPLOAD_DIR}"
echo "   5. Album name: ${ALBUM_NAME}"
echo "   6. Enable: 'Extract Metadata' (for cultural context)"
echo "   7. Enable: 'Detect Faces' (for auto-tagging)"
echo ""
read -p "Press ENTER when upload is complete..."

# Step 5: Verify auto-tagging worked
echo ""
echo "Step 5: Verifying auto-tagging..."
sqlplus -S ${DB_USER}/${DB_PASS}@${DB_SERVICE} <<EOF
    SET HEADING ON
    SET FEEDBACK OFF
    
    SELECT 'Newly uploaded media:' as info FROM dual;
    SELECT file_type, COUNT(*) as count
    FROM album_media
    GROUP BY file_type;
    
    SELECT 'Auto-tagged faces in new photos:' as info FROM dual;
    SELECT ft.face_name, COUNT(DISTINCT ft.media_id) as photos_tagged
    FROM face_tags ft
    INNER JOIN album_media am ON ft.media_id = am.id
    WHERE am.created_at > SYSDATE - 1  -- Last 24 hours
    GROUP BY ft.face_name
    ORDER BY photos_tagged DESC;
    
    SELECT 'Photos with metadata:' as info FROM dual;
    SELECT COUNT(*) as count,
           SUM(CASE WHEN rich_metadata IS NOT NULL THEN 1 ELSE 0 END) as with_rich_metadata
    FROM album_media
    WHERE created_at > SYSDATE - 1;
    
    EXIT;
EOF

echo ""
echo "=========================================="
echo "✅ Album reset complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Test camera search with your selfie"
echo "  2. Test person search: 'Deepak', 'Sheetal', etc."
echo "  3. Test unified search: 'Deepak and Sheetal'"
echo "  4. Verify cultural metadata in unified search"
echo "  5. Continue face embedding backfill if needed"
echo ""
