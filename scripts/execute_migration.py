#!/usr/bin/env python3
"""Execute Phase 4 Data Migration"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from twelvelabvideoai.src.utils.db_utils_flask_safe import get_flask_safe_connection

print("="*70)
print("🚀 Phase 4: Data Migration - Assigning Content to Admin User")
print("="*70)

ADMIN_USER_ID = 1

try:
    with get_flask_safe_connection() as conn:
        cursor = conn.cursor()
        
        # Step 1: Verify admin user
        print("\n1️⃣ Verifying admin user...")
        cursor.execute("SELECT id, username, role FROM users WHERE id = :user_id", {'user_id': ADMIN_USER_ID})
        user = cursor.fetchone()
        if not user:
            print(f"   ❌ Admin user (ID={ADMIN_USER_ID}) not found!")
            sys.exit(1)
        print(f"   ✅ Admin user: ID={user[0]}, Username={user[1]}, Role={user[2]}")
        
        # Step 2: Check orphaned content
        print("\n2️⃣ Checking orphaned content...")
        cursor.execute("SELECT COUNT(*) FROM album_media WHERE user_id IS NULL")
        album_media_nulls = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM query_embedding_cache WHERE user_id IS NULL")
        cache_nulls = cursor.fetchone()[0]
        
        print(f"   ALBUM_MEDIA: {album_media_nulls} records with NULL user_id")
        print(f"   QUERY_EMBEDDING_CACHE: {cache_nulls} records with NULL user_id")
        
        if album_media_nulls == 0 and cache_nulls == 0:
            print("\n   ✅ No orphaned content found!")
        else:
            # Show samples
            if album_media_nulls > 0:
                print("\n   Sample ALBUM_MEDIA records:")
                cursor.execute("""
                    SELECT id, album_name, created_at
                    FROM album_media 
                    WHERE user_id IS NULL 
                    AND ROWNUM <= 5
                """)
                for row in cursor.fetchall():
                    print(f"     - ID: {row[0]}, Album: {row[1]}, Created: {row[2]}")
            
            # Step 3: Confirm migration
            print(f"\n3️⃣ Ready to migrate {album_media_nulls + cache_nulls} records to user ID {ADMIN_USER_ID}")
            response = input("   Proceed with migration? (yes/no): ").strip().lower()
            
            if response != 'yes':
                print("\n   ❌ Migration cancelled by user")
                sys.exit(0)
            
            # Step 4: Execute migration
            print("\n4️⃣ Executing migration...")
            
            if album_media_nulls > 0:
                cursor.execute(
                    "UPDATE album_media SET user_id = :user_id WHERE user_id IS NULL",
                    {'user_id': ADMIN_USER_ID}
                )
                conn.commit()
                print(f"   ✅ Updated {cursor.rowcount} ALBUM_MEDIA records")
            
            if cache_nulls > 0:
                cursor.execute(
                    "UPDATE query_embedding_cache SET user_id = :user_id WHERE user_id IS NULL",
                    {'user_id': ADMIN_USER_ID}
                )
                conn.commit()
                print(f"   ✅ Updated {cursor.rowcount} QUERY_EMBEDDING_CACHE records")
        
        # Step 5: Apply NOT NULL constraints
        print("\n5️⃣ Applying NOT NULL constraints...")
        
        try:
            cursor.execute("ALTER TABLE album_media MODIFY user_id NUMBER NOT NULL")
            conn.commit()
            print("   ✅ ALBUM_MEDIA.user_id is now NOT NULL")
        except Exception as e:
            if "ORA-01451" in str(e) or "cannot modify" in str(e):
                print("   ℹ️  ALBUM_MEDIA.user_id is already NOT NULL")
            else:
                print(f"   ⚠️  Error modifying ALBUM_MEDIA: {e}")
        
        try:
            cursor.execute("ALTER TABLE query_embedding_cache MODIFY user_id NUMBER NOT NULL")
            conn.commit()
            print("   ✅ QUERY_EMBEDDING_CACHE.user_id is now NOT NULL")
        except Exception as e:
            if "ORA-01451" in str(e) or "cannot modify" in str(e):
                print("   ℹ️  QUERY_EMBEDDING_CACHE.user_id is already NOT NULL")
            else:
                print(f"   ⚠️  Error modifying QUERY_EMBEDDING_CACHE: {e}")
        
        # Step 6: Verify migration
        print("\n6️⃣ Verifying migration...")
        cursor.execute("SELECT COUNT(*) FROM album_media WHERE user_id IS NULL")
        remaining_nulls = cursor.fetchone()[0]
        
        if remaining_nulls == 0:
            print("   ✅ All ALBUM_MEDIA records have user_id")
        else:
            print(f"   ⚠️  Still {remaining_nulls} NULL user_id values in ALBUM_MEDIA")
        
        cursor.execute("SELECT COUNT(*) FROM query_embedding_cache WHERE user_id IS NULL")
        remaining_nulls = cursor.fetchone()[0]
        
        if remaining_nulls == 0:
            print("   ✅ All QUERY_EMBEDDING_CACHE records have user_id")
        else:
            print(f"   ⚠️  Still {remaining_nulls} NULL user_id values in QUERY_EMBEDDING_CACHE")
        
        # Show distribution
        print("\n📊 Content Distribution:")
        cursor.execute("""
            SELECT u.username, u.role, COUNT(am.id) as content_count
            FROM users u
            LEFT JOIN album_media am ON u.id = am.user_id
            GROUP BY u.username, u.role
            ORDER BY content_count DESC
        """)
        for row in cursor.fetchall():
            print(f"   {row[0]} ({row[1]}): {row[2]} items")
        
        print("\n" + "="*70)
        print("✅ Migration Complete!")
        print("="*70)
        print("\nNext steps:")
        print("1. Test content visibility as different users")
        print("2. Verify upload attribution works")
        print("3. Test delete ownership validation")
        print("4. Deploy to production server")
        
except Exception as e:
    print(f"\n❌ Error during migration: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
