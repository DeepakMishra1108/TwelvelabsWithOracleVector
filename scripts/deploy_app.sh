#!/bin/bash

###############################################################################
# Data Guardian - Application Deployment Script
# Run this as dataguardian user after system setup
###############################################################################

set -e  # Exit on error

echo "=========================================="
echo "Data Guardian - Application Deployment"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

# Check if running as dataguardian user
if [ "$USER" != "dataguardian" ]; then
    print_error "This script must be run as dataguardian user"
    echo "Run: sudo su - dataguardian"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$(dirname "$SCRIPT_DIR")"

cd "$APP_DIR"

# Step 1: Setup virtual environment
print_info "Setting up Python virtual environment..."
if [ ! -d "twelvelabvideoai" ]; then
    python3 -m venv twelvelabvideoai
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

source twelvelabvideoai/bin/activate
print_success "Virtual environment activated"

# Step 2: Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip
print_success "Pip upgraded"

# Step 3: Install dependencies
print_info "Installing Python dependencies..."
pip install -r requirements.txt
pip install gunicorn python-dotenv
print_success "Dependencies installed"

# Step 4: Create necessary directories
print_info "Creating directories..."
mkdir -p logs
mkdir -p static
mkdir -p temp
mkdir -p uploads
print_success "Directories created"

# Step 5: Check for .env file
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    echo ""
    echo "Create .env file with the following variables:"
    echo ""
    cat << 'EOF'
# Oracle Database
ORACLE_DB_USERNAME=ADMIN
ORACLE_DB_PASSWORD=your_password
ORACLE_DB_CONNECT_STRING=your_connection_string
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
FLASK_SECRET_KEY=your_secret_key_min_32_chars
FLASK_HOST=0.0.0.0
FLASK_PORT=8080

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
EOF
    echo ""
    exit 1
else
    print_success ".env file found"
fi

# Step 6: Check for database wallet
if [ ! -d "twelvelabvideoai/wallet" ] || [ -z "$(ls -A twelvelabvideoai/wallet)" ]; then
    print_error "Database wallet not found!"
    echo ""
    echo "Upload wallet files to: twelvelabvideoai/wallet/"
    echo "From your local machine:"
    echo "  scp -r /path/to/wallet/* ubuntu@YOUR_VM_IP:/tmp/"
    echo "  ssh ubuntu@YOUR_VM_IP"
    echo "  sudo mv /tmp/wallet_* /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet/"
    echo "  sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet"
    echo ""
    exit 1
else
    print_success "Database wallet found"
fi

# Step 7: Test application
print_info "Testing application..."
export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_9:$LD_LIBRARY_PATH
python -c "
import sys
sys.path.insert(0, 'src')
try:
    import oracledb
    print('✓ Oracle DB client imported successfully')
except Exception as e:
    print(f'✗ Error importing oracledb: {e}')
    sys.exit(1)

try:
    import flask
    print('✓ Flask imported successfully')
except Exception as e:
    print(f'✗ Error importing flask: {e}')
    sys.exit(1)

print('✓ All imports successful')
"

if [ $? -eq 0 ]; then
    print_success "Application test passed"
else
    print_error "Application test failed"
    exit 1
fi

# Step 8: Create Gunicorn config
print_info "Creating Gunicorn configuration..."
cat > gunicorn_config.py << 'EOF'
"""Gunicorn configuration for Data Guardian"""
import multiprocessing
import os

bind = "127.0.0.1:8080"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

timeout = 120
graceful_timeout = 30
keepalive = 5

accesslog = "/home/dataguardian/logs/gunicorn-access.log"
errorlog = "/home/dataguardian/logs/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

proc_name = "data-guardian"
daemon = False
pidfile = "/home/dataguardian/gunicorn.pid"
user = "dataguardian"
group = "www-data"
umask = 0o007
EOF
print_success "Gunicorn config created"

# Step 9: Create systemd service (requires sudo)
print_info "Creating systemd service..."
sudo tee /etc/systemd/system/dataguardian.service > /dev/null << EOF
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

ExecStart=/home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/bin/gunicorn \\
    --config /home/dataguardian/TwelvelabsWithOracleVector/gunicorn_config.py \\
    --chdir /home/dataguardian/TwelvelabsWithOracleVector/src \\
    localhost_only_flask:app

ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=30
PrivateTmp=true
Restart=always
RestartSec=10

NoNewPrivileges=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/dataguardian

[Install]
WantedBy=multi-user.target
EOF
print_success "Systemd service created"

# Step 10: Configure Nginx
print_info "Configuring Nginx..."
sudo tee /etc/nginx/sites-available/dataguardian > /dev/null << 'EOF'
upstream dataguardian_app {
    server 127.0.0.1:8080 fail_timeout=0;
}

server {
    listen 80;
    server_name _;

    client_max_body_size 500M;
    client_body_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    access_log /var/log/nginx/dataguardian-access.log;
    error_log /var/log/nginx/dataguardian-error.log;

    location /static/ {
        alias /home/dataguardian/TwelvelabsWithOracleVector/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://dataguardian_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_buffering off;
        proxy_cache off;
        
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /health {
        proxy_pass http://dataguardian_app;
        access_log off;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/dataguardian /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
print_success "Nginx configured"

# Step 11: Test Nginx config
print_info "Testing Nginx configuration..."
sudo nginx -t
print_success "Nginx config valid"

# Step 12: Setup log rotation
print_info "Setting up log rotation..."
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
print_success "Log rotation configured"

# Step 13: Enable and start services
print_info "Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable dataguardian
sudo systemctl start dataguardian
sudo systemctl reload nginx
print_success "Services started"

# Wait for service to be ready
print_info "Waiting for application to start..."
sleep 5

# Step 14: Check service status
print_info "Checking service status..."
if sudo systemctl is-active --quiet dataguardian; then
    print_success "Data Guardian service is running"
else
    print_error "Data Guardian service failed to start"
    echo "Check logs: sudo journalctl -u dataguardian -n 50"
    exit 1
fi

if sudo systemctl is-active --quiet nginx; then
    print_success "Nginx service is running"
else
    print_error "Nginx service failed"
    exit 1
fi

# Get VM IP
VM_IP=$(curl -s ifconfig.me)

# Summary
echo ""
echo "=========================================="
echo "✓ Deployment Complete!"
echo "=========================================="
echo ""
echo "Application Details:"
echo "  - Service: dataguardian"
echo "  - Gunicorn: http://127.0.0.1:8080"
echo "  - Nginx: http://0.0.0.0:80"
echo "  - Public Access: http://$VM_IP"
echo ""
echo "Useful Commands:"
echo "  - View logs: sudo journalctl -u dataguardian -f"
echo "  - Restart: sudo systemctl restart dataguardian"
echo "  - Status: sudo systemctl status dataguardian"
echo ""
echo "Next Steps:"
echo "  1. Visit: http://$VM_IP"
echo "  2. Setup SSL: sudo certbot --nginx -d your-domain.com"
echo "  3. Configure DNS to point to: $VM_IP"
echo ""
