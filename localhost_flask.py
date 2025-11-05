#!/usr/bin/env python3
"""
Localhost-only Flask app - guaranteed to work without domain configuration issues
"""

from flask import Flask, request, render_template, jsonify
import os
import sys
import json
import logging

# Add src to path
sys.path.append('./twelvelabvideoai/src')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import album manager safely
try:
    from unified_album_manager import album_manager
    UNIFIED_ALBUM_AVAILABLE = True
    logger.info("✅ Album manager imported successfully")
except Exception as e:
    logger.error(f"❌ Could not import album manager: {e}")
    album_manager = None
    UNIFIED_ALBUM_AVAILABLE = False

# Create Flask app with explicit localhost configuration
app = Flask(__name__, template_folder='./twelvelabvideoai/src/templates')

# Explicitly set localhost-only configuration
app.config['SERVER_NAME'] = None  # No domain binding
app.config['PREFERRED_URL_SCHEME'] = 'http'
app.config['APPLICATION_ROOT'] = '/'

@app.route('/')
def index():
    """Main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Template error: {e}")
        return f"Template error: {e}", 500

@app.route('/health')
def health_check():
    """Simple health check for localhost"""
    return jsonify({
        'status': 'healthy',
        'mode': 'localhost',
        'albums_available': UNIFIED_ALBUM_AVAILABLE,
        'host': request.host
    })

@app.route('/list_unified_albums')
def list_unified_albums():
    """List all albums"""
    try:
        logger.info("📋 Album listing request received")
        
        if not UNIFIED_ALBUM_AVAILABLE or album_manager is None:
            logger.error("❌ Album manager not available")
            return jsonify({'error': 'Album manager not available', 'albums': [], 'count': 0})
        
        logger.info("🔍 Fetching albums...")
        albums = album_manager.list_albums()
        
        # Convert to proper format
        album_list = []
        for album in albums:
            album_data = {
                'album_id': album.get('album_id'),
                'album_name': album.get('album_name'),
                'description': album.get('description', ''),
                'created_at': album.get('created_at'),
                'item_count': album.get('item_count', 0)
            }
            album_list.append(album_data)
        
        logger.info(f"✅ Found {len(album_list)} albums")
        return jsonify({'albums': album_list, 'count': len(album_list)})
        
    except Exception as e:
        logger.error(f"❌ Error listing albums: {e}")
        return jsonify({'error': str(e), 'albums': [], 'count': 0})

@app.route('/debug')
def debug_info():
    """Debug endpoint to show configuration"""
    return jsonify({
        'app_config': {
            'SERVER_NAME': app.config.get('SERVER_NAME'),
            'PREFERRED_URL_SCHEME': app.config.get('PREFERRED_URL_SCHEME'),
            'APPLICATION_ROOT': app.config.get('APPLICATION_ROOT'),
        },
        'request_info': {
            'host': request.host,
            'url': request.url,
            'headers': dict(request.headers)
        },
        'environment': {
            'SERVER_NAME': os.environ.get('SERVER_NAME'),
            'FLASK_HOST': os.environ.get('FLASK_HOST'),
            'CORS_ORIGINS': os.environ.get('CORS_ORIGINS'),
        }
    })

if __name__ == '__main__':
    logger.info("🚀 Starting localhost-only Flask app...")
    logger.info("🌐 Access at: http://localhost:8080")
    logger.info("💊 Health check: http://localhost:8080/health")
    logger.info("🔧 Debug info: http://localhost:8080/debug")
    
    # Run on localhost only - no domain configuration
    app.run(
        host='127.0.0.1',  # Localhost only, not 0.0.0.0
        port=8080,
        debug=False,
        threaded=True
    )