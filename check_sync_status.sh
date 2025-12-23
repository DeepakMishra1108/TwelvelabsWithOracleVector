#!/bin/bash

###############################################################################
# Quick Status Check Script
# Checks sync status between Local, GitHub, and VM
###############################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VM_HOST="ubuntu@150.136.235.189"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}📊 Code Sync Status Check${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Local Status
echo -e "${YELLOW}💻 LOCAL (Mac):${NC}"
echo "   Branch: $(git branch --show-current)"
echo "   Latest commit: $(git log -1 --oneline)"

# Check if ahead/behind
git fetch origin --quiet
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_COMMIT=$(git rev-parse origin/$(git branch --show-current))

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    echo -e "   Status: ${GREEN}✓ In sync with GitHub${NC}"
else
    AHEAD=$(git rev-list origin/$(git branch --show-current)..HEAD --count)
    BEHIND=$(git rev-list HEAD..origin/$(git branch --show-current) --count)
    
    if [ "$AHEAD" -gt 0 ]; then
        echo -e "   Status: ${YELLOW}↑ $AHEAD commits ahead of GitHub${NC}"
    fi
    if [ "$BEHIND" -gt 0 ]; then
        echo -e "   Status: ${YELLOW}↓ $BEHIND commits behind GitHub${NC}"
    fi
fi

# Uncommitted changes
if ! git diff-index --quiet HEAD --; then
    CHANGED_FILES=$(git status --short | wc -l | tr -d ' ')
    echo -e "   ${YELLOW}⚠️  $CHANGED_FILES uncommitted file(s)${NC}"
else
    echo -e "   ${GREEN}✓ No uncommitted changes${NC}"
fi
echo ""

# GitHub Status
echo -e "${YELLOW}🌐 GITHUB:${NC}"
echo "   Repository: $(git remote get-url origin)"
echo "   Branch: origin/$(git branch --show-current)"
echo "   Latest commit: $(git log origin/$(git branch --show-current) -1 --oneline 2>/dev/null || echo 'Unable to fetch')"
echo ""

# VM Status
echo -e "${YELLOW}🖥️  VM SERVER:${NC}"
echo "   Checking VM status..."
VM_INFO=$(ssh -o ConnectTimeout=5 $VM_HOST "sudo su - dataguardian -c 'cd /home/dataguardian/TwelvelabsWithOracleVector && git branch --show-current && git log -1 --oneline'" 2>/dev/null)

if [ $? -eq 0 ]; then
    VM_BRANCH=$(echo "$VM_INFO" | head -1)
    VM_COMMIT=$(echo "$VM_INFO" | tail -1)
    
    echo "   Branch: $VM_BRANCH"
    echo "   Latest commit: $VM_COMMIT"
    
    # Check if VM is behind
    VM_COMMIT_HASH=$(echo "$VM_COMMIT" | awk '{print $1}')
    LOCAL_COMMIT_SHORT=$(git rev-parse --short HEAD)
    
    if [ "$VM_COMMIT_HASH" = "$LOCAL_COMMIT_SHORT" ]; then
        echo -e "   Status: ${GREEN}✓ In sync with local${NC}"
    else
        echo -e "   Status: ${YELLOW}⚠️  Different from local - deploy needed${NC}"
    fi
    
    # Service status
    SERVICE_STATUS=$(ssh $VM_HOST "sudo systemctl is-active dataguardian.service" 2>/dev/null)
    if [ "$SERVICE_STATUS" = "active" ]; then
        echo -e "   Service: ${GREEN}✓ Running${NC}"
    else
        echo -e "   Service: ${RED}✗ Not running${NC}"
    fi
else
    echo -e "   ${RED}✗ Unable to connect to VM${NC}"
fi
echo ""

# Recommendations
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}📝 Recommendations:${NC}"

if ! git diff-index --quiet HEAD --; then
    echo "   1. Commit local changes: git add . && git commit -m 'message'"
fi

if [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
    if [ "$AHEAD" -gt 0 ]; then
        echo "   2. Push to GitHub: git push origin main"
    fi
    if [ "$BEHIND" -gt 0 ]; then
        echo "   2. Pull from GitHub: git pull origin main"
    fi
fi

if [ "$VM_COMMIT_HASH" != "$LOCAL_COMMIT_SHORT" ] && [ $? -eq 0 ]; then
    echo "   3. Deploy to VM: ./deploy_to_vm.sh 'message'"
fi

if [ "$SERVICE_STATUS" != "active" ]; then
    echo "   4. Start service: ssh $VM_HOST 'sudo systemctl start dataguardian.service'"
fi

echo ""
