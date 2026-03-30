"""
F-3 Lite: パターンベースフォーム解析エンジン
AI不使用・パターンマッチングのみでフォーム構造を解析
出力はF-3(Gemini)と完全互換 → F-4(auto_executor)は変更不要
"""
import re
import time
from typing import Dict, List, Optional, Tuple
from playwright.async_api import async_playwright


# ====== パターンテーブル ======

# type属性による一意特定
TYPE_CATEGORY_MAP = {
    'email': 'email',
    'tel': 'phone',
    'url': 'url',
}

# name/id属性パターン（優先順位順）
NAME_PATTERNS = [
    # email（先にチェック — "name"を含むフィールドとの誤マッチ防止）
    (r'e[-_]?mail|mail[-_]?addr', 'email'),
    # phone分割
    (r'tel[-_]?1|phone[-_]?1|denwa[-_]?1', 'phone1'),
    (r'tel[-_]?2|phone[-_]?2|denwa[-_]?2', 'phone2'),
    (r'tel[-_]?3|phone[-_]?3|denwa[-_]?3', 'phone3'),
    # phone
    (r'(?:^|[-_])tel(?:$|[-_\[])|phone|denwa|mobile|keitai', 'phone'),
    # zipcode分割
    (r'zip[-_]?1|post[-_]?1|yubin[-_]?1', 'zipcode1'),
    (r'zip[-_]?2|post[-_]?2|yubin[-_]?2', 'zipcode2'),
    # zipcode
    (r'zip|postal|yubin', 'zipcode'),
    # company
    (r'company|corp|kaisha|organi[sz]ation|firm|org[-_]name', 'company'),
    # department / position
    (r'department|busho|division|section', 'department'),
    (r'position|yakushoku|job[-_]?title|jobtitle', 'position'),
    # name_kana（kanaを先にチェック — nameより前に）
    (r'kana|furi|reading|pronunciation|furigana', 'name_kana'),
    # name系（姓→名→フル の順）
    (r'(?:last|family)[-_]?name|sei(?:$|[-_])|(?:^|[-_])sei(?:$|[-_])', 'last_name'),
    (r'(?:first|given)[-_]?name|mei(?:$|[-_])|(?:^|[-_])mei(?:$|[-_])', 'first_name'),
    (r'(?:full[-_]?)?name|namae|shimei', 'full_name'),
    # address系
    (r'pref|todofuken|prefecture', 'prefecture'),
    (r'(?:^|[-_])city|shiku', 'city'),
    (r'address|addr|jusho|jyusho', 'address'),
    # subject
    (r'subject|title|kenmei|youken', 'subject'),
    # url
    (r'(?:^|[-_])url|homepage|website', 'url'),
    # gender
    (r'gender|sex|seibetsu', 'gender'),
    # message（最後 — bodyやcontentは他の意味もあるため）
    (r'message|body|content|inquiry|naiyo', 'message'),
]

# placeholder/labelパターン（日本語優先）
LABEL_PATTERNS = [
    # email
    (r'メール|eメール|e-mail|email|メールアドレス', 'email'),
    # phone
    (r'電話|tel(?!e)|phone|携帯', 'phone'),
    # company
    (r'会社名|法人名|企業名|御社名|貴社名|組織名|所属.*(?:名|企業|会社)', 'company'),
    # department / position
    (r'部署|所属部門|部門名', 'department'),
    (r'役職', 'position'),
    # name_kana
    (r'ふりがな|フリガナ|カナ|よみ|読み|furigana', 'name_kana'),
    # name系
    (r'^姓$|^苗字$|last\s*name|family\s*name', 'last_name'),
    (r'^名$|first\s*name|given\s*name', 'first_name'),
    (r'お名前|氏名|ご担当者|担当者名|your\s*name|full\s*name|名前', 'full_name'),
    # zipcode
    (r'郵便番号|〒|zip|postal', 'zipcode'),
    # address
    (r'都道府県|prefecture', 'prefecture'),
    (r'市区町村|city', 'city'),
    (r'住所|番地|所在地|address', 'address'),
    # subject
    (r'お問い合わせ種別|お問い合わせ項目|種類|種別|件名|subject', 'subject'),
    # message
    (r'お問い合わせ内容|お問合せ内容|ご用件|本文|メッセージ|ご相談|ご質問|message|inquiry', 'message'),
    # url
    (r'url|ホームページ|ウェブサイト|website', 'url'),
    # gender
    (r'性別|gender', 'gender'),
]

# checkbox分類パターン
CHECKBOX_PATTERNS = [
    (r'プライバシー|個人情報|privacy|privacypolicy', 'privacy_agreement'),
    (r'利用規約|terms|規約に同意', 'terms_agreement'),
    (r'同意|agree|consent', 'agreement'),
]

# name属性の除外パターン（company等との誤マッチ防止）
NAME_EXCLUDE = {
    'full_name': [r'company', r'org', r'corp', r'file', r'user', r'kana', r'furi', r'mail', r'email'],
}


class FormAnalyzerLite:
    """F-3 Lite: パターンベースフォーム解析"""

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def analyze_form(self, form_url: str, timeout: int = 60000) -> Dict:
        """フォームを解析してform_analysis互換の結果を返す"""
        start_time = time.time()

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()

                # ページ読み込み
                await page.goto(form_url, timeout=timeout, wait_until='load')
                await page.wait_for_timeout(3000)

                # SPA待機
                await self._wait_for_spa(page)

                # reCAPTCHA検出
                recaptcha = await self._detect_recaptcha(page)

                # フィールド抽出
                fields = await self._extract_all_fields(page)

                # 電話番号・郵便番号の分割検出
                fields = self._detect_split_fields(fields)

                # NG判定
                ng_flag, ng_reason = self._detect_ng(form_url, fields)

                elapsed = round(time.time() - start_time, 1)

                return {
                    'url': form_url,
                    'recaptcha_type': recaptcha['type'],
                    'has_recaptcha': recaptcha['type'] != 'none',
                    'form_fields': fields,
                    'field_count': len(fields),
                    'estimated_time': self._estimate_time(recaptcha['type'], len(fields)),
                    'analysis_status': 'success',
                    'error_message': None,
                    'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'ai_analyzed': False,
                    'analysis_method': 'lite',
                    'ng_flag': ng_flag,
                    'ng_reason': ng_reason,
                    'elapsed_seconds': elapsed,
                }

            except Exception as e:
                return {
                    'url': form_url,
                    'recaptcha_type': 'none',
                    'has_recaptcha': False,
                    'form_fields': [],
                    'field_count': 0,
                    'estimated_time': 0,
                    'analysis_status': 'error',
                    'error_message': str(e)[:200],
                    'analyzed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'ai_analyzed': False,
                    'analysis_method': 'lite',
                    'ng_flag': False,
                    'ng_reason': None,
                }
            finally:
                if browser:
                    await browser.close()

    # ====== ページ待機 ======

    async def _wait_for_spa(self, page):
        """SPA/動的フォームの待機"""
        try:
            await page.wait_for_load_state('networkidle', timeout=5000)
        except Exception:
            pass
        # form要素が出現するまで追加待機
        try:
            await page.wait_for_selector('form, input, textarea', timeout=5000)
        except Exception:
            pass

    # ====== reCAPTCHA検出 ======

    async def _detect_recaptcha(self, page) -> Dict:
        """reCAPTCHA検出（v2/v3/none）"""
        try:
            # v2
            v2_selectors = [
                'iframe[src*="recaptcha/api2/anchor"]',
                '.g-recaptcha',
                'div[class*="g-recaptcha"]',
            ]
            for sel in v2_selectors:
                if await page.query_selector(sel):
                    return {'type': 'v2'}

            # v3
            v3_selectors = [
                '.grecaptcha-badge',
                'script[src*="recaptcha/releases"]',
            ]
            for sel in v3_selectors:
                if await page.query_selector(sel):
                    return {'type': 'v3'}

            # v3 script content check
            scripts = await page.evaluate("""() => {
                return Array.from(document.scripts).map(s => s.src || s.textContent.substring(0, 500)).join(' ');
            }""")
            if 'grecaptcha.execute' in scripts or 'grecaptcha.ready' in scripts:
                return {'type': 'v3'}

            return {'type': 'none'}
        except Exception:
            return {'type': 'none'}

    # ====== フィールド抽出 ======

    async def _extract_all_fields(self, page) -> List[Dict]:
        """DOM走査でフィールドを抽出"""
        fields = []

        # メインページ
        fields.extend(await self._extract_fields_from_context(page))

        # iframe内
        try:
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                frame_url = frame.url or ''
                is_form_iframe = any(k in frame_url for k in
                    ['hs-form', 'hubspot', 'formrun', 'bownow', 'form.k3r', 'formmailer'])
                if is_form_iframe or not fields:
                    try:
                        iframe_fields = await self._extract_fields_from_context(frame)
                        if iframe_fields:
                            fields.extend(iframe_fields)
                    except Exception:
                        pass
        except Exception:
            pass

        return fields

    async def _extract_fields_from_context(self, context) -> List[Dict]:
        """コンテキストからフィールド情報を一括抽出（JS実行1回で高速化）"""
        try:
            raw_fields = await context.evaluate("""() => {
                const results = [];
                const seen = new Set();

                function getLabel(el) {
                    // 1. for属性
                    if (el.id) {
                        const lbl = document.querySelector('label[for="' + el.id + '"]');
                        if (lbl) return lbl.textContent.trim();
                    }
                    // 2. 親label
                    const pLbl = el.closest('label');
                    if (pLbl) return pLbl.textContent.trim();
                    // 3. 前の兄弟要素
                    let prev = el.previousElementSibling;
                    for (let i = 0; i < 3 && prev; i++) {
                        if (prev.tagName === 'LABEL') return prev.textContent.trim();
                        const inner = prev.querySelector && prev.querySelector('label');
                        if (inner) return inner.textContent.trim();
                        prev = prev.previousElementSibling;
                    }
                    // 4. 親要素のテキスト
                    const par = el.parentElement;
                    if (par) {
                        const parLbl = par.querySelector('label');
                        if (parLbl) return parLbl.textContent.trim();
                        const dt = par.closest('dl') ? par.closest('dl').querySelector('dt') : null;
                        if (dt) return dt.textContent.trim();
                        const th = par.closest('tr') ? par.closest('tr').querySelector('th') : null;
                        if (th) return th.textContent.trim();
                        const txt = par.textContent.trim();
                        if (txt.length < 50 && txt.length > 0) return txt;
                    }
                    return '';
                }

                function isVisible(el) {
                    try {
                        const st = window.getComputedStyle(el);
                        if (st.display === 'none' || st.visibility === 'hidden') return false;
                        if (el.offsetParent === null && st.position !== 'fixed') return false;
                        return true;
                    } catch(e) { return false; }
                }

                // input要素
                const inputs = document.querySelectorAll('input');
                for (const el of inputs) {
                    const type = (el.type || 'text').toLowerCase();
                    if (['hidden', 'submit', 'button', 'image', 'reset', 'file'].includes(type)) continue;
                    if (!isVisible(el) && type !== 'checkbox') continue;
                    const key = el.name + '|' + el.id + '|' + type;
                    if (seen.has(key) && type !== 'radio') continue;
                    seen.add(key);
                    results.push({
                        tag: 'input', type: type,
                        name: el.name || '', id: el.id || '',
                        placeholder: el.placeholder || '',
                        label: getLabel(el),
                        ariaLabel: el.getAttribute('aria-label') || '',
                        required: el.required || el.getAttribute('aria-required') === 'true',
                        maxlength: el.maxLength > 0 && el.maxLength < 10000 ? el.maxLength : null,
                        options: null,
                    });
                }

                // textarea要素
                const textareas = document.querySelectorAll('textarea');
                for (const el of textareas) {
                    if (!isVisible(el)) continue;
                    results.push({
                        tag: 'textarea', type: 'textarea',
                        name: el.name || '', id: el.id || '',
                        placeholder: el.placeholder || '',
                        label: getLabel(el),
                        ariaLabel: el.getAttribute('aria-label') || '',
                        required: el.required || el.getAttribute('aria-required') === 'true',
                        maxlength: null,
                        options: null,
                    });
                }

                // select要素
                const selects = document.querySelectorAll('select');
                for (const el of selects) {
                    if (!isVisible(el)) continue;
                    const opts = Array.from(el.options).map(o => ({value: o.value, text: o.text.trim()}));
                    results.push({
                        tag: 'select', type: 'select',
                        name: el.name || '', id: el.id || '',
                        placeholder: '',
                        label: getLabel(el),
                        ariaLabel: el.getAttribute('aria-label') || '',
                        required: el.required,
                        maxlength: null,
                        options: opts.slice(0, 30),
                    });
                }

                return results;
            }""")
        except Exception as e:
            print(f"  ⚠️ DOM走査エラー: {e}")
            return []

        # Pythonでカテゴリ判定
        fields = []
        for raw in raw_fields:
            category = self._categorize(raw)
            field = {
                'type': raw['type'] if raw['type'] != 'textarea' else 'textarea',
                'name': raw['name'],
                'id': raw['id'],
                'label': raw['label'][:100] if raw['label'] else '',
                'placeholder': raw['placeholder'],
                'aria_label': raw['ariaLabel'],
                'required': raw['required'],
                'field_category': category,
            }
            if raw['options']:
                field['options'] = raw['options']
            fields.append(field)

        return fields

    # ====== カテゴリ判定 ======

    def _categorize(self, raw: Dict) -> str:
        """パターンマッチングでfield_categoryを判定"""
        field_type = raw['type']
        name = raw['name'].lower()
        field_id = raw['id'].lower()
        placeholder = raw['placeholder'].lower()
        label = raw['label'].lower()
        aria_label = raw['ariaLabel'].lower()

        # 1. checkbox特別処理
        if field_type == 'checkbox':
            combined = f"{name} {field_id} {label} {aria_label}"
            for pattern, cat in CHECKBOX_PATTERNS:
                if re.search(pattern, combined, re.I):
                    return cat
            return 'checkbox'

        # 2. radio特別処理
        if field_type == 'radio':
            combined = f"{name} {field_id} {label}"
            # subject系ラジオ
            if re.search(r'subject|type|category|種別|種類|お問い合わせ', combined, re.I):
                return 'subject'
            return 'other'

        # 3. type属性で一意特定
        if field_type in TYPE_CATEGORY_MAP:
            return TYPE_CATEGORY_MAP[field_type]

        # 4. textarea → message（ただし後のname/labelで上書きされる可能性あり）
        textarea_default = field_type == 'textarea'

        # 5. name/id属性パターン
        for name_text in [name, field_id]:
            if not name_text:
                continue
            for pattern, cat in NAME_PATTERNS:
                if re.search(pattern, name_text):
                    # 除外パターンチェック
                    excludes = NAME_EXCLUDE.get(cat, [])
                    if any(re.search(ex, name_text) for ex in excludes):
                        continue
                    return cat

        # 6. placeholder/label/aria-labelパターン
        for text in [placeholder, label, aria_label]:
            if not text:
                continue
            for pattern, cat in LABEL_PATTERNS:
                if re.search(pattern, text, re.I):
                    return cat

        # 7. メールアドレス形式のplaceholder
        if placeholder and re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]+', raw['placeholder']):
            return 'email'

        # 8. textareaデフォルト
        if textarea_default:
            return 'message'

        # 9. select: optionsからsubject/prefecture推定
        if field_type == 'select' and raw.get('options'):
            opt_texts = ' '.join(o.get('text', '') for o in raw['options'])
            if re.search(r'北海道|東京|大阪|福岡|都道府県', opt_texts):
                return 'prefecture'
            if re.search(r'お問い合わせ|ご相談|サービス|その他', opt_texts):
                return 'subject'

        return 'other'

    # ====== 分割フィールド検出 ======

    def _detect_split_fields(self, fields: List[Dict]) -> List[Dict]:
        """連続する短いinputを電話番号/郵便番号分割として検出"""
        # phone1/2/3, zipcode1/2 は既にname属性パターンで検出済み
        # ここでは未検出の分割パターンを補完
        for i in range(len(fields) - 2):
            f1, f2, f3 = fields[i], fields[i+1], fields[i+2]
            # 3連続のphone系 → phone1/2/3
            if (f1.get('field_category') == 'phone' and
                f2.get('field_category') == 'phone' and
                f3.get('field_category') == 'phone'):
                fields[i]['field_category'] = 'phone1'
                fields[i+1]['field_category'] = 'phone2'
                fields[i+2]['field_category'] = 'phone3'

        for i in range(len(fields) - 1):
            f1, f2 = fields[i], fields[i+1]
            # 2連続のzipcode系 → zipcode1/2
            if (f1.get('field_category') == 'zipcode' and
                f2.get('field_category') == 'zipcode'):
                fields[i]['field_category'] = 'zipcode1'
                fields[i+1]['field_category'] = 'zipcode2'

        return fields

    # ====== NG判定 ======

    def _detect_ng(self, url: str, fields: List[Dict]) -> Tuple[bool, Optional[str]]:
        """URLパス+フィールドラベルからNG判定"""
        from urllib.parse import urlparse
        path = urlparse(url).path.lower()

        ng_rules = {
            'ng_recruit': {
                'path': ['recruit', 'career', 'entry', 'jobs', 'hiring', 'saiyo'],
                'label': ['応募', 'エントリー', '志望動機', '履歴書', '希望職種'],
            },
            'ng_reserve': {
                'path': ['reserve', 'booking', 'reservation', 'yoyaku'],
                'label': ['予約日', '来店日', '人数', 'チェックイン', '宿泊'],
            },
            'ng_login': {
                'path': ['login', 'signin', 'signup', 'register'],
                'label': ['パスワード', 'ログイン', '会員登録'],
            },
        }

        field_labels = ' '.join(f.get('label', '') for f in fields).lower()

        for ng_type, rules in ng_rules.items():
            path_match = any(p in path for p in rules['path'])
            label_match = any(l in field_labels for l in rules['label'])
            if path_match and label_match:
                return True, ng_type
            # path_matchだけでも判定（ラベルがなくてもURLパターンが強い場合）
            if path_match and any(p in path for p in ['recruit', 'login', 'signup']):
                return True, ng_type

        return False, None

    # ====== ユーティリティ ======

    def _estimate_time(self, recaptcha_type: str, field_count: int) -> int:
        """推定実行時間（秒）"""
        base = 10
        if recaptcha_type == 'v2':
            base += 30
        return base + field_count * 2
