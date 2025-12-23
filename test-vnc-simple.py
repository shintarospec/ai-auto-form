#!/usr/bin/env python3
"""
VNC + Playwright 簡易テスト
"""
import os
os.environ['DISPLAY'] = ':99'

print("=== VNC + Playwright 簡易テスト ===")
print(f"DISPLAY: {os.environ.get('DISPLAY')}")

try:
    from playwright.sync_api import sync_playwright
    print("✅ Playwright import成功")
    
    print("🚀 ブラウザ起動中...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        print("✅ Chromiumブラウザ起動成功")
        
        page = browser.new_page()
        print("📄 新しいページ作成")
        
        page.goto('https://example.com')
        print(f"✅ ページ表示: {page.title()}")
        
        import time
        print("⏳ 5秒待機（VNCで確認してください）")
        time.sleep(5)
        
        browser.close()
        print("✅ ブラウザ終了")
        
    print("\n🎉 テスト完了！")
    
except ImportError as e:
    print(f"❌ Import エラー: {e}")
    print("→ pip install playwright を実行してください")
except Exception as e:
    print(f"❌ エラー発生: {e}")
    import traceback
    traceback.print_exc()
