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
    """Create table to cache search query embeddings with Oracle 23ai in-memory optimization"""
    
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Drop table if exists (for clean recreation)
            try:
                logger.info("🗑️ Dropping existing QUERY_EMBEDDING_CACHE table if exists...")
                cursor.execute("DROP TABLE query_embedding_cache CASCADE CONSTRAINTS")
                logger.info("✅ Dropped existing table")
            except Exception:
                logger.info("ℹ️ Table doesn't exist yet, creating new one...")
            
            logger.info("🔧 Creating QUERY_EMBEDDING_CACHE table with Oracle 23ai in-memory features...")
            
            # Create table with in-memory optimization
            # Note: Only one INMEMORY clause allowed - combining all settings
            # UNIQUE constraint on query_text auto-creates an index, so we don't create a separate one
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
                INMEMORY PRIORITY HIGH MEMCOMPRESS FOR QUERY LOW
            """)
            
            # Create index on last_used_at for cache cleanup queries
            cursor.execute("""
                CREATE INDEX idx_qcache_last_used ON query_embedding_cache(last_used_at)
            """)
            
            conn.commit()
            logger.info("✅ QUERY_EMBEDDING_CACHE table created successfully!")
            logger.info("   - Oracle 23ai In-Memory enabled with HIGH priority")
            logger.info("   - Memory compression: QUERY LOW (optimized for fast queries)")
            logger.info("   - Columns: query_text (UNIQUE), embedding_vector, model_name, usage_count")
            logger.info("   - Indexes: auto-created on query_text (from UNIQUE), idx_qcache_last_used")
            logger.info("   📊 In-Memory features will provide sub-millisecond cache lookups!")
            
    except Exception as e:
        logger.error(f"❌ Failed to create table: {e}")
        logger.info("   ℹ️ If in-memory features are not available, the table will still work without them")
        # Try creating without in-memory if it fails
        try:
            logger.info("   🔄 Retrying without in-memory features...")
            with get_flask_safe_connection() as conn:
                cursor = conn.cursor()
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
                cursor.execute("CREATE INDEX idx_qcache_last_used ON query_embedding_cache(last_used_at)")
                conn.commit()
                logger.info("✅ Table created successfully (without in-memory features)")
        except Exception as e2:
            logger.error(f"❌ Failed to create table even without in-memory: {e2}")
            raise

if __name__ == '__main__':
    create_query_cache_table()
