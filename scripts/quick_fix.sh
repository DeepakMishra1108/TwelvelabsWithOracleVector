#!/bin/bash
# Quick Fix Script - Run this when SSH becomes accessible
# This keeps the service stopped while we deploy

set -e
SERVER="ubuntu@150.136.235.189"

echo "=== Quick Fix for DataGuardian VM ==="

# Step 1: Stop and disable auto-restart
echo "Step 1: Stopping service and preventing auto-restart..."
ssh $SERVER 'sudo systemctl stop dataguardian-https.service && sudo systemctl disable dataguardian-https.service'
echo "✅ Service stopped and disabled"
echo ""

# Step 2: Kill any Python processes
echo "Step 2: Killing Python processes..."
ssh $SERVER 'sudo pkill -9 python3 || true'
echo "✅ Processes killed"
echo ""

# Step 3: Deploy main file only (most critical)
echo "Step 3: Deploying localhost_only_flask.py..."
scp src/localhost_only_flask.py $SERVER:/home/ubuntu/
ssh $SERVER 'sudo cp /home/ubuntu/localhost_only_flask.py /home/dataguardian/TwelvelabsWithOracleVector/src/ && sudo chown dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/src/localhost_only_flask.py'
echo "✅ Main file deployed"
echo ""

# Step 4: Verify ImageBind preload is removed
echo "Step 4: Verifying fix..."
if ssh $SERVER 'grep "Preloading ImageBind" /home/dataguardian/TwelvelabsWithOracleVector/src/localhost_only_flask.py' 2>/dev/null; then
    echo "⚠️ WARNING: ImageBind preload still present!"
    exit 1
else
    echo "✅ ImageBind preload removed"
fi
echo ""

# Step 5: Re-enable and start service
echo "Step 5: Starting service..."
ssh $SERVER 'sudo systemctl enable dataguardian-https.service && sudo systemctl start dataguardian-https.service'
echo "✅ Service started"
echo ""

# Step 6: Wait and check status
echo "Step 6: Waiting 10 seconds for startup..."
sleep 10
ssh $SERVER 'sudo systemctl status dataguardian-https.service --no-pager | head -15'
echo ""

# Step 7: Test endpoint
echo "Step 7: Testing HTTPS..."
curl -k -I --connect-timeout 10 https://150.136.235.189:8443/ 2>&1 | head -5
echo ""

echo "=== Fix Complete ==="
