-- Add index on face_tags.face_name for faster search
-- This will speed up unified search queries that filter by face names

CREATE INDEX IF NOT EXISTS idx_face_tags_face_name ON face_tags(face_name);

-- Also add index on media_id for faster joins
CREATE INDEX IF NOT EXISTS idx_face_tags_media_id ON face_tags(media_id);

-- Show index status
SELECT index_name, table_name, column_name, index_type 
FROM user_ind_columns 
WHERE table_name = 'FACE_TAGS';
