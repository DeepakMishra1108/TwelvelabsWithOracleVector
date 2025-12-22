-- Add rich_metadata column to album_media table for storing AI-generated descriptions
-- This will store structured metadata like: background, objects, activities, clothing, themes, mood

ALTER TABLE album_media ADD (
    rich_metadata CLOB CHECK (rich_metadata IS JSON)
);

-- Create an index for JSON searches
CREATE INDEX idx_album_media_rich_metadata ON album_media(rich_metadata) INDEXTYPE IS CTXSYS.CONTEXT;

-- Verify the column was added
SELECT column_name, data_type 
FROM user_tab_columns 
WHERE table_name = 'ALBUM_MEDIA' 
AND column_name = 'RICH_METADATA';
