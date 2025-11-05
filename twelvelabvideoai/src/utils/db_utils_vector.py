#!/usr/bin/env python3
"""Enhanced database utilities for Oracle DB with VECTOR support and SAFE connection management

CRITICAL: This module now includes timeout protection to prevent shell crashes
"""
import os
import logging
import signal
import sys
import struct
import numpy as np
from dotenv import load_dotenv
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple
import threading
import time

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseTimeout(Exception):
    """Custom exception for database timeouts"""
    pass

def timeout_handler(signum, frame):
    """Handle timeout signal to prevent hanging"""
    raise DatabaseTimeout("Database operation timed out")

# Database configuration from environment
DB_CONFIG = {
    'user': os.getenv('ORACLE_DB_USERNAME'),
    'password': os.getenv('ORACLE_DB_PASSWORD'),
    'dsn': os.getenv('ORACLE_DB_CONNECT_STRING'),
    'config_dir': os.getenv('ORACLE_DB_WALLET_PATH'),
    'wallet_location': os.getenv('ORACLE_DB_WALLET_PATH'),
    'wallet_password': os.getenv('ORACLE_DB_WALLET_PASSWORD')
}

# DISABLED: Connection pools cause hanging - use direct connections only
_connection_pool = None
_pool_lock = threading.Lock()


def validate_db_config():
    """Validate that all required database configuration is present"""
    required_keys = ['user', 'password', 'dsn', 'wallet_location', 'wallet_password']
    missing = [key for key in required_keys if not DB_CONFIG.get(key)]
    
    if missing:
        raise ValueError(f"Missing required database configuration: {missing}")
    
    return True


def create_connection_pool():
    """Create and return a new Oracle connection pool with timeout protection"""
    global _connection_pool
    
    with _pool_lock:
        if _connection_pool is not None:
            return _connection_pool
            
        try:
            validate_db_config()
            
            # Add connection timeout to prevent hanging
            import signal
            
            def timeout_handler(signum, frame):
                raise Exception("Connection pool creation timed out")
            
            # Set 15 second timeout for pool creation
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(15)
            
            try:
                # Set shorter timeouts to prevent hanging
                _connection_pool = oracledb.create_pool(
                    user=DB_CONFIG['user'],
                    password=DB_CONFIG['password'],
                    dsn=DB_CONFIG['dsn'],
                    config_dir=DB_CONFIG['config_dir'],
                    wallet_location=DB_CONFIG['wallet_location'],
                    wallet_password=DB_CONFIG['wallet_password'],
                    min=1,  # Reduced min connections
                    max=3,  # Reduced max connections  
                    increment=1,
                    getmode=POOL_CONFIG['getmode'],
                    timeout=5,  # Shorter timeout
                    wait_timeout=3,  # Shorter wait
                    max_lifetime_session=1800  # Shorter lifetime
                )
                
                logger.info(f"Created Oracle connection pool: min=1, max=3")
                return _connection_pool
                
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            _connection_pool = None
            # Don't raise, fall back to direct connections
            return None


def get_db_connection(timeout=10):
    """SAFE database connection without pools - direct connection only
    
    Args:
        timeout (int): Connection timeout in seconds
        
    Returns:
        oracledb.Connection: Direct database connection
        
    Raises:
        DatabaseTimeout: If connection times out
        Exception: If connection fails
    """
    import oracledb
    old_handler = None
    
    try:
        validate_db_config()
        
        # Set connection timeout to prevent hanging
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        logger.debug("🔍 Creating SAFE direct database connection...")
        
        connection = oracledb.connect(
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            dsn=DB_CONFIG['dsn'],
            config_dir=DB_CONFIG['config_dir'],
            wallet_location=DB_CONFIG['wallet_location'],
            wallet_password=DB_CONFIG['wallet_password']
        )
        
        # Cancel alarm - connection successful
        signal.alarm(0)
        
        logger.debug("✅ SAFE direct database connection created")
        return connection
            
    except DatabaseTimeout:
        logger.error("❌ Direct database connection timed out!")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create direct connection: {e}")
        raise
    finally:
        # Always cancel alarm
        if old_handler:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


def get_direct_connection():
    """Get a direct database connection with timeout protection (fallback)
    
    Returns:
        oracledb.Connection: Direct database connection
    """
    import signal
    
    def timeout_handler(signum, frame):
        raise Exception("Direct connection timed out")
    
    try:
        validate_db_config()
        
        # Set connection timeout to prevent hanging
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10 second timeout
        
        try:
            connection = oracledb.connect(
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                dsn=DB_CONFIG['dsn'],
                config_dir=DB_CONFIG['config_dir'],
                wallet_location=DB_CONFIG['wallet_location'],
                wallet_password=DB_CONFIG['wallet_password']
            )
            
            logger.debug("Created direct database connection")
            return connection
            
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        
    except Exception as e:
        logger.error(f"Failed to create direct connection: {e}")
        raise


@contextmanager
def get_connection(timeout=10):
    """
    SAFE database connection with timeout protection - prevents shell crashes
    
    Args:
        timeout (int): Connection timeout in seconds
        
    Yields:
        oracledb.Connection: Database connection
        
    Raises:
        DatabaseTimeout: If connection times out
        Exception: If connection fails
    """
    connection = None
    old_handler = None
    
    try:
        # Import oracledb with timeout protection
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        import oracledb
        
        logger.info("🔍 Attempting SAFE database connection...")
        
        # Validate config
        validate_db_config()
        
        # Create direct connection (NO POOLS - they cause hangs)
        connection = oracledb.connect(
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            dsn=DB_CONFIG['dsn'],
            config_dir=DB_CONFIG['config_dir'],
            wallet_location=DB_CONFIG['wallet_location'],
            wallet_password=DB_CONFIG['wallet_password']
        )
        
        # Cancel alarm - connection successful
        signal.alarm(0)
        
        logger.info("✅ SAFE database connection established")
        yield connection
        
    except DatabaseTimeout:
        logger.error("❌ Database connection timed out!")
        if connection:
            try:
                connection.close()
            except:
                pass
        raise
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        if connection:
            try:
                connection.close()
            except:
                pass
        raise
    finally:
        # Always cancel alarm
        signal.alarm(0)
        
        # Close connection
        if connection:
            try:
                connection.close()
                logger.debug("🔒 Database connection closed")
            except Exception as e:
                logger.debug(f"Error closing connection: {e}")


# CONNECTION POOL FUNCTIONS REMOVED - THEY CAUSED SYSTEM HANGS
# All database connections now use SAFE direct connections with timeout protection


def test_db_connectivity(timeout=5):
    """Test database connectivity without hanging
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        import signal
        
        # Set alarm to prevent hanging
        def timeout_handler(signum, frame):
            raise TimeoutError("Database connection timeout")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 'Connected' FROM DUAL")
                result = cursor.fetchone()
                cursor.close()
                signal.alarm(0)  # Cancel alarm
                return result is not None
                
        except TimeoutError:
            logger.error("Database connection timed out")
            return False
        finally:
            signal.alarm(0)  # Ensure alarm is cancelled
            
    except Exception as e:
        logger.error(f"Database connectivity test failed: {e}")
        return False


# Oracle VECTOR utilities
def create_vector_from_list(embedding_list: List[float], dimension: int = None) -> str:
    """Convert a Python list to Oracle VECTOR format
    
    Args:
        embedding_list: List of float values
        dimension: Optional dimension specification
        
    Returns:
        str: Oracle VECTOR literal string
    """
    if dimension is None:
        dimension = len(embedding_list)
    
    # Format as Oracle VECTOR literal
    vector_str = '[' + ','.join(f'{val:.6f}' for val in embedding_list) + ']'
    return vector_str


def vector_similarity_search(connection, table: str, query_vector: List[float], 
                           top_k: int = 10, similarity_type: str = 'COSINE',
                           additional_filters: str = None) -> List[Dict]:
    """Perform vector similarity search using Oracle VECTOR functions
    
    Args:
        connection: Database connection
        table: Table name (video_embeddings or photo_embeddings)
        query_vector: Query embedding as list of floats
        top_k: Number of top results to return
        similarity_type: 'COSINE', 'DOT', or 'EUCLIDEAN'
        additional_filters: Optional WHERE clause filters
        
    Returns:
        List[Dict]: Search results with similarity scores
    """
    try:
        cursor = connection.cursor()
        
        # Create Oracle VECTOR from query
        query_vector_str = create_vector_from_list(query_vector)
        
        # Build query based on table type
        if table == 'video_embeddings':
            base_query = """
                SELECT video_file, start_time, end_time,
                       VECTOR_DISTANCE(embedding_vector, :query_vector, {similarity_type}) as similarity_score
                FROM video_embeddings
            """
        elif table == 'photo_embeddings':
            base_query = """
                SELECT id, album_name, photo_file,
                       VECTOR_DISTANCE(embedding_vector, :query_vector, {similarity_type}) as similarity_score
                FROM photo_embeddings
            """
        else:
            raise ValueError(f"Unknown table: {table}")
        
        # Add filters if provided
        if additional_filters:
            base_query += f" WHERE {additional_filters}"
        
        # Add ordering and limit
        base_query += f"""
            ORDER BY similarity_score ASC
            FETCH FIRST {top_k} ROWS ONLY
        """
        
        # Format query with similarity type
        query = base_query.format(similarity_type=similarity_type)
        
        # Execute query
        cursor.execute(query, {'query_vector': query_vector_str})
        results = cursor.fetchall()
        
        # Format results
        formatted_results = []
        for row in results:
            if table == 'video_embeddings':
                formatted_results.append({
                    'video_file': row[0],
                    'start_time': row[1],
                    'end_time': row[2],
                    'similarity_score': float(row[3])
                })
            else:  # photo_embeddings
                formatted_results.append({
                    'id': row[0],
                    'album_name': row[1],
                    'photo_file': row[2],
                    'similarity_score': float(row[3])
                })
        
        cursor.close()
        return formatted_results
        
    except Exception as e:
        logger.error(f"Vector similarity search failed: {e}")
        raise


def insert_vector_embedding(connection, table: str, embedding_data: Dict[str, Any]) -> bool:
    """Insert embedding data with Oracle VECTOR type
    
    Args:
        connection: Database connection
        table: Target table name
        embedding_data: Dictionary containing embedding data
        
    Returns:
        bool: Success status
    """
    try:
        cursor = connection.cursor()
        
        if table == 'video_embeddings':
            query = """
                INSERT INTO video_embeddings 
                (video_file, start_time, end_time, embedding_vector) 
                VALUES (:video_file, :start_time, :end_time, :embedding_vector)
            """
            # Convert embedding list to VECTOR format
            vector_str = create_vector_from_list(embedding_data['embedding_vector'])
            params = {
                'video_file': embedding_data['video_file'],
                'start_time': embedding_data['start_time'],
                'end_time': embedding_data['end_time'],
                'embedding_vector': vector_str
            }
            
        elif table == 'photo_embeddings':
            query = """
                INSERT INTO photo_embeddings 
                (album_name, photo_file, embedding_vector) 
                VALUES (:album_name, :photo_file, :embedding_vector)
            """
            # Convert embedding list to VECTOR format
            vector_str = create_vector_from_list(embedding_data['embedding_vector'])
            params = {
                'album_name': embedding_data['album_name'],
                'photo_file': embedding_data['photo_file'],
                'embedding_vector': vector_str
            }
        else:
            raise ValueError(f"Unknown table: {table}")
        
        cursor.execute(query, params)
        connection.commit()
        cursor.close()
        
        logger.debug(f"Inserted vector embedding into {table}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to insert vector embedding: {e}")
        connection.rollback()
        return False


def batch_insert_vector_embeddings(connection, table: str, embeddings_list: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Batch insert multiple vector embeddings
    
    Args:
        connection: Database connection
        table: Target table name
        embeddings_list: List of embedding data dictionaries
        
    Returns:
        Tuple[int, int]: (success_count, failed_count)
    """
    success_count = 0
    failed_count = 0
    
    try:
        cursor = connection.cursor()
        
        if table == 'video_embeddings':
            query = """
                INSERT INTO video_embeddings 
                (video_file, start_time, end_time, embedding_vector) 
                VALUES (:video_file, :start_time, :end_time, :embedding_vector)
            """
        elif table == 'photo_embeddings':
            query = """
                INSERT INTO photo_embeddings 
                (album_name, photo_file, embedding_vector) 
                VALUES (:album_name, :photo_file, :embedding_vector)
            """
        else:
            raise ValueError(f"Unknown table: {table}")
        
        # Prepare batch data
        batch_data = []
        for embedding_data in embeddings_list:
            try:
                vector_str = create_vector_from_list(embedding_data['embedding_vector'])
                
                if table == 'video_embeddings':
                    params = {
                        'video_file': embedding_data['video_file'],
                        'start_time': embedding_data['start_time'],
                        'end_time': embedding_data['end_time'],
                        'embedding_vector': vector_str
                    }
                else:  # photo_embeddings
                    params = {
                        'album_name': embedding_data['album_name'],
                        'photo_file': embedding_data['photo_file'],
                        'embedding_vector': vector_str
                    }
                
                batch_data.append(params)
                
            except Exception as e:
                logger.error(f"Failed to prepare embedding data: {e}")
                failed_count += 1
        
        # Execute batch insert
        if batch_data:
            cursor.executemany(query, batch_data)
            connection.commit()
            success_count = len(batch_data)
            
        cursor.close()
        logger.info(f"Batch inserted {success_count} embeddings, {failed_count} failed")
        
    except Exception as e:
        logger.error(f"Batch insert failed: {e}")
        connection.rollback()
        failed_count = len(embeddings_list)
    
    return success_count, failed_count


def get_health_status() -> Dict[str, Any]:
    """Get database connection health status
    
    Returns:
        Dict: Health status information
    """
    status = {
        'database': 'unknown',
        'pool_status': 'unknown',
        'active_connections': 0,
        'config_valid': False
    }
    
    try:
        # Check configuration
        validate_db_config()
        status['config_valid'] = True
        
        # Check pool status
        if _connection_pool:
            status['pool_status'] = 'active'
            status['active_connections'] = _connection_pool.opened
        else:
            status['pool_status'] = 'not_created'
        
        # Test connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            result = cursor.fetchone()
            if result:
                status['database'] = 'healthy'
            cursor.close()
            
    except Exception as e:
        status['database'] = f'error: {str(e)}'
        logger.error(f"Health check failed: {e}")
    
    return status


# Migration utilities for BLOB to VECTOR conversion
def migrate_blob_to_vector(connection, table: str, batch_size: int = 1000) -> Dict[str, int]:
    """Migrate existing BLOB embeddings to VECTOR format
    
    Args:
        connection: Database connection
        table: Table name to migrate
        batch_size: Number of records to process per batch
        
    Returns:
        Dict: Migration statistics
    """
    stats = {'migrated': 0, 'failed': 0, 'total': 0}
    
    try:
        cursor = connection.cursor()
        
        # Count total records
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        stats['total'] = cursor.fetchone()[0]
        
        if stats['total'] == 0:
            logger.info(f"No records to migrate in {table}")
            return stats
        
        # Process in batches
        offset = 0
        while offset < stats['total']:
            try:
                # Fetch batch
                if table == 'video_embeddings':
                    query = """
                        SELECT id, video_file, start_time, end_time, embedding_vector
                        FROM video_embeddings
                        ORDER BY id
                        OFFSET :offset ROWS FETCH NEXT :batch_size ROWS ONLY
                    """
                else:  # photo_embeddings
                    query = """
                        SELECT id, album_name, photo_file, embedding_vector
                        FROM photo_embeddings
                        ORDER BY id
                        OFFSET :offset ROWS FETCH NEXT :batch_size ROWS ONLY
                    """
                
                cursor.execute(query, {'offset': offset, 'batch_size': batch_size})
                rows = cursor.fetchall()
                
                if not rows:
                    break
                
                # Process each row
                for row in rows:
                    try:
                        # Extract BLOB embedding
                        blob_data = row[-1]  # Last column is embedding_vector
                        if blob_data:
                            # Convert BLOB to float array
                            embedding_bytes = blob_data.read() if hasattr(blob_data, 'read') else bytes(blob_data)
                            num_floats = len(embedding_bytes) // 4
                            embedding_array = list(struct.unpack(f'{num_floats}f', embedding_bytes))
                            
                            # Convert to VECTOR format
                            vector_str = create_vector_from_list(embedding_array)
                            
                            # Update record
                            update_query = f"UPDATE {table} SET embedding_vector = :vector WHERE id = :id"
                            cursor.execute(update_query, {'vector': vector_str, 'id': row[0]})
                            
                            stats['migrated'] += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate record {row[0]}: {e}")
                        stats['failed'] += 1
                
                # Commit batch
                connection.commit()
                offset += batch_size
                
                logger.info(f"Migrated batch: {offset}/{stats['total']} records")
                
            except Exception as e:
                logger.error(f"Batch migration failed at offset {offset}: {e}")
                connection.rollback()
                break
        
        cursor.close()
        logger.info(f"Migration completed: {stats['migrated']} migrated, {stats['failed']} failed")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        
    return stats