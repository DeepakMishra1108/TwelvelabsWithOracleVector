#!/usr/bin/env python3
"""Store photo embeddings in Oracle DB

This module creates Marengo embeddings for photos and stores them in Oracle.
Photos are organized into albums.
"""
import os
import struct
import oracledb
from dotenv import load_dotenv
from twelvelabs import TwelveLabs
from utils.db_utils import get_db_connection
import oci
import time
from urllib.parse import urlparse, parse_qs

load_dotenv()


def create_photo_embedding(client, image_url):
    """Create a Marengo embedding for a single photo
    
    Args:
        client: TwelveLabs client instance
        image_url: URL to the photo (http/https or file:// or oci://)
        
    Returns:
        list: Embedding vector as list of floats, or None on error
    """
    def _get_par_url_for_oci_path(oci_path, ttl_seconds=3600):
        try:
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
                return None

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

    def _resolve_image_url(image_url):
        # If path is an OCI path, create a PAR and return it
        if isinstance(image_url, str) and image_url.startswith('oci://'):
            par = _get_par_url_for_oci_path(image_url)
            if par:
                return par
            return image_url

        # If it's our local object proxy path (/object_proxy?path=...), try to extract the oci path
        if isinstance(image_url, str) and image_url.startswith('/object_proxy'):
            parsed = urlparse(image_url)
            qs = parse_qs(parsed.query)
            path_param = qs.get('path', [None])[0]
            if path_param and path_param.startswith('oci://'):
                par = _get_par_url_for_oci_path(path_param)
                if par:
                    return par
            # Fallback: build absolute URL from APP_BASE_URL or localhost
            base = os.getenv('APP_BASE_URL', 'http://127.0.0.1:8080')
            return base.rstrip('/') + image_url

        return image_url

    try:
        # resolve potential proxy/oci URLs to a reachable URL for TwelveLabs
        resolved_url = _resolve_image_url(image_url)
        print(f"Creating photo embedding for resolved URL: {resolved_url}")
        # Use Marengo-retrieval-2.7 for image embeddings
        # Try common shapes across SDK versions
        task = None
        try:
            task = client.embed.create(
                model_name="Marengo-retrieval-2.7",
                image_url=resolved_url
            )
        except Exception as e:
            print(f"embed.create raised: {e}")
            raise

        task_id = getattr(task, 'id', None) or getattr(task, 'task_id', None)
        print(f"Created embed task id={task_id}")

        # Preferred: use the tasks.wait_for_done helper if available
        try:
            if hasattr(client.embed, 'tasks') and hasattr(client.embed.tasks, 'wait_for_done') and task_id:
                status = client.embed.tasks.wait_for_done(sleep_interval=2, task_id=task_id)
                print(f"tasks.wait_for_done returned status: {getattr(status, 'status', None)}")
                # retrieve final task
                try:
                    final = client.embed.tasks.retrieve(task_id=task_id)
                except Exception:
                    final = status
            else:
                # fallback: some SDKs return a task object with wait_for_done method
                if hasattr(task, 'wait_for_done'):
                    task.wait_for_done(sleep_interval=2)
                    final = task
                else:
                    final = task

            final_status = getattr(final, 'status', None)
            print(f"Final task status: {final_status}")

            # Extract embedding depending on shape
            embedding = None
            if hasattr(final, 'image_embedding') and getattr(final.image_embedding, 'float', None) is not None:
                embedding = final.image_embedding.float
            elif getattr(final, 'image_embedding', None) is not None and hasattr(final.image_embedding, 'float_'):
                embedding = final.image_embedding.float_
            # New: support ImageEmbeddingResult with segments list containing BaseSegment(float_=...)
            elif getattr(final, 'image_embedding', None) is not None and getattr(final.image_embedding, 'segments', None):
                try:
                    seg0 = final.image_embedding.segments[0]
                    if hasattr(seg0, 'float_'):
                        embedding = seg0.float_
                    elif hasattr(seg0, 'float'):
                        embedding = seg0.float
                    else:
                        # try to coerce segment to list
                        embedding = list(seg0)
                except Exception:
                    embedding = None
            elif hasattr(final, 'image_embedding') and isinstance(final.image_embedding, (list, tuple)):
                embedding = final.image_embedding

            if embedding:
                print(f"Embedding vector length: {len(embedding)}")
                return embedding
            else:
                print(f"No embedding found on final task object: {repr(final)[:400]}")
                return None

        except Exception as e:
            print(f"Exception while waiting/retrieving embed task: {e}")
            return None

    except Exception as e:
        # If the TwelveLabs client attached an HTTP response, try to show it
        try:
            # for httpx exceptions some libs attach .request/.response
            resp = getattr(e, 'response', None)
            if resp is not None:
                print(f"Error creating photo embedding: status_code={getattr(resp, 'status_code', None)}, body={getattr(resp, 'text', None)}")
            else:
                print(f"Error creating photo embedding: {e}")
        except Exception:
            print(f"Error creating photo embedding (non-HTTP): {e}")
        return None


def store_photo_embedding_in_db(album_name, photo_file, embedding_vector):
    """Store a photo embedding in Oracle DB as float32 BLOB
    
    Args:
        album_name: Name of the album this photo belongs to
        photo_file: Photo file path or URL
        embedding_vector: List of floats (embedding)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        connection = get_db_connection()
        
        cursor = connection.cursor()
        
        # Convert embedding to float32 BLOB
        embedding_bytes = struct.pack(f'{len(embedding_vector)}f', *embedding_vector)
        
        insert_sql = """
        INSERT INTO photo_embeddings (album_name, photo_file, embedding_vector)
        VALUES (:1, :2, :3)
        """
        
        cursor.execute(insert_sql, (album_name, photo_file, embedding_bytes))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        print(f"Stored photo embedding: {photo_file} in album '{album_name}'")
        return True
        
    except Exception as e:
        print(f"Error storing photo embedding: {e}")
        return False


def create_photo_embeddings_for_album(album_name, photo_urls):
    """Create and store embeddings for multiple photos in an album
    
    Args:
        album_name: Name of the album
        photo_urls: List of photo URLs
        
    Returns:
        dict: Results with success count and errors
    """
    api_key = os.getenv('TWELVE_LABS_API_KEY')
    if not api_key:
        return {'error': 'TWELVE_LABS_API_KEY not set', 'success': 0, 'failed': 0}
    
    client = TwelveLabs(api_key=api_key)
    
    results = {
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for photo_url in photo_urls:
        print(f"Processing photo: {photo_url}")
        
        # Create embedding
        embedding = create_photo_embedding(client, photo_url)
        
        if embedding:
            # Store in DB
            if store_photo_embedding_in_db(album_name, photo_url, embedding):
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(f"Failed to store: {photo_url}")
        else:
            results['failed'] += 1
            results['errors'].append(f"Failed to create embedding: {photo_url}")
    
    return results


if __name__ == '__main__':
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python store_photo_embeddings.py <album_name> <photo_url1> [photo_url2 ...]")
        sys.exit(1)
    
    album = sys.argv[1]
    photos = sys.argv[2:]
    
    print(f"Creating embeddings for album '{album}' with {len(photos)} photo(s)")
    results = create_photo_embeddings_for_album(album, photos)
    
    print(f"\nResults:")
    print(f"  Success: {results['success']}")
    print(f"  Failed: {results['failed']}")
    if results['errors']:
        print(f"  Errors:")
        for err in results['errors']:
            print(f"    - {err}")
