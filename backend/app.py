"""
AI AutoForm - Flask API Server
Phase 2: Backend Integration
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

# ========================================
# Health Check
# ========================================
@app.route('/api/health', methods=['GET'])
def health_check():
    """システムヘルスチェック"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI AutoForm API',
        'version': '2.0.0'
    })

# ========================================
# Companies API
# ========================================
@app.route('/api/companies', methods=['GET'])
@limiter.limit("30 per minute")
def get_companies():
    """企業リスト取得"""
    # TODO: データベースから取得
    return jsonify({
        'companies': [],
        'total': 0
    })

@app.route('/api/companies', methods=['POST'])
@limiter.limit("10 per minute")
def create_company():
    """新規企業登録"""
    data = request.get_json()
    
    # バリデーション
    if not data.get('name') or not data.get('url'):
        return jsonify({'error': '企業名とURLは必須です'}), 400
    
    # TODO: データベースに保存
    return jsonify({
        'message': '企業を登録しました',
        'company': {
            'id': 1,
            'name': data['name'],
            'url': data['url']
        }
    }), 201

@app.route('/api/companies/<int:company_id>/analyze', methods=['POST'])
@limiter.limit("5 per minute")
def analyze_company(company_id):
    """企業AI解析"""
    # TODO: Gemini API連携
    return jsonify({
        'message': 'AI解析を開始しました',
        'company_id': company_id,
        'status': 'analyzing'
    })

# ========================================
# Projects API
# ========================================
@app.route('/api/projects', methods=['GET'])
def get_projects():
    """プロジェクト一覧取得"""
    # TODO: データベースから取得
    return jsonify({
        'projects': [],
        'total': 0
    })

@app.route('/api/projects', methods=['POST'])
@limiter.limit("10 per minute")
def create_project():
    """新規プロジェクト作成"""
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'プロジェクト名は必須です'}), 400
    
    # TODO: データベースに保存
    return jsonify({
        'message': 'プロジェクトを作成しました',
        'project': {
            'id': 1,
            'name': data['name']
        }
    }), 201

# ========================================
# Workers API
# ========================================
@app.route('/api/workers', methods=['GET'])
def get_workers():
    """作業者一覧取得"""
    # TODO: データベースから取得
    return jsonify({
        'workers': [],
        'total': 0
    })

@app.route('/api/workers', methods=['POST'])
@limiter.limit("10 per minute")
def create_worker():
    """新規作業者登録"""
    data = request.get_json()
    
    if not data.get('name') or not data.get('email'):
        return jsonify({'error': '名前とメールアドレスは必須です'}), 400
    
    # TODO: データベースに保存
    return jsonify({
        'message': '作業者を登録しました',
        'worker': {
            'id': 1,
            'name': data['name'],
            'email': data['email']
        }
    }), 201

# ========================================
# Target Lists API (NEW)
# ========================================
target_lists_db = []  # 仮のメモリストア

@app.route('/api/target-lists', methods=['GET'])
def get_target_lists():
    """ターゲットリスト一覧取得"""
    return jsonify({
        'targetLists': target_lists_db
    })

@app.route('/api/target-lists', methods=['POST'])
@limiter.limit("20 per minute")
def create_target_list():
    """ターゲットリスト作成"""
    data = request.get_json()
    
    if not data.get('name') or not data.get('companies'):
        return jsonify({'error': 'リスト名と企業リストは必須です'}), 400
    
    new_list = {
        'id': len(target_lists_db) + 1,
        'name': data['name'],
        'companies': data['companies'],
        'createdAt': datetime.utcnow().isoformat()
    }
    
    target_lists_db.append(new_list)
    
    return jsonify({
        'message': 'ターゲットリストを作成しました',
        'targetList': new_list
    }), 201

@app.route('/api/target-lists/<int:list_id>', methods=['DELETE'])
def delete_target_list(list_id):
    """ターゲットリスト削除"""
    global target_lists_db
    target_lists_db = [tl for tl in target_lists_db if tl['id'] != list_id]
    
    return jsonify({
        'message': 'ターゲットリストを削除しました'
    })

# ========================================
# Tasks API - Form Submission (NEW)
# ========================================
@app.route('/api/tasks/<int:task_id>/submit', methods=['POST'])
@limiter.limit("10 per minute")
def submit_task_form(task_id):
    """タスクのフォーム自動送信"""
    data = request.get_json()
    
    if not data.get('companyUrl') or not data.get('formData'):
        return jsonify({'error': 'URLとフォームデータは必須です'}), 400
    
    try:
        # Playwright自動化サービスをインポート
        from services.automation_service import FormAutomationService
        
        # ヘッドレスモードで起動（headless=False にするとブラウザが表示される）
        automation = FormAutomationService(headless=False)
        automation.start()
        
        # formDataを適切なキー名に変換
        message_data = {
            'sender_company': data['formData'].get('company', ''),
            'sender_name': data['formData'].get('name', ''),
            'sender_email': data['formData'].get('email', ''),
            'sender_phone': data['formData'].get('phone', ''),
            'message': data['formData'].get('message', '')
        }
        
        # テスト用フォームURLを使用（本番環境では実際のURLを使用）
        # デフォルトはlocalhost（ローカル開発環境）
        test_form_url = 'http://localhost:8000/test-form.html'
        
        actual_url = data.get('companyUrl', test_form_url)
        
        # URLが空またはプレースホルダーの場合はテストフォームを使用
        if not actual_url or 'example.com' in actual_url:
            actual_url = test_form_url
        
        result = automation.fill_contact_form(
            form_url=actual_url,
            message_data=message_data,
            wait_for_captcha=False  # Codespaces環境では自動で進める
        )
        
        automation.stop()
        
        if result.get('success'):
            return jsonify({
                'message': 'フォーム送信が完了しました',
                'taskId': task_id,
                'result': result,
                'url': actual_url
            })
        else:
            return jsonify({
                'error': 'フォーム送信に失敗しました',
                'details': result.get('error')
            }), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': f'送信処理エラー: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

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
    ║   Version: 2.0.0                          ║
    ║   Environment: {os.getenv('FLASK_ENV', 'development'): <30}║
    ║   Port: {port: <35}║
    ╚═══════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
