# 🔐 SSL Quick Start Guide

## ⚡ TL;DR - Get HTTPS Running in 2 Minutes

```bash
# 1. Generate SSL certificate
cd scripts && ./generate_ssl_certificate.sh && cd ..

# 2. Start with SSL (already configured in .env)
./start_secure.sh

# 3. Open browser
# Visit: https://localhost:8443
# Accept browser warning (this is normal for self-signed certs)
```

---

## 🎯 Essential Commands

| Task | Command |
|------|---------|
| **Generate Certificate** | `./scripts/generate_ssl_certificate.sh` |
| **Start with HTTPS** | `./start_secure.sh` |
| **Start with HTTP** | Set `SSL_ENABLED="false"` in .env |
| **View Certificate** | `openssl x509 -in ssl/certificate.crt -text -noout` |
| **Check Expiry** | `openssl x509 -in ssl/certificate.crt -noout -dates` |
| **Test Connection** | `curl -k https://localhost:8443/health` |

---

## 🌐 Browser Warnings - Quick Fix

### Chrome/Edge
**Warning:** "Your connection is not private"  
**Fix:** Click "Advanced" → "Proceed to localhost" or type `thisisunsafe`

### Firefox  
**Warning:** "Your connection is not secure"  
**Fix:** Click "Advanced" → "Accept the Risk and Continue"

### Safari
**Warning:** "This Connection Is Not Private"  
**Fix:** Click "Show Details" → "visit this website"

---

## 🔧 Configuration (.env)

```bash
# Enable/Disable HTTPS
SSL_ENABLED="true"          # true = HTTPS, false = HTTP

# Certificate paths (relative to project root)
SSL_CERT_PATH="ssl/certificate.crt"
SSL_KEY_PATH="ssl/private.key"

# Port configuration
FLASK_PORT="8443"           # HTTPS port (8443 or 443)
# FLASK_PORT="8080"         # HTTP port (if SSL disabled)

# Host (localhost only for security)
FLASK_HOST="127.0.0.1"
```

---

## 📂 File Structure

```
TwelvelabsVideoAI/
├── ssl/
│   ├── certificate.crt    ✅ Public (safe to share)
│   └── private.key        🔒 PRIVATE (never commit!)
├── scripts/
│   └── generate_ssl_certificate.sh
└── start_secure.sh
```

---

## 🐛 Troubleshooting

### Problem: SSL certificates not found
```bash
# Solution: Generate them
./scripts/generate_ssl_certificate.sh
```

### Problem: Port already in use
```bash
# Solution: Kill process or use different port
lsof -i :8443
kill -9 <PID>
# OR change FLASK_PORT in .env
```

### Problem: Browser keeps showing warning
**This is NORMAL!** Self-signed certificates always trigger warnings.  
Just accept it each time or add certificate to system trust store.

---

## 🔄 Switch Between HTTP/HTTPS

**HTTPS Mode:**
```bash
# In .env
SSL_ENABLED="true"
FLASK_PORT="8443"

# Restart
./start_secure.sh
```

**HTTP Mode:**
```bash
# In .env
SSL_ENABLED="false"
FLASK_PORT="8080"

# Restart
python3 src/localhost_only_flask.py
```

---

## 📞 URLs

| Mode | URL |
|------|-----|
| **HTTPS** | https://localhost:8443 |
| **HTTP** | http://localhost:8080 |
| **Health Check** | /health |
| **Config Debug** | /config_debug |

---

## ⚠️ Security Notes

- ✅ Self-signed certificates are **perfect for development**
- ❌ **DO NOT** use self-signed certificates in production
- 🔒 **NEVER** commit `ssl/private.key` to git
- 🔄 **Rotate** certificates every 90 days
- 📅 **Monitor** certificate expiration dates

---

## 📚 Full Documentation

For detailed information, see: [SSL_TLS_CONFIGURATION.md](docs/guides/SSL_TLS_CONFIGURATION.md)

---

**Need Help?** Check the troubleshooting section in the full documentation.
