# Complete VM Deployment Guide - All Phases

## 🎯 Deployment Overview

Deploy **ALL 20+ commits** from Phase 1-4, Rate Limiting, OCI Multi-Tenant, Admin Dashboard, and Testing to production VM.

**Target**: 150.136.235.189 (ubuntu@mishras.online)  
**Service**: dataguardian  
**Time**: ~5 minutes automated

## 🚀 One-Command Deployment

```bash
ssh ubuntu@150.136.235.189 << 'ENDSSH'
cd /home/ubuntu/TwelvelabsVideoAI
git fetch origin main && \
git checkout origin/main -- scripts/deploy_to_production.sh && \
chmod +x scripts/deploy_to_production.sh && \
./scripts/deploy_to_production.sh
ENDSSH
```

## 📦 What's Being Deployed (Summary)

| Component | Commits | Lines | Status |
|-----------|---------|-------|--------|
| Phase 1-4: Multi-Tenant RBAC | ec78289-b116e5b | 3100+ | ✅ |
| Rate Limiting System | 87c7aa4-8fa100c | 1500+ | ✅ |
| OCI Multi-Tenant Paths | 9c863c6 | 400+ | ✅ |
| Admin Dashboard | 90a4d86-e6e53bb | 800+ | ✅ |
| Testing Infrastructure | 902217f-f20080d | 1200+ | ✅ |
| **TOTAL** | **20+ commits** | **7000+** | **✅ Ready** |

## ✅ Quick Verification After Deployment

```bash
# 1. Service running?
sudo systemctl status dataguardian
# Expected: active (running)

# 2. No errors?
sudo journalctl -u dataguardian --since "2 minutes ago" | grep -i error
# Expected: No critical errors

# 3. App responding?
curl -I http://localhost:8080/
# Expected: HTTP/1.1 200 or 302

# 4. External access?
curl -I https://mishras.online/
# Expected: HTTP/2 200

# 5. Admin dashboard?
# Browser: https://mishras.online/admin/quotas
# Expected: Dashboard loads with user list
```

## 🔧 If Issues Occur

### Service won't start:
```bash
sudo journalctl -u dataguardian -n 100  # Check logs
sudo lsof -i :8080                       # Check port
python3 src/localhost_only_flask.py      # Run manually
```

### Database errors:
```bash
python3 scripts/test_db_connection.py   # Test DB
ls -la twelvelabvideoai/wallet/          # Check wallet
cat .env | grep ORACLE_DB                # Check credentials
```

### Rollback if needed:
```bash
cd /home/ubuntu/backups
ls -lt backup_*.tar.gz | head -1         # Find latest backup
# Then extract and restart service
```

## 📚 Full Documentation

- **`DEPLOYMENT_QUICKSTART.md`** - Detailed step-by-step guide
- **`scripts/deploy_to_production.sh`** - Automated deployment script
- **`MULTI_TENANT_COMPLETE.md`** - Phase 1-4 features
- **`RATE_LIMITING_OCI_STORAGE.md`** - Rate limiting details
- **`ADMIN_DASHBOARD_COMPLETE.md`** - Dashboard features
- **`OCI_PATH_ISOLATION_TESTING.md`** - Testing procedures

## 🎯 Success Criteria

✅ Service: `active (running)`  
✅ Logs: No errors in last 5 min  
✅ HTTP: Returns 200/302  
✅ Login: Works correctly  
✅ Dashboard: `https://mishras.online/admin/quotas` accessible  
✅ Features: Multi-tenant, rate limiting, admin tools all functional

---

**Script**: `./scripts/deploy_to_production.sh`  
**Auto**: Backup → Stop → Pull → Migrate → Start → Verify  
**Safe**: Creates backup before changes, can rollback anytime
