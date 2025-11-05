#!/bin/bash
# Startup script for mishras.online domain deployment

echo "🌐 Configuring Flask app for mishras.online domain..."

# Set domain environment variables
export SERVER_NAME="mishras.online:8080"
export URL_SCHEME="https"
export FLASK_HOST="0.0.0.0"
export FLASK_PORT="8080"
export FLASK_DEBUG="True"
export CORS_ORIGINS="https://mishras.online,http://mishras.online"

# Change to the correct directory
cd "$(dirname "$0")/src"

echo "📂 Working directory: $(pwd)"
# Set OCI configuration for Media bucket
export DEFAULT_OCI_BUCKET="Media"
export OCI_COMPARTMENT_ID="ocid1.compartment.oc1..aaaaaaaaipofyxb7s2xmwe3j3skrccrj6yek6lgtlkekguzqlr2mlgyt54iq"
export MEDIA_BUCKET_OCID="ocid1.bucket.oc1.iad.aaaaaaaam5laocwjifjkwkxkyikyr2zdqy6vh5sdldrsqcluiw6s4hgi64lq"

echo "🔗 Domain: ${SERVER_NAME}"
echo "📦 OCI Bucket: ${DEFAULT_OCI_BUCKET}"
echo "🚀 Starting Flask application..."

# Start the Flask app with domain configuration
../bin/python agent_playback_app.py