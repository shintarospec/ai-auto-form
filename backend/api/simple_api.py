"""
Simple API for Phase 1 MVP
シンプルなAPI実装（4つのエンドポイント）
"""

from flask import Blueprint, jsonify, request
from backend.database import get_db_session
from backend.simple_models import Company, Product, Task
from sqlalchemy.orm import joinedload
from datetime import datetime
import os
import asyncio
from playwright.async_api import async_playwright

simple_bp = Blueprint('simple', __name__, url_prefix='/api/simple')


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
