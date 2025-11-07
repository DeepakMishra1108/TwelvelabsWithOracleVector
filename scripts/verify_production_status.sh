#!/bin/bash
# Verify production status: indexed videos, cache, embeddings
# Run this on the VM or from Mac with SSH

set -e

echo "=============================================="
echo "🔍 PRODUCTION STATUS VERIFICATION"
echo "=============================================="
echo ""

# Check if running on VM or need SSH
if [ -d "/home/dataguardian/TwelvelabsWithOracleVector" ]; then
    # Running on VM
    cd /home/dataguardian/TwelvelabsWithOracleVector
    VENV_PATH="./twelvelabvideoai/bin/activate"
else
    # Running from Mac, use SSH
    echo "📡 Connecting to VM..."
    ssh ubuntu@150.136.235.189 "bash -s" < "$0"
    exit 0
fi

# Activate virtual environment
source "$VENV_PATH"
cd /home/dataguardian/TwelvelabsWithOracleVector

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
fi

echo "=============================================="
echo "1️⃣  TWELVELABS INDEXES & VIDEOS"
echo "=============================================="
echo ""

python3 << 'PYEOF'
import os
from twelvelabs import TwelveLabs

try:
    client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
    
    indexes = list(client.index.list())
    print(f"📚 TwelveLabs Indexes: {len(indexes)}\n")
    
    total_videos = 0
    for idx in indexes:
        print(f"Index: {idx.name}")
        print(f"  ID: {idx.id}")
        
        try:
            videos = list(client.index.video.list(idx.id))
            total_videos += len(videos)
            print(f"  Videos: {len(videos)}")
            
            if videos:
                print(f"  Sample videos:")
                for v in videos[:5]:
                    filename = v.metadata.filename if v.metadata and hasattr(v.metadata, 'filename') and v.metadata.filename else v.id
                    duration = getattr(v.metadata, 'duration', 'N/A') if v.metadata else 'N/A'
                    print(f"    • {filename} (duration: {duration}s)")
                if len(videos) > 5:
                    print(f"    ... and {len(videos) - 5} more")
        except Exception as e:
            print(f"  ❌ Error listing videos: {e}")
        print()
    
    print(f"✅ Total videos indexed: {total_videos}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n⚠️  TwelveLabs API may be rate limited or credentials invalid")

PYEOF

echo ""
echo "=============================================="
echo "2️⃣  QUERY EMBEDDING CACHE"
echo "=============================================="
echo ""

python3 << 'PYEOF'
import os
import oracledb

try:
    conn = oracledb.connect(
        user=os.getenv("ORACLE_DB_USERNAME"),
        password=os.getenv("ORACLE_DB_PASSWORD"),
        dsn=os.getenv("ORACLE_DB_CONNECT_STRING"),
        config_dir=os.getenv("ORACLE_DB_WALLET_PATH")
    )
    
    cursor = conn.cursor()
    
    # Total cached queries
    cursor.execute("SELECT COUNT(*) FROM query_embedding_cache")
    total = cursor.fetchone()[0]
    print(f"💾 Total Cached Queries: {total}\n")
    
    if total > 0:
        # Most used queries
        cursor.execute("""
            SELECT 
                query_text, 
                usage_count, 
                last_used_at,
                CASE WHEN user_id IS NULL THEN 'Global' ELSE 'User ' || user_id END as scope
            FROM query_embedding_cache 
            ORDER BY usage_count DESC 
            FETCH FIRST 10 ROWS ONLY
        """)
        print("📊 Top 10 Cached Queries (by usage):\n")
        for i, row in enumerate(cursor, 1):
            print(f"  {i}. \"{row[0]}\"")
            print(f"     Hits: {row[1]} | Scope: {row[3]} | Last used: {row[2]}")
        
        # Cache statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_queries,
                SUM(usage_count) as total_hits,
                ROUND(AVG(usage_count), 2) as avg_hits_per_query,
                MAX(usage_count) as max_hits
            FROM query_embedding_cache
        """)
        stats = cursor.fetchone()
        print(f"\n📈 Cache Statistics:")
        print(f"  Total queries: {stats[0]}")
        print(f"  Total hits: {stats[1]}")
        print(f"  Avg hits/query: {stats[2]}")
        print(f"  Max hits (single query): {stats[3]}")
        
        # Calculate cache hit rate (queries with >1 usage)
        cursor.execute("""
            SELECT 
                COUNT(*) as cached_queries,
                (SELECT COUNT(*) FROM query_embedding_cache WHERE usage_count > 1) as hit_queries
            FROM query_embedding_cache
        """)
        hit_stats = cursor.fetchone()
        hit_rate = (hit_stats[1] / hit_stats[0] * 100) if hit_stats[0] > 0 else 0
        print(f"  Cache hit rate: {hit_rate:.1f}% ({hit_stats[1]} of {hit_stats[0]} queries reused)")
    else:
        print("⚠️  No queries cached yet. Cache will populate on first searches.")
    
    cursor.close()
    conn.close()
    print("\n✅ Query cache check complete")
    
except Exception as e:
    print(f"❌ Error: {e}")

PYEOF

echo ""
echo "=============================================="
echo "3️⃣  VIDEO EMBEDDINGS IN DATABASE"
echo "=============================================="
echo ""

python3 << 'PYEOF'
import os
import oracledb

try:
    conn = oracledb.connect(
        user=os.getenv("ORACLE_DB_USERNAME"),
        password=os.getenv("ORACLE_DB_PASSWORD"),
        dsn=os.getenv("ORACLE_DB_CONNECT_STRING"),
        config_dir=os.getenv("ORACLE_DB_WALLET_PATH")
    )
    
    cursor = conn.cursor()
    
    # Count video embeddings
    cursor.execute("SELECT COUNT(*) FROM video_embeddings")
    count = cursor.fetchone()[0]
    print(f"🎬 Total Video Embeddings: {count}\n")
    
    if count > 0:
        # Group by video
        cursor.execute("""
            SELECT 
                video_id, 
                video_title, 
                COUNT(*) as segment_count,
                MIN(start_time) as first_segment,
                MAX(end_time) as last_segment
            FROM video_embeddings
            GROUP BY video_id, video_title
            ORDER BY segment_count DESC
            FETCH FIRST 10 ROWS ONLY
        """)
        print("📹 Top 10 Videos (by segment count):\n")
        for i, row in enumerate(cursor, 1):
            print(f"  {i}. {row[1]}")
            print(f"     Video ID: {row[0]}")
            print(f"     Segments: {row[2]}")
            print(f"     Duration: {row[3]}s - {row[4]}s")
        
        # Total statistics
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT video_id) as unique_videos,
                COUNT(*) as total_segments,
                ROUND(AVG(segment_count), 2) as avg_segments_per_video
            FROM (
                SELECT video_id, COUNT(*) as segment_count
                FROM video_embeddings
                GROUP BY video_id
            )
        """)
        stats = cursor.fetchone()
        print(f"\n📊 Video Embedding Statistics:")
        print(f"  Unique videos: {stats[0]}")
        print(f"  Total segments: {stats[1]}")
        print(f"  Avg segments/video: {stats[2]}")
    else:
        print("⚠️  No video embeddings in database yet.")
        print("   Videos need to be indexed and embeddings stored.")
    
    cursor.close()
    conn.close()
    print("\n✅ Video embeddings check complete")
    
except Exception as e:
    print(f"❌ Error: {e}")

PYEOF

echo ""
echo "=============================================="
echo "4️⃣  API RATE LIMIT STATUS"
echo "=============================================="
echo ""

python3 << 'PYEOF'
import os
from twelvelabs import TwelveLabs
from datetime import datetime

try:
    client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
    
    # Try a lightweight API call to check rate limit headers
    try:
        indexes = list(client.index.list())
        print("✅ TwelveLabs API is accessible")
        print("   Rate limit status: OK (can make requests)")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "rate limit" in error_str.lower():
            print("❌ TwelveLabs API is rate limited")
            print(f"   Error: {e}")
            
            # Try to extract reset time
            if "after" in error_str:
                import re
                match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', error_str)
                if match:
                    reset_time = match.group(1)
                    print(f"   Reset time: {reset_time}")
        else:
            print(f"❌ TwelveLabs API error: {e}")
    
except Exception as e:
    print(f"❌ Error checking API: {e}")

PYEOF

echo ""
echo "=============================================="
echo "✅ VERIFICATION COMPLETE"
echo "=============================================="
echo ""
echo "📝 Summary saved to: /tmp/production_status.txt"

# Save summary
{
    echo "Production Status Check - $(date)"
    echo "======================================"
    echo ""
    echo "Run: $0"
    echo ""
} > /tmp/production_status.txt

echo "✅ Done!"
