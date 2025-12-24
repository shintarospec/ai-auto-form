"""
AI AutoForm - Playwright Automation Service
フォーム自動入力のPoC実装
"""

from playwright.sync_api import sync_playwright, Page, Browser
from typing import Dict, Optional
import time

class FormAutomationService:
    """フォーム自動入力サービス"""
    
    def __init__(self, headless: bool = False, display: Optional[str] = None):
        """
        初期化
        
        Args:
            headless: ヘッドレスモードで実行するか（False=GUI表示）
            display: DISPLAY環境変数（VNC使用時は ":1"）
        """
        self.headless = headless
        self.display = display
        self.playwright = None
        self.browser = None
    
    def start(self):
        """ブラウザ起動"""
        # VNCディスプレイを設定
        import os
        if self.display:
            os.environ['DISPLAY'] = self.display
        
        self.playwright = sync_playwright().start()
        # VPS環境ではChromiumを優先（VNC対応）
        try:
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu'  # VNC環境向け
                ]
            )
            print(f"✅ ブラウザ(Chromium)を起動しました (headless={self.headless}, DISPLAY={os.environ.get('DISPLAY', 'default')})")
        except Exception as e:
            print(f"⚠️ Chromium起動失敗、Webkitで再試行: {e}")
            # フォールバックでWebkitを試行
            self.browser = self.playwright.webkit.launch(
                headless=self.headless
            )
            print(f"✅ ブラウザ(Webkit)を起動しました (headless={self.headless}, DISPLAY={os.environ.get('DISPLAY', 'default')})")
    
    def stop(self):
        """ブラウザ終了"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        print("✅ ブラウザを終了しました")
    
    def fill_contact_form(
        self,
        form_url: str,
        message_data: Dict,
        wait_for_captcha: bool = True
    ) -> Dict:
        """
        問い合わせフォームに自動入力
        
        Args:
            form_url: フォームURL
            message_data: 入力データ
                - sender_name: 送信者名
                - sender_email: メールアドレス
                - sender_company: 会社名
                - sender_phone: 電話番号（オプション）
                - message: メッセージ本文
            wait_for_captcha: reCAPTCHA待機するか
        
        Returns:
            結果
        """
        if not self.browser:
            raise RuntimeError("ブラウザが起動していません。start()を呼んでください")
        
        # Codespaces環境でlocalhost URLを変換
        import os
        codespace_name = os.environ.get('CODESPACE_NAME')
        if codespace_name and 'localhost:8000' in form_url:
            # localhost:8000 を Codespaces公開URLに変換
            form_url = form_url.replace('http://localhost:8000', f'https://{codespace_name}-8000.app.github.dev')
            print(f"🔄 URL変換: Codespaces公開URLを使用します")
        
        # ブラウザウィンドウをフルスクリーン表示（1920x1080）
        page = self.browser.new_page(viewport={'width': 1920, 'height': 1080})
        
        # コンソールログをキャプチャ
        page.on("console", lambda msg: print(f"🖥️  Browser console: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"❌ Page error: {exc}"))
        
        try:
            # ページを開く
            print(f"📄 フォームページを開いています: {form_url}")
            page.goto(form_url, wait_until='networkidle', timeout=30000)
            time.sleep(2)
            
            # ページにフォームデータパネルを埋め込む（カスタムコンテキストメニュー付き）
            print("📋 ページにフォームデータパネルを埋め込んでいます...")
            
            try:
                result = page.evaluate("""
                    (formData) => {
                        console.log('🔹 Starting data panel injection', formData);
                        window.formData = formData;
                        
                        // テスト：パネルが既に存在するか確認
                        if (document.getElementById('form-data-panel')) {
                            console.log('⚠️  Panel already exists, removing...');
                            document.getElementById('form-data-panel').remove();
                        }
                        if (document.getElementById('custom-context-menu')) {
                            console.log('⚠️  Menu already exists, removing...');
                            document.getElementById('custom-context-menu').remove();
                        }
                        
                        return { success: true, dataKeys: Object.keys(formData) };
                    }
                """, message_data)
                print(f"✅ 初期化成功: {result}")
            except Exception as e:
                print(f"❌ JavaScriptエラー（初期化）: {e}")
                raise
            
            # メインのデータパネル＆メニュー埋め込み
            print("📋 データパネルとカスタムメニューを作成中...")
            
            try:
                result = page.evaluate("""
                    (formData) => {
                        console.log('🔹 Creating panel and menu with data:', formData);
                    window.formData = formData;
                    
                    // データパネルを作成
                    const panel = document.createElement('div');
                    panel.id = 'form-data-panel';
                    panel.style.cssText = 'position:fixed;top:10px;right:10px;background:rgba(33,150,243,0.95);color:white;padding:15px;border-radius:8px;font-family:sans-serif;font-size:13px;z-index:999999;max-width:300px;max-height:600px;overflow-y:auto;box-shadow:0 4px 12px rgba(0,0,0,0.3)';
                    
                    // タイトルと使い方説明
                    const header = document.createElement('div');
                    header.style.cssText = 'margin-bottom:12px;padding-bottom:12px;border-bottom:2px solid rgba(255,255,255,0.3)';
                    
                    const title = document.createElement('div');
                    title.textContent = '📋 フォーム入力データ';
                    title.style.cssText = 'font-weight:bold;font-size:14px;margin-bottom:8px';
                    header.appendChild(title);
                    
                    const instruction = document.createElement('div');
                    instruction.style.cssText = 'font-size:11px;line-height:1.5;opacity:0.9;background:rgba(255,255,255,0.1);padding:8px;border-radius:4px';
                    instruction.innerHTML = '✅ <strong>使い方</strong><br>① 下のデータをクリック（コピー）<br>② VNC画面の入力欄を右クリック<br>③ 「Paste」を選択して貼り付け';
                    header.appendChild(instruction);
                    
                    panel.appendChild(header);
                    
                    // 各データフィールド
                    Object.keys(window.formData).forEach(function(key) {
                        const value = window.formData[key];
                        const item = document.createElement('div');
                        item.className = 'data-item';
                        item.style.cssText = 'margin:8px 0;padding:8px;background:rgba(255,255,255,0.15);border-radius:4px;cursor:pointer;transition:background 0.2s;user-select:none';
                        
                        item.onmouseover = function() { this.style.background = 'rgba(255,255,255,0.25)'; };
                        item.onmouseout = function() { this.style.background = 'rgba(255,255,255,0.15)'; };
                        
                        // 左クリック: クリップボードにコピー
                        item.onclick = function() {
                            navigator.clipboard.writeText(value);
                            this.style.background = 'rgba(76,175,80,0.8)';
                            const self = this;
                            setTimeout(function() { self.style.background = 'rgba(255,255,255,0.15)'; }, 1000);
                        };
                        
                        const label = document.createElement('div');
                        label.textContent = key.replace(/_/g, ' ');
                        label.style.cssText = 'font-size:11px;opacity:0.8;margin-bottom:4px';
                        item.appendChild(label);
                        
                        const val = document.createElement('div');
                        val.textContent = String(value);
                        val.style.cssText = 'word-break:break-all;font-size:12px';
                        item.appendChild(val);
                        
                        panel.appendChild(item);
                    });
                    
                    const note = document.createElement('div');
                    note.textContent = '💡 クリックでコピー＆自動入力';
                    note.style.cssText = 'margin-top:10px;font-size:11px;opacity:0.7;text-align:center';
                    panel.appendChild(note);
                    
                    document.body.appendChild(panel);
                    
                    console.log('✅ Data panel with auto-fill loaded', formData);
                    return { 
                        success: true, 
                        panelExists: !!document.getElementById('form-data-panel')
                    };
                }
            """, message_data)
                print(f"✅ データパネル＆メニュー作成成功: {result}")
            except Exception as e:
                print(f"❌ JavaScriptエラー（パネル作成）: {e}")
                raise
            
            # フォームフィールドの検出と入力
            fields_filled = []
            
            # 名前フィールド（sender_name または name キー対応）
            name_value = message_data.get('sender_name') or message_data.get('name', '')
            name_selectors = [
                'input[name="name"]',
                'input[id="name"]',
                'input[name*="name"]',
                'input[id*="name"]',
                'input[placeholder*="名前"]',
                'input[placeholder*="お名前"]',
            ]
            if name_value and self._fill_field(page, name_selectors, name_value):
                fields_filled.append('name')
            
            # メールフィールド（sender_email または email キー対応）
            email_value = message_data.get('sender_email') or message_data.get('email', '')
            email_selectors = [
                'input[name="email"]',
                'input[id="email"]',
                'input[type="email"]',
                'input[name*="email"]',
                'input[name*="mail"]',
                'input[id*="email"]',
            ]
            if email_value and self._fill_field(page, email_selectors, email_value):
                fields_filled.append('email')
            
            # 会社名フィールド（sender_company または company キー対応）
            company_value = message_data.get('sender_company') or message_data.get('company', '')
            company_selectors = [
                'input[name="company"]',
                'input[id="company"]',
                'input[name*="company"]',
                'input[name*="kaisya"]',
                'input[id*="company"]',
                'input[placeholder*="会社"]',
                'input[placeholder*="企業"]',
            ]
            if company_value and self._fill_field(page, company_selectors, company_value):
                fields_filled.append('company')
            
            # 電話番号フィールド（sender_phone または phone キー対応）
            phone_value = message_data.get('sender_phone') or message_data.get('phone', '')
            phone_selectors = [
                'input[name="phone"]',
                'input[id="phone"]',
                'input[type="tel"]',
                'input[name*="phone"]',
                'input[name*="tel"]',
                'input[id*="phone"]',
            ]
            if phone_value:
                if self._fill_field(page, phone_selectors, phone_value):
                    fields_filled.append('phone')
            
            # メッセージフィールド
            message_selectors = [
                'textarea',
                'textarea[name*="message"]',
                'textarea[name*="inquiry"]',
                'textarea[id*="message"]',
            ]
            if self._fill_field(page, message_selectors, message_data.get('message', '')):
                fields_filled.append('message')
            
            print(f"✅ フィールドに入力しました: {', '.join(fields_filled)}")
            
            # reCAPTCHAチェック
            has_recaptcha = self._check_recaptcha(page)
            
            if has_recaptcha and wait_for_captcha:
                print("⚠️  reCAPTCHAを検出しました")
                print("   作業者が手動で解決してください...")
                # ここでブラウザを作業者に渡す
                # 実際の実装では、WebSocketで作業者画面に通知
            
            # 作業者が内容を確認して送信ボタンを押すまで待機
            print("👀 作業者による確認待ち...")
            print("   フォーム内容を確認して、送信ボタンを押してください")
            print(f"   {60}秒後に自動的にブラウザを閉じます")
            
            # 初期状態を記録
            initial_url = page.url
            submitted = False
            wait_time = 60
            
            # フォームの初期値を記録（送信後はリセットされる）
            try:
                initial_name = page.locator('input[name="name"]').input_value()
            except:
                initial_name = None
            
            # 1秒ごとにチェック（60回）
            for i in range(wait_time):
                time.sleep(1)
                
                # ブラウザが閉じられたかチェック
                if page.is_closed():
                    print("⚠️  作業者がブラウザを閉じました")
                    break
                
                # フォームがリセットされたかチェック（最も確実な方法）
                try:
                    current_name = page.locator('input[name="name"]').input_value()
                    if initial_name and current_name == '':
                        submitted = True
                        print(f"✅ 送信完了を検出しました（フォームリセット）！ ({i+1}秒後)")
                        time.sleep(2)
                        break
                except:
                    pass
                
                # 成功メッセージが表示されたかチェック（0.5秒間隔で2回確認）
                try:
                    for selector in ['#result', '#success-message', '.success', '.thank-you']:
                        success_element = page.locator(selector)
                        if success_element.count() > 0:
                            # 要素が存在する場合、visible状態をチェック
                            try:
                                if success_element.is_visible():
                                    submitted = True
                                    print(f"✅ 送信完了を検出しました（成功メッセージ表示: {selector}）！ ({i+1}秒後)")
                                    time.sleep(2)
                                    break
                            except:
                                # hiddenクラスの有無でチェック
                                classes = success_element.get_attribute('class') or ''
                                if 'hidden' not in classes.lower():
                                    submitted = True
                                    print(f"✅ 送信完了を検出しました（成功メッセージ表示: {selector}）！ ({i+1}秒後)")
                                    time.sleep(2)
                                    break
                    if submitted:
                        break
                except Exception as e:
                    pass
                
                # URL変化をチェック
                current_url = page.url
                if current_url != initial_url:
                    if any(keyword in current_url.lower() for keyword in ['thank', 'success', 'confirm', 'complete']):
                        submitted = True
                        print(f"✅ 送信完了を検出しました（URL変化）！ ({i+1}秒後)")
                        print(f"   遷移先URL: {current_url}")
                        time.sleep(2)
                        break
            
            if not submitted:
                print("⚠️  送信完了を検出できませんでした（タイムアウト）")
                print("   作業者が送信ボタンを押さなかった可能性があります")
            
            # スクリーンショットを撮影（送信後の状態）
            screenshot_path = f'/tmp/form_screenshot_{int(time.time())}.png'
            page.screenshot(path=screenshot_path)
            print(f"📸 スクリーンショットを保存: {screenshot_path}")
            
            return {
                'success': True,
                'fields_filled': fields_filled,
                'has_recaptcha': has_recaptcha,
                'screenshot': screenshot_path,
                'submitted': submitted,  # 送信されたかどうか
                'final_url': page.url,  # 最終URL
                'message': f'{len(fields_filled)}個のフィールドに入力完了' + (' → 送信完了' if submitted else ' → 送信未完了')
            }
            
        except Exception as e:
            print(f"❌ エラー: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            # ページを閉じる
            if page:
                page.close()
                print("🔒 ページを閉じました")
    
    def _fill_field(self, page: Page, selectors: list, value: str) -> bool:
        """
        フィールドに値を入力（複数セレクタを試行）
        
        Args:
            page: Playwrightページ
            selectors: セレクタのリスト
            value: 入力値
        
        Returns:
            成功したかどうか
        """
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if element.count() > 0 and element.is_visible():
                    element.fill(value)
                    time.sleep(0.5)  # 自然な入力を模倣
                    return True
            except:
                continue
        return False
    
    def _check_recaptcha(self, page: Page) -> bool:
        """
        reCAPTCHAの存在をチェック
        
        Args:
            page: Playwrightページ
        
        Returns:
            reCAPTCHAが存在するか
        """
        recaptcha_selectors = [
            'iframe[src*="recaptcha"]',
            '.g-recaptcha',
            '#g-recaptcha',
            'div[class*="recaptcha"]'
        ]
        
        for selector in recaptcha_selectors:
            try:
                if page.locator(selector).count() > 0:
                    return True
            except:
                continue
        
        return False
    
    def take_screenshot(self, page: Page, filename: str = 'screenshot.png'):
        """スクリーンショット撮影"""
        page.screenshot(path=filename)
        print(f"📸 スクリーンショットを保存しました: {filename}")


# ========================================
# テスト用スクリプト
# ========================================
if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════╗
    ║   Playwright Form Automation PoC          ║
    ║   AI AutoForm                             ║
    ╚═══════════════════════════════════════════╝
    """)
    
    # テストデータ
    test_data = {
        'sender_name': '山田太郎',
        'sender_email': 'test@example.com',
        'sender_company': 'テスト株式会社',
        'sender_phone': '03-1234-5678',
        'message': '''
突然のご連絡失礼いたします。
テスト株式会社の山田と申します。

貴社のWebサイトを拝見し、事業内容に大変興味を持ちました。
弊社のサービスが貴社のビジネスに貢献できる可能性があると考え、
ご連絡させていただきました。

詳細につきまして、一度お話しさせていただく機会をいただけますと幸いです。
        '''.strip()
    }
    
    # サービス初期化
    service = FormAutomationService(headless=False)
    
    try:
        service.start()
        
        # テスト用URL（実際のフォームURLに置き換えてください）
        test_url = input("\nテストするフォームのURLを入力してください: ").strip()
        
        if test_url:
            print("\n自動入力を開始します...")
            result = service.fill_contact_form(test_url, test_data)
            
            if result['success']:
                print(f"\n✅ {result['message']}")
                if result['has_recaptcha']:
                    print("\nreCAPTCHAを手動で解決してください...")
                    input("Enter キーを押して続行...")
                
                # スクリーンショット
                if 'page' in result:
                    service.take_screenshot(result['page'])
                    result['page'].close()
            else:
                print(f"\n❌ エラー: {result.get('error')}")
        else:
            print("URLが入力されませんでした")
    
    finally:
        service.stop()
