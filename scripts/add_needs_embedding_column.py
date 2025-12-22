#!/usr/bin/env python3
"""Add needs_embedding column to face_tags table"""

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

print("Adding needs_embedding column to face_tags...")

conn = oracledb.connect(
    user=username,
    password=password,
    dsn=dsn,
    config_dir=wallet_location,
    wallet_location=wallet_location,
    wallet_password=wallet_password
)

cursor = conn.cursor()

try:
    # Add column if not exists
    cursor.execute("""
        ALTER TABLE face_tags ADD needs_embedding NUMBER(1) DEFAULT 1
    """)
    print("✅ Column added")
except Exception as e:
    if 'ORA-01430' in str(e):  # Column already exists
        print("ℹ️  Column already exists")
    else:
        raise

# Set needs_embedding=1 for faces without embeddings
cursor.execute("""
    UPDATE face_tags 
    SET needs_embedding = 1 
    WHERE face_embedding IS NULL
""")
rows = cursor.rowcount
print(f"✅ Marked {rows} faces as needing embeddings")

# Set needs_embedding=0 for faces with embeddings
cursor.execute("""
    UPDATE face_tags 
    SET needs_embedding = 0 
    WHERE face_embedding IS NOT NULL
""")
rows = cursor.rowcount
print(f"✅ Marked {rows} faces as having embeddings")

conn.commit()
conn.close()

print("✅ Done!")
