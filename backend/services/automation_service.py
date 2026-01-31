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
        # Mac互換性のためWebkit（Safari）を使用
        try:
            self.browser = self.playwright.webkit.launch(
                headless=self.headless
            )
            print(f"✅ ブラウザ(Webkit)を起動しました (headless={self.headless}, DISPLAY={os.environ.get('DISPLAY', 'default')})")
        except Exception as e:
            print(f"⚠️ Webkit起動失敗: {e}")
            # フォールバックでChromiumを試行
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            print(f"✅ ブラウザ(Chromium)を起動しました (headless={self.headless}, DISPLAY={os.environ.get('DISPLAY', 'default')})")
    
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
        wait_for_captcha: bool = True,
        form_fields: list = None
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
            form_fields: AI解析結果のフォームフィールド情報（オプション）
        
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
        
        page = self.browser.new_page()
        
        # VNC用に画面を最大化
        page.set_viewport_size({"width": 1920, "height": 1080})
        
        try:
            # ページを開く
            print(f"📄 フォームページを開いています: {form_url}")
            page.goto(form_url, wait_until='networkidle', timeout=30000)
            time.sleep(2)
            
            # フォームフィールドの検出と入力
            fields_filled = []
            
            # AI解析結果がある場合は解析結果ベースで入力
            if form_fields:
                print(f"🤖 AI解析結果を使用して入力 ({len(form_fields)}フィールド)")
                fields_filled = self._fill_with_analysis(page, form_fields, message_data)
            else:
                # フォールバック: 従来のセレクタベース入力
                print(f"⚠️ 解析結果なし - フォールバックモードで実行")
                fields_filled = self._fill_with_fallback(page, message_data)
            
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
                initial_name = page.locator('input#name').input_value()
            except:
                initial_name = None
            
            # 1秒ごとにチェック（60回）
            for i in range(wait_time):
                time.sleep(1)
                
                # ブラウザが閉じられたかチェック
                if page.is_closed():
                    print("⚠️  作業者がブラウザを閉じました")
                    break
                
                # URL変化をチェック
                current_url = page.url
                if current_url != initial_url:
                    if any(keyword in current_url.lower() for keyword in ['thank', 'success', 'confirm', 'complete']):
                        submitted = True
                        print(f"✅ 送信完了を検出しました（URL変化）！ ({i+1}秒後)")
                        print(f"   遷移先URL: {current_url}")
                        time.sleep(2)
                        break
                
                # 成功メッセージが表示されたかチェック（test-contact-form.html用）
                try:
                    # id="result" が表示されたか（hiddenクラスが外れたか）
                    success_element = page.locator('#result')
                    if success_element.count() > 0 and success_element.is_visible():
                        submitted = True
                        print(f"✅ 送信完了を検出しました（成功メッセージ表示）！ ({i+1}秒後)")
                        time.sleep(2)
                        break
                except:
                    pass
                
                # フォームがリセットされたかチェック（入力値が消えた）
                try:
                    current_name = page.locator('input#name').input_value()
                    if initial_name and current_name == '':
                        submitted = True
                        print(f"✅ 送信完了を検出しました（フォームリセット）！ ({i+1}秒後)")
                        time.sleep(2)
                        break
                except:
                    pass
            
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
        print(f"\n🔍 入力試行: 値='{value[:30]}...' ({len(value)}文字)")
        print(f"   セレクタ数: {len(selectors)}")
        
        for i, selector in enumerate(selectors):
            try:
                print(f"   [{i+1}] 試行: {selector}")
                element = page.locator(selector).first
                count = element.count()
                print(f"       → マッチ数: {count}")
                
                if count > 0:
                    visible = element.is_visible()
                    print(f"       → 表示: {visible}")
                    
                    if visible:
                        element.fill(value)
                        print(f"       ✅ fill()実行完了")
                        
                        # 確認
                        try:
                            result_value = element.input_value()
                            print(f"       → 確認: '{result_value[:30]}...' ({len(result_value)}文字)")
                            if len(result_value) > 0:
                                print(f"✅ 入力成功: {selector}")
                                return True
                        except:
                            print(f"       ✅ 入力成功（textarea）: {selector}")
                            return True
            except Exception as e:
                print(f"       ❌ エラー: {e}")
                continue
        
        print(f"❌ 全セレクタで失敗\n")
        return False
    
    def _fill_with_analysis(self, page: Page, form_fields: list, message_data: Dict) -> list:
        """
        AI解析結果を使って入力
        
        Args:
            page: Playwrightページ
            form_fields: AI解析結果のフォームフィールド情報
            message_data: 入力データ
        
        Returns:
            入力成功したフィールド名リスト
        """
        fields_filled = []
        
        # field_category -> message_dataキーのマッピング
        category_to_data = {
            'full_name': message_data.get('name', ''),
            'name': message_data.get('name', ''),
            'email': message_data.get('email', ''),
            'phone': message_data.get('phone', ''),
            'company': message_data.get('company', ''),
            'message': message_data.get('message', ''),
            'inquiry': message_data.get('message', ''),
            'content': message_data.get('message', ''),
            'subject': message_data.get('subject', 'お問い合わせ'),
            'title': message_data.get('subject', 'お問い合わせ'),
            # 部長/担当者名
            'department': message_data.get('department', ''),
            'position': message_data.get('position', ''),
            # ふりがな（name_kana）
            'name_kana': message_data.get('name_kana', ''),
            'full_name_kana': message_data.get('name_kana', ''),
            'last_name_kana': message_data.get('last_name_kana', ''),
            'first_name_kana': message_data.get('first_name_kana', ''),
        }
        
        for field in form_fields:
            field_name = field.get('name') or field.get('id')
            field_id = field.get('id')
            field_type = field.get('type', 'input')
            category = field.get('field_category', 'unknown')
            label = field.get('label', '')
            
            # ラベルからカテゴリを推測（AI誤分類対策）
            if category in ['other', 'unknown', '']:
                category = self._infer_category_from_label(label, field_name)
                if category not in ['other', 'unknown']:
                    print(f"  🔄 ラベルからカテゴリ補正: {field_name} ({label}) → {category}")
            
            # チェックボックスはスキップ（別処理が必要）
            if field_type == 'checkbox':
                continue
            
            # セレクトボックスは別処理
            if field_type == 'select':
                # 種別/お問い合わせ先セレクトの場合、最初の有効な選択肢を選ぶ
                if category in ['subject', 'inquiry_type'] or '種別' in label or 'お問い合わせ' in label:
                    if self._select_first_valid_option(page, field_name, field_id):
                        fields_filled.append(category)
                continue
            
            # カテゴリから入力値を取得
            value = category_to_data.get(category, '')
            
            if not value:
                continue
            
            # セレクタを構築（解析結果のname/idを最優先）
            tag = 'textarea' if field_type == 'textarea' else 'input'
            selectors = []
            
            if field_name:
                selectors.append(f'{tag}[name="{field_name}"]')
            if field_id and field_id != field_name:
                selectors.append(f'{tag}[id="{field_id}"]')
            if field_name:
                selectors.append(f'{tag}[name*="{field_name}"]')
                selectors.append(f'{tag}[id*="{field_name}"]')
            
            # 入力試行
            if self._fill_field(page, selectors, value):
                fields_filled.append(category)
        
        return fields_filled
    
    def _fill_with_fallback(self, page: Page, message_data: Dict) -> list:
        """
        従来のセレクタベースで入力（フォールバック）
        
        Args:
            page: Playwrightページ
            message_data: 入力データ
        
        Returns:
            入力成功したフィールド名リスト
        """
        fields_filled = []
        
        # 会社名フィールド（先に入力）
        company_selectors = [
            'input#company',
            'input[name="company"]',
            'input[id*="company"]',
            'input[name*="company"]',
            'input[placeholder*="会社"]',
            'input[placeholder*="企業"]',
        ]
        if self._fill_field(page, company_selectors, message_data.get('company', '')):
            fields_filled.append('company')
        
        # 名前フィールド
        name_selectors = [
            'input#name',
            'input[name="name"]',
            'input[id*="name"][id*="name"]:not([id*="company"]):not([id*="user"])',
            'input[placeholder*="名前"]',
            'input[placeholder*="お名前"]',
        ]
        if self._fill_field(page, name_selectors, message_data.get('name', '')):
            fields_filled.append('name')
        
        # メールフィールド
        email_selectors = [
            'input#email',
            'input[name="email"]',
            'input[type="email"]',
            'input[name*="email"]',
            'input[name*="mail"]',
            'input[id*="email"]',
        ]
        if self._fill_field(page, email_selectors, message_data.get('email', '')):
            fields_filled.append('email')
        
        # 電話番号フィールド
        phone_selectors = [
            'input#phone',
            'input[name="phone"]',
            'input[type="tel"]',
            'input[name*="phone"]',
            'input[name*="tel"]',
            'input[id*="phone"]',
        ]
        if message_data.get('phone'):
            if self._fill_field(page, phone_selectors, message_data.get('phone')):
                fields_filled.append('phone')
        
        # メッセージフィールド
        message_selectors = [
            'textarea#message',
            'textarea[name="message"]',
            'textarea',
            'textarea[name*="message"]',
            'textarea[name*="inquiry"]',
            'textarea[id*="message"]',
        ]
        if self._fill_field(page, message_selectors, message_data.get('message', '')):
            fields_filled.append('message')
        
        return fields_filled
    
    def _infer_category_from_label(self, label: str, field_name: str) -> str:
        """
        ラベルからカテゴリを推測（AI誤分類のフォールバック）
        
        Args:
            label: フィールドのラベル
            field_name: フィールド名
        
        Returns:
            推測されたカテゴリ
        """
        text = (label + ' ' + field_name).lower()
        
        # ルールベースのマッピング
        # プライバシー・同意系（チェックボックス用）
        if 'プライバシー' in text or 'privacy' in text or '個人情報' in text:
            return 'privacy_agreement'
        if '利用規約' in text or 'terms' in text or '規約に同意' in text:
            return 'terms_agreement'
        # ふりがな（name_kanaより先に判定）
        if 'ふりがな' in text or 'フリガナ' in text or 'kana' in text or 'furi' in text or 'カナ' in text or 'furigana' in text:
            return 'name_kana'
        if '会社' in text or 'company' in text or '企業' in text or '法人' in text or '貴社' in text:
            return 'company'
        if 'メール' in text or 'email' in text or 'mail' in text:
            return 'email'
        if '電話' in text or 'tel' in text or 'phone' in text:
            return 'phone'
        if '名前' in text or 'お名前' in text or '氏名' in text:
            return 'full_name'
        if 'メッセージ' in text or '内容' in text or '本文' in text or '問い合わせ内容' in text:
            return 'message'
        if '件名' in text or 'タイトル' in text or 'subject' in text:
            return 'subject'
        if '種別' in text or 'お問い合わせ先' in text:
            return 'inquiry_type'
        
        return 'other'
    
    def _select_first_valid_option(self, page: Page, field_name: str, field_id: str) -> bool:
        """
        セレクトボックスで最初の有効な選択肢を選ぶ
        
        Args:
            page: Playwrightページ
            field_name: フィールド名
            field_id: フィールドID
        
        Returns:
            成功したか
        """
        selectors = []
        if field_name:
            selectors.append(f'select[name="{field_name}"]')
        if field_id and field_id != field_name:
            selectors.append(f'select[id="{field_id}"]')
        
        for selector in selectors:
            try:
                select_element = page.locator(selector)
                if select_element.count() > 0:
                    # 選択肢を取得
                    options = select_element.locator('option').all()
                    for option in options:
                        value = option.get_attribute('value')
                        text = option.inner_text()
                        # 空値や「選択してください」をスキップ
                        if value and value.strip() and '選択' not in text:
                            select_element.select_option(value=value)
                            print(f"  ✅ セレクト選択: {selector} → {text}")
                            return True
            except Exception as e:
                print(f"  ⚠️ セレクト選択失敗: {selector} - {e}")
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
