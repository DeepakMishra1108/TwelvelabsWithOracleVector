"""HTTP utilities: download helper using httpx and small path helpers."""
import os
import shutil
import httpx


def download_url_to_file(url, dst_path, timeout=60):
    # file:// handling
    if url.startswith('file://'):
        local_path = url[len('file://'):]
        if os.path.exists(local_path):
            shutil.copyfile(local_path, dst_path)
            return True, None
        return False, f'file not found: {local_path}'

    if os.path.exists(url):
        shutil.copyfile(url, dst_path)
        return True, None

    if url.startswith('/'):
        url = f'http://127.0.0.1:8080{url}'

    try:
        with httpx.stream('GET', url, timeout=timeout) as r:
            r.raise_for_status()
            with open(dst_path, 'wb') as f:
                for chunk in r.iter_bytes(1024 * 64):
                    if chunk:
                        f.write(chunk)
        return True, None
    except Exception as e:
        return False, str(e)
