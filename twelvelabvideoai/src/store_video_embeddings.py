import os
import sys
import array
import time
import oracledb
from twelvelabs import TwelveLabs
from twelvelabs.types import VideoSegment
from twelvelabs.embed import TasksStatusResponse
from dotenv import load_dotenv
import oci
from utils.db_utils import get_db_connection
#from twelvelabs.models.embed import EmbeddingsTask
#from twelvelabs import Task
#from twelvelabs.embed import EmbeddingResponse, AudioEmbeddingResult

import json
# from create_schema_video_embeddings import create_vector_index, drop_vector_index
import argparse

load_dotenv()
 # Environment variables
db_username = os.getenv("ORACLE_DB_USERNAME")
db_password = os.getenv("ORACLE_DB_PASSWORD")
db_connect_string = os.getenv("ORACLE_DB_CONNECT_STRING")
db_wallet_path = os.getenv("ORACLE_DB_WALLET_PATH")
db_wallet_pw = os.getenv("ORACLE_DB_WALLET_PASSWORD")
twelvelabs_api_key = os.getenv("TWELVE_LABS_API_KEY")

# Constants
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'Marengo-retrieval-2.7')
SEGMENT_DURATION = int(os.getenv('SEGMENT_DURATION', '10'))
TOP_K = int(os.getenv('TOP_K', '5'))

# Initialize TwelveLabs client
twelvelabs_client = TwelveLabs(api_key=twelvelabs_api_key)


def on_task_update(task: TasksStatusResponse):
    print(f"  Status={task.status}")

def _get_par_url_for_oci_path(oci_path, ttl_seconds=3600):
    """Create a PREAUTH URL (PAR) for an oci:// namespace/bucket/object path and return the HTTP URL.

    Expects oci to be imported. Uses oci_config loader if available.
    """
    try:
        # resolve config
        try:
            from oci_config import load_oci_config
        except Exception:
            load_oci_config = None

        if load_oci_config:
            cfg = load_oci_config(oci)
        else:
            cfg = oci.config.from_file()

        obj_client = oci.object_storage.ObjectStorageClient(cfg)
        path = oci_path[len('oci://'):]
        parts = path.split('/', 2)
        if len(parts) == 2:
            namespace = obj_client.get_namespace().data
            bucket = parts[0]
            object_name = parts[1]
        elif len(parts) == 3:
            namespace = parts[0]
            bucket = parts[1]
            object_name = parts[2]
        else:
            raise ValueError('invalid oci path')

        expiry_ts = int(time.time()) + ttl_seconds
        time_expires = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(expiry_ts))
        par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name='playback-par',
            object_name=object_name,
            access_type=oci.object_storage.models.CreatePreauthenticatedRequestDetails.ACCESS_TYPE_OBJECT_READ,
            time_expires=time_expires
        )
        par = obj_client.create_preauthenticated_request(namespace, bucket, par_details)
        access_uri = getattr(par.data, 'access_uri', None) or getattr(par.data, 'accessUri', None)
        base_url = obj_client.base_client.endpoint
        if access_uri:
            return base_url.rstrip('/') + access_uri
        return None
    except Exception:
        return None


def create_video_embeddings(client, video_url, model_name=None, clip_length=None):
    """Create embeddings for a video URL using TwelveLabs.

    video_url: http(s) URL (for example a PAR URL) or public URL
    model_name: optional model override (e.g., 'Marengo-retrieval-2.7')
    clip_length: optional clip length in seconds
    """
    model = model_name or EMBEDDING_MODEL
    clip = clip_length or SEGMENT_DURATION
    print(f"Creating embeddings for video URL: {video_url} using model={model} clip_length={clip}")
    task = client.embed.tasks.create(
        model_name=model,
        video_url=video_url,
        video_clip_length=clip
    )
    print(f"Created video embedding task: id={task.id} model_name={EMBEDDING_MODEL}")
    status = client.embed.tasks.wait_for_done(sleep_interval=5, task_id=task.id, callback=on_task_update)
    print(f"Embedding done: {status.status}")
    task = client.embed.tasks.retrieve(task_id=task.id, embedding_option=["visual-text", "audio"])
    return task.id

def store_embeddings_in_db(connection, task_id, video_file, tw_client=None):
    """Store video embeddings in Oracle DB.

    tw_client: optional TwelveLabs client used to retrieve the task; will be
    created from env if not provided.
    """
    if tw_client is None:
        tw_client = twelvelabs_client
    task = tw_client.embed.tasks.retrieve(task_id)

    # Get embeddings from the task
    if not task.video_embedding or not task.video_embedding.segments:
        print("No embeddings found")
        return
def store_embeddings_in_db(connection, task_id, video_file, tw_client=None):
    """Store video embeddings in Oracle DB.

    tw_client: optional TwelveLabs client used to retrieve the task; will be
    created from env if not provided.
    """
    if tw_client is None:
        tw_client = TwelveLabs(api_key=twelvelabs_api_key)
    task = tw_client.embed.tasks.retrieve(task_id)

    # Get embeddings from the task
    if not task.video_embedding or not task.video_embedding.segments:
        print("No embeddings found")
        return
    
    insert_sql = """
    INSERT INTO video_embeddings (
        id, video_file, start_time, end_time, embedding_vector
    ) VALUES (
        :1, :2, :3, :4, :5
    )"""
    
    # We'll build rows and insert in chunks, but avoid exceeding Oracle's bind limit (65535)
    MAX_BINDS = 65535
    data_batch = []

    with connection.cursor() as cursor:
        for idx, segment in enumerate(task.video_embedding.segments):
            id = f"{task_id}_{idx}"
            # vector: array of floats. Serialize to bytes and bind as a single BLOB to avoid expanding into many binds
            vector = array.array("f", segment.float_)
            try:
                vector_bytes = vector.tobytes()
                vector_bind = oracledb.Binary(vector_bytes)
            except Exception:
                # fallback: try to convert to a bytes string via repr
                vector_bind = str(list(vector)).encode('utf-8')

            print("Passed the embedding float")
            data_batch.append([
                id,
                video_file,
                segment.start_offset_sec,
                segment.end_offset_sec,
                vector_bind
            ])

            # Periodically flush in a way that respects Oracle's bind variable limit.
            # Estimate binds per row: 4 simple columns + the vector length (if array.array binds individual elements)
            if len(data_batch) >= 100:  # check periodically
                # vector is now bound as a single BLOB, so binds per row = 5
                binds_per_row = 5
                max_rows = max(1, MAX_BINDS // binds_per_row)
                # If current batch exceeds allowable rows, flush in safe-sized chunks
                if len(data_batch) >= max_rows:
                    to_insert = data_batch[:max_rows]
                    try:
                        cursor.executemany(insert_sql, to_insert)
                        connection.commit()
                    except Exception:
                        # Fall back to single-row inserts to be safe
                        for row in to_insert:
                            try:
                                cursor.execute(insert_sql, row)
                            except Exception:
                                print('Failed single-row insert')
                        connection.commit()
                    data_batch = data_batch[max_rows:]

        # Insert any remaining rows in safe-sized chunks
        while data_batch:
            # binds per row is 5 (id,video_file,start,end,blob)
            binds_per_row = 5
            max_rows = max(1, MAX_BINDS // binds_per_row)
            to_insert = data_batch[:max_rows]
            try:
                cursor.executemany(insert_sql, to_insert)
                connection.commit()
            except Exception:
                for row in to_insert:
                    try:
                        cursor.execute(insert_sql, row)
                    except Exception:
                        print('Failed single-row insert during final flush')
                connection.commit()
            data_batch = data_batch[max_rows:]

    print(f"Stored {len(task.video_embedding.segments)} embeddings in database")

def load_task_ids():
    """Load existing task IDs from JSON file"""
    try:
        with open('video_task_ids.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_task_ids(task_ids):
    """Save task IDs to JSON file"""
    with open('video_task_ids.json', 'w') as f:
        json.dump(task_ids, f, indent=2)

def read_all_objects_from_bucket(bucket_name, prefix=None):
    try:
        from oci_config import load_oci_config
    except Exception:
        load_oci_config = None

    if load_oci_config:
        config = load_oci_config(oci)
    else:
        config = oci.config.from_file()

    object_storage_client = oci.object_storage.ObjectStorageClient(config)
    namespace = object_storage_client.get_namespace().data

    # List objects in the bucket
    list_objects_response = object_storage_client.list_objects(namespace, bucket_name, prefix=prefix)
    objects = list_objects_response.data.objects

    for obj in objects:
        object_name = obj.name
        print(f"Reading object: {object_name}")
        response = object_storage_client.get_object(namespace, bucket_name, object_name)
        data = response.data.content  # bytes
        # Process data as needed
        print(data)  # or save/process

# Example usage:
# read_all_objects_from_bucket('your_bucket_name')
def process_video(connection, video_path):
    """Process a single video file"""
    print(f"\nProcessing video: {video_path}")
    
    # Load existing task IDs
    task_ids = load_task_ids()
    
    # If video was already processed, use existing task_id to store embeddings
    if video_path in task_ids:
        task_id = task_ids[video_path]
        print(f"Video previously processed with task_id: {task_id}")
        print("Re-storing embeddings in database...")
        try:
            store_embeddings_in_db(connection, task_id, video_path)
        except Exception as e:
            print(f"Error storing embeddings for {video_path}: {str(e)}")
        return
    
    try:
        # Create embeddings and store in DB
        print("Creating video embeddings...")
        # If the video_path is an OCI path, create a PAR URL and use that for embedding
        if isinstance(video_path, str) and video_path.startswith('oci://'):
            par = _get_par_url_for_oci_path(video_path)
            if not par:
                raise RuntimeError('Failed to create PAR for ' + video_path)
            task_id = create_video_embeddings(twelvelabs_client, par)
        else:
            # assume video_path is an http(s) URL or local file path already handled
            task_id = create_video_embeddings(twelvelabs_client, video_path)
        
        # Store task_id in JSON
        task_ids[video_path] = task_id
        save_task_ids(task_ids)

        print("Storing embeddings in database...")
        # Store the original video_path (oci://... or URL) in the DB
        store_embeddings_in_db(connection, task_id, video_path, tw_client=twelvelabs_client)
    except Exception as e:
        print(f"Error processing video {video_path}: {str(e)}")

def store_video_embeddings(video_path):
    """Process video file(s) and store embeddings in Oracle DB"""
    try:
        connection = get_db_connection()
        connection.autocommit = True  # Enable autocommit
        
        # Verify DB version
        db_version = tuple(int(s) for s in connection.version.split("."))[:2]
        if db_version < (23, 7):
            sys.exit("This example requires Oracle Database 23.7 or later")
        print("Connected to Oracle Database")
        
        if not os.path.exists(video_path):
            print(f"Path not found: {video_path}")
            sys.exit(1)
        
        # Process videos
        if os.path.isfile(video_path):
            print (f"Processing single video file: {video_path}")
            process_video(connection, video_path)
        else:
            # Process all video files in the directory
            video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.webm')
            for filename in os.listdir(video_path):
                if filename.lower().endswith(video_extensions):
                    video_file_path = os.path.join(video_path, filename)
                    process_video(connection, video_file_path)
                    
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Store video embeddings')
    parser.add_argument('video_path', help='Path to video file or folder')
    
    
    print("Loded ENV - ", db_username, db_password, db_connect_string, db_wallet_path,twelvelabs_api_key)
    args = parser.parse_args()


    # Initialize Twelve Labs client
    twelvelabs_client = TwelveLabs(api_key=twelvelabs_api_key)
    # if not twelvelabs_client.api_key:
    #     print('\nYou need to set your TWELVE_LABS_API_KEY\n')
    #     print('https://playground.twelvelabs.io/dashboard/api-key')
    #     print('export TWELVE_LABS_API_KEY=your_api_key_value\n')
    #     exit()
    
    # Constants
    EMBEDDING_MODEL = "Marengo-retrieval-2.7"
    #EMBEDDING_MODEL = "marengo-embed-2-7-v1:0"
    SEGMENT_DURATION = 10  # seconds per segment
    TOP_K = 5  # number of results to return in similarity search
    
    store_video_embeddings(args.video_path) 