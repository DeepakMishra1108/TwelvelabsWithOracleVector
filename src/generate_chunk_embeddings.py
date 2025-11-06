#!/usr/bin/env python3
"""Generate embeddings for already uploaded video chunks

This script finds video chunks in the database that don't have embeddings yet
and generates TwelveLabs embeddings for them.
"""

import os
import sys
import logging
from dotenv import load_dotenv
import threading
import time
import json
import oracledb

load_dotenv()

# Setup logging before any other imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import OCI after logging setup
try:
    import oci
    logger.info("✅ OCI SDK imported")
except Exception as e:
    logger.error(f"❌ Failed to import OCI SDK: {e}")
    sys.exit(1)

# Import TwelveLabs
try:
    from twelvelabs import TwelveLabs
    logger.info("✅ TwelveLabs SDK imported")
except Exception as e:
    logger.error(f"❌ Failed to import TwelveLabs: {e}")
    sys.exit(1)


def get_db_connection():
    """Get database connection"""
    try:
        db_username = os.getenv("ORACLE_DB_USERNAME")
        db_password = os.getenv("ORACLE_DB_PASSWORD")
        db_connect_string = os.getenv("ORACLE_DB_CONNECT_STRING")
        db_wallet_path = os.getenv("ORACLE_DB_WALLET_PATH")
        db_wallet_pw = os.getenv("ORACLE_DB_WALLET_PASSWORD")
        
        # Initialize Oracle client with wallet
        try:
            oracledb.init_oracle_client(config_dir=db_wallet_path)
        except Exception as init_err:
            # Already initialized, ignore
            pass
        
        connection = oracledb.connect(
            user=db_username,
            password=db_password,
            dsn=db_connect_string,
            config_dir=db_wallet_path,
            wallet_location=db_wallet_path,
            wallet_password=db_wallet_pw
        )
        
        return connection
    except Exception as e:
        logger.exception(f"❌ Error connecting to database: {e}")
        return None


def load_oci_config():
    """Load OCI configuration"""
    try:
        # Try loading from repository-local path first
        local_config_path = os.path.join(
            os.path.dirname(__file__),
            'twelvelabvideoai',
            '.oci',
            'config'
        )
        
        if os.path.exists(local_config_path):
            config = oci.config.from_file(local_config_path, "DEFAULT")
            logger.info(f"✅ Loaded OCI config from: {local_config_path}")
            return config
        
        # Fallback to default OCI config
        config = oci.config.from_file()
        logger.info("✅ Loaded OCI config from default location")
        return config
        
    except Exception as e:
        logger.error(f"❌ Failed to load OCI config: {e}")
        return None


def get_par_url_for_oci_path(oci_path):
    """Generate PAR URL for an OCI object path"""
    try:
        from datetime import datetime, timedelta
        
        # Parse OCI path: oci://namespace/bucket/object_path
        if not oci_path.startswith('oci://'):
            logger.error(f"Invalid OCI path format: {oci_path}")
            return None
        
        path_parts = oci_path.replace('oci://', '').split('/', 2)
        if len(path_parts) != 3:
            logger.error(f"Could not parse OCI path: {oci_path}")
            return None
        
        namespace, bucket, object_name = path_parts
        
        # Load OCI config
        config = load_oci_config()
        if not config:
            logger.error("Could not load OCI config")
            return None
        
        # Create object storage client
        obj_client = oci.object_storage.ObjectStorageClient(config)
        
        # Check if object exists
        try:
            obj_client.head_object(namespace, bucket, object_name)
        except Exception as e:
            logger.error(f"Object not found in OCI: {object_name} - {e}")
            return None
        
        # Create PAR with datetime expiration
        expiration = datetime.utcnow() + timedelta(days=7)
        
        par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
            name=f"chunk-embed-{int(time.time())}",
            access_type="ObjectRead",
            time_expires=expiration,
            object_name=object_name
        )
        
        par = obj_client.create_preauthenticated_request(namespace, bucket, par_details)
        par_url = f"https://objectstorage.{config['region']}.oraclecloud.com{par.data.access_uri}"
        
        logger.info(f"✅ Created PAR URL for {object_name}")
        return par_url
        
    except Exception as e:
        logger.exception(f"❌ Error creating PAR URL: {e}")
        return None


def find_chunks_without_embeddings():
    """Find video chunks that don't have embeddings"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        cursor = conn.cursor()
        
        # Find chunks (file_name contains 'chunk') that don't have embeddings
        query = """
            SELECT 
                am.id,
                am.file_name,
                am.album_name,
                am.file_type,
                am.oci_namespace || '/' || am.oci_bucket || '/' || am.oci_object_path as oci_path
            FROM album_media am
            WHERE am.file_type = 'video'
              AND (am.file_name LIKE '%chunk%' OR am.oci_object_path LIKE '%chunk%')
              AND NOT EXISTS (
                  SELECT 1 FROM video_embeddings ve 
                  WHERE ve.video_file = am.file_name
              )
            ORDER BY am.id
        """
        
        cursor.execute(query)
        columns = [col[0].lower() for col in cursor.description]
        chunks = []
        
        for row in cursor:
            chunk_data = dict(zip(columns, row))
            # Prepend oci:// to the path
            chunk_data['oci_path'] = f"oci://{chunk_data['oci_path']}"
            chunks.append(chunk_data)
        
        cursor.close()
        conn.close()
        logger.info(f"📊 Found {len(chunks)} chunks without embeddings")
        return chunks
        
    except Exception as e:
        logger.exception(f"❌ Error finding chunks: {e}")
        return []


def generate_embedding_for_chunk(chunk_data):
    """Generate embedding for a single chunk"""
    try:
        from twelvelabs import TwelveLabs
        
        media_id = chunk_data['id']
        file_name = chunk_data['file_name']
        album_name = chunk_data['album_name']
        oci_path = chunk_data['oci_path']
        
        logger.info(f"🎬 Processing chunk {media_id}: {file_name}")
        
        # Generate PAR URL
        logger.info(f"🔗 Generating PAR URL for {oci_path}")
        par_url = get_par_url_for_oci_path(oci_path)
        
        if not par_url:
            logger.error(f"❌ Could not generate PAR URL for chunk {media_id}")
            return False
        
        # Create TwelveLabs client
        client = TwelveLabs(api_key=os.getenv("TWELVE_LABS_API_KEY"))
        
        # Create embedding task
        logger.info(f"🧠 Creating embeddings for chunk {media_id}")
        task = client.embed.tasks.create(
            model_name="Marengo-retrieval-2.7",
            video_url=par_url,
            video_clip_length=10
        )
        
        # Wait for completion
        task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
        
        if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
            status = client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
            final = client.embed.tasks.retrieve(task_id=task_id)
        elif hasattr(task, 'wait_for_done'):
            task.wait_for_done(sleep_interval=2)
            final = task
        else:
            final = task
        
        # Store embeddings
        embedding_count = 0
        
        logger.info(f"📦 Response attributes: {dir(final)}")
        if hasattr(final, 'video_embedding'):
            logger.info(f"✅ Has video_embedding attribute")
            logger.info(f"📦 video_embedding type: {type(final.video_embedding)}")
            if final.video_embedding and hasattr(final.video_embedding, 'segments') and final.video_embedding.segments:
                logger.info(f"✅ Has segments: {len(final.video_embedding.segments)} segments")
            else:
                logger.warning(f"❌ No segments or segments is None")
        else:
            logger.warning(f"❌ No video_embedding attribute on final response")
        
        if hasattr(final, 'video_embedding') and final.video_embedding and hasattr(final.video_embedding, 'segments') and final.video_embedding.segments:
            conn = get_db_connection()
            if not conn:
                logger.error(f"❌ Could not connect to database")
                return False
                
            cursor = conn.cursor()
            
            # Check first segment structure
            if len(final.video_embedding.segments) > 0:
                first_seg = final.video_embedding.segments[0]
                logger.info(f"📦 First segment: start={first_seg.start_offset_sec}, end={first_seg.end_offset_sec}")
                if hasattr(first_seg, 'embedding_scope') and first_seg.embedding_scope:
                    logger.info(f"✅ Has embedding_scope with {len(first_seg.embedding_scope)} items")
                    first_scope = first_seg.embedding_scope[0]
                    logger.info(f"📦 First scope attributes: {dir(first_scope)}")
            
            for segment in final.video_embedding.segments:
                if hasattr(segment, 'embedding_scope') and segment.embedding_scope:
                    for scope in segment.embedding_scope:
                        if hasattr(scope, 'embedding') and scope.embedding:
                            embedding_vector = scope.embedding.float
                            
                            # Insert into video_embeddings table
                            try:
                                embedding_json = json.dumps(list(embedding_vector))
                                cursor.execute("""
                                    INSERT INTO video_embeddings 
                                    (video_file, start_time, end_time, embedding_vector) 
                                    VALUES (:video_file, :start_time, :end_time, TO_VECTOR(:embedding))
                                """, {
                                    'video_file': file_name,
                                    'start_time': segment.start_offset_sec,
                                    'end_time': segment.end_offset_sec,
                                    'embedding': embedding_json
                                })
                                embedding_count += 1
                            except Exception as db_err:
                                logger.error(f"❌ Failed to store segment embedding: {db_err}")
                elif hasattr(segment, 'float_'):
                    # Direct embedding on segment
                    embedding_vector = segment.float_
                    
                    try:
                        embedding_json = json.dumps(list(embedding_vector))
                        cursor.execute("""
                            INSERT INTO video_embeddings 
                            (video_file, start_time, end_time, embedding_vector) 
                            VALUES (:video_file, :start_time, :end_time, TO_VECTOR(:embedding))
                        """, {
                            'video_file': file_name,
                            'start_time': segment.start_offset_sec if hasattr(segment, 'start_offset_sec') else 0,
                            'end_time': segment.end_offset_sec if hasattr(segment, 'end_offset_sec') else 0,
                            'embedding': embedding_json
                        })
                        embedding_count += 1
                    except Exception as db_err:
                        logger.error(f"❌ Failed to store segment embedding: {db_err}")
            
            conn.commit()
            cursor.close()
            
            # Update album_media with first embedding as representative
            if embedding_count > 0 and hasattr(final.video_embedding.segments[0], 'embedding_scope'):
                first_scope = final.video_embedding.segments[0].embedding_scope[0]
                if hasattr(first_scope, 'embedding') and first_scope.embedding:
                    representative_embedding = first_scope.embedding.float
                    try:
                        cursor = conn.cursor()
                        embedding_json = json.dumps(list(representative_embedding))
                        cursor.execute("""
                            UPDATE album_media 
                            SET embedding_vector = TO_VECTOR(:embedding) 
                            WHERE id = :media_id
                        """, {
                            'embedding': embedding_json,
                            'media_id': media_id
                        })
                        conn.commit()
                        cursor.close()
                        logger.info(f"✅ Updated album_media with representative embedding")
                    except Exception as update_err:
                        logger.warning(f"⚠️ Could not update album_media: {update_err}")
            
            conn.close()
        
        if embedding_count > 0:
            logger.info(f"✅ Created {embedding_count} embeddings for chunk {media_id}: {file_name}")
            return True
        else:
            logger.error(f"❌ No embeddings created for chunk {media_id}")
            return False
            
    except Exception as e:
        logger.exception(f"❌ Error generating embedding for chunk {chunk_data.get('id')}: {e}")
        return False


def process_chunks_parallel(chunks, max_workers=2):
    """Process multiple chunks in parallel"""
    results = {
        'success': 0,
        'failed': 0,
        'total': len(chunks)
    }
    
    def worker(chunk):
        if generate_embedding_for_chunk(chunk):
            results['success'] += 1
        else:
            results['failed'] += 1
    
    threads = []
    for i in range(0, len(chunks), max_workers):
        batch = chunks[i:i+max_workers]
        batch_threads = []
        
        for chunk in batch:
            thread = threading.Thread(target=worker, args=(chunk,))
            thread.daemon = True
            thread.start()
            batch_threads.append(thread)
        
        # Wait for batch to complete
        for thread in batch_threads:
            thread.join()
        
        logger.info(f"📊 Progress: {results['success']}/{results['total']} completed, {results['failed']} failed")
    
    return results


def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("🚀 Starting chunk embedding generation")
    logger.info("=" * 60)
    
    # Find chunks without embeddings
    chunks = find_chunks_without_embeddings()
    
    if not chunks:
        logger.info("✅ No chunks found that need embeddings")
        return
    
    # Display chunks
    logger.info(f"\n📋 Chunks to process:")
    for chunk in chunks:
        logger.info(f"  - ID: {chunk['id']}, File: {chunk['file_name']}, Album: {chunk['album_name']}")
    
    # Ask for confirmation
    print(f"\n❓ Process {len(chunks)} chunks? (y/n): ", end='')
    response = input().strip().lower()
    
    if response != 'y':
        logger.info("❌ Cancelled by user")
        return
    
    # Process chunks
    logger.info(f"\n🔄 Processing {len(chunks)} chunks...")
    start_time = time.time()
    
    results = process_chunks_parallel(chunks, max_workers=2)
    
    elapsed = time.time() - start_time
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✅ Successful: {results['success']}/{results['total']}")
    logger.info(f"❌ Failed: {results['failed']}/{results['total']}")
    logger.info(f"⏱️  Time elapsed: {elapsed:.1f} seconds")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
