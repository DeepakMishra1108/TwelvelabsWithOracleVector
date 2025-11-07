#!/bin/bash
# Start Flask Application with SSL Support
# Date: November 8, 2025

echo "🚀 DataGuardian Flask Application - Secure Startup"
echo "==================================================="
echo ""

# Check if running from correct directory
if [ ! -f "src/localhost_only_flask.py" ]; then
    echo "❌ Error: Must run from project root directory"
    echo "   Current directory: $(pwd)"
    echo "   Expected: TwelvelabsVideoAI/"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "   Please create .env file with required configuration"
    exit 1
fi

# Source environment variables
source .env

# Check SSL configuration
SSL_ENABLED="${SSL_ENABLED:-false}"
SSL_CERT_PATH="${SSL_CERT_PATH:-ssl/certificate.crt}"
SSL_KEY_PATH="${SSL_KEY_PATH:-ssl/private.key}"

if [ "$SSL_ENABLED" == "true" ]; then
    echo "🔐 SSL/TLS Mode: ENABLED"
    echo ""
    
    # Check if SSL certificates exist
    if [ ! -f "$SSL_CERT_PATH" ] || [ ! -f "$SSL_KEY_PATH" ]; then
        echo "❌ SSL certificates not found!"
        echo "   Expected certificate: $SSL_CERT_PATH"
        echo "   Expected private key: $SSL_KEY_PATH"
        echo ""
        echo "   Generating SSL certificates..."
        echo ""
        
        cd scripts
        ./generate_ssl_certificate.sh
        cd ..
        
        if [ ! -f "$SSL_CERT_PATH" ]; then
            echo "❌ Failed to generate SSL certificates"
            exit 1
        fi
    fi
    
    # Display certificate info
    echo "📋 Certificate Information:"
    openssl x509 -in "$SSL_CERT_PATH" -noout -subject -dates 2>/dev/null | sed 's/^/   /'
    echo ""
    
    PROTOCOL="https"
    PORT="${FLASK_PORT:-8443}"
else
    echo "🔓 SSL/TLS Mode: DISABLED (HTTP only)"
    echo ""
    PROTOCOL="http"
    PORT="${FLASK_PORT:-8080}"
fi

HOST="${FLASK_HOST:-127.0.0.1}"

echo "⚙️  Application Configuration:"
echo "   Protocol: $PROTOCOL"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo ""

echo "🔗 Access URLs:"
echo "   Application: $PROTOCOL://$HOST:$PORT/"
echo "   Health Check: $PROTOCOL://$HOST:$PORT/health"
echo "   Config Debug: $PROTOCOL://$HOST:$PORT/config_debug"
echo ""

if [ "$SSL_ENABLED" == "true" ]; then
    echo "⚠️  BROWSER SECURITY WARNING:"
    echo "   Self-signed certificates will trigger a browser warning."
    echo "   This is NORMAL and EXPECTED for development."
    echo ""
    echo "   To proceed:"
    echo "   1. Your browser will show 'Your connection is not private'"
    echo "   2. Click 'Advanced' or 'Show Details'"
    echo "   3. Click 'Proceed to localhost' or 'Accept the Risk'"
    echo ""
    echo "   Firefox: Add Security Exception"
    echo "   Chrome: Type 'thisisunsafe' when warning shows"
    echo "   Safari: Click 'Show Details' → 'visit this website'"
    echo ""
fi

echo "🎯 Starting Flask application..."
echo "   Press Ctrl+C to stop"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Python virtual environment exists
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment..."
    source .venv/bin/activate
fi

# Start Flask application
python3 src/localhost_only_flask.py
