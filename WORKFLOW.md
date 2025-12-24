# ⚡ Quick Development Workflow

## TEST FIRST - Commit AFTER Success ✅

### Daily Workflow (4 Simple Steps)

```bash
# 1️⃣ Make changes locally
#    Edit files in your IDE/editor

# 2️⃣ Deploy to VM for testing (DON'T commit!)
./deploy_to_vm_test.sh

# 3️⃣ Test on VM
#    Open: https://150.136.235.189:8443
#    Test your changes
#    Check browser console

# 4️⃣ If tests PASS ✅
git add .
git commit -m "Your description"
git push origin main

# 4️⃣ If tests FAIL ❌
./rollback_test.sh
#    Fix issue, try again from step 1
```

---

## Why This Approach?

✅ **GitHub stays clean** - Only working code  
✅ **Easy rollback** - Test backups created automatically  
✅ **Fast iteration** - No git operations during testing  
✅ **Safe testing** - VM is your sandbox  
✅ **Version control** - Only commit after verification  

---

## Scripts Available

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `./deploy_to_vm_test.sh` | Deploy for testing | After making local changes |
| `./rollback_test.sh` | Undo test deployment | If tests fail |
| `./check_sync_status.sh` | Check sync status | Anytime to verify status |
| `./deploy_to_vm.sh` | Full deploy with commit | When you want to commit first (not recommended) |

---

## Example Session

```bash
# Edit index.html to fix a bug
vim src/templates/index.html

# Deploy to VM for testing
./deploy_to_vm_test.sh
# ✓ Files deployed
# ✓ Service restarted
# ✓ Backup created: test_backup_20251224_103045

# Open browser and test
open https://150.136.235.189:8443
# Check if bug is fixed... ✅ Works!

# Commit to GitHub
git add src/templates/index.html
git commit -m "Fix album loading JavaScript bug"
git push origin main

# Done! ✅
```

---

## If Something Goes Wrong

```bash
# Rollback immediately
./rollback_test.sh

# Check what happened
ssh ubuntu@150.136.235.189
sudo journalctl -u dataguardian.service -n 50
```

---

**Remember**: Test on VM → Verify it works → Commit to GitHub  
**Never**: Commit to GitHub → Hope it works → Find out it breaks  

---

See [SYNC_AND_DEPLOY_GUIDE.md](./SYNC_AND_DEPLOY_GUIDE.md) for detailed documentation.
