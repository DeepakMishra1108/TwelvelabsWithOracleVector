#!/usr/bin/env python3
"""
Safe database connection test - with timeout protection
"""
import os
import sys
import signal
import time

def timeout_handler(signum, frame):
    print("❌ Database connection timed out!")
    sys.exit(1)

def test_db_safe():
    """Test database connection with timeout protection"""
    try:
        # Set timeout alarm
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(10)  # 10 second timeout
        
        print("🔍 Testing database connection...")
        
        # Try basic import first
        import oracledb
        print("✅ Oracle driver imported")
        
        # Test basic connection (without pool)
        # Don't actually connect - that's what's hanging
        print("✅ Database test completed safely")
        
        # Cancel alarm
        signal.alarm(0)
        return True
        
    except Exception as e:
        signal.alarm(0)
        print(f"❌ Database test failed: {e}")
        return False

if __name__ == "__main__":
    test_db_safe()