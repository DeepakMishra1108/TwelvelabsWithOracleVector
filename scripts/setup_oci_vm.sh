#!/bin/bash

###############################################################################
# Data Guardian - OCI VM Setup Script
# Run this script on your OCI VM after initial SSH connection
###############################################################################

set -e  # Exit on error

echo "=========================================="
echo "Data Guardian - OCI VM Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

# Network connectivity check
check_network() {
    print_info "Verifying network connectivity..."
    
    # Critical services that must be reachable
    SERVICES=(
        "https://github.com|GitHub"
        "https://pypi.org|PyPI"
        "https://api.twelvelabs.io|TwelveLabs API"
        "https://archive.ubuntu.com|Ubuntu Repos"
    )
    
    local all_ok=true
    
    for service in "${SERVICES[@]}"; do
        IFS='|' read -r url name <<< "$service"
        printf "  Testing %-20s ... " "$name"
        
        HTTP_CODE=$(timeout 10 curl -s -o /dev/null -w "%{http_code}" "$url")
        # Accept 2xx, 3xx, and 404 (TwelveLabs API returns 404 for root endpoint)
        if echo "$HTTP_CODE" | grep -qE "^(2|3|404)"; then
            print_success "OK"
        else
            print_error "FAILED (HTTP $HTTP_CODE)"
            all_ok=false
        fi
    done
    
    if [ "$all_ok" = false ]; then
        echo ""
        print_error "Network connectivity check failed!"
        echo ""
        echo "This VM cannot reach required internet services."
        echo "Common causes:"
        echo "  1. Security List missing egress rules"
        echo "     → Add rule: Destination 0.0.0.0/0, Protocol: All"
        echo "  2. Route Table not configured"
        echo "     → Verify route: 0.0.0.0/0 → Internet Gateway"
        echo "  3. Internet Gateway not attached to VCN"
        echo "     → Check VCN → Internet Gateways"
        echo "  4. VM in private subnet without NAT Gateway"
        echo "     → Use public subnet or add NAT Gateway"
        echo ""
        echo "See OCI_NETWORK_SETUP.md for detailed troubleshooting."
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "Network connectivity verified ✓"
    fi
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root. Run as ubuntu/opc user."
   exit 1
fi

print_info "Starting system setup..."

# Run network check before any network-dependent operations
check_network

# Step 1: Update system
print_info "Updating system packages..."
sudo apt update && sudo apt upgrade -y
print_success "System updated"

# Step 2: Install essential tools
print_info "Installing essential tools..."
sudo apt install -y build-essential curl wget git vim unzip software-properties-common
print_success "Essential tools installed"

# Step 3: Install Python 3.11
print_info "Installing Python 3.11..."
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
print_success "Python 3.11 installed: $(python3 --version)"

# Step 4: Install FFmpeg
print_info "Installing FFmpeg..."
sudo apt install -y ffmpeg
print_success "FFmpeg installed: $(ffmpeg -version | head -n1)"

# Step 5: Install Nginx
print_info "Installing Nginx..."
sudo apt install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx
print_success "Nginx installed and started"

# Step 6: Install Oracle Instant Client
print_info "Installing Oracle Instant Client..."
cd /tmp
if [ ! -f "instantclient-basic-linux.x64-21.9.0.0.0dbru.zip" ]; then
    wget https://download.oracle.com/otn_software/linux/instantclient/219000/instantclient-basic-linux.x64-21.9.0.0.0dbru.zip
fi

sudo mkdir -p /opt/oracle
sudo unzip -o instantclient-basic-linux.x64-21.9.0.0.0dbru.zip -d /opt/oracle
sudo sh -c "echo /opt/oracle/instantclient_21_9 > /etc/ld.so.conf.d/oracle-instantclient.conf"
sudo ldconfig

# Add to bashrc
if ! grep -q "LD_LIBRARY_PATH.*instantclient" ~/.bashrc; then
    echo 'export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_9:$LD_LIBRARY_PATH' >> ~/.bashrc
fi
export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_9:$LD_LIBRARY_PATH

print_success "Oracle Instant Client installed"

# Step 7: Create dataguardian user
print_info "Creating dataguardian user..."
if ! id "dataguardian" &>/dev/null; then
    sudo useradd -m -s /bin/bash dataguardian
    sudo usermod -aG www-data dataguardian
    print_success "User 'dataguardian' created"
else
    print_info "User 'dataguardian' already exists"
fi

# Step 8: Configure firewall
print_info "Configuring firewall..."
sudo apt install -y ufw
sudo ufw --force enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
print_success "Firewall configured"

# Step 9: Install monitoring tools
print_info "Installing monitoring tools..."
sudo apt install -y htop iotop nethogs
print_success "Monitoring tools installed"

# Step 10: Install Certbot for SSL
print_info "Installing Certbot..."
sudo apt install -y certbot python3-certbot-nginx
print_success "Certbot installed"

# Summary
echo ""
echo "=========================================="
echo "✓ System Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Switch to dataguardian user: sudo su - dataguardian"
echo "2. Clone repository: git clone <repo-url>"
echo "3. Run: ./scripts/deploy_app.sh"
echo ""
echo "Installed:"
echo "  - Python $(python3 --version)"
echo "  - FFmpeg $(ffmpeg -version | head -n1 | cut -d' ' -f3)"
echo "  - Nginx $(nginx -v 2>&1 | cut -d'/' -f2)"
echo "  - Oracle Instant Client 21.9"
echo ""
