#!/usr/bin/env python3
"""Safe database utilities with timeout protection to prevent shell hangs"""
import os
import logging
import oracledb
from dotenv import load_dotenv
from contextlib import contextmanager
import signal
import time

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

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Database operation timed out")

def safe_db_connection(timeout=10):
    """Create a database connection with strict timeout protection
    
    Args:
        timeout: Maximum time to wait for connection (seconds)
        
    Returns:
        oracledb.Connection or None: Database connection or None if failed
    """
    connection = None
    
    # Set up timeout signal
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout)
    
    try:
        # Validate configuration
        required_keys = ['user', 'password', 'dsn', 'wallet_location', 'wallet_password']
        missing = [key for key in required_keys if not DB_CONFIG.get(key)]
        
        if missing:
            logger.error(f"Missing database configuration: {missing}")
            return None
        
        # Create connection with timeout protection
        connection = oracledb.connect(
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            dsn=DB_CONFIG['dsn'],
            config_dir=DB_CONFIG['config_dir'],
            wallet_location=DB_CONFIG['wallet_location'],
            wallet_password=DB_CONFIG['wallet_password']
        )
        
        # Test connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        cursor.fetchone()
        cursor.close()
        
        logger.info("✅ Database connection successful")
        return connection
        
    except TimeoutError:
        logger.error("❌ Database connection timed out")
        if connection:
            try:
                connection.close()
            except:
                pass
        return None
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        if connection:
            try:
                connection.close()
            except:
                pass
        return None
        
    finally:
        # Reset alarm
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

@contextmanager
def get_connection():
    """Safe context manager for database connections
    
    Yields:
        oracledb.Connection or None: Database connection
    """
    connection = None
    try:
        connection = safe_db_connection(timeout=10)
        if connection is None:
            raise Exception("Failed to establish database connection")
        yield connection
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if connection:
            try:
                connection.close()
                logger.debug("Database connection closed safely")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

def test_db_connection():
    """Test database connectivity safely without hanging"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM album_media")
            count = cursor.fetchone()[0]
            cursor.close()
            print(f"✅ Database test successful - Files in album_media: {count}")
            return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing database connection...")
    test_db_connection()