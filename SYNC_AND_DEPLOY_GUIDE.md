# 🔄 Code Sync & Deployment Guide

## Current Repository Structure

**GitHub Repository**: `https://github.com/DeepakMishra1108/TwelvelabsWithOracleVector.git`

### Locations:
1. **Local Development** (macOS): `/Users/deepamis/Documents/GitHub/TwelvelabsVideoAI`
2. **VM Server** (OCI): `/home/dataguardian/TwelvelabsWithOracleVector`
3. **GitHub Remote**: `origin/main`

---

## 📊 Current Status

✅ **Git Status**: 
- Branch: `main`
- Ahead of origin by 7 commits (needs push)
- Working directory: Clean

✅ **VM Server**:
- IP: `150.136.235.189`
- User: `dataguardian`
- Service: `dataguardian.service` / `dataguardian-https.service`
- Python Environment: `/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai`

---

## 🚀 Proper Workflow (Test-First Approach)

### Step 1: Make Changes Locally (Your Mac)

```bash
cd /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI

# Edit your files
# Make your changes in src/, scripts/, etc.

# Check what changed
git status
git diff
```

### Step 2: Deploy to VM for Testing (DON'T commit yet!)

#### Option A: Direct File Copy (RECOMMENDED for testing)

```bash
# From your Mac, copy changed files directly to VM
# Example: Deploy updated index.html
scp src/templates/index.html ubuntu@150.136.235.189:/tmp/
ssh ubuntu@150.136.235.189 "sudo cp /tmp/index.html /home/dataguardian/TwelvelabsWithOracleVector/src/templates/ && sudo chown dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/src/templates/index.html"

# Restart service to apply changes
ssh ubuntu@150.136.235.189 "sudo systemctl restart dataguardian.service"

# Or use the quick deploy script (see below)
./deploy_to_vm_test.sh
```

**Benefits:**
- ✅ Fast - only copies changed files
- ✅ No git operations on VM
- ✅ Easy to rollback if test fails
- ✅ GitHub stays clean until verified

#### Option B: Full Git Deployment (After testing succeeds)

```bash
# SSH to VM
ssh ubuntu@150.136.235.189
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector

# Pull latest code
git pull origin main

# Restart service
sudo systemctl restart dataguardian.service

# Check status
sudo systemctl status dataguardian.service
sudo journalctl -u dataguardian.service -f
```

### Step 3: Test on VM

```bash
# Check service status
ssh ubuntu@150.136.235.189 "sudo systemctl status dataguardian.service"

# Check logs for errors
ssh ubuntu@150.136.235.189 "sudo journalctl -u dataguardian.service -n 50"

# Test the application in browser
# Open: https://150.136.235.189:8443
# - Test the feature you changed
# - Check browser console for errors
# - Verify everything works
```

### Step 4: Commit to GitHub (Only After Successful Testing!)

```bash
# Back on your Mac
cd /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI

# If tests passed, commit your changes
git add .
git commit -m "Descriptive message about what was fixed/added"
git push origin main
```

### Step 5: Sync VM with GitHub (Optional but recommended)

```bash
# Now sync VM with GitHub for consistency
ssh ubuntu@150.136.235.189
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector
git pull origin main  # This will be a fast-forward since files already match
```

---

## 📁 File Locations on VM

### Application Files
```
/home/dataguardian/TwelvelabsWithOracleVector/
├── src/
│   ├── localhost_only_flask.py      # Main Flask app
│   ├── templates/
│   │   └── index.html                # Fixed JS file (your current work)
│   └── utils/
│       ├── face_detection_helper.py
│       └── ...
├── scripts/
│   ├── vm_safe_deploy.sh            # Use this for deployment!
│   └── deploy_app.sh
├── twelvelabvideoai/                 # Python virtual environment
│   ├── bin/python3
│   └── lib/
├── .env                              # VM-specific (NOT in git)
├── ssl/                              # VM-specific (NOT in git)
│   ├── certificate.crt
│   └── private.key
├── gunicorn_config.py                # VM-specific (NOT in git)
└── logs/
    ├── gunicorn-access.log
    └── gunicorn-error.log
```

### Important VM-Specific Files (Never Commit!)
These files are unique to the VM and should NEVER be committed to git:

1. **`.env`** - Database credentials, API keys, secrets
2. **`ssl/certificate.crt`** - SSL certificate
3. **`ssl/private.key`** - SSL private key
4. **`gunicorn_config.py`** - Server configuration with paths
5. **`twelvelabvideoai/`** - Python virtual environment

These are already in `.gitignore` ✅

---

## 🔒 Security Best Practices

### Never Commit Sensitive Data

```bash
# Check before committing
git status
git diff

# Make sure these are in .gitignore:
.env
ssl/*.key
ssl/*.crt
gunicorn_config.py
twelvelabvideoai/
```

### VM Backup Directory
- VM backups are created during deployment: `vm_backup_YYYYMMDD_HHMMSS/`
- These contain VM-specific configs
- Now in `.gitignore` ✅
- Can be safely deleted after successful deployment

---

## 🐛 Troubleshooting

### Problem: Changes not appearing on VM

**Solution:**
```bash
# On VM, check git status
cd /home/dataguardian/TwelvelabsWithOracleVector
git status
git log --oneline -5

# Compare with GitHub
git fetch origin
git log origin/main --oneline -5

# If behind, pull changes
./scripts/vm_safe_deploy.sh
```

### Problem: Service won't start after deployment

**Solution:**
```bash
# Check logs
sudo journalctl -u dataguardian.service -n 100 --no-pager

# Common issues:
# 1. Missing dependencies
source /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/activate
pip install -r requirements.txt

# 2. Permission issues
sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector

# 3. Port already in use
sudo lsof -i :8080
sudo lsof -i :8443
```

### Problem: Git conflicts on VM

**Solution:**
```bash
# Save local changes
git stash save "VM local changes backup"

# Pull fresh code
git pull origin main

# Review what was stashed
git stash show

# Apply if needed (carefully!)
git stash pop
```

---

## 📝 Quick Commands Reference

### Local (Mac) - Test-First Workflow
```bash
# 1. Make changes to files

# 2. Deploy to VM for testing (NO commit yet!)
./deploy_to_vm_test.sh

# 3. Test in browser: https://150.136.235.189:8443

# 4. If test FAILS - rollback
./rollback_test.sh

# 5. If test PASSES - commit to git
git add .
git commit -m "Description"
git push origin main

# View history
git log --oneline -10
```

### VM Server
```bash
# Connect
ssh ubuntu@150.136.235.189
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector

# Deploy
./scripts/vm_safe_deploy.sh

# Service control
sudo systemctl status dataguardian.service
sudo systemctl restart dataguardian.service
sudo journalctl -u dataguardian.service -f

# Check what's different from GitHub
git fetch origin
git diff origin/main
```

---

## 🎯 Best Practices

### DO ✅
- **TEST ON VM FIRST** before committing to GitHub
- Use `deploy_to_vm_test.sh` for test deployments
- Verify changes work on VM before `git commit`
- Only commit to GitHub after successful VM testing
- Write descriptive commit messages
- Review changes before deploying (`git diff`)
- Keep VM-specific files out of git
- Use rollback script if tests fail

### DON'T ❌
- **Don't commit untested changes to GitHub**
- Don't manually edit files on VM (except emergencies)
- Don't commit sensitive data (.env, SSL keys)
- Don't skip testing on VM
- Don't delete test_backup folders until verified
- Don't push uncommitted changes from VM to GitHub

---

## 🔄 Current Uncommitted Changes

As of now, you have:
- ✅ JavaScript fixes committed
- ✅ .gitignore updated
- 🔄 7 commits ahead of origin (need to push)

**Next steps:**
1. Push to GitHub: `git push origin main`
2. Deploy to VM: Use `vm_safe_deploy.sh`
3. Test the application: Verify albums load and buttons work

---

## 📞 Emergency Rollback

If deployment breaks something:

```bash
# On VM
cd /home/dataguardian/TwelvelabsWithOracleVector

# Find the backup
ls -lt vm_backup_*/

# Restore VM configs
cp vm_backup_LATEST/.env .
cp vm_backup_LATEST/ssl/* ssl/
cp vm_backup_LATEST/gunicorn_config.py .

# Rollback code to previous commit
git log --oneline -5  # Find commit hash
git reset --hard COMMIT_HASH

# Restart service
sudo systemctl restart dataguardian.service
```

---

## 📚 Related Documentation

- [DEPLOYMENT_QUICK_START.md](./DEPLOYMENT_QUICK_START.md) - Quick deploy commands
- [scripts/vm_safe_deploy.sh](./scripts/vm_safe_deploy.sh) - Safe deployment script
- [DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md) - Current deployment info
- [README.md](./README.md) - Project overview

---

## ✅ Action Items for Clean Sync

1. **Push current changes to GitHub:**
   ```bash
   git push origin main
   ```

2. **Deploy to VM:**
   ```bash
   ssh ubuntu@150.136.235.189
   sudo su - dataguardian
   cd /home/dataguardian/TwelvelabsWithOracleVector
   ./scripts/vm_safe_deploy.sh
   ```

3. **Test the fixes:**
   - Open https://150.136.235.189:8443
   - Check if albums load
   - Test button clicks
   - Verify no JavaScript errors in console

4. **Clean up local backup directories (optional):**
   ```bash
   # On Mac - these are already in .gitignore now
   rm -rf vm_backup_20251223_*
   ```

---

**Last Updated**: December 24, 2025
**Status**: Ready for deployment
