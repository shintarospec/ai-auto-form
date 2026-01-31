"""
FormAnalyzer - フォーム事前分析サービス
Phase 2-B: ハイブリッド自動化戦略 + AI解析

企業のお問い合わせフォームを事前分析し、以下を検出：
- reCAPTCHA有無・バージョン（v2/v3/無し）
- フォームフィールド構造（AI解析）
- 推定処理時間

AI解析: Gemini 2.5 Flash によるフォーム認識（0.019円/社）
"""

import asyncio
import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from typing import Dict, Optional, List
import time

# Gemini Service（AI解析用）
try:
    from backend.services.gemini_service import GeminiService
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ GeminiService not available - falling back to rule-based analysis")


class FormAnalyzer:
    """フォーム事前分析クラス（AI解析対応）"""
    
    # reCAPTCHA検出用セレクタ
    RECAPTCHA_SELECTORS = {
        'v2_iframe': 'iframe[src*="recaptcha/api2/anchor"]',
        'v2_checkbox': '.g-recaptcha',
        'v2_div': 'div[class*="g-recaptcha"]',
        'v3_badge': '.grecaptcha-badge',
        'v3_script': 'script[src*="recaptcha/releases"]',
        'v3_token': 'input[name="g-recaptcha-response"]'
    }
    
    # v3検出の確実な指標（これがあれば確実にv3）
    V3_EXECUTE_PATTERNS = [
        'grecaptcha.execute',
        'grecaptcha.ready',
        'render=explicit'
    ]
    
    # フォールバック用：一般的なフォームフィールド名パターン（AI解析失敗時に使用）
    FIELD_PATTERNS = {
        # 名前: 一般的なフィールド名 + 日本で多い姓名（placeholder用）
        'name': ['name', 'お名前', '氏名', 'fullname', 'your-name', 'firstname', 'lastname', 
                 'first_name', 'last_name', '名前', 'sei', 'mei', '姓', '名',
                 # よく使われる姓（Top20）
                 '佐藤', '鈴木', '高橋', '田中', '伊藤', '渡辺', '山本', '中村', '小林', '加藤',
                 '吉田', '山田', '佐々木', '山口', '松本', '井上', '木村', '林', '斎藤', '清水',
                 # よく使われる名（男女）
                 '太郎', '一郎', '健太', '大輔', '翔太', '拓也', '直樹', '和也', '達也', '健一',
                 '花子', '美咲', '陽子', '恵子', '裕子', '愛', 'さくら', '美香', '真由美', '久美子'],
        'email': ['email', 'mail', 'メール', 'e-mail', 'emailaddress', 'your-email', '@'],
        'company': ['company', '会社', '企業', 'organization', 'corp', '法人', 'kigyou', 
                    '株式会社', '（株）', '(株)', '有限会社'],
        'phone': ['phone', 'tel', '電話', 'mobile', '携帯', 'fax', 'denwa'],
        'message': ['message', 'inquiry', 'お問い合わせ', 'content', 'body', 'comment', 
                    '内容', '本文', 'naiyo', 'お問合せ', 'ご質問', 'ご要望']
    }
    
    def __init__(self, headless: bool = True, use_ai: bool = True):
        """
        Args:
            headless: ヘッドレスモードで実行するか
            use_ai: AI解析を使用するか（デフォルト: True）
        """
        self.headless = headless
        self.use_ai = use_ai and GEMINI_AVAILABLE
        self.gemini_service = None
        
        # AI解析が有効な場合、GeminiServiceを初期化
        if self.use_ai:
            try:
                self.gemini_service = GeminiService()
                print("✅ AI解析モード有効 (Gemini 2.5 Flash)")
            except Exception as e:
                print(f"⚠️ Gemini初期化失敗、ルールベース解析にフォールバック: {e}")
                self.use_ai = False
        else:
            print("ℹ️ ルールベース解析モード")
        
    async def analyze_form(self, form_url: str, timeout: int = 30000) -> Dict:
        """
        フォームを分析してreCAPTCHAと構造を検出（AI解析対応）
        
        Args:
            form_url: フォームURL
            timeout: タイムアウト（ミリ秒）
            
        Returns:
            {
                'url': str,
                'recaptcha_type': 'v2' | 'v3' | 'none',
                'has_recaptcha': bool,
                'form_fields': List[Dict],
                'field_count': int,
                'estimated_time': int,  # 秒
                'analysis_status': 'success' | 'error',
                'error_message': Optional[str],
                'analyzed_at': str,
                'ai_analyzed': bool  # AI解析を使用したかどうか
            }
        """
        start_time = time.time()
        
        async with async_playwright() as p:
            browser = None
            try:
                # ブラウザ起動（ChromiumをSandbox無効化で起動）
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                print(f"🔍 フォーム分析開始: {form_url}")
                
                # ページ読み込み
                await page.goto(form_url, timeout=timeout, wait_until='networkidle')
                
                # 基本待機（動的コンテンツ読み込み）
                await page.wait_for_timeout(2000)
                
                # HubSpot Forms検出（Cross-Origin iframeのため手動対応必須）
                hubspot_detected = False
                try:
                    hubspot_form = await page.query_selector('iframe[id*="hs-form"]')
                    if hubspot_form:
                        hubspot_detected = True
                        print("⚠️ HubSpot Forms検出 - Cross-Origin iframeのため手動対応必須")
                except:
                    pass
                
                # HubSpot Formsの場合、手動対応として返す
                if hubspot_detected:
                    elapsed_time = time.time() - start_time
                    return {
                        'url': form_url,
                        'recaptcha_type': 'hubspot-iframe',  # 特殊タイプとして識別
                        'has_recaptcha': False,
                        'recaptcha_details': {'hubspot_iframe': True},
                        'form_fields': [],
                        'field_count': 0,
                        'estimated_time': 0,  # 手動のため時間推定なし
                        'analysis_status': 'success',
                        'error_message': 'HubSpot Formsはiframe内のため自動入力不可',
                        'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'analysis_duration': round(elapsed_time, 2),
                        'manual_required': True,
                        'manual_reason': 'HubSpot Forms (Cross-Origin iframe)',
                        'ai_analyzed': False
                    }
                
                # reCAPTCHA検出
                recaptcha_result = await self._detect_recaptcha(page)
                
                # フォームフィールド解析（AI解析 or ルールベース）
                ai_analyzed = False
                if self.use_ai and self.gemini_service:
                    print("🤖 AI解析を実行中...")
                    form_fields, ai_analyzed = await self._analyze_form_fields_with_ai(page, form_url)
                    if not ai_analyzed:
                        print("⚠️ AI解析失敗、ルールベースにフォールバック")
                        form_fields = await self._analyze_form_fields(page)
                else:
                    form_fields = await self._analyze_form_fields(page)
                
                # 推定処理時間計算
                estimated_time = self._calculate_estimated_time(
                    recaptcha_result['recaptcha_type'],
                    len(form_fields)
                )
                
                elapsed_time = time.time() - start_time
                
                result = {
                    'url': form_url,
                    'recaptcha_type': recaptcha_result['recaptcha_type'],
                    'has_recaptcha': recaptcha_result['has_recaptcha'],
                    'recaptcha_details': recaptcha_result['details'],
                    'form_fields': form_fields,
                    'field_count': len(form_fields),
                    'estimated_time': estimated_time,
                    'analysis_status': 'success',
                    'error_message': None,
                    'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'analysis_duration': round(elapsed_time, 2),
                    'ai_analyzed': ai_analyzed
                }
                
                analysis_method = "AI" if ai_analyzed else "ルールベース"
                print(f"✅ 分析完了 ({analysis_method}): reCAPTCHA={recaptcha_result['recaptcha_type']}, フィールド={len(form_fields)}件")
                
                return result
                
            except PlaywrightTimeout:
                return self._error_result(form_url, 'タイムアウト: ページ読み込みに失敗しました')
                
            except Exception as e:
                return self._error_result(form_url, f'分析エラー: {str(e)}')
                
            finally:
                if browser:
                    await browser.close()
    
    async def _detect_recaptcha(self, page) -> Dict:
        """
        reCAPTCHAの有無とバージョンを検出
        
        Returns:
            {
                'recaptcha_type': 'v2' | 'v3' | 'none',
                'has_recaptcha': bool,
                'details': Dict
            }
        """
        details = {
            'v2_checkbox': False,
            'v2_iframe': False,
            'v3_badge': False,
            'v3_script': False
        }
        
        # v2検出（チェックボックス型）
        try:
            v2_elements = await page.query_selector_all(self.RECAPTCHA_SELECTORS['v2_checkbox'])
            if v2_elements:
                details['v2_checkbox'] = True
                print("🔒 reCAPTCHA v2（チェックボックス）検出")
                return {
                    'recaptcha_type': 'v2',
                    'has_recaptcha': True,
                    'details': details
                }
        except:
            pass
        
        # v2検出（iframe）
        try:
            v2_iframe = await page.query_selector(self.RECAPTCHA_SELECTORS['v2_iframe'])
            if v2_iframe:
                details['v2_iframe'] = True
                print("🔒 reCAPTCHA v2（iframe）検出")
                return {
                    'recaptcha_type': 'v2',
                    'has_recaptcha': True,
                    'details': details
                }
        except:
            pass
        
        # v3検出（バッジ）
        try:
            v3_badge = await page.query_selector(self.RECAPTCHA_SELECTORS['v3_badge'])
            if v3_badge:
                details['v3_badge'] = True
                print("🔐 reCAPTCHA v3（バッジ）検出")
                return {
                    'recaptcha_type': 'v3',
                    'has_recaptcha': True,
                    'details': details
                }
        except:
            pass
        
        # v3検出（スクリプト - より厳密な検出）
        try:
            scripts = await page.query_selector_all('script')
            for script in scripts:
                src = await script.get_attribute('src')
                if src and 'recaptcha' in src:
                    # スクリプトのsrcだけでなく、v3特有のパターンを確認
                    page_content = await page.content()
                    is_v3 = any(pattern in page_content for pattern in self.V3_EXECUTE_PATTERNS)
                    
                    if is_v3:
                        details['v3_script'] = True
                        print("🔐 reCAPTCHA v3（スクリプト+execute確認）検出")
                        return {
                            'recaptcha_type': 'v3',
                            'has_recaptcha': True,
                            'details': details
                        }
                    else:
                        # recaptchaスクリプトはあるが、execute呼び出しがない場合
                        # → v2か動的読み込みの可能性、安全のためv2として扱う
                        details['v2_script_only'] = True
                        print("⚠️ reCAPTCHAスクリプト検出（execute未確認、v2として扱う）")
                        return {
                            'recaptcha_type': 'v2',
                            'has_recaptcha': True,
                            'details': details
                        }
        except:
            pass
        
        # reCAPTCHA無し
        print("✅ reCAPTCHA無し")
        return {
            'recaptcha_type': 'none',
            'has_recaptcha': False,
            'details': details
        }
    
    async def _analyze_form_fields_with_ai(self, page, form_url: str) -> tuple:
        """
        AI（Gemini）を使用してフォームフィールドを解析
        
        Args:
            page: Playwrightページオブジェクト
            form_url: フォームURL
        
        Returns:
            (fields_list, ai_analyzed: bool)
        """
        try:
            # フォーム要素のHTMLを抽出（ラベル取得を強化）
            form_html = await page.evaluate('''() => {
                // ラベルを取得するヘルパー関数
                function getLabel(el) {
                    // 方法1: label[for="id"]
                    if (el.id) {
                        const labelFor = document.querySelector(`label[for="${el.id}"]`);
                        if (labelFor && labelFor.textContent.trim()) {
                            return labelFor.textContent.trim();
                        }
                    }
                    
                    // 方法2: 親要素内のlabel
                    let parent = el.parentElement;
                    for (let i = 0; i < 5 && parent; i++) {
                        const label = parent.querySelector('label');
                        if (label && label.textContent.trim()) {
                            return label.textContent.trim();
                        }
                        
                        // 方法3: 前の兄弟要素にラベルテキスト
                        const prevSibling = parent.previousElementSibling;
                        if (prevSibling) {
                            const text = prevSibling.textContent.trim();
                            if (text && text.length < 50) {
                                return text;
                            }
                        }
                        
                        parent = parent.parentElement;
                    }
                    
                    // 方法4: 親要素のテキスト（inputより前のテキスト）
                    parent = el.parentElement;
                    if (parent) {
                        const clone = parent.cloneNode(true);
                        clone.querySelectorAll('input, textarea, select').forEach(e => e.remove());
                        const text = clone.textContent.trim();
                        if (text && text.length < 100) {
                            return text.split('\\n')[0].trim();
                        }
                    }
                    
                    // 方法5: aria-label
                    if (el.getAttribute('aria-label')) {
                        return el.getAttribute('aria-label');
                    }
                    
                    // 方法6: title属性
                    if (el.title) {
                        return el.title;
                    }
                    
                    return '';
                }
                
                const formElements = [];
                
                // input要素
                document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"])').forEach(el => {
                    formElements.push({
                        tag: 'input',
                        type: el.type || 'text',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        required: el.required,
                        label: getLabel(el),
                        outerHTML: el.outerHTML.substring(0, 500)
                    });
                });
                
                // textarea要素
                document.querySelectorAll('textarea').forEach(el => {
                    formElements.push({
                        tag: 'textarea',
                        type: 'textarea',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        required: el.required,
                        label: getLabel(el),
                        outerHTML: el.outerHTML.substring(0, 500)
                    });
                });
                
                // select要素
                document.querySelectorAll('select').forEach(el => {
                    const options = Array.from(el.options).map(o => o.text).slice(0, 10);
                    formElements.push({
                        tag: 'select',
                        type: 'select',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: '',
                        required: el.required,
                        label: getLabel(el),
                        options: options,
                        outerHTML: el.outerHTML.substring(0, 500)
                    });
                });
                
                return JSON.stringify(formElements, null, 2);
            }''')
            
            if not form_html or form_html == '[]':
                print("⚠️ フォーム要素が見つかりません")
                return [], False
            
            # Gemini APIでフィールド解析
            ai_result = self.gemini_service.analyze_form_fields(form_html, form_url)
            
            if 'error' in ai_result or not ai_result.get('fields'):
                print(f"⚠️ AI解析エラー: {ai_result.get('error', 'フィールド検出なし')}")
                return [], False
            
            # AI結果を標準フォーマットに変換
            fields = []
            for field in ai_result.get('fields', []):
                fields.append({
                    'type': field.get('type', 'input'),
                    'name': field.get('name', ''),
                    'id': field.get('id', ''),
                    'label': field.get('label', ''),
                    'placeholder': field.get('placeholder', ''),
                    'required': field.get('required', False),
                    'field_category': self._normalize_field_category(field.get('field_category', 'other')),
                    'ai_confidence': field.get('confidence', 0.5),
                    'ai_reasoning': field.get('reasoning', '')
                })
            
            print(f"🤖 AI解析完了: {len(fields)}フィールド検出")
            return fields, True
            
        except Exception as e:
            print(f"❌ AI解析例外: {e}")
            return [], False
    
    def _normalize_field_category(self, category: str) -> str:
        """AIの出力カテゴリを標準カテゴリに正規化（詳細カテゴリを維持）"""
        category = category.lower().strip()
        
        # 詳細なカテゴリはそのまま返す（last_name, first_name, phone1等）
        valid_categories = [
            'last_name', 'first_name', 'full_name',  # 名前系
            'email',
            'company',
            'phone', 'phone1', 'phone2', 'phone3',  # 電話系
            'zipcode', 'zipcode1', 'zipcode2',  # 郵便番号系
            'address',
            'message',
            'subject',
            'checkbox',
            'url',
            'other'
        ]
        
        if category in valid_categories:
            return category
        
        # 類似カテゴリの正規化
        if category in ['lastname']:
            return 'last_name'
        if category in ['firstname']:
            return 'first_name'
        if category in ['fullname', 'name']:
            return 'full_name'
        if category in ['tel', 'telephone']:
            return 'phone'
        if category in ['mail']:
            return 'email'
        if category in ['organization', 'corp']:
            return 'company'
        if category in ['inquiry', 'content', 'body']:
            return 'message'
        if category in ['agree', 'consent']:
            return 'checkbox'
        if category in ['title']:
            return 'subject'
        if category in ['website', 'homepage']:
            return 'url'
        if category in ['zip', 'postal']:
            return 'zipcode'
        if category in ['addr']:
            return 'address'
        
        return 'other'
    
    async def _analyze_form_fields(self, page) -> List[Dict]:
        """
        フォームフィールドを解析（ルールベース、フォールバック用）
        
        Returns:
            [
                {
                    'type': 'input' | 'textarea' | 'select',
                    'name': str,
                    'id': str,
                    'label': str,
                    'required': bool,
                    'field_category': 'name' | 'email' | 'company' | 'phone' | 'message' | 'other'
                },
                ...
            ]
        """
        fields = []
        
        # メインページのフィールド検出
        fields.extend(await self._extract_fields_from_context(page))
        
        # iframe内のフィールド検出（HubSpot Forms等）
        try:
            frames = page.frames
            for frame in frames:
                if 'hs-form' in frame.url or 'hubspot' in frame.url:
                    print("🔍 HubSpot iframe内フィールドを検出中...")
                    iframe_fields = await self._extract_fields_from_context(frame)
                    fields.extend(iframe_fields)
        except Exception as e:
            print(f"⚠️ iframe解析エラー: {e}")
        
        print(f"📝 フィールド {len(fields)}件 検出")
        return fields
    
    async def _extract_fields_from_context(self, context) -> List[Dict]:
        """指定されたコンテキスト（ページまたはフレーム）からフィールドを抽出"""
        fields = []
        
        # input要素（hidden, submit, button, radio除外）
        inputs = await context.query_selector_all(
            'input[type="text"], input[type="email"], input[type="tel"], '
            'input:not([type]):not([type="hidden"]):not([type="submit"]):not([type="button"])'
            ':not([type="radio"]):not([type="file"])'
        )
        for input_elem in inputs:
            # hidden inputを再度チェック（フォールバック）
            input_type = await input_elem.get_attribute('type')
            if input_type and input_type.lower() in ['hidden', 'submit', 'button', 'radio', 'file']:
                continue
            # チェックボックスは特別に処理
            if input_type and input_type.lower() == 'checkbox':
                field_info = await self._extract_field_info(input_elem, 'checkbox')
            else:
                field_info = await self._extract_field_info(input_elem, 'input')
            if field_info:
                fields.append(field_info)
        
        # チェックボックスを明示的に検索（同意ボタン等）
        checkboxes = await context.query_selector_all('input[type="checkbox"]')
        for checkbox in checkboxes:
            field_info = await self._extract_field_info(checkbox, 'checkbox')
            if field_info:
                # 重複チェック
                if not any(f['name'] == field_info['name'] for f in fields):
                    fields.append(field_info)
        
        # textarea要素
        textareas = await context.query_selector_all('textarea')
        for textarea in textareas:
            field_info = await self._extract_field_info(textarea, 'textarea')
            if field_info:
                fields.append(field_info)
        
        # select要素
        selects = await context.query_selector_all('select')
        for select in selects:
            field_info = await self._extract_field_info(select, 'select')
            if field_info:
                fields.append(field_info)
        
        return fields
    
    async def _extract_field_info(self, element, field_type: str) -> Optional[Dict]:
        """フィールド情報を抽出"""
        try:
            name = await element.get_attribute('name') or ''
            field_id = await element.get_attribute('id') or ''
            placeholder = await element.get_attribute('placeholder') or ''
            required = await element.get_attribute('required') is not None
            
            # aria-label, title属性も取得
            aria_label = await element.get_attribute('aria-label') or ''
            title = await element.get_attribute('title') or ''
            
            # ラベル取得試行（複数の方法）
            label = ''
            if field_id:
                try:
                    # 方法1: for属性でのラベル
                    label_elem = await element.evaluate_handle(
                        f'(el) => document.querySelector("label[for=\\"{field_id}\\"]")'
                    )
                    if label_elem:
                        label = await label_elem.inner_text()
                except:
                    pass
            
            if not label:
                try:
                    # 方法2: 親要素がlabelの場合
                    parent_label = await element.evaluate(
                        '(el) => { let p = el.closest("label"); return p ? p.textContent : ""; }'
                    )
                    if parent_label:
                        label = parent_label
                except:
                    pass
            
            # ラベルがなければaria-labelやtitleを使用
            if not label:
                label = aria_label or title
            
            # フィールド分類（field_typeも渡す）
            field_category = self._categorize_field(name, field_id, placeholder, label, field_type)
            
            return {
                'type': field_type,
                'name': name,
                'id': field_id,
                'label': label.strip() if label else '',
                'placeholder': placeholder,
                'required': required,
                'field_category': field_category
            }
            
        except Exception as e:
            print(f"⚠️ フィールド抽出エラー: {e}")
            return None
    
    def _categorize_field(self, name: str, field_id: str, placeholder: str, label: str, field_type: str = 'input') -> str:
        """フィールドを分類（優先度順にチェック）"""
        import re
        
        combined_text = f"{name} {field_id} {placeholder} {label}".lower()
        
        # チェックボックスは同意系として分類
        if field_type == 'checkbox':
            return 'checkbox'
        
        # メールアドレス形式のplaceholderを検出（例: taro@example.jp）
        if placeholder and re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]+', placeholder):
            return 'email'
        
        # 優先度順に判定（より具体的なパターンを先に）
        priority_order = ['email', 'phone', 'company', 'message', 'name']
        
        for category in priority_order:
            patterns = self.FIELD_PATTERNS[category]
            for pattern in patterns:
                if pattern in combined_text:
                    return category
        
        # textareaはデフォルトでmessage
        if field_type == 'textarea':
            return 'message'
        
        return 'other'
    
    def _calculate_estimated_time(self, recaptcha_type: str, field_count: int) -> int:
        """
        推定処理時間を計算（秒）
        
        Args:
            recaptcha_type: reCAPTCHAタイプ
            field_count: フィールド数
            
        Returns:
            推定時間（秒）
        """
        base_time = field_count * 2  # フィールド1つあたり2秒
        
        if recaptcha_type == 'v2':
            # reCAPTCHA v2: 人間の手動対応が必要
            return base_time + 60  # +60秒（reCAPTCHA解決）
        elif recaptcha_type == 'v3':
            # reCAPTCHA v3: 自動対応可能
            return base_time + 5  # +5秒（v3検証）
        else:
            # reCAPTCHA無し: 完全自動
            return base_time + 3  # +3秒（送信・確認）
    
    def _error_result(self, form_url: str, error_message: str) -> Dict:
        """エラー結果を返す"""
        print(f"❌ 分析失敗: {error_message}")
        return {
            'url': form_url,
            'recaptcha_type': None,
            'has_recaptcha': None,
            'form_fields': [],
            'field_count': 0,
            'estimated_time': None,
            'analysis_status': 'error',
            'error_message': error_message,
            'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }


# 同期版ラッパー
def analyze_form_sync(form_url: str, headless: bool = True, timeout: int = 30000) -> Dict:
    """
    同期的にフォーム分析を実行
    
    Args:
        form_url: フォームURL
        headless: ヘッドレスモード
        timeout: タイムアウト（ミリ秒）
        
    Returns:
        分析結果Dict
    """
    analyzer = FormAnalyzer(headless=headless)
    return asyncio.run(analyzer.analyze_form(form_url, timeout))
