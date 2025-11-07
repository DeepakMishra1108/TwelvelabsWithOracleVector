#!/bin/bash

###############################################################################
# Pre-Deployment Checklist and Validation
# Run this before oci_full_deployment.sh
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }
print_info() { echo -e "${YELLOW}➜ $1${NC}"; }
print_section() { echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n${BLUE}$1${NC}\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"; }

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALL_CHECKS_PASSED=true

print_section "Data Guardian - Pre-Deployment Checklist"

echo "This script will verify all prerequisites before deployment."
echo ""

# Check 1: OCI Configuration
print_info "Checking OCI configuration..."
OCI_CONFIG="${PROJECT_ROOT}/twelvelabvideoai/.oci/config"

if [ -f "$OCI_CONFIG" ]; then
    print_success "OCI config found: $OCI_CONFIG"
    
    # Validate OCI config has required fields
    if grep -q "user=" "$OCI_CONFIG" && grep -q "key_file=" "$OCI_CONFIG"; then
        print_success "OCI config appears valid"
        
        # Check if private key exists
        KEY_FILE=$(grep "key_file=" "$OCI_CONFIG" | cut -d'=' -f2)
        if [ -f "$KEY_FILE" ]; then
            print_success "OCI private key found: $KEY_FILE"
        else
            print_error "OCI private key not found: $KEY_FILE"
            ALL_CHECKS_PASSED=false
        fi
    else
        print_error "OCI config missing required fields"
        ALL_CHECKS_PASSED=false
    fi
else
    print_error "OCI config not found: $OCI_CONFIG"
    ALL_CHECKS_PASSED=false
fi

# Check 2: SSH Keys
print_info "Checking SSH keys for VM access..."
SSH_PUBLIC_KEY="$HOME/.ssh/id_rsa.pub"
SSH_PRIVATE_KEY="$HOME/.ssh/id_rsa"

if [ -f "$SSH_PUBLIC_KEY" ] && [ -f "$SSH_PRIVATE_KEY" ]; then
    print_success "SSH key pair found"
else
    print_error "SSH key pair not found"
    echo "  Generate with: ssh-keygen -t rsa -b 4096 -f $HOME/.ssh/id_rsa"
    ALL_CHECKS_PASSED=false
fi

# Check 3: Database Wallet
print_info "Checking Oracle Database wallet..."
WALLET_DIR="${PROJECT_ROOT}/twelvelabvideoai/wallet"

if [ -d "$WALLET_DIR" ]; then
    # Check for essential wallet files
    REQUIRED_FILES=("cwallet.sso" "tnsnames.ora" "sqlnet.ora")
    WALLET_OK=true
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$WALLET_DIR/$file" ]; then
            print_error "Missing wallet file: $file"
            WALLET_OK=false
            ALL_CHECKS_PASSED=false
        fi
    done
    
    if [ "$WALLET_OK" = true ]; then
        print_success "Database wallet files found"
    fi
else
    print_error "Wallet directory not found: $WALLET_DIR"
    echo "  Download wallet from OCI Console → Autonomous Database → DB Connection → Download Wallet"
    ALL_CHECKS_PASSED=false
fi

# Check 4: Environment Configuration
print_info "Checking .env configuration..."
ENV_FILE="${PROJECT_ROOT}/twelvelabvideoai/.env"

if [ -f "$ENV_FILE" ]; then
    print_success ".env file found"
    
    # Check for required environment variables
    REQUIRED_VARS=("ORACLE_DB_USERNAME" "ORACLE_DB_PASSWORD" "ORACLE_DB_CONNECT_STRING" "TWELVE_LABS_API_KEY" "OCI_COMPARTMENT_ID" "DEFAULT_OCI_BUCKET")
    ENV_OK=true
    
    for var in "${REQUIRED_VARS[@]}"; do
        if grep -q "^${var}=" "$ENV_FILE"; then
            # Check if value is filled in (not template placeholder)
            VALUE=$(grep "^${var}=" "$ENV_FILE" | cut -d'=' -f2)
            if [[ "$VALUE" =~ YOUR_.*_HERE ]] || [ -z "$VALUE" ]; then
                print_error "$var is not configured (contains placeholder or empty)"
                ENV_OK=false
                ALL_CHECKS_PASSED=false
            else
                print_success "$var is configured"
            fi
        else
            print_error "$var is missing from .env file"
            ENV_OK=false
            ALL_CHECKS_PASSED=false
        fi
    done
else
    print_error ".env file not found: $ENV_FILE"
    echo ""
    echo "  Create .env file:"
    echo "  1. Copy template: cp ${PROJECT_ROOT}/twelvelabvideoai/.env.template ${PROJECT_ROOT}/twelvelabvideoai/.env"
    echo "  2. Edit: nano ${PROJECT_ROOT}/twelvelabvideoai/.env"
    echo "  3. Fill in all YOUR_*_HERE placeholders with actual values"
    echo ""
    ALL_CHECKS_PASSED=false
fi

# Check 5: Git Repository
print_info "Checking git repository status..."
cd "$PROJECT_ROOT"

if git rev-parse --git-dir > /dev/null 2>&1; then
    print_success "Git repository detected"
    
    # Check for uncommitted changes
    if git diff-index --quiet HEAD --; then
        print_success "No uncommitted changes"
    else
        print_info "⚠ You have uncommitted changes. Consider committing before deployment."
    fi
else
    print_error "Not a git repository"
    ALL_CHECKS_PASSED=false
fi

# Check 6: Required Scripts
print_info "Checking deployment scripts..."
REQUIRED_SCRIPTS=(
    "scripts/oci_full_deployment.sh"
    "scripts/setup_oci_vm.sh"
    "scripts/deploy_app.sh"
    "scripts/manage.sh"
)

SCRIPTS_OK=true
for script in "${REQUIRED_SCRIPTS[@]}"; do
    SCRIPT_PATH="${PROJECT_ROOT}/${script}"
    if [ -f "$SCRIPT_PATH" ]; then
        if [ -x "$SCRIPT_PATH" ]; then
            print_success "$(basename $script) is executable"
        else
            print_error "$(basename $script) is not executable"
            echo "  Fix with: chmod +x $SCRIPT_PATH"
            SCRIPTS_OK=false
            ALL_CHECKS_PASSED=false
        fi
    else
        print_error "$(basename $script) not found"
        SCRIPTS_OK=false
        ALL_CHECKS_PASSED=false
    fi
done

print_section "Checklist Summary"

if [ "$ALL_CHECKS_PASSED" = true ]; then
    echo ""
    print_success "✓ All checks passed! You're ready to deploy."
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Next Step: Run Full Deployment"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Run the following command to deploy:"
    echo ""
    echo "  cd $PROJECT_ROOT"
    echo "  ./scripts/oci_full_deployment.sh"
    echo ""
    echo "This will:"
    echo "  1. Install OCI CLI (if needed)"
    echo "  2. Create VCN and networking components"
    echo "  3. Create OCI Compute VM"
    echo "  4. Configure security rules"
    echo "  5. Deploy Data Guardian application"
    echo ""
    echo "Estimated time: 10-15 minutes"
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    exit 0
else
    echo ""
    print_error "✗ Some checks failed. Please fix the issues above before deployment."
    echo ""
    echo "Common fixes:"
    echo ""
    echo "1. Create .env file:"
    echo "   cp ${PROJECT_ROOT}/twelvelabvideoai/.env.template ${PROJECT_ROOT}/twelvelabvideoai/.env"
    echo "   nano ${PROJECT_ROOT}/twelvelabvideoai/.env"
    echo ""
    echo "2. Generate SSH keys:"
    echo "   ssh-keygen -t rsa -b 4096 -f $HOME/.ssh/id_rsa"
    echo ""
    echo "3. Download Database Wallet:"
    echo "   - OCI Console → Autonomous Database → Your DB"
    echo "   - DB Connection → Download Wallet"
    echo "   - Extract to: ${PROJECT_ROOT}/twelvelabvideoai/wallet/"
    echo ""
    echo "4. Make scripts executable:"
    echo "   chmod +x ${PROJECT_ROOT}/scripts/*.sh"
    echo ""
    exit 1
fi
