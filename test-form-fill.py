#!/usr/bin/env python3
"""
フォーム自動入力テスト（VNC統合）
VNC画面でブラウザの動作が見えます
"""

import sys
import os
sys.path.insert(0, '/opt/ai-auto-form')

from backend.services.automation_service import FormAutomationService
import time

def main():
    print("=" * 60)
    print("🚀 フォーム自動入力テスト開始")
    print("=" * 60)
    
    # VNC統合モード（headless=False, display=:99）
    service = FormAutomationService(headless=False, display=":99")
    
    try:
        print("\n📌 ブラウザ起動中...")
        service.start()
        time.sleep(2)
        
        # テストデータ
        test_data = {
            "sender_name": "山田太郎",
            "sender_email": "test@example.com",
            "sender_company": "株式会社テスト",
            "sender_phone": "03-1234-5678",
            "message": "自動入力テストメッセージです。\nVNC画面で入力の様子が見えています。"
        }
        
        print("\n📝 フォーム自動入力実行中...")
        print(f"   URL: http://153.126.154.158:8000/test-contact-form.html")
        print(f"   送信者: {test_data['sender_name']}")
        print(f"   メール: {test_data['sender_email']}")
        
        result = service.fill_contact_form(
            form_url="http://153.126.154.158:8000/test-contact-form.html",
            message_data=test_data,
            wait_for_captcha=False  # テストなのでreCAPTCHA待機なし
        )
        
        print("\n" + "=" * 60)
        print("✅ テスト完了")
        print("=" * 60)
        print(f"結果: {result}")
        
        # ブラウザを10秒間表示したまま保持
        print("\n⏰ 10秒後にブラウザを閉じます...")
        time.sleep(10)
        
    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔚 ブラウザ終了中...")
        service.stop()
        print("✅ テスト完了")

if __name__ == "__main__":
    main()
