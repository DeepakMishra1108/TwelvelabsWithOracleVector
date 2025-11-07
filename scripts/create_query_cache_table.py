#!/usr/bin/env python3
"""Create query embedding cache table to reduce TwelveLabs API calls"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

from utils.db_utils_flask_safe import get_flask_safe_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_query_cache_table():
    """Create table to cache search query embeddings"""
    
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_tables 
                WHERE table_name = 'QUERY_EMBEDDING_CACHE'
            """)
            
            if cursor.fetchone()[0] > 0:
                logger.info("✅ QUERY_EMBEDDING_CACHE table already exists")
                return
            
            logger.info("🔧 Creating QUERY_EMBEDDING_CACHE table...")
            
            # Create table
            cursor.execute("""
                CREATE TABLE query_embedding_cache (
                    id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    query_text VARCHAR2(500) NOT NULL UNIQUE,
                    embedding_vector VECTOR(1024, FLOAT32),
                    model_name VARCHAR2(100) DEFAULT 'Marengo-retrieval-2.7',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usage_count NUMBER DEFAULT 1
                )
            """)
            
            # Create index on query_text for fast lookups
            cursor.execute("""
                CREATE INDEX idx_query_cache_text ON query_embedding_cache(query_text)
            """)
            
            # Create index on last_used_at for cache cleanup
            cursor.execute("""
                CREATE INDEX idx_query_cache_last_used ON query_embedding_cache(last_used_at)
            """)
            
            conn.commit()
            logger.info("✅ QUERY_EMBEDDING_CACHE table created successfully!")
            logger.info("   - Columns: query_text, embedding_vector, model_name, usage_count")
            logger.info("   - Indexes: query_text, last_used_at")
            
    except Exception as e:
        logger.error(f"❌ Failed to create table: {e}")
        raise

if __name__ == '__main__':
    create_query_cache_table()
