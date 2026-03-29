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
from urllib.parse import urlparse
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
        
    async def analyze_form(self, form_url: str, timeout: int = 60000) -> Dict:
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
                await page.goto(form_url, timeout=timeout, wait_until='load')

                # 基本待機（動的コンテンツ読み込み）
                await page.wait_for_timeout(5000)

                # SPA/動的フォーム対応: hydration完了を待機
                await self._wait_for_spa_hydration(page)
                
                # 外部フォームiframe検出（HubSpot, Google Forms, MS Forms等）
                iframe_info = await self._detect_form_iframe(page)

                # reCAPTCHA検出
                recaptcha_result = await self._detect_recaptcha(page)

                # フォームフィールド解析（AI解析 or ルールベース）
                ai_analyzed = False
                if self.use_ai and self.gemini_service:
                    print("🤖 AI解析を実行中...")
                    form_fields, ai_analyzed = await self._analyze_form_fields_with_ai(page, form_url)

                    # SPA対応: フィールド0件なら追加待機してリトライ
                    if ai_analyzed and len(form_fields) == 0:
                        print("⚠️ AI解析でフィールド0件 → SPA追加待機してリトライ")
                        await page.wait_for_timeout(5000)
                        form_fields, ai_analyzed = await self._analyze_form_fields_with_ai(page, form_url)

                    if not ai_analyzed:
                        print("⚠️ AI解析失敗、ルールベースにフォールバック")
                        form_fields = await self._analyze_form_fields(page)

                        # ルールベースでも0件ならSPA追加待機してリトライ
                        if len(form_fields) == 0:
                            print("⚠️ ルールベースでもフィールド0件 → SPA追加待機してリトライ")
                            await page.wait_for_timeout(5000)
                            form_fields = await self._analyze_form_fields(page)
                else:
                    form_fields = await self._analyze_form_fields(page)

                    # ルールベースでも0件ならSPA追加待機してリトライ
                    if len(form_fields) == 0:
                        print("⚠️ ルールベースでもフィールド0件 → SPA追加待機してリトライ")
                        await page.wait_for_timeout(5000)
                        form_fields = await self._analyze_form_fields(page)

                # iframe内フォーム対応: メインページでフィールド0件 & フォームiframe検出の場合
                if len(form_fields) == 0 and iframe_info:
                    print(f"🔍 iframe内フォーム検出 ({iframe_info['service']}) → iframe URLへ遷移して解析")
                    iframe_url = iframe_info['url']

                    try:
                        iframe_page = await context.new_page()
                        await iframe_page.goto(iframe_url, timeout=timeout, wait_until='load')
                        await iframe_page.wait_for_timeout(3000)

                        if self.use_ai and self.gemini_service:
                            form_fields, ai_analyzed = await self._analyze_form_fields_with_ai(iframe_page, iframe_url)
                            if not ai_analyzed:
                                form_fields = await self._analyze_form_fields(iframe_page)
                        else:
                            form_fields = await self._analyze_form_fields(iframe_page)

                        # iframe内のreCAPTCHAも検出
                        iframe_recaptcha = await self._detect_recaptcha(iframe_page)
                        if iframe_recaptcha['has_recaptcha']:
                            recaptcha_result = iframe_recaptcha

                        await iframe_page.close()
                        print(f"✅ iframe内フォーム解析完了: {len(form_fields)}フィールド検出")
                    except Exception as e:
                        print(f"⚠️ iframe内フォーム解析エラー: {e}")
                        # iframeの種類を記録して返す
                        if iframe_info['service'] in ('google_forms', 'ms_forms', 'hubspot'):
                            elapsed_time = time.time() - start_time
                            return {
                                'url': form_url,
                                'recaptcha_type': f"{iframe_info['service']}-iframe",
                                'has_recaptcha': False,
                                'recaptcha_details': {'iframe_service': iframe_info['service']},
                                'form_fields': [],
                                'field_count': 0,
                                'estimated_time': 0,
                                'analysis_status': 'success',
                                'error_message': f"{iframe_info['service']}はiframe内のため自動入力不可",
                                'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                                'analysis_duration': round(elapsed_time, 2),
                                'manual_required': True,
                                'manual_reason': f"{iframe_info['service']} (Cross-Origin iframe)",
                                'ai_analyzed': False
                            }
                
                # 推定処理時間計算
                estimated_time = self._calculate_estimated_time(
                    recaptcha_result['recaptcha_type'],
                    len(form_fields)
                )

                # NG判定（営業NGフォームの検出）
                page_title = await page.title() or ''
                ng_flag, ng_reason = self._detect_ng_form(
                    form_url, page_title, form_fields
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
                    'ai_analyzed': ai_analyzed,
                    'ng_flag': ng_flag,
                    'ng_reason': ng_reason
                }

                analysis_method = "AI" if ai_analyzed else "ルールベース"
                ng_info = f", NG={ng_reason}" if ng_flag else ""
                print(f"✅ 分析完了 ({analysis_method}): reCAPTCHA={recaptcha_result['recaptcha_type']}, フィールド={len(form_fields)}件{ng_info}")

                return result
                
            except PlaywrightTimeout:
                return self._error_result(form_url, 'タイムアウト: ページ読み込みに失敗しました')
                
            except Exception as e:
                return self._error_result(form_url, f'分析エラー: {str(e)}')
                
            finally:
                if browser:
                    await browser.close()
    
    # 外部フォームiframe検出用パターン
    FORM_IFRAME_PATTERNS = {
        'hubspot': ['hs-form', 'hubspot.com'],
        'google_forms': ['docs.google.com/forms'],
        'ms_forms': ['forms.office.com', 'forms.microsoft.com'],
        'bownow': ['bownow.jp/forms'],
        'k3r': ['form.k3r.jp'],
        'formrun': ['form.run'],
        'formmailer': ['formmailer.jp'],
        'typeform': ['typeform.com'],
    }

    async def _detect_form_iframe(self, page) -> Optional[Dict]:
        """
        外部フォームサービスのiframeを検出

        Returns:
            {'service': str, 'url': str} or None
        """
        try:
            iframes = await page.query_selector_all('iframe')
            for iframe in iframes:
                src = await iframe.get_attribute('src') or ''
                if not src:
                    continue
                for service, patterns in self.FORM_IFRAME_PATTERNS.items():
                    if any(pattern in src for pattern in patterns):
                        print(f"🔍 外部フォームiframe検出: {service} ({src[:80]}...)")
                        return {'service': service, 'url': src}
        except Exception as e:
            print(f"⚠️ iframe検出エラー: {e}")
        return None

    async def _wait_for_spa_hydration(self, page) -> None:
        """
        SPA（React/Vue/Next.js等）のhydration完了を待機
        フレームワーク検出後、フォーム要素が表示されるまで最大5秒待つ
        """
        try:
            is_spa = await page.evaluate('''() => {
                // React検出
                if (document.querySelector('[data-reactroot]') ||
                    document.querySelector('#__next') ||
                    document.querySelector('#root[data-reactroot]') ||
                    window.__NEXT_DATA__ ||
                    window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
                    return 'react';
                }
                // Vue検出
                if (document.querySelector('[data-v-]') ||
                    document.querySelector('#app[data-v-app]') ||
                    window.__VUE__ ||
                    document.querySelector('[data-server-rendered]')) {
                    return 'vue';
                }
                // Nuxt検出
                if (window.__NUXT__ || document.querySelector('#__nuxt')) {
                    return 'nuxt';
                }
                // Gatsby検出
                if (document.querySelector('#___gatsby')) {
                    return 'gatsby';
                }
                return null;
            }''')

            if is_spa:
                print(f"🔍 SPAフレームワーク検出: {is_spa} → フォーム要素の出現を待機")
                # フォーム要素が出現するまで最大8秒待機
                try:
                    await page.wait_for_selector(
                        'form, input[type="text"], input[type="email"], textarea, '
                        '[contenteditable="true"], [role="textbox"], div.form-field',
                        timeout=8000
                    )
                    print("✅ フォーム要素の出現を確認")
                    # hydration後の安定化のためさらに少し待つ
                    await page.wait_for_timeout(1000)
                except Exception:
                    print("⚠️ SPA内でフォーム要素が見つかりません（タイムアウト）")
        except Exception as e:
            # JS実行エラーは無視して続行
            print(f"⚠️ SPA検出スキップ: {e}")

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
                    // 方法0: WPCF7対応 - wpcf7-form-control-wrapの前の要素
                    const wrap = el.closest('.wpcf7-form-control-wrap');
                    if (wrap) {
                        const prevEl = wrap.previousElementSibling;
                        if (prevEl) {
                            const text = prevEl.textContent.trim().substring(0, 50);
                            if (text) return text;
                        }
                    }
                    
                    // 方法1: label[for="id"]（CSS.escapeで特殊文字を安全にエスケープ）
                    if (el.id) {
                        try {
                            const escapedId = CSS.escape(el.id);
                            const labelFor = document.querySelector(`label[for="${escapedId}"]`);
                            if (labelFor && labelFor.textContent.trim()) {
                                return labelFor.textContent.trim();
                            }
                        } catch(e) { /* セレクタ無効時はスキップ */ }
                    }
                    
                    // 方法2: 親要素内のlabel（IMP-016: 自分専用のlabelか検証）
                    let parent = el.parentElement;
                    for (let i = 0; i < 5 && parent; i++) {
                        const label = parent.querySelector('label');
                        if (label && label.textContent.trim()) {
                            // IMP-016: このlabelが自分のinputに対応するか確認
                            // parent内のinput/textarea/selectが1つだけ、または
                            // labelがこのinputの直前にある場合のみ採用
                            const inputs = parent.querySelectorAll('input:not([type="hidden"]):not([type="submit"]), textarea, select');
                            if (inputs.length <= 1) {
                                return label.textContent.trim();
                            }
                            // 複数inputがある場合はスキップ（ズレ防止）
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

                    // IMP-016追加: 方法2.5: 直前の兄弟要素（el自体の）
                    let prevEl = el.previousElementSibling;
                    if (prevEl) {
                        const text = prevEl.textContent.trim();
                        if (text && text.length < 50) {
                            return text;
                        }
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

                    // 方法5: placeholder（IMP-016: labelが見つからない場合のフォールバック）
                    if (el.placeholder && el.placeholder.trim()) {
                        return el.placeholder.trim();
                    }

                    // 方法6: aria-label
                    if (el.getAttribute('aria-label')) {
                        return el.getAttribute('aria-label');
                    }

                    // 方法7: title属性
                    if (el.title) {
                        return el.title;
                    }

                    return '';
                }
                
                const formElements = [];

                // 除外すべきフィールド名パターン
                const EXCLUDE_NAMES = [
                    'g-recaptcha-response',
                    'g-recaptcha-hidden',
                    '_wpcf7_ak_hp_textarea',
                    '_wpcf7_ak_hp_texarea',
                    'honeypot',
                    'is_bot',
                ];
                // ハニーポット系のname属性パターン
                const HONEYPOT_PATTERNS = [
                    /^_wpcf7_ak_/,
                    /honeypot/i,
                    /is_bot/i,
                    /^wpforms\\[hp\\]/,
                    /^your-hp$/,
                    /^hp$/,
                ];
                function shouldExclude(el) {
                    const name = el.name || '';
                    const id = el.id || '';
                    const type = (el.type || '').toLowerCase();
                    // 除外リストに一致
                    if (EXCLUDE_NAMES.some(ex => name.includes(ex) || id.includes(ex))) return true;
                    // ハニーポットパターンに一致
                    if (HONEYPOT_PATTERNS.some(re => re.test(name))) return true;
                    // password型フィールドはお問い合わせフォームには不要（ログイン等）
                    if (type === 'password') return true;
                    // name/id両方空でも、placeholder・aria-label・ラベル等があればAIに渡す
                    // 完全に識別情報のない要素のみ除外
                    if (!name && !id) {
                        const placeholder = el.placeholder || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const title = el.title || '';
                        const hasLabel = getLabel(el) !== '';
                        if (!placeholder && !ariaLabel && !title && !hasLabel) return true;
                    }
                    // サイト内検索バーの除外（name="s" でform.roleがsearch、または検索フォーム内）
                    if (name === 's' || name === 'key_word') {
                        const form = el.closest('form');
                        if (!form || form.getAttribute('role') === 'search' ||
                            form.classList.contains('search-form') ||
                            form.id === 'searchform' || form.action?.includes('/?s=')) {
                            return true;
                        }
                        // formが無い場合も除外（ヘッダー等の検索バー）
                        if (!form) return true;
                    }
                    return false;
                }

                // input要素
                document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"])').forEach(el => {
                    if (shouldExclude(el)) return;
                    formElements.push({
                        tag: 'input',
                        type: el.type || 'text',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        aria_label: el.getAttribute('aria-label') || '',
                        required: el.required,
                        label: getLabel(el),
                        outerHTML: el.outerHTML.substring(0, 500)
                    });
                });

                // textarea要素
                document.querySelectorAll('textarea').forEach(el => {
                    if (shouldExclude(el)) return;
                    formElements.push({
                        tag: 'textarea',
                        type: 'textarea',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        aria_label: el.getAttribute('aria-label') || '',
                        required: el.required,
                        label: getLabel(el),
                        outerHTML: el.outerHTML.substring(0, 500)
                    });
                });
                
                // select要素
                document.querySelectorAll('select').forEach(el => {
                    if (shouldExclude(el)) return;
                    const options = Array.from(el.options).map(o => o.text).slice(0, 10);
                    formElements.push({
                        tag: 'select',
                        type: 'select',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: '',
                        aria_label: el.getAttribute('aria-label') || '',
                        required: el.required,
                        label: getLabel(el),
                        options: options,
                        outerHTML: el.outerHTML.substring(0, 500)
                    });
                });
                
                // contenteditable / role="textbox" 要素（SPA系フォーム）
                document.querySelectorAll('[contenteditable="true"], [role="textbox"]').forEach(el => {
                    // 既にinput/textareaとして検出済みの場合はスキップ
                    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return;
                    const label = getLabel(el);
                    const ariaLabel = el.getAttribute('aria-label') || '';
                    const placeholder = el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || '';
                    if (!label && !ariaLabel && !placeholder) return;
                    formElements.push({
                        tag: 'contenteditable',
                        type: 'textarea',
                        name: el.getAttribute('name') || '',
                        id: el.id || '',
                        placeholder: placeholder,
                        aria_label: ariaLabel,
                        required: el.getAttribute('required') !== null || el.getAttribute('aria-required') === 'true',
                        label: label,
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
                    'type': field.get('type') or 'input',
                    'name': field.get('name') or '',
                    'id': field.get('id') or '',
                    'label': field.get('label') or '',
                    'placeholder': field.get('placeholder') or '',
                    'aria_label': field.get('aria_label') or '',
                    'required': field.get('required', False),
                    'field_category': self._normalize_field_category(field.get('field_category') or 'other'),
                    'ai_confidence': field.get('confidence', 0.5),
                    'ai_reasoning': field.get('reasoning') or ''
                })
            
            print(f"🤖 AI解析完了: {len(fields)}フィールド検出")
            return fields, True
            
        except Exception as e:
            print(f"❌ AI解析例外: {e}")
            return [], False
    
    def _normalize_field_category(self, category: str) -> str:
        """AIの出力カテゴリを標準カテゴリに正規化（詳細カテゴリを維持）"""
        if not category:
            return 'other'
        category = category.lower().strip()
        
        # 詳細なカテゴリはそのまま返す（last_name, first_name, phone1等）
        valid_categories = [
            'last_name', 'first_name', 'full_name',  # 名前系
            'name_kana', 'last_name_kana', 'first_name_kana',  # カナ系
            'company_kana',  # 会社名カナ
            'email',
            'company',
            'phone', 'phone1', 'phone2', 'phone3',  # 電話系
            'department', 'position',  # 部署・役職
            'zipcode', 'zipcode1', 'zipcode2',  # 郵便番号系
            'prefecture', 'city', 'address',  # 住所系
            'gender',
            'message',
            'subject',
            'checkbox',
            'privacy_agreement', 'terms_agreement',  # 同意系
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
        if category in ['kana', 'furigana', 'reading']:
            return 'name_kana'
        if category in ['lastname_kana']:
            return 'last_name_kana'
        if category in ['firstname_kana']:
            return 'first_name_kana'
        if category in ['tel', 'telephone']:
            return 'phone'
        if category in ['mail']:
            return 'email'
        if category in ['organization', 'corp']:
            return 'company'
        if category in ['company_name_kana', 'company-name-kana', 'company_furigana']:
            return 'company_kana'
        if category in ['dept', 'division', 'section']:
            return 'department'
        if category in ['role', 'job_title']:
            return 'position'
        if category in ['inquiry', 'content', 'body']:
            return 'message'
        if category in ['agree', 'consent', 'privacy', 'privacy_policy']:
            return 'privacy_agreement'
        if category in ['terms', 'tos']:
            return 'terms_agreement'
        if category in ['title', 'category', 'inquiry_type']:
            return 'subject'
        if category in ['website', 'homepage']:
            return 'url'
        if category in ['zip', 'postal']:
            return 'zipcode'
        if category in ['addr']:
            return 'address'
        if category in ['pref']:
            return 'prefecture'
        if category in ['sex']:
            return 'gender'
        
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
        
        # iframe内のフィールド検出（HubSpot Forms, 汎用iframe等）
        try:
            frames = page.frames
            for frame in frames:
                if frame == page.main_frame:
                    continue
                frame_url = frame.url or ''
                # 既知のフォームサービスiframe
                is_form_iframe = (
                    'hs-form' in frame_url or 'hubspot' in frame_url or
                    'formrun' in frame_url or 'bownow' in frame_url or
                    'form.k3r' in frame_url or 'formmailer' in frame_url
                )
                if is_form_iframe:
                    print(f"🔍 フォームiframe内フィールドを検出中: {frame_url[:60]}")
                    iframe_fields = await self._extract_fields_from_context(frame)
                    fields.extend(iframe_fields)
                elif not fields:
                    # メインページで0件の場合、全iframeを探索
                    try:
                        iframe_fields = await self._extract_fields_from_context(frame)
                        if iframe_fields:
                            print(f"🔍 iframe内フォーム検出: {frame_url[:60]} ({len(iframe_fields)}件)")
                            fields.extend(iframe_fields)
                    except Exception:
                        pass
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
                'aria_label': aria_label,
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
    
    # NG判定用パターン定義
    # 判定ソース: URLのパス部分 + フィールド情報のみ（タイトル・企業名・ページテキストは使用しない）
    NG_PATTERNS = {
        'recruitment': {
            'url_path': ['recruit', 'career', 'entry', 'jobs', 'hiring', 'saiyo', 'boshu'],
            'field_label': ['応募', 'エントリー', '志望動機', '履歴書', '職務経歴',
                            '希望職種', '希望勤務地', '入社希望日', '現在の年収',
                            '学歴', '卒業年', '在籍企業'],
        },
        'reservation': {
            'url_path': ['reserve', 'booking', 'reservation', 'yoyaku'],
            'field_label': ['予約日', '予約時間', '来店日', '来店時間', '人数',
                            'チェックイン', 'チェックアウト', '宿泊日', '宿泊数',
                            '希望日時', '来院日'],
        },
        'medical': {
            'url_path': ['patient', 'shinryo', 'jushin'],
            'field_label': ['患者', '症状', '診察', '保険証', '受診', '問診',
                            '既往歴', '服用中', '診療科', 'お薬', '病歴',
                            '保険証番号', '受診希望'],
        },
        'registration': {
            'url_path': ['signup', 'register', 'touroku', 'create-account'],
            'field_label': ['パスワード確認', 'パスワード再入力', '会員登録',
                            'ユーザーID', 'ログインID', 'パスワード設定',
                            '秘密の質問'],
        },
    }

    def _detect_ng_form(self, form_url: str, page_title: str,
                        form_fields: List[Dict]) -> tuple:
        """
        営業NGフォームを検出

        判定ソースを2つに限定（偽陽性防止）:
        1. URLのパス部分のみ（ドメイン・企業名は除外）
        2. フォームのフィールド情報（ラベル、name、placeholder、選択肢テキスト）

        ページタイトル・企業名・ページ本文テキストは使用しない。

        Args:
            form_url: フォームURL
            page_title: ページタイトル（使用しない、互換性のため残す）
            form_fields: 解析済みフィールドリスト

        Returns:
            (ng_flag: bool, ng_reason: str or None)
        """
        # URLのパス部分のみ抽出（ドメインを除外して偽陽性を防ぐ）
        url_path = urlparse(form_url).path.lower()

        # フィールドのラベル・name・placeholder・選択肢テキストを結合
        field_texts = []
        for f in form_fields:
            field_texts.append((f.get('label') or '').lower())
            field_texts.append((f.get('name') or '').lower())
            field_texts.append((f.get('placeholder') or '').lower())
            # select/radioの選択肢テキストも含める
            for opt in f.get('options', []):
                if isinstance(opt, str):
                    field_texts.append(opt.lower())
                elif isinstance(opt, dict):
                    field_texts.append((opt.get('text') or '').lower())
                    field_texts.append((opt.get('value') or '').lower())
        all_field_text = ' '.join(field_texts)

        for ng_type, patterns in self.NG_PATTERNS.items():
            # URLパス判定（パス部分のみ、ドメイン除外）
            if any(p in url_path for p in patterns['url_path']):
                print(f"🚫 NG検出({ng_type}): URLパス一致 ({url_path})")
                return True, ng_type

            # フィールド情報判定（2つ以上一致でNG）
            match_count = sum(
                1 for p in patterns['field_label']
                if p.lower() in all_field_text
            )
            if match_count >= 2:
                print(f"🚫 NG検出({ng_type}): フィールドラベル{match_count}件一致")
                return True, ng_type

        return False, None

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
            'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'ng_flag': False,
            'ng_reason': None
        }


# 同期版ラッパー
def analyze_form_sync(form_url: str, headless: bool = True, timeout: int = 60000) -> Dict:
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
