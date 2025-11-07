#!/usr/bin/env python3
"""Test database connection and albums"""
import sys
import os

sys.path.insert(0, '/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src')
from utils.db_utils_vector import get_db_connection

try:
    print("Testing database connection...")
    connection = get_db_connection()
    
    if connection:
        print("✅ Database connection successful")
        
        cursor = connection.cursor()
        
        # Test albums table
        cursor.execute("SELECT COUNT(*) FROM photo_albums")
        album_count = cursor.fetchone()[0]
        print(f"✅ Albums table accessible: {album_count} albums found")
        
        # List some albums
        cursor.execute("SELECT album_id, album_name FROM photo_albums WHERE ROWNUM <= 10 ORDER BY created_at DESC")
        albums = cursor.fetchall()
        print("\nRecent albums:")
        for album_id, album_name in albums:
            print(f"  - {album_name} (ID: {album_id})")
        
        cursor.close()
        connection.close()
    else:
        print("❌ Failed to get database connection")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
