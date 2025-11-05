#!/usr/bin/env python3
"""Database connectivity test script with timeout protection"""

import sys
import os
import signal
import logging

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def timeout_handler(signum, frame):
    """Handle timeout signal"""
    print("❌ Database connection timed out after 10 seconds")
    sys.exit(1)

def test_database():
    """Test database connectivity with timeout"""
    try:
        # Set 10 second timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)
        
        print("🔍 Testing database connectivity...")
        
        from utils.db_utils_vector import test_db_connectivity
        
        if test_db_connectivity(timeout=5):
            print("✅ Database connection successful")
            
            # Test a simple query
            from utils.db_utils_vector import get_connection
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM album_media")
                count = cursor.fetchone()[0]
                cursor.close()
                print(f"✅ Found {count} files in album_media table")
                
            signal.alarm(0)  # Cancel timeout
            return True
        else:
            print("❌ Database connection failed")
            signal.alarm(0)
            return False
            
    except Exception as e:
        signal.alarm(0)
        print(f"❌ Database test error: {e}")
        return False

if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)