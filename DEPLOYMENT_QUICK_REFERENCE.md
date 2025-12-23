# Quick Deployment Reference

## Current Consolidated Structure (Dec 22, 2025)

### ✅ Deployment Targets (Single Source of Truth)

| File Type | Local Location | Server Location |
|-----------|----------------|-----------------|
| Flask App | `src/localhost_only_flask.py` | `/home/dataguardian/TwelvelabsWithOracleVector/src/` |
| Templates | `src/templates/*.html` | `/home/dataguardian/TwelvelabsWithOracleVector/src/templates/` |
| Local Utils | `src/utils/*.py` | `/home/dataguardian/TwelvelabsWithOracleVector/src/utils/` |
| Shared Utils | `twelvelabvideoai/src/*.py` | `/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src/` |

### 🚀 Quick Deploy Commands

**Deploy Templates Only:**
```bash
scp src/templates/*.html ubuntu@150.136.235.189:/tmp/ && \
ssh ubuntu@150.136.235.189 'sudo cp /tmp/*.html /home/dataguardian/TwelvelabsWithOracleVector/src/templates/ && \
sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/src/templates/ && \
sudo systemctl restart dataguardian-https.service'
```

**Deploy Flask App:**
```bash
scp src/localhost_only_flask.py ubuntu@150.136.235.189:/tmp/ && \
ssh ubuntu@150.136.235.189 'sudo cp /tmp/localhost_only_flask.py /home/dataguardian/TwelvelabsWithOracleVector/src/ && \
sudo chown dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/src/localhost_only_flask.py && \
sudo systemctl restart dataguardian-https.service'
```

**Deploy Single Template:**
```bash
scp src/templates/index.html ubuntu@150.136.235.189:/tmp/ && \
ssh ubuntu@150.136.235.189 'sudo cp /tmp/index.html /home/dataguardian/TwelvelabsWithOracleVector/src/templates/ && \
sudo chown dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/src/templates/index.html && \
sudo systemctl restart dataguardian-https.service'
```

**Deploy Utils:**
```bash
scp src/utils/face_detection_helper.py ubuntu@150.136.235.189:/tmp/ && \
ssh ubuntu@150.136.235.189 'sudo cp /tmp/face_detection_helper.py /home/dataguardian/TwelvelabsWithOracleVector/src/utils/ && \
sudo chown dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/src/utils/face_detection_helper.py && \
sudo systemctl restart dataguardian-https.service'
```

### 🔍 Verification Commands

**Check Service Status:**
```bash
ssh ubuntu@150.136.235.189 'sudo systemctl status dataguardian-https.service --no-pager | head -20'
```

**Check Recent Logs:**
```bash
ssh ubuntu@150.136.235.189 'sudo journalctl -u dataguardian-https.service --since "1 minute ago" --no-pager | tail -30'
```

**Check Template Files:**
```bash
ssh ubuntu@150.136.235.189 'sudo ls -lh /home/dataguardian/TwelvelabsWithOracleVector/src/templates/'
```

**Verify File Line Count:**
```bash
ssh ubuntu@150.136.235.189 'sudo wc -l /home/dataguardian/TwelvelabsWithOracleVector/src/templates/index.html'
wc -l src/templates/index.html
```

**Test Website:**
```bash
curl -k -s https://150.136.235.189:8443/ | head -20
```

### ⚠️ What NOT to Deploy To

**DO NOT deploy templates to these locations anymore:**
- ❌ `/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/src/templates/`
- ❌ Any other templates directory

**Reason:** Flask now reads from `src/templates/` only (consolidated structure)

### 📦 Template Files (10 total)

1. admin_quotas.html
2. admin_tools.html
3. admin_users.html
4. camera_face_search.html
5. face_tagging_components.html
6. face_tags_manager.html
7. index.html
8. index_old.html
9. login.html
10. profile.html

### 🔧 Service Management

**Restart:**
```bash
ssh ubuntu@150.136.235.189 'sudo systemctl restart dataguardian-https.service'
```

**Stop:**
```bash
ssh ubuntu@150.136.235.189 'sudo systemctl stop dataguardian-https.service'
```

**Start:**
```bash
ssh ubuntu@150.136.235.189 'sudo systemctl start dataguardian-https.service'
```

**View Logs (Live):**
```bash
ssh ubuntu@150.136.235.189 'sudo journalctl -u dataguardian-https.service -f'
```

### 🎯 Common Issues

**Issue:** Changes not appearing after deployment
**Fix:** 
1. Verify file was deployed: `ssh ubuntu@150.136.235.189 'sudo wc -l /path/to/file'`
2. Check local vs remote line counts match
3. Restart service: `sudo systemctl restart dataguardian-https.service`
4. Clear browser cache (Ctrl+Shift+R)

**Issue:** Service won't start
**Fix:**
1. Check logs: `sudo journalctl -u dataguardian-https.service --no-pager | tail -50`
2. Check Python syntax: `ssh ubuntu@server 'cd /home/dataguardian/.../src && sudo -u dataguardian python3 -m py_compile localhost_only_flask.py'`
3. Check permissions: `sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/src/`
