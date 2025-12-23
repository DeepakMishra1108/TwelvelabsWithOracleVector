#!/bin/bash

###############################################################################
# Quick Push and Deploy Script
# Syncs local changes → GitHub → VM Server
# Usage: ./deploy_to_vm.sh "Your commit message"
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# VM Configuration
VM_HOST="ubuntu@150.136.235.189"
VM_USER="dataguardian"
VM_PROJECT_PATH="/home/dataguardian/TwelvelabsWithOracleVector"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 Quick Push and Deploy to VM${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Check for changes
echo -e "${YELLOW}📋 Step 1: Checking for local changes...${NC}"
if ! git diff-index --quiet HEAD --; then
    echo -e "${GREEN}✓ Local changes detected${NC}"
    
    # Show what's changed
    echo ""
    echo "Modified files:"
    git status --short
    echo ""
    
    # Get commit message
    if [ -z "$1" ]; then
        echo -e "${RED}❌ Error: Commit message required${NC}"
        echo "Usage: ./deploy_to_vm.sh \"Your commit message\""
        exit 1
    fi
    
    COMMIT_MSG="$1"
    
    # Step 2: Commit changes
    echo -e "${YELLOW}💾 Step 2: Committing changes...${NC}"
    git add .
    git commit -m "$COMMIT_MSG"
    echo -e "${GREEN}✓ Changes committed${NC}"
    echo ""
else
    echo -e "${GREEN}✓ No uncommitted changes${NC}"
    echo ""
fi

# Step 3: Push to GitHub
echo -e "${YELLOW}⬆️  Step 3: Pushing to GitHub...${NC}"
CURRENT_BRANCH=$(git branch --show-current)
git push origin $CURRENT_BRANCH
echo -e "${GREEN}✓ Pushed to origin/$CURRENT_BRANCH${NC}"
echo ""

# Step 4: Deploy to VM
echo -e "${YELLOW}🖥️  Step 4: Deploying to VM...${NC}"
echo "Connecting to $VM_HOST..."
echo ""

ssh -t $VM_HOST << 'ENDSSH'
    # Switch to dataguardian user
    sudo su - dataguardian << 'ENDSU'
        cd /home/dataguardian/TwelvelabsWithOracleVector
        
        echo "📥 Pulling latest changes from GitHub..."
        ./scripts/vm_safe_deploy.sh
        
        echo ""
        echo "✅ Deployment completed!"
        echo ""
        echo "🔍 Checking service status..."
        sudo systemctl status dataguardian.service --no-pager -l | head -20
ENDSU
ENDSSH

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""
echo "🌐 Application URL: https://150.136.235.189:8443"
echo ""
echo "📊 To check logs:"
echo "   ssh $VM_HOST"
echo "   sudo journalctl -u dataguardian.service -f"
echo ""
