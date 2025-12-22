-- Check current face name distribution
SELECT face_name, COUNT(*) as count
FROM face_tags
WHERE face_name IS NOT NULL
GROUP BY face_name
ORDER BY COUNT(*) DESC;

-- Show a sample of photos with Group_1 faces
SELECT DISTINCT am.id, am.file_name, ft.face_name
FROM face_tags ft
JOIN album_media am ON ft.media_id = am.id
WHERE ft.face_name = 'Group_1'
FETCH FIRST 10 ROWS ONLY;
