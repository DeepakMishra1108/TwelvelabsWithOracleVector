#!/usr/bin/env python3
"""Flask-safe database utilities for Oracle DB with VECTOR support

This module replaces signal-based timeouts with threading-based timeouts
to work properly in Flask request threads.
"""
import os
import logging
import sys
import struct
import numpy as np
from dotenv import load_dotenv
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple
import threading
import time
import queue

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseTimeout(Exception):
    """Custom exception for database timeouts"""
    pass

# Database configuration from environment
DB_CONFIG = {
    'user': os.getenv('ORACLE_DB_USERNAME'),
    'password': os.getenv('ORACLE_DB_PASSWORD'),
    'dsn': os.getenv('ORACLE_DB_CONNECT_STRING'),
    'config_dir': os.getenv('ORACLE_DB_WALLET_PATH'),
    'wallet_location': os.getenv('ORACLE_DB_WALLET_PATH'),
    'wallet_password': os.getenv('ORACLE_DB_WALLET_PASSWORD')
}

def validate_db_config():
    """Validate that all required database configuration is present"""
    required_keys = ['user', 'password', 'dsn', 'wallet_location', 'wallet_password']
    missing = [key for key in required_keys if not DB_CONFIG.get(key)]
    
    if missing:
        raise ValueError(f"Missing required database configuration: {missing}")
    
    logger.debug("✅ Database configuration validated")
    return True

def _run_with_threading_timeout(func, timeout_seconds=30):
    """Run a function with threading-based timeout instead of signal-based"""
    result_queue = queue.Queue()
    error_queue = queue.Queue()
    
    def worker():
        try:
            result = func()
            result_queue.put(result)
        except Exception as e:
            error_queue.put(e)
    
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        logger.warning(f"Database operation timed out after {timeout_seconds} seconds")
        raise DatabaseTimeout(f"Operation timed out after {timeout_seconds} seconds")
    
    if not error_queue.empty():
        raise error_queue.get()
    
    if not result_queue.empty():
        return result_queue.get()
    
    return None

@contextmanager
def get_flask_safe_connection(timeout=15):
    """Flask-safe database connection with threading-based timeout"""
    connection = None
    try:
        logger.debug("🔄 Creating Flask-safe database connection...")
        
        def create_connection():
            import oracledb
            
            # Validate configuration
            validate_db_config()
            
            # Use thin mode (no Oracle Instant Client required)
            # Create connection with wallet in thin mode
            conn = oracledb.connect(
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                dsn=DB_CONFIG['dsn'],
                config_dir=DB_CONFIG['config_dir'],
                wallet_location=DB_CONFIG['wallet_location'],
                wallet_password=DB_CONFIG['wallet_password']
            )
            
            logger.debug("✅ Flask-safe database connection established (thin mode)")
            return conn
        
        # Create connection with threading timeout
        connection = _run_with_threading_timeout(create_connection, timeout)
        
        yield connection
        
    except DatabaseTimeout:
        logger.error("❌ Failed to create Flask-safe connection: timeout")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create Flask-safe connection: {e}")
        raise
    finally:
        if connection:
            try:
                connection.close()
                logger.debug("🔒 Flask-safe database connection closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing connection: {e}")

def flask_safe_execute_query(query, params=None, timeout=30):
    """Execute query with Flask-safe threading timeout"""
    try:
        def execute():
            with get_flask_safe_connection(timeout=timeout) as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                if query.strip().upper().startswith('SELECT'):
                    rows = cursor.fetchall()
                    
                    # Convert CLOBs to strings while connection is still open
                    converted_rows = []
                    for row in rows:
                        converted_row = []
                        for value in row:
                            if value is not None and hasattr(value, 'read'):
                                # This is a CLOB/BLOB - read it now
                                try:
                                    converted_row.append(value.read())
                                except:
                                    converted_row.append(None)
                            else:
                                converted_row.append(value)
                        converted_rows.append(tuple(converted_row))
                    
                    return converted_rows
                else:
                    conn.commit()
                    return cursor.rowcount
        
        return _run_with_threading_timeout(execute, timeout)
        
    except DatabaseTimeout:
        logger.error(f"❌ Query execution timed out after {timeout} seconds")
        raise
    except Exception as e:
        logger.error(f"❌ Query execution failed: {e}")
        raise

def flask_safe_insert_vector_data(table_name, data_dict, timeout=30):
    """Insert data with vector columns using Flask-safe connection"""
    try:
        def insert():
            with get_flask_safe_connection(timeout=timeout) as conn:
                cursor = conn.cursor()
                
                # Build insert query
                columns = list(data_dict.keys())
                placeholders = [':' + col for col in columns]
                
                query = f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                """
                
                # Convert numpy arrays to binary format for vector columns
                processed_data = {}
                for key, value in data_dict.items():
                    if isinstance(value, np.ndarray):
                        # Convert numpy array to Oracle VECTOR format
                        processed_data[key] = value.astype(np.float32).tobytes()
                    else:
                        processed_data[key] = value
                
                cursor.execute(query, processed_data)
                conn.commit()
                
                return cursor.rowcount
        
        return _run_with_threading_timeout(insert, timeout)
        
    except DatabaseTimeout:
        logger.error(f"❌ Vector insert timed out after {timeout} seconds")
        raise
    except Exception as e:
        logger.error(f"❌ Vector insert failed: {e}")
        raise

def flask_safe_vector_search(query_vector, table_name, vector_column, limit=10, timeout=30):
    """Perform vector similarity search using Flask-safe connection"""
    try:
        def search():
            with get_flask_safe_connection(timeout=timeout) as conn:
                cursor = conn.cursor()
                
                # Convert numpy array to binary if needed
                if isinstance(query_vector, np.ndarray):
                    vector_data = query_vector.astype(np.float32).tobytes()
                else:
                    vector_data = query_vector
                
                query = f"""
                SELECT *, VECTOR_DISTANCE({vector_column}, :query_vector) as distance
                FROM {table_name}
                ORDER BY VECTOR_DISTANCE({vector_column}, :query_vector)
                FETCH FIRST :limit ROWS ONLY
                """
                
                cursor.execute(query, {
                    'query_vector': vector_data,
                    'limit': limit
                })
                
                return cursor.fetchall()
        
        return _run_with_threading_timeout(search, timeout)
        
    except DatabaseTimeout:
        logger.error(f"❌ Vector search timed out after {timeout} seconds")
        raise
    except Exception as e:
        logger.error(f"❌ Vector search failed: {e}")
        raise

def test_flask_safe_connection():
    """Test Flask-safe database connection"""
    try:
        logger.info("🧪 Testing Flask-safe database connection...")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 'Hello from Flask-safe DB' as message FROM dual")
            result = cursor.fetchone()
            logger.info(f"✅ Flask-safe connection test successful: {result}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Flask-safe connection test failed: {e}")
        return False

if __name__ == "__main__":
    # Test the Flask-safe connection
    logging.basicConfig(level=logging.INFO)
    test_flask_safe_connection()