# 🚀 Quick Deployment Guide

## For Future Deployments (Use This!)

### ⚡ One-Command Deployment

```bash
ssh ubuntu@150.136.235.189
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector
./scripts/vm_safe_deploy.sh
```

✅ This automatically:
- Backs up VM-specific files
- Pulls latest code
- Restores configurations
- Restarts services
- Validates everything

---

## ❌ DON'T Do This Anymore

```bash
# OLD WAY (causes problems):
git pull origin main
sudo systemctl restart dataguardian
```

**Why not?**
- Overwrites SSL certificates
- Loses environment configs
- Drops VM-specific changes
- Causes 502 errors

---

## 📚 Full Documentation

See: [docs/deployment/VM_SAFE_DEPLOYMENT.md](./docs/deployment/VM_SAFE_DEPLOYMENT.md)

---

## 🆘 Emergency Contacts

- Deployment script: `./scripts/vm_safe_deploy.sh`
- Check logs: `sudo journalctl -u dataguardian -f`
- SSL regenerate: `./scripts/generate_ssl_certificate.sh`
