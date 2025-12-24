#!/usr/bin/env python3
"""
Migrate AI_TAGS from CLOB to JSON column for better performance and compatibility
This aligns AI_TAGS with rich_metadata which is already JSON
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'twelvelabvideoai', 'src'))

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_ai_tags_to_json():
    """Migrate AI_TAGS from CLOB to JSON"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info("🔧 Migrating AI_TAGS from CLOB to JSON...")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check current column type
            cursor.execute("""
                SELECT data_type 
                FROM user_tab_columns 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND column_name = 'AI_TAGS'
            """)
            
            result = cursor.fetchone()
            if not result:
                logger.info("⚠️  AI_TAGS column does not exist")
                return False
            
            current_type = result[0]
            logger.info(f"📋 Current AI_TAGS type: {current_type}")
            
            if current_type == 'JSON':
                logger.info("✅ AI_TAGS is already JSON type")
                return True
            
            # Step 1: Create temporary JSON column
            logger.info("📝 Step 1: Creating temporary ai_tags_new JSON column...")
            try:
                cursor.execute("ALTER TABLE album_media ADD (ai_tags_new JSON)")
            except Exception as e:
                if 'ORA-01430' in str(e):  # Column already exists
                    logger.info("   Column ai_tags_new already exists, continuing...")
                else:
                    raise
            
            # Step 2: Convert plain text AI_TAGS to JSON format
            logger.info("📝 Step 2: Converting text tags to JSON format...")
            cursor.execute("""
                SELECT id, AI_TAGS 
                FROM album_media 
                WHERE AI_TAGS IS NOT NULL
            """)
            
            rows = cursor.fetchall()
            logger.info(f"   Found {len(rows)} records with AI_TAGS")
            
            converted = 0
            for row in rows:
                media_id = row[0]
                ai_tags_clob = row[1]
                
                # Convert CLOB to string
                if hasattr(ai_tags_clob, 'read'):
                    tags_text = ai_tags_clob.read()
                else:
                    tags_text = str(ai_tags_clob)
                
                # Convert text format to JSON
                import json
                tags_json = {
                    "raw_text": tags_text,
                    "generated_by": "auto_tag",
                    "version": "1.0"
                }
                
                # Parse structured tags if they exist
                if "TITLE:" in tags_text or "CATEGORIES:" in tags_text or "SUBJECTS:" in tags_text:
                    lines = tags_text.split('\n')
                    for line in lines:
                        if line.startswith('TITLE:'):
                            tags_json['title'] = line.replace('TITLE:', '').strip()
                        elif line.startswith('CATEGORIES:'):
                            cats = line.replace('CATEGORIES:', '').strip()
                            tags_json['categories'] = [c.strip() for c in cats.split(',')]
                        elif line.startswith('SUBJECTS:'):
                            subs = line.replace('SUBJECTS:', '').strip()
                            tags_json['subjects'] = [s.strip() for s in subs.split(',')]
                        elif line.startswith('HASHTAGS:'):
                            tags = line.replace('HASHTAGS:', '').strip()
                            tags_json['hashtags'] = [h.strip() for h in tags.split() if h.startswith('#')]
                        elif line.startswith('CONFIDENCE:'):
                            tags_json['confidence'] = line.replace('CONFIDENCE:', '').strip()
                
                # Update the new column
                cursor.execute("""
                    UPDATE album_media 
                    SET ai_tags_new = :json_data
                    WHERE id = :id
                """, {"json_data": json.dumps(tags_json), "id": media_id})
                
                converted += 1
                if converted % 100 == 0:
                    conn.commit()
                    logger.info(f"   Converted {converted}/{len(rows)} records...")
            
            conn.commit()
            logger.info(f"✅ Converted {converted} records to JSON")
            
            # Step 3: Drop old column and rename new one
            logger.info("📝 Step 3: Swapping columns...")
            cursor.execute("ALTER TABLE album_media DROP COLUMN AI_TAGS")
            cursor.execute("ALTER TABLE album_media RENAME COLUMN ai_tags_new TO AI_TAGS")
            
            conn.commit()
            logger.info("✅ Migration completed successfully!")
            
            # Verify
            cursor.execute("""
                SELECT data_type 
                FROM user_tab_columns 
                WHERE table_name = 'ALBUM_MEDIA' 
                AND column_name = 'AI_TAGS'
            """)
            
            new_type = cursor.fetchone()[0]
            logger.info(f"✅ Verified: AI_TAGS is now {new_type}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = migrate_ai_tags_to_json()
    sys.exit(0 if success else 1)
