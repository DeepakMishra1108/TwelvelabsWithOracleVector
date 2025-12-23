# File Structure Consolidation - Dec 22, 2025

## Problem Statement

The project had **duplicate file structures** causing deployment confusion:

```
TwelvelabsWithOracleVector/
├── src/
│   ├── localhost_only_flask.py
│   ├── templates/
│   │   └── *.html (10 files)
│   └── utils/
│
└── twelvelabvideoai/
    └── src/
        ├── templates/
        │   └── *.html (9 files - missing camera_face_search.html)
        ├── auth_utils.py
        ├── auth_rbac.py
        ├── oci_storage.py
        └── (other utility modules)
```

**Issues:**
1. Flask config pointed to `twelvelabvideoai/src/templates/` 
2. But gunicorn ran from `src/` directory (`--chdir /home/dataguardian/.../src`)
3. Result: Updates to one templates folder didn't reflect in the app
4. Constant confusion about which file was "live"

## Solution Implemented

### 1. Consolidated Template Location
- **All templates now in:** `/src/templates/`
- **Python utilities still in:** `/twelvelabvideoai/src/` (imported via sys.path)
- **Flask app in:** `/src/localhost_only_flask.py`

### 2. Updated Flask Configuration

**Before:**
```python
# Go up one level from src/ to project root, then into twelvelabvideoai/src
project_root = os.path.dirname(current_dir)
twelvelabs_src_dir = os.path.join(project_root, 'twelvelabvideoai', 'src')
sys.path.insert(0, twelvelabs_src_dir)

TEMPLATES_DIR = os.path.join(twelvelabs_src_dir, 'templates')  # WRONG!
app = Flask(__name__, template_folder=TEMPLATES_DIR)
```

**After:**
```python
# Import Python modules from twelvelabvideoai/src (for utilities like auth, RBAC, etc.)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
twelvelabs_src_dir = os.path.join(project_root, 'twelvelabvideoai', 'src')
sys.path.insert(0, twelvelabs_src_dir)

# Templates directory is local to this src folder
TEMPLATES_DIR = os.path.join(current_dir, 'templates')  # CORRECT!
app = Flask(__name__, template_folder=TEMPLATES_DIR)
```

### 3. File Organization

```
TwelvelabsWithOracleVector/
├── src/                           # Main application directory (gunicorn runs here)
│   ├── localhost_only_flask.py   # Main Flask app
│   ├── templates/                 # ✅ SINGLE SOURCE OF TRUTH for templates
│   │   ├── admin_quotas.html
│   │   ├── admin_tools.html
│   │   ├── admin_users.html
│   │   ├── camera_face_search.html
│   │   ├── face_tagging_components.html
│   │   ├── face_tags_manager.html
│   │   ├── index.html
│   │   ├── index_old.html
│   │   ├── login.html
│   │   └── profile.html
│   └── utils/                     # Local utilities
│       ├── db_utils_flask_safe.py
│       ├── face_detection_helper.py
│       └── ...
│
└── twelvelabvideoai/              # Python virtual environment + utility modules
    └── src/                       # Python utility modules (imported via sys.path)
        ├── auth_utils.py
        ├── auth_rbac.py
        ├── oci_storage.py
        ├── rate_limiter.py
        └── ...
```

## Deployment Process (Simplified)

### Before (Confusing):
```bash
# Had to update BOTH locations
scp file.html ubuntu@server:/tmp/
ssh ubuntu@server 'sudo cp /tmp/file.html /home/.../src/templates/'
ssh ubuntu@server 'sudo cp /tmp/file.html /home/.../twelvelabvideoai/src/templates/'
```

### After (Simple):
```bash
# Update ONLY src/templates/
scp src/templates/*.html ubuntu@server:/tmp/
ssh ubuntu@server 'sudo cp /tmp/*.html /home/.../src/templates/'
ssh ubuntu@server 'sudo systemctl restart dataguardian-https.service'
```

## Benefits

1. ✅ **Single source of truth** for templates
2. ✅ **No more duplicate files** causing confusion
3. ✅ **Simpler deployment** process
4. ✅ **Clear separation**: 
   - `src/` = Flask app + templates + local utils
   - `twelvelabvideoai/src/` = Shared Python utility modules
5. ✅ **Fewer mistakes** when updating files

## Migration Checklist

- [x] Update Flask configuration in localhost_only_flask.py
- [x] Copy all templates to src/templates/
- [x] Deploy updated Flask app to server
- [x] Deploy all templates to server
- [x] Restart service
- [x] Verify templates are being read correctly
- [ ] **TODO: Remove or archive** `/home/dataguardian/.../twelvelabvideoai/src/templates/` (optional cleanup)

## Future Updates

**When updating templates:**
1. Edit files in `src/templates/` (both local and on server)
2. Deploy with: `scp src/templates/*.html ubuntu@server:/tmp/`
3. Copy to: `/home/dataguardian/TwelvelabsWithOracleVector/src/templates/`
4. Restart service

**When updating Python utilities:**
1. Edit files in `src/utils/` or `twelvelabvideoai/src/`
2. Deploy to the corresponding location on server
3. Restart service

## Notes

- The `twelvelabvideoai/src/` directory is still needed for Python utility modules (auth, RBAC, OCI storage, etc.)
- It's added to `sys.path` so Flask can import these modules
- Only templates were consolidated to avoid the duplicate file issue
- The virtual environment (`twelvelabvideoai/bin/`) remains unchanged
