# Security Policy

## Reporting Security Issues

If you discover a security vulnerability, please email: deepak_mishra@hotmail.com

**DO NOT** create a public GitHub issue for security vulnerabilities.

## Important Security Notes

### Credentials Management

⚠️ **NEVER commit credentials to the repository**

- All passwords, API keys, and secrets should be stored in `.env` files
- `.env` files are in `.gitignore` and should NEVER be committed
- Use environment variables for all sensitive configuration

### Admin Password

🔐 The default admin password has been **CHANGED** for security reasons.

**To reset the admin password:**

```bash
ssh ubuntu@150.136.235.189
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector
source twelvelabvideoai/bin/activate
python3 scripts/reset_admin_password.py
```

This will generate a **secure random password**. Save it immediately!

### Secret Key Management

The `FLASK_SECRET_KEY` must be:
- Stored in `.env` file only
- Never committed to git
- Consistent across all application workers
- Kept secret and secure

### Database Credentials

Database connection details are stored in:
- `twelvelabvideoai/wallet/` directory (in `.gitignore`)
- Environment variables in `.env` file

### API Keys

TwelveLabs API key is stored in:
- `.env` file as `TWELVE_LABS_API_KEY`
- Never hardcoded in source files

## Best Practices

1. ✅ Use `.env` files for all secrets
2. ✅ Rotate passwords regularly
3. ✅ Use strong, randomly generated passwords
4. ✅ Never commit `.env` files
5. ✅ Review code before committing
6. ✅ Use GitGuardian or similar tools to scan for exposed secrets
7. ✅ Revoke and rotate any accidentally exposed credentials immediately

## Incident Response

If credentials are exposed:

1. **Immediately** change the exposed password/key
2. Revoke the exposed credential if possible
3. Review access logs for unauthorized access
4. Remove the credential from git history (contact maintainer)
5. Update all systems using the credential

## Contact

For security concerns: deepak_mishra@hotmail.com
