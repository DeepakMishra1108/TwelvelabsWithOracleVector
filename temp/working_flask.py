#!/usr/bin/env python3
"""
Working Flask app - simplified version of agent_playback_app.py
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

app = Flask(__name__, template_folder='./twelvelabvideoai/src/templates')

@app.route('/')
def index():
    """Main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Template error: {e}")
        return f"Template error: {e}", 500

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
        logger.info(f"✅ Found {len(albums)} albums")
        
        # Convert datetime objects to strings for JSON
        albums_json = []
        for album in albums:
            album_copy = album.copy()
            if 'created_at' in album_copy and album_copy['created_at']:
                album_copy['created_at'] = album_copy['created_at'].isoformat()
            if 'updated_at' in album_copy and album_copy['updated_at']:
                album_copy['updated_at'] = album_copy['updated_at'].isoformat()
            albums_json.append(album_copy)
        
        return jsonify({'albums': albums_json, 'count': len(albums_json)})
        
    except Exception as e:
        logger.exception('❌ Failed to list albums')
        return jsonify({'error': str(e), 'albums': [], 'count': 0}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'album_manager': UNIFIED_ALBUM_AVAILABLE,
        'albums_count': len(album_manager.list_albums()) if UNIFIED_ALBUM_AVAILABLE else 0
    })

if __name__ == '__main__':
    logger.info("🚀 Starting simplified Flask app...")
    
    # Set environment variables
    os.environ['PYTHONPATH'] = './twelvelabvideoai/src'
    
    try:
        app.run(host='0.0.0.0', port=8080, debug=False)
    except Exception as e:
        logger.error(f"❌ Flask startup failed: {e}")
        import traceback
        traceback.print_exc()