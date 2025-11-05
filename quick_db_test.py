#!/usr/bin/env python3
"""
Quick database connection test - SAFE VERSION
Tests the new timeout-protected database connections
"""

import sys
import os
import signal
import time

# Add src to path
sys.path.append('./twelvelabvideoai/src')

# Test our safe database connection
def test_safe_db():
    """Test the new safe database connection system"""
    
    print("🧪 Testing SAFE database connection...")
    print("🔍 This test has timeout protection to prevent shell hangs")
    
    try:
        from utils.db_utils_vector import get_connection, test_db_connectivity
        
        # Test 1: Basic connectivity test
        print("\n🔍 Test 1: Basic connectivity test...")
        is_connected = test_db_connectivity(timeout=10)
        print(f"   Result: {'✅ CONNECTED' if is_connected else '❌ FAILED'}")
        
        # Test 2: Direct connection context manager
        print("\n🔍 Test 2: Context manager connection...")
        try:
            with get_connection(timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 'Hello from Safe DB' as message FROM DUAL")
                result = cursor.fetchone()
                cursor.close()
                print(f"   Result: ✅ SUCCESS - {result[0] if result else 'No result'}")
        except Exception as e:
            print(f"   Result: ❌ FAILED - {e}")
        
        # Test 3: Multiple quick connections (stress test)
        print("\n🔍 Test 3: Multiple connection stress test...")
        success_count = 0
        for i in range(3):
            try:
                with get_connection(timeout=5) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM DUAL")
                    result = cursor.fetchone()
                    cursor.close()
                    if result:
                        success_count += 1
                print(f"   Connection {i+1}: ✅")
            except Exception as e:
                print(f"   Connection {i+1}: ❌ {e}")
        
        print(f"\n🎯 Stress test result: {success_count}/3 connections successful")
        
        print("\n🎉 Database connection test COMPLETED")
        print("✅ No shell hangs detected!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Set overall timeout for the entire test
    def overall_timeout(signum, frame):
        print("\n⏰ Overall test timeout reached")
        sys.exit(1)
    
    signal.signal(signal.SIGALRM, overall_timeout)
    signal.alarm(60)  # 1 minute max for entire test
    
    try:
        test_safe_db()
    finally:
        signal.alarm(0)  # Cancel timeout
        print("\n🏁 Test script finished")