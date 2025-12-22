-- Create vector index on face_tags.face_embedding for faster similarity search
-- This index dramatically improves performance when searching for similar faces

-- Check if index already exists
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM user_indexes
    WHERE index_name = 'IDX_FACE_EMBEDDING_VECTOR';
    
    IF v_count = 0 THEN
        -- Create vector index using IVF (Inverted File Index) with HNSW (Hierarchical Navigable Small World)
        -- Parameters:
        -- - DISTANCE: COSINE (matches the VECTOR_DISTANCE metric used in queries)
        -- - ACCURACY: 95 (balance between speed and accuracy)
        EXECUTE IMMEDIATE '
            CREATE VECTOR INDEX idx_face_embedding_vector 
            ON face_tags(face_embedding)
            ORGANIZATION NEIGHBOR PARTITIONS
            WITH DISTANCE COSINE
            WITH TARGET ACCURACY 95';
        
        DBMS_OUTPUT.PUT_LINE('✅ Vector index created on face_tags.face_embedding');
    ELSE
        DBMS_OUTPUT.PUT_LINE('ℹ️  Vector index already exists on face_tags.face_embedding');
    END IF;
END;
/

-- Gather statistics for the new index
BEGIN
    DBMS_STATS.GATHER_INDEX_STATS(
        ownname => USER,
        indname => 'IDX_FACE_EMBEDDING_VECTOR',
        estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE
    );
    DBMS_OUTPUT.PUT_LINE('✅ Index statistics gathered');
END;
/

-- Show index details
SELECT 
    index_name,
    index_type,
    status,
    tablespace_name
FROM user_indexes
WHERE index_name = 'IDX_FACE_EMBEDDING_VECTOR';
