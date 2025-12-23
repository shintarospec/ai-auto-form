#!/usr/bin/env python3
"""
フォーム自動入力のVNCテスト
test-contact-form.htmlに対して自動入力を実行
"""

import sys
import os
sys.path.insert(0, '/opt/ai-auto-form')
os.environ['DISPLAY'] = ':99'
os.environ['DATABASE_URL'] = 'postgresql://autoform_user:secure_password_123@localhost:5432/ai_autoform'

from backend.services.automation_service import FormAutomationService
from backend.database import get_db
from backend.simple_models import Task
import time

def test_form_autofill():
    """VNC上でフォーム自動入力をテスト"""
    print("🧪 フォーム自動入力 VNCテスト開始")
    print(f"📺 DISPLAY: {os.environ.get('DISPLAY')}")
    
    # データベースからタスクを取得
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(os.environ['DATABASE_URL'])
    Session = sessionmaker(bind=engine)
    db = Session()
    
    task = db.query(Task).filter(Task.id == 1).first()
    
    if not task:
        print("❌ タスクが見つかりません")
        return False
    
    print(f"\n📋 タスク情報:")
    print(f"   会社: {task.company.name}")
    print(f"   商品: {task.product.name}")
    print(f"   ステータス: {task.status}")
    
    # メッセージデータを準備
    message_data = {
        'sender_name': '山田太郎',
        'sender_email': 'yamada@example.com',
        'sender_company': '株式会社サンプル',
        'sender_phone': '03-1234-5678',
        'message': f"{task.company.name}様\n\n{task.product.name}についてお問い合わせさせていただきます。"
    }
    
    # automation_service初期化
    service = FormAutomationService(headless=False, display=':99')
    
    try:
        service.start()
        time.sleep(2)
        
        # VPS上のテストフォームURL
        form_url = 'http://153.126.154.158:8000/test-contact-form.html'
        print(f"\n📄 フォームURL: {form_url}")
        
        # 自動入力実行
        print("\n🤖 自動入力を開始します...")
        result = service.fill_contact_form(
            form_url=form_url,
            message_data=message_data,
            wait_for_captcha=False  # テストなのでCAPTCHA待機なし
        )
        
        print(f"\n✅ 自動入力完了: {result}")
        
        # VNC画面確認のため15秒待機
        print("\n⏳ VNC画面を確認できるよう15秒待機します...")
        print("   👀 http://153.126.154.158:6080/vnc.html を確認してください")
        time.sleep(15)
        
        print("\n✅ テスト成功！フォーム自動入力がVNC上で動作しました")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        service.stop()
        db.close()
    
    return True

if __name__ == '__main__':
    success = test_form_autofill()
    sys.exit(0 if success else 1)
