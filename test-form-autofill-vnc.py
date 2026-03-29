#!/usr/bin/env python3
"""
VNC経由でフォーム自動入力をテスト
VNCビューアー（http://153.126.154.158:6080/vnc.html）で
ブラウザの動作を確認できます
"""

import os
import sys
sys.path.insert(0, '/opt/ai-auto-form')

from backend.services.automation_service import FormAutomationService
import time

def test_form_autofill():
    """VNC経由でフォーム自動入力をテスト"""
    
    print("=" * 60)
    print("🚀 VNC + Playwright フォーム自動入力テスト")
    print("=" * 60)
    print()
    print("📺 VNCビューアーを開いてください:")
    print("   http://153.126.154.158:6080/vnc.html")
    print()
    print("⏱️  5秒後に開始します...")
    time.sleep(5)
    
    # テストデータ
    test_data = {
        'sender_name': '山田太郎',
        'sender_company': 'テスト株式会社',
        'sender_email': 'yamada@test-company.jp',
        'sender_phone': '03-1234-5678',
        'message': 'VNC経由でのフォーム自動入力テストです。\\nPlaywrightが正常に動作しています。'
    }
    
    form_url = 'http://153.126.154.158:8000/test-contact-form.html'
    
    # FormAutomationServiceを初期化（VNCモード）
    service = FormAutomationService(
        headless=False,  # ブラウザを表示
        display=':99'    # VNCディスプレイ
    )
    
    try:
        print("🌐 ブラウザを起動中...")
        service.start()
        print("✅ ブラウザ起動完了")
        print()
        
        print(f"📄 フォームページを開いています: {form_url}")
        result = service.fill_contact_form(
            form_url=form_url,
            message_data=test_data,
            wait_for_captcha=False  # テストなのでCAPTCHA待機なし
        )
        
        print()
        print("=" * 60)
        print("📊 実行結果:")
        print("=" * 60)
        print(f"ステータス: {result.get('status', 'unknown')}")
        if result.get('message'):
            print(f"メッセージ: {result['message']}")
        if result.get('screenshot'):
            print(f"スクリーンショット: {result['screenshot']}")
        print()
        
        # 結果を確認するため10秒待機
        print("⏱️  結果確認のため10秒待機します...")
        time.sleep(10)
        
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print()
        print("🔒 ブラウザを終了中...")
        service.stop()
        print("✅ テスト完了")

if __name__ == '__main__':
    test_form_autofill()
