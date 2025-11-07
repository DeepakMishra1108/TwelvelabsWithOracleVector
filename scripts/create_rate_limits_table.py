#!/usr/bin/env python3
"""
Create USER_RATE_LIMITS table for multi-tenant rate limiting.

This script creates tables to track and enforce per-user rate limits on:
- API calls per minute/hour/day
- File uploads per day
- Search queries per hour
- Video processing minutes per day

Usage:
    python scripts/create_rate_limits_table.py
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import oracledb

# Load environment variables
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_connection():
    """Get Oracle database connection."""
    wallet_path = os.getenv("ORACLE_DB_WALLET_PATH")
    return oracledb.connect(
        user=os.getenv("ORACLE_DB_USERNAME"),
        password=os.getenv("ORACLE_DB_PASSWORD"),
        dsn=os.getenv("ORACLE_DB_CONNECT_STRING"),
        config_dir=wallet_path,
        wallet_location=wallet_path,
        wallet_password=os.getenv("ORACLE_DB_WALLET_PASSWORD")
    )


def create_rate_limits_table():
    """Create USER_RATE_LIMITS table with per-user quotas and usage tracking."""
    
    create_table_sql = """
    CREATE TABLE user_rate_limits (
        id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id NUMBER NOT NULL,
        
        -- Quota limits (NULL = unlimited)
        max_uploads_per_day NUMBER DEFAULT 100,
        max_searches_per_hour NUMBER DEFAULT 1000,
        max_api_calls_per_minute NUMBER DEFAULT 60,
        max_video_processing_minutes_per_day NUMBER DEFAULT 60,
        max_storage_gb NUMBER DEFAULT 10,
        
        -- Current usage counters
        uploads_today NUMBER DEFAULT 0,
        searches_this_hour NUMBER DEFAULT 0,
        api_calls_this_minute NUMBER DEFAULT 0,
        video_minutes_today NUMBER DEFAULT 0,
        storage_used_gb NUMBER DEFAULT 0,
        
        -- Reset timestamps
        last_daily_reset TIMESTAMP DEFAULT SYSTIMESTAMP,
        last_hourly_reset TIMESTAMP DEFAULT SYSTIMESTAMP,
        last_minute_reset TIMESTAMP DEFAULT SYSTIMESTAMP,
        
        -- Metadata
        created_at TIMESTAMP DEFAULT SYSTIMESTAMP,
        updated_at TIMESTAMP DEFAULT SYSTIMESTAMP,
        
        -- Foreign key to users table
        CONSTRAINT fk_rate_limit_user FOREIGN KEY (user_id) 
            REFERENCES users(id) ON DELETE CASCADE,
        
        -- One rate limit record per user
        CONSTRAINT uk_user_rate_limit UNIQUE (user_id)
    )
    """
    
    create_index_sql = """
    CREATE INDEX idx_rate_limits_user_id ON user_rate_limits(user_id)
    """
    
    create_usage_log_table_sql = """
    CREATE TABLE user_usage_log (
        id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id NUMBER NOT NULL,
        action_type VARCHAR2(50) NOT NULL,
        action_details VARCHAR2(500),
        resource_consumed NUMBER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT SYSTIMESTAMP,
        ip_address VARCHAR2(45),
        
        CONSTRAINT fk_usage_log_user FOREIGN KEY (user_id) 
            REFERENCES users(id) ON DELETE CASCADE
    )
    """
    
    create_usage_log_index_sql = """
    CREATE INDEX idx_usage_log_user_time ON user_usage_log(user_id, timestamp)
    """
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT COUNT(*) FROM user_tables 
            WHERE table_name = 'USER_RATE_LIMITS'
        """)
        
        if cursor.fetchone()[0] > 0:
            logger.info("✅ USER_RATE_LIMITS table already exists")
        else:
            logger.info("Creating USER_RATE_LIMITS table...")
            cursor.execute(create_table_sql)
            logger.info("✅ USER_RATE_LIMITS table created")
            
            try:
                logger.info("Creating index on user_id...")
                cursor.execute(create_index_sql)
                logger.info("✅ Index created")
            except Exception as e:
                if "ORA-01408" in str(e):
                    logger.info("✅ Index already exists (auto-created)")
                else:
                    raise
        
        # Check usage log table
        cursor.execute("""
            SELECT COUNT(*) FROM user_tables 
            WHERE table_name = 'USER_USAGE_LOG'
        """)
        
        if cursor.fetchone()[0] > 0:
            logger.info("✅ USER_USAGE_LOG table already exists")
        else:
            logger.info("Creating USER_USAGE_LOG table...")
            cursor.execute(create_usage_log_table_sql)
            logger.info("✅ USER_USAGE_LOG table created")
            
            try:
                logger.info("Creating index on user_id and timestamp...")
                cursor.execute(create_usage_log_index_sql)
                logger.info("✅ Index created")
            except Exception as e:
                if "ORA-01408" in str(e):
                    logger.info("✅ Index already exists (auto-created)")
                else:
                    raise
        
        conn.commit()
        logger.info("✅ All rate limiting tables ready")
        
        # Initialize rate limits for existing users
        initialize_rate_limits_for_existing_users(cursor)
        conn.commit()
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating rate limits table: {e}")
        return False


def initialize_rate_limits_for_existing_users(cursor):
    """Create default rate limit records for users who don't have one."""
    
    logger.info("Checking for users without rate limits...")
    
    # Get users without rate limits
    cursor.execute("""
        SELECT u.id, u.role 
        FROM users u
        LEFT JOIN user_rate_limits r ON u.id = r.user_id
        WHERE r.id IS NULL
    """)
    
    users = cursor.fetchall()
    
    if not users:
        logger.info("✅ All users already have rate limits configured")
        return
    
    logger.info(f"Found {len(users)} users without rate limits. Initializing...")
    
    for user_id, role in users:
        # Set quotas based on role
        if role == 'admin':
            quotas = {
                'max_uploads_per_day': None,  # Unlimited
                'max_searches_per_hour': None,
                'max_api_calls_per_minute': None,
                'max_video_processing_minutes_per_day': None,
                'max_storage_gb': None
            }
        elif role == 'editor':
            quotas = {
                'max_uploads_per_day': 100,
                'max_searches_per_hour': 1000,
                'max_api_calls_per_minute': 60,
                'max_video_processing_minutes_per_day': 120,
                'max_storage_gb': 50
            }
        else:  # viewer
            quotas = {
                'max_uploads_per_day': 0,  # No uploads
                'max_searches_per_hour': 500,
                'max_api_calls_per_minute': 30,
                'max_video_processing_minutes_per_day': 0,
                'max_storage_gb': 0
            }
        
        cursor.execute("""
            INSERT INTO user_rate_limits (
                user_id, 
                max_uploads_per_day,
                max_searches_per_hour,
                max_api_calls_per_minute,
                max_video_processing_minutes_per_day,
                max_storage_gb
            ) VALUES (
                :user_id,
                :max_uploads_per_day,
                :max_searches_per_hour,
                :max_api_calls_per_minute,
                :max_video_processing_minutes_per_day,
                :max_storage_gb
            )
        """, {
            'user_id': user_id,
            **quotas
        })
        
        logger.info(f"  ✅ Initialized rate limits for user {user_id} (role: {role})")
    
    logger.info(f"✅ Initialized rate limits for {len(users)} users")


def display_current_limits():
    """Display current rate limits for all users."""
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.role,
                r.max_uploads_per_day,
                r.max_searches_per_hour,
                r.max_api_calls_per_minute,
                r.max_video_processing_minutes_per_day,
                r.max_storage_gb,
                r.uploads_today,
                r.searches_this_hour,
                r.api_calls_this_minute,
                r.video_minutes_today,
                r.storage_used_gb
            FROM users u
            LEFT JOIN user_rate_limits r ON u.id = r.user_id
            ORDER BY u.id
        """)
        
        users = cursor.fetchall()
        
        print("\n" + "="*100)
        print("CURRENT RATE LIMITS AND USAGE")
        print("="*100)
        print(f"{'User ID':<8} {'Username':<15} {'Role':<10} {'Uploads':<15} {'Searches':<15} {'API Calls':<15}")
        print("-"*100)
        
        for row in users:
            user_id, username, role, max_up, max_search, max_api, max_vid, max_storage, \
                up_today, search_hour, api_min, vid_today, storage = row
            
            uploads = f"{up_today or 0}/{max_up or '∞'}"
            searches = f"{search_hour or 0}/{max_search or '∞'}"
            api_calls = f"{api_min or 0}/{max_api or '∞'}"
            
            print(f"{user_id:<8} {username:<15} {role:<10} {uploads:<15} {searches:<15} {api_calls:<15}")
        
        print("="*100 + "\n")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error displaying limits: {e}")


if __name__ == "__main__":
    logger.info("🚀 Starting rate limits table creation...")
    
    success = create_rate_limits_table()
    
    if success:
        display_current_limits()
        logger.info("\n✅ Rate limiting setup complete!")
        logger.info("\nNext steps:")
        logger.info("1. Implement rate limiting middleware in Flask")
        logger.info("2. Add rate limit checks to upload/search/API routes")
        logger.info("3. Create admin UI to view and adjust user limits")
    else:
        logger.error("\n❌ Rate limiting setup failed")
        sys.exit(1)
