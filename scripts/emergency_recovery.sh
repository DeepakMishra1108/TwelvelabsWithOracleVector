#!/bin/bash
# Emergency Recovery Script for OCI VM
# Run this immediately after VM becomes accessible

set -e

SERVER="ubuntu@150.136.235.189"
echo "=== Emergency Recovery for DataGuardian VM ==="
echo "Server: $SERVER"
echo ""

# Step 1: Check SSH connectivity
echo "Step 1: Testing SSH connection..."
if ! ssh -o ConnectTimeout=10 $SERVER 'echo "SSH OK"'; then
    echo "❌ SSH still not accessible. Wait and try again."
    exit 1
fi
echo "✅ SSH connection successful"
echo ""

# Step 2: Check service status
echo "Step 2: Checking service status..."
ssh $SERVER 'sudo systemctl status dataguardian-https.service --no-pager | head -20'
echo ""

# Step 3: Stop problematic service
echo "Step 3: Stopping dataguardian-https service..."
ssh $SERVER 'sudo systemctl stop dataguardian-https.service || true'
echo "✅ Service stopped"
echo ""

# Step 4: Check for stuck Python processes
echo "Step 4: Checking for stuck Python processes..."
ssh $SERVER 'ps aux | grep -E "python|gunicorn|imagebind" | grep -v grep || echo "No Python processes found"'
echo ""

# Step 5: Deploy clean code (without ImageBind preload)
echo "Step 5: Deploying fixed application files..."
scp ../src/localhost_only_flask.py $SERVER:/home/ubuntu/
scp ../src/search_flask_safe.py $SERVER:/home/ubuntu/
scp ../src/search_unified_flask_safe.py $SERVER:/home/ubuntu/
echo "✅ Files copied to staging"
echo ""

# Step 6: Deploy utils directory
echo "Step 6: Deploying utility modules..."
ssh $SERVER 'mkdir -p /home/ubuntu/src/utils'
scp -r ../src/utils/* $SERVER:/home/ubuntu/src/utils/
echo "✅ Utils deployed"
echo ""

# Step 7: Move files to production
echo "Step 7: Moving files to production directory..."
ssh $SERVER 'sudo cp /home/ubuntu/localhost_only_flask.py /home/dataguardian/TwelvelabsWithOracleVector/src/'
ssh $SERVER 'sudo cp /home/ubuntu/search_flask_safe.py /home/dataguardian/TwelvelabsWithOracleVector/src/'
ssh $SERVER 'sudo cp /home/ubuntu/search_unified_flask_safe.py /home/dataguardian/TwelvelabsWithOracleVector/src/'
ssh $SERVER 'sudo cp -r /home/ubuntu/src/utils/* /home/dataguardian/TwelvelabsWithOracleVector/src/utils/'
ssh $SERVER 'sudo chown -R dataguardian:dataguardian /home/dataguardian/TwelvelabsWithOracleVector/src/'
echo "✅ Files deployed to production"
echo ""

# Step 8: Verify the fix (check for ImageBind preload)
echo "Step 8: Verifying ImageBind preload is removed..."
if ssh $SERVER 'grep -n "Preloading ImageBind" /home/dataguardian/TwelvelabsWithOracleVector/src/localhost_only_flask.py'; then
    echo "⚠️ WARNING: ImageBind preload code still present!"
else
    echo "✅ ImageBind preload removed"
fi
echo ""

# Step 9: Start the service
echo "Step 9: Starting dataguardian-https service..."
ssh $SERVER 'sudo systemctl start dataguardian-https.service'
sleep 5
echo ""

# Step 10: Check service status
echo "Step 10: Checking service status..."
ssh $SERVER 'sudo systemctl status dataguardian-https.service --no-pager | head -20'
echo ""

# Step 11: Test HTTPS endpoint
echo "Step 11: Testing HTTPS endpoint..."
sleep 3
curl -k -I --connect-timeout 5 https://150.136.235.189:8443/ 2>&1 | head -5
echo ""

echo "=== Recovery Complete ==="
echo ""
echo "Next steps:"
echo "1. Test camera search: https://150.136.235.189:8443"
echo "2. Monitor logs: ssh $SERVER 'sudo journalctl -u dataguardian-https.service -f'"
echo "3. Check service: ssh $SERVER 'sudo systemctl status dataguardian-https.service'"
