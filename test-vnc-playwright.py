#!/usr/bin/env python3
"""
VNC + Playwright 統合テスト
ブラウザがVNC上に表示されることを確認
"""

import sys
import os
sys.path.insert(0, '/opt/ai-auto-form')
os.environ['DISPLAY'] = ':99'

from backend.services.automation_service import FormAutomationService
import time

def test_vnc_browser():
    """VNC上でブラウザを起動してテスト"""
    print("🧪 VNC + Playwright 統合テスト開始")
    print(f"📺 DISPLAY: {os.environ.get('DISPLAY')}")
    
    # automation_service初期化（headless=False, display=:99）
    service = FormAutomationService(headless=False, display=':99')
    
    try:
        # ブラウザ起動
        print("\n🚀 ブラウザを起動します...")
        service.start()
        time.sleep(3)
        
        # シンプルなページを開く
        page = service.browser.new_page()
        print("\n📄 テストページを開きます...")
        page.goto('https://www.example.com')
        time.sleep(5)
        
        # ページタイトルを確認
        title = page.title()
        print(f"\n✅ ページタイトル: {title}")
        
        # スクリーンショット撮影
        screenshot_path = '/opt/ai-auto-form/vnc-test-screenshot.png'
        page.screenshot(path=screenshot_path)
        print(f"\n📸 スクリーンショット保存: {screenshot_path}")
        
        # VNC画面でブラウザが見えるように少し待機
        print("\n⏳ VNC画面を確認できるよう10秒待機します...")
        print("   👀 http://153.126.154.158:6080/vnc.html を確認してください")
        time.sleep(10)
        
        page.close()
        print("\n✅ テスト成功！ブラウザがVNC上に表示されました")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        service.stop()
    
    return True

if __name__ == '__main__':
    success = test_vnc_browser()
    sys.exit(0 if success else 1)
