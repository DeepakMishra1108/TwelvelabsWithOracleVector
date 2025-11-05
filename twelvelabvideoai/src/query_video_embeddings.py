import os
import sys
import array
import time
import oracledb
import math
from twelvelabs import TwelveLabs
from twelvelabs.types import VideoSegment
from twelvelabs.embed import TasksStatusResponse
from dotenv import load_dotenv
import oci
from utils.db_utils import get_db_connection

load_dotenv()
# Environment variables
db_username = os.getenv("ORACLE_DB_USERNAME")
db_password = os.getenv("ORACLE_DB_PASSWORD")
db_connect_string = os.getenv("ORACLE_DB_CONNECT_STRING")
db_wallet_path = os.getenv("ORACLE_DB_WALLET_PATH")
db_wallet_pw = os.getenv("ORACLE_DB_WALLET_PASSWORD")
twelvelabs_api_key = os.getenv("TWELVE_LABS_API_KEY")

# Constants
EMBEDDING_MODEL = "Marengo-retrieval-2.7"
SEGMENT_DURATION = 6  # seconds per segment
TOP_K = 5  # number of results to return in similarity search

# Initialize Twelve Labs client
twelvelabs_client = TwelveLabs(api_key=twelvelabs_api_key)

def similarity_search(connection, query_text):
    """Perform similarity search using query text"""
    try:
        # Create embedding for query
        embedding = twelvelabs_client.embed.create(
            model_name=EMBEDDING_MODEL,
            text=query_text,
            text_truncate="start",
        )

        if len(embedding.text_embedding.segments) > 1:
            print(f"Warning: Query generated {len(embedding.text_embedding.segments)} segments. Using only the first segment.")

        # Use float32 for storage compatibility with store_video_embeddings
        qlist = embedding.text_embedding.segments[0].float_
        # convert to array of floats (float32)
        qvec = array.array('f', qlist)

        # Fetch all embeddings and compute cosine similarity client-side to avoid binding large arrays in SQL
        results = []
        cursor = connection.cursor()
        cursor.execute("SELECT video_file, start_time, end_time, embedding_vector FROM video_embeddings")
        for row in cursor:
            vf, st, et, blob = row[0], row[1], row[2], row[3]
            try:
                # blob is stored as raw bytes of float32 array
                if blob is None:
                    continue
                if isinstance(blob, memoryview):
                    b = blob.tobytes()
                else:
                    b = bytes(blob)
                arr = array.array('f')
                arr.frombytes(b)
                # compute cosine similarity
                if len(arr) != len(qvec):
                    # If dimensions mismatch, compute over the common prefix length instead
                    min_len = min(len(arr), len(qvec))
                    if min_len == 0:
                        # nothing to compare
                        continue
                    arr_view = arr[:min_len]
                    q_view = qvec[:min_len]
                    print(f"Dimension mismatch: stored={len(arr)} query={len(qvec)} — using first {min_len} elements")
                else:
                    arr_view = arr
                    q_view = qvec
                # dot and norms
                dot = 0.0
                qnorm = 0.0
                vnorm = 0.0
                for a, bval in zip(q_view, arr_view):
                    dot += float(a) * float(bval)
                    qnorm += float(a) * float(a)
                    vnorm += float(bval) * float(bval)
                if qnorm == 0 or vnorm == 0:
                    continue
                cos = dot / (math.sqrt(qnorm) * math.sqrt(vnorm))
                results.append((cos, {'video_file': vf, 'start_time': st, 'end_time': et}))
            except Exception:
                continue
        cursor.close()
        # sort by highest cosine similarity
        results.sort(key=lambda x: x[0], reverse=True)
        top = [r[1] for r in results[:TOP_K]]
        return top
        
    except oracledb.DatabaseError as e:
        print(f"Database error occurred: {str(e)}")
        # Re-raise the exception to be handled by the calling function
        raise
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise


def similarity_search_multiple(connection, query_texts, batch_size=1000, top_k=5):
    """Perform multiple similarity searches using a list of query texts in batches"""
    results_by_query = {}
    
    # Process queries in batches
    for i in range(0, len(query_texts), batch_size):
        batch_queries = query_texts[i:i + batch_size]
        print(f"\nProcessing batch {i//batch_size + 1} ({len(batch_queries)} queries)")
        
        # Create embeddings for batch queries and perform client-side similarity search
        embeddings = []
        for query_text in batch_queries:
            embedding = twelvelabs_client.embed.create(
                model_name=EMBEDDING_MODEL,
                text=query_text,
                text_truncate="start",
            )

            if len(embedding.text_embedding.segments) > 1:
                print(f"Warning: Query '{query_text}' generated {len(embedding.text_embedding.segments)} segments. Using only the first segment.")

            qvec = array.array('f', embedding.text_embedding.segments[0].float_)
            embeddings.append((query_text, qvec))

        # Fetch all stored embeddings once
        with connection.cursor() as cursor:
            cursor.execute("SELECT video_file, start_time, end_time, embedding_vector FROM video_embeddings")
            stored = []
            for row in cursor:
                vf, st, et, blob = row[0], row[1], row[2], row[3]
                try:
                    if blob is None:
                        continue
                    b = bytes(blob) if not isinstance(blob, memoryview) else blob.tobytes()
                    arr = array.array('f')
                    arr.frombytes(b)
                    stored.append((vf, st, et, arr))
                except Exception:
                    continue

        # For each query, compute top-K by cosine similarity
        for query_text, qvec in embeddings:
            results = []
            for vf, st, et, arr in stored:
                if len(arr) != len(qvec):
                    min_len = min(len(arr), len(qvec))
                    if min_len == 0:
                        continue
                    arr_view = arr[:min_len]
                    q_view = qvec[:min_len]
                    print(f"Dimension mismatch: stored={len(arr)} query={len(qvec)} — using first {min_len} elements")
                else:
                    arr_view = arr
                    q_view = qvec
                dot = 0.0; qnorm = 0.0; vnorm = 0.0
                for a, bval in zip(q_view, arr_view):
                    dot += float(a) * float(bval)
                    qnorm += float(a) * float(a)
                    vnorm += float(bval) * float(bval)
                if qnorm == 0 or vnorm == 0:
                    continue
                cos = dot / (math.sqrt(qnorm) * math.sqrt(vnorm))
                results.append((cos, {'video_file': vf, 'start_time': st, 'end_time': et}))
            results.sort(key=lambda x: x[0], reverse=True)
            results_by_query[query_text] = [r[1] for r in results[:top_k]]
    
    return results_by_query

def query_video_embeddings(query_text):
    """Query video embeddings database with the given text"""
    try:
        connection = get_db_connection()
        
        # Verify DB version
        db_version = tuple(int(s) for s in connection.version.split("."))[:2]
        if db_version < (23, 7):
            sys.exit("This example requires Oracle Database 23.7 or later")
        print("Connected to Oracle Database")
        
        print("\nSearching for relevant video segments...")
        results = similarity_search(connection, query_text)
        
        print("\nResults:")
        print("========")
        for r in results:
            #print(f"Video: {r['video_file']}")
            print(f"Segment: {r['start_time']:.1f}s to {r['end_time']:.1f}s\n")
                
    finally:
        if 'connection' in locals():
            connection.close()
    
    return results

def query_video_embeddings_multiple(query_texts, top_k=5):
    """Query video embeddings database with multiple text queries"""
    try:
        connection = get_db_connection()
        connection.autocommit = True
        
        print("connected to Oracle Database")

        # Verify DB version
        db_version = tuple(int(s) for s in connection.version.split("."))[:2]
        if db_version < (23, 7):
            sys.exit("This example requires Oracle Database 23.7 or later")
        print("Connected to Oracle Database")
        
        print("\nSearching for relevant video segments...")
        results_by_query = similarity_search_multiple(connection, query_texts, top_k=top_k)
        
        print("\nResults:")
        print("========")
        for query_text, results in results_by_query.items():
            print(f"\nQuery: '{query_text}'")
            print("-" * (len(query_text) + 9))
            for r in results:
                #print(f"Video: {r['video_file']}")
                print(f"Segment: {r['start_time']:.1f}s to {r['end_time']:.1f}s\n")
                
    finally:
        if 'connection' in locals():
            connection.close()
    
    return results_by_query

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python query_video_embeddings.py 'query1' 'query2' ...")
        sys.exit(1)
    print("Loded ENV - ", db_username, db_password, db_connect_string, db_wallet_path,twelvelabs_api_key)



    #if not twelvelabs_client.api_key:
    #    print('\nYou need to set your TWELVE_LABS_API_KEY\n')
    #    print('https://playground.twelvelabs.io/dashboard/api-key')
    #    print('export TWELVE_LABS_API_KEY=your_api_key_value\n')
    #    exit()

    queries = sys.argv[1:]
    query_video_embeddings_multiple(queries)