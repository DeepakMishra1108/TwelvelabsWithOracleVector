#!/bin/bash

###############################################################################
# Helper script to configure .env file with your credentials
###############################################################################

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Configure .env File for Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "You need to fill in 4 required values in the .env file:"
echo ""
echo -e "${YELLOW}1. ORACLE_DB_PASSWORD${NC}"
echo "   Your Oracle Autonomous Database ADMIN password"
echo ""
echo -e "${YELLOW}2. ORACLE_DB_CONNECT_STRING${NC}"
echo "   Found in wallet: ocdmrealtime_high"
echo "   (Already detected: ocdmrealtime_high)"
echo ""
echo -e "${YELLOW}3. ORACLE_DB_WALLET_PASSWORD${NC}"
echo "   Password you set when downloading the database wallet"
echo ""
echo -e "${YELLOW}4. TWELVE_LABS_API_KEY${NC}"
echo "   Get from: https://dashboard.twelvelabs.io/"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "I'll open the .env file in your default editor."
echo "Replace all 'YOUR_*_HERE' placeholders with actual values."
echo ""
read -p "Press ENTER to open .env file for editing..."

# Update connection string automatically
sed -i.bak 's/YOUR_CONNECTION_STRING_HIGH/ocdmrealtime_high/' /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI/twelvelabvideoai/.env

# Open in editor
if [ -n "$VISUAL" ]; then
    $VISUAL /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI/twelvelabvideoai/.env
elif [ -n "$EDITOR" ]; then
    $EDITOR /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI/twelvelabvideoai/.env
elif command -v code &> /dev/null; then
    code /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI/twelvelabvideoai/.env
elif command -v nano &> /dev/null; then
    nano /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI/twelvelabvideoai/.env
else
    vi /Users/deepamis/Documents/GitHub/TwelvelabsVideoAI/twelvelabvideoai/.env
fi

echo ""
echo -e "${GREEN}✓ .env file saved${NC}"
echo ""
echo "Next steps:"
echo "1. Verify all values are filled in (no YOUR_*_HERE placeholders)"
echo "2. Run: ./scripts/pre_deployment_check.sh"
echo "3. If checks pass, run: ./scripts/oci_full_deployment.sh"
echo ""
