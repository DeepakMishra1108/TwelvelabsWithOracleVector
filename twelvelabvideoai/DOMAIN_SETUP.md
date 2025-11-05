# Mishras.Online Domain Setup Guide

## 🌐 Current Configuration

The Flask application has been successfully configured to use `mishras.online` as the primary domain.

### ✅ What's Been Done:

1. **Flask App Configuration**
   - Server name set to `mishras.online:8080`
   - CORS headers configured for the domain
   - Security headers added for production
   - Domain-aware health check endpoint

2. **Startup Script Created**
   - `start_mishras_domain.sh` - Easy domain deployment
   - Environment variables pre-configured
   - Automatic directory navigation

3. **Nginx Configuration Template**
   - `nginx-mishras-online.conf` - Production reverse proxy setup
   - SSL/HTTPS configuration
   - Security headers
   - Large file upload support

## 🚀 Current Access Methods:

### Local Development:
- **Direct Flask:** http://127.0.0.1:8080
- **Network Access:** http://192.168.0.123:8080

### Production Domain (requires DNS setup):
- **Target URL:** https://mishras.online:8080
- **HTTP Redirect:** http://mishras.online → https://mishras.online

## 📋 Next Steps for Full Domain Setup:

### 1. DNS Configuration
```bash
# Add these DNS records for mishras.online:
A     mishras.online     YOUR_SERVER_IP
AAAA  mishras.online     YOUR_SERVER_IPv6  # Optional
CNAME www.mishras.online mishras.online
```

### 2. SSL Certificate Setup
```bash
# Using Let's Encrypt (recommended):
sudo certbot --nginx -d mishras.online -d www.mishras.online

# Or use your existing SSL certificate files in:
# /path/to/your/ssl/certificate.crt
# /path/to/your/ssl/private.key
```

### 3. Nginx Setup (Production)
```bash
# Copy the nginx configuration:
sudo cp nginx-mishras-online.conf /etc/nginx/sites-available/mishras-online
sudo ln -s /etc/nginx/sites-available/mishras-online /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

### 4. Firewall Configuration
```bash
# Allow HTTPS traffic:
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp
```

### 5. Production Deployment (Optional)
```bash
# For production, consider using gunicorn:
pip install gunicorn
gunicorn --bind 127.0.0.1:8080 --workers 4 agent_playback_app:app
```

## 🔧 Configuration Files Created:

1. **`.env.domain`** - Environment variables template
2. **`start_mishras_domain.sh`** - Startup script
3. **`nginx-mishras-online.conf`** - Nginx configuration
4. **Flask app** - Updated with domain support

## 🧪 Testing the Setup:

### Local Testing:
```bash
# Start with domain configuration:
./start_mishras_domain.sh

# Test health endpoint:
curl http://127.0.0.1:8080/health
```

### Domain Testing (after DNS setup):
```bash
# Test domain access:
curl https://mishras.online:8080/health

# Test CORS headers:
curl -H "Origin: https://mishras.online" https://mishras.online:8080/health -v
```

## 📱 Application Features Available:

- **Unified Album Upload** - Upload photos & videos to organized albums
- **Cross-Media Search** - Search across photos and videos simultaneously  
- **Vector Embeddings** - TwelveLabs Marengo-based similarity search
- **Oracle VECTOR DB** - High-performance native vector operations
- **Domain Security** - CORS, security headers, and SSL support

## 🔗 Access URLs:

- **Application:** https://mishras.online:8080
- **Health Check:** https://mishras.online:8080/health
- **API Endpoints:** https://mishras.online:8080/api/*

The application is ready for domain deployment! Just complete the DNS and SSL setup steps above.