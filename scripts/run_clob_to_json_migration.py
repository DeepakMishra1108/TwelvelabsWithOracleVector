#!/usr/bin/env python3
"""Migrate CLOB columns to native JSON type for better performance"""
import oracledb
import os
import sys

# Load environment variables
env_vars = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env_vars[key] = value.strip('"').strip("'")

# Get Oracle connection parameters (use actual env variable names)
user = env_vars.get("ORACLE_DB_USERNAME")
password = env_vars.get("ORACLE_DB_PASSWORD")
dsn = env_vars.get("ORACLE_DB_CONNECT_STRING")
wallet_location = env_vars.get("ORACLE_DB_WALLET_PATH")
wallet_password = env_vars.get("ORACLE_DB_WALLET_PASSWORD")

if not all([user, password, dsn, wallet_location, wallet_password]):
    print("✗ Missing required environment variables:")
    print(f"  ORACLE_DB_USERNAME: {'✓' if user else '✗'}")
    print(f"  ORACLE_DB_PASSWORD: {'✓' if password else '✗'}")
    print(f"  ORACLE_DB_CONNECT_STRING: {'✓' if dsn else '✗'}")
    print(f"  ORACLE_DB_WALLET_PATH: {'✓' if wallet_location else '✗'}")
    print(f"  ORACLE_DB_WALLET_PASSWORD: {'✓' if wallet_password else '✗'}")
    sys.exit(1)

print(f"✓ Using wallet from: {wallet_location}")

# Connect with wallet-based connection
conn = oracledb.connect(
    user=user,
    password=password,
    dsn=dsn,
    config_dir=wallet_location,
    wallet_location=wallet_location,
    wallet_password=wallet_password
)

cursor = conn.cursor()

print("=" * 60)
print("CLOB to JSON Migration")
print("=" * 60)

# Step 1: Migrate rich_metadata
print("\nStep 1: Migrating rich_metadata from CLOB to JSON...")
try:
    cursor.execute("ALTER TABLE album_media ADD rich_metadata_json JSON")
    print("  ✓ Added rich_metadata_json column")
except Exception as e:
    if "ORA-01430" in str(e) or "already exists" in str(e).lower():
        print("  ℹ Column already exists, continuing...")
    else:
        print(f"  ✗ Error adding column: {e}")
        sys.exit(1)

try:
    cursor.execute("""
        UPDATE album_media 
        SET rich_metadata_json = rich_metadata
        WHERE rich_metadata IS NOT NULL
    """)
    rows = cursor.rowcount
    conn.commit()
    print(f"  ✓ Copied {rows} rows to new column")
except Exception as e:
    print(f"  ✗ Error copying data: {e}")
    conn.rollback()
    sys.exit(1)

try:
    cursor.execute("ALTER TABLE album_media DROP COLUMN rich_metadata")
    print("  ✓ Dropped old CLOB column")
except Exception as e:
    print(f"  ✗ Error dropping column: {e}")
    sys.exit(1)

try:
    cursor.execute("ALTER TABLE album_media RENAME COLUMN rich_metadata_json TO rich_metadata")
    print("  ✓ Renamed column to rich_metadata")
except Exception as e:
    print(f"  ✗ Error renaming column: {e}")
    sys.exit(1)

# Step 2: Create JSON search index
print("\nStep 2: Creating JSON search index...")
try:
    cursor.execute("""
        CREATE SEARCH INDEX rich_metadata_search_idx 
        ON album_media (rich_metadata) 
        FOR JSON
    """)
    print("  ✓ Created JSON search index")
except Exception as e:
    if "ORA-01408" in str(e) or "already exists" in str(e).lower():
        print("  ℹ Index already exists")
    else:
        print(f"  ⚠ Index creation: {e}")
        print("  (This is optional, continuing...)")

# Step 3: Verify migration
print("\nStep 3: Verifying migration...")
cursor.execute("""
    SELECT data_type
    FROM user_tab_columns 
    WHERE table_name = 'ALBUM_MEDIA' AND column_name = 'RICH_METADATA'
""")
row = cursor.fetchone()
if row:
    data_type = row[0]
    print(f"  ✓ Column type: {data_type}")
    if data_type == "JSON":
        print("  ✓ Successfully migrated to native JSON type!")
    else:
        print(f"  ⚠ Warning: Column type is {data_type}, not JSON")
else:
    print("  ✗ Column not found!")
    sys.exit(1)

cursor.execute("SELECT COUNT(*) FROM album_media WHERE rich_metadata IS NOT NULL")
count = cursor.fetchone()[0]
print(f"  ✓ Rows with rich_metadata: {count}")

conn.close()

print("\n" + "=" * 60)
print("Migration completed successfully!")
print("=" * 60)
print("\nNext steps:")
print("1. Restart the application to use native JSON functions")
print("2. Monitor performance improvements")
print("3. Optional: Remove DBMS_LOB fallback from queries")
