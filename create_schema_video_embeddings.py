import os
import oracledb
import argparse
import sys
import os
from dotenv import load_dotenv



def create_vector_index(cursor):
    cursor.execute("""
        CREATE VECTOR INDEX video_embeddings_idx
        ON video_embeddings(embedding_vector)
        ORGANIZATION NEIGHBOR PARTITIONS
        DISTANCE COSINE
        WITH TARGET ACCURACY 95
    """)

def drop_vector_index(cursor):
    """Drop the vector index if it exists"""
    print("\nDropping vector index...")
    cursor.execute("DROP INDEX video_embeddings_idx")
    print("Index dropped successfully")

def main():
    # Connect to Oracle Database
    load_dotenv()
    with oracledb.connect(
        user=db_username,
        password=db_password,
        dsn=db_connect_string,
        config_dir=db_wallet_path,
        wallet_location=db_wallet_path,
        wallet_password=db_wallet_pw
    ) as connection:

        with connection.cursor() as cursor:
            # Drop existing table if it exists
            try:
                print("dropping table: video_embeddings")
                cursor.execute("DROP TABLE video_embeddings")
            except oracledb.DatabaseError as e:
                if e.args[0].code != 942:  # ignore ORA-942: table does not exist
                    raise
    
            print("creating table: video_embeddings")
            # Create video_embeddings table
            cursor.execute("""
                CREATE TABLE video_embeddings (
                    id VARCHAR2(100) PRIMARY KEY,
                    video_file VARCHAR2(1000),
                    start_time NUMBER,
                    end_time NUMBER,
                    embedding_vector VECTOR(1024, float64)
                )
            """)

            print("creating vector index")
            create_vector_index(cursor)

if __name__ == "__main__":
    # Add command line argument parsing
    
    load_dotenv()
    # Environment variables
    db_username = os.getenv("ORACLE_DB_USERNAME")
    db_password = os.getenv("ORACLE_DB_PASSWORD")
    db_connect_string = os.getenv("ORACLE_DB_CONNECT_STRING")
    db_wallet_path = os.getenv("ORACLE_DB_WALLET_PATH")
    db_wallet_pw = os.getenv("ORACLE_DB_WALLET_PASSWORD")

    print("Loded ENV - ", db_username, db_password, db_connect_string, db_wallet_path)
    parser = argparse.ArgumentParser(description='Create video embeddings schema and index')

    args = parser.parse_args()
    main()

