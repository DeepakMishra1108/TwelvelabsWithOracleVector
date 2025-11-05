#!/usr/bin/env python3
"""Create Oracle DB schema for photo embeddings

This script creates the photo_embeddings table to store Marengo embeddings
for photos organized in albums.

Usage:
    python create_schema_photo_embeddings.py
"""
import os
import sys
from dotenv import load_dotenv
import oracledb

load_dotenv()


def create_photo_embeddings_table():
    """Create the photo_embeddings table if it doesn't exist"""
    
    # Connect to Oracle DB
    try:
        connection = oracledb.connect(
            user=os.getenv('ORACLE_DB_USERNAME'),
            password=os.getenv('ORACLE_DB_PASSWORD'),
            dsn=os.getenv('ORACLE_DB_CONNECT_STRING'),
            wallet_location=os.getenv('ORACLE_DB_WALLET_PATH'),
            wallet_password=os.getenv('ORACLE_DB_WALLET_PASSWORD')
        )
        print("Connected to Oracle Database")
    except Exception as e:
        print(f"Failed to connect to Oracle DB: {e}")
        sys.exit(1)

    cursor = connection.cursor()

    # Create table SQL
    create_table_sql = """
    CREATE TABLE photo_embeddings (
        id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        album_name VARCHAR2(500),
        photo_file VARCHAR2(2000),
        embedding_vector BLOB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    try:
        cursor.execute(create_table_sql)
        print("Table 'photo_embeddings' created successfully")
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        if error_obj.code == 955:  # ORA-00955: name is already used by an existing object
            print("Table 'photo_embeddings' already exists")
        else:
            print(f"Error creating table: {e}")
            cursor.close()
            connection.close()
            sys.exit(1)

    # Create index on album_name for faster queries
    create_index_sql = """
    CREATE INDEX idx_photo_album ON photo_embeddings(album_name)
    """
    
    try:
        cursor.execute(create_index_sql)
        print("Index 'idx_photo_album' created successfully")
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        if error_obj.code == 955:
            print("Index 'idx_photo_album' already exists")
        else:
            print(f"Warning: Could not create index: {e}")

    connection.commit()
    cursor.close()
    connection.close()
    print("Schema setup complete")


if __name__ == '__main__':
    create_photo_embeddings_table()
