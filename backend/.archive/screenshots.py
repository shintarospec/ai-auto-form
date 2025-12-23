"""
Screenshots API endpoint.
Serve screenshot images for worker console.
"""

from flask import send_file, jsonify
from backend.api import screenshots_bp
import os


@screenshots_bp.route('/<path:filename>', methods=['GET'])
def get_screenshot(filename):
    """Get a screenshot image"""
    try:
        filepath = f'/tmp/{filename}'
        if not os.path.exists(filepath):
            return jsonify({'error': 'Screenshot not found'}), 404
        
        return send_file(filepath, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
