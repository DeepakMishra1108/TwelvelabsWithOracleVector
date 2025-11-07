# SSL/TLS Configuration Guide
**Date:** November 8, 2025  
**Feature:** HTTPS Support with Self-Signed Certificates

---

## 🔐 Overview

This guide explains how to enable HTTPS/SSL for the DataGuardian Flask application using self-signed certificates for local development and testing.

## ✨ Features

- ✅ **TLS 1.2/1.3 Support** - Modern encryption protocols
- ✅ **Self-Signed Certificates** - No external CA required
- ✅ **Easy Configuration** - Simple environment variable setup
- ✅ **Automatic Generation** - Script creates certificates automatically
- ✅ **Dual Mode** - Switch between HTTP and HTTPS easily
- ✅ **Subject Alternative Names (SAN)** - Proper certificate validation
- ✅ **Secure Key Storage** - Proper file permissions

---

## 🚀 Quick Start

### 1. Generate SSL Certificate

```bash
cd scripts
./generate_ssl_certificate.sh
```

This creates:
- `ssl/private.key` - Private key (2048-bit RSA)
- `ssl/certificate.crt` - Self-signed certificate (valid 365 days)

### 2. Configure Environment

The `.env` file already includes SSL configuration:

```bash
# SSL/TLS Configuration
SSL_ENABLED="true"
SSL_CERT_PATH="ssl/certificate.crt"
SSL_KEY_PATH="ssl/private.key"
FLASK_PORT="8443"
FLASK_HOST="127.0.0.1"
```

### 3. Start Application

```bash
# Use the secure startup script
./start_secure.sh

# Or run directly
python3 src/localhost_only_flask.py
```

### 4. Access Application

- **URL**: https://localhost:8443
- **Health**: https://localhost:8443/health
- **Config**: https://localhost:8443/config_debug

---

## 📋 Certificate Details

### Generated Certificate Specifications

| Property | Value |
|----------|-------|
| **Key Type** | RSA 2048-bit |
| **Algorithm** | SHA-256 |
| **Validity** | 365 days |
| **Common Name** | localhost |
| **Organization** | DataGuardian |
| **Country** | US |
| **State** | California |
| **City** | San Francisco |

### Subject Alternative Names (SAN)

The certificate includes multiple SANs for flexibility:

- DNS: `localhost`
- DNS: `127.0.0.1`
- DNS: `::1`
- IP: `127.0.0.1`
- IP: `::1` (IPv6)

---

## 🌐 Browser Configuration

### Expected Behavior

When accessing https://localhost:8443, browsers will show a security warning because the certificate is self-signed (not from a trusted Certificate Authority).

**This is NORMAL and EXPECTED for development!**

### Browser-Specific Instructions

#### 🦊 Firefox
1. Warning: "Your connection is not secure"
2. Click **"Advanced"**
3. Click **"Accept the Risk and Continue"**
4. Or click **"Add Exception"** → **"Confirm Security Exception"**

#### 🔵 Chrome/Edge
1. Warning: "Your connection is not private"
2. Click **"Advanced"**
3. Click **"Proceed to localhost (unsafe)"**
4. Or type: **`thisisunsafe`** (literally type this on the warning page)

#### 🧭 Safari
1. Warning: "This Connection Is Not Private"
2. Click **"Show Details"**
3. Click **"visit this website"**
4. Enter your Mac password if prompted
5. Click **"Visit Website"** again

---

## 🔧 Configuration Options

### Environment Variables

All SSL settings are configured in `.env`:

```bash
# Enable/Disable SSL (true/false)
SSL_ENABLED="true"

# Path to SSL certificate (relative to project root)
SSL_CERT_PATH="ssl/certificate.crt"

# Path to private key (relative to project root)
SSL_KEY_PATH="ssl/private.key"

# Port for HTTPS (standard: 443, dev: 8443)
FLASK_PORT="8443"

# Host binding (localhost only for security)
FLASK_HOST="127.0.0.1"
```

### Switch Between HTTP and HTTPS

**Enable HTTPS:**
```bash
# In .env
SSL_ENABLED="true"
FLASK_PORT="8443"

# Restart application
./start_secure.sh
```

**Disable HTTPS (HTTP only):**
```bash
# In .env
SSL_ENABLED="false"
FLASK_PORT="8080"

# Restart application
python3 src/localhost_only_flask.py
```

---

## 🛠️ Certificate Management

### View Certificate Details

```bash
# Full certificate info
openssl x509 -in ssl/certificate.crt -text -noout

# Subject and validity dates
openssl x509 -in ssl/certificate.crt -noout -subject -dates

# SHA-256 fingerprint
openssl x509 -in ssl/certificate.crt -noout -fingerprint -sha256
```

### Verify Certificate and Key Match

```bash
# Get certificate modulus
openssl x509 -noout -modulus -in ssl/certificate.crt | openssl md5

# Get private key modulus (should match above)
openssl rsa -noout -modulus -in ssl/private.key | openssl md5
```

### Regenerate Certificate

```bash
# Remove old certificate
rm -rf ssl/

# Generate new certificate
cd scripts
./generate_ssl_certificate.sh
cd ..

# Restart application
./start_secure.sh
```

### Custom Certificate Parameters

Edit `scripts/generate_ssl_certificate.sh` to customize:

```bash
# Certificate validity (days)
DAYS_VALID=365

# Organization details
COUNTRY="US"
STATE="California"
CITY="San Francisco"
ORG="DataGuardian"
COMMON_NAME="localhost"
```

---

## 🔒 Security Considerations

### Development vs Production

**⚠️ Important: Self-signed certificates are for DEVELOPMENT ONLY**

For production deployment:
1. Use certificates from a trusted CA (Let's Encrypt, DigiCert, etc.)
2. Use proper domain names (not localhost)
3. Implement certificate pinning if needed
4. Enable HSTS (HTTP Strict Transport Security)
5. Configure proper TLS cipher suites

### File Permissions

The certificate generation script automatically sets secure permissions:

```bash
# Private key - Read-only for owner
chmod 600 ssl/private.key

# Certificate - Read for all (public info)
chmod 644 ssl/certificate.crt
```

### Best Practices

1. **Never commit** `ssl/private.key` to version control
2. **Rotate certificates** regularly (every 90 days recommended)
3. **Monitor expiration** dates
4. **Keep private key** secure and backed up separately
5. **Use strong passphrases** if encrypting private keys

---

## 📂 File Structure

```
TwelvelabsVideoAI/
├── ssl/                              # SSL certificates directory
│   ├── certificate.crt               # Public certificate
│   └── private.key                   # Private key (keep secure!)
├── scripts/
│   └── generate_ssl_certificate.sh   # Certificate generator
├── src/
│   └── localhost_only_flask.py       # Flask app (SSL-enabled)
├── .env                              # Environment config
├── .gitignore                        # Excludes ssl/private.key
└── start_secure.sh                   # Startup script
```

---

## 🧪 Testing SSL Configuration

### 1. Test HTTPS Connection

```bash
# Using curl (accept self-signed cert)
curl -k https://localhost:8443/health

# View SSL handshake details
curl -vk https://localhost:8443/health
```

### 2. Test with OpenSSL Client

```bash
# Connect and view certificate
openssl s_client -connect localhost:8443 -showcerts

# Test specific TLS version
openssl s_client -connect localhost:8443 -tls1_2
openssl s_client -connect localhost:8443 -tls1_3
```

### 3. Verify Certificate Chain

```bash
# Verify certificate
openssl verify ssl/certificate.crt

# Note: Self-signed will show "unable to get local issuer certificate"
# This is expected for self-signed certificates
```

---

## 🐛 Troubleshooting

### Issue: "SSL certificates not found"

**Symptoms:**
```
❌ SSL enabled but certificate files not found!
   Expected: /path/to/ssl/certificate.crt
   Expected: /path/to/ssl/private.key
```

**Solution:**
```bash
cd scripts
./generate_ssl_certificate.sh
```

### Issue: "Permission denied" on private key

**Symptoms:**
```
[Errno 13] Permission denied: 'ssl/private.key'
```

**Solution:**
```bash
chmod 600 ssl/private.key
```

### Issue: Browser shows "NET::ERR_CERT_AUTHORITY_INVALID"

**This is NORMAL for self-signed certificates!**

**Solution:** Follow browser-specific instructions above to accept the certificate.

### Issue: "Address already in use" error

**Symptoms:**
```
OSError: [Errno 48] Address already in use
```

**Solution:**
```bash
# Find process using port 8443
lsof -i :8443

# Kill the process
kill -9 <PID>

# Or use different port in .env
FLASK_PORT="8444"
```

### Issue: Flask falls back to HTTP

**Check logs for:**
```
❌ SSL enabled but certificate files not found!
   Falling back to HTTP mode...
```

**Solution:** Verify paths in `.env` and regenerate certificates.

---

## 📊 Performance Impact

### SSL/TLS Overhead

Adding SSL/TLS has minimal impact on localhost development:

| Metric | HTTP | HTTPS | Overhead |
|--------|------|-------|----------|
| Handshake | N/A | ~10-50ms | One-time |
| Request Latency | <5ms | <10ms | ~5ms |
| Throughput | ~100 MB/s | ~95 MB/s | ~5% |
| CPU Usage | Baseline | +2-5% | Minimal |

**Recommendation:** Keep SSL enabled for development to match production environment.

---

## 🔄 Upgrading to Production Certificates

When deploying to production, replace self-signed certificates with proper CA-signed certificates:

### Option 1: Let's Encrypt (Free)

```bash
# Install certbot
sudo apt-get install certbot

# Get certificate (requires domain and port 80)
sudo certbot certonly --standalone -d yourdomain.com

# Update .env
SSL_CERT_PATH="/etc/letsencrypt/live/yourdomain.com/fullchain.pem"
SSL_KEY_PATH="/etc/letsencrypt/live/yourdomain.com/privkey.pem"
```

### Option 2: Commercial CA

1. Generate CSR: `openssl req -new -key private.key -out request.csr`
2. Submit CSR to CA (DigiCert, GlobalSign, etc.)
3. Download signed certificate
4. Update paths in `.env`

---

## 📚 Additional Resources

### Documentation
- [OpenSSL Documentation](https://www.openssl.org/docs/)
- [Flask SSL/TLS Guide](https://flask.palletsprojects.com/en/stable/deploying/ssl/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)

### Tools
- [SSL Labs Server Test](https://www.ssllabs.com/ssltest/)
- [Certificate Decoder](https://www.sslshopper.com/certificate-decoder.html)
- [OpenSSL Command Generator](https://www.sslshopper.com/article-most-common-openssl-commands.html)

---

## ✅ Verification Checklist

After setup, verify:

- [ ] SSL certificates generated in `ssl/` directory
- [ ] Private key has 600 permissions (`ls -l ssl/private.key`)
- [ ] Certificate is valid (`openssl x509 -in ssl/certificate.crt -noout -dates`)
- [ ] `.env` has `SSL_ENABLED="true"`
- [ ] Application starts without errors
- [ ] Can access https://localhost:8443
- [ ] Browser shows certificate details (click padlock icon)
- [ ] Health endpoint returns 200 OK
- [ ] No console errors in browser

---

## 🎓 Understanding Self-Signed Certificates

### What is a Self-Signed Certificate?

A self-signed certificate is a digital certificate that is signed by the creator rather than a trusted Certificate Authority (CA).

**Pros:**
- ✅ Free (no CA fees)
- ✅ Quick to generate
- ✅ Full control
- ✅ Perfect for development/testing
- ✅ Same encryption as CA-signed

**Cons:**
- ❌ Not trusted by browsers by default
- ❌ Requires manual trust installation
- ❌ No identity verification
- ❌ Not suitable for public websites

### Certificate Trust Chain

**CA-Signed Certificate:**
```
Root CA → Intermediate CA → Your Certificate → Your Server
(Trusted)   (Trusted)        (Trusted)         (HTTPS ✅)
```

**Self-Signed Certificate:**
```
Your Certificate → Your Server
(Not Trusted)      (Warning ⚠️)
```

---

**Last Updated:** November 8, 2025  
**Version:** 1.0  
**Status:** ✅ Production Ready (Development Use)
