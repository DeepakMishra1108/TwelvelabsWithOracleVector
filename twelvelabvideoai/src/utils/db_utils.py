#!/usr/bin/env python3
"""Enhanced database utilities for Oracle DB with VECTOR support and connection pooling

This module provides centralized database connection management, connection pooling,
and Oracle VECTOR operations for improved search performance and accuracy.
"""
import os
import logging
import oracledb
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List, Tuple
import struct
import threading
import time
from contextlib import contextmanager

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration from environment
DB_CONFIG = {
    'user': os.getenv('ORACLE_DB_USERNAME'),
    'password': os.getenv('ORACLE_DB_PASSWORD'),
    'dsn': os.getenv('ORACLE_DB_CONNECT_STRING'),
    'config_dir': os.getenv('ORACLE_DB_WALLET_PATH'),
    'wallet_location': os.getenv('ORACLE_DB_WALLET_PATH'),
    'wallet_password': os.getenv('ORACLE_DB_WALLET_PASSWORD')
}

# Connection pool configuration
POOL_CONFIG = {
    'min': int(os.getenv('DB_POOL_MIN', '2')),
    'max': int(os.getenv('DB_POOL_MAX', '10')),
    'increment': int(os.getenv('DB_POOL_INCREMENT', '1')),
    'getmode': oracledb.POOL_GETMODE_WAIT,
    'timeout': int(os.getenv('DB_POOL_TIMEOUT', '30'))
}

# Global connection pool
_connection_pool = None
_pool_lock = threading.Lock()

import os
import oracledb
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Singleton class for managing Oracle database connections"""
    
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
        return cls._instance
    
    def get_connection(self) -> oracledb.Connection:
        """Get Oracle database connection using environment variables"""
        if self._connection is None or not self._connection.is_healthy():
            self._connection = self._create_connection()
        return self._connection
    
    def _create_connection(self) -> oracledb.Connection:
        """Create new Oracle database connection"""
        try:
            # Validate required environment variables
            required_vars = [
                'ORACLE_DB_USERNAME',
                'ORACLE_DB_PASSWORD', 
                'ORACLE_DB_CONNECT_STRING',
                'ORACLE_DB_WALLET_PATH',
                'ORACLE_DB_WALLET_PASSWORD'
            ]
            
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                raise ValueError(f"Missing required environment variables: {missing_vars}")
            
            connection = oracledb.connect(
                user=os.getenv('ORACLE_DB_USERNAME'),
                password=os.getenv('ORACLE_DB_PASSWORD'),
                dsn=os.getenv('ORACLE_DB_CONNECT_STRING'),
                config_dir=os.getenv('ORACLE_DB_WALLET_PATH'),
                wallet_location=os.getenv('ORACLE_DB_WALLET_PATH'),
                wallet_password=os.getenv('ORACLE_DB_WALLET_PASSWORD')
            )
            
            logger.info("Successfully connected to Oracle database")
            return connection
            
        except Exception as e:
            logger.error(f"Failed to connect to Oracle database: {e}")
            raise
    
    def close_connection(self):
        """Close the database connection"""
        if self._connection:
            try:
                self._connection.close()
                self._connection = None
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")

def get_db_connection() -> oracledb.Connection:
    """
    Get a database connection instance
    This is the main function that all other modules should use
    """
    db = DatabaseConnection()
    return db.get_connection()

def execute_query(query: str, params: Optional[tuple] = None, fetch_all: bool = True):
    """
    Execute a query and return results
    
    Args:
        query: SQL query to execute
        params: Optional parameters for the query
        fetch_all: If True, return all results. If False, return one result
    
    Returns:
        Query results or None
    """
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if query.strip().upper().startswith('SELECT'):
            if fetch_all:
                return cursor.fetchall()
            else:
                return cursor.fetchone()
        else:
            connection.commit()
            return cursor.rowcount
            
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        connection.rollback()
        raise
    finally:
        cursor.close()

def insert_embedding(table: str, embedding_data: dict) -> int:
    """
    Insert embedding data into specified table
    
    Args:
        table: Target table name (video_embeddings or photo_embeddings)
        embedding_data: Dictionary containing embedding data
    
    Returns:
        Number of rows inserted
    """
    if table == 'video_embeddings':
        query = """
        INSERT INTO video_embeddings 
        (video_file, start_time, end_time, embedding_vector) 
        VALUES (:video_file, :start_time, :end_time, :embedding_vector)
        """
    elif table == 'photo_embeddings':
        query = """
        INSERT INTO photo_embeddings 
        (photo_file, album_name, embedding_vector) 
        VALUES (:photo_file, :album_name, :embedding_vector)
        """
    else:
        raise ValueError(f"Unknown table: {table}")
    
    return execute_query(query, tuple(embedding_data.values()), fetch_all=False)

def test_connection():
    """Test database connection and return basic info"""
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Test query
        cursor.execute("SELECT 1 FROM DUAL")
        result = cursor.fetchone()
        
        # Get table counts
        cursor.execute("SELECT COUNT(*) FROM video_embeddings")
        video_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM photo_embeddings")
        photo_count = cursor.fetchone()[0]
        
        cursor.close()
        
        return {
            'status': 'success',
            'test_query': result[0],
            'video_embeddings_count': video_count,
            'photo_embeddings_count': photo_count
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

if __name__ == "__main__":
    # Test the connection when run directly
    print("Testing database connection...")
    result = test_connection()
    print(f"Connection test result: {result}")