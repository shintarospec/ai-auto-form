"""
AI AutoForm - Flask API Server
Phase 1: MVP Version
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# CORS Configuration（開発環境用 - すべて許可）
CORS(app)

# Initialize database
from backend.database import init_db
with app.app_context():
    init_db()

# Register API Blueprints
from backend.api.simple_api import simple_bp
app.register_blueprint(simple_bp)  # Phase 1 MVP API

# ========================================
# Root Endpoint
# ========================================
@app.route('/')
def index():
    """API情報を返す"""
    return jsonify({
        'service': 'AI AutoForm API',
        'version': '1.0.0 MVP',
        'status': 'running',
        'endpoints': {
            'health': '/api/health',
            'tasks': '/api/simple/tasks',
            'task_detail': '/api/simple/tasks/<id>',
            'execute_task': 'POST /api/simple/tasks/<id>/execute',
            'complete_task': 'POST /api/simple/tasks/<id>/complete'
        }
    })

# ========================================
# Static Files (Screenshots)
# ========================================
@app.route('/screenshots/<path:filename>')
def serve_screenshot(filename):
    """スクリーンショット画像を配信"""
    screenshots_dir = '/workspaces/ai-auto-form/screenshots'
    return send_from_directory(screenshots_dir, filename)

# ========================================
# Health Check
# ========================================
@app.route('/api/health', methods=['GET'])
def health_check():
    """システムヘルスチェック"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI AutoForm API',
        'version': '3.0.0',
        'database': 'PostgreSQL'
    })

# ========================================
# Error Handlers
# ========================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'レート制限を超えました。しばらく待ってから再試行してください。'}), 429

# ========================================
# Run Server
# ========================================
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    print(f"""
    ╔═══════════════════════════════════════════╗
    ║   AI AutoForm API Server                  ║
    ║   Version: 3.0.0 (PostgreSQL)             ║
    ║   Environment: {os.getenv('FLASK_ENV', 'development'): <30}║
    ║   Port: {port: <35}║
    ║   Database: PostgreSQL                    ║
    ╚═══════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=debug)

