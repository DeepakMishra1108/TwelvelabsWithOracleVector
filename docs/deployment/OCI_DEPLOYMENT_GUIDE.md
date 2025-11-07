# 🚀 OCI VM Deployment Guide

Complete guide to deploy Data Guardian Flask application on Oracle Cloud Infrastructure VM.

---

## 📋 Prerequisites

### OCI Resources

- ✅ **Oracle Autonomous Database** (already configured)
- ✅ **OCI Object Storage Bucket** (already configured)
- ⬜ **OCI Compute VM** (to be created)
- ⬜ **Public IP Address**
- ⬜ **VCN with Internet Gateway** (see [Network Setup Guide](OCI_NETWORK_SETUP.md))

### Local Requirements

- SSH client
- OCI CLI (optional)
- Database wallet files
- `.env` configuration file

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Internet                              │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS (Port 443)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                 OCI Compute VM (Ubuntu)                       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    Nginx (Port 80/443)                 │  │
│  │         Reverse Proxy + SSL Termination               │  │
│  └─────────────────────┬──────────────────────────────────┘  │
│                        │ HTTP (localhost:8080)                │
│  ┌─────────────────────▼──────────────────────────────────┐  │
│  │              Gunicorn (WSGI Server)                    │  │
│  │         Workers: CPU_COUNT * 2 + 1                     │  │
│  └─────────────────────┬──────────────────────────────────┘  │
│                        │                                      │
│  ┌─────────────────────▼──────────────────────────────────┐  │
│  │          Flask Application (localhost_only_flask)      │  │
│  │  - TwelveLabs AI Integration                          │  │
│  │  - Oracle DB Queries (Vector Search)                  │  │
│  │  - OCI Object Storage API                             │  │
│  └────────────────────────────────────────────────────────┘  │
└────────┬────────────────┬────────────────────┬───────────────┘
         │                │                    │
         │ mTLS          │ REST API           │ REST API
         ▼                ▼                    ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ Oracle ADB 23ai │ │ TwelveLabs   │ │ OCI Object Storage   │
│ • Vector Search │ │ • Marengo AI │ │ • Media Files        │
│ • Metadata      │ │ • Embeddings │ │ • 11 9s Durability   │
└─────────────────┘ └──────────────┘ └──────────────────────┘
```

---

## 🖥️ Step 1: Create OCI Compute Instance

### 1.1 Create VM via OCI Console

1. Navigate to **Compute** > **Instances** > **Create Instance**
2. Configure:
   - **Name**: `dataguardian-app-server`
   - **Image**: `Ubuntu 22.04 LTS`
   - **Shape**: `VM.Standard.E4.Flex` (2 OCPUs, 16GB RAM recommended)
   - **VCN**: Select your existing VCN
   - **Subnet**: Public subnet with internet gateway
   - **Public IP**: Assign public IPv4 address
   - **SSH Key**: Upload your public SSH key

3. Click **Create**

### 1.2 Configure Network Access

**IMPORTANT**: Your VM needs bidirectional internet access:
- **Inbound**: Public access to HTTP/HTTPS (ports 80/443)
- **Outbound**: VM access to TwelveLabs API, GitHub, PyPI, Oracle services

For detailed network configuration including:
- Security List ingress/egress rules
- Internet Gateway setup
- Route table verification
- Connectivity testing
- Troubleshooting

**See: [OCI_NETWORK_SETUP.md](OCI_NETWORK_SETUP.md)** ← Complete network configuration guide

**Quick checklist:**
- [ ] Security List has ingress rules (0.0.0.0/0 → ports 22, 80, 443)
- [ ] Security List has egress rules (0.0.0.0/0 → all protocols)
- [ ] Route table has route: 0.0.0.0/0 → Internet Gateway
- [ ] Internet Gateway is attached and enabled
- [ ] VM is in public subnet with public IP assigned

### 1.3 Connect to VM

```bash
ssh -i ~/.ssh/your_key ubuntu@<VM_PUBLIC_IP>
```

---

## 🔧 Step 2: Initial VM Setup

### 2.1 Run System Setup Script

```bash
# Clone repository
git clone https://github.com/DeepakMishra1108/TwelvelabsWithOracleVector.git
cd TwelvelabsWithOracleVector

# Make scripts executable
chmod +x scripts/*.sh

# Run system setup (as ubuntu user)
./scripts/setup_oci_vm.sh
```

This installs:
- ✅ Python 3.11
- ✅ FFmpeg
- ✅ Nginx
- ✅ Oracle Instant Client
- ✅ System utilities

### 2.2 Switch to Application User

```bash
sudo su - dataguardian
cd /home/dataguardian
```

---

## 📦 Step 3: Upload Configuration Files

### 3.1 Upload Database Wallet

From your **local machine**:

```bash
# Copy wallet to VM
scp -r ~/path/to/wallet/* ubuntu@<VM_IP>:/tmp/wallet/

# SSH to VM and move wallet
ssh ubuntu@<VM_IP>
sudo mkdir -p /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet
sudo mv /tmp/wallet/* /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet/
sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector
```

### 3.2 Create .env File

```bash
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector

# Create .env file
cat > .env << 'EOF'
# Oracle Database
ORACLE_DB_USERNAME=ADMIN
ORACLE_DB_PASSWORD=YourStrongPassword123!
ORACLE_DB_CONNECT_STRING=your_db_high
ORACLE_DB_WALLET_PATH=/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet
ORACLE_DB_WALLET_PASSWORD=YourWalletPassword

# OCI Object Storage
OCI_BUCKET=Media
OCI_NAMESPACE=your_tenancy_namespace
OCI_REGION=us-phoenix-1

# TwelveLabs
TWELVE_LABS_API_KEY=tlk_xxxxxxxxxxxxxxxxxx
TWELVE_LABS_INDEX_ID=your_index_id

# Flask
FLASK_ENV=production
FLASK_SECRET_KEY=generate_32_char_random_key_here
FLASK_HOST=0.0.0.0
FLASK_PORT=8080

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
EOF

# Secure the file
chmod 600 .env
```

### 3.3 Clone Repository (if not already done)

```bash
cd /home/dataguardian
git clone https://github.com/DeepakMishra1108/TwelvelabsWithOracleVector.git
cd TwelvelabsWithOracleVector
```

---

## 🚀 Step 4: Deploy Application

### 4.1 Run Deployment Script

```bash
# Ensure you're the dataguardian user
sudo su - dataguardian
cd /home/dataguardian/TwelvelabsWithOracleVector

# Run deployment
./scripts/deploy_app.sh
```

The script will:
1. ✅ Create Python virtual environment
2. ✅ Install dependencies (Flask, oracledb, gunicorn, etc.)
3. ✅ Create directories (logs, uploads, temp)
4. ✅ Configure Gunicorn
5. ✅ Create systemd service
6. ✅ Configure Nginx reverse proxy
7. ✅ Start services

### 4.2 Verify Deployment

```bash
# Check service status
sudo systemctl status dataguardian
sudo systemctl status nginx

# View logs
sudo journalctl -u dataguardian -f

# Test application
curl http://localhost:8080/health
```

---

## 🌐 Step 5: Access Application

### 5.1 Get Public IP

```bash
curl ifconfig.me
```

### 5.2 Access via Browser

```
http://<VM_PUBLIC_IP>
```

You should see the Data Guardian interface!

---

## 🔒 Step 6: Setup SSL (Optional but Recommended)

### 6.1 Configure Domain Name

1. Point your domain DNS to VM public IP:
   ```
   A Record: dataguardian.yourdomain.com → <VM_PUBLIC_IP>
   ```

2. Wait for DNS propagation (5-30 minutes)

### 6.2 Install SSL Certificate

```bash
# Get free SSL certificate from Let's Encrypt
sudo certbot --nginx -d dataguardian.yourdomain.com

# Follow prompts:
# - Enter email address
# - Agree to terms
# - Choose: Redirect HTTP to HTTPS
```

### 6.3 Test SSL

```
https://dataguardian.yourdomain.com
```

Certbot auto-renewal is configured. Certificates renew automatically every 90 days.

---

## 🛠️ Management Commands

### Service Management

```bash
# Start service
sudo systemctl start dataguardian

# Stop service
sudo systemctl stop dataguardian

# Restart service
sudo systemctl restart dataguardian

# Check status
sudo systemctl status dataguardian

# View logs
sudo journalctl -u dataguardian -f
sudo journalctl -u dataguardian -n 100
```

### Application Updates

```bash
# Pull latest code
cd /home/dataguardian/TwelvelabsWithOracleVector
git pull origin main

# Activate venv and update dependencies
source twelvelabvideoai/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart dataguardian
```

### Log Files

```bash
# Application logs
tail -f /home/dataguardian/logs/gunicorn-access.log
tail -f /home/dataguardian/logs/gunicorn-error.log

# Nginx logs
sudo tail -f /var/log/nginx/dataguardian-access.log
sudo tail -f /var/log/nginx/dataguardian-error.log

# System logs
sudo journalctl -u dataguardian -f
```

### Performance Monitoring

```bash
# System resources
htop

# Network connections
sudo nethogs

# Disk I/O
sudo iotop

# Application processes
ps aux | grep gunicorn
```

---

## 🐛 Troubleshooting

### Service Won't Start

```bash
# Check detailed error
sudo journalctl -u dataguardian -xe

# Common issues:
# 1. Wallet files missing
ls -la /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet

# 2. Environment variables
cat /home/dataguardian/TwelvelabsWithOracleVector/.env

# 3. Python dependencies
source /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/activate
pip list

# 4. Test Python imports
python -c "import oracledb; import flask; print('OK')"
```

### Database Connection Issues

```bash
# Test Oracle client
export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_9:$LD_LIBRARY_PATH
python -c "import oracledb; print(oracledb.version)"

# Check wallet files
ls -la /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet/
# Should see: cwallet.sso, tnsnames.ora, sqlnet.ora, etc.

# Test connection
python3 << EOF
import oracledb
import os

oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_21_9")

conn = oracledb.connect(
    user=os.getenv('ORACLE_DB_USERNAME'),
    password=os.getenv('ORACLE_DB_PASSWORD'),
    dsn=os.getenv('ORACLE_DB_CONNECT_STRING'),
    config_dir=os.getenv('ORACLE_DB_WALLET_PATH'),
    wallet_location=os.getenv('ORACLE_DB_WALLET_PATH'),
    wallet_password=os.getenv('ORACLE_DB_WALLET_PASSWORD')
)
print("✓ Connected successfully!")
conn.close()
EOF
```

### Nginx Issues

```bash
# Test Nginx config
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx

# Check Nginx status
sudo systemctl status nginx

# View Nginx error log
sudo tail -f /var/log/nginx/error.log
```

### Port Already in Use

```bash
# Check what's using port 8080
sudo lsof -i :8080
sudo netstat -tulpn | grep :8080

# Kill process if needed
sudo kill <PID>
```

### High Memory Usage

```bash
# Check memory
free -h

# Reduce Gunicorn workers
# Edit: /home/dataguardian/TwelvelabsWithOracleVector/gunicorn_config.py
workers = 4  # Reduce from default

# Restart
sudo systemctl restart dataguardian
```

---

## 📊 Performance Tuning

### Gunicorn Configuration

Edit `/home/dataguardian/TwelvelabsWithOracleVector/gunicorn_config.py`:

```python
# For high-traffic sites
workers = 8  # Increase workers
worker_class = "gevent"  # Use async workers
worker_connections = 2000

# For low-memory VMs
workers = 2  # Reduce workers
max_requests = 500  # Restart workers more frequently
```

### Nginx Configuration

Edit `/etc/nginx/sites-available/dataguardian`:

```nginx
# Increase upload size
client_max_body_size 1G;

# Enable gzip compression
gzip on;
gzip_types text/plain text/css application/json application/javascript;

# Cache static files
location /static/ {
    expires 90d;
    add_header Cache-Control "public, immutable";
}
```

### System Resources

```bash
# Increase file descriptors
sudo vim /etc/security/limits.conf
# Add:
dataguardian soft nofile 65536
dataguardian hard nofile 65536

# Increase shared memory (for Oracle client)
sudo vim /etc/sysctl.conf
# Add:
kernel.shmmax = 68719476736
kernel.shmall = 4294967296
```

---

## 🔐 Security Hardening

### Firewall Rules

```bash
# Allow only necessary ports
sudo ufw status
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Secure .env File

```bash
# Restrict permissions
chmod 600 /home/dataguardian/TwelvelabsWithOracleVector/.env
chown dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/.env
```

### Regular Updates

```bash
# Setup automatic security updates
sudo apt install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

### Fail2Ban (Optional)

```bash
# Install fail2ban
sudo apt install fail2ban

# Configure
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 📈 Monitoring & Alerts

### Setup Basic Monitoring

```bash
# Install monitoring tools
sudo apt install sysstat

# View system stats
sar -u 1 10  # CPU
sar -r 1 10  # Memory
sar -n DEV 1 10  # Network
```

### Health Check Endpoint

The application includes a health check:

```bash
curl http://localhost:8080/health
```

Monitor this with tools like:
- UptimeRobot
- Pingdom
- OCI Monitoring Service

---

## 💰 Cost Optimization

### Use OCI Always-Free Resources

- ✅ 2x AMD-based Compute VMs (1/8 OCPU, 1GB RAM) - **FREE FOREVER**
- ✅ 2x Autonomous Databases (1 OCPU, 20GB) - **FREE FOREVER**
- ✅ 10GB Object Storage - **FREE FOREVER**

For production:
- Use VM.Standard.E4.Flex (pay-as-you-go)
- Scale Autonomous Database OCPUs (1-128)
- Archive cold storage (95% cost reduction)

### Estimated Monthly Cost (Production)

| Resource | Configuration | Cost |
|----------|---------------|------|
| Compute VM | E4.Flex (2 OCPU, 16GB) | ~$61 |
| Autonomous DB | 1 OCPU, 20GB | FREE |
| Object Storage | 100GB + 1M API calls | ~$2 |
| Data Transfer | 1TB egress | ~$9 |
| **Total** | | **~$72/month** |

---

## 🎓 Next Steps

1. ✅ **Monitor Application**: Set up monitoring and alerts
2. ✅ **Setup Backups**: Configure automated backups
3. ✅ **Load Testing**: Test performance under load
4. ✅ **Setup CI/CD**: Automate deployments
5. ✅ **Enable CDN**: Use OCI CDN for static assets
6. ✅ **Multi-Region**: Deploy to multiple regions for HA

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/DeepakMishra1108/TwelvelabsWithOracleVector/issues)
- **Oracle Cloud**: [Support Portal](https://support.oracle.com/)
- **Documentation**: See [README.md](./README.md)

---

**Deployment Time**: ~30 minutes  
**Difficulty**: Intermediate  
**Prerequisites**: Basic Linux, OCI, and networking knowledge

🎉 **Your Data Guardian is now running on OCI!**
