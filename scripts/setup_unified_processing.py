#!/usr/bin/env python3
"""
Add required columns for unified photo processing:
1. rich_metadata CLOB - for GPT-4o-mini metadata
2. face_embedding VECTOR(512) - for DeepFace embeddings in face_tags table
"""
import sys
import oracledb

def add_required_columns():
    """Add columns needed for unified photo processing"""
    conn = None
    try:
        # Connect to database using Oracle Cloud wallet
        wallet_path = '/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet'
        
        conn = oracledb.connect(
            user='TELCOVIDEOENCODE',
            password='!Q2w3e4r5t6y',
            dsn='ocdmrealtime_high',
            config_dir=wallet_path,
            wallet_location=wallet_path,
            wallet_password='!Q2w3e4r5t'
        )
        
        cursor = conn.cursor()
        
        print("="*60)
        print("Adding columns for unified photo processing...")
        print("="*60)
        
        # 1. Add rich_metadata to album_media
        print("\n1. Adding rich_metadata column to album_media...")
        try:
            cursor.execute("""
                ALTER TABLE album_media ADD (
                    rich_metadata CLOB CHECK (rich_metadata IS JSON)
                )
            """)
            print("   ✅ Added rich_metadata column")
        except Exception as e:
            if "ORA-01430" in str(e):
                print("   ⚠️  Column already exists")
            else:
                print(f"   ❌ Error: {e}")
        
        # 2. Add face_embedding to face_tags
        print("\n2. Adding face_embedding column to face_tags...")
        try:
            cursor.execute("""
                ALTER TABLE face_tags ADD (
                    face_embedding VECTOR(512)
                )
            """)
            print("   ✅ Added face_embedding column")
        except Exception as e:
            if "ORA-01430" in str(e):
                print("   ⚠️  Column already exists")
            else:
                print(f"   ❌ Error: {e}")
        
        # 3. Create indexes for faster searches
        print("\n3. Creating indexes...")
        
        # Index on face_embedding for vector search
        try:
            cursor.execute("""
                CREATE INDEX idx_face_embedding ON face_tags(face_embedding)
            """)
            print("   ✅ Created index on face_embedding")
        except Exception as e:
            if "ORA-00955" in str(e):
                print("   ⚠️  Index already exists")
            else:
                print(f"   ❌ Error: {e}")
        
        # Verify columns exist
        print("\n4. Verifying columns...")
        
        cursor.execute("""
            SELECT column_name, data_type 
            FROM user_tab_columns 
            WHERE table_name = 'ALBUM_MEDIA' 
            AND column_name = 'RICH_METADATA'
        """)
        if cursor.fetchone():
            print("   ✅ album_media.rich_metadata verified")
        else:
            print("   ❌ album_media.rich_metadata NOT FOUND")
        
        cursor.execute("""
            SELECT column_name, data_type 
            FROM user_tab_columns 
            WHERE table_name = 'FACE_TAGS' 
            AND column_name = 'FACE_EMBEDDING'
        """)
        if cursor.fetchone():
            print("   ✅ face_tags.face_embedding verified")
        else:
            print("   ❌ face_tags.face_embedding NOT FOUND")
        
        conn.commit()
        cursor.close()
        
        print("\n" + "="*60)
        print("✅ Database schema updated successfully!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Database update failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = add_required_columns()
    sys.exit(0 if success else 1)
