#!/usr/bin/env python3
"""
Migrate Face Tags Schema: 512-dim → 1024-dim
Simple standalone script that uses oracledb directly
"""

import os
import oracledb
from dotenv import load_dotenv

# Load environment
env_path = '/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/.env'
load_dotenv(env_path)

username = os.getenv('ORACLE_DB_USERNAME')
password = os.getenv('ORACLE_DB_PASSWORD')
dsn = os.getenv('ORACLE_DB_CONNECT_STRING')
wallet_location = os.getenv('ORACLE_DB_WALLET_PATH')
wallet_password = os.getenv('ORACLE_DB_WALLET_PASSWORD')

print("=" * 80)
print("🚀 Face Tags Schema Migration: 512-dim → 1024-dim")
print("=" * 80)

# Ask for confirmation
print("\n⚠️  WARNING: This will DROP the face_embedding column and all data!")
print("   You will need to regenerate all face embeddings after this.")
response = input("\nContinue? (yes/no): ").strip().lower()

if response != 'yes':
    print("❌ Migration cancelled")
    exit(0)

# Connect to database
print("\n📡 Connecting to Oracle database...")
conn = oracledb.connect(
    user=username,
    password=password,
    dsn=dsn,
    config_dir=wallet_location,
    wallet_location=wallet_location,
    wallet_password=wallet_password
)

cursor = conn.cursor()

# Check current schema
print("\n📊 Checking current schema...")
cursor.execute("""
    SELECT column_name, data_type, data_length
    FROM user_tab_columns
    WHERE table_name = 'FACE_TAGS'
    AND column_name = 'FACE_EMBEDDING'
""")

result = cursor.fetchone()
if result:
    print(f"   Current: {result[0]} {result[1]} ({result[2]})")
else:
    print("   ❌ face_embedding column not found!")
    conn.close()
    exit(1)

# Drop and recreate column
print("\n🔄 Migrating face_embedding column to 1024 dimensions...")

print("   1️⃣  Dropping old column...")
cursor.execute("ALTER TABLE face_tags DROP COLUMN face_embedding")

print("   2️⃣  Adding new column (1024-dim)...")
cursor.execute("""
    ALTER TABLE face_tags 
    ADD face_embedding VECTOR(1024, FLOAT32)
""")

conn.commit()

# Verify
print("\n✅ Verifying new schema...")
cursor.execute("""
    SELECT column_name, data_type, data_length
    FROM user_tab_columns
    WHERE table_name = 'FACE_TAGS'
    AND column_name = 'FACE_EMBEDDING'
""")

result = cursor.fetchone()
if result:
    print(f"   New: {result[0]} {result[1]} ({result[2]})")

conn.close()

print("\n" + "=" * 80)
print("✅ Schema migration complete!")
print("⚠️  Note: All existing face embeddings have been cleared")
print("   Run regenerate_face_embeddings_twelvelabs.py to regenerate")
print("=" * 80)
