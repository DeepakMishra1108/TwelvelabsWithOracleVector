#!/bin/bash
# Deploy Face Tagging Feature to Production VM
# This script deploys all face tagging components to the production server

set -e  # Exit on error

# Configuration
VM_HOST="ubuntu@150.136.235.189"
VM_PATH="/home/dataguardian/TwelvelabsWithOracleVector"
LOCAL_PATH="/Users/deepamis/Documents/GitHub/TwelvelabsVideoAI"

echo "========================================="
echo "Face Tagging Feature Deployment"
echo "========================================="
echo ""

# Step 1: Deploy backend utilities
echo "📦 Step 1: Deploying backend utilities..."
scp "$LOCAL_PATH/src/utils/face_detection_helper.py" \
    "$VM_HOST:$VM_PATH/src/utils/"

scp "$LOCAL_PATH/src/utils/auto_face_recognition.py" \
    "$VM_HOST:$VM_PATH/src/utils/"

scp "$LOCAL_PATH/src/utils/face_filtering.py" \
    "$VM_HOST:$VM_PATH/src/utils/"

echo "✅ Backend utilities deployed"
echo ""

# Step 2: Deploy main Flask app
echo "📦 Step 2: Deploying main Flask application..."
scp "$LOCAL_PATH/src/localhost_only_flask.py" \
    "$VM_HOST:$VM_PATH/src/"

echo "✅ Flask app deployed"
echo ""

# Step 3: Deploy UI components
echo "📦 Step 3: Deploying UI components..."
scp "$LOCAL_PATH/twelvelabvideoai/src/templates/face_tagging_components.html" \
    "$VM_HOST:$VM_PATH/twelvelabvideoai/src/templates/"

echo "✅ UI components deployed"
echo ""

# Step 4: Install dependencies on VM
echo "📦 Step 4: Installing dependencies on VM..."
ssh $VM_HOST << 'EOF'
cd /home/dataguardian/TwelvelabsWithOracleVector
pip install opencv-python --quiet
python -c "import cv2; print('✅ OpenCV', cv2.__version__, 'installed')"
EOF

echo "✅ Dependencies installed"
echo ""

# Step 5: Restart application
echo "🔄 Step 5: Restarting application..."
ssh $VM_HOST << 'EOF'
sudo systemctl restart dataguardian
sleep 3
sudo systemctl status dataguardian --no-pager | head -20
EOF

echo "✅ Application restarted"
echo ""

# Step 6: Test endpoints
echo "🧪 Step 6: Testing endpoints..."
ssh $VM_HOST << 'EOF'
cd /home/dataguardian/TwelvelabsWithOracleVector

echo "Testing face profile endpoint..."
curl -s -X GET http://localhost:8443/user/face_profile \
  -H "Cookie: session=test" || echo "⚠️  Endpoint requires authentication"

echo ""
echo "Testing face detection helper..."
python -c "from src.utils.face_detection_helper import check_dependencies; print('✅ Face detection module loaded')"

echo ""
echo "Testing auto face recognition..."
python -c "from src.utils.auto_face_recognition import auto_recognize_faces; print('✅ Auto recognition module loaded')"

echo ""
echo "Testing face filtering..."
python -c "from src.utils.face_filtering import should_filter_by_face; print('✅ Face filtering module loaded')"
EOF

echo "✅ Tests completed"
echo ""

# Step 7: Check database tables
echo "🗄️  Step 7: Verifying database schema..."
ssh $VM_HOST << 'EOF'
cd /home/dataguardian/TwelvelabsWithOracleVector

python << 'PYTHON'
import sys
sys.path.insert(0, 'twelvelabvideoai/src')

from utils.db_utils_flask_safe import get_flask_safe_connection

try:
    with get_flask_safe_connection() as conn:
        cursor = conn.cursor()
        
        # Check face_tags table
        cursor.execute("SELECT COUNT(*) FROM face_tags")
        face_tags_count = cursor.fetchone()[0]
        print(f"✅ face_tags table: {face_tags_count} records")
        
        # Check user_face_profiles table
        cursor.execute("SELECT COUNT(*) FROM user_face_profiles")
        profiles_count = cursor.fetchone()[0]
        print(f"✅ user_face_profiles table: {profiles_count} records")
        
        # Check face_recognition_cache table
        cursor.execute("SELECT COUNT(*) FROM face_recognition_cache")
        cache_count = cursor.fetchone()[0]
        print(f"✅ face_recognition_cache table: {cache_count} records")
        
        print("\n✅ All database tables verified")
except Exception as e:
    print(f"❌ Database check failed: {e}")
    sys.exit(1)
PYTHON
EOF

echo ""
echo "========================================="
echo "✅ Deployment Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Test face capture: Login as viewer user"
echo "2. Test face detection: Upload a photo, click 'Detect Faces'"
echo "3. Test manual tagging: Tag a detected face"
echo "4. Test auto-recognition: Upload another photo with the same person"
echo "5. Monitor logs: ssh $VM_HOST 'tail -f /home/dataguardian/logs/gunicorn-error.log'"
echo ""
echo "Access the application at: https://150.136.235.189:8443"
echo ""
