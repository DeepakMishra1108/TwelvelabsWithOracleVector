#!/usr/bin/env python3
"""Check face_tags and add capability to update names"""

import oracledb
import sys
import os

# Load environment from .env file
env_file = '/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/.env'
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

def get_connection():
    """Get Oracle database connection"""
    conn = oracledb.connect(
        user=os.environ['ORACLE_DB_USERNAME'],
        password=os.environ['ORACLE_DB_PASSWORD'],
        dsn=os.environ['ORACLE_DB_CONNECT_STRING'],
        config_dir=os.environ.get('ORACLE_DB_WALLET_PATH', ''),
        wallet_location=os.environ.get('ORACLE_DB_WALLET_PATH', ''),
        wallet_password=os.environ.get('ORACLE_DB_WALLET_PASSWORD', '')
    )
    return conn

def check_face_tags():
    """Check all face tags"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, face_name FROM face_tags ORDER BY id")
        rows = cursor.fetchall()
        
        print(f"\n📊 Total face tags: {len(rows)}")
        print("=" * 50)
        
        unnamed_count = 0
        
        for row in rows:
            face_id = row[0]
            face_name = row[1] if row[1] else None
            
            if not row[1]:
                unnamed_count += 1
                name_display = "❌ UNKNOWN"
            else:
                name_display = f"✅ {face_name}"
            
            print(f"ID: {face_id:3d} | Name: {name_display}")
        
        print("=" * 50)
        print(f"📝 Summary:")
        print(f"   - Total: {len(rows)}")
        print(f"   - With names: {len(rows) - unnamed_count}")
        print(f"   - Without names (UNKNOWN): {unnamed_count}")
    finally:
        conn.close()

def update_face_tag_name(face_id, new_name):
    """Update name for a specific face tag"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Check if face tag exists
        cursor.execute("SELECT id, face_name FROM face_tags WHERE id = :id", {'id': face_id})
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ Face tag ID {face_id} not found")
            return False
        
        old_name = row[1] if row[1] else "UNKNOWN"
        
        # Update the name
        cursor.execute(
            "UPDATE face_tags SET face_name = :name WHERE id = :id",
            {'name': new_name, 'id': face_id}
        )
        conn.commit()
        
        print(f"✅ Updated face tag ID {face_id}")
        print(f"   Old name: {old_name}")
        print(f"   New name: {new_name}")
        return True
    except Exception as e:
        print(f"❌ Error updating face tag: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # No arguments - just check
        check_face_tags()
    elif len(sys.argv) == 3 and sys.argv[1] == 'update':
        # update <face_id> <name>
        try:
            face_id = int(sys.argv[2])
            print(f"\nEnter new name for face tag ID {face_id}:")
            new_name = input().strip()
            if new_name:
                update_face_tag_name(face_id, new_name)
            else:
                print("❌ Name cannot be empty")
        except ValueError:
            print("❌ Face ID must be a number")
            print("Usage: python check_face_tags.py update <face_id>")
    elif len(sys.argv) == 4 and sys.argv[1] == 'update':
        # update <face_id> <name>
        try:
            face_id = int(sys.argv[2])
            new_name = sys.argv[3]
            update_face_tag_name(face_id, new_name)
        except ValueError:
            print("❌ Face ID must be a number")
            print("Usage: python check_face_tags.py update <face_id> <name>")
    else:
        print("Usage:")
        print("  python check_face_tags.py                    # Check all face tags")
        print("  python check_face_tags.py update <face_id>   # Update face tag name (interactive)")
        print("  python check_face_tags.py update <face_id> <name>  # Update face tag name")
