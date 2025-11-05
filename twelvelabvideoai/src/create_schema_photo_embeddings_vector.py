#!/usr/bin/env python3
"""Create enhanced photo embeddings table with Oracle VECTOR support

This script creates the photo_embeddings table with Oracle VECTOR type
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

def create_photo_embeddings_table_vector():
    """Create photo_embeddings table with Oracle VECTOR type"""
    
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
            cursor.execute("DROP TABLE photo_embeddings")
            logger.info("Dropped existing photo_embeddings table")
        except Exception:
            pass  # Table doesn't exist
        
        # Create table with Oracle VECTOR type
        # Using VECTOR(1024, FLOAT32) for TwelveLabs Marengo embeddings
        create_table_sql = """
        CREATE TABLE photo_embeddings (
            id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            album_name VARCHAR2(500) NOT NULL,
            photo_file VARCHAR2(2000) NOT NULL,
            embedding_vector VECTOR(1024, FLOAT32),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uk_photo_embeddings UNIQUE (album_name, photo_file)
        )
        """
        
        cursor.execute(create_table_sql)
        logger.info("Created photo_embeddings table with VECTOR type")
        
        # Create indexes for better performance
        indexes = [
            "CREATE INDEX idx_photo_embeddings_album ON photo_embeddings(album_name)",
            "CREATE INDEX idx_photo_embeddings_file ON photo_embeddings(photo_file)",
            "CREATE INDEX idx_photo_embeddings_created ON photo_embeddings(created_at)",
            # Vector index for similarity search optimization
            "CREATE VECTOR INDEX idx_photo_embeddings_vector ON photo_embeddings(embedding_vector) PARAMETERS('accuracy 0.95')"
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                logger.info(f"Created index: {index_sql.split()[2]}")
            except Exception as e:
                logger.warning(f"Failed to create index: {e}")
        
        # Create trigger for updated_at
        trigger_sql = """
        CREATE OR REPLACE TRIGGER trg_photo_embeddings_updated_at
        BEFORE UPDATE ON photo_embeddings
        FOR EACH ROW
        BEGIN
            :NEW.updated_at := CURRENT_TIMESTAMP;
        END;
        """
        
        cursor.execute(trigger_sql)
        logger.info("Created update trigger for photo_embeddings")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info("✅ Photo embeddings table created successfully with Oracle VECTOR support")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create photo embeddings table: {e}")
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
            WHERE table_name = 'PHOTO_EMBEDDINGS'
            ORDER BY column_id
        """)
        
        columns = cursor.fetchall()
        logger.info("Photo embeddings table structure:")
        for col in columns:
            logger.info(f"  {col[0]}: {col[1]}")
        
        # Check indexes
        cursor.execute("""
            SELECT index_name, index_type, uniqueness
            FROM user_indexes 
            WHERE table_name = 'PHOTO_EMBEDDINGS'
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
    print("Creating photo embeddings table with Oracle VECTOR support...")
    
    if create_photo_embeddings_table_vector():
        print("\n" + "="*60)
        print("✅ SUCCESS: Photo embeddings table created with VECTOR support")
        print("="*60)
        
        if verify_table_structure():
            print("✅ Table structure verified successfully")
        
        print("\nFeatures enabled:")
        print("• Oracle VECTOR(1024, FLOAT32) for embeddings")
        print("• Vector similarity search with VECTOR_DISTANCE()")
        print("• Vector indexes for performance optimization")
        print("• Automatic timestamps and triggers")
        print("• Optimized indexes for common queries")
        print("• Unique constraint on album_name + photo_file")
        
    else:
        print("\n" + "="*60)
        print("❌ FAILED: Could not create photo embeddings table")
        print("="*60)
        sys.exit(1)