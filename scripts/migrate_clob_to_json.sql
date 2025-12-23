-- Migrate CLOB columns to native JSON type for better performance in Oracle 26ai
-- This provides better performance, simpler queries, and native JSON operations

-- 1. Migrate rich_metadata from CLOB to JSON
BEGIN
    -- Add new JSON column
    EXECUTE IMMEDIATE 'ALTER TABLE album_media ADD rich_metadata_json JSON';
    
    -- Copy data from CLOB to JSON (only valid JSON)
    EXECUTE IMMEDIATE '
        UPDATE album_media 
        SET rich_metadata_json = rich_metadata
        WHERE rich_metadata IS NOT NULL 
        AND JSON_VALID(rich_metadata) = 1
    ';
    
    COMMIT;
    
    -- Drop old CLOB column
    EXECUTE IMMEDIATE 'ALTER TABLE album_media DROP COLUMN rich_metadata';
    
    -- Rename new column to original name
    EXECUTE IMMEDIATE 'ALTER TABLE album_media RENAME COLUMN rich_metadata_json TO rich_metadata';
    
    DBMS_OUTPUT.PUT_LINE('✅ Migrated rich_metadata from CLOB to JSON');
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        DBMS_OUTPUT.PUT_LINE('❌ Error migrating rich_metadata: ' || SQLERRM);
        RAISE;
END;
/

-- 2. Migrate AI_TAGS from CLOB to JSON (if it stores JSON data)
-- Check if AI_TAGS is JSON or plain text first
DECLARE
    v_is_json NUMBER;
BEGIN
    -- Check if AI_TAGS contains JSON
    SELECT COUNT(*)
    INTO v_is_json
    FROM album_media
    WHERE AI_TAGS IS NOT NULL
    AND JSON_VALID(AI_TAGS) = 1
    AND ROWNUM = 1;
    
    IF v_is_json > 0 THEN
        -- AI_TAGS contains JSON, migrate it
        EXECUTE IMMEDIATE 'ALTER TABLE album_media ADD ai_tags_json JSON';
        
        EXECUTE IMMEDIATE '
            UPDATE album_media 
            SET ai_tags_json = AI_TAGS
            WHERE AI_TAGS IS NOT NULL 
            AND JSON_VALID(AI_TAGS) = 1
        ';
        
        COMMIT;
        
        EXECUTE IMMEDIATE 'ALTER TABLE album_media DROP COLUMN AI_TAGS';
        EXECUTE IMMEDIATE 'ALTER TABLE album_media RENAME COLUMN ai_tags_json TO AI_TAGS';
        
        DBMS_OUTPUT.PUT_LINE('✅ Migrated AI_TAGS from CLOB to JSON');
    ELSE
        DBMS_OUTPUT.PUT_LINE('ℹ️  AI_TAGS is not JSON data, keeping as CLOB');
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        DBMS_OUTPUT.PUT_LINE('⚠️  AI_TAGS migration skipped: ' || SQLERRM);
END;
/

-- 3. Create JSON search indexes for better performance
BEGIN
    -- Index for rich_metadata tags
    EXECUTE IMMEDIATE '
        CREATE SEARCH INDEX rich_metadata_search_idx 
        ON album_media (rich_metadata) 
        FOR JSON
    ';
    DBMS_OUTPUT.PUT_LINE('✅ Created JSON search index on rich_metadata');
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -1418 THEN
            DBMS_OUTPUT.PUT_LINE('ℹ️  Search index already exists');
        ELSE
            DBMS_OUTPUT.PUT_LINE('⚠️  Could not create search index: ' || SQLERRM);
        END IF;
END;
/

-- Verify migration
SELECT 
    'rich_metadata' as column_name,
    data_type,
    COUNT(*) as row_count
FROM user_tab_columns, album_media
WHERE table_name = 'ALBUM_MEDIA'
AND column_name = 'RICH_METADATA'
GROUP BY data_type;

SELECT 
    'AI_TAGS' as column_name,
    data_type,
    COUNT(*) as row_count
FROM user_tab_columns, album_media
WHERE table_name = 'ALBUM_MEDIA'
AND column_name = 'AI_TAGS'
GROUP BY data_type;

DBMS_OUTPUT.PUT_LINE('✅ Migration complete!');
