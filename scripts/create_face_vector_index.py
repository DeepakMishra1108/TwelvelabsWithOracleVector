#!/usr/bin/env python3
"""
Create vector index on face_tags.face_embedding column
This dramatically improves face recognition performance
"""

import sys
import os

# Add both possible paths
sys.path.insert(0, '/home/dataguardian/TwelvelabsWithOracleVector/src')
sys.path.insert(0, '/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src')

try:
    from utils.db_utils_flask_safe import get_flask_safe_connection
except ImportError:
    # Try alternative import path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from utils.db_utils_flask_safe import get_flask_safe_connection

def create_vector_index():
    """Create vector index on face_embedding column"""
    try:
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if index exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM user_indexes 
                WHERE index_name = 'IDX_FACE_EMBEDDING_VECTOR'
            """)
            
            index_exists = cursor.fetchone()[0] > 0
            
            if index_exists:
                print("ℹ️  Vector index already exists on face_tags.face_embedding")
                return True
            
            print("🔄 Creating vector index on face_tags.face_embedding...")
            print("   This may take a few minutes with 965 embeddings...")
            
            # Create vector index
            cursor.execute("""
                CREATE VECTOR INDEX idx_face_embedding_vector 
                ON face_tags(face_embedding)
                ORGANIZATION NEIGHBOR PARTITIONS
                WITH DISTANCE COSINE
                WITH TARGET ACCURACY 95
            """)
            
            conn.commit()
            
            print("✅ Vector index created successfully!")
            print("🔄 Gathering index statistics...")
            
            # Gather statistics
            cursor.execute("""
                BEGIN
                    DBMS_STATS.GATHER_INDEX_STATS(
                        ownname => USER,
                        indname => 'IDX_FACE_EMBEDDING_VECTOR',
                        estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE
                    );
                END;
            """)
            
            conn.commit()
            
            print("✅ Index statistics gathered")
            
            # Show index details
            cursor.execute("""
                SELECT 
                    index_name,
                    index_type,
                    status,
                    tablespace_name
                FROM user_indexes
                WHERE index_name = 'IDX_FACE_EMBEDDING_VECTOR'
            """)
            
            row = cursor.fetchone()
            if row:
                print(f"\n📊 Index Details:")
                print(f"   Name: {row[0]}")
                print(f"   Type: {row[1]}")
                print(f"   Status: {row[2]}")
                print(f"   Tablespace: {row[3]}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error creating vector index: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Face Embedding Vector Index Creation")
    print("=" * 60)
    
    success = create_vector_index()
    
    if success:
        print("\n✅ Face recognition queries will now be much faster!")
        print("   The index enables Oracle to quickly find similar faces")
        print("   without loading all 965 embeddings into memory.")
    else:
        print("\n❌ Failed to create vector index")
        sys.exit(1)
