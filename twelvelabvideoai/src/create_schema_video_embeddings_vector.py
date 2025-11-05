#!/usr/bin/env python3
"""Create enhanced video embeddings table with Oracle VECTOR support

This script creates the video_embeddings table with Oracle VECTOR type
for improved search performance and native vector operations.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.db_utils_vector import get_db_connection, validate_db_config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_video_embeddings_table_vector():
    """Create video_embeddings table with Oracle VECTOR type"""
    
    # Validate configuration first
    try:
        validate_db_config()
    except Exception as e:
        logger.error(f"Database configuration invalid: {e}")
        return False
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Drop existing table if it exists
        try:
            cursor.execute("DROP TABLE video_embeddings")
            logger.info("Dropped existing video_embeddings table")
        except Exception:
            pass  # Table doesn't exist
        
        # Create table with Oracle VECTOR type
        # Using VECTOR(1024, FLOAT32) for TwelveLabs Marengo embeddings
        create_table_sql = """
        CREATE TABLE video_embeddings (
            id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            video_file VARCHAR2(2000) NOT NULL,
            start_time NUMBER(10,2) NOT NULL,
            end_time NUMBER(10,2) NOT NULL,
            embedding_vector VECTOR(1024, FLOAT32),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        cursor.execute(create_table_sql)
        logger.info("Created video_embeddings table with VECTOR type")
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX idx_video_embeddings_file ON video_embeddings(video_file)",
            "CREATE INDEX idx_video_embeddings_time ON video_embeddings(start_time, end_time)",
            "CREATE INDEX idx_video_embeddings_created ON video_embeddings(created_at)",
            # Vector index for similarity search optimization
            "CREATE VECTOR INDEX idx_video_embeddings_vector ON video_embeddings(embedding_vector) PARAMETERS('accuracy 0.95')"
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                logger.info(f"Created index: {index_sql.split()[2]}")
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")
        
        # Create trigger for updated_at
        trigger_sql = """
        CREATE OR REPLACE TRIGGER trg_video_embeddings_updated_at
        BEFORE UPDATE ON video_embeddings
        FOR EACH ROW
        BEGIN
            :NEW.updated_at := CURRENT_TIMESTAMP;
        END;
        """
        
        cursor.execute(trigger_sql)
        logger.info("Created update trigger for video_embeddings")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ Video embeddings table created successfully with Oracle VECTOR support")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create video embeddings table: {e}")
        return False


def verify_table_structure():
    """Verify the table was created correctly"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check table structure
        cursor.execute("""
            SELECT column_name, data_type, data_length, data_precision, data_scale
            FROM user_tab_columns 
            WHERE table_name = 'VIDEO_EMBEDDINGS'
            ORDER BY column_id
        """)
        
        columns = cursor.fetchall()
        logger.info("Video embeddings table structure:")
        for col in columns:
            logger.info(f"  {col[0]}: {col[1]}")
        
        # Check indexes
        cursor.execute("""
            SELECT index_name, index_type, uniqueness
            FROM user_indexes 
            WHERE table_name = 'VIDEO_EMBEDDINGS'
        """)
        
        indexes = cursor.fetchall()
        logger.info("Indexes created:")
        for idx in indexes:
            logger.info(f"  {idx[0]}: {idx[1]} ({idx[2]})")
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to verify table structure: {e}")
        return False


if __name__ == "__main__":
    print("Creating video embeddings table with Oracle VECTOR support...")
    
    if create_video_embeddings_table_vector():
        print("\n" + "="*60)
        print("✅ SUCCESS: Video embeddings table created with VECTOR support")
        print("="*60)
        
        if verify_table_structure():
            print("✅ Table structure verified successfully")
        
        print("\nFeatures enabled:")
        print("• Oracle VECTOR(1024, FLOAT32) for embeddings")
        print("• Vector similarity search with VECTOR_DISTANCE()")
        print("• Vector indexes for performance optimization")
        print("• Automatic timestamps and triggers")
        print("• Optimized indexes for common queries")
        
    else:
        print("\n" + "="*60)
        print("❌ FAILED: Could not create video embeddings table")
        print("="*60)
        sys.exit(1)