#!/bin/bash
# Template Deployment Script
# Deploys templates to the single active location: /home/dataguardian/TwelvelabsWithOracleVector/src/templates/

set -e

SERVER="ubuntu@150.136.235.189"
TEMPLATES_DIR="./src/templates"
SERVER_PATH="/home/dataguardian/TwelvelabsWithOracleVector/src/templates"

echo "🚀 Deploying templates from $TEMPLATES_DIR"
echo "📍 Target: $SERVER:$SERVER_PATH"
echo ""

# Copy templates to /tmp
echo "📤 Uploading templates..."
scp ${TEMPLATES_DIR}/*.html ${SERVER}:/tmp/

# Move to final location with proper permissions
echo "📥 Installing templates..."
ssh ${SERVER} "sudo bash -c 'cp /tmp/*.html ${SERVER_PATH}/ && chown dataguardian:dataguardian ${SERVER_PATH}/*.html && rm /tmp/*.html'"

echo ""
echo "✅ Deployment complete!"
echo "📊 Verifying..."
ssh ${SERVER} "sudo ls -lh ${SERVER_PATH}/*.html | wc -l | xargs echo 'Templates deployed:'"
