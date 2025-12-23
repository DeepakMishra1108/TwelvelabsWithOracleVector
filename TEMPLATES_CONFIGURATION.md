# Templates Configuration - Verified ✅

## Single Source of Truth
All templates are now consolidated to a single location:
- **Local**: `./src/templates/`
- **Server**: `/home/dataguardian/TwelvelabsWithOracleVector/src/templates/`

## Flask Configuration ✅

**File**: `/src/localhost_only_flask.py`

```python
# Line 22: Set current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Line 30: Templates directory is local to this src folder
TEMPLATES_DIR = os.path.join(current_dir, 'templates')

# Line 425: Flask app with explicit template folder
app = Flask(__name__, template_folder=TEMPLATES_DIR)
```

**Result**: Flask looks for templates in `/home/dataguardian/TwelvelabsWithOracleVector/src/templates/`

## Gunicorn Configuration ✅

**File**: `/gunicorn_config_https.py`

```python
bind = "0.0.0.0:8443"
workers = 2
worker_class = "sync"
timeout = 300
```

## Systemd Service ✅

**File**: `/etc/systemd/system/dataguardian-https.service`

```ini
WorkingDirectory=/home/dataguardian/TwelvelabsWithOracleVector
ExecStart=/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/gunicorn \
    --config /home/dataguardian/TwelvelabsWithOracleVector/gunicorn_config_https.py \
    --chdir /home/dataguardian/TwelvelabsWithOracleVector/src \
    localhost_only_flask:app
```

**Key**: `--chdir /home/dataguardian/TwelvelabsWithOracleVector/src` ensures Flask runs from the `src/` directory.

## Path Resolution ✅

1. Systemd service starts gunicorn
2. Gunicorn changes directory to `/home/dataguardian/TwelvelabsWithOracleVector/src/`
3. Gunicorn loads `localhost_only_flask:app` from current directory
4. Flask app sets `current_dir = os.path.dirname(os.path.abspath(__file__))`
   - This resolves to `/home/dataguardian/TwelvelabsWithOracleVector/src/`
5. Flask app sets `TEMPLATES_DIR = os.path.join(current_dir, 'templates')`
   - This resolves to `/home/dataguardian/TwelvelabsWithOracleVector/src/templates/`
6. Flask app created with `template_folder=TEMPLATES_DIR`

## Verification

```bash
# Check Flask app location
$ ls -l /home/dataguardian/TwelvelabsWithOracleVector/src/localhost_only_flask.py
✅ -rw-r--r-- 1 dataguardian dataguardian 269064 Dec 22 22:27

# Check templates directory
$ ls /home/dataguardian/TwelvelabsWithOracleVector/src/templates/*.html | wc -l
✅ 12 templates

# Check for duplicate directories
$ find /home/dataguardian/TwelvelabsWithOracleVector -name "templates" -type d | grep -v "lib/python"
✅ Only one: /home/dataguardian/TwelvelabsWithOracleVector/src/templates
```

## Deployment

Use the consolidated deployment script:

```bash
./deploy_templates.sh
```

This script:
1. Copies all templates from `./src/templates/*.html`
2. Deploys to `/home/dataguardian/TwelvelabsWithOracleVector/src/templates/`
3. Sets proper ownership (dataguardian:dataguardian)
4. No duplicate locations to maintain

## Summary

✅ Flask app: Points to `src/templates/`
✅ Gunicorn: Runs from `src/` directory
✅ Systemd: `--chdir` ensures correct working directory
✅ Templates: Single location `/src/templates/`
✅ Deployment: Single target location
✅ No duplicates: Removed `twelvelabvideoai/src/templates/`

**Status**: All configurations verified and working correctly! 🎉
