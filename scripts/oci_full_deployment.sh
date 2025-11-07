#!/bin/bash

###############################################################################
# Data Guardian - Complete OCI Deployment Automation
# 
# This script will:
# 1. Install OCI CLI (if needed)
# 2. Create OCI Compute VM
# 3. Configure networking (Security Lists, Internet Gateway)
# 4. SSH to VM and run setup scripts
# 5. Deploy the application
#
# Prerequisites:
# - OCI config at: twelvelabvideoai/.oci/config
# - SSH key pair for VM access
# - Database wallet files
# - .env file with credentials
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${YELLOW}➜ $1${NC}"; }
print_section() { echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n${BLUE}$1${NC}\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"; }

# Configuration
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OCI_CONFIG="${PROJECT_ROOT}/twelvelabvideoai/.oci/config"
COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaaipofyxb7s2xmwe3j3skrccrj6yek6lgtlkekguzqlr2mlgyt54iq"
REGION="us-ashburn-1"

# VM Configuration
VM_NAME="dataguardian-app-server"
VM_SHAPE="VM.Standard.E4.Flex"
VM_OCPUS=2
VM_MEMORY_GB=16
VM_IMAGE_ID=""  # Will be fetched dynamically
AVAILABILITY_DOMAIN=""  # Will be fetched dynamically

# VCN Configuration
VCN_CIDR="10.0.0.0/16"
SUBNET_CIDR="10.0.1.0/24"
VCN_NAME="dataguardian-vcn"
SUBNET_NAME="dataguardian-public-subnet"

# SSH Configuration
SSH_PUBLIC_KEY_PATH="$HOME/.ssh/id_rsa.pub"
SSH_PRIVATE_KEY_PATH="$HOME/.ssh/id_rsa"

print_section "Data Guardian - OCI Full Deployment"

echo "Configuration:"
echo "  Region: $REGION"
echo "  VM Name: $VM_NAME"
echo "  VM Shape: $VM_SHAPE ($VM_OCPUS OCPUs, ${VM_MEMORY_GB}GB RAM)"
echo "  OCI Config: $OCI_CONFIG"
echo ""

# Check prerequisites
print_info "Checking prerequisites..."

if [ ! -f "$OCI_CONFIG" ]; then
    print_error "OCI config not found at: $OCI_CONFIG"
    exit 1
fi
print_success "OCI config found"

if [ ! -f "$SSH_PUBLIC_KEY_PATH" ]; then
    print_error "SSH public key not found at: $SSH_PUBLIC_KEY_PATH"
    echo "Generate SSH key with: ssh-keygen -t rsa -b 4096 -f $HOME/.ssh/id_rsa"
    exit 1
fi
print_success "SSH key found"

# Check if OCI CLI is installed
print_info "Checking OCI CLI installation..."
if ! command -v oci &> /dev/null; then
    print_info "OCI CLI not found. Installing..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if ! command -v brew &> /dev/null; then
            print_error "Homebrew not found. Please install from: https://brew.sh"
            exit 1
        fi
        
        print_info "Installing OCI CLI via Homebrew..."
        brew update
        brew install oci-cli
    else
        # Linux
        print_info "Installing OCI CLI..."
        bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" -- --accept-all-defaults
    fi
    
    print_success "OCI CLI installed"
else
    print_success "OCI CLI already installed: $(oci --version)"
fi

# Configure OCI CLI to use our config
export OCI_CLI_CONFIG_FILE="$OCI_CONFIG"
print_success "Using OCI config: $OCI_CONFIG"

print_section "Step 1: Fetch OCI Resources"

# Get availability domain
print_info "Fetching availability domain..."
AVAILABILITY_DOMAIN=$(oci iam availability-domain list \
    --compartment-id "$COMPARTMENT_ID" \
    --region "$REGION" \
    --query 'data[0].name' \
    --raw-output 2>/dev/null)

if [ -z "$AVAILABILITY_DOMAIN" ]; then
    print_error "Failed to fetch availability domain"
    exit 1
fi
print_success "Availability Domain: $AVAILABILITY_DOMAIN"

# Get Ubuntu 22.04 image
print_info "Fetching Ubuntu 22.04 image..."
VM_IMAGE_ID=$(oci compute image list \
    --compartment-id "$COMPARTMENT_ID" \
    --region "$REGION" \
    --operating-system "Canonical Ubuntu" \
    --operating-system-version "22.04" \
    --shape "$VM_SHAPE" \
    --sort-by TIMECREATED \
    --sort-order DESC \
    --limit 1 \
    --query 'data[0]."id"' \
    --raw-output 2>/dev/null)

if [ -z "$VM_IMAGE_ID" ]; then
    print_error "Failed to fetch Ubuntu 22.04 image"
    exit 1
fi
print_success "Image ID: $VM_IMAGE_ID"

print_section "Step 2: Create VCN and Networking"

# Check if VCN already exists
print_info "Checking for existing VCN..."
EXISTING_VCN=$(oci network vcn list \
    --compartment-id "$COMPARTMENT_ID" \
    --region "$REGION" \
    --display-name "$VCN_NAME" \
    --query 'data[0].id' \
    --raw-output 2>/dev/null || echo "")

if [ -n "$EXISTING_VCN" ]; then
    print_info "VCN already exists: $EXISTING_VCN"
    VCN_ID="$EXISTING_VCN"
else
    print_info "Creating VCN..."
    VCN_ID=$(oci network vcn create \
        --compartment-id "$COMPARTMENT_ID" \
        --region "$REGION" \
        --display-name "$VCN_NAME" \
        --cidr-block "$VCN_CIDR" \
        --dns-label "dataguardian" \
        --wait-for-state AVAILABLE \
        --query 'data.id' \
        --raw-output)
    
    print_success "VCN created: $VCN_ID"
fi

# Create Internet Gateway
print_info "Checking for Internet Gateway..."
IGW_ID=$(oci network internet-gateway list \
    --compartment-id "$COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --region "$REGION" \
    --query 'data[0].id' \
    --raw-output 2>/dev/null || echo "")

if [ -z "$IGW_ID" ]; then
    print_info "Creating Internet Gateway..."
    IGW_ID=$(oci network internet-gateway create \
        --compartment-id "$COMPARTMENT_ID" \
        --vcn-id "$VCN_ID" \
        --region "$REGION" \
        --display-name "${VCN_NAME}-igw" \
        --is-enabled true \
        --wait-for-state AVAILABLE \
        --query 'data.id' \
        --raw-output)
    
    print_success "Internet Gateway created: $IGW_ID"
else
    print_info "Internet Gateway exists: $IGW_ID"
fi

# Create Route Table
print_info "Checking for Route Table..."
RT_ID=$(oci network route-table list \
    --compartment-id "$COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --region "$REGION" \
    --query 'data[0].id' \
    --raw-output 2>/dev/null || echo "")

if [ -z "$RT_ID" ]; then
    print_info "Creating Route Table..."
    RT_ID=$(oci network route-table create \
        --compartment-id "$COMPARTMENT_ID" \
        --vcn-id "$VCN_ID" \
        --region "$REGION" \
        --display-name "${VCN_NAME}-rt" \
        --route-rules '[{"destination":"0.0.0.0/0","destinationType":"CIDR_BLOCK","networkEntityId":"'$IGW_ID'"}]' \
        --wait-for-state AVAILABLE \
        --query 'data.id' \
        --raw-output)
    
    print_success "Route Table created with Internet Gateway route"
else
    print_info "Route Table exists: $RT_ID"
    
    # Update route table to ensure IGW route exists
    print_info "Updating Route Table with Internet Gateway route..."
    oci network route-table update \
        --rt-id "$RT_ID" \
        --region "$REGION" \
        --route-rules '[{"destination":"0.0.0.0/0","destinationType":"CIDR_BLOCK","networkEntityId":"'$IGW_ID'"}]' \
        --force \
        --wait-for-state AVAILABLE > /dev/null
    
    print_success "Route Table updated"
fi

# Create Security List
print_info "Checking for Security List..."
SL_ID=$(oci network security-list list \
    --compartment-id "$COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --region "$REGION" \
    --query 'data[0].id' \
    --raw-output 2>/dev/null || echo "")

if [ -z "$SL_ID" ]; then
    print_info "Creating Security List..."
    
    # Create security list with ingress and egress rules
    SL_ID=$(oci network security-list create \
        --compartment-id "$COMPARTMENT_ID" \
        --vcn-id "$VCN_ID" \
        --region "$REGION" \
        --display-name "${VCN_NAME}-seclist" \
        --egress-security-rules '[{"destination":"0.0.0.0/0","protocol":"all","isStateless":false}]' \
        --ingress-security-rules '[
            {"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":22,"max":22}},"isStateless":false},
            {"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":80,"max":80}},"isStateless":false},
            {"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":443,"max":443}},"isStateless":false}
        ]' \
        --wait-for-state AVAILABLE \
        --query 'data.id' \
        --raw-output)
    
    print_success "Security List created with ingress (22,80,443) and egress (all) rules"
else
    print_info "Security List exists: $SL_ID"
    
    # Update security list to ensure rules exist
    print_info "Updating Security List rules..."
    oci network security-list update \
        --security-list-id "$SL_ID" \
        --region "$REGION" \
        --egress-security-rules '[{"destination":"0.0.0.0/0","protocol":"all","isStateless":false}]' \
        --ingress-security-rules '[
            {"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":22,"max":22}},"isStateless":false},
            {"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":80,"max":80}},"isStateless":false},
            {"source":"0.0.0.0/0","protocol":"6","tcpOptions":{"destinationPortRange":{"min":443,"max":443}},"isStateless":false}
        ]' \
        --force \
        --wait-for-state AVAILABLE > /dev/null
    
    print_success "Security List updated"
fi

# Create Public Subnet
print_info "Checking for Public Subnet..."
SUBNET_ID=$(oci network subnet list \
    --compartment-id "$COMPARTMENT_ID" \
    --vcn-id "$VCN_ID" \
    --region "$REGION" \
    --display-name "$SUBNET_NAME" \
    --query 'data[0].id' \
    --raw-output 2>/dev/null || echo "")

if [ -z "$SUBNET_ID" ]; then
    print_info "Creating Public Subnet..."
    SUBNET_ID=$(oci network subnet create \
        --compartment-id "$COMPARTMENT_ID" \
        --vcn-id "$VCN_ID" \
        --region "$REGION" \
        --availability-domain "$AVAILABILITY_DOMAIN" \
        --display-name "$SUBNET_NAME" \
        --cidr-block "$SUBNET_CIDR" \
        --dns-label "dataguardpub" \
        --route-table-id "$RT_ID" \
        --security-list-ids "[\"$SL_ID\"]" \
        --prohibit-public-ip-on-vnic false \
        --wait-for-state AVAILABLE \
        --query 'data.id' \
        --raw-output)
    
    print_success "Public Subnet created: $SUBNET_ID"
else
    print_info "Public Subnet exists: $SUBNET_ID"
fi

print_section "Step 3: Create Compute Instance"

# Check if VM already exists
print_info "Checking for existing compute instance..."
EXISTING_VM=$(oci compute instance list \
    --compartment-id "$COMPARTMENT_ID" \
    --region "$REGION" \
    --display-name "$VM_NAME" \
    --query 'data[0].id' \
    --raw-output 2>/dev/null || echo "")

if [ -n "$EXISTING_VM" ]; then
    print_info "Compute instance already exists: $EXISTING_VM"
    INSTANCE_ID="$EXISTING_VM"
    
    # Get instance state
    INSTANCE_STATE=$(oci compute instance get \
        --instance-id "$INSTANCE_ID" \
        --region "$REGION" \
        --query 'data."lifecycle-state"' \
        --raw-output)
    
    print_info "Instance state: $INSTANCE_STATE"
    
    if [ "$INSTANCE_STATE" != "RUNNING" ]; then
        print_info "Starting instance..."
        oci compute instance action \
            --instance-id "$INSTANCE_ID" \
            --region "$REGION" \
            --action START \
            --wait-for-state RUNNING > /dev/null
        print_success "Instance started"
    fi
else
    print_info "Creating compute instance (this may take 2-3 minutes)..."
    
    # Read SSH public key
    SSH_KEY_CONTENT=$(cat "$SSH_PUBLIC_KEY_PATH")
    
    # Create instance
    INSTANCE_ID=$(oci compute instance launch \
        --compartment-id "$COMPARTMENT_ID" \
        --region "$REGION" \
        --availability-domain "$AVAILABILITY_DOMAIN" \
        --display-name "$VM_NAME" \
        --image-id "$VM_IMAGE_ID" \
        --shape "$VM_SHAPE" \
        --shape-config "{\"ocpus\":$VM_OCPUS,\"memoryInGBs\":$VM_MEMORY_GB}" \
        --subnet-id "$SUBNET_ID" \
        --assign-public-ip true \
        --ssh-authorized-keys-file "$SSH_PUBLIC_KEY_PATH" \
        --wait-for-state RUNNING \
        --query 'data.id' \
        --raw-output)
    
    print_success "Compute instance created: $INSTANCE_ID"
fi

# Get public IP
print_info "Fetching public IP address..."
sleep 5  # Wait for VNIC to be ready
VNIC_ID=$(oci compute instance list-vnics \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'data[0]."id"' \
    --raw-output)

PUBLIC_IP=$(oci network vnic get \
    --vnic-id "$VNIC_ID" \
    --region "$REGION" \
    --query 'data."public-ip"' \
    --raw-output)

if [ -z "$PUBLIC_IP" ] || [ "$PUBLIC_IP" == "null" ]; then
    print_error "Failed to get public IP address"
    exit 1
fi

print_success "Public IP: $PUBLIC_IP"

print_section "Step 4: Wait for VM to be Ready"

print_info "Waiting for SSH to become available (this may take 1-2 minutes)..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$SSH_PRIVATE_KEY_PATH" ubuntu@$PUBLIC_IP "echo 'SSH ready'" &>/dev/null; then
        print_success "SSH connection established"
        break
    fi
    
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 10
done

echo ""

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    print_error "SSH connection timeout. Please check:"
    echo "  1. Security List allows port 22 from your IP"
    echo "  2. VM is in RUNNING state"
    echo "  3. Public IP is assigned: $PUBLIC_IP"
    exit 1
fi

print_section "Step 5: Upload Configuration Files"

print_info "Creating remote directory structure..."
ssh -i "$SSH_PRIVATE_KEY_PATH" ubuntu@$PUBLIC_IP "mkdir -p ~/TwelvelabsWithOracleVector/twelvelabvideoai/wallet"

print_info "Uploading wallet files..."
if [ -d "${PROJECT_ROOT}/twelvelabvideoai/wallet" ]; then
    scp -r -i "$SSH_PRIVATE_KEY_PATH" ${PROJECT_ROOT}/twelvelabvideoai/wallet/* ubuntu@$PUBLIC_IP:~/TwelvelabsWithOracleVector/twelvelabvideoai/wallet/
    print_success "Wallet files uploaded"
else
    print_error "Wallet directory not found: ${PROJECT_ROOT}/twelvelabvideoai/wallet"
    echo "Please ensure wallet files are in place before deployment"
    exit 1
fi

print_info "Uploading .env file..."
if [ -f "${PROJECT_ROOT}/twelvelabvideoai/.env" ]; then
    scp -i "$SSH_PRIVATE_KEY_PATH" ${PROJECT_ROOT}/twelvelabvideoai/.env ubuntu@$PUBLIC_IP:~/TwelvelabsWithOracleVector/twelvelabvideoai/.env
    print_success ".env file uploaded"
else
    print_error ".env file not found: ${PROJECT_ROOT}/twelvelabvideoai/.env"
    echo "Please create .env file before deployment"
    exit 1
fi

print_section "Step 6: Run System Setup on VM"

print_info "Cloning repository on VM..."
ssh -i "$SSH_PRIVATE_KEY_PATH" ubuntu@$PUBLIC_IP << 'EOF'
if [ ! -d ~/TwelvelabsWithOracleVector/.git ]; then
    cd ~
    git clone https://github.com/DeepakMishra1108/TwelvelabsWithOracleVector.git
    cd TwelvelabsWithOracleVector
    chmod +x scripts/*.sh
fi
EOF

print_success "Repository cloned"

print_info "Running system setup script (this will take 5-10 minutes)..."
ssh -i "$SSH_PRIVATE_KEY_PATH" ubuntu@$PUBLIC_IP << 'EOF'
cd ~/TwelvelabsWithOracleVector
./scripts/setup_oci_vm.sh
EOF

print_success "System setup completed"

print_section "Step 7: Deploy Application"

print_info "Running application deployment..."
ssh -i "$SSH_PRIVATE_KEY_PATH" ubuntu@$PUBLIC_IP << 'EOF'
# Copy wallet and .env from uploaded location to deployment location
sudo mkdir -p /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet
sudo cp -r ~/TwelvelabsWithOracleVector/twelvelabvideoai/wallet/* /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/wallet/
sudo cp ~/TwelvelabsWithOracleVector/twelvelabvideoai/.env /home/dataguardian/TwelvelabsWithOracleVector/twelvelabvideoai/.env
sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector

# Switch to dataguardian user and deploy
sudo -u dataguardian bash << 'DEPLOY'
cd /home/dataguardian/TwelvelabsWithOracleVector
./scripts/deploy_app.sh
DEPLOY
EOF

print_success "Application deployed"

print_section "Deployment Complete! 🎉"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Data Guardian Application Successfully Deployed"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  🌐 Application URL: http://$PUBLIC_IP"
echo "  🔒 HTTPS URL: https://$PUBLIC_IP (after SSL setup)"
echo "  📊 Server IP: $PUBLIC_IP"
echo "  🖥️  VM Name: $VM_NAME"
echo "  📍 Region: $REGION"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Next Steps:"
echo ""
echo "1. Test Application:"
echo "   curl http://$PUBLIC_IP"
echo "   open http://$PUBLIC_IP"
echo ""
echo "2. Setup SSL Certificate (optional but recommended):"
echo "   ssh -i $SSH_PRIVATE_KEY_PATH ubuntu@$PUBLIC_IP"
echo "   sudo /home/dataguardian/TwelvelabsWithOracleVector/scripts/manage.sh ssl-setup your-domain.com"
echo ""
echo "3. Monitor Application:"
echo "   ssh -i $SSH_PRIVATE_KEY_PATH ubuntu@$PUBLIC_IP"
echo "   sudo /home/dataguardian/TwelvelabsWithOracleVector/scripts/manage.sh status"
echo "   sudo /home/dataguardian/TwelvelabsWithOracleContract/scripts/manage.sh logs"
echo ""
echo "4. View Application Logs:"
echo "   ssh -i $SSH_PRIVATE_KEY_PATH ubuntu@$PUBLIC_IP"
echo "   sudo journalctl -u dataguardian -f"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""
print_success "Deployment automation complete!"
echo ""
