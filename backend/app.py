"""
AI AutoForm - Flask API Server
Phase 4: Database Integration
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')

# CORS Configuration（開発環境用 - すべてのoriginを許可）
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# JWT
jwt = JWTManager(app)

# Rate Limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv('RATELIMIT_STORAGE_URL', 'memory://')
)

# Initialize database
from backend.database import init_db
with app.app_context():
    init_db()

# Register API Blueprints
from backend.api import workers_bp, products_bp, projects_bp, tasks_bp, targets_bp
app.register_blueprint(workers_bp)
app.register_blueprint(products_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(targets_bp)

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

