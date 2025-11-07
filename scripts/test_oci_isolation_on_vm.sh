#!/bin/bash
# Test OCI Path Isolation on Production VM
# Run this script on the OCI VM (150.136.235.189) where OCI is configured

echo "=================================================="
echo "OCI Path Isolation Testing - Production VM"
echo "=================================================="
echo ""

# Check if running on VM
if [ ! -f "/home/ubuntu/TwelvelabsVideoAI/.env" ]; then
    echo "❌ Error: This script should be run on the production VM"
    echo "   SSH to VM: ssh ubuntu@150.136.235.189"
    echo "   Then run: cd /home/ubuntu/TwelvelabsVideoAI && ./scripts/test_oci_isolation_on_vm.sh"
    exit 1
fi

cd /home/ubuntu/TwelvelabsVideoAI

echo "1️⃣  Checking OCI Configuration..."
echo "=================================="
if grep -q "OCI_NAMESPACE" .env && grep -q "OCI_BUCKET_NAME" .env; then
    echo "✅ OCI environment variables found in .env"
    grep "OCI_NAMESPACE" .env
    grep "OCI_BUCKET_NAME" .env
else
    echo "❌ OCI environment variables missing from .env"
    echo "   Add the following to .env:"
    echo "   OCI_NAMESPACE=your_namespace"
    echo "   OCI_BUCKET_NAME=video-ai-storage"
    exit 1
fi
echo ""

echo "2️⃣  Running Path Isolation Tests..."
echo "=================================="
python3 scripts/test_oci_path_isolation.py
TEST_EXIT_CODE=$?
echo ""

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
    echo ""
    echo "3️⃣  Next Steps - Manual Testing:"
    echo "=================================="
    echo ""
    echo "A. Test User 1 Upload:"
    echo "   1. Login as user 1 (admin or editor)"
    echo "   2. Upload a photo via web UI"
    echo "   3. Expected path: users/1/uploads/photos/{filename}"
    echo ""
    echo "B. Test User 2 Upload:"
    echo "   1. Login as user 2 (different user)"
    echo "   2. Upload a photo via web UI"
    echo "   3. Expected path: users/2/uploads/photos/{filename}"
    echo ""
    echo "C. Test Generated Content:"
    echo "   1. Login as user 1"
    echo "   2. Create a slideshow or montage"
    echo "   3. Expected path: users/1/generated/slideshows/{filename}"
    echo "   4. Or: users/1/generated/montages/{filename}"
    echo ""
    echo "D. Verify OCI Bucket:"
    echo "   Run: oci os object list --bucket-name video-ai-storage --prefix users/"
    echo ""
    echo "E. Test Access Isolation:"
    echo "   1. Login as user 1, note a file path"
    echo "   2. Logout, login as user 2"
    echo "   3. Try to access user 1's file URL"
    echo "   4. Should get 403 Forbidden or redirect"
    echo ""
else
    echo "❌ Some tests failed. Fix the issues above before manual testing."
    exit 1
fi
