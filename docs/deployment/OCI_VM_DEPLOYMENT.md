# Deploy Data Guardian to OCI Compute Instance

> **Complete guide to deploy Flask application on Oracle Cloud VM**

**Last Updated:** November 7, 2025

---

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Step 1: Create OCI Compute Instance](#step-1-create-oci-compute-instance)
- [Step 2: Configure Network & Security](#step-2-configure-network--security)
- [Step 3: Connect to Your VM](#step-3-connect-to-your-vm)
- [Step 4: Install Dependencies](#step-4-install-dependencies)
- [Step 5: Deploy Application](#step-5-deploy-application)
- [Step 6: Configure Production Server](#step-6-configure-production-server)
- [Step 7: Enable HTTPS (SSL)](#step-7-enable-https-ssl)
- [Step 8: Setup Monitoring](#step-8-setup-monitoring)
- [Troubleshooting](#troubleshooting)

---

## Overview

This guide will help you deploy the Data Guardian Flask application on an OCI Compute instance, connecting to your existing:
- ✅ Oracle Autonomous Database 23ai
- ✅ OCI Object Storage bucket
- ✅ TwelveLabs API

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Internet (Users)                          │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS (443)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              OCI Load Balancer (Optional)                    │
│                  SSL Termination                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            OCI Compute Instance (VM)                         │
│                                                              │
│  • Ubuntu 22.04 / Oracle Linux 8                            │
│  • Gunicorn (WSGI Server)                                   │
│  • Nginx (Reverse Proxy)                                    │
│  • Flask Application                                         │
│  • Python 3.11                                              │
│  • FFmpeg                                                   │
└──────┬──────────────┬──────────────┬────────────────────────┘
       │              │              │
       │ mTLS         │ REST API     │ OCI SDK
       ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
│  Autonomous │ │ TwelveLabs  │ │  OCI Object      │
│  Database   │ │     API     │ │   Storage        │
│   23ai      │ │             │ │                  │
└─────────────┘ └─────────────┘ └──────────────────┘
```

---

## Prerequisites

### OCI Account Setup
- ✅ OCI account with compute quotas
- ✅ Existing Autonomous Database (already configured)
- ✅ Existing Object Storage bucket (already configured)
- ✅ Database wallet files downloaded
- ✅ OCI API keys configured

### Local Setup
- ✅ SSH key pair generated
- ✅ Git installed locally
- ✅ TwelveLabs API key

---

## Step 1: Create OCI Compute Instance

### 1.1 Create VM Instance

1. **Log into OCI Console**: https://cloud.oracle.com/
2. **Navigate**: Compute → Instances → Create Instance

3. **Configure Instance**:
   ```
   Name: data-guardian-app
   Image: Ubuntu 22.04 Minimal
   Shape: VM.Standard.E4.Flex
     - OCPUs: 2 (can start with 1, scale up later)
     - Memory: 16 GB (can start with 8 GB)
   ```

4. **Networking**:
   ```
   VCN: Select your existing VCN (or create new)
   Subnet: Public subnet
   Public IP: Assign a reserved public IP
   ```

5. **SSH Keys**:
   - Upload your SSH public key (`~/.ssh/id_rsa.pub`)
   - Or generate new key pair and download private key

6. **Boot Volume**: 50 GB (minimum)

7. **Click**: Create

### 1.2 Alternative: Use Always-Free Tier

For testing/PoC, use Always-Free compute:
```
Shape: VM.Standard.E2.1.Micro
  - 1 OCPU
  - 1 GB Memory
  - FOREVER FREE
```

**Note**: This is sufficient for testing but not production workloads.

---

## Step 2: Configure Network & Security

### 2.1 Configure Security List

**Add Ingress Rules** (allow incoming traffic):

| Type | Protocol | Port | Source | Description |
|------|----------|------|--------|-------------|
| SSH | TCP | 22 | Your IP/32 | SSH access |
| HTTP | TCP | 80 | 0.0.0.0/0 | Web traffic |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Secure web traffic |
| Custom | TCP | 8080 | Your IP/32 | Dev access (optional) |

**Navigation**: VCN → Security Lists → Default Security List → Add Ingress Rule

### 2.2 Configure Network Security Group (Recommended)

Create NSG for better security:

```bash
# Create NSG
Name: data-guardian-nsg
VCN: Your VCN

# Add Rules
1. Ingress: TCP/22 from your IP (SSH)
2. Ingress: TCP/443 from 0.0.0.0/0 (HTTPS)
3. Egress: TCP/443 to 0.0.0.0/0 (HTTPS outbound for APIs)
4. Egress: TCP/1522 to your DB subnet (Database)
```

### 2.3 Configure Firewall on VM

We'll configure this after connecting to the VM.

---

## Step 3: Connect to Your VM

### 3.1 Get VM Public IP

```bash
# From OCI Console, copy the Public IP address
# Example: 129.213.45.67
```

### 3.2 SSH into VM

```bash
# Replace with your IP and key path
ssh -i ~/.ssh/id_rsa ubuntu@129.213.45.67

# First time, accept fingerprint: yes
```

### 3.3 Update System

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y build-essential curl wget git vim
```

---

## Step 4: Install Dependencies

### 4.1 Install Python 3.11

```bash
# Add deadsnakes PPA for latest Python
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Set Python 3.11 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Verify
python3 --version  # Should show Python 3.11.x
```

### 4.2 Install FFmpeg

```bash
sudo apt install -y ffmpeg

# Verify
ffmpeg -version
```

### 4.3 Install Nginx

```bash
sudo apt install -y nginx

# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Check status
sudo systemctl status nginx
```

### 4.4 Install Oracle Instant Client

```bash
# Download Oracle Instant Client
cd /tmp
wget https://download.oracle.com/otn_software/linux/instantclient/219000/instantclient-basic-linux.x64-21.9.0.0.0dbru.zip

# Install unzip if needed
sudo apt install -y unzip

# Extract
sudo mkdir -p /opt/oracle
sudo unzip instantclient-basic-linux.x64-21.9.0.0.0dbru.zip -d /opt/oracle

# Configure library path
sudo sh -c "echo /opt/oracle/instantclient_21_9 > /etc/ld.so.conf.d/oracle-instantclient.conf"
sudo ldconfig

# Set environment variables
echo 'export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_9:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

---

## Step 5: Deploy Application

### 5.1 Create Application User

```bash
# Create dedicated user for app
sudo useradd -m -s /bin/bash dataguardian
sudo usermod -aG www-data dataguardian

# Switch to app user
sudo su - dataguardian
```

### 5.2 Clone Repository

```bash
# Generate SSH key for GitHub (as dataguardian user)
ssh-keygen -t rsa -b 4096 -C "dataguardian@oci"

# Add public key to GitHub
cat ~/.ssh/id_rsa.pub
# Copy this and add to: GitHub → Settings → SSH and GPG keys

# Clone repository
cd ~
git clone git@github.com:DeepakMishra1108/TwelvelabsWithOracleVector.git
cd TwelvelabsWithOracleVector
```

### 5.3 Setup Virtual Environment

```bash
# Create virtual environment
python3 -m venv twelvelabvideoai
source twelvelabvideoai/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install production server
pip install gunicorn
```

### 5.4 Upload Database Wallet

From your **local machine**, upload wallet:

```bash
# Create wallet directory on VM
ssh ubuntu@129.213.45.67 'sudo mkdir -p /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet && sudo chown dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet'

# Upload wallet files
scp -i ~/.ssh/id_rsa -r /path/to/your/wallet/* ubuntu@129.213.45.67:/tmp/wallet/

# Move to correct location
ssh ubuntu@129.213.45.67 'sudo mv /tmp/wallet/* /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet/ && sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet'
```

### 5.5 Configure Environment Variables

```bash
# As dataguardian user on VM
cd /home/dataguardian/TwelvelabsWithOracleVector

# Create .env file
cat > .env << 'EOF'
# Oracle Database
ORACLE_DB_USERNAME=ADMIN
ORACLE_DB_PASSWORD=your_actual_password_here
ORACLE_DB_CONNECT_STRING=your_connection_string_here
ORACLE_DB_WALLET_PATH=/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet
ORACLE_DB_WALLET_PASSWORD=your_wallet_password

# OCI Object Storage
OCI_BUCKET=Media
OCI_NAMESPACE=your_namespace
OCI_REGION=us-phoenix-1

# TwelveLabs
TWELVE_LABS_API_KEY=your_api_key
TWELVE_LABS_INDEX_ID=your_index_id

# Flask
FLASK_ENV=production
FLASK_SECRET_KEY=your_secret_key_here_min_32_chars
FLASK_HOST=0.0.0.0
FLASK_PORT=8080

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
EOF

# Set secure permissions
chmod 600 .env

# Load environment variables
source .env
```

### 5.6 Test Application

```bash
# Test run (should start without errors)
python src/localhost_only_flask.py

# If successful, you should see:
# * Running on http://0.0.0.0:8080

# Test from another terminal
curl http://localhost:8080

# Stop with Ctrl+C
```

---

## Step 6: Configure Production Server

### 6.1 Create Gunicorn Configuration

```bash
# Create gunicorn config
cat > /home/dataguardian/TwelvelabsWithOracleVector/gunicorn_config.py << 'EOF'
"""Gunicorn configuration for Data Guardian"""

import multiprocessing
import os

# Bind to localhost (Nginx will proxy)
bind = "127.0.0.1:8080"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1  # Common formula
worker_class = "sync"
worker_connections = 1000
max_requests = 1000  # Restart workers after N requests (prevent memory leaks)
max_requests_jitter = 50  # Add randomness to prevent thundering herd

# Timeouts
timeout = 120  # 2 minutes (for video processing)
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "/home/dataguardian/logs/gunicorn-access.log"
errorlog = "/home/dataguardian/logs/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "data-guardian"

# Server mechanics
daemon = False  # systemd will manage this
pidfile = "/home/dataguardian/gunicorn.pid"
user = "dataguardian"
group = "www-data"
umask = 0o007

# SSL (if terminating SSL at Gunicorn instead of Nginx)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"
EOF

# Create logs directory
mkdir -p /home/dataguardian/logs
```

### 6.2 Create Systemd Service

Exit to ubuntu user (or use sudo):

```bash
# Exit dataguardian user
exit

# Create systemd service file
sudo tee /etc/systemd/system/dataguardian.service > /dev/null << 'EOF'
[Unit]
Description=Data Guardian Flask Application
After=network.target

[Service]
Type=notify
User=dataguardian
Group=www-data
WorkingDirectory=/home/dataguardian/TwelvelabsWithOracleVector
Environment="PATH=/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin"
Environment="LD_LIBRARY_PATH=/opt/oracle/instantclient_21_9"
EnvironmentFile=/home/dataguardian/TwelvelabsWithOracleVector/.env

ExecStart=/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/gunicorn \
    --config /home/dataguardian/TwelvelabsWithOracleVector/gunicorn_config.py \
    --chdir /home/dataguardian/TwelvelabsWithOracleVector/src \
    localhost_only_flask:app

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30
PrivateTmp=true
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/dataguardian

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable dataguardian

# Start service
sudo systemctl start dataguardian

# Check status
sudo systemctl status dataguardian
```

### 6.3 Configure Nginx Reverse Proxy

```bash
# Create Nginx site configuration
sudo tee /etc/nginx/sites-available/dataguardian > /dev/null << 'EOF'
# Data Guardian Nginx Configuration

upstream dataguardian_app {
    server 127.0.0.1:8080 fail_timeout=0;
}

server {
    listen 80;
    server_name _;  # Replace with your domain: dataguardian.example.com

    # Redirect HTTP to HTTPS (uncomment after SSL setup)
    # return 301 https://$server_name$request_uri;

    client_max_body_size 500M;  # Max upload size
    client_body_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    # Access logs
    access_log /var/log/nginx/dataguardian-access.log;
    error_log /var/log/nginx/dataguardian-error.log;

    # Static files (if any)
    location /static/ {
        alias /home/dataguardian/TwelvelabsWithOracleVector/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Main application
    location / {
        proxy_pass http://dataguardian_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # For Server-Sent Events (upload progress)
        proxy_buffering off;
        proxy_cache off;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://dataguardian_app;
        access_log off;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/dataguardian /etc/nginx/sites-enabled/

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### 6.4 Configure Firewall

```bash
# Install UFW if not present
sudo apt install -y ufw

# Allow SSH (important - don't lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status
```

---

## Step 7: Enable HTTPS (SSL)

### 7.1 Install Certbot (Let's Encrypt)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate (replace with your domain)
sudo certbot --nginx -d dataguardian.example.com

# Follow prompts:
# - Enter email for renewal notifications
# - Agree to Terms of Service
# - Choose to redirect HTTP to HTTPS (recommended)

# Certbot will automatically:
# 1. Obtain SSL certificate
# 2. Update Nginx configuration
# 3. Setup auto-renewal
```

### 7.2 Test Auto-Renewal

```bash
# Dry run renewal
sudo certbot renew --dry-run

# If successful, auto-renewal is configured
```

### 7.3 Manual SSL (Alternative)

If you have your own SSL certificate:

```bash
# Copy certificate files to VM
sudo mkdir -p /etc/nginx/ssl
sudo cp your_cert.crt /etc/nginx/ssl/
sudo cp your_key.key /etc/nginx/ssl/
sudo chmod 600 /etc/nginx/ssl/*

# Update Nginx config to use SSL
# See commented SSL section in nginx config above
```

---

## Step 8: Setup Monitoring

### 8.1 Application Logs

```bash
# View application logs
sudo journalctl -u dataguardian -f

# View Nginx logs
sudo tail -f /var/log/nginx/dataguardian-access.log
sudo tail -f /var/log/nginx/dataguardian-error.log

# View Gunicorn logs
sudo tail -f /home/dataguardian/logs/gunicorn-error.log
```

### 8.2 Setup Log Rotation

```bash
sudo tee /etc/logrotate.d/dataguardian > /dev/null << 'EOF'
/home/dataguardian/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 dataguardian www-data
    sharedscripts
    postrotate
        systemctl reload dataguardian > /dev/null 2>&1 || true
    endscript
}
EOF
```

### 8.3 Setup Basic Monitoring

```bash
# Install monitoring tools
sudo apt install -y htop iotop nethogs

# Check resource usage
htop

# Monitor network
nethogs

# Check disk usage
df -h

# Check memory
free -h
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check systemd status
sudo systemctl status dataguardian

# Check logs for errors
sudo journalctl -u dataguardian -n 100 --no-pager

# Check if port is in use
sudo netstat -tulpn | grep 8080

# Test manually
sudo su - dataguardian
cd TwelvelabsWithOracleVector
source twelvelabvideoai/bin/activate
python src/localhost_only_flask.py
```

### Database Connection Issues

```bash
# Test database connectivity
cd /home/dataguardian/TwelvelabsWithOracleVector
source twelvelabvideoai/bin/activate
python -c "import oracledb; print('Oracle client version:', oracledb.clientversion())"

# Check wallet files
ls -la twelvelabvideoai/wallet/

# Test connection
python -c "
import oracledb
oracledb.init_oracle_client(lib_dir='/opt/oracle/instantclient_21_9')
# Add your connection test here
"
```

### Nginx Issues

```bash
# Test Nginx config
sudo nginx -t

# Check Nginx status
sudo systemctl status nginx

# Restart Nginx
sudo systemctl restart nginx

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log
```

### Firewall Blocking Traffic

```bash
# Check firewall rules
sudo ufw status verbose

# Check if port is open
sudo netstat -tulpn | grep :80
sudo netstat -tulpn | grep :443

# Test from outside
curl -I http://YOUR_VM_IP
```

### Performance Issues

```bash
# Check CPU/Memory
htop

# Check disk I/O
iotop

# Check network
nethogs

# Adjust Gunicorn workers
# Edit gunicorn_config.py and change workers count

# Restart service
sudo systemctl restart dataguardian
```

---

## Next Steps

### 1. Setup Load Balancer (Production)

For high availability, add an OCI Load Balancer:
- Distributes traffic across multiple VMs
- SSL termination at load balancer
- Health checks and auto-failover

### 2. Setup Auto-Scaling

Configure OCI Instance Pools for auto-scaling:
- Scale up during high traffic
- Scale down to save costs
- Automatic health monitoring

### 3. Setup Backup

```bash
# Backup application code
cd /home/dataguardian
tar -czf backup-$(date +%Y%m%d).tar.gz TwelvelabsWithOracleVector/

# Upload to Object Storage
oci os object put --bucket-name backups --file backup-*.tar.gz
```

### 4. Setup CI/CD

Automate deployments using GitHub Actions or OCI DevOps.

---

## Quick Reference

### Start/Stop/Restart

```bash
# Application
sudo systemctl start dataguardian
sudo systemctl stop dataguardian
sudo systemctl restart dataguardian
sudo systemctl status dataguardian

# Nginx
sudo systemctl start nginx
sudo systemctl stop nginx
sudo systemctl restart nginx
sudo systemctl reload nginx  # Reload config without downtime
```

### Update Application

```bash
# As dataguardian user
cd /home/dataguardian/TwelvelabsWithOracleVector
git pull origin main
source twelvelabvideoai/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart dataguardian
```

### View Logs

```bash
# Real-time application logs
sudo journalctl -u dataguardian -f

# Last 100 lines
sudo journalctl -u dataguardian -n 100

# Filter by date
sudo journalctl -u dataguardian --since "2025-11-07"
```

---

## Security Checklist

- [ ] SSH key-based authentication only (disable password auth)
- [ ] Firewall configured (UFW enabled)
- [ ] SSL certificate installed
- [ ] Strong passwords in .env file
- [ ] .env file has 600 permissions
- [ ] Database wallet secured
- [ ] Nginx security headers enabled
- [ ] Regular security updates scheduled
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented

---

**Deployment Complete!** 🚀

Your Data Guardian application is now running on OCI VM with production-grade configuration.

**Access your application at**: `http://YOUR_VM_IP` or `https://your-domain.com`
