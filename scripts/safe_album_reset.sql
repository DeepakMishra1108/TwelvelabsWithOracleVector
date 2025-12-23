-- Safe Album Reset Script
-- Keeps: face_tags, users, authentication
-- Deletes: photos/videos from album_media
-- Date: 2025-12-22

-- STEP 1: BACKUP (Run these first to save data)
-- ============================================

-- Backup face_tags (your trained faces - KEEP THIS!)
create table face_tags_backup
   as
      select *
        from face_tags;

-- Backup album_media for reference
create table album_media_backup
   as
      select *
        from album_media;

-- Verify backups
select count(*) as face_tags_backup_count
  from face_tags_backup;
select count(*) as album_media_backup_count
  from album_media_backup;
select count(*) as face_tags_current_count
  from face_tags;
select count(*) as album_media_current_count
  from album_media;


-- STEP 2: CHECK WHAT WILL BE DELETED
-- ===================================

-- Check photos to be deleted
select file_type,
       count(*) as count,
       round(
          sum(file_size) / 1024 / 1024,
          2
       ) as total_mb
  from album_media
 group by file_type;

-- Check face tags per person
select face_name,
       count(*) as face_count,
       sum(
          case
             when imagebind_processed = 1 then
                1
             else
                0
          end
       ) as imagebind_ready
  from face_tags
 group by face_name
 order by face_count desc;


-- STEP 3: CLEAN ORPHANED FACE TAGS (Optional)
-- ============================================
-- Remove face tags that point to non-existent media
-- (Only if you've already deleted photos manually)

delete from face_tags
 where media_id not in (
   select id
     from album_media
);

-- Check remaining face tags
select count(*) as remaining_face_tags
  from face_tags;


-- STEP 4: DELETE ALBUM MEDIA (Nuclear option - use carefully!)
-- =============================================================
-- WARNING: This deletes ALL photos and videos from database
-- OCI objects will remain (not deleted automatically)

-- Option A: Delete all photos and videos
delete from album_media;
commit;

-- Option B: Delete only photos, keep videos
-- DELETE FROM album_media WHERE file_type = 'photo';
-- COMMIT;

-- Option C: Delete only videos, keep photos
-- DELETE FROM album_media WHERE file_type = 'video';
-- COMMIT;

-- Option D: Delete specific album only
-- DELETE FROM album_media WHERE album_name = 'YourAlbumName';
-- COMMIT;


-- STEP 5: VERIFY CLEAN STATE
-- ===========================

-- Should be empty (or reduced)
select count(*) as remaining_media
  from album_media;

-- Should still have your face embeddings
select count(*) as face_tags_count,
       sum(
          case
             when imagebind_processed = 1 then
                1
             else
                0
          end
       ) as with_imagebind
  from face_tags;

-- Check face tag distribution
select face_name,
       count(*) as count
  from face_tags
 group by face_name
 order by count desc;


-- STEP 6: RESET AUTO-INCREMENT (Optional)
-- ========================================
-- Reset media_id sequence if you want IDs to start from 1

-- Oracle doesn't use AUTO_INCREMENT, check if there's a sequence
-- SELECT sequence_name FROM user_sequences WHERE sequence_name LIKE '%ALBUM_MEDIA%';
-- ALTER SEQUENCE album_media_seq RESTART START WITH 1;


-- STEP 7: RESTORE IF NEEDED (Emergency recovery)
-- ===============================================
-- If something goes wrong, restore from backup

-- INSERT INTO album_media SELECT * FROM album_media_backup;
-- COMMIT;


-- STEP 8: CLEANUP BACKUPS (After verifying everything works)
-- ===========================================================
-- Drop backup tables after 7 days of successful operation

-- DROP TABLE album_media_backup;
-- DROP TABLE face_tags_backup;