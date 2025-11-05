"""OCI utilities: PAR creation and simple file-backed PAR cache."""
import os
import time
import json
try:
    import oci
except Exception:
    oci = None

PAR_CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '.par_cache.json')
PAR_TTL_SECONDS_DEFAULT = int(os.getenv('PAR_TTL_SECONDS', '3600'))

_par_cache = {}

def load_par_cache():
    global _par_cache
    try:
        path = os.path.abspath(PAR_CACHE_FILE)
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                _par_cache = {tuple(k.split('|')): (v[0], int(v[1])) for k, v in data.items()}
    except Exception:
        _par_cache = {}

def save_par_cache():
    try:
        path = os.path.abspath(PAR_CACHE_FILE)
        serializable = {('|'.join(k)): [v[0], int(v[1])] for k, v in _par_cache.items()}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(serializable, f)
    except Exception:
        pass

def get_par_url_for_oci(vf, ttl_seconds=None):
    """Create or reuse a PAR URL for an oci:// path. Returns a HTTP URL or fallback proxy path.

    This helper manages an internal cache and persists it to PAR_CACHE_FILE.
    """
    if not oci:
        return f'/object_proxy?path={vf}'
    ttl = ttl_seconds or PAR_TTL_SECONDS_DEFAULT
    try:
        path = vf[len('oci://'):]
        parts = path.split('/', 2)
        config = oci.config.from_file()
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
            namespace = obj_client.get_namespace().data
            bucket = parts[0]
            object_name = parts[1]

        cache_key = (namespace, bucket, object_name)
        now_ts = int(time.time())
        cached = _par_cache.get(cache_key)
        if cached and cached[1] > now_ts:
            return cached[0]

        expiry_ts = int(time.time()) + ttl
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
            url = base_url.rstrip('/') + access_uri
            _par_cache[cache_key] = (url, now_ts + ttl)
            try:
                save_par_cache()
            except Exception:
                pass
            return url
        return f'/object_proxy?path={vf}'
    except Exception:
        return f'/object_proxy?path={vf}'
