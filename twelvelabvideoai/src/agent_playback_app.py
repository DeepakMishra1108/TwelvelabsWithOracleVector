from flask import Flask, request, render_template, jsonify, Response
import os
import sys
import json
import re
import io
import time
import logging
from query_video_embeddings import query_video_embeddings_multiple, query_video_embeddings
from store_video_embeddings import store_video_embeddings, create_video_embeddings, store_embeddings_in_db
from utils.oci_utils import load_par_cache, save_par_cache, get_par_url_for_oci as utils_get_par_url_for_oci
from utils.ffmpeg_utils import cut_segment as utils_cut_segment, concat_segments as utils_concat_segments, extract_frame_bytes as utils_extract_frame_bytes
from utils.http_utils import download_url_to_file as utils_download_url_to_file
import uuid
import os
import base64
from concurrent.futures import ThreadPoolExecutor
import subprocess
import tempfile
import shutil
import pathlib
import httpx
from dotenv import load_dotenv
import oracledb
from twelvelabs import TwelveLabs

# Import unified album manager with error handling
try:
    from unified_album_manager import album_manager, create_unified_embedding
    UNIFIED_ALBUM_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not import unified_album_manager: {e}")
    album_manager = None
    create_unified_embedding = None
    UNIFIED_ALBUM_AVAILABLE = False

try:
    # pegasus_client is a local helper that wraps Pegasus + validation
    from pegasus_client import generate_plan_from_candidates
except Exception:
    generate_plan_from_candidates = None
try:
    from pegasus_helpers import normalize_plan, validate_edit_plan
except Exception:
    normalize_plan = None
    validate_edit_plan = None

# Security: simple API key protection for upload/proxy endpoints
UPLOAD_API_KEY = os.getenv('UPLOAD_API_KEY')
MULTIPART_THRESHOLD = int(os.getenv('MULTIPART_THRESHOLD', str(50 * 1024 * 1024)))  # 50MB

# Task registry for background jobs
_upload_tasks = {}
UPLOAD_TASKS_FILE = os.path.join(os.path.dirname(__file__), '..', 'upload_tasks.json')
# Summary task registry
_summary_tasks = {}
SUMMARY_TASKS_FILE = os.path.join(os.path.dirname(__file__), '..', 'summary_tasks.json')

# Thread pool for background processing
EXECUTOR = ThreadPoolExecutor(max_workers=int(os.getenv('UPLOAD_WORKERS', '2')))


def load_upload_tasks():
    """Load persisted upload tasks from disk into the in-memory registry."""
    global _upload_tasks
    try:
        path = os.path.abspath(UPLOAD_TASKS_FILE)
        if os.path.exists(path):
            with open(path, 'r') as f:
                _upload_tasks = json.load(f)
                # logger may not be configured when this module is first imported;
                # callers should ensure logger exists before relying on the log.
                try:
                    logger.info('Loaded upload tasks: %d', len(_upload_tasks))
                except Exception:
                    pass
    except Exception:
        try:
            logger.exception('Failed to load upload tasks')
        except Exception:
            pass


def load_summary_tasks():
    global _summary_tasks
    try:
        path = os.path.abspath(SUMMARY_TASKS_FILE)
        if os.path.exists(path):
            with open(path, 'r') as f:
                _summary_tasks = json.load(f)
                logger.info('Loaded summary tasks: %d', len(_summary_tasks))
    except Exception:
        logger.exception('Failed to load summary tasks')

def save_summary_tasks():
    try:
        path = os.path.abspath(SUMMARY_TASKS_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(_summary_tasks, f)
        logger.debug('Saved summary tasks: %d', len(_summary_tasks))
    except Exception:
        logger.exception('Failed to save summary tasks')
    # persisted summary tasks saved; nothing else to do here


def _update_summary_task(task_id, **kwargs):
    """Helper to update a summary task's metadata and persist."""
    global _summary_tasks
    t = _summary_tasks.get(task_id, {})
    t.update(kwargs)
    _summary_tasks[task_id] = t
    try:
        save_summary_tasks()
    except Exception:
        logger.exception('Failed to persist summary tasks')


def save_upload_tasks():
    try:
        path = os.path.abspath(UPLOAD_TASKS_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(_upload_tasks, f)
        logger.debug('Saved upload tasks: %d', len(_upload_tasks))
    except Exception:
        logger.exception('Failed to save upload tasks')


# load_upload_tasks() is called after logger and PAR cache are initialized below

try:
    import oci
except Exception:
    oci = None
try:
    from oci_config import load_oci_config as _central_load_oci_config
except Exception:
    _central_load_oci_config = None

# Configure logging
logging.basicConfig(level=os.getenv('APP_LOG_LEVEL', 'INFO'))
logger = logging.getLogger('agent_playback')
# Load .env early so modules can read TWELVE_LABS_API_KEY, OCI creds, etc.
try:
    load_dotenv()
    logger.debug('Loaded .env file into environment')
except Exception:
    # if dotenv isn't present or fails, continue; fall back to real env
    pass

# PAR caching: in-memory cache mapping (namespace,bucket,object) -> (url, expiry_ts)
_par_cache = {}
# File-backed cache path
PAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', '.par_cache.json')
# Default PAR TTL in seconds (can be set via env)
PAR_TTL_SECONDS = int(os.getenv('PAR_TTL_SECONDS', '3600'))
# Optional local media root (only serve files under this directory if configured)
MEDIA_ROOT = os.getenv('MEDIA_ROOT')  # e.g. /path/to/media

# Use the `templates` folder next to this file for HTML templates
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
app = Flask(__name__, template_folder=TEMPLATES_DIR)

# Domain and CORS Configuration for mishras.online
@app.after_request
def after_request(response):
    """Add CORS headers and security headers for mishras.online domain"""
    origin = request.headers.get('Origin')
    cors_origins = os.getenv('CORS_ORIGINS', 'https://mishras.online,http://mishras.online').split(',')
    
    if origin in cors_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-API-KEY'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    # Security headers for production domain
    if 'mishras.online' in request.headers.get('Host', ''):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Note: HSTS should be handled by reverse proxy/load balancer
    
    return response

@app.route('/health')
def health_check_domain():
    """Health check endpoint that returns domain info"""
    return jsonify({
        'status': 'healthy',
        'domain': request.headers.get('Host', 'unknown'),
        'server_name': app.config.get('SERVER_NAME'),
        'url_scheme': app.config.get('PREFERRED_URL_SCHEME', 'http'),
        'timestamp': int(time.time())
    })


def load_par_cache():
    global _par_cache
    try:
        path = os.path.abspath(PAR_CACHE_FILE)
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                # convert keys back to tuples
                _par_cache = {tuple(k.split('|')): (v[0], int(v[1])) for k, v in data.items()}
                logger.info('Loaded PAR cache with %d entries', len(_par_cache))
    except Exception:
        logger.exception('Failed to load PAR cache')


def save_par_cache():
    try:
        path = os.path.abspath(PAR_CACHE_FILE)
        serializable = {('|'.join(k)): [v[0], int(v[1])] for k, v in _par_cache.items()}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(serializable, f)
        logger.debug('Saved PAR cache with %d entries', len(_par_cache))
    except Exception:
        logger.exception('Failed to save PAR cache to disk')


# Load existing cache at startup
load_par_cache()

# Load persisted upload tasks after logger exists
load_upload_tasks()
load_summary_tasks()


def _load_oci_config():
    """Local wrapper that uses the central loader when available."""
    if not oci:
        raise RuntimeError('OCI SDK not available')
    if _central_load_oci_config:
        return _central_load_oci_config(oci)
    return oci.config.from_file()
# The main HTML UI has been moved to a template file under `templates/index.html`


def _get_par_url_for_oci(vf):
    # delegate to utils
    try:
        return utils_get_par_url_for_oci(vf)
    except Exception:
        return f'/object_proxy?path={vf}'


def normalize_video_entry(r):
    """Normalize a video entry's video_file into a browser-accessible URL."""
    vf = r.get('video_file')
    url = vf
    if vf and isinstance(vf, str):
        if vf.startswith('oci://'):
            if oci:
                try:
                    url = _get_par_url_for_oci(vf)
                except Exception:
                    url = f'/object_proxy?path={vf}'
            else:
                url = f'/object_proxy?path={vf}'
        elif os.path.isabs(vf):
            try:
                if MEDIA_ROOT and os.path.commonpath([os.path.abspath(vf), os.path.abspath(MEDIA_ROOT)]) == os.path.abspath(MEDIA_ROOT):
                    url = f'/object_proxy_local?path={vf}'
                else:
                    url = ''
            except Exception:
                url = ''

    rc = r.copy()
    rc['video_file'] = url
    return rc


def normalize_photo_entry(p):
    """Normalize a photo entry's photo_file into a browser-accessible URL."""
    pf = p.get('photo_file')
    url = pf
    if pf and isinstance(pf, str):
        if pf.startswith('oci://'):
            if oci:
                try:
                    url = _get_par_url_for_oci(pf)
                except Exception:
                    url = f'/object_proxy?path={pf}'
            else:
                url = f'/object_proxy?path={pf}'
        elif os.path.isabs(pf):
            try:
                if MEDIA_ROOT and os.path.commonpath([os.path.abspath(pf), os.path.abspath(MEDIA_ROOT)]) == os.path.abspath(MEDIA_ROOT):
                    url = f'/object_proxy_local?path={pf}'
                else:
                    url = ''
            except Exception:
                url = ''
    pc = p.copy()
    pc['photo_file'] = url
    return pc


def generate_edit_plan_with_pegasus(queries, duration_limit=60, max_segments=6, style_hint=None, top_k=20, dry_run=False, candidates_override=None):
    """Ask TwelveLabs Pegasus to produce an edit plan from candidate segments.

    If dry_run=True the function will return a dict { 'prompt': str, 'candidates': [...] }
    instead of calling the TwelveLabs API. This is useful for validating and tuning
    the prompt/format without making network calls.

    On normal runs returns a dict { plan: [...], narrative: str }
    """
    load_dotenv()
    api_key = os.getenv('TWELVE_LABS_API_KEY')
    if not api_key:
        raise RuntimeError('TWELVE_LABS_API_KEY not configured')

    # Gather candidate segments from DB (reuse existing search function)
    # Allow callers to pass a pre-built candidate list to avoid DB/API calls (useful for dry runs)
    if candidates_override is not None:
        candidates_list = candidates_override[:top_k]
    else:
        try:
            candidates = query_video_embeddings_multiple(queries)
            first = queries[0]
            candidates_list = candidates.get(first, [])[:top_k]
        except Exception as e:
            logger.exception('Failed to query candidates for Pegasus plan')
            raise

    # Build a stricter prompt that asks Pegasus to return JSON matching a small schema.
    # We include an explicit example object and ask for JSON only (no explanation text).
    import json as _json
    schema_example = {
        "plan": [
            {
                "video_file": "oci://namespace/bucket/object.mp4",
                "start": 1.23,
                "end": 6.78,
                "caption": "Short caption for the clip",
                "narrator_text": "One-sentence narration for this clip"
            }
        ],
        "narrative": "A one-paragraph overall narrative describing the assembled highlight"
    }

    prompt_parts = [
        'You are Pegasus. Return ONLY a single valid JSON object and NOTHING else (no surrounding text).',
        'Produce an edit plan for a short highlight video that can be constructed by concatenating short clips from the candidate segments.',
        f'Max total duration (seconds): {duration_limit}. Max segments: {max_segments}.',
    ]
    if style_hint:
        prompt_parts.append(f'Style hint: {style_hint}.')
    prompt_parts.append('Candidates:')
    # include candidate list (video_file, start, end, score)
    prompt_parts.append(_json.dumps(candidates_list))
    prompt_parts.append('Return JSON matching this example schema (use the same keys and types):')
    prompt_parts.append(_json.dumps(schema_example, indent=2))
    prompt_parts.append('Requirements:')
    prompt_parts.append('- The top-level object MUST have keys "plan" (array) and "narrative" (string).')
    prompt_parts.append('- Each plan item MUST include video_file (string), start (float seconds), end (float seconds).')
    prompt_parts.append('- Optional keys per item: caption (string), narrator_text (string), transition (string).')
    prompt_parts.append('- Use seconds as floats for start/end. Ensure start < end and durations sum to <= Max total duration.')
    prompt_parts.append('Return ONLY the JSON object. No markdown, no explanation, no extra text.')
    prompt = '\n'.join(prompt_parts)

    # If dry-run requested, return the prompt and the candidate list for inspection
    if dry_run:
        return {'prompt': prompt, 'candidates': candidates_list}

    tw = TwelveLabs(api_key=api_key)
    try:
        gen = tw.generate.create(model_name='Pegasus', prompt=prompt, max_tokens=1500)
        # Some SDKs return text in generation. We'll attempt to parse JSON from the output
        text = ''
        try:
            # try different attributes depending on SDK version
            text = getattr(gen, 'text', None) or getattr(gen, 'output', None) or str(gen)
        except Exception:
            text = str(gen)

        # Extract first JSON object from the model output
        import re
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise RuntimeError('Pegasus did not return JSON')
        plan_json = _json.loads(m.group(0))
        return plan_json
    except Exception as e:
        logger.exception('Pegasus generation failed')
        raise


@app.route('/plan_summary', methods=['POST'])
def plan_summary():
    """Endpoint: generate an edit plan using Pegasus for the provided queries.

    JSON body: { "queries": ["text"], "duration_limit": 60, "max_segments": 6 }
    Returns: { task_id, plan }
    """
    payload = request.get_json() or {}
    queries = payload.get('queries')
    if not queries:
        return jsonify({'error': 'queries required'}), 400
    duration_limit = int(payload.get('duration_limit', 60))
    max_segments = int(payload.get('max_segments', 6))
    style = payload.get('style')

    task_id = str(uuid.uuid4())
    _summary_tasks[task_id] = {'status': 'planning', 'queries': queries, 'created_at': int(time.time())}
    save_summary_tasks()

    # Gather candidate segments from DB
    try:
        candidates_by_query = query_video_embeddings_multiple(queries)
        first = queries[0]
        candidates_list = candidates_by_query.get(first, [])
    except Exception as e:
        logger.exception('Failed to query candidates for plan_summary')
        _update_summary_task(task_id, status='failed', error=str(e))
        return jsonify({'error': str(e)}), 500

    # If we have a pegasus_client wrapper and an API key, prefer it (it includes validation + retry)
    if generate_plan_from_candidates and os.getenv('TWELVE_LABS_API_KEY'):
        try:
            plan = generate_plan_from_candidates(candidates_list, duration_limit=duration_limit, max_segments=max_segments, style_hint=style, retries=1)
            _update_summary_task(task_id, status='planned', plan=plan, planned_at=int(time.time()))
            return jsonify({'task_id': task_id, 'plan': plan})
        except Exception as e:
            logger.exception('Pegasus client failed to generate plan')
            _update_summary_task(task_id, status='failed', error=str(e))
            return jsonify({'error': str(e)}), 500

    # Fallback: use the in-module generator which will call Pegasus directly (or raise if no key)
    try:
        plan = generate_edit_plan_with_pegasus(queries, duration_limit, max_segments, style)
        _update_summary_task(task_id, status='planned', plan=plan, planned_at=int(time.time()))
        return jsonify({'task_id': task_id, 'plan': plan})
    except Exception as e:
        logger.exception('Fallback Pegasus generation failed')
        _update_summary_task(task_id, status='failed', error=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/generate_summary_pegasus', methods=['POST'])
def generate_summary_pegasus():
    """Generate a Pegasus plan or dry-run using the Pegasus model.

    JSON body: { "queries": [...], "duration_limit":60, "max_segments":6, "style":null, "top_k":20, "dry_run": false }
    Returns: { task_id, plan/dry }
    """
    payload = request.get_json() or {}
    queries = payload.get('queries')
    if not queries:
        return jsonify({'error': 'queries required'}), 400
    duration_limit = int(payload.get('duration_limit', 60))
    max_segments = int(payload.get('max_segments', 6))
    style = payload.get('style')
    top_k = int(payload.get('top_k', 20))
    dry_run = bool(payload.get('dry_run', False))

    task_id = str(uuid.uuid4())
    _summary_tasks[task_id] = {'status': 'planning', 'queries': queries, 'created_at': int(time.time()), 'method': 'pegasus'}
    save_summary_tasks()

    # Allow passing candidates_override for testing
    candidates_override = payload.get('candidates_override')

    try:
        if generate_plan_from_candidates and os.getenv('TWELVE_LABS_API_KEY'):
            plan = generate_plan_from_candidates(candidates_override or [], duration_limit=duration_limit, max_segments=max_segments, style_hint=style, retries=1)
        else:
            plan = generate_edit_plan_with_pegasus(queries, duration_limit=duration_limit, max_segments=max_segments, style_hint=style, top_k=top_k, dry_run=dry_run, candidates_override=candidates_override)
        _update_summary_task(task_id, status='planned', plan=plan, planned_at=int(time.time()))
        return jsonify({'task_id': task_id, 'plan': plan})
    except Exception as e:
        logger.exception('Pegasus summary generation failed')
        _update_summary_task(task_id, status='failed', error=str(e))
        return jsonify({'error': str(e)}), 500


# The simple HTML fallback has been moved to templates/index.html as well


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    payload = request.get_json()
    # Accept either a list of queries or a single query string.
    queries = payload.get('queries')
    if not queries:
        q = payload.get('query')
        if not q:
            return jsonify({'error': 'No queries provided'}), 400
        # Build multiple prompts: full phrase + individual words
        words = [w for w in re.split(r'\s+', q.strip()) if w]
        # Keep original phrase first, then unique words
        # Normalize to preserve order and avoid duplicates
        seen = set()
        combined = []
        if q not in seen:
            combined.append(q)
            seen.add(q)
        for w in words:
            if w not in seen:
                combined.append(w)
                seen.add(w)
        queries = combined

    # Use existing module to query DB for all queries
    try:
        results_by_query = query_video_embeddings_multiple(queries)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # Normalize all video_file paths for every query and produce consistent by_query structure
    by_query = {}

    for q in queries:
        raw_list = results_by_query.get(q, []) or []
        normalized_list = [ normalize_video_entry(r) for r in raw_list ]
        # Standardize the per-query object: include both photos and videos keys
        by_query[q] = {
            'photos': [],
            'videos': normalized_list
        }

    # Also return a top-level 'results' for the primary query for backward compatibility
    primary_results = by_query.get(queries[0], {}).get('videos', [])
    return jsonify({'results': primary_results, 'by_query': by_query})



@app.route('/object_proxy')
def object_proxy():
    # Streams an OCI object through the Flask app. Expects query param `path=oci://...`
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'path param required'}), 400
    if not path.startswith('oci://'):
        return jsonify({'error': 'only oci:// paths supported by this proxy'}), 400

    # Simple API key check for proxy
    if UPLOAD_API_KEY:
        key = request.headers.get('X-API-KEY') or request.args.get('api_key')
        if key != UPLOAD_API_KEY:
            return jsonify({'error': 'unauthorized'}), 401

    if not oci:
        return jsonify({'error': 'OCI SDK not available on server'}), 500

    # Parse path
    path_body = path[len('oci://'):]
    parts = path_body.split('/', 2)
    try:
        config = _load_oci_config()
        obj_client = oci.object_storage.ObjectStorageClient(config)
        if len(parts) == 2:
            namespace = obj_client.get_namespace().data
            bucket = parts[0]
            object_name = parts[1]
        elif len(parts) == 3:
            namespace = parts[0]
            bucket = parts[1]
            object_name = parts[2]
        else:
            return jsonify({'error': 'invalid oci path format'}), 400

        # Range support: parse Range header if present
        range_header = request.headers.get('Range')
        if range_header:
            # Expected format: bytes=start-end
            m = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if not m:
                return jsonify({'error': 'invalid Range header'}), 400
            start = int(m.group(1))
            end = m.group(2)
            if end:
                end = int(end)
                range_spec = f"bytes={start}-{end}"
            else:
                range_spec = f"bytes={start}-"
            get_obj = obj_client.get_object(namespace, bucket, object_name, range=range_spec)
            status_code = 206
        else:
            get_obj = obj_client.get_object(namespace, bucket, object_name)
            status_code = 200

        stream = get_obj.data.raw

        def generate():
            for chunk in stream.stream(1024 * 64, decode_content=True):
                yield chunk

        # Attempt to derive content type
        content_type = get_obj.headers.get('content-type', 'application/octet-stream')
        resp = Response(generate(), content_type=content_type)
        resp.status_code = status_code
        # If Range requested, add Content-Range header if available
        if range_header:
            content_range = get_obj.headers.get('content-range') or get_obj.headers.get('Content-Range')
            if content_range:
                resp.headers['Content-Range'] = content_range
        return resp
    except Exception as e:
        logger.exception('object_proxy error')
        return jsonify({'error': str(e)}), 500


@app.route('/debug_embeddings')
def debug_embeddings():
    """Temporary debug endpoint: returns count of embeddings and sample vector lengths."""
    try:
        load_dotenv()
        user = os.getenv('ORACLE_DB_USERNAME')
        pwd = os.getenv('ORACLE_DB_PASSWORD')
        dsn = os.getenv('ORACLE_DB_CONNECT_STRING')
        wallet = os.getenv('ORACLE_DB_WALLET_PATH')
        wallet_pw = os.getenv('ORACLE_DB_WALLET_PASSWORD')
        if not user or not pwd or not dsn:
            return jsonify({'error': 'DB credentials not configured in environment'}), 500

        conn = oracledb.connect(user=user, password=pwd, dsn=dsn, config_dir=wallet, wallet_location=wallet, wallet_password=wallet_pw)
        cur = conn.cursor()
        try:
            cur.execute('SELECT COUNT(*) FROM video_embeddings')
            cnt = cur.fetchone()[0]
        except Exception as e:
            cur.close(); conn.close()
            return jsonify({'error': 'Failed to query video_embeddings', 'detail': str(e)}), 500

        samples = []
        try:
            cur.execute("SELECT video_file, start_time, end_time, embedding_vector FROM video_embeddings WHERE ROWNUM <= 10")
            for row in cur:
                vf, st, et, blob = row[0], row[1], row[2], row[3]
                if blob is None:
                    samples.append({'video_file': vf, 'start_time': st, 'end_time': et, 'bytes_len': 0, 'vec_len': 0})
                    continue
                try:
                    b = bytes(blob) if not isinstance(blob, memoryview) else blob.tobytes()
                    vec_len = int(len(b) / 4) if len(b) else 0
                    samples.append({'video_file': vf, 'start_time': st, 'end_time': et, 'bytes_len': len(b), 'vec_len': vec_len})
                except Exception as e:
                    samples.append({'video_file': vf, 'start_time': st, 'end_time': et, 'error': str(e)})
        finally:
            cur.close(); conn.close()

        # aggregate unique vector dimensions
        dims = sorted(list({s.get('vec_len', 0) for s in samples if isinstance(s.get('vec_len', None), int)}))
        return jsonify({'count': cnt, 'sample_count': len(samples), 'sample_rows': samples, 'unique_dims': dims})
    except Exception as e:
        logger.exception('debug_embeddings error')
        return jsonify({'error': 'internal', 'detail': str(e)}), 500


@app.route('/object_proxy_local')
def object_proxy_local():
    # Streams a local file from MEDIA_ROOT. Query param `path` should be an absolute path.
    path = request.args.get('path')
    if not path:
        return jsonify({'error': 'path param required'}), 400
    if not os.path.isabs(path):
        return jsonify({'error': 'path must be absolute'}), 400

    if not MEDIA_ROOT:
        return jsonify({'error': 'MEDIA_ROOT not configured'}), 500

    # Ensure path is under MEDIA_ROOT
    try:
        if os.path.commonpath([os.path.abspath(path), os.path.abspath(MEDIA_ROOT)]) != os.path.abspath(MEDIA_ROOT):
            return jsonify({'error': 'requested path not allowed'}), 403
    except Exception:
        return jsonify({'error': 'invalid path'}), 400

    if not os.path.exists(path):
        return jsonify({'error': 'file not found'}), 404

    file_size = os.path.getsize(path)

    # Parse Range header for partial content support
    range_header = request.headers.get('Range')
    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not m:
            return jsonify({'error': 'invalid Range header'}), 400
        start = int(m.group(1))
        end = m.group(2)
        if end:
            end = int(end)
            if end >= file_size:
                end = file_size - 1
        else:
            end = file_size - 1
        if start >= file_size:
            # Requested range not satisfiable
            resp = Response(status=416)
            resp.headers['Content-Range'] = f'bytes */{file_size}'
            return resp

        length = end - start + 1

        def generate_range(path, start, end):
            with open(path, 'rb') as f:
                f.seek(start)
                remaining = end - start + 1
                chunk_size = 1024 * 64
                while remaining > 0:
                    read_size = chunk_size if remaining >= chunk_size else remaining
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        # Determine content type
        try:
            import mimetypes
            content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        except Exception:
            content_type = 'application/octet-stream'

        resp = Response(generate_range(path, start, end), status=206, content_type=content_type)
        resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(length)
        return resp

    # No Range header: stream entire file
    def generate():
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(1024 * 64)
                if not chunk:
                    break
                yield chunk

    try:
        import mimetypes
        content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
    except Exception:
        content_type = 'application/octet-stream'

    resp = Response(generate(), content_type=content_type)
    resp.headers['Content-Length'] = str(file_size)
    resp.headers['Accept-Ranges'] = 'bytes'
    return resp


@app.route('/upload', methods=['POST'])
def upload():
    """Upload a video, store in OCI object storage (bucket), create PAR, create embeddings and store into Oracle DB."""
    if 'videoFile' not in request.files:
        return jsonify({'error': 'videoFile is required'}), 400
    file = request.files['videoFile']
    bucket = request.form.get('bucket')
    filename = file.filename
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400

    if not oci:
        return jsonify({'error': 'OCI SDK not configured on server'}), 500

    # API key protection for upload
    if UPLOAD_API_KEY:
        key = request.headers.get('X-API-KEY')
        if key != UPLOAD_API_KEY:
            return jsonify({'error': 'unauthorized'}), 401

    try:
        config = _load_oci_config()
        obj_client = oci.object_storage.ObjectStorageClient(config)
        namespace = obj_client.get_namespace().data

        # If no bucket provided, user must specify; otherwise pick default from env
        if not bucket:
            bucket = os.getenv('DEFAULT_OCI_BUCKET')
            if not bucket:
                return jsonify({'error': 'Bucket not specified and DEFAULT_OCI_BUCKET not set'}), 400

        # Upload object (streaming)
        # Use request.content_length if available; do not read whole file into memory.
        file_size = None
        try:
            # Flask's FileStorage may expose content_length
            file_size = getattr(file, 'content_length', None) or request.content_length
        except Exception:
            file_size = None

        # If size known and larger than threshold, use multipart upload. If unknown, try streaming put_object
        if file_size and file_size > MULTIPART_THRESHOLD:
            logger.info('Using multipart upload for %s (size=%d)', filename, file_size)
            # create multipart upload
            create_details = oci.object_storage.models.CreateMultipartUploadDetails(object=filename)
            mpu = obj_client.create_multipart_upload(namespace, bucket, create_details)
            upload_id = mpu.data.upload_id
            part_num = 1
            parts = []
            while True:
                chunk = file.stream.read(10 * 1024 * 1024)  # 10MB parts
                if not chunk:
                    break
                resp = obj_client.upload_part(namespace, bucket, filename, upload_id, part_num, chunk)
                etag = None
                try:
                    etag = (resp.headers.get('etag') if resp and hasattr(resp, 'headers') else None)
                except Exception:
                    etag = None
                # Use the SDK model for parts
                part_detail = oci.object_storage.models.CommitMultipartUploadPartDetails(part_num=part_num, etag=etag)
                parts.append(part_detail)
                part_num += 1

            commit_details = oci.object_storage.models.CommitMultipartUploadDetails(parts_to_commit=parts)
            obj_client.commit_multipart_upload(namespace, bucket, filename, upload_id, commit_details)
        else:
            # For small files or unknown size, stream directly to put_object using the file.stream (no buffering)
            logger.info('Using single PUT for %s (size=%s)', filename, str(file_size))
            # Ensure the stream is at the current position (Flask provides a fresh stream for the file)
            obj_client.put_object(namespace, bucket, filename, file.stream)

        # Create PAR for uploaded object and return URL
        oci_path = f'oci://{namespace}/{bucket}/{filename}'
        par_url = _get_par_url_for_oci(oci_path) if oci else f'/object_proxy?path={oci_path}'

        # Determine whether the client asked to auto-create embeddings for this upload
        embed_flag = request.form.get('embed', 'true').lower()
        should_embed = embed_flag not in ('0', 'false', 'no')

        queued_task_id = None
        if should_embed:
            # start background embedding task
            queued_task_id = start_embedding_background(namespace, bucket, filename, par_url)

        return jsonify({'task_id': queued_task_id, 'par_url': par_url, 'oci_path': oci_path})
    except Exception as e:
        logger.exception('Upload failed')
        return jsonify({'error': str(e)}), 500


def start_embedding_background(namespace, bucket, filename, par_url):
    """Start the background embedding + DB storage task and return the task_id."""
    task_id = str(uuid.uuid4())
    _upload_tasks[task_id] = {'status': 'pending', 'filename': filename, 'bucket': bucket, 'namespace': namespace, 'par_url': par_url}
    save_upload_tasks()

    def run_task(tid, namespace, bucket, filename, par_url):
        logger.info('Background task %s starting for %s', tid, filename)
        _upload_tasks[tid]['status'] = 'running'
        save_upload_tasks()
        try:
            # Download object to temp file
            import tempfile
            get_obj = None
            if oci:
                try:
                    config = _load_oci_config()
                    obj_client = oci.object_storage.ObjectStorageClient(config)
                    get_obj = obj_client.get_object(namespace, bucket, filename)
                except Exception:
                    # If object download fails, we still attempt embedding via PAR URL
                    logger.exception('Failed to download object for task %s; will proceed using PAR URL', tid)

            tmpfile_path = None
            if get_obj is not None:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1])
                tmpfile_path = tmp.name
                with open(tmpfile_path, 'wb') as f:
                    for chunk in get_obj.data.raw.stream(1024 * 64, decode_content=True):
                        f.write(chunk)

            # Create embeddings task with TwelveLabs (using PAR URL)
            from twelvelabs import TwelveLabs
            tw_client = TwelveLabs(api_key=os.getenv('TWELVE_LABS_API_KEY'))
            # Check if caller requested a preferred model for this task
            preferred_model = _upload_tasks.get(tid, {}).get('preferred_model')
            try:
                if preferred_model:
                    # store_video_embeddings.create_video_embeddings supports client+model in twelvelabs wrapper
                    created_task_id = create_video_embeddings(tw_client, par_url, model_name=preferred_model)
                else:
                    created_task_id = create_video_embeddings(tw_client, par_url)
            except TypeError:
                # older signature: create_video_embeddings(client, video_url)
                created_task_id = create_video_embeddings(tw_client, par_url)

            # Store embeddings in DB
            import oracledb
            conn = oracledb.connect(
                user=os.getenv('ORACLE_DB_USERNAME'),
                password=os.getenv('ORACLE_DB_PASSWORD'),
                dsn=os.getenv('ORACLE_DB_CONNECT_STRING'),
                config_dir=os.getenv('ORACLE_DB_WALLET_PATH'),
                wallet_location=os.getenv('ORACLE_DB_WALLET_PATH'),
                wallet_password=os.getenv('ORACLE_DB_WALLET_PASSWORD')
            )
            try:
                store_embeddings_in_db(conn, created_task_id, f'oci://{namespace}/{bucket}/{filename}')
            finally:
                conn.close()

            _upload_tasks[tid]['status'] = 'done'
            _upload_tasks[tid]['task_id'] = created_task_id
            save_upload_tasks()
            logger.info('Background task %s completed', tid)
        except Exception as e:
            logger.exception('Background task %s failed: %s', tid, e)
            _upload_tasks[tid]['status'] = 'failed'
            _upload_tasks[tid]['error'] = str(e)
            save_upload_tasks()

    EXECUTOR.submit(run_task, task_id, namespace, bucket, filename, par_url)
    return task_id


@app.route('/create_embedding', methods=['POST'])
def create_embedding():
    """Trigger embedding creation for an already-uploaded object.

    Accepts JSON body: { "oci_path": "oci://namespace/bucket/object" } or { "par_url": "https://..." }
    """
    payload = request.get_json() or {}
    oci_path = payload.get('oci_path')
    par_url = payload.get('par_url')
    if not oci_path and not par_url:
        return jsonify({'error': 'oci_path or par_url required'}), 400

    # If oci_path provided, parse namespace/bucket/object
    namespace = bucket = filename = None
    if oci_path:
        if not oci_path.startswith('oci://'):
            return jsonify({'error': 'oci_path must start with oci://'}), 400
        body = oci_path[len('oci://'):]
        parts = body.split('/', 2)
        if len(parts) == 3:
            namespace, bucket, filename = parts
        elif len(parts) == 2:
            # namespace will be resolved via obj client when running task; for now store bucket/filename
            bucket, filename = parts
        else:
            return jsonify({'error': 'invalid oci_path format'}), 400

    # If par_url not provided but oci_path is, create a PAR
    if not par_url and oci_path and oci:
        par_url = _get_par_url_for_oci(oci_path)

    # If we don't have namespace yet, try to get from PAR or resolve via OCI
    if not namespace and oci and oci_path and '/' in oci_path[len('oci://'):]:
        # Try resolving namespace via client
        try:
            config = _load_oci_config()
            obj_client = oci.object_storage.ObjectStorageClient(config)
            namespace = obj_client.get_namespace().data
        except Exception:
            namespace = None

    if not bucket or not filename:
        return jsonify({'error': 'Could not determine bucket/filename from oci_path'}), 400

    task_id = start_embedding_background(namespace, bucket, filename, par_url)
    return jsonify({'task_id': task_id})


@app.route('/create_embedding_marengo', methods=['POST'])
def create_embedding_marengo():
    """Trigger embedding creation using the Marengo model specifically.

    Accepts JSON body: { "oci_path": "oci://namespace/bucket/object" } or { "par_url": "https://..." }
    Returns: { task_id }
    """
    payload = request.get_json() or {}
    oci_path = payload.get('oci_path')
    par_url = payload.get('par_url')
    if not oci_path and not par_url:
        return jsonify({'error': 'oci_path or par_url required'}), 400

    # reuse create_embedding flow but instruct the background to prefer Marengo
    namespace = bucket = filename = None
    if oci_path:
        if not oci_path.startswith('oci://'):
            return jsonify({'error': 'oci_path must start with oci://'}), 400
        body = oci_path[len('oci://'):]
        parts = body.split('/', 2)
        if len(parts) == 3:
            namespace, bucket, filename = parts
        elif len(parts) == 2:
            bucket, filename = parts
        else:
            return jsonify({'error': 'invalid oci_path format'}), 400

    if not par_url and oci_path and oci:
        par_url = _get_par_url_for_oci(oci_path)

    if not namespace and oci and oci_path and '/' in oci_path[len('oci://'):]:
        try:
            config = _load_oci_config()
            obj_client = oci.object_storage.ObjectStorageClient(config)
            namespace = obj_client.get_namespace().data
        except Exception:
            namespace = None

    if not bucket or not filename:
        return jsonify({'error': 'Could not determine bucket/filename from oci_path'}), 400

    # start a background embedding task but pass a flag to prefer Marengo model
    task_id = start_embedding_background(namespace, bucket, filename, par_url)
    # record that caller wanted Marengo in the task metadata
    _upload_tasks[task_id]['preferred_model'] = 'Marengo-retrieval-2.7'
    save_upload_tasks()
    return jsonify({'task_id': task_id})


@app.route('/task_status/<task_id>')
def task_status(task_id):
    task = _upload_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'task not found'}), 404
    return jsonify(task)


@app.route('/create_embedding_from_upload', methods=['POST'])
def create_embedding_from_upload():
    """Create embeddings for a previously uploaded file.

    Accepts JSON: { "upload_task_id": "..." } OR { "oci_path": "oci://..." } OR { "par_url": "https://..." }
    Optional: preferred_model (e.g. 'Marengo-retrieval-2.7'), force (bool) to re-run even if task already done.
    """
    payload = request.get_json() or {}
    upload_task_id = payload.get('upload_task_id')
    oci_path = payload.get('oci_path')
    par_url = payload.get('par_url')
    preferred_model = payload.get('preferred_model')
    force = bool(payload.get('force', False))

    # If upload_task_id provided, look up metadata
    if upload_task_id:
        meta = _upload_tasks.get(upload_task_id)
        if not meta:
            return jsonify({'error': 'upload task not found'}), 404
        # Protect against duplicate embedding runs: if an embedding task_id already exists, require force to re-run
        existing_emb_task = meta.get('task_id')
        if existing_emb_task and not force:
            return jsonify({'error': 'embeddings already created or queued for this upload', 'existing_task_id': existing_emb_task}), 409
        # If the upload task does not already have an associated embedding, proceed
        oci_path = oci_path or meta.get('oci_path') or meta.get('object_path')
        par_url = par_url or meta.get('par_url')
        namespace = meta.get('namespace')
        bucket = meta.get('bucket')
        filename = meta.get('filename') or meta.get('object_name')
    else:
        namespace = bucket = filename = None

    # If caller provided oci_path, derive bucket/filename
    if oci_path and oci_path.startswith('oci://'):
        body = oci_path[len('oci://'):]
        parts = body.split('/', 2)
        if len(parts) == 3:
            namespace, bucket, filename = parts
        elif len(parts) == 2:
            bucket, filename = parts

    # If par_url not provided but we have oci_path and OCI is available, create a PAR
    if not par_url and oci_path and oci:
        par_url = _get_par_url_for_oci(oci_path)

    if not bucket or not filename:
        return jsonify({'error': 'Could not determine bucket/filename'}), 400

    # Optionally record preferred model in upload task metadata
    task_id = start_embedding_background(namespace, bucket, filename, par_url)
    if preferred_model:
        _upload_tasks[task_id]['preferred_model'] = preferred_model
        save_upload_tasks()

    return jsonify({'task_id': task_id})


@app.route('/list_uploads', methods=['GET'])
def list_uploads():
    """Return recent upload tasks for client-side selection."""
    try:
        items = []
        for k, v in _upload_tasks.items():
            entry = v.copy()
            entry['upload_task_id'] = k
            items.append(entry)
        # sort by created_at if present
        try:
            items.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        except Exception:
            pass
        return jsonify({'uploads': items})
    except Exception as e:
        logger.exception('Failed to list uploads')
        return jsonify({'error': str(e)}), 500


def _download_url_to_file(url, dst_path, timeout=60):
    """Compatibility wrapper that delegates to utils.download_url_to_file"""
    try:
        return utils_download_url_to_file(url, dst_path, timeout=timeout)
    except Exception as e:
        logger.exception('Failed to download %s', url)
        return False, str(e)


def _run_ffmpeg_cut(input_url, start, end, out_path):
    """Compatibility wrapper that delegates to utils.cut_segment"""
    return utils_cut_segment(input_url, start, end, out_path)


def _extract_frame_to_bytes(input_url, time_offset=0.5):
    """Extract a single frame as JPEG bytes from input_url at time_offset seconds using ffmpeg.
    Returns bytes on success, or (None, error) on failure.
    """
    # If input is oci://, resolve to PAR first
    if isinstance(input_url, str) and input_url.startswith('oci://'):
        try:
            input_url = _get_par_url_for_oci(input_url)
        except Exception:
            pass
    return utils_extract_frame_bytes(input_url, time_offset=time_offset)


def _concat_segments(segment_paths, out_path):
    return utils_concat_segments(segment_paths, out_path)


@app.route('/build_summary', methods=['POST'])
def build_summary():
    """Build a summarized video from query results.

    JSON body options:
      - queries: [ 'text query', ... ] (required)
      - duration_limit: int seconds (optional, default 60)
      - max_segments: int (optional, default 6)

    Returns: streamed MP4 response (Content-Type: video/mp4) or JSON error.
    """
    payload = request.get_json() or {}
    queries = payload.get('queries')
    if not queries:
        return jsonify({'error': 'queries required'}), 400

    duration_limit = int(payload.get('duration_limit', 60))
    max_segments = int(payload.get('max_segments', 6))

    # Enqueue asynchronous summary build job and return task_id immediately
    task_id = str(uuid.uuid4())
    _summary_tasks[task_id] = {'status': 'queued', 'queries': queries, 'duration_limit': duration_limit, 'max_segments': max_segments, 'created_at': int(time.time())}
    try:
        save_summary_tasks()
    except Exception:
        logger.exception('Failed to persist new summary task')

    def _run_build(tid, queries, duration_limit, max_segments, upload_flag):
        _update_summary_task(tid, status='running', started_at=int(time.time()))
        try:
            results_by_query = query_video_embeddings_multiple(queries)
            first_query = queries[0]
            results = results_by_query.get(first_query, [])
            if not results:
                _update_summary_task(tid, status='failed', error='no results found for query')
                return

            # Select segments
            selected = []
            total = 0.0
            for r in results:
                if len(selected) >= max_segments:
                    break
                s = float(r.get('start_time', 0))
                e = float(r.get('end_time', s + 5))
                dur = max(0.1, e - s)
                if total + dur > duration_limit and selected:
                    break
                selected.append({'video_file': r.get('video_file'), 'start': s, 'end': e, 'duration': dur})
                total += dur

            if not selected:
                _update_summary_task(tid, status='failed', error='no suitable segments selected')
                return

            tmp_dir = tempfile.mkdtemp(prefix='summary_')
            segment_paths = []
            for idx, seg in enumerate(selected):
                vf = seg['video_file']
                if isinstance(vf, str) and vf.startswith('oci://') and oci:
                    try:
                        download_url = _get_par_url_for_oci(vf)
                    except Exception:
                        download_url = vf
                else:
                    download_url = vf

                seg_out = os.path.join(tmp_dir, f'seg_{idx}.mp4')
                # Run ffmpeg to cut. Capture logs for diagnostics
                rc, out, err = _run_ffmpeg_cut(download_url, seg['start'], seg['end'], seg_out)
                if rc != 0:
                    # fallback to download + cut
                    input_tmp = os.path.join(tmp_dir, f'input_{idx}'+pathlib.Path(download_url).suffix)
                    ok, derr = _download_url_to_file(download_url, input_tmp)
                    if not ok:
                        _update_summary_task(tid, status='failed', error=f'download failed: {derr}')
                        return
                    rc2, out2, err2 = _run_ffmpeg_cut(input_tmp, seg['start'], seg['end'], seg_out)
                    out += '\n' + out2
                    err += '\n' + err2
                    try:
                        os.unlink(input_tmp)
                    except Exception:
                        pass
                # persist logs per-segment (append)
                seg_log = _summary_tasks.get(tid, {}).get('ffmpeg_logs', '')
                seg_log += f'--- segment {idx} (input={download_url}) stdout:\n{out}\nstderr:\n{err}\n'
                _update_summary_task(tid, ffmpeg_logs=seg_log)
                segment_paths.append(seg_out)

            out_path = os.path.join(tmp_dir, 'summary.mp4')
            rc_c, out_c, err_c = _concat_segments(segment_paths, out_path)
            # record concat logs
            concat_logs = _summary_tasks.get(tid, {}).get('ffmpeg_logs', '')
            concat_logs += f'--- concat stdout:\n{out_c}\nconcat stderr:\n{err_c}\n'
            _update_summary_task(tid, ffmpeg_logs=concat_logs)
            if rc_c != 0:
                _update_summary_task(tid, status='failed', error='ffmpeg concat failed')
                return

            if upload_flag:
                if not oci:
                    _update_summary_task(tid, status='failed', error='OCI SDK not available on server')
                    return
                config = _load_oci_config()
                obj_client = oci.object_storage.ObjectStorageClient(config)
                namespace = obj_client.get_namespace().data
                bucket = os.getenv('DEFAULT_OCI_BUCKET') or 'Media'
                object_name = f'summary_{uuid.uuid4().hex}.mp4'
                with open(out_path, 'rb') as f:
                    obj_client.put_object(namespace, bucket, object_name, f)
                oci_path = f'oci://{namespace}/{bucket}/{object_name}'
                par_url = _get_par_url_for_oci(oci_path) if oci else f'/object_proxy?path={oci_path}'
                _update_summary_task(tid, status='done', oci_path=oci_path, par_url=par_url, finished_at=int(time.time()))
            else:
                # store local path for retrieval
                _update_summary_task(tid, status='done', out_path=out_path, finished_at=int(time.time()))
        except Exception as e:
            logger.exception('Summary build task %s failed', tid)
            _update_summary_task(tid, status='failed', error=str(e))
        finally:
            try:
                EXECUTOR.submit(lambda p: shutil.rmtree(p), tmp_dir)
            except Exception:
                pass

    EXECUTOR.submit(_run_build, task_id, queries, duration_limit, max_segments, payload.get('upload', True))
    return jsonify({'task_id': task_id})



@app.route('/summary_status/<task_id>')
def summary_status(task_id):
    t = _summary_tasks.get(task_id)
    if not t:
        return jsonify({'error': 'task not found'}), 404
    # Only return lightweight metadata; ffmpeg_logs may be large but we include it for diagnostics
    return jsonify(t)


@app.route('/summary_output/<task_id>')
def summary_output(task_id):
    t = _summary_tasks.get(task_id)
    if not t:
        return jsonify({'error': 'task not found'}), 404
    # If OCI path present, redirect to PAR or proxy
    if t.get('oci_path') and t.get('par_url'):
        return jsonify({'oci_path': t.get('oci_path'), 'par_url': t.get('par_url')})
    # Otherwise if local out_path is present, stream with Range support
    out_path = t.get('out_path')
    if not out_path or not os.path.exists(out_path):
        return jsonify({'error': 'output not available'}), 404

    file_size = os.path.getsize(out_path)
    range_header = request.headers.get('Range')
    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not m:
            return jsonify({'error': 'invalid Range header'}), 400
        start = int(m.group(1))
        end = m.group(2)
        if end:
            end = int(end)
            if end >= file_size:
                end = file_size - 1
        else:
            end = file_size - 1
        if start >= file_size:
            resp = Response(status=416)
            resp.headers['Content-Range'] = f'bytes */{file_size}'
            return resp
        length = end - start + 1

        def generate_range(path, start, end):
            with open(path, 'rb') as f:
                f.seek(start)
                remaining = end - start + 1
                chunk_size = 1024 * 64
                while remaining > 0:
                    read_size = chunk_size if remaining >= chunk_size else remaining
                    chunk = f.read(read_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        try:
            import mimetypes
            content_type = mimetypes.guess_type(out_path)[0] or 'application/octet-stream'
        except Exception:
            content_type = 'application/octet-stream'

        resp = Response(generate_range(out_path, start, end), status=206, content_type=content_type)
        resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        resp.headers['Accept-Ranges'] = 'bytes'
        resp.headers['Content-Length'] = str(length)
        return resp

    def generate():
        with open(out_path, 'rb') as f:
            while True:
                chunk = f.read(1024 * 64)
                if not chunk:
                    break
                yield chunk

    try:
        import mimetypes
        content_type = mimetypes.guess_type(out_path)[0] or 'application/octet-stream'
    except Exception:
        content_type = 'application/octet-stream'

    resp = Response(generate(), content_type=content_type)
    resp.headers['Content-Length'] = str(file_size)
    resp.headers['Accept-Ranges'] = 'bytes'
    return resp


@app.route('/execute_plan', methods=['POST'])
def execute_plan():
    """Execute a validated Pegasus plan.

    Accepts JSON body: { plan: {plan:[{video_file,start,end,...}], narrative:...}, upload: bool }
    Enqueues a background task that performs cuts, concatenation, and optional upload.
    Returns { task_id }
    """
    payload = request.get_json() or {}
    plan = payload.get('plan')
    upload_flag = payload.get('upload', True)
    if not plan:
        return jsonify({'error': 'plan required'}), 400

    # Normalize and validate server-side if helpers available
    if normalize_plan:
        try:
            plan = normalize_plan(plan)
        except Exception:
            pass
    if validate_edit_plan:
        ok, errs = validate_edit_plan(plan, duration_limit=payload.get('duration_limit'), max_segments=payload.get('max_segments'))
        if not ok:
            return jsonify({'error': 'plan validation failed', 'details': errs}), 400

    # Create a summary task and enqueue execution
    task_id = str(uuid.uuid4())
    _summary_tasks[task_id] = {'status': 'queued', 'plan': plan, 'created_at': int(time.time())}
    save_summary_tasks()

    def _run_plan(tid, plan_obj, upload_flag):
        _update_summary_task(tid, status='running', started_at=int(time.time()))
        tmp_dir = tempfile.mkdtemp(prefix='execplan_')
        try:
            items = plan_obj.get('plan', [])
            segment_paths = []
            total = 0.0
            for idx, item in enumerate(items):
                vf = item.get('video_file')
                s = float(item.get('start', 0))
                e = float(item.get('end', s + 5))
                dur = max(0.0, e - s)
                total += dur

                # Resolve video_file to a download URL if it's oci://
                download_url = vf
                if isinstance(vf, str) and vf.startswith('oci://') and oci:
                    try:
                        download_url = _get_par_url_for_oci(vf)
                    except Exception:
                        download_url = vf

                seg_out = os.path.join(tmp_dir, f'seg_{idx}.mp4')
                rc, out, err = _run_ffmpeg_cut(download_url, s, e, seg_out)
                if rc != 0:
                    # fallback: download then cut
                    input_tmp = os.path.join(tmp_dir, f'input_{idx}' + pathlib.Path(download_url).suffix)
                    ok, derr = _download_url_to_file(download_url, input_tmp)
                    if not ok:
                        _update_summary_task(tid, status='failed', error=f'download failed for item {idx}: {derr}')
                        return
                    rc2, out2, err2 = _run_ffmpeg_cut(input_tmp, s, e, seg_out)
                    out += '\n' + out2
                    err += '\n' + err2
                    try:
                        os.unlink(input_tmp)
                    except Exception:
                        pass

                # append logs
                logs = _summary_tasks.get(tid, {}).get('ffmpeg_logs', '')
                logs += f'--- item {idx} stdout:\n{out}\nstderr:\n{err}\n'
                _update_summary_task(tid, ffmpeg_logs=logs)
                segment_paths.append(seg_out)

            # concat
            out_path = os.path.join(tmp_dir, 'summary.mp4')
            rc_c, out_c, err_c = _concat_segments(segment_paths, out_path)
            logs = _summary_tasks.get(tid, {}).get('ffmpeg_logs', '')
            logs += f'--- concat stdout:\n{out_c}\nconcat stderr:\n{err_c}\n'
            _update_summary_task(tid, ffmpeg_logs=logs)
            if rc_c != 0:
                _update_summary_task(tid, status='failed', error='ffmpeg concat failed')
                return

            if upload_flag:
                if not oci:
                    _update_summary_task(tid, status='failed', error='OCI SDK not available')
                    return
                try:
                    config = _load_oci_config()
                    obj_client = oci.object_storage.ObjectStorageClient(config)
                    namespace = obj_client.get_namespace().data
                    bucket = os.getenv('DEFAULT_OCI_BUCKET') or 'Media'
                    object_name = f'pegasus_summary_{uuid.uuid4().hex}.mp4'
                    with open(out_path, 'rb') as f:
                        obj_client.put_object(namespace, bucket, object_name, f)
                    oci_path = f'oci://{namespace}/{bucket}/{object_name}'
                    par_url = _get_par_url_for_oci(oci_path) if oci else f'/object_proxy?path={oci_path}'
                    _update_summary_task(tid, status='done', oci_path=oci_path, par_url=par_url, finished_at=int(time.time()))
                except Exception as e:
                    _update_summary_task(tid, status='failed', error=str(e))
                    return
            else:
                _update_summary_task(tid, status='done', out_path=out_path, finished_at=int(time.time()))
        except Exception as e:
            logger.exception('Plan execution %s failed', tid)
            _update_summary_task(tid, status='failed', error=str(e))
        finally:
            try:
                # cleanup in background after a small delay to allow downloads
                def _cleanup(p):
                    try: shutil.rmtree(p)
                    except Exception: pass
                EXECUTOR.submit(lambda p: shutil.rmtree(p), tmp_dir)
            except Exception:
                pass

    EXECUTOR.submit(_run_plan, task_id, plan, upload_flag)
    return jsonify({'task_id': task_id})


@app.route('/thumbnail_preview')
def thumbnail_preview():
    """Return a base64 JPEG data URL for a single frame from the provided video path.

    Query params: path (oci:// or http/https or local), time (seconds, optional)
    Returns JSON: { data_url: 'data:image/jpeg;base64,...' }
    """
    path = request.args.get('path')
    time_s = float(request.args.get('time', '0.5'))
    if not path:
        return jsonify({'error': 'path required'}), 400
    try:
        # If local and under MEDIA_ROOT, ensure allowed
        if os.path.isabs(path) and MEDIA_ROOT:
            if os.path.commonpath([os.path.abspath(path), os.path.abspath(MEDIA_ROOT)]) != os.path.abspath(MEDIA_ROOT):
                return jsonify({'error': 'path not allowed'}), 403

        data, err = _extract_frame_to_bytes(path, time_s)
        if err:
            return jsonify({'error': err}), 500
        b64 = base64.b64encode(data).decode('ascii')
        data_url = 'data:image/jpeg;base64,' + b64
        return jsonify({'data_url': data_url})
    except Exception as e:
        logger.exception('thumbnail_preview error')
        return jsonify({'error': str(e)}), 500


# ==================== PHOTO ALBUM ENDPOINTS ====================

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    """Upload a photo to OCI for later embedding creation
    
    Accepts multipart/form-data with 'photo' file and 'album_name'
    Returns: { photo_url, album_name }
    """
    try:
        from store_photo_embeddings import create_photo_embedding, store_photo_embedding_in_db
        from PIL import Image
    except Exception as e:
        return jsonify({'error': f'Photo module not available: {e}'}), 500
    
    if 'photo' not in request.files:
        return jsonify({'error': 'photo file required'}), 400
    
    photo = request.files['photo']
    album_name = request.form.get('album_name', 'default')
    
    if photo.filename == '':
        return jsonify({'error': 'empty filename'}), 400
    
    # Upload to OCI if available
    if not oci:
        return jsonify({'error': 'OCI SDK not available'}), 500
    
    try:
        config = _load_oci_config()
        obj_client = oci.object_storage.ObjectStorageClient(config)
        namespace = obj_client.get_namespace().data
        bucket = os.getenv('OCI_BUCKET', 'Media')
        
        # Save to temp file first
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(photo.filename)[1]) as tmp:
            photo.save(tmp.name)
            tmp_path = tmp.name
        
        # Resize image if too large for TwelveLabs (5.2 MB limit)
        max_size_mb = 5.0  # Use 5 MB to have some buffer under the 5.2 MB limit
        
        if os.path.getsize(tmp_path) > max_size_mb * 1024 * 1024:
            logger.info(f"Resizing large image: {photo.filename} ({os.path.getsize(tmp_path) / (1024*1024):.1f} MB)")
            
            # Open and resize image
            with Image.open(tmp_path) as img:
                # Convert to RGB if necessary (for PNG with alpha channel, etc.)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Calculate new size maintaining aspect ratio
                original_size = img.size
                quality = 85
                scale_factor = 0.8
                
                # Try progressively smaller sizes until under limit
                for attempt in range(5):
                    new_width = int(original_size[0] * scale_factor)
                    new_height = int(original_size[1] * scale_factor)
                    
                    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    
                    # Save to temp file and check size
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_resized:
                        resized_img.save(tmp_resized.name, 'JPEG', quality=quality, optimize=True)
                        tmp_resized_path = tmp_resized.name
                    
                    new_size = os.path.getsize(tmp_resized_path)
                    logger.info(f"Attempt {attempt+1}: {new_width}x{new_height}, quality={quality}, size={new_size/(1024*1024):.1f}MB")
                    
                    if new_size <= max_size_mb * 1024 * 1024:
                        # Size is good, replace original
                        os.unlink(tmp_path)
                        tmp_path = tmp_resized_path
                        # Update filename to .jpg
                        base_name = os.path.splitext(photo.filename)[0]
                        photo.filename = f"{base_name}_resized.jpg"
                        logger.info(f"Image resized successfully to {new_size/(1024*1024):.1f}MB")
                        break
                    else:
                        # Too large still, try smaller
                        os.unlink(tmp_resized_path)
                        scale_factor *= 0.8
                        quality = max(60, quality - 10)
                else:
                    # If we couldn't get it small enough after 5 attempts
                    logger.warning(f"Could not resize image {photo.filename} to under {max_size_mb}MB")
                    return jsonify({'error': f'Image too large and could not be resized to under {max_size_mb}MB'}), 400
        
        # Upload to OCI
        object_name = f"photos/{album_name}/{photo.filename}"
        with open(tmp_path, 'rb') as f:
            obj_client.put_object(namespace, bucket, object_name, f)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Create PAR URL
        oci_path = f"oci://{namespace}/{bucket}/{object_name}"
        par_url = _get_par_url_for_oci(oci_path)
        
        return jsonify({
            'photo_url': par_url,
            'oci_path': oci_path,
            'album_name': album_name,
            'filename': photo.filename
        })
        
    except Exception as e:
        logger.exception('Failed to upload photo')
        return jsonify({'error': str(e)}), 500


@app.route('/create_photo_embeddings', methods=['POST'])
def create_photo_embeddings_endpoint():
    """Create enhanced Marengo embeddings for photos using Oracle VECTOR
    
    Accepts JSON: {
        "album_name": "vacation2024",
        "photo_urls": ["https://...", "oci://..."],
        "batch_size": 50  // optional
    }
    Returns: { success, failed, errors, processing_time, embeddings_created, embeddings_stored }
    """
    try:
        from store_photo_embeddings_vector import create_photo_embeddings_for_album_enhanced
    except Exception as e:
        # Fallback to original photo embeddings
        try:
            from store_photo_embeddings import create_photo_embeddings_for_album
            logger.warning("Using fallback photo embeddings (BLOB-based)")
        except Exception as e2:
            return jsonify({'error': f'No photo embedding module available: {e}, {e2}'}), 500
    
    payload = request.get_json() or {}
    album_name = payload.get('album_name')
    photo_urls = payload.get('photo_urls', [])
    batch_size = payload.get('batch_size', 50)
    
    if not album_name:
        return jsonify({'error': 'album_name required'}), 400
    if not photo_urls:
        return jsonify({'error': 'photo_urls required (list)'}), 400
    
    try:
        # Convert oci:// paths to PAR URLs
        resolved_urls = []
        for url in photo_urls:
            if url.startswith('oci://'):
                resolved_urls.append(_get_par_url_for_oci(url))
            else:
                resolved_urls.append(url)

        # Use enhanced VECTOR embeddings if available
        if 'create_photo_embeddings_for_album_enhanced' in locals():
            results = create_photo_embeddings_for_album_enhanced(
                album_name, resolved_urls, batch_size=batch_size
            )
        else:
            # Fallback to original embeddings
            results = create_photo_embeddings_for_album(album_name, resolved_urls)
        
        # Include mapping of original -> resolved URL for visibility
        mapping = {orig: resolved for orig, resolved in zip(photo_urls, resolved_urls)}
        results['resolved_urls'] = mapping
        return jsonify(results)

    except Exception as e:
        logger.exception('Failed to create photo embeddings')
        return jsonify({'error': str(e)}), 500


@app.route('/search_photos', methods=['POST'])
def search_photos_endpoint():
    """Enhanced search for photos using Oracle VECTOR
    
    Accepts JSON: {
        "query": "sunset beach",
        "album_name": "vacation2024",  // optional
        "top_k": 10,  // optional
        "similarity_type": "COSINE",  // optional
        "min_similarity": 0.7  // optional
    }
    Returns: { results: [{photo_file, album_name, similarity_score}] }
    """
    try:
        from query_photo_embeddings_vector import search_photos_multiple_enhanced
    except Exception as e:
        # Fallback to original photo search
        try:
            from query_photo_embeddings import search_photos
            logger.warning("Using fallback photo search (BLOB-based)")
        except Exception as e2:
            return jsonify({'error': f'No photo query module available: {e}, {e2}'}), 500
    
    payload = request.get_json() or {}
    queries = payload.get('queries')
    if not queries:
        q = payload.get('query')
        if not q:
            return jsonify({'error': 'query required'}), 400
        # Full phrase + individual words
        words = [w for w in re.split(r'\s+', q.strip()) if w]
        seen = set()
        combined = []
        if q not in seen:
            combined.append(q); seen.add(q)
        for w in words:
            if w not in seen:
                combined.append(w); seen.add(w)
        queries = combined

    album_name = payload.get('album_name')
    top_k = payload.get('top_k', 10)
    similarity_type = payload.get('similarity_type', 'COSINE')
    min_similarity = payload.get('min_similarity')

    try:
        # Use enhanced VECTOR search if available
        if 'search_photos_multiple_enhanced' in locals():
            results_by_query = search_photos_multiple_enhanced(
                queries, album_name=album_name, top_k=top_k, similarity_type=similarity_type
            )
            
            # Apply similarity threshold if specified
            if min_similarity is not None:
                for query in results_by_query:
                    if similarity_type == 'COSINE':
                        results_by_query[query] = [
                            r for r in results_by_query[query] 
                            if r['similarity_score'] <= (1.0 - min_similarity)
                        ]
        else:
            # Fallback to original search
            results_by_query = {}
            for qq in queries:
                results_by_query[qq] = search_photos(qq, album_name=album_name, top_k=top_k)

        # Normalize into by_query mapping with consistent object shape
        by_query = {}
        for qq, lst in results_by_query.items():
            norm_photos = [ normalize_photo_entry(p) for p in (lst or []) ]
            by_query[qq] = {
                'photos': norm_photos,
                'videos': []
            }
        return jsonify({'by_query': by_query})
    except Exception as e:
        logger.exception('Failed to search photos')
        return jsonify({'error': str(e)}), 500


@app.route('/search_unified', methods=['POST'])
def search_unified_endpoint():
    """Enhanced unified search across photos and videos using Oracle VECTOR
    
    Accepts JSON: {
        "queries": ["sunset", "beach"],  // or single string
        "top_k_photos": 10,  // optional
        "top_k_videos": 10,  // optional
        "album_name": "vacation2024",  // optional, for photos only
        "similarity_type": "COSINE",  // optional: COSINE, DOT, EUCLIDEAN
        "min_similarity": 0.7  // optional similarity threshold
    }
    Returns: {
        photo_results: {query: [results]},
        video_results: {query: [results]},
        summary: {query: {photo_count, video_count, total_count}},
        performance: {total_time, photo_time, video_time, parallel_execution}
    }
    """
    try:
        from unified_search_vector import unified_search_enhanced
    except Exception as e:
        # Fallback to original unified search
        try:
            from unified_search import unified_search
            logger.warning("Using fallback unified search (BLOB-based)")
        except Exception as e2:
            return jsonify({'error': f'No unified search module available: {e}, {e2}'}), 500
    
    payload = request.get_json() or {}
    queries = payload.get('queries')
    if not queries:
        q = payload.get('query')
        if not q:
            return jsonify({'error': 'queries required'}), 400
        words = [w for w in re.split(r'\s+', q.strip()) if w]
        seen = set(); combined = []
        if q not in seen:
            combined.append(q); seen.add(q)
        for w in words:
            if w not in seen:
                combined.append(w); seen.add(w)
        queries = combined

    top_k_photos = payload.get('top_k_photos', 10)
    top_k_videos = payload.get('top_k_videos', 10)
    album_name = payload.get('album_name')
    similarity_type = payload.get('similarity_type', 'COSINE')
    min_similarity = payload.get('min_similarity')

    try:
        # Use enhanced VECTOR search if available
        if 'unified_search_enhanced' in locals():
            results = unified_search_enhanced(
                query_texts=queries,
                top_k_photos=top_k_photos,
                top_k_videos=top_k_videos,
                album_name=album_name,
                similarity_type=similarity_type,
                min_similarity=min_similarity
            )
            # Results are already in the correct format
            return jsonify(results)
        else:
            # Fallback to original search
            results = unified_search(
                queries,
                top_k_photos=top_k_photos,
                top_k_videos=top_k_videos,
                album_name=album_name
            )
            # Convert unified_search result into by_query mapping for consistent client format
            photos = results.get('photos', {})
            videos = results.get('videos', {})
            summary = results.get('summary', {})

        by_query = {}
        for q in queries:
            raw_photos = photos.get(q, []) or []
            norm_photos = [ normalize_photo_entry(p) for p in raw_photos ]
            raw_videos = videos.get(q, []) or []
            norm_videos = [ normalize_video_entry(v) for v in raw_videos ]
            by_query[q] = {
                'photos': norm_photos,
                'videos': norm_videos
            }

        out = {'by_query': by_query, 'summary': summary}
        return jsonify(out)
    except Exception as e:
        logger.exception('Failed to perform unified search')
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health_check():
    """Health check endpoint for Oracle VECTOR system
    
    Returns comprehensive system health status
    """
    try:
        from utils.db_utils_vector import get_health_status
        health = get_health_status()
        
        # Add additional system checks
        health['flask_status'] = 'healthy'
        health['twelvelabs_api'] = 'configured' if os.getenv('TWELVE_LABS_API_KEY') else 'not_configured'
        
        # Determine overall status
        overall_status = 'healthy'
        if health.get('database') != 'healthy':
            overall_status = 'degraded'
        if not health.get('config_valid'):
            overall_status = 'unhealthy'
            
        health['overall_status'] = overall_status
        
        status_code = 200 if overall_status == 'healthy' else 503
        return jsonify(health), status_code
        
    except Exception as e:
        return jsonify({
            'overall_status': 'unhealthy',
            'error': str(e),
            'flask_status': 'healthy'
        }), 503


@app.route('/list_albums')
def list_albums_endpoint():
    """List all unique album names from photo_embeddings table
    
    Returns: { albums: [album_name, ...] }
    """
    try:
        # Check basic env configuration first
        user = os.getenv('ORACLE_DB_USERNAME')
        pwd = os.getenv('ORACLE_DB_PASSWORD')
        dsn = os.getenv('ORACLE_DB_CONNECT_STRING')
        wallet = os.getenv('ORACLE_DB_WALLET_PATH')
        wallet_pw = os.getenv('ORACLE_DB_WALLET_PASSWORD')

        if not (user and pwd and dsn):
            logger.warning('Oracle DB not fully configured (ORACLE_DB_USERNAME/ORACLE_DB_PASSWORD/ORACLE_DB_CONNECT_STRING missing)')
            return jsonify({'albums': [], 'count': 0, 'warning': 'Oracle DB not configured (set ORACLE_DB_USERNAME, ORACLE_DB_PASSWORD and ORACLE_DB_CONNECT_STRING)'}), 200

        try:
            connection = oracledb.connect(
                user=user,
                password=pwd,
                dsn=dsn,
                wallet_location=wallet,
                wallet_password=wallet_pw
            )

            cursor = connection.cursor()
            cursor.execute("SELECT DISTINCT album_name FROM photo_embeddings ORDER BY album_name")
            albums = [row[0] for row in cursor]

            cursor.close()
            connection.close()

            return jsonify({'albums': albums, 'count': len(albums)})
        except Exception as e:
            # Handle common Oracle client errors like missing wallet/config (DPY-4027) gracefully
            msg = str(e)
            logger.exception('Failed to list albums')
            if 'DPY-4027' in msg or 'no configuration directory' in msg or 'no such file or directory' in msg:
                return jsonify({'albums': [], 'count': 0, 'warning': 'Oracle client configuration not found (missing wallet/tnsnames). Set ORACLE_DB_WALLET_PATH or provide a connect string).'}), 200
            return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.exception('Unexpected error in list_albums_endpoint')
        return jsonify({'error': str(e)}), 500


# ==================== UNIFIED ALBUM ENDPOINTS ====================

@app.route('/upload_unified', methods=['POST'])
def upload_unified():
    """Upload media (photo or video) to unified album system
    
    Accepts multipart/form-data with:
    - 'mediaFile': photo or video file 
    - 'album_name': album name (required)
    - 'auto_embed': whether to auto-create embeddings (default: true)
    
    Returns: { media_id, album_name, file_type, oci_path, par_url, task_id }
    """
    # Debug logging
    logger.info(f"Upload request - Files: {list(request.files.keys())}")
    logger.info(f"Upload request - Form: {dict(request.form)}")
    
    if not UNIFIED_ALBUM_AVAILABLE or album_manager is None:
        return jsonify({'error': 'Unified album module not available'}), 500
    
    if 'mediaFile' not in request.files:
        return jsonify({'error': 'mediaFile is required'}), 400
    
    file = request.files['mediaFile']
    album_name = request.form.get('album_name')
    auto_embed = request.form.get('auto_embed', 'true').lower() in ('true', '1', 'yes')
    
    if not file.filename:
        return jsonify({'error': 'Invalid filename'}), 400
    if not album_name:
        return jsonify({'error': 'album_name is required'}), 400
    
    if not oci:
        return jsonify({'error': 'OCI SDK not configured on server'}), 500

    try:
        # Detect file type
        file_type, mime_type = album_manager.detect_file_type(file.filename)
        if file_type == 'unknown':
            return jsonify({'error': f'Unsupported file type: {mime_type}'}), 400
        
        config = _load_oci_config()
        obj_client = oci.object_storage.ObjectStorageClient(config)
        namespace = obj_client.get_namespace().data
        bucket = os.getenv('DEFAULT_OCI_BUCKET', 'Media')
        
        # Create album-specific object path
        object_name = f"albums/{album_name}/{file_type}s/{file.filename}"
        
        # Handle large files with multipart upload if needed
        file_size = getattr(file, 'content_length', None) or request.content_length
        
        if file_size and file_size > MULTIPART_THRESHOLD:
            logger.info('Using multipart upload for %s (size=%d)', file.filename, file_size)
            create_details = oci.object_storage.models.CreateMultipartUploadDetails(object=object_name)
            mpu = obj_client.create_multipart_upload(namespace, bucket, create_details)
            upload_id = mpu.data.upload_id
            part_num = 1
            parts = []
            while True:
                chunk = file.stream.read(10 * 1024 * 1024)  # 10MB parts
                if not chunk:
                    break
                resp = obj_client.upload_part(namespace, bucket, object_name, upload_id, part_num, chunk)
                etag = resp.headers.get('etag') if resp and hasattr(resp, 'headers') else None
                part_detail = oci.object_storage.models.CommitMultipartUploadPartDetails(part_num=part_num, etag=etag)
                parts.append(part_detail)
                part_num += 1
            commit_details = oci.object_storage.models.CommitMultipartUploadDetails(parts_to_commit=parts)
            obj_client.commit_multipart_upload(namespace, bucket, object_name, upload_id, commit_details)
        else:
            logger.info('Using single PUT for %s (size=%s)', file.filename, str(file_size))
            obj_client.put_object(namespace, bucket, object_name, file.stream)
        
        # Create OCI path and PAR URL
        oci_path = f'oci://{namespace}/{bucket}/{object_name}'
        par_url = _get_par_url_for_oci(oci_path)
        
        # Store metadata in unified album system
        media_id = album_manager.store_media_metadata(
            album_name=album_name,
            file_name=file.filename,
            file_path=oci_path,
            file_type=file_type,
            mime_type=mime_type,
            file_size=file_size,
            oci_namespace=namespace,
            oci_bucket=bucket,
            oci_object_path=object_name
        )
        
        task_id = None
        if auto_embed and media_id:
            # Start background embedding creation
            task_id = str(uuid.uuid4())
            _upload_tasks[task_id] = {
                'status': 'pending',
                'media_id': media_id,
                'album_name': album_name,
                'filename': file.filename,
                'file_type': file_type,
                'oci_path': oci_path,
                'par_url': par_url
            }
            save_upload_tasks()
            
            def run_unified_embedding_task(tid, media_id, oci_path, file_type, album_name):
                logger.info('Background unified embedding task %s starting for %s', tid, file.filename)
                _upload_tasks[tid]['status'] = 'running'
                save_upload_tasks()
                
                try:
                    if file_type == 'video':
                        # Create video embeddings
                        embedding_ids = create_unified_embedding(oci_path, file_type, album_name)
                        if embedding_ids:
                            _upload_tasks[tid]['status'] = 'done'
                            _upload_tasks[tid]['embedding_ids'] = embedding_ids
                        else:
                            _upload_tasks[tid]['status'] = 'failed'
                            _upload_tasks[tid]['error'] = 'Video embedding creation failed'
                    
                    elif file_type == 'photo':
                        # Create photo embedding
                        embedding_id = create_unified_embedding(oci_path, file_type, album_name)
                        if embedding_id:
                            _upload_tasks[tid]['status'] = 'done'
                            _upload_tasks[tid]['embedding_id'] = embedding_id
                        else:
                            _upload_tasks[tid]['status'] = 'failed'
                            _upload_tasks[tid]['error'] = 'Photo embedding creation failed'
                    
                    save_upload_tasks()
                    logger.info('Background unified embedding task %s completed', tid)
                    
                except Exception as e:
                    logger.exception('Background unified embedding task %s failed: %s', tid, e)
                    _upload_tasks[tid]['status'] = 'failed'
                    _upload_tasks[tid]['error'] = str(e)
                    save_upload_tasks()
            
            EXECUTOR.submit(run_unified_embedding_task, task_id, media_id, oci_path, file_type, album_name)
        
        return jsonify({
            'media_id': media_id,
            'album_name': album_name,
            'file_type': file_type,
            'oci_path': oci_path,
            'par_url': par_url,
            'task_id': task_id,
            'auto_embed': auto_embed
        })
        
    except Exception as e:
        logger.exception('Unified upload failed')
        return jsonify({'error': str(e)}), 500


@app.route('/list_unified_albums')
def list_unified_albums():
    """List all albums from unified album system with counts
    
    Returns: { albums: [{album_name, total_items, photo_count, video_count, embedded_count, created_at, updated_at}] }
    """
    try:
        logger.info("📋 Album listing request received")
        
        if not UNIFIED_ALBUM_AVAILABLE or album_manager is None:
            logger.error("❌ Unified album manager not available")
            return jsonify({'error': 'Album manager not available', 'albums': [], 'count': 0}), 500
        
        logger.info("🔍 Fetching unified albums list...")
        albums = album_manager.list_albums()
        logger.info(f"✅ Found {len(albums)} albums")
        
        # Convert datetime objects to strings for JSON serialization
        albums_serializable = []
        for album in albums:
            album_copy = album.copy()
            if 'created_at' in album_copy and album_copy['created_at']:
                album_copy['created_at'] = album_copy['created_at'].isoformat()
            if 'updated_at' in album_copy and album_copy['updated_at']:
                album_copy['updated_at'] = album_copy['updated_at'].isoformat()
            albums_serializable.append(album_copy)
        
        response_data = {'albums': albums_serializable, 'count': len(albums_serializable)}
        logger.info(f"📤 Returning {len(albums_serializable)} albums")
        return jsonify(response_data)
        
    except Exception as e:
        logger.exception('❌ Failed to list unified albums')
        return jsonify({'error': str(e), 'albums': [], 'count': 0}), 500


@app.route('/get_album_contents/<album_name>')
def get_album_contents(album_name):
    """Get all media (photos and videos) in a specific album
    
    Returns: { contents: [{id, file_name, file_type, has_embedding, ...}] }
    """
    try:
        if not UNIFIED_ALBUM_AVAILABLE or album_manager is None:
            return jsonify({'error': 'Album manager not available', 'contents': []}), 500
            
        contents = album_manager.get_album_contents(album_name)
        
        # Normalize file paths to browser-accessible URLs
        for item in contents:
            if item.get('file_path') and item['file_path'].startswith('oci://'):
                try:
                    item['browser_url'] = _get_par_url_for_oci(item['file_path'])
                except Exception:
                    item['browser_url'] = f"/object_proxy?path={item['file_path']}"
            else:
                item['browser_url'] = item.get('file_path', '')
        
        return jsonify({'contents': contents, 'album_name': album_name, 'count': len(contents)})
    except Exception as e:
        logger.exception('Failed to get album contents')
        return jsonify({'error': str(e)}), 500


@app.route('/search_unified_album', methods=['POST'])
def search_unified_album():
    """Search across unified albums using vector similarity
    
    Accepts JSON: {
        "query": "sunset beach",
        "album_name": "vacation2024",  // optional
        "file_type": "photo",  // optional: photo, video
        "top_k": 10  // optional
    }
    Returns: { results: [{id, album_name, file_name, file_type, distance, browser_url, ...}] }
    """
    if not UNIFIED_ALBUM_AVAILABLE or album_manager is None:
        return jsonify({'error': 'Unified album module not available'}), 500
    
    payload = request.get_json() or {}
    query = payload.get('query')
    if not query:
        return jsonify({'error': 'query required'}), 400
    
    album_name = payload.get('album_name')
    file_type = payload.get('file_type')
    top_k = payload.get('top_k', 10)
    
    try:
        results = album_manager.search_unified_album(
            query_text=query,
            album_name=album_name,
            file_type=file_type,
            top_k=top_k
        )
        
        # Normalize file paths to browser-accessible URLs
        for result in results:
            if result.get('file_path') and result['file_path'].startswith('oci://'):
                try:
                    result['browser_url'] = _get_par_url_for_oci(result['file_path'])
                except Exception:
                    result['browser_url'] = f"/object_proxy?path={result['file_path']}"
            else:
                result['browser_url'] = result.get('file_path', '')
        
        return jsonify({'results': results, 'query': query, 'count': len(results)})
    except Exception as e:
        logger.exception('Failed to search unified album')
        return jsonify({'error': str(e)}), 500


@app.route('/create_unified_embeddings', methods=['POST'])
def create_unified_embeddings():
    """Create embeddings for media in unified album system
    
    Accepts JSON: {
        "media_ids": [1, 2, 3],  // specific media IDs
        "album_name": "vacation2024",  // or all media in album
        "file_type": "photo"  // optional: photo, video
    }
    Returns: { task_id, processing_count }
    """
    if not UNIFIED_ALBUM_AVAILABLE or album_manager is None or create_unified_embedding is None:
        return jsonify({'error': 'Unified album module not available'}), 500
    
    payload = request.get_json() or {}
    media_ids = payload.get('media_ids', [])
    album_name = payload.get('album_name')
    file_type = payload.get('file_type')
    
    if not media_ids and not album_name:
        return jsonify({'error': 'media_ids or album_name required'}), 400
    
    try:
        # If album_name provided, get all media in that album
        if album_name and not media_ids:
            contents = album_manager.get_album_contents(album_name)
            media_items = contents
            if file_type:
                media_items = [item for item in media_items if item['file_type'] == file_type]
        else:
            # Get specific media items by ID
            media_items = []
            # TODO: Implement get_media_by_ids in album_manager
        
        if not media_items:
            return jsonify({'error': 'No media items found'}), 400
        
        # Start background embedding task
        task_id = str(uuid.uuid4())
        _upload_tasks[task_id] = {
            'status': 'pending',
            'type': 'unified_embeddings',
            'album_name': album_name,
            'file_type': file_type,
            'processing_count': len(media_items)
        }
        save_upload_tasks()
        
        def run_unified_embedding_batch(tid, media_items):
            logger.info('Background unified embedding batch %s starting for %d items', tid, len(media_items))
            _upload_tasks[tid]['status'] = 'running'
            save_upload_tasks()
            
            try:
                successful = 0
                failed = 0
                
                for item in media_items:
                    try:
                        file_path = item['file_path']
                        file_type = item['file_type']
                        album_name = item['album_name']
                        
                        if item.get('has_embedding') == 'Y':
                            logger.info(f"Skipping {item['file_name']} - already has embedding")
                            continue
                        
                        result = create_unified_embedding(file_path, file_type, album_name)
                        if result:
                            successful += 1
                        else:
                            failed += 1
                            
                    except Exception as e:
                        logger.exception(f"Failed to create embedding for {item.get('file_name', 'unknown')}")
                        failed += 1
                
                _upload_tasks[tid]['status'] = 'done'
                _upload_tasks[tid]['successful'] = successful
                _upload_tasks[tid]['failed'] = failed
                save_upload_tasks()
                logger.info('Background unified embedding batch %s completed: %d successful, %d failed', tid, successful, failed)
                
            except Exception as e:
                logger.exception('Background unified embedding batch %s failed: %s', tid, e)
                _upload_tasks[tid]['status'] = 'failed'
                _upload_tasks[tid]['error'] = str(e)
                save_upload_tasks()
        
        EXECUTOR.submit(run_unified_embedding_batch, task_id, media_items)
        
        return jsonify({
            'task_id': task_id,
            'processing_count': len(media_items),
            'album_name': album_name,
            'file_type': file_type
        })
        
    except Exception as e:
        logger.exception('Failed to create unified embeddings')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Configuration for mishras.online domain
    host = os.getenv('FLASK_HOST', '0.0.0.0')  # Listen on all interfaces
    port = int(os.getenv('FLASK_PORT', '8080'))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Set server name for proper URL generation
    if not app.config.get('SERVER_NAME'):
        server_name = os.getenv('SERVER_NAME', 'mishras.online:8080')
        app.config['SERVER_NAME'] = server_name
    
    # Security settings for production domain
    app.config['PREFERRED_URL_SCHEME'] = os.getenv('URL_SCHEME', 'https')
    
    print(f"🚀 Starting Flask app for domain: {app.config.get('SERVER_NAME')}")
    print(f"📡 Listening on: {host}:{port}")
    print(f"🔗 Access URL: {app.config['PREFERRED_URL_SCHEME']}://{app.config['SERVER_NAME']}")
    
    app.run(host=host, port=port, debug=debug)
