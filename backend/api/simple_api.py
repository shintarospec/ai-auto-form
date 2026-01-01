"""
Simple API for Phase 1 MVP
シンプルなAPI実装（4つのエンドポイント）
"""

from flask import Blueprint, jsonify, request
from backend.database import get_db_session
from backend.simple_models import Company, Product, Task
from sqlalchemy.orm import joinedload
from sqlalchemy import text
from datetime import datetime
import os
import asyncio
from playwright.async_api import async_playwright
from backend.services.gemini_service import GeminiService

simple_bp = Blueprint('simple', __name__, url_prefix='/api/simple')


# ===============================
# ヘルパー関数: 分割/結合処理
# ===============================

def combine_split_fields(data, field_base, separator='-'):
    """
    分割されたフィールドを結合する
    例: sender_phone_1, sender_phone_2, sender_phone_3 → "090-0000-0000"
    """
    parts = []
    index = 1
    while True:
        key = f"{field_base}_{index}"
        if key in data and data[key]:
            parts.append(data[key])
            index += 1
        else:
            break
    
    if parts:
        return separator.join(parts)
    return None


def split_combined_field(value, separator='-'):
    """
    結合されたフィールドを分割する
    例: "090-0000-0000" → ["090", "0000", "0000"]
    """
    if not value:
        return []
    return [part.strip() for part in value.split(separator) if part.strip()]


def prepare_form_data_from_product(product):
    """
    Productオブジェクトから form_data を生成
    分割フィールドと結合フィールドの両方に対応
    """
    form_data = {}
    
    # 氏名（分割 or 結合）
    if product.sender_last_name and product.sender_first_name:
        form_data['name'] = f"{product.sender_last_name} {product.sender_first_name}"
        form_data['last_name'] = product.sender_last_name
        form_data['first_name'] = product.sender_first_name
    elif product.sender_name:
        form_data['name'] = product.sender_name
    
    # フリガナ（分割 or 結合）
    if product.sender_last_name_kana and product.sender_first_name_kana:
        form_data['name_kana'] = f"{product.sender_last_name_kana} {product.sender_first_name_kana}"
        form_data['last_name_kana'] = product.sender_last_name_kana
        form_data['first_name_kana'] = product.sender_first_name_kana
    
    # 会社情報
    if product.sender_company:
        form_data['company'] = product.sender_company
    if product.sender_company_kana:
        form_data['company_kana'] = product.sender_company_kana
    if product.sender_company_url:
        form_data['company_url'] = product.sender_company_url
    if product.sender_department:
        form_data['department'] = product.sender_department
    if product.sender_position:
        form_data['position'] = product.sender_position
    if product.sender_rep_name:
        form_data['rep_name'] = product.sender_rep_name
    if product.sender_rep_name_kana:
        form_data['rep_name_kana'] = product.sender_rep_name_kana
    
    # 性別
    if product.sender_gender:
        form_data['gender'] = product.sender_gender
    
    # 電話番号（分割 or 結合）
    if product.sender_phone_1 and product.sender_phone_2 and product.sender_phone_3:
        form_data['phone'] = f"{product.sender_phone_1}-{product.sender_phone_2}-{product.sender_phone_3}"
        form_data['phone1'] = product.sender_phone_1
        form_data['phone2'] = product.sender_phone_2
        form_data['phone3'] = product.sender_phone_3
    elif product.sender_phone:
        form_data['phone'] = product.sender_phone
        # 分割を試みる
        parts = split_combined_field(product.sender_phone, '-')
        if len(parts) == 3:
            form_data['phone1'], form_data['phone2'], form_data['phone3'] = parts
    
    # 携帯番号（分割 or 結合）
    if product.sender_mobile_1 and product.sender_mobile_2 and product.sender_mobile_3:
        form_data['mobile'] = f"{product.sender_mobile_1}-{product.sender_mobile_2}-{product.sender_mobile_3}"
        form_data['mobile1'] = product.sender_mobile_1
        form_data['mobile2'] = product.sender_mobile_2
        form_data['mobile3'] = product.sender_mobile_3
    
    # FAX（分割 or 結合）
    if product.sender_fax_1 and product.sender_fax_2 and product.sender_fax_3:
        form_data['fax'] = f"{product.sender_fax_1}-{product.sender_fax_2}-{product.sender_fax_3}"
        form_data['fax1'] = product.sender_fax_1
        form_data['fax2'] = product.sender_fax_2
        form_data['fax3'] = product.sender_fax_3
    
    # メールアドレス
    if product.sender_email:
        form_data['email'] = product.sender_email
    if product.sender_email_company:
        form_data['email_company'] = product.sender_email_company
    if product.sender_email_personal:
        form_data['email_personal'] = product.sender_email_personal
    
    # 郵便番号（分割 or 結合）
    if product.sender_zipcode_1 and product.sender_zipcode_2:
        form_data['zipcode'] = f"{product.sender_zipcode_1}-{product.sender_zipcode_2}"
        form_data['zipcode1'] = product.sender_zipcode_1
        form_data['zipcode2'] = product.sender_zipcode_2
    
    # 住所（分割 or 結合）
    if product.sender_prefecture:
        form_data['prefecture'] = product.sender_prefecture
    if product.sender_city:
        form_data['city'] = product.sender_city
    if product.sender_address:
        form_data['address'] = product.sender_address
    
    # 住所結合版
    if product.sender_prefecture and product.sender_city and product.sender_address:
        form_data['full_address'] = f"{product.sender_prefecture}{product.sender_city}{product.sender_address}"
    
    # お問い合わせ
    if product.sender_inquiry_title:
        form_data['inquiry_title'] = product.sender_inquiry_title
    if product.sender_inquiry_detail:
        form_data['inquiry_detail'] = product.sender_inquiry_detail
    
    return form_data


# ===============================
# API エンドポイント
# ===============================

@simple_bp.route('/migrate/sender-info', methods=['POST'])
def migrate_sender_info():
    """送信者情報カラム追加マイグレーション"""
    db = get_db_session()
    try:
        print("📝 マイグレーション開始: sender情報追加")
        
        # 1. カラム追加
        db.execute(text("""
            ALTER TABLE simple_products
            ADD COLUMN IF NOT EXISTS sender_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS sender_email VARCHAR(200),
            ADD COLUMN IF NOT EXISTS sender_company VARCHAR(200),
            ADD COLUMN IF NOT EXISTS sender_phone VARCHAR(50)
        """))
        print("✅ カラム追加完了")
        
        # 2. デフォルト値設定
        result = db.execute(text("""
            UPDATE simple_products 
            SET 
                sender_name = COALESCE(sender_name, '山田太郎'),
                sender_email = COALESCE(sender_email, 'yamada@example.com'),
                sender_company = COALESCE(sender_company, '株式会社テスト'),
                sender_phone = COALESCE(sender_phone, '03-1234-5678')
        """))
        
        db.commit()
        print(f"✅ デフォルト値設定完了 (更新: {result.rowcount}行)")
        
        # 3. 確認
        result = db.execute(text("""
            SELECT id, name, sender_name, sender_email, sender_company, sender_phone
            FROM simple_products
        """)).fetchall()
        
        products = [
            {
                'id': row[0],
                'name': row[1],
                'sender_name': row[2],
                'sender_email': row[3],
                'sender_company': row[4],
                'sender_phone': row[5]
            }
            for row in result
        ]
        
        return jsonify({
            'success': True,
            'message': '送信者情報カラム追加完了',
            'updated_rows': len(products),
            'products': products
        })
        
    except Exception as e:
        db.rollback()
        print(f"❌ マイグレーションエラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    finally:
        db.close()


@simple_bp.route('/migrate/google-place-id', methods=['POST'])
def migrate_google_place_id():
    """google_place_idカラム追加マイグレーション"""
    db = get_db_session()
    try:
        # 1. カラム追加
        db.execute(text("""
            ALTER TABLE simple_companies
            ADD COLUMN IF NOT EXISTS google_place_id VARCHAR(255);
        """))
        
        # 2. インデックス作成
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_google_place_id 
            ON simple_companies(google_place_id);
        """))
        
        db.commit()
        
        # 3. 確認
        result = db.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'simple_companies'
            AND column_name = 'google_place_id';
        """)).fetchone()
        
        return jsonify({
            'success': True,
            'message': 'google_place_id column added successfully',
            'column_info': {
                'name': result[0] if result else None,
                'type': result[1] if result else None
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@simple_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """タスク一覧を取得"""
    db = get_db_session()
    try:
        tasks = db.query(Task).options(
            joinedload(Task.company),
            joinedload(Task.product)
        ).order_by(Task.created_at.desc()).all()
        
        return jsonify([task.to_dict() for task in tasks])
    finally:
        db.close()


@simple_bp.route('/companies', methods=['GET'])
def get_companies():
    """企業一覧を取得"""
    db = get_db_session()
    try:
        companies = db.query(Company).order_by(Company.created_at.desc()).all()
        return jsonify([company.to_dict() for company in companies])
    finally:
        db.close()


@simple_bp.route('/products', methods=['GET'])
def get_products():
    """案件・商材一覧を取得"""
    db = get_db_session()
    try:
        products = db.query(Product).order_by(Product.created_at.desc()).all()
        return jsonify([product.to_dict() for product in products])
    finally:
        db.close()


@simple_bp.route('/products', methods=['POST'])
def create_product():
    """新規案件を作成"""
    db = get_db_session()
    try:
        data = request.get_json()
        
        # バリデーション
        if not data.get('name'):
            return jsonify({'error': '案件名は必須です'}), 400
        
        # 送信者名：フルネームまたは姓名どちらかが必須
        has_name = data.get('sender_name') or (data.get('sender_last_name') and data.get('sender_first_name'))
        if not has_name:
            return jsonify({'error': '送信者名（フルネームまたは姓名）は必須です'}), 400
            
        # メールアドレス：いずれかが必須
        has_email = data.get('sender_email') or data.get('sender_email_company') or data.get('sender_email_personal')
        if not has_email:
            return jsonify({'error': '送信者メールアドレスは必須です'}), 400
            
        if not data.get('sender_company'):
            return jsonify({'error': '送信者会社名は必須です'}), 400
        
        # 重複チェック
        existing = db.query(Product).filter(Product.name == data['name']).first()
        if existing:
            return jsonify({'error': '同じ名前の案件が既に存在します'}), 400
        
        # 新規作成
        product = Product(
            name=data['name'],
            description=data.get('description'),
            message_template=data.get('message_template'),
            # 基本情報（後方互換性のため既存フィールドも保持）
            sender_name=data.get('sender_name'),
            sender_last_name=data.get('sender_last_name'),
            sender_first_name=data.get('sender_first_name'),
            sender_last_name_kana=data.get('sender_last_name_kana'),
            sender_first_name_kana=data.get('sender_first_name_kana'),
            sender_gender=data.get('sender_gender'),
            # 会社情報
            sender_company=data.get('sender_company'),
            sender_company_kana=data.get('sender_company_kana'),
            sender_company_url=data.get('sender_company_url'),
            sender_department=data.get('sender_department'),
            sender_position=data.get('sender_position'),
            sender_rep_name=data.get('sender_rep_name'),
            sender_rep_name_kana=data.get('sender_rep_name_kana'),
            # 連絡先
            sender_phone=data.get('sender_phone'),
            sender_phone_1=data.get('sender_phone_1'),
            sender_phone_2=data.get('sender_phone_2'),
            sender_phone_3=data.get('sender_phone_3'),
            sender_mobile_1=data.get('sender_mobile_1'),
            sender_mobile_2=data.get('sender_mobile_2'),
            sender_mobile_3=data.get('sender_mobile_3'),
            sender_fax_1=data.get('sender_fax_1'),
            sender_fax_2=data.get('sender_fax_2'),
            sender_fax_3=data.get('sender_fax_3'),
            # メール
            sender_email=data.get('sender_email'),
            sender_email_company=data.get('sender_email_company'),
            sender_email_personal=data.get('sender_email_personal'),
            # 住所
            sender_zipcode_1=data.get('sender_zipcode_1'),
            sender_zipcode_2=data.get('sender_zipcode_2'),
            sender_prefecture=data.get('sender_prefecture'),
            sender_city=data.get('sender_city'),
            sender_address=data.get('sender_address'),
            # お問い合わせ
            sender_inquiry_title=data.get('sender_inquiry_title'),
            sender_inquiry_detail=data.get('sender_inquiry_detail')
        )
        
        db.add(product)
        db.commit()
        db.refresh(product)
        
        return jsonify({
            'success': True,
            'product': product.to_dict(),
            'message': '案件を登録しました'
        }), 201
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@simple_bp.route('/projects', methods=['GET'])
def get_projects():
    """プロジェクト一覧を取得（互換性のため残す）"""
    db = get_db_session()
    try:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        return jsonify([project.to_dict() for project in projects])
    finally:
        db.close()


@simple_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """特定のタスクを取得"""
    db = get_db_session()
    try:
        task = db.query(Task).options(
            joinedload(Task.company),
            joinedload(Task.product)
        ).filter(Task.id == task_id).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify(task.to_dict())
    finally:
        db.close()


@simple_bp.route('/tasks/<int:task_id>/execute', methods=['POST'])
def execute_task(task_id):
    """タスクを実行（Playwright自動入力 + VNC表示 + スクリーンショット）"""
    db = get_db_session()
    try:
        task = db.query(Task).options(
            joinedload(Task.company),
            joinedload(Task.product)
        ).filter(Task.id == task_id).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.status not in ['pending', 'failed']:
            return jsonify({'error': 'Task cannot be executed in current status'}), 400
        
        # ステータスを処理中に変更
        task.status = 'in_progress'
        db.commit()
        
        # VNC環境でPlaywright自動入力を実行
        from backend.services.automation_service import FormAutomationService
        
        try:
            # VNC統合：headless=False, DISPLAY=:99
            automation = FormAutomationService(headless=False, display=':99')
            automation.start()
            
            # フォームデータ準備
            message_data = task.form_data
            print(f"\n🔍 タスクID {task_id} のフォームデータ:")
            print(f"   form_data型: {type(message_data)}")
            print(f"   form_data内容: {message_data}")
            print(f"   company: '{message_data.get('company', 'N/A')}'")
            print(f"   name: '{message_data.get('name', 'N/A')}'")
            print(f"   email: '{message_data.get('email', 'N/A')}'")
            print(f"   message長: {len(message_data.get('message', ''))}文字\n")
            
            # フォーム自動入力実行
            result = automation.fill_contact_form(
                form_url=task.company.form_url,
                message_data=message_data,
                wait_for_captcha=True
            )
            
            automation.stop()
            
            # 結果を保存
            if result.get('screenshot_path'):
                task.screenshot_path = result['screenshot_path']
            
            # 送信完了を検出した場合はcompletedに、そうでなければin_progressのまま
            if result.get('submitted'):
                task.status = 'completed'
                task.submitted = True
                task.completed_at = datetime.utcnow()
            else:
                task.status = 'in_progress'  # reCAPTCHA・送信確認待ち
            
            db.commit()
            
            return jsonify({
                'success': True,
                'message': 'Automation completed. Check VNC viewer.',
                'submitted': result.get('submitted', False),
                'screenshot_path': result.get('screenshot_path'),
                'vnc_url': 'http://153.126.154.158:6080/vnc.html'
            })
            
        except Exception as e:
            task.status = 'failed'
            db.commit()
            return jsonify({'error': f'Automation failed: {str(e)}'}), 500
            
    finally:
        db.close()


@simple_bp.route('/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """タスクを完了済みにする（手動送信後）"""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.status != 'in_progress':
            return jsonify({'error': 'Task must be in progress to complete'}), 400
        
        task.status = 'completed'
        task.submitted = True
        task.completed_at = datetime.utcnow()
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Task marked as completed'
        })
        
    finally:
        db.close()


@simple_bp.route('/tasks/<int:task_id>/skip', methods=['POST'])
def skip_task(task_id):
    """タスクをスキップ（pendingに戻す）"""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task.status != 'in_progress':
            return jsonify({'error': 'Task must be in progress to skip'}), 400
        
        # pendingに戻す
        task.status = 'pending'
        task.submitted = False
        task.completed_at = None
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Task skipped and reset to pending'
        })
        
    finally:
        db.close()


async def run_automation(task):
    """
    Playwright自動化実行
    1. フォームページを開く
    2. フォーム要素を検出
    3. データを入力
    4. スクリーンショットを撮影
    5. ブラウザを閉じる
    """
    # スクリーンショット保存ディレクトリ
    screenshots_dir = '/workspaces/ai-auto-form/screenshots'
    os.makedirs(screenshots_dir, exist_ok=True)
    
    screenshot_filename = f'task_{task.id}_{int(datetime.utcnow().timestamp())}.png'
    screenshot_path = os.path.join(screenshots_dir, screenshot_filename)
    
    async with async_playwright() as p:
        # Chromiumを使用（headlessモード）
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        try:
            # フォームページを開く
            await page.goto(task.company.form_url, wait_until='networkidle', timeout=30000)
            
            # フォームデータを入力
            form_data = task.form_data
            
            # 一般的なフォーム要素を検出して入力
            # name フィールド
            if 'name' in form_data:
                await fill_field(page, ['input[name*="name"]', 'input[id*="name"]', 'input[placeholder*="名前"]'], form_data['name'])
            
            # email フィールド
            if 'email' in form_data:
                await fill_field(page, ['input[type="email"]', 'input[name*="email"]', 'input[name*="mail"]'], form_data['email'])
            
            # company フィールド
            if 'company' in form_data:
                await fill_field(page, ['input[name*="company"]', 'input[name*="kaisya"]', 'input[placeholder*="会社"]'], form_data['company'])
            
            # phone フィールド
            if 'phone' in form_data:
                await fill_field(page, ['input[type="tel"]', 'input[name*="tel"]', 'input[name*="phone"]'], form_data['phone'])
            
            # message フィールド
            if 'message' in form_data:
                await fill_field(page, ['textarea[name*="message"]', 'textarea[name*="inquiry"]', 'textarea[placeholder*="お問い合わせ"]'], form_data['message'])
            
            # 少し待機（入力完了を確認）
            await page.wait_for_timeout(1000)
            
            # スクリーンショット撮影
            await page.screenshot(path=screenshot_path, full_page=True)
            
            return {
                'success': True,
                'screenshot_path': f'/screenshots/{screenshot_filename}'
            }
            
        finally:
            await browser.close()


async def fill_field(page, selectors, value):
    """
    フィールドに値を入力（複数のセレクタを試行）
    """
    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                await element.fill(value)
                return True
        except Exception:
            continue
    return False


@simple_bp.route('/tasks/reset', methods=['POST'])
def reset_tasks():
    """全タスクを未処理状態にリセット"""
    db = get_db_session()
    try:
        updated_count = db.query(Task).filter(
            Task.status.in_(['in_progress', 'completed', 'failed'])
        ).update({
            'status': 'pending',
            'screenshot_path': None,
            'submitted': False,
            'completed_at': None
        }, synchronize_session=False)
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'{updated_count}件のタスクを未処理にリセットしました',
            'reset_count': updated_count
        })
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@simple_bp.route('/vnc/send-data', methods=['POST'])
def send_to_vnc():
    """VNC内のブラウザに直接データを送信（クリップボード経由）"""
    data = request.get_json()
    
    if not data or 'text' not in data:
        return jsonify({'error': 'text field is required'}), 400
    
    text_to_send = data['text']
    
    try:
        # VNC内のクリップボードに書き込み（xsel/xclipコマンド使用）
        import subprocess
        import os
        
        # デバッグログ
        print(f"🔍 [VNC Send] テキスト長: {len(text_to_send)}")
        print(f"🔍 [VNC Send] 先頭100文字: {text_to_send[:100]}")
        
        # DISPLAY環境変数を設定
        env = os.environ.copy()
        env['DISPLAY'] = ':99'
        
        # xselコマンドでクリップボードに書き込み
        process = subprocess.Popen(
            ['xsel', '-b', '-i'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = process.communicate(input=text_to_send.encode('utf-8'))
        
        # デバッグログ
        print(f"🔍 [xsel] Return code: {process.returncode}")
        if stdout:
            print(f"🔍 [xsel] stdout: {stdout.decode('utf-8')}")
        if stderr:
            print(f"🔍 [xsel] stderr: {stderr.decode('utf-8')}")
        
        if process.returncode == 0:
            print(f"✅ [VNC Send] クリップボードに書き込み成功")
            return jsonify({
                'success': True,
                'message': f'Sent {len(text_to_send)} characters to VNC clipboard',
                'hint': 'VNC画面でCtrl+Vでペーストしてください'
            })
        else:
            raise Exception(f'xsel command failed with code {process.returncode}: {stderr.decode("utf-8") if stderr else "no error message"}')
        
    except Exception as e:
        print(f"❌ [VNC Send] エラー: {str(e)}")
        return jsonify({'error': f'Failed to send to VNC: {str(e)}'}), 500


@simple_bp.route('/vnc/auto-paste', methods=['POST'])
def auto_paste_to_vnc():
    """VNC内のフォーカス中フィールドに自動ペースト"""
    data = request.get_json()
    
    if not data or 'text' not in data:
        return jsonify({'error': 'text field is required'}), 400
    
    text_to_send = data['text']
    
    try:
        import subprocess
        import os
        
        print(f"🤖 [Auto Paste] テキスト長: {len(text_to_send)}")
        
        # DISPLAY環境変数を設定
        env = os.environ.copy()
        env['DISPLAY'] = ':99'
        
        # 1. クリップボードに書き込み
        process = subprocess.Popen(
            ['xsel', '-b', '-i'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = process.communicate(input=text_to_send.encode('utf-8'))
        
        if process.returncode != 0:
            raise Exception(f'xsel failed: {stderr.decode("utf-8") if stderr else "unknown error"}')
        
        # 2. xdotoolでCtrl+A（全選択）→ Ctrl+V（ペースト）を送信
        # 既存の内容を削除して新しい内容に置き換える
        select_all_process = subprocess.run(
            ['xdotool', 'key', '--delay', '50', 'ctrl+a'],
            env=env,
            capture_output=True,
            text=True
        )
        
        if select_all_process.returncode != 0:
            print(f"⚠️ [Auto Paste] Ctrl+A failed (continuing anyway): {select_all_process.stderr}")
        
        # 3. ペースト
        paste_process = subprocess.run(
            ['xdotool', 'key', '--delay', '100', 'ctrl+v'],
            env=env,
            capture_output=True,
            text=True
        )
        
        if paste_process.returncode != 0:
            raise Exception(f'xdotool failed: {paste_process.stderr}')
        
        print(f"✅ [Auto Paste] 自動ペースト成功（既存内容を置き換え）")
        return jsonify({
            'success': True,
            'message': f'Auto-pasted {len(text_to_send)} characters to focused field (replaced existing content)'
        })
        
    except Exception as e:
        print(f"❌ [Auto Paste] エラー: {str(e)}")
        return jsonify({'error': f'Failed to auto-paste: {str(e)}'}), 500


@simple_bp.route('/tasks/generate', methods=['POST'])
def generate_tasks():
    """
    Phase 2-A: 案件×企業リストから大量タスク生成（シンプル設計）
    
    Request Body:
    {
        "product_id": 1,
        "company_ids": [11, 12, 13, ...] or "all",
        "use_ai": true
    }
    """
    db = get_db_session()
    
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        company_ids = data.get('company_ids', 'all')
        use_ai = data.get('use_ai', False)
        
        if not product_id:
            return jsonify({'error': 'product_id is required'}), 400
        
        # 案件取得
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return jsonify({'error': f'Product {product_id} not found'}), 404
        
        # 企業リスト取得
        if company_ids == 'all':
            companies = db.query(Company).all()
        else:
            companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
        
        if not companies:
            return jsonify({'error': 'No companies found'}), 404
        
        # AI文面カスタマイズ準備
        gemini_service = None
        if use_ai:
            try:
                from backend.services.gemini_service import GeminiService
                gemini_service = GeminiService()
                print(f"✅ Gemini AI enabled (model: gemini-2.5-flash)")
            except Exception as e:
                print(f"⚠️ Gemini AI initialization failed: {e}")
                use_ai = False
        
        # タスク生成（重複チェック付き）
        tasks_created = 0
        tasks_skipped = 0
        
        for company in companies:
            # 重複チェック：同じ企業ID × 案件IDの組み合わせが存在するか
            existing_task = db.query(Task).filter(
                Task.company_id == company.id,
                Task.product_id == product_id
            ).first()
            
            if existing_task:
                print(f"⚠️ Task already exists for company {company.name} (ID: {company.id}) × product {product_id}")
                tasks_skipped += 1
                continue
            
            # AI文面カスタマイズ
            if use_ai and gemini_service:
                try:
                    company_info = {
                        'name': company.name,
                        'industry': company.industry,
                        'description': company.description,
                        'employee_count': company.employee_count,
                        'established_year': company.established_year
                    }
                    product_info = {
                        'name': product.name,
                        'message_template': product.message_template or f"貴社の{product.name}についてご提案させていただきます。"
                    }
                    
                    custom_message = gemini_service.generate_custom_message_simple(
                        company_info, product_info
                    )
                    print(f"✅ AI message generated for {company.name} ({len(custom_message)} chars)")
                except Exception as e:
                    print(f"⚠️ AI generation failed for {company.name}: {e}")
                    custom_message = product.message_template or f"貴社の{product.name}についてご提案させていただきます。"
            else:
                # AIを使わない場合は、テンプレートをそのまま使用
                custom_message = product.message_template or f"貴社の{product.name}についてご提案させていただきます。"
            
            # form_data生成（分割/結合対応）
            form_data = prepare_form_data_from_product(product)
            form_data['message'] = custom_message  # メッセージは別途追加
            
            # タスク作成
            task = Task(
                company_id=company.id,
                product_id=product_id,
                status='pending',
                form_data=form_data
            )
            db.add(task)
            tasks_created += 1
        
        db.commit()
        
        print(f"✅ Generated {tasks_created} tasks for product '{product.name}' (skipped {tasks_skipped} duplicates)")
        
        return jsonify({
            'success': True,
            'tasks_created': tasks_created,
            'tasks_skipped': tasks_skipped,
            'product_id': product_id,
            'product_name': product.name,
            'ai_enabled': use_ai,
            'companies_count': len(companies)
        })
        
    except Exception as e:
        db.rollback()
        print(f"❌ Task generation error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@simple_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """案件を更新"""
    db = get_db_session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        data = request.get_json()
        
        # 名前の重複チェック（自分以外）
        if 'name' in data and data['name'] != product.name:
            existing = db.query(Product).filter(
                Product.name == data['name'],
                Product.id != product_id
            ).first()
            if existing:
                return jsonify({'error': '同じ名前の案件が既に存在します'}), 400
        
        # 更新
        if 'name' in data:
            product.name = data['name']
        if 'description' in data:
            product.description = data['description']
        if 'message_template' in data:
            product.message_template = data['message_template']
        if 'industry' in data:
            product.industry = data['industry']
        
        # 送信者情報の更新（すべてのフィールドに対応）
        if 'sender_name' in data:
            product.sender_name = data['sender_name']
        if 'sender_last_name' in data:
            product.sender_last_name = data['sender_last_name']
        if 'sender_first_name' in data:
            product.sender_first_name = data['sender_first_name']
        if 'sender_last_name_kana' in data:
            product.sender_last_name_kana = data['sender_last_name_kana']
        if 'sender_first_name_kana' in data:
            product.sender_first_name_kana = data['sender_first_name_kana']
        if 'sender_gender' in data:
            product.sender_gender = data['sender_gender']
        if 'sender_company' in data:
            product.sender_company = data['sender_company']
        if 'sender_company_kana' in data:
            product.sender_company_kana = data['sender_company_kana']
        if 'sender_company_url' in data:
            product.sender_company_url = data['sender_company_url']
        if 'sender_department' in data:
            product.sender_department = data['sender_department']
        if 'sender_position' in data:
            product.sender_position = data['sender_position']
        if 'sender_rep_name' in data:
            product.sender_rep_name = data['sender_rep_name']
        if 'sender_rep_name_kana' in data:
            product.sender_rep_name_kana = data['sender_rep_name_kana']
        if 'sender_phone' in data:
            product.sender_phone = data['sender_phone']
        if 'sender_phone_1' in data:
            product.sender_phone_1 = data['sender_phone_1']
        if 'sender_phone_2' in data:
            product.sender_phone_2 = data['sender_phone_2']
        if 'sender_phone_3' in data:
            product.sender_phone_3 = data['sender_phone_3']
        if 'sender_mobile_1' in data:
            product.sender_mobile_1 = data['sender_mobile_1']
        if 'sender_mobile_2' in data:
            product.sender_mobile_2 = data['sender_mobile_2']
        if 'sender_mobile_3' in data:
            product.sender_mobile_3 = data['sender_mobile_3']
        if 'sender_fax_1' in data:
            product.sender_fax_1 = data['sender_fax_1']
        if 'sender_fax_2' in data:
            product.sender_fax_2 = data['sender_fax_2']
        if 'sender_fax_3' in data:
            product.sender_fax_3 = data['sender_fax_3']
        if 'sender_email' in data:
            product.sender_email = data['sender_email']
        if 'sender_email_company' in data:
            product.sender_email_company = data['sender_email_company']
        if 'sender_email_personal' in data:
            product.sender_email_personal = data['sender_email_personal']
        if 'sender_zipcode_1' in data:
            product.sender_zipcode_1 = data['sender_zipcode_1']
        if 'sender_zipcode_2' in data:
            product.sender_zipcode_2 = data['sender_zipcode_2']
        if 'sender_prefecture' in data:
            product.sender_prefecture = data['sender_prefecture']
        if 'sender_city' in data:
            product.sender_city = data['sender_city']
        if 'sender_address' in data:
            product.sender_address = data['sender_address']
        if 'sender_inquiry_title' in data:
            product.sender_inquiry_title = data['sender_inquiry_title']
        if 'sender_inquiry_detail' in data:
            product.sender_inquiry_detail = data['sender_inquiry_detail']
        
        db.commit()
        
        return jsonify({
            'success': True,
            'product': product.to_dict(),
            'message': '案件を更新しました'
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@simple_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """タスクのメッセージを更新"""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        data = request.get_json()
        
        if 'message' in data:
            # form_dataを更新
            if task.form_data is None:
                task.form_data = {}
            task.form_data['message'] = data['message']
            # SQLAlchemyにJSON更新を通知
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(task, 'form_data')
        
        db.commit()
        
        return jsonify({
            'success': True,
            'task': task.to_dict(),
            'message': 'タスクを更新しました'
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@simple_bp.route('/tasks/<int:task_id>/regenerate-message', methods=['POST'])
def regenerate_task_message(task_id):
    """タスクのメッセージをAIで再生成"""
    db = get_db_session()
    try:
        task = db.query(Task).options(
            joinedload(Task.company),
            joinedload(Task.product)
        ).filter(Task.id == task_id).first()
        
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if not task.company or not task.product:
            return jsonify({'error': 'タスクに企業または案件情報がありません'}), 400
        
        # Gemini APIでメッセージ生成
        gemini = GeminiService()
        
        company_info = {
            'name': task.company.name,
            'industry': task.company.industry,
            'description': task.company.description,
            'employee_count': task.company.employee_count,
            'established_year': task.company.established_year
        }
        
        product_info = {
            'name': task.product.name,
            'description': task.product.description,
            'message_template': task.product.message_template
        }
        
        new_message = gemini.generate_custom_message_simple(company_info, product_info)
        
        # タスク更新
        if task.form_data is None:
            task.form_data = {}
        task.form_data['message'] = new_message
        
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(task, 'form_data')
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': new_message,
            'task': task.to_dict(),
            'info': 'AIでメッセージを再生成しました'
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@simple_bp.route('/migrate/add-sender-info', methods=['POST'])
def migrate_add_sender_info():
    """マイグレーション: simple_productsに送信者情報カラム追加"""
    db = get_db_session()
    try:
        from sqlalchemy import text
        
        print("📝 マイグレーション開始")
        
        # カラム追加
        db.execute(text("""
            ALTER TABLE simple_products 
            ADD COLUMN IF NOT EXISTS sender_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS sender_email VARCHAR(200),
            ADD COLUMN IF NOT EXISTS sender_company VARCHAR(200),
            ADD COLUMN IF NOT EXISTS sender_phone VARCHAR(50)
        """))
        
        # デフォルト値設定
        result = db.execute(text("""
            UPDATE simple_products 
            SET 
                sender_name = COALESCE(sender_name, '山田太郎'),
                sender_email = COALESCE(sender_email, 'yamada@example.com'),
                sender_company = COALESCE(sender_company, '株式会社テスト'),
                sender_phone = COALESCE(sender_phone, '03-1234-5678')
        """))
        
        db.commit()
        
        # 確認
        result = db.execute(text("""
            SELECT id, name, sender_name, sender_email, sender_company, sender_phone 
            FROM simple_products
        """))
        
        products = [{'id': r[0], 'name': r[1], 'sender_name': r[2], 'sender_email': r[3], 'sender_company': r[4], 'sender_phone': r[5]} for r in result]
        
        return jsonify({'success': True, 'message': 'マイグレーション完了', 'products': products})
        
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@simple_bp.route('/migrate/add-extended-sender-info', methods=['POST'])
def migrate_add_extended_sender_info():
    """マイグレーション: simple_productsに拡張送信者情報カラム追加"""
    db = get_db_session()
    try:
        print("📝 拡張送信者情報マイグレーション開始")
        
        # 基本情報カラム追加
        db.execute(text("""
            ALTER TABLE simple_products 
            ADD COLUMN IF NOT EXISTS sender_last_name VARCHAR(50),
            ADD COLUMN IF NOT EXISTS sender_first_name VARCHAR(50),
            ADD COLUMN IF NOT EXISTS sender_last_name_kana VARCHAR(50),
            ADD COLUMN IF NOT EXISTS sender_first_name_kana VARCHAR(50),
            ADD COLUMN IF NOT EXISTS sender_gender VARCHAR(10)
        """))
        print("✅ 基本情報カラム追加完了")
        
        # 会社情報カラム追加
        db.execute(text("""
            ALTER TABLE simple_products 
            ADD COLUMN IF NOT EXISTS sender_company_kana VARCHAR(200),
            ADD COLUMN IF NOT EXISTS sender_company_url VARCHAR(500),
            ADD COLUMN IF NOT EXISTS sender_department VARCHAR(100),
            ADD COLUMN IF NOT EXISTS sender_position VARCHAR(100),
            ADD COLUMN IF NOT EXISTS sender_rep_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS sender_rep_name_kana VARCHAR(100)
        """))
        print("✅ 会社情報カラム追加完了")
        
        # 連絡先カラム追加
        db.execute(text("""
            ALTER TABLE simple_products 
            ADD COLUMN IF NOT EXISTS sender_phone_1 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_phone_2 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_phone_3 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_mobile_1 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_mobile_2 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_mobile_3 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_fax_1 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_fax_2 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_fax_3 VARCHAR(10)
        """))
        print("✅ 連絡先カラム追加完了")
        
        # メールカラム追加
        db.execute(text("""
            ALTER TABLE simple_products 
            ADD COLUMN IF NOT EXISTS sender_email_company VARCHAR(200),
            ADD COLUMN IF NOT EXISTS sender_email_personal VARCHAR(200)
        """))
        print("✅ メールカラム追加完了")
        
        # 住所カラム追加
        db.execute(text("""
            ALTER TABLE simple_products 
            ADD COLUMN IF NOT EXISTS sender_zipcode_1 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_zipcode_2 VARCHAR(10),
            ADD COLUMN IF NOT EXISTS sender_prefecture VARCHAR(50),
            ADD COLUMN IF NOT EXISTS sender_city VARCHAR(100),
            ADD COLUMN IF NOT EXISTS sender_address VARCHAR(500)
        """))
        print("✅ 住所カラム追加完了")
        
        # お問い合わせカラム追加
        db.execute(text("""
            ALTER TABLE simple_products 
            ADD COLUMN IF NOT EXISTS sender_inquiry_title VARCHAR(500),
            ADD COLUMN IF NOT EXISTS sender_inquiry_detail TEXT
        """))
        print("✅ お問い合わせカラム追加完了")
        
        db.commit()
        
        # 確認
        result = db.execute(text("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'simple_products' 
              AND column_name LIKE 'sender_%'
            ORDER BY ordinal_position
        """))
        
        columns = [{'column': r[0], 'type': r[1], 'max_length': r[2]} for r in result]
        
        return jsonify({
            'success': True, 
            'message': '拡張送信者情報マイグレーション完了',
            'columns_added': len(columns),
            'columns': columns
        })
        
    except Exception as e:
        db.rollback()
        print(f"❌ マイグレーションエラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
