#!/bin/bash
#
# VM-Safe Deployment Script
# Preserves VM-specific changes while pulling latest code
#
# Usage: ./scripts/vm_safe_deploy.sh

set -e  # Exit on error

echo "🚀 Starting VM-Safe Deployment..."
echo "=================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo ""
echo "📍 Current directory: $(pwd)"
echo "📍 Current branch: $(git branch --show-current)"
echo ""

# Step 1: Backup current VM-specific files
echo -e "${YELLOW}📦 Step 1: Backing up VM-specific configurations...${NC}"
BACKUP_DIR="vm_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# List of VM-specific files that should NOT be in git
VM_SPECIFIC_FILES=(
    "ssl/certificate.crt"
    "ssl/private.key"
    "gunicorn_config.py"
    ".env"
)

for file in "${VM_SPECIFIC_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ Backing up: $file"
        mkdir -p "$BACKUP_DIR/$(dirname "$file")"
        cp "$file" "$BACKUP_DIR/$file"
    fi
done

echo -e "${GREEN}✅ Backup completed in: $BACKUP_DIR${NC}"
echo ""

# Step 2: Check for local changes
echo -e "${YELLOW}🔍 Step 2: Checking for local changes...${NC}"
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}⚠️  Local changes detected!${NC}"
    echo ""
    echo "Modified files:"
    git status --short
    echo ""
    
    # Create a patch of local changes
    PATCH_FILE="$BACKUP_DIR/local_changes.patch"
    git diff > "$PATCH_FILE"
    echo -e "${GREEN}✓ Local changes saved to: $PATCH_FILE${NC}"
    
    # Stash local changes
    echo ""
    echo -e "${YELLOW}📥 Stashing local changes...${NC}"
    git stash push -m "VM deployment backup $(date +%Y%m%d_%H%M%S)"
    echo -e "${GREEN}✅ Changes stashed${NC}"
else
    echo -e "${GREEN}✓ No local changes detected${NC}"
fi
echo ""

# Step 3: Pull latest code
echo -e "${YELLOW}⬇️  Step 3: Pulling latest code from repository...${NC}"
CURRENT_COMMIT=$(git rev-parse HEAD)
echo "Current commit: $CURRENT_COMMIT"

if git pull origin main; then
    NEW_COMMIT=$(git rev-parse HEAD)
    if [ "$CURRENT_COMMIT" != "$NEW_COMMIT" ]; then
        echo -e "${GREEN}✅ Code updated successfully${NC}"
        echo "New commit: $NEW_COMMIT"
        echo ""
        echo "📝 Changes pulled:"
        git log --oneline "$CURRENT_COMMIT..$NEW_COMMIT"
    else
        echo -e "${GREEN}✓ Already up to date${NC}"
    fi
else
    echo -e "${RED}❌ Git pull failed!${NC}"
    echo "Restoring from stash..."
    git stash pop
    exit 1
fi
echo ""

# Step 4: Restore VM-specific files
echo -e "${YELLOW}📂 Step 4: Restoring VM-specific configurations...${NC}"
for file in "${VM_SPECIFIC_FILES[@]}"; do
    if [ -f "$BACKUP_DIR/$file" ]; then
        echo "  ✓ Restoring: $file"
        mkdir -p "$(dirname "$file")"
        cp "$BACKUP_DIR/$file" "$file"
    fi
done
echo -e "${GREEN}✅ VM-specific files restored${NC}"
echo ""

# Step 5: Check if stash needs to be reapplied
echo -e "${YELLOW}🔄 Step 5: Checking for stashed changes...${NC}"
if git stash list | grep -q "VM deployment backup"; then
    echo -e "${YELLOW}📥 Reapplying stashed changes...${NC}"
    
    # Try to apply stash
    if git stash pop; then
        echo -e "${GREEN}✅ Stashed changes applied successfully${NC}"
    else
        echo -e "${RED}⚠️  Merge conflicts detected!${NC}"
        echo ""
        echo "Conflicting files:"
        git diff --name-only --diff-filter=U
        echo ""
        echo -e "${YELLOW}Please resolve conflicts manually:${NC}"
        echo "1. Edit the conflicted files"
        echo "2. Run: git add <resolved-files>"
        echo "3. Run: git stash drop"
        echo ""
        echo "Original changes are in: $PATCH_FILE"
        exit 1
    fi
else
    echo -e "${GREEN}✓ No stashed changes to apply${NC}"
fi
echo ""

# Step 6: Validate critical files
echo -e "${YELLOW}🔍 Step 6: Validating deployment...${NC}"

CRITICAL_FILES=(
    "src/localhost_only_flask.py"
    "src/search_unified_flask_safe.py"
    "twelvelabvideoai/src/oci_storage.py"
    "twelvelabvideoai/src/rate_limiter.py"
    "twelvelabvideoai/src/auth_rbac.py"
)

MISSING_FILES=()
for file in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
        echo -e "${RED}  ✗ Missing: $file${NC}"
    else
        echo -e "${GREEN}  ✓ Found: $file${NC}"
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "${RED}❌ Deployment validation failed!${NC}"
    echo "Missing critical files. Please check repository."
    exit 1
fi

echo -e "${GREEN}✅ All critical files present${NC}"
echo ""

# Step 7: SSL Certificate Check
echo -e "${YELLOW}🔒 Step 7: Checking SSL certificates...${NC}"
if [ -f "ssl/certificate.crt" ] && [ -f "ssl/private.key" ]; then
    # Validate that cert and key match
    CERT_MODULUS=$(openssl x509 -noout -modulus -in ssl/certificate.crt 2>/dev/null | openssl md5)
    KEY_MODULUS=$(openssl rsa -noout -modulus -in ssl/private.key 2>/dev/null | openssl md5)
    
    if [ "$CERT_MODULUS" = "$KEY_MODULUS" ]; then
        echo -e "${GREEN}✓ SSL certificate and key match${NC}"
    else
        echo -e "${RED}⚠️  SSL certificate and key DO NOT match!${NC}"
        echo "Regenerating SSL certificates..."
        ./scripts/generate_ssl_certificate.sh
    fi
else
    echo -e "${YELLOW}⚠️  SSL certificates missing${NC}"
    echo "Generating new SSL certificates..."
    if [ -f "./scripts/generate_ssl_certificate.sh" ]; then
        ./scripts/generate_ssl_certificate.sh
    else
        echo "Generating with openssl directly..."
        mkdir -p ssl
        openssl req -x509 -newkey rsa:4096 -nodes \
            -keyout ssl/private.key \
            -out ssl/certificate.crt \
            -days 365 \
            -subj "/C=US/ST=California/L=San Francisco/O=Data Guardian/OU=IT/CN=localhost"
    fi
fi
echo ""

# Step 8: Restart services
echo -e "${YELLOW}🔄 Step 8: Restarting services...${NC}"

# Test Nginx config
if command -v nginx &> /dev/null; then
    echo "Testing Nginx configuration..."
    if sudo nginx -t 2>&1 | grep -q "successful"; then
        echo -e "${GREEN}✓ Nginx configuration valid${NC}"
        echo "Reloading Nginx..."
        sudo systemctl reload nginx
    else
        echo -e "${RED}✗ Nginx configuration invalid${NC}"
        sudo nginx -t
        exit 1
    fi
fi

# Restart application
if systemctl is-active --quiet dataguardian; then
    echo "Restarting Data Guardian service..."
    sudo systemctl restart dataguardian
    sleep 3
    
    if systemctl is-active --quiet dataguardian; then
        echo -e "${GREEN}✓ Data Guardian service restarted${NC}"
    else
        echo -e "${RED}✗ Data Guardian service failed to start${NC}"
        echo "Check logs: sudo journalctl -u dataguardian -n 50"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Data Guardian service not running${NC}"
    echo "Start it with: sudo systemctl start dataguardian"
fi
echo ""

# Step 9: Health check
echo -e "${YELLOW}🏥 Step 9: Running health check...${NC}"
sleep 2

# Check if application responds
if curl -k -s -o /dev/null -w "%{http_code}" https://localhost | grep -q "^[23]"; then
    echo -e "${GREEN}✓ Application is responding${NC}"
else
    echo -e "${YELLOW}⚠️  Application may not be fully started yet${NC}"
    echo "Check logs: sudo journalctl -u dataguardian -f"
fi
echo ""

# Final summary
echo "=================================="
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo "=================================="
echo ""
echo "📊 Summary:"
echo "  • Backup location: $BACKUP_DIR"
echo "  • Git commit: $(git rev-parse --short HEAD)"
echo "  • Branch: $(git branch --show-current)"
echo ""
echo "📝 Next steps:"
echo "  1. Test the application: https://your-server-ip"
echo "  2. Monitor logs: sudo journalctl -u dataguardian -f"
echo "  3. Check backup if needed: $BACKUP_DIR"
echo ""
echo "💡 Tip: Keep backups for 7 days, then remove old ones"
echo ""
