#!/usr/bin/env python3
"""Refresh environment helper

This script helps to "reset" the project environment by:
 - optionally backing up and deleting rows in the `video_embeddings` table
 - optionally deleting objects from an OCI bucket (by prefix)
 - removing local task/state files (summary_tasks.json, upload_tasks.json, video_task_ids.json, .par_cache.json)

Usage examples:
  # Dry-run: show what would be done
  python scripts/refresh_environment.py --dry-run --oci-bucket MyBucket --oci-prefix summary_

  # Backup DB and delete rows, delete summary object files in OCI, remove local task JSON and caches
  python scripts/refresh_environment.py --yes --backup-db backup.json --delete-db --oci-delete --oci-bucket MyBucket --oci-prefix summary_ --clean-local

Note: This script requires the OCI SDK and Oracle DB credentials to be configured via environment
variables or dotfile (.env). It will prompt for confirmation unless --yes is supplied.
"""
import os
import sys
import json
import argparse
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

LOCAL_FILES_TO_CLEAN = [
    os.path.join(REPO_ROOT, 'upload_tasks.json'),
    os.path.join(REPO_ROOT, 'summary_tasks.json'),
    os.path.join(REPO_ROOT, 'video_task_ids.json'),
    os.path.join(REPO_ROOT, '.par_cache.json'),
]


def confirm(prompt):
    resp = input(prompt + ' [y/N]: ').strip().lower()
    return resp in ('y', 'yes')


def backup_db_rows(conn, out_path):
    cur = conn.cursor()
    try:
        cur.execute('SELECT id, video_file, start_time, end_time, embedding_vector FROM video_embeddings')
        rows = []
        for r in cur:
            id_, vf, st, et, blob = r
            try:
                b = bytes(blob) if not isinstance(blob, memoryview) else blob.tobytes()
            except Exception:
                b = None
            rows.append({'id': id_, 'video_file': vf, 'start_time': st, 'end_time': et, 'embedding_bytes_len': len(b) if b else 0})
        with open(out_path, 'w') as f:
            json.dump(rows, f, indent=2)
        print(f'Backed up {len(rows)} rows to {out_path}')
    finally:
        cur.close()


def delete_db_rows(conn):
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM video_embeddings')
        conn.commit()
        print('Deleted rows from video_embeddings')
    finally:
        cur.close()


def remove_local_files(dry_run=False):
    for p in LOCAL_FILES_TO_CLEAN:
        if os.path.exists(p):
            if dry_run:
                print('[dry-run] would remove', p)
            else:
                try:
                    os.remove(p)
                    print('Removed', p)
                except Exception as e:
                    print('Failed to remove', p, e)
        else:
            print('Not present:', p)


def delete_oci_objects(bucket, prefix=None, dry_run=True, oci_config_path=None):
    try:
        import oci
    except Exception as e:
        print('OCI SDK not installed:', e)
        return

    # Load config from default file location or environment
    try:
        # If an explicit config path was provided use it; otherwise try default
        if oci_config_path:
            cfg_file = os.path.expanduser(oci_config_path)
            cfg = oci.config.from_file(cfg_file)
        else:
            # Try the standard location then env var
            try:
                cfg = oci.config.from_file()
            except Exception:
                env_path = os.getenv('OCI_CONFIG_FILE', '~/.oci/config')
                cfg = oci.config.from_file(os.path.expanduser(env_path))
    except Exception as e:
        print('Failed to load OCI config:', e)
        return

    client = oci.object_storage.ObjectStorageClient(cfg)
    namespace = client.get_namespace().data
    print('Using namespace:', namespace)
    # list objects with optional prefix and delete
    kwargs = {}
    if prefix:
        kwargs['prefix'] = prefix

    objects = []
    try:
        resp = client.list_objects(namespace, bucket, **kwargs)
        objects = resp.data.objects or []
    except Exception as e:
        print('Failed to list objects:', e)
        return

    print(f'Found {len(objects)} objects in bucket {bucket} with prefix {prefix}')
    for obj in objects:
        name = obj.name
        if dry_run:
            print('[dry-run] would delete:', name)
        else:
            try:
                client.delete_object(namespace, bucket, name)
                print('Deleted:', name)
            except Exception as e:
                print('Failed to delete', name, e)


def attempt_delete_twelvelabs_tasks(task_ids, dry_run=True):
    # The TwelveLabs API may not allow deletion of completed embedding tasks; this function
    # attempts to call a delete or cancel method if available; otherwise we print guidance.
    try:
        from twelvelabs import TwelveLabs
    except Exception:
        print('twelvelabs SDK not available; cannot attempt task cleanup')
        return

    api_key = os.getenv('TWELVE_LABS_API_KEY')
    if not api_key:
        print('TWELVE_LABS_API_KEY not set; skipping TwelveLabs cleanup')
        return
    client = TwelveLabs(api_key=api_key)

    for tid in task_ids:
        print('Task:', tid)
        if dry_run:
            print('[dry-run] would attempt to delete or cancel', tid)
            continue
        # Try common shapes: client.embed.tasks.delete(task_id), or client.embed.tasks.cancel
        try:
            tasks_obj = getattr(client, 'embed').tasks
            delete_fn = getattr(tasks_obj, 'delete', None)
            cancel_fn = getattr(tasks_obj, 'cancel', None)
            if callable(delete_fn):
                delete_fn(task_id=tid)
                print('Deleted task', tid)
                continue
            if callable(cancel_fn):
                cancel_fn(task_id=tid)
                print('Cancelled task', tid)
                continue
            print('No delete/cancel available for TwelveLabs tasks via SDK; please revoke API keys or contact TwelveLabs support for permanent removal')
        except Exception as e:
            print('Error while attempting to delete/cancel task', tid, e)


def main():
    p = argparse.ArgumentParser(description='Refresh environment: DB rows, OCI objects, local files')
    p.add_argument('--dry-run', action='store_true', help='Show actions without performing them')
    p.add_argument('--yes', action='store_true', help='Do not prompt for confirmation')
    p.add_argument('--backup-db', help='Path to write DB backup JSON before deletion')
    p.add_argument('--delete-db', action='store_true', help='Delete rows from video_embeddings')
    p.add_argument('--oracle-wallet', help='Path to Oracle wallet directory (optional)')
    p.add_argument('--oci-delete', action='store_true', help='Delete objects from OCI bucket')
    p.add_argument('--oci-bucket', help='OCI bucket name to operate on')
    p.add_argument('--oci-prefix', help='OCI object prefix to match for deletion')
    p.add_argument('--oci-config', help='Path to OCI config file (defaults to ~/.oci/config)')
    p.add_argument('--clean-local', action='store_true', help='Remove local task/state files')
    p.add_argument('--twelvelabs-clean', action='store_true', help='Attempt to clean task ids from TwelveLabs using video_task_ids.json')
    args = p.parse_args()

    if not args.yes and not args.dry_run:
        ok = confirm('This will perform destructive actions. Are you sure you want to continue?')
        if not ok:
            print('Aborting')
            sys.exit(1)

    # Oracle DB connection may be required
    conn = None
    if (args.backup_db or args.delete_db):
        try:
            import oracledb
            # Allow explicit wallet path via CLI (falls back to env var)
            wallet_path = args.oracle_wallet if hasattr(args, 'oracle_wallet') and args.oracle_wallet else os.getenv('ORACLE_DB_WALLET_PATH')
            wallet_password = os.getenv('ORACLE_DB_WALLET_PASSWORD')
            # Build connect kwargs defensively
            connect_kwargs = dict(
                user=os.getenv('ORACLE_DB_USERNAME'),
                password=os.getenv('ORACLE_DB_PASSWORD'),
                dsn=os.getenv('ORACLE_DB_CONNECT_STRING'),
            )
            if wallet_path:
                wallet_path = os.path.expanduser(wallet_path)
                connect_kwargs['wallet_location'] = wallet_path
            if wallet_password:
                connect_kwargs['wallet_password'] = wallet_password

            conn = oracledb.connect(**connect_kwargs)
        except Exception as e:
            print('Failed to connect to Oracle DB:', e)
            conn = None

    try:
        if args.backup_db and conn:
            if args.dry_run:
                print('[dry-run] would backup DB to', args.backup_db)
            else:
                backup_db_rows(conn, args.backup_db)

        if args.delete_db and conn:
            if args.dry_run:
                print('[dry-run] would delete rows from video_embeddings')
            else:
                delete_db_rows(conn)

        if args.oci_delete:
            if not args.oci_bucket:
                print('oci-delete requires --oci-bucket');
            else:
                delete_oci_objects(args.oci_bucket, prefix=args.oci_prefix, dry_run=args.dry_run, oci_config_path=args.oci_config)

        if args.clean_local:
            remove_local_files(dry_run=args.dry_run)

        if args.twelvelabs_clean:
            # read local video_task_ids.json if present
            vt = os.path.join(REPO_ROOT, 'video_task_ids.json')
            if os.path.exists(vt):
                with open(vt, 'r') as f:
                    data = json.load(f)
                ids = list(data.values())
                attempt_delete_twelvelabs_tasks(ids, dry_run=args.dry_run)
            else:
                print('video_task_ids.json not found; nothing to clean for TwelveLabs')

    finally:
        if conn:
            try: conn.close()
            except Exception: pass


if __name__ == '__main__':
    main()
