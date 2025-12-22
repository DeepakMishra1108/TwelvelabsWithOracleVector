#!/usr/bin/env python3
"""
Add rich_metadata column to album_media table
"""
import sys
import os
import oracledb

def add_rich_metadata_column():
    """Add rich_metadata CLOB column to album_media table"""
    conn = None
    try:
        # Connect to database
        conn = oracledb.connect(
            user='telcovideoencode',
            password='Srihari@24',
            dsn='150.136.65.73:1522/FREEPDB1'
        )
        cursor = conn.cursor()
        
        print("Adding rich_metadata column to album_media table...")
        
        # Add column
        try:
            cursor.execute("""
                ALTER TABLE album_media ADD (
                    rich_metadata CLOB CHECK (rich_metadata IS JSON)
                )
            """)
            print("✅ Added rich_metadata column")
        except Exception as e:
            if "ORA-01430" in str(e):
                print("⚠️  Column already exists")
            else:
                raise
        
        # Verify column exists
        cursor.execute("""
            SELECT column_name, data_type 
            FROM user_tab_columns 
            WHERE table_name = 'ALBUM_MEDIA' 
            AND column_name = 'RICH_METADATA'
        """)
        result = cursor.fetchone()
        
        if result:
            print(f"✅ Verified: {result[0]} ({result[1]})")
        else:
            print("❌ Column not found after addition")
            return False
        
        conn.commit()
        cursor.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = add_rich_metadata_column()
    sys.exit(0 if success else 1)
