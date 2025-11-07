# Git History Cleanup - Exposed Credentials

## ⚠️ URGENT: Credentials in Git History

The password `Admin@123` was committed in previous git commits and is still visible in the repository history, even though it's been removed from the current code.

## Immediate Actions Taken ✅

1. ✅ **Changed server password** to: `1tMslvkY9TrCSeQH` (SAVE THIS!)
2. ✅ Removed hardcoded password from `reset_admin_password.py`
3. ✅ Updated script to generate secure random passwords
4. ✅ Added `SECURITY.md` with security policies
5. ✅ Committed and pushed fixes

## Git History Cleanup Required

The following commits contain the exposed password:
- `d0f3e4f` - Fix intermittent login issue
- Earlier commits in the authentication series

### Option 1: Force Push (Recommended for Private Repos)

⚠️ **WARNING**: This rewrites history. All collaborators must re-clone.

```bash
# Backup your repo first
git clone --mirror https://github.com/DeepakMishra1108/TwelvelabsWithOracleVector.git backup/

# Install BFG Repo Cleaner (faster than git filter-branch)
brew install bfg  # macOS
# or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Remove the password from all history
bfg --replace-text passwords.txt TwelvelabsWithOracleVector.git

# Clean up
cd TwelvelabsWithOracleVector
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (⚠️ destructive)
git push origin --force --all
git push origin --force --tags
```

**Create `passwords.txt`:**
```
Admin@123
```

### Option 2: GitHub's Secret Scanning

GitHub may auto-revoke some exposed secrets. Check:
1. Go to repository Settings → Security → Secret scanning alerts
2. Review and resolve any alerts
3. Mark as resolved once password is changed

### Option 3: Accept the Risk

Since you've:
- ✅ Changed the password on the server
- ✅ Removed it from current code
- ✅ The old password no longer works

The risk is mitigated. However, the password remains in git history.

## Verification

Verify the old password no longer works:
```bash
# This should FAIL
curl -X POST http://150.136.235.189/login \
  -d "username=admin&password=Admin@123" \
  -H "Content-Type: application/x-www-form-urlencoded"

# This should SUCCEED  
curl -X POST http://150.136.235.189/login \
  -d "username=admin&password=1tMslvkY9TrCSeQH" \
  -H "Content-Type: application/x-www-form-urlencoded"
```

## Future Prevention

1. ✅ Never hardcode passwords in source code
2. ✅ Use `.env` files (already in .gitignore)
3. ✅ Use GitGuardian pre-commit hooks
4. ✅ Review code before committing
5. ✅ Use password managers for secure storage

## New Admin Credentials

```
URL: http://150.136.235.189
Username: admin
Password: 1tMslvkY9TrCSeQH
```

**SAVE THIS PASSWORD SECURELY!**

## Support

If you need help cleaning git history:
- Contact: deepak_mishra@hotmail.com
- GitGuardian documentation: https://docs.gitguardian.com
