#!/bin/bash

# Safe startup script for Flask app with database connectivity checks
echo "🔍 Testing database connectivity before starting Flask app..."

cd "$(dirname "$0")/src"

# Test database connection with timeout
echo "📡 Testing Oracle database connection..."
timeout 10 ../bin/python -c "
import sys
sys.path.append('.')
from utils.db_utils_vector import test_db_connectivity
if test_db_connectivity():
    print('✅ Database connection successful')
    exit(0)
else:
    print('❌ Database connection failed')
    exit(1)
" 

if [ $? -eq 0 ]; then
    echo "🚀 Database connection verified. Starting Flask app..."
    
    # Set domain configuration
    export SERVER_NAME="mishras.online:8080"
    export URL_SCHEME="https"
    export FLASK_HOST="0.0.0.0"
    export FLASK_PORT="8080"
    export FLASK_DEBUG="True"
    
    # Set OCI configuration for Media bucket
    export DEFAULT_OCI_BUCKET="Media"
    export OCI_COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaaipofyxb7s2xmwe3j3skrccrj6yek6lgtlkekguzqlr2mlgyt54iq"
    export MEDIA_BUCKET_OCID="ocid1.bucket.oc1.iad.aaaaaaaam5laocwjifjkwkxkyikyr2zdqy6vh5sdldrsqcluiw6s4hgi64lq"
    
    echo "🔗 Domain: ${SERVER_NAME}"
    echo "📦 OCI Bucket: ${DEFAULT_OCI_BUCKET}"
    echo "🚀 Starting Flask application..."
    
    # Start Flask app
    ../bin/python agent_playback_app.py
else
    echo "❌ Cannot start Flask app - database connection failed"
    echo "Please check:"
    echo "  - Oracle wallet configuration"
    echo "  - Database connection string"
    echo "  - Network connectivity"
    exit 1
fi