#!/bin/bash
#
# Quick Deploy & Restart Script for VM
# Pulls latest code and restarts the service
#
# Usage: ./scripts/deploy_and_restart.sh

set -e  # Exit on error

echo "🚀 Deploy & Restart - Data Guardian"
echo "==================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$(dirname "$0")/.."

echo -e "${YELLOW}📥 Pulling latest code...${NC}"
git pull origin main

echo -e "${YELLOW}🔄 Restarting Data Guardian service...${NC}"
sudo systemctl restart dataguardian

echo -e "${YELLOW}⏳ Waiting for service to start...${NC}"
sleep 5

# Check if service is running
if sudo systemctl is-active --quiet dataguardian; then
    echo -e "${GREEN}✅ Service restarted successfully!${NC}"

    # Quick health check
    if curl -k -s -o /dev/null -w "%{http_code}" https://localhost 2>/dev/null | grep -q "^[23]"; then
        echo -e "${GREEN}✅ Application is responding${NC}"
    else
        echo -e "${YELLOW}⚠️  Application may still be starting...${NC}"
    fi

    echo ""
    echo "🌐 Test your application at: https://your-server-ip"
    echo "📊 Monitor logs: sudo journalctl -u dataguardian -f"
else
    echo -e "${RED}❌ Service failed to start${NC}"
    echo "Check logs: sudo journalctl -u dataguardian -n 50"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Deployment & restart complete!${NC}"