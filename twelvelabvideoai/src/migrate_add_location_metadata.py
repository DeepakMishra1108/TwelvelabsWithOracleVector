#!/usr/bin/env python3
"""
Database migration script to add GPS and location metadata columns to album_media table
Adds support for: latitude, longitude, altitude, city, state, country, capture date, camera info
"""
import os
import sys
import logging
from dotenv import load_dotenv

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_migration():
    """Add GPS and location metadata columns to album_media table"""
    try:
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        logger.info("🔄 Starting database migration: Add GPS and location metadata columns")
        
        with get_flask_safe_connection() as conn:
            cursor = conn.cursor()
            
            # Check if columns already exist
            check_columns_sql = """
            SELECT column_name 
            FROM user_tab_columns 
            WHERE table_name = 'ALBUM_MEDIA' 
            AND column_name IN ('LATITUDE', 'LONGITUDE', 'GPS_ALTITUDE', 'CITY', 'COUNTRY', 
                               'CAPTURE_DATE', 'CAMERA_MAKE', 'CAMERA_MODEL')
            """
            
            cursor.execute(check_columns_sql)
            existing_columns = {row[0] for row in cursor.fetchall()}
            
            if existing_columns:
                logger.warning(f"⚠️ Some columns already exist: {existing_columns}")
                logger.info("Skipping existing columns and adding only missing ones...")
            
            # Add GPS coordinates columns
            if 'LATITUDE' not in existing_columns:
                logger.info("Adding LATITUDE column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD latitude NUMBER(10, 7)
                """)
                logger.info("✅ LATITUDE column added")
            
            if 'LONGITUDE' not in existing_columns:
                logger.info("Adding LONGITUDE column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD longitude NUMBER(10, 7)
                """)
                logger.info("✅ LONGITUDE column added")
            
            if 'GPS_ALTITUDE' not in existing_columns:
                logger.info("Adding GPS_ALTITUDE column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD gps_altitude NUMBER(10, 2)
                """)
                logger.info("✅ GPS_ALTITUDE column added")
            
            # Add location information columns
            if 'CITY' not in existing_columns:
                logger.info("Adding CITY column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD city VARCHAR2(200)
                """)
                logger.info("✅ CITY column added")
            
            if 'STATE' not in existing_columns:
                logger.info("Adding STATE column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD state VARCHAR2(200)
                """)
                logger.info("✅ STATE column added")
            
            if 'COUNTRY' not in existing_columns:
                logger.info("Adding COUNTRY column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD country VARCHAR2(200)
                """)
                logger.info("✅ COUNTRY column added")
            
            if 'COUNTRY_CODE' not in existing_columns:
                logger.info("Adding COUNTRY_CODE column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD country_code VARCHAR2(10)
                """)
                logger.info("✅ COUNTRY_CODE column added")
            
            # Add capture date and camera information
            if 'CAPTURE_DATE' not in existing_columns:
                logger.info("Adding CAPTURE_DATE column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD capture_date TIMESTAMP
                """)
                logger.info("✅ CAPTURE_DATE column added")
            
            if 'CAMERA_MAKE' not in existing_columns:
                logger.info("Adding CAMERA_MAKE column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD camera_make VARCHAR2(200)
                """)
                logger.info("✅ CAMERA_MAKE column added")
            
            if 'CAMERA_MODEL' not in existing_columns:
                logger.info("Adding CAMERA_MODEL column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD camera_model VARCHAR2(200)
                """)
                logger.info("✅ CAMERA_MODEL column added")
            
            # Add image orientation
            if 'ORIENTATION' not in existing_columns:
                logger.info("Adding ORIENTATION column...")
                cursor.execute("""
                    ALTER TABLE album_media 
                    ADD orientation NUMBER
                """)
                logger.info("✅ ORIENTATION column added")
            
            # Commit changes
            conn.commit()
            
            logger.info("✅ Migration completed successfully!")
            logger.info("📊 New columns added to album_media table:")
            logger.info("   - latitude, longitude, gps_altitude (GPS coordinates)")
            logger.info("   - city, state, country, country_code (location)")
            logger.info("   - capture_date, camera_make, camera_model (metadata)")
            logger.info("   - orientation (image orientation)")
            
            # Show updated table structure
            cursor.execute("""
                SELECT column_name, data_type, data_length, nullable 
                FROM user_tab_columns 
                WHERE table_name = 'ALBUM_MEDIA' 
                ORDER BY column_id
            """)
            
            logger.info("\n📋 Updated table structure:")
            for row in cursor.fetchall():
                col_name, data_type, data_len, nullable = row
                logger.info(f"   {col_name:30} {data_type:20} {'NULL' if nullable == 'Y' else 'NOT NULL'}")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise

if __name__ == '__main__':
    try:
        run_migration()
        print("\n✅ Database migration completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
