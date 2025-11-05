#!/usr/bin/env python3
"""
Comprehensive validation script for TwelveLabs Video AI application
Checks: Syntax, imports, configuration, database connectivity, API access
"""
import os
import sys
import subprocess
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_status(status, message):
    """Print colored status message"""
    if status == 'success':
        print(f"{GREEN}✅ {message}{RESET}")
    elif status == 'error':
        print(f"{RED}❌ {message}{RESET}")
    elif status == 'warning':
        print(f"{YELLOW}⚠️  {message}{RESET}")
    elif status == 'info':
        print(f"{BLUE}ℹ️  {message}{RESET}")

def check_syntax(file_path):
    """Check Python syntax"""
    try:
        subprocess.run(['python', '-m', 'py_compile', file_path], 
                      check=True, capture_output=True)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode()

def main():
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  TwelveLabs Video AI - Comprehensive Validation{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # Key application files to validate
    key_files = [
        'localhost_only_flask.py',
        'twelvelabvideoai/src/unified_album_manager.py',
        'twelvelabvideoai/src/unified_album_manager_flask_safe.py',
        'twelvelabvideoai/src/utils/db_utils_flask_safe.py',
        'twelvelabvideoai/src/utils/db_utils_vector.py',
        'twelvelabvideoai/src/oci_config.py',
        'twelvelabvideoai/src/store_photo_embeddings.py',
        'twelvelabvideoai/src/store_video_embeddings.py',
    ]
    
    print_status('info', 'Phase 1: Syntax Validation')
    print('-' * 60)
    
    syntax_errors = []
    for file_path in key_files:
        if os.path.exists(file_path):
            success, error = check_syntax(file_path)
            if success:
                print_status('success', f'{file_path}')
            else:
                print_status('error', f'{file_path}: {error}')
                syntax_errors.append(file_path)
        else:
            print_status('warning', f'{file_path} - NOT FOUND')
    
    print(f"\n{'-'*60}\n")
    print_status('info', 'Phase 2: Import Validation')
    print('-' * 60)
    
    # Test key imports
    imports_to_test = [
        ('Flask', 'from flask import Flask, request, jsonify'),
        ('OCI SDK', 'import oci'),
        ('TwelveLabs', 'from twelvelabs import TwelveLabs'),
        ('Oracle DB', 'import oracledb'),
        ('dotenv', 'from dotenv import load_dotenv'),
    ]
    
    import_errors = []
    for name, import_stmt in imports_to_test:
        try:
            exec(import_stmt)
            print_status('success', f'{name}')
        except Exception as e:
            print_status('error', f'{name}: {e}')
            import_errors.append(name)
    
    print(f"\n{'-'*60}\n")
    print_status('info', 'Phase 3: Environment Configuration')
    print('-' * 60)
    
    # Check critical environment variables
    env_vars = [
        'ORACLE_DB_USERNAME',
        'ORACLE_DB_PASSWORD',
        'ORACLE_DB_CONNECT_STRING',
        'ORACLE_DB_WALLET_PATH',
        'TWELVE_LABS_API_KEY',
        'OCI_TENANCY',
        'OCI_USER',
        'OCI_FINGERPRINT',
        'OCI_KEY_FILE',
    ]
    
    missing_env = []
    for var in env_vars:
        if os.getenv(var):
            print_status('success', f'{var}')
        else:
            print_status('warning', f'{var} - NOT SET')
            missing_env.append(var)
    
    print(f"\n{'-'*60}\n")
    print_status('info', 'Phase 4: Database Connectivity')
    print('-' * 60)
    
    try:
        sys.path.insert(0, 'twelvelabvideoai/src')
        from utils.db_utils_flask_safe import get_flask_safe_connection
        
        with get_flask_safe_connection(timeout=5) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            result = cursor.fetchone()
            if result and result[0] == 1:
                print_status('success', 'Database connection successful')
            else:
                print_status('error', 'Database query returned unexpected result')
    except Exception as e:
        print_status('error', f'Database connection failed: {e}')
    
    print(f"\n{'-'*60}\n")
    print_status('info', 'Phase 5: File System Checks')
    print('-' * 60)
    
    # Check critical directories and files
    paths_to_check = [
        ('Wallet directory', os.getenv('ORACLE_DB_WALLET_PATH')),
        ('OCI config', os.path.expanduser('~/.oci/config')),
        ('Templates directory', 'twelvelabvideoai/src/templates'),
        ('Static directory', 'twelvelabvideoai/src/static'),
    ]
    
    for name, path in paths_to_check:
        if path and os.path.exists(path):
            print_status('success', f'{name}: {path}')
        else:
            print_status('warning', f'{name}: {path} - NOT FOUND')
    
    # Summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  Validation Summary{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    total_issues = len(syntax_errors) + len(import_errors) + len(missing_env)
    
    if total_issues == 0:
        print_status('success', 'All validations passed! ✨')
    else:
        print_status('warning', f'Found {total_issues} issue(s):')
        if syntax_errors:
            print(f"  - Syntax errors in {len(syntax_errors)} file(s)")
        if import_errors:
            print(f"  - Import errors for {len(import_errors)} package(s)")
        if missing_env:
            print(f"  - {len(missing_env)} environment variable(s) not set")
    
    print()

if __name__ == '__main__':
    main()
