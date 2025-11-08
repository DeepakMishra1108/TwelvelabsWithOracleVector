# VM Deployment Guide - Preserving Local Changes

## 🎯 Problem Statement

When deploying code updates from Git to a production VM, certain files should **NOT** be overwritten:
- SSL certificates (generated per server)
- Environment variables (.env)
- Server-specific configurations
- VM-specific code modifications

This guide explains how to safely deploy updates while preserving these critical files.

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [What Gets Preserved](#what-gets-preserved)
3. [Deployment Methods](#deployment-methods)
4. [Troubleshooting](#troubleshooting)
5. [Best Practices](#best-practices)

---

## 🚀 Quick Start

### Method 1: Automated Safe Deployment (Recommended)

```bash
ssh ubuntu@150.136.235.189
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector
./scripts/vm_safe_deploy.sh
```

This script will:
✅ Backup all VM-specific files  
✅ Pull latest code from Git  
✅ Restore VM-specific configurations  
✅ Restart services safely  
✅ Run health checks  

---

## 🔒 What Gets Preserved

### Files That Should NEVER Be in Git

These files are **server-specific** and should be generated/configured on each VM:

```
.env                        # Environment variables (secrets, credentials)
ssl/certificate.crt         # SSL certificate (server-specific)
ssl/private.key            # SSL private key (NEVER commit!)
gunicorn_config.py         # Server-specific Gunicorn config
.oci/config               # OCI credentials
wallet/*                  # Oracle wallet files
```

**Why?**
- **Security**: Private keys and secrets must not be in version control
- **Server-specific**: Each server needs its own SSL certificate
- **Environment differences**: Dev/Staging/Prod have different configs

### VM-Specific Code Changes

Sometimes you need VM-specific code modifications that shouldn't be committed:

**Location**: These are typically in stashed git changes
- Performance tuning specific to VM specs
- Temporary debugging code
- Environment-specific workarounds

---

## 🛠️ Deployment Methods

### Method 1: Automated Safe Deployment Script ⭐ RECOMMENDED

**File**: `scripts/vm_safe_deploy.sh`

**What it does:**
1. ✅ Backs up VM-specific files to timestamped directory
2. ✅ Stashes any local code changes
3. ✅ Pulls latest code from Git
4. ✅ Restores VM-specific files
5. ✅ Reapplies local changes (if any)
6. ✅ Validates SSL certificates
7. ✅ Restarts services
8. ✅ Runs health checks

**Usage:**
```bash
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector
./scripts/vm_safe_deploy.sh
```

**Output:**
```
🚀 Starting VM-Safe Deployment...
==================================
📦 Step 1: Backing up VM-specific configurations...
  ✓ Backing up: ssl/certificate.crt
  ✓ Backing up: .env
✅ Backup completed in: vm_backup_20251108_013000

🔍 Step 2: Checking for local changes...
✓ No local changes detected

⬇️  Step 3: Pulling latest code from repository...
✅ Code updated successfully
...
🎉 Deployment completed successfully!
```

---

### Method 2: Manual Deployment (Advanced Users)

If you need more control or the script fails:

```bash
# 1. Backup critical files
cd /home/dataguardian/TwelvelabsWithOracleVector
mkdir -p ~/backup_$(date +%Y%m%d)
cp -r ssl .env gunicorn_config.py ~/backup_$(date +%Y%m%d)/

# 2. Stash local changes
git stash push -m "Pre-deployment backup"

# 3. Pull latest code
git pull origin main

# 4. Restore critical files
cp ~/backup_$(date +%Y%m%d)/ssl/* ssl/
cp ~/backup_$(date +%Y%m%d)/.env .env
cp ~/backup_$(date +%Y%m%d)/gunicorn_config.py .

# 5. Reapply local changes (if needed)
git stash list  # Check what's stashed
git stash show -p stash@{0}  # Preview changes
git stash pop  # Apply changes

# 6. If conflicts, resolve them
git status  # Check for conflicts
# Edit conflicted files
git add <resolved-files>
git stash drop

# 7. Restart services
sudo systemctl restart dataguardian
sudo systemctl reload nginx
```

---

### Method 3: Fresh Deployment (Clean Install)

When you want to start fresh without preserving local changes:

```bash
cd /home/dataguardian/TwelvelabsWithOracleVector

# 1. Backup only critical configs
mkdir -p ~/clean_backup_$(date +%Y%m%d)
cp -r ssl .env wallet ~/clean_backup_$(date +%Y%m%d)/

# 2. Reset repository to match remote
git fetch origin
git reset --hard origin/main

# 3. Restore only necessary files
cp ~/clean_backup_$(date +%Y%m%d)/.env .env
cp ~/clean_backup_$(date +%Y%m%d)/ssl/private.key ssl/

# 4. Regenerate certificate (must match private key)
./scripts/generate_ssl_certificate.sh

# 5. Restart services
sudo systemctl restart dataguardian
```

---

## 🔧 Troubleshooting

### Issue 1: SSL Certificate Mismatch After Deployment

**Symptom:**
```
nginx: [emerg] SSL_CTX_use_PrivateKey() failed 
(SSL: error:05800074:x509 certificate routines::key values mismatch)
```

**Cause:** Certificate was overwritten by Git, but private key wasn't

**Solution:**
```bash
cd /home/dataguardian/TwelvelabsWithOracleVector
# Regenerate both certificate AND key
./scripts/generate_ssl_certificate.sh
# Or manually:
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout ssl/private.key \
  -out ssl/certificate.crt \
  -days 365 \
  -subj "/C=US/ST=CA/L=SF/O=DataGuardian/CN=150.136.235.189"

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl restart dataguardian
```

---

### Issue 2: Merge Conflicts During Stash Pop

**Symptom:**
```
CONFLICT (content): Merge conflict in src/localhost_only_flask.py
```

**Solution:**
```bash
# 1. Check conflicted files
git status

# 2. View conflicts
cat src/localhost_only_flask.py | grep -A 10 "<<<<<<<" 

# 3. Option A: Accept their version (from Git)
git checkout --theirs src/localhost_only_flask.py

# 3. Option B: Accept our version (VM changes)
git checkout --ours src/localhost_only_flask.py

# 3. Option C: Manual resolution
# Edit file and remove conflict markers:
# <<<<<<< Updated upstream
# =======
# >>>>>>> Stashed changes

# 4. Mark as resolved
git add src/localhost_only_flask.py

# 5. Drop the stash (since we handled it)
git stash drop
```

---

### Issue 3: Application Won't Start After Deployment

**Check logs:**
```bash
# System service logs
sudo journalctl -u dataguardian -n 50

# Application logs
sudo tail -f /home/dataguardian/TwelvelabsWithOracleVector/logs/gunicorn-error.log

# Nginx logs
sudo tail -f /var/log/nginx/error.log
```

**Common causes:**

1. **Missing dependencies:**
```bash
source twelvelabvideoai/bin/activate
pip install -r requirements.txt
```

2. **Database connection:**
```bash
# Check if wallet files exist
ls -la twelvelabvideoai/wallet/

# Test connection
python scripts/test_db_connection.py
```

3. **Port already in use:**
```bash
sudo netstat -tulpn | grep 8443
# If another process is using it, kill it
sudo kill <PID>
```

---

### Issue 4: Lost VM-Specific Changes

**If you accidentally overwrote changes:**

```bash
# 1. Check stash list
git stash list

# 2. View stashed content
git stash show -p stash@{0}

# 3. Reapply stashed changes
git stash apply stash@{0}

# 4. Check backup directories
ls -la vm_backup_*/
ls -la ~/backup_*/

# 5. Restore from backup
cp vm_backup_20251108_013000/src/localhost_only_flask.py src/
```

---

## 📚 Best Practices

### 1. Always Use the Safe Deployment Script

```bash
# DON'T do this on VM:
git pull

# DO this instead:
./scripts/vm_safe_deploy.sh
```

### 2. Keep VM-Specific Changes Minimal

**Prefer environment variables over code changes:**

```python
# BAD: Hardcoded in code
MAX_WORKERS = 5

# GOOD: Environment variable
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '5'))
```

### 3. Document VM-Specific Changes

Create a file: `VM_CUSTOMIZATIONS.md`

```markdown
# VM-Specific Customizations

## Performance Tuning
- Gunicorn workers: 5 (based on CPU cores)
- Worker timeout: 120s (due to large video processing)

## Security
- SSL certificate valid until: 2026-11-08
- Certificate regeneration: ./scripts/generate_ssl_certificate.sh

## Environment Variables
- FLASK_ENV=production
- WORKERS=5
```

### 4. Regular Backups

```bash
# Automated backup cron job
# Add to crontab: crontab -e
0 2 * * * cd /home/dataguardian/TwelvelabsWithOracleVector && tar -czf ~/backups/app_$(date +\%Y\%m\%d).tar.gz .env ssl/ wallet/
```

### 5. Test Before Deploying to Production

```bash
# On a staging/test VM first:
./scripts/vm_safe_deploy.sh

# Run integration tests
python -m pytest tests/

# Then deploy to production
```

### 6. Monitor After Deployment

```bash
# Watch logs for 5 minutes
sudo journalctl -u dataguardian -f

# Check for errors
sudo journalctl -u dataguardian --since "5 minutes ago" | grep -i error

# Test endpoints
curl -k https://localhost/health
```

---

## 🔐 .gitignore Configuration

**Make sure these are in `.gitignore`:**

```gitignore
# Environment
.env
*.env

# SSL/TLS
ssl/private.key
ssl/certificate.crt
ssl/*.key
ssl/*.crt

# OCI
.oci/
wallet/
**/*.sso
**/*.p12

# VM-specific
gunicorn_config.py
vm_backup_*/
backup_*/

# Logs
*.log
logs/
```

---

## 📖 Deployment Checklist

Before each deployment:

- [ ] Backup VM-specific files
- [ ] Check current application status
- [ ] Note current Git commit
- [ ] Run deployment script
- [ ] Verify SSL certificates
- [ ] Check service status
- [ ] Test application endpoints
- [ ] Monitor logs for errors
- [ ] Document any issues

---

## 🆘 Emergency Rollback

If deployment fails and application won't start:

```bash
# 1. Check Git history
git log --oneline -5

# 2. Rollback to previous commit
git reset --hard <previous-commit-hash>

# 3. Restore from backup
cp ~/backup_*/ssl/* ssl/
cp ~/backup_*/.env .env

# 4. Restart services
sudo systemctl restart dataguardian
sudo systemctl reload nginx

# 5. Verify
curl -k https://localhost/health
```

---

## 📞 Support

If you encounter issues:

1. **Check logs**: `sudo journalctl -u dataguardian -n 100`
2. **View backups**: `ls -la vm_backup_*/ ~/backup_*/`
3. **Check stash**: `git stash list`
4. **Review this guide**: `/docs/deployment/VM_SAFE_DEPLOYMENT.md`

---

## 📝 Change Log

| Date | Change | By |
|------|--------|-----|
| 2025-11-08 | Initial VM safe deployment guide | System |
| 2025-11-08 | Added automated deployment script | System |
| 2025-11-08 | Added SSL certificate handling | System |

---

**Last Updated**: November 8, 2025  
**Maintained By**: DevOps Team  
**Version**: 1.0
