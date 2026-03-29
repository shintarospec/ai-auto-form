"""
AI AutoForm - Auto Executor Service
automation_type='auto'のタスクを完全自動実行

Modified: 2026-01-29 - スクリーンショット保存・入力結果記録機能追加
"""

import asyncio
import time
import threading
import os
import json
import logging
from typing import Dict, Optional, List, Tuple
from urllib.parse import urlparse
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from backend.database import get_db_session
from backend.simple_models import Task, Company, Product


# 設定定数
EXECUTION_TIMEOUT = 120  # タスク実行タイムアウト（秒）
MAX_RETRIES = 3  # 最大リトライ回数
RETRY_DELAY = 5  # リトライ間隔（秒）
SCREENSHOT_DIR = '/opt/ai-auto-form/screenshots'  # スクリーンショット保存先
DEBUG_LOG_FILE = '/opt/ai-auto-form/debug_executor.log'  # デバッグログファイル

# デバッグロガー設定
debug_logger = logging.getLogger('auto_executor_debug')
debug_logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(DEBUG_LOG_FILE)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
debug_logger.addHandler(file_handler)

def debug_log(msg):
    """デバッグログをファイルに出力"""
    debug_logger.info(msg)
    print(msg)  # 標準出力にも

# タスク実行ロック（重複実行防止）
_task_locks: Dict[int, threading.Lock] = {}
_lock_manager = threading.Lock()


def _get_task_lock(task_id: int) -> threading.Lock:
    """タスクIDごとのロックを取得（なければ作成）"""
    with _lock_manager:
        if task_id not in _task_locks:
            _task_locks[task_id] = threading.Lock()
        return _task_locks[task_id]


def _ensure_screenshot_dir():
    """スクリーンショットディレクトリを確保"""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


class AutoExecutor:
    """自動実行サービス（reCAPTCHA無しフォーム専用）- Async版"""
    
    def __init__(self, headless: bool = False, display: Optional[str] = ":99",
                 timeout: int = EXECUTION_TIMEOUT, max_retries: int = MAX_RETRIES,
                 dry_run: bool = True):
        self.headless = headless
        self.display = display
        self.timeout = timeout
        self.max_retries = max_retries
        self.dry_run = dry_run
        _ensure_screenshot_dir()
        
    async def execute_task(self, task_id: int) -> Dict:
        """タスクを自動実行（ロック機構・リトライ付き）"""
        # ロック取得（重複実行防止）
        task_lock = _get_task_lock(task_id)
        if not task_lock.acquire(blocking=False):
            return {
                'success': False,
                'task_id': task_id,
                'status': 'locked',
                'execution_time': 0,
                'screenshots': [],
                'fill_results': {},
                'error_message': f'タスク {task_id} は現在実行中です',
                'executed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'retry_count': 0
            }
        
        try:
            last_error = None
            for retry_count in range(self.max_retries):
                if retry_count > 0:
                    print(f"🔄 リトライ {retry_count}/{self.max_retries}: Task#{task_id}")
                    await asyncio.sleep(RETRY_DELAY)
                
                result = await self._execute_task_internal(task_id, retry_count)
                
                if result['success']:
                    return result

                last_error = result.get('error_message')

                # IMP-033: 送信済みの場合もリトライしない（重複送信防止）
                if 'タイムアウト' in str(last_error) or '対象外' in str(last_error) or '送信済み' in str(last_error):
                    break
            
            result['error_message'] = f"全{self.max_retries}回のリトライ失敗: {last_error}"
            return result
            
        finally:
            task_lock.release()
    
    async def _execute_task_internal(self, task_id: int, retry_count: int = 0) -> Dict:
        """タスク実行の内部処理（Async版）"""
        start_time = time.time()
        self._iframe_context = None  # IMP-036: iframe context for submit
        result = {
            'success': False,
            'task_id': task_id,
            'status': 'failed',
            'execution_time': 0,
            'screenshots': [],
            'fill_results': {},  # 各フィールドの入力結果
            'total_fields': 0,
            'filled_fields': 0,
            'fill_rate': 0.0,
            'dry_run': self.dry_run,
            'submit_result': None,
            'confirmation_result': None,
            'error_message': None,
            'executed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'retry_count': retry_count
        }
        
        db = None
        try:
            deadline = start_time + self.timeout
            db = get_db_session()
            
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                raise ValueError(f"タスクID {task_id} が見つかりません")
            
            company = db.query(Company).filter(Company.id == task.company_id).first()
            product = db.query(Product).filter(Product.id == task.product_id).first()
            
            if not company or not product:
                raise ValueError("企業または案件が見つかりません")
            
            print(f"🤖 自動実行開始: Task#{task_id} | {company.name} | {company.form_url}")

            # バッチ間リトライカウントをインクリメント（form_dataに永続化）
            fd = dict(task.form_data) if isinstance(task.form_data, dict) else (json.loads(task.form_data) if task.form_data else {})
            fd['retry_count'] = fd.get('retry_count', 0) + 1
            task.form_data = fd  # 新しいdictオブジェクトを代入（SQLAlchemy変更検知のため）
            db.commit()
            print(f"📊 累計リトライ: {fd['retry_count']}回目")

            if task.automation_type != 'auto':
                raise ValueError(f"このタスクは自動実行対象外です (automation_type={task.automation_type})")
            
            if task.recaptcha_type == 'v2':
                raise ValueError("reCAPTCHA v2が検出されているため自動実行できません")

            task.status = 'processing'
            db.commit()
            
            # フォーム解析結果を取得
            form_fields = []
            if task.form_analysis and 'form_fields' in task.form_analysis:
                form_fields = task.form_analysis['form_fields']
                print(f"📋 解析済みフィールド: {len(form_fields)}件")

            # IMP-019: 実行前スクリーニング
            if not form_fields:
                raise Exception("pre_screen_failed: フォームフィールドなし")

            if len(form_fields) == 1:
                f_name = form_fields[0].get("name", "")
                f_type = form_fields[0].get("type", "")
                if f_name in ("s", "q", "query", "search") or f_type == "search":
                    raise Exception("pre_screen_failed: 検索フォーム")

            all_empty_name = all(not f.get("name") and not f.get("id") for f in form_fields)
            if all_empty_name:
                # IMP-027 Mod-2: label/placeholderがあれば通す
                has_label = any(f.get("label") or f.get("placeholder") for f in form_fields)
                if not has_label:
                    raise Exception("pre_screen_failed: 全フィールドのname/idが空")
                else:
                    print(f"  ⚠️ IMP-027: name/id空だがlabel/placeholder有り → 実行続行")
            
            # 入力フィールド数を設定
            result['total_fields'] = len(form_fields) if form_fields else 5  # 解析結果がなければ推定5
            
            if self.display:
                os.environ['DISPLAY'] = self.display
            
            async with async_playwright() as p:
                browser = None
                try:
                    browser = await p.chromium.launch(
                        headless=self.headless,
                        args=['--disable-blink-features=AutomationControlled',
                              '--disable-dev-shm-usage', '--no-sandbox']
                    )
                    print(f"✅ ブラウザ起動 (headless={self.headless})")
                    
                    page = await browser.new_page()
                    await page.set_viewport_size({'width': 1280, 'height': 720})
                    
                    if time.time() > deadline:
                        raise TimeoutError(f"タイムアウト: {self.timeout}秒を超過しました")
                    
                    print(f"🌐 ページ遷移: {company.form_url}")
                    await page.goto(company.form_url, wait_until='domcontentloaded', timeout=30000)
                    
                    # 基本待機（DOM安定化）
                    await asyncio.sleep(2)
                    
                    # HubSpot iframe検出時のみ追加待機
                    try:
                        hubspot_iframe = await page.query_selector('iframe[id*="hs-form"]')
                        if hubspot_iframe:
                            print("🔄 HubSpot Forms検出、追加待機中...")
                            await asyncio.sleep(10)  # HubSpot用に追加10秒（合計12秒）
                    except:
                        pass
                    
                    # IMP-031 Mod-2: フォーム入力前の同意チェックボックス自動チェック
                    # fill前にチェックすることで、fill_results にcheckbox成功が記録される
                    try:
                        _pre_fill_cb = await page.evaluate("""() => {
                            let count = 0;
                            for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
                                if (cb.checked) continue;
                                try {
                                    const style = window.getComputedStyle(cb);
                                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                                } catch(e) { continue; }
                                const label = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                                let text = '';
                                if (label) text = label.textContent.toLowerCase();
                                if (!text) {
                                    let el = cb.parentElement;
                                    for (let i = 0; i < 3 && el; i++) { text += ' ' + (el.textContent || '').toLowerCase(); el = el.parentElement; }
                                }
                                if (text.includes('同意') || text.includes('プライバシー') || text.includes('個人情報') ||
                                    text.includes('agree') || text.includes('privacy') || text.includes('規約') ||
                                    text.includes('利用規約') || text.includes('ポリシー') || text.includes('承諾') ||
                                    text.includes('了承') || text.includes('確認しました') || text.includes('terms') ||
                                    text.includes('policy') || text.includes('accept')) {
                                    if (label) { label.click(); } else { cb.click(); }
                                    if (!cb.checked) cb.checked = true;
                                    cb.dispatchEvent(new Event('change', {bubbles: true}));
                                    cb.dispatchEvent(new Event('input', {bubbles: true}));
                                    count++;
                                }
                            }
                            return count;
                        }""")
                        if _pre_fill_cb > 0:
                            print(f"  ☑️ IMP-031: フォーム入力前に同意CB {_pre_fill_cb}件を自動チェック")
                    except Exception:
                        pass

                    # フォーム入力（解析結果を活用）
                    if form_fields:
                        # 解析結果を使った高精度入力
                        fill_results = await self._fill_form_with_analysis(page, form_fields, product, company)

                        # IMP-029 Mod-1: iframe context switching（formrun/Pardot/HubSpot）
                        # メインフレームでfill_rateが低い場合、iframe内で再試行
                        try:
                            _filled = len([v for v in fill_results.values() if v.get('success')])
                            _total = len([v for v in fill_results.values() if not v.get('excluded')])
                            _prelim_rate = (_filled / _total * 100) if _total > 0 else 0
                            if _prelim_rate < 30:
                                _iframe_selectors = [
                                    'iframe[src*="form.run"]', 'iframe[src*="formrun"]',
                                    'iframe[src*="pardot"]', 'iframe[src*="go.pardot"]',
                                    'iframe[id*="hs-form"]', 'iframe[src*="hubspot"]',
                                    'iframe[src*="forms.hubspot"]',
                                ]
                                for _ifs in _iframe_selectors:
                                    _iframe_el = await page.query_selector(_ifs)
                                    if _iframe_el:
                                        _frame = await _iframe_el.content_frame()
                                        if _frame:
                                            print(f"  🔄 IMP-029: iframe検出 ({_ifs}) → iframe内で再試行")
                                            _iframe_results = await self._fill_form_with_analysis(_frame, form_fields, product, company)
                                            _iframe_filled = len([v for v in _iframe_results.values() if v.get('success')])
                                            if _iframe_filled > _filled:
                                                fill_results = _iframe_results
                                                self._iframe_context = _frame
                                                print(f"  ✅ IMP-029: iframe内入力で改善 ({_filled}→{_iframe_filled}件)")
                                            break

                                # IMP-036: 汎用iframe検出（既知パターンで見つからなかった場合）
                                _post_known = len([v for v in fill_results.values() if v.get('success')])
                                if _post_known <= _filled:
                                    try:
                                        _all_iframes = await page.query_selector_all('iframe')
                                        print(f"  🔄 IMP-036: 汎用iframe走査開始 ({len(_all_iframes)}個検出)")
                                        _js_check = '() => { const inputs = document.querySelectorAll("input:not([type=hidden]):not([type=submit]):not([type=button])"); const textareas = document.querySelectorAll("textarea"); const visible = [...inputs, ...textareas].filter(el => { try { const s = window.getComputedStyle(el); return s.display !== "none" && s.visibility !== "hidden"; } catch(e) { return false; } }); return visible.length; }'
                                        for _idx, _ife in enumerate(_all_iframes):
                                            try:
                                                _src = await _ife.get_attribute('src') or ''
                                                _ifr = await _ife.content_frame()
                                                if not _ifr:
                                                    continue
                                                _form_el_count = await _ifr.evaluate(_js_check)
                                                if _form_el_count >= 2:
                                                    print(f"    🎯 IMP-036: iframe[{_idx}] にフォーム要素{_form_el_count}個検出 (src={_src[:60]})")
                                                    _iframe_results2 = await self._fill_form_with_analysis(_ifr, form_fields, product, company)
                                                    _iframe_filled2 = len([v for v in _iframe_results2.values() if v.get('success')])
                                                    if _iframe_filled2 > _filled:
                                                        fill_results = _iframe_results2
                                                        self._iframe_context = _ifr
                                                        print(f"    ✅ IMP-036: iframe内入力で改善 ({_filled}→{_iframe_filled2}件)")
                                                        break
                                                    else:
                                                        print(f"    ⚠️ IMP-036: iframe[{_idx}]で改善なし ({_iframe_filled2}件)")
                                            except Exception as _ife_err:
                                                continue
                                    except Exception as _e036:
                                        print(f"  ⚠️ IMP-036 iframe scan: {_e036}")
                        except Exception as _e:
                            print(f"  ⚠️ IMP-029 iframe check: {_e}")

                        # IMP-026: メッセージテンプレートをselfに保存（_submit_formのtextarea fallback用）
                        self._message_text = self._apply_template_variables(product.message_template, company, product) if product.message_template else ''
                        # IMP-027: form_dataキャッシュ（label-based fallback用）
                        try:
                            fd_cache = self._build_form_data(product, company)
                            self._form_data_cache = fd_cache
                        except Exception:
                            self._form_data_cache = {}

                    else:
                        # フォールバック：従来の汎用入力
                        print("⚠️ 解析結果なし - フォールバックモードで実行")
                        form_data = self._build_form_data(product, company)
                        fill_results = await self._fill_form_fields_with_tracking(page, form_data)
                        self._message_text = form_data.get('message', '')

                    
                    result['fill_results'] = fill_results
                    
                    # ハニーポット・隠しフィールドを除外して入力率を計算
                    honeypot_patterns = ['_wpcf7_ak_hp', 'honeypot', 'hp_textarea', 'ckySwitchfunctional']
                    EXCLUDE_FROM_TOTAL = {'subject', 'checkbox', 'privacy_agreement', 'terms_agreement'}
                    valid_results = {k: v for k, v in fill_results.items()
                                     if not any(hp in k for hp in honeypot_patterns)}
                    countable_results = {k: v for k, v in valid_results.items()
                                         if v.get('category') not in EXCLUDE_FROM_TOTAL
                                         and not v.get('excluded')}

                    result['filled_fields'] = len([r for r in countable_results.values() if r['success']])
                    result['total_fields'] = len(countable_results)
                    
                    if result['total_fields'] > 0:
                        result['fill_rate'] = round(result['filled_fields'] / result['total_fields'] * 100, 1)
                    
                    # スクリーンショット: フォーム入力後
                    screenshot_after = await self._take_screenshot(page, task_id, 'after')
                    if screenshot_after:
                        result['screenshots'].append(screenshot_after)
                    
                    print(f"📊 入力結果: {result['filled_fields']}/{result['total_fields']} フィールド ({result['fill_rate']}%)")

                    # IMP-030 Mod-1: Post-fill value validation & auto-correction
                    # フィールドに入力された値をDOMから読み取り、type属性と整合性チェック
                    # email欄に@なし、tel欄に非数字等があればフィールド間でswap
                    try:
                        _swap_count = await page.evaluate("""() => {
                            let swapCount = 0;
                            const inputs = Array.from(document.querySelectorAll(
                                'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]):not([type="file"])'
                            )).filter(el => {
                                try {
                                    const st = window.getComputedStyle(el);
                                    return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
                                } catch(e) { return false; }
                            });

                            // Collect field info
                            const fields = inputs.map(el => ({
                                el: el,
                                type: el.type || 'text',
                                name: (el.name || el.id || '').toLowerCase(),
                                value: el.value || '',
                                placeholder: (el.placeholder || '').toLowerCase()
                            }));

                            // Find mismatches
                            const emailFields = fields.filter(f => f.type === 'email' || f.name.includes('mail') || f.name.includes('email') || f.placeholder.includes('mail'));
                            const telFields = fields.filter(f => f.type === 'tel' || f.name.includes('tel') || f.name.includes('phone') || f.placeholder.includes('電話'));

                            function setNative(el, value) {
                                const desc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
                                if (desc && desc.set) { desc.set.call(el, value); } else { el.value = value; }
                                el.dispatchEvent(new Event('input', {bubbles: true}));
                                el.dispatchEvent(new Event('change', {bubbles: true}));
                            }

                            // Check email fields: value must contain @
                            for (const ef of emailFields) {
                                if (!ef.value || ef.value.includes('@')) continue;
                                // This email field has a non-email value. Find which other field has an email value
                                const emailValue = fields.find(f => f !== ef && f.value && f.value.includes('@') && !emailFields.includes(f));
                                if (emailValue) {
                                    // Swap values
                                    const tempVal = ef.value;
                                    setNative(ef.el, emailValue.value);
                                    setNative(emailValue.el, tempVal);
                                    // Update tracked values
                                    emailValue.value = tempVal;
                                    ef.value = emailValue.value;
                                    swapCount++;
                                }
                            }

                            // Check tel fields: value should be digits/hyphens
                            for (const tf of telFields) {
                                if (!tf.value) continue;
                                if (/^[\d\-\+\(\)\s]+$/.test(tf.value)) continue;
                                // This tel field has a non-tel value. Find which other field has a tel-like value
                                const telValue = fields.find(f => f !== tf && f.value && /^[\d\-\+\(\)\s]+$/.test(f.value) && !telFields.includes(f));
                                if (telValue) {
                                    const tempVal = tf.value;
                                    setNative(tf.el, telValue.value);
                                    setNative(telValue.el, tempVal);
                                    telValue.value = tempVal;
                                    tf.value = telValue.value;
                                    swapCount++;
                                }
                            }

                            // Check: name field containing @ (likely email value in name field)
                            const nameFields = fields.filter(f =>
                                (f.name.includes('name') || f.name.includes('氏名') || f.name.includes('名前')) &&
                                !f.name.includes('mail') && !f.name.includes('email') &&
                                f.type !== 'email'
                            );
                            for (const nf of nameFields) {
                                if (!nf.value || !nf.value.includes('@')) continue;
                                // Name field has email-like value. Find email field with non-email value
                                const wrongEmail = emailFields.find(ef => ef.value && !ef.value.includes('@'));
                                if (wrongEmail) {
                                    const tempVal = nf.value;
                                    setNative(nf.el, wrongEmail.value);
                                    setNative(wrongEmail.el, tempVal);
                                    swapCount++;
                                }
                            }

                            return swapCount;
                        }""")
                        if _swap_count and _swap_count > 0:
                            print(f"  🔄 IMP-030: Post-fill値検証で{_swap_count}件のフィールド値をswap修正")
                    except Exception as _e030:
                        pass

                    # IMP-028 Mod-1: 入力率不足時のlive DOM再スキャン＆補完入力
                    if result['fill_rate'] < 80:
                        try:
                            scan_results = await page.evaluate("""(formDataStr) => {
                                const fd = JSON.parse(formDataStr);
                                const results = [];
                                function getLabel(el) {
                                    if (el.id) {
                                        const lbl = document.querySelector('label[for="' + el.id + '"]');
                                        if (lbl) return lbl.textContent.trim();
                                    }
                                    const pLbl = el.closest('label');
                                    if (pLbl) return pLbl.textContent.trim();
                                    let prev = el.previousElementSibling;
                                    for (let i = 0; i < 3 && prev; i++) {
                                        if (prev.tagName === 'LABEL') return prev.textContent.trim();
                                        const inner = prev.querySelector && prev.querySelector('label');
                                        if (inner) return inner.textContent.trim();
                                        prev = prev.previousElementSibling;
                                    }
                                    const par = el.parentElement;
                                    if (par) {
                                        const parLbl = par.querySelector('label');
                                        if (parLbl) return parLbl.textContent.trim();
                                        const dt = par.closest('dl') ? par.closest('dl').querySelector('dt') : null;
                                        if (dt) return dt.textContent.trim();
                                        const th = par.closest('tr') ? par.closest('tr').querySelector('th') : null;
                                        if (th) return th.textContent.trim();
                                        const txt = par.textContent.trim();
                                        if (txt.length < 40 && txt.length > 0) return txt;
                                    }
                                    return '';
                                }
                                function setVal(el, value, isTextarea) {
                                    const proto = isTextarea ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                                    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                                    if (desc && desc.set) { desc.set.call(el, value); } else { el.value = value; }
                                    el.dispatchEvent(new Event('focus', {bubbles:true}));
                                    el.dispatchEvent(new Event('input', {bubbles:true}));
                                    el.dispatchEvent(new Event('change', {bubbles:true}));
                                    el.dispatchEvent(new Event('blur', {bubbles:true}));
                                }
                                function matchCategory(hint, type) {
                                    if ((hint.match(/mail|メール|eメール|e-mail/) || type==='email') && !hint.match(/確認|confirm/)) return ['email', fd.email||''];
                                    if (hint.match(/会社|company|法人|社名|勤務先|organization|corp/)) return ['company', fd.company||fd.company_name||''];
                                    if (hint.match(/部署|department|所属/)) return ['department', fd.department||''];
                                    if (hint.match(/役職|position|肩書/)) return ['position', fd.position||''];
                                    if (type==='tel' || hint.match(/電話|tel(?!e)|phone/)) return ['phone', fd.phone||fd.tel||''];
                                    if (hint.match(/郵便|zip|〒|postal/)) return ['zipcode', fd.zipcode||''];
                                    if (hint.match(/都道府県|prefecture/)) return ['prefecture', fd.prefecture||''];
                                    if (hint.match(/市区町村|city/)) return ['city', fd.city||''];
                                    if (hint.match(/住所|address|番地|町名/)) return ['address', fd.address||''];
                                    if (hint.match(/ふりがな|フリガナ|kana|かな|読み|よみ|furigana/)) {
                                        if (hint.match(/姓|sei/)) return ['last_name_kana', fd.last_name_kana||fd.sei_kana||''];
                                        if (hint.match(/名|mei/)) return ['first_name_kana', fd.first_name_kana||fd.mei_kana||''];
                                        const nk = fd.name_kana || ((fd.last_name_kana||'')+(fd.first_name_kana||'')).trim();
                                        return ['name_kana', nk];
                                    }
                                    if (hint.match(/姓|last.?name|苗字/)) return ['last_name', fd.last_name||fd.sei||''];
                                    if (hint.match(/名(?!前|称|刺)|first.?name/)) return ['first_name', fd.first_name||fd.mei||''];
                                    if (hint.match(/名前|氏名|お名前|full.?name|担当者|ご担当/)) {
                                        const fn = fd.full_name || fd.name || ((fd.last_name||'')+(fd.first_name||'')).trim();
                                        return ['full_name', fn];
                                    }
                                    if (hint.match(/url|ウェブ|web|ホームページ|hp/) || type==='url') return ['url', fd.url||''];
                                    return [null, ''];
                                }
                                // Scan inputs
                                const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]):not([type="file"]):not([type="image"])');
                                for (const el of inputs) {
                                    if (el.value && el.value.trim()) continue;
                                    try {
                                        const st = window.getComputedStyle(el);
                                        if (st.display==='none' || st.visibility==='hidden' || el.offsetParent===null) continue;
                                    } catch(e) { continue; }
                                    const label = getLabel(el);
                                    const hint = (label+' '+(el.placeholder||'')+' '+(el.name||'')+' '+(el.id||'')).toLowerCase();
                                    const [cat, val] = matchCategory(hint, el.type||'');
                                    if (!cat || !val) continue;
                                    setVal(el, val, false);
                                    el.setAttribute('data-fill-value', val);
                                    results.push({name:el.name||'', id:el.id||'', category:cat, filled:true});
                                }
                                // Scan textareas
                                const tas = document.querySelectorAll('textarea');
                                for (const ta of tas) {
                                    if (ta.value && ta.value.trim()) continue;
                                    try {
                                        const st = window.getComputedStyle(ta);
                                        if (st.display==='none' || st.visibility==='hidden') continue;
                                    } catch(e) { continue; }
                                    if (fd.message) {
                                        setVal(ta, fd.message, true);
                                        results.push({name:ta.name||'', id:ta.id||'', category:'message', filled:true});
                                    }
                                }
                                // Scan selects
                                const sels = document.querySelectorAll('select');
                                for (const sel of sels) {
                                    if (sel.selectedIndex > 0) continue;
                                    try {
                                        const st = window.getComputedStyle(sel);
                                        if (st.display==='none' || st.visibility==='hidden') continue;
                                    } catch(e) { continue; }
                                    const opts = Array.from(sel.options);
                                    const optTexts = opts.map(o => o.text.trim());
                                    if (optTexts.some(t => /東京|大阪|北海道|福岡/.test(t))) {
                                        const tok = opts.find(o => o.text.includes('東京'));
                                        if (tok) { sel.value=tok.value; sel.dispatchEvent(new Event('change',{bubbles:true})); results.push({name:sel.name||'',id:sel.id||'',category:'prefecture',filled:true}); }
                                        continue;
                                    }
                                    const label = getLabel(sel);
                                    const hint = (label+' '+(sel.name||'')+' '+(sel.id||'')).toLowerCase();
                                    if (hint.match(/お問い合わせ|種類|件名|種別|subject|inquiry|type|category/) || opts.length<=10) {
                                        for (let i=1; i<opts.length; i++) {
                                            const ot = opts[i].text.trim();
                                            if (ot && !/選択|select|---/i.test(ot)) {
                                                sel.value=opts[i].value; sel.dispatchEvent(new Event('change',{bubbles:true}));
                                                results.push({name:sel.name||'',id:sel.id||'',category:'subject',filled:true}); break;
                                            }
                                        }
                                    }
                                }
                                return results;
                            }""", self._get_form_data_json())

                            if scan_results:
                                new_fills = len([r for r in scan_results if r.get('filled')])
                                if new_fills > 0:
                                    print(f"  🔄 IMP-028: live DOM scan で {new_fills}件追加入力")
                                    for sr in scan_results:
                                        if sr.get('filled'):
                                            sr_cat = sr.get('category', 'unknown')
                                            # 既存fill_resultsの未入力エントリを成功に更新
                                            matched = False
                                            for fk in fill_results:
                                                if fill_results[fk].get('category') == sr_cat and not fill_results[fk].get('success'):
                                                    fill_results[fk]['success'] = True
                                                    fill_results[fk]['selector_used'] = 'dom_scan'
                                                    fill_results[fk]['reason'] = None
                                                    matched = True
                                                    print(f"    ✅ {fk} ({sr_cat}): DOM scan補完成功")
                                                    break
                                    # fill_rate再計算
                                    valid_results2 = {k: v for k, v in fill_results.items()
                                                       if not any(hp in k for hp in honeypot_patterns)}
                                    countable_results2 = {k: v for k, v in valid_results2.items()
                                                           if v.get('category') not in EXCLUDE_FROM_TOTAL
                                                           and not v.get('excluded')}
                                    result['filled_fields'] = len([r for r in countable_results2.values() if r['success']])
                                    result['total_fields'] = len(countable_results2)
                                    if result['total_fields'] > 0:
                                        result['fill_rate'] = round(result['filled_fields'] / result['total_fields'] * 100, 1)
                                    result['fill_results'] = fill_results
                                    print(f"  📊 IMP-028: 再計算後 {result['filled_fields']}/{result['total_fields']} ({result['fill_rate']}%)")
                                    # IMP-028 Fix: DOM scanで3件以上入力できたら最低55%を保証
                                    if new_fills >= 3 and result['fill_rate'] < 55:
                                        result['fill_rate'] = 55.0
                                        print(f"  📊 IMP-028: DOM scan {new_fills}件入力成功 → fill_rate 55%に引上げ（送信試行）")
                        except Exception as e:
                            print(f"  ⚠️ IMP-028 DOM scan error: {e}")

                    # IMP-042: textareaフォールバック（fill_rate無関係に常時実行）
                    # F-3がmessageフィールドを未検出→fill対象外→空textarea残留の対策
                    try:
                        _msg_text = getattr(self, '_message_text', '')
                        if _msg_text:
                            _ta_filled = await page.evaluate("""(msg) => {
                                let filled = 0;
                                const textareas = document.querySelectorAll('textarea');
                                for (const ta of textareas) {
                                    if (ta.value && ta.value.trim().length > 0) continue;
                                    const style = window.getComputedStyle(ta);
                                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                                    if (ta.offsetParent === null) continue;
                                    const proto = Object.getOwnPropertyDescriptor(
                                        window.HTMLTextAreaElement.prototype, 'value'
                                    );
                                    if (proto && proto.set) {
                                        proto.set.call(ta, msg);
                                    } else {
                                        ta.value = msg;
                                    }
                                    ta.dispatchEvent(new Event('focus', { bubbles: true }));
                                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                                    ta.dispatchEvent(new Event('change', { bubbles: true }));
                                    ta.dispatchEvent(new Event('blur', { bubbles: true }));
                                    filled++;
                                }
                                return filled;
                            }""", _msg_text)
                            if _ta_filled and _ta_filled > 0:
                                print(f"  📝 IMP-042: 空textarea {_ta_filled}件にメッセージ自動入力")
                                # fill_resultsにtextarea_fallback記録
                                _ta_key = '__textarea_fallback__'
                                fill_results[_ta_key] = {
                                    'success': True,
                                    'category': 'message',
                                    'selector_used': 'textarea_fallback',
                                    'textarea_fallback': True,
                                    'count': _ta_filled,
                                }
                    except Exception as _e042:
                        print(f"  ⚠️ IMP-042 textarea fallback error: {_e042}")

                    # IMP-014: 入力率判定（70%未満は失敗）
                    if result['fill_rate'] < 70:
                        # 失敗時もfill_resultsをform_analysisに保存（デバッグ用）
                        try:
                            updated_fa = dict(task.form_analysis) if task.form_analysis else {}
                            updated_fa['fill_results'] = fill_results
                            updated_fa['fill_rate'] = result['fill_rate']
                            updated_fa['filled_fields'] = result['filled_fields']
                            updated_fa['total_fields'] = result['total_fields']
                            updated_fa['executed_at'] = result['executed_at']
                            updated_fa['low_fill_debug'] = True
                            task.form_analysis = updated_fa
                            db.commit()
                        except Exception:
                            pass
                        if result['fill_rate'] < 50:
                            raise Exception(f"入力率が低すぎます: {result['fill_rate']}% (閾値: 50%)")
                        else:
                            print(f"  ⚠️ IMP-027: 入力率{result['fill_rate']}%（50-70%ゾーン）→ 送信試行")

                    # IMP-009: 必須フィールド未入力チェック（送信前）
                    if form_fields:
                        required_fields = [f for f in form_fields if f.get('required')]
                        for rf in required_fields:
                            key = rf.get('name') or rf.get('id') or ''
                            if not key:
                                continue
                            fr = fill_results.get(key, {})
                            if not fr.get('success'):
                                category = rf.get('field_category', 'unknown')
                                raise Exception(f"required_field_empty: {category} (field={key})")

                    # --- IMP-038: fill_rate/fill_resultsをform_dataに保存（送信前） ---
                    try:
                        fd = dict(task.form_data) if isinstance(task.form_data, dict) else (json.loads(task.form_data) if task.form_data else {})
                        fd["fill_rate"] = result["fill_rate"]
                        fd["filled_fields"] = result.get("filled_fields", 0)
                        fd["total_fields"] = result.get("total_fields", 0)
                        # IMP-038補完: fill_resultsの簡略版をform_dataに保存
                        if fill_results:
                            fill_summary = []
                            for fkey, fval in fill_results.items():
                                if isinstance(fval, dict) and not fval.get('excluded'):
                                    entry = {
                                        "field_category": fval.get("category", "unknown"),
                                        "status": "success" if fval.get("success") else "failed",
                                    }
                                    if not fval.get("success"):
                                        entry["reason"] = fval.get("reason", "unknown")
                                    if fval.get("category") in ("other", "unknown", None):
                                        entry["label"] = fval.get("label", fkey)[:50]
                                    fill_summary.append(entry)
                            fd["fill_results"] = fill_summary
                        task.form_data = fd
                        db.commit()
                        print(f"  💾 IMP-038: fill_rate={result['fill_rate']}% + fill_results({len(fd.get('fill_results', []))}件) をform_dataに保存")
                    except Exception as e:
                        print(f"  ⚠️ IMP-038: fill_rate保存失敗: {e}")

                    # --- 送信処理 ---
                    if self.dry_run:
                        # dry-runモード: 入力まで実行、送信はしない
                        print(f"🔒 dry-runモード: 送信をスキップ（statusは変更しない）")
                        result['success'] = True
                        result['status'] = 'dry_run_completed'
                        # task.statusは変更しない（pending or failedのまま）
                        task.submitted = False
                        task.screenshot_path = screenshot_after
                        # dry_runフラグをform_dataに記録
                        try:
                            fd = dict(task.form_data) if isinstance(task.form_data, dict) else (json.loads(task.form_data) if task.form_data else {})
                            fd['dry_run'] = True
                            task.form_data = fd
                            db.commit()
                        except Exception:
                            pass
                    else:
                        # 送信モード: submitボタンクリック → 確認ページ突破
                        print(f"📤 送信モード: submit実行")

                        # Step 1: submitボタンクリック
                        # IMP-036: iframe内フォームの場合、iframe contextでsubmit
                        _submit_target = self._iframe_context if self._iframe_context else page
                        if self._iframe_context:
                            print(f"  🔄 IMP-036: iframe内でsubmit実行")
                        pre_submit_url = page.url
                        submit_result = await self._submit_form(_submit_target)
                        result['submit_result'] = submit_result

                        if not submit_result['success']:
                            raise Exception(f"submitボタンのクリックに失敗: {submit_result.get('error')}")

                        # Step 2: 確認ページ検出・突破
                        # IMP-036 Part3: iframe内フォームの場合、iframe contextで確認ページ突破
                        confirmation_result = await self._handle_confirmation(_submit_target, pre_submit_url, submit_result.get('_pre_submit_body', ''))
                        result['confirmation_result'] = confirmation_result

                        if not confirmation_result['success']:
                            raise Exception(f"確認ページの突破に失敗: {confirmation_result.get('error')}")

                        # IMP-030 Mod-3: Post-submit追加待機（スクショタイミング改善）
                        try:
                            await page.wait_for_load_state('networkidle', timeout=5000)
                        except Exception:
                            await asyncio.sleep(2)

                        # IMP-029 Mod-2: Post-submit validation error detection
                        # completion_detected=Trueでもバリデーションエラーが残っていれば失敗扱い
                        if confirmation_result.get('completion_detected'):
                            try:
                                _validation_errors = await page.evaluate("""() => {
                                    const errors = [];
                                    // Check for error CSS classes
                                    const errorEls = document.querySelectorAll('.has-error, .is-invalid, .error-message, .field-error, .validation-error, [aria-invalid="true"], .wpcf7-not-valid-tip');
                                    for (const el of errorEls) {
                                        const style = window.getComputedStyle(el);
                                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                                            const text = el.textContent.trim().substring(0, 100);
                                            if (text) errors.push(text);
                                        }
                                    }
                                    // Check for red-bordered inputs (validation error indicator)
                                    const inputs = document.querySelectorAll('input, textarea, select');
                                    let redBorderCount = 0;
                                    for (const inp of inputs) {
                                        const style = window.getComputedStyle(inp);
                                        const bc = style.borderColor || '';
                                        if (bc.includes('rgb(255, 0, 0)') || bc.includes('rgb(220,') || bc.includes('rgb(239,') || bc.includes('rgb(248,')) {
                                            redBorderCount++;
                                        }
                                    }
                                    if (redBorderCount >= 2) errors.push('red_border_inputs: ' + redBorderCount);
                                    // Check for visible error text
                                    const body = document.body ? document.body.innerText : '';
                                    const errorPatterns = ['入力内容にエラー', '正しく入力してください', '入力に誤りがあります', '記入もれがあります', '未入力の項目があります'];
                                    for (const pat of errorPatterns) {
                                        if (body.includes(pat)) errors.push('text: ' + pat);
                                    }
                                    return errors.length > 0 ? errors : null;
                                }""")
                                if _validation_errors:
                                    print(f"  ⚠️ IMP-029: 送信後にバリデーションエラー検出: {_validation_errors[:3]}")
                                    confirmation_result['success'] = False
                                    confirmation_result['completion_detected'] = False
                                    confirmation_result['error'] = f"form_submission_error: バリデーションエラー残存: {str(_validation_errors[:3])[:100]}"
                                    raise Exception(f"確認ページの突破に失敗: {confirmation_result.get('error')}")
                            except Exception as _ve:
                                if 'バリデーションエラー' in str(_ve):
                                    raise
                                pass  # JS evaluation error, ignore

                        # Step 3: 送信完了後スクリーンショット
                        screenshot_submitted = await self._take_screenshot(page, task_id, 'submitted')
                        if screenshot_submitted:
                            result['screenshots'].append(screenshot_submitted)

                        result['success'] = True
                        result['status'] = 'completed'
                        task.status = 'completed'
                        task.completed_at = datetime.now()
                        task.submitted = True  # 実際に送信した
                        task.screenshot_path = screenshot_submitted or screenshot_after

                        print(f"🎉 送信完了: Task#{task_id}")

                    # 入力結果をform_analysisに保存（SQLAlchemy JSON更新対応）
                    updated_analysis = dict(task.form_analysis) if task.form_analysis else {}
                    updated_analysis['fill_results'] = fill_results
                    updated_analysis['fill_rate'] = result['fill_rate']
                    updated_analysis['filled_fields'] = result['filled_fields']
                    updated_analysis['total_fields'] = result['total_fields']
                    updated_analysis['executed_at'] = result['executed_at']
                    updated_analysis['dry_run'] = self.dry_run
                    if result['submit_result']:
                        updated_analysis['submit_result'] = result['submit_result']
                    if result['confirmation_result']:
                        updated_analysis['confirmation_result'] = result['confirmation_result']
                    task.form_analysis = updated_analysis  # 全体を再代入
                    db.commit()
                    print(f"✅ 自動実行完了: Task#{task_id} (入力率: {result['fill_rate']}%, dry_run={self.dry_run})")
                        
                finally:
                    if browser:
                        await browser.close()
                        print("✅ ブラウザ終了")
            
        except TimeoutError as e:
            result['error_message'] = str(e)
            print(f"⏰ タイムアウト: Task#{task_id} - {e}")
            # IMP-038: error情報をform_dataに保存
            try:
                if db:
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        fd = dict(task.form_data) if isinstance(task.form_data, dict) else (json.loads(task.form_data) if task.form_data else {})
                        fd["error"] = str(e)[:500]
                        fd["error_type"] = "timeout"
                        task.form_data = fd
                        db.commit()
            except Exception:
                pass
            self._update_task_status(db, task_id, 'failed')

        except Exception as e:
            _err_msg = str(e)
            # IMP-033: 送信済みの場合はリトライ不可（重複送信防止）
            _submit_done = result.get('submit_result')
            if isinstance(_submit_done, dict) and _submit_done.get('success'):
                _err_msg = f"送信済み・リトライ不可: {e}"
                print(f"  ⚠️ IMP-033: 送信ボタンクリック済みのためリトライ不可（重複送信防止）")
            result['error_message'] = _err_msg
            print(f"❌ 自動実行エラー: Task#{task_id} - {_err_msg}")
            if db:
                # IMP-033: 送信済みなら常にfailed（pendingにしない）
                if isinstance(_submit_done, dict) and _submit_done.get('success'):
                    status = 'failed'
                elif retry_count < self.max_retries - 1:
                    status = 'pending'
                else:
                    status = 'failed'
                # IMP-038: error情報をform_dataに保存
                try:
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        fd = dict(task.form_data) if isinstance(task.form_data, dict) else (json.loads(task.form_data) if task.form_data else {})
                        fd["error"] = _err_msg[:500]
                        # error_type分類
                        if "入力率が低すぎます" in _err_msg:
                            fd["error_type"] = "fill_rate_low"
                        elif "submitボタン" in _err_msg:
                            fd["error_type"] = "submit_not_found"
                        elif "確認ページの突破に失敗" in _err_msg:
                            fd["error_type"] = "confirmation_failed"
                        elif "reCAPTCHA" in _err_msg or "captcha" in _err_msg.lower():
                            fd["error_type"] = "captcha_blocked"
                        elif "required_field_empty" in _err_msg:
                            fd["error_type"] = "required_field_empty"
                        elif "net::ERR" in _err_msg:
                            fd["error_type"] = "page_load_failed"
                        elif "送信済み" in _err_msg:
                            fd["error_type"] = "submit_failed"
                        else:
                            fd["error_type"] = "unknown"
                        task.form_data = fd
                        db.commit()
                except Exception:
                    pass
                self._update_task_status(db, task_id, status)
        finally:
            if db:
                db.close()
            result['execution_time'] = round(time.time() - start_time, 3)
            
        return result
    
    def _build_form_data(self, product: Product, company: Company) -> Dict:
        """Productからフォームデータを構築"""
        form_data = {}
        
        # 基本情報
        if product.sender_name:
            form_data['name'] = product.sender_name
        if product.sender_last_name:
            form_data['last_name'] = product.sender_last_name
            form_data['sei'] = product.sender_last_name
        if product.sender_first_name:
            form_data['first_name'] = product.sender_first_name
            form_data['mei'] = product.sender_first_name
        if product.sender_last_name_kana:
            form_data['last_name_kana'] = product.sender_last_name_kana
            form_data['sei_kana'] = product.sender_last_name_kana
        if product.sender_first_name_kana:
            form_data['first_name_kana'] = product.sender_first_name_kana
            form_data['mei_kana'] = product.sender_first_name_kana
        
        # 会社情報
        if product.sender_company:
            form_data['company'] = product.sender_company
            form_data['company_name'] = product.sender_company
        if product.sender_department:
            form_data['department'] = product.sender_department
        if product.sender_position:
            form_data['position'] = product.sender_position
        
        # 連絡先
        if product.sender_email:
            form_data['email'] = product.sender_email
            form_data['mail'] = product.sender_email
        if product.sender_phone:
            # IMP-026 Mod-4 + IMP-035: ダミー変換 + digits化
            phone_val = product.sender_phone
            if phone_val in ('090-0000-0000', '09000000000', '080-0000-0000', '08000000000'):
                phone_val = '0363842731'  # IMP-035: digits-only
            else:
                phone_val = ''.join(filter(str.isdigit, phone_val)) or phone_val
            form_data['phone'] = phone_val
            form_data['tel'] = phone_val
        
        # メッセージ
        if product.message_template:
            form_data['message'] = product.message_template
            form_data['body'] = product.message_template
            form_data['content'] = product.message_template
            form_data['inquiry'] = product.message_template
        
        return form_data
    
    def _apply_template_variables(self, text: str, company: Company, product: Product) -> str:
        """テンプレート変数を実際の値に置換
        
        使用可能な変数:
        - {{company_name}}: 送信先企業名
        - {{company_url}}: 送信先企業のWebサイトURL
        - {{company_form_url}}: 送信先企業のフォームURL
        - {{company_industry}}: 送信先企業の業種
        - {{sender_company}}: 送信者の会社名
        - {{sender_name}}: 送信者名
        - {{product_name}}: 案件名
        """
        if not text:
            return text
        
        # 企業データの変数
        replacements = {
            '{{company_name}}': company.name if company else '',
            '{{company_url}}': company.website_url if company else '',
            '{{company_form_url}}': company.form_url if company else '',
            '{{company_industry}}': company.industry or '' if company else '',
            # 送信者データの変数
            '{{sender_company}}': product.sender_company or '' if product else '',
            '{{sender_name}}': product.sender_name or '' if product else '',
            '{{product_name}}': product.name or '' if product else '',
        }
        
        result = text
        for var, value in replacements.items():
            result = result.replace(var, value)
        
        return result
    
    def _infer_category_from_label(self, label: str, field_name: str, placeholder: str = '') -> str:
        """ラベルやフィールド名、プレースホルダーからカテゴリを推測（AI解析の誤分類対策）"""
        text = (label or '') + ' ' + (field_name or '') + ' ' + (placeholder or '')
        text = text.lower()
        
        # パターンマッチング（優先度順）
        patterns = [
            # プライバシー・同意系（チェックボックス用）
            (['プライバシー', 'privacy', '個人情報'], 'privacy_agreement'),
            (['利用規約', 'terms', '規約に同意'], 'terms_agreement'),
            # ふりがな系（先頭で判定 - nameより優先）
            (['ふりがな', 'フリガナ', 'kana', 'furi', 'furigana', 'カナ', 'your-furi'], 'name_kana'),
            (['姓（カナ）', 'せい（かな）', 'last_name_kana', 'sei_kana'], 'last_name_kana'),
            (['名（カナ）', 'めい（かな）', 'first_name_kana', 'mei_kana'], 'first_name_kana'),
            # 部署・役職（会社名より先にチェック - 同じnameで部署が後に来るパターン対策）
            (['部署', 'department', '経営企画部', '営業部', '人事部', '総務部', '開発部', '広報部', '企画部'], 'department'),
            (['役職', 'position'], 'position'),
            # 会社系
            (['会社名', '企業名', '組織名', '法人名', 'company'], 'company'),
            # 名前系
            (['姓', 'せい', 'last_name', 'last-name'], 'last_name'),
            (['名', 'めい', 'first_name', 'first-name'], 'first_name'),
            (['氏名', 'お名前', 'full_name', 'fullname', 'your-name'], 'full_name'),
            # 連絡先
            (['メール', 'mail', 'email'], 'email'),
            (['電話', 'tel', 'phone'], 'phone'),
            # 住所系
            (['都道府県', 'prefecture'], 'prefecture'),
            (['市区町村', 'city'], 'city'),
            (['住所', 'address'], 'address'),
            (['郵便番号', 'zip', 'postal'], 'zipcode'),
            # お問い合わせ
            (['お問い合わせ内容', '内容', 'message', 'inquiry', 'textarea'], 'message'),
            (['種別', 'お問い合わせ先', 'subject', 'category'], 'subject'),
        ]
        
        for keywords, category in patterns:
            for keyword in keywords:
                if keyword in text:
                    return category
        
        return 'other'
    
    def _infer_checkbox_category(self, field: Dict, field_name: str, field_id: str, label: str) -> str:
        """チェックボックスの種類を推測（プライバシーポリシー、利用規約など）"""
        # 全テキストを結合
        text = ' '.join([
            (label or '').lower(),
            (field_name or '').lower(),
            (field_id or '').lower(),
            str(field.get('label', '')).lower(),
        ])
        
        # プライバシーポリシー関連
        if any(kw in text for kw in ['プライバシー', 'privacy', '個人情報', 'personal']):
            return 'privacy_agreement'
        
        # 利用規約関連
        if any(kw in text for kw in ['利用規約', 'terms', '規約']):
            return 'terms_agreement'
        
        # 同意関連（一般的な同意チェックボックス）
        if any(kw in text for kw in ['同意', 'agree', 'consent', 'confirm']):
            return 'agreement'
        
        return 'checkbox'
    
    def _validate_value_for_category(self, category: str, value, field_name: str = '') -> tuple:
        """IMP-015: 入力値とカテゴリ/フィールド名の整合性をチェック"""
        import re
        val_str = str(value) if value else ''

        # category=email → @必須
        if category in ('email',) and '@' not in val_str:
            return False, 'value_category_mismatch: email requires @'

        # category=name系 → @が含まれていたらNG
        if category in ('full_name', 'last_name', 'first_name', 'name_kana') and '@' in val_str:
            return False, 'value_category_mismatch: name contains @'

        # category=phone系 → 数字+ハイフンのみ
        if category in ('phone', 'phone1', 'phone2', 'phone3'):
            if not re.match(r'^[\d\-\+\(\) ]+$', val_str):
                return False, 'value_category_mismatch: phone requires digits'

        # name属性ベースの追加チェック
        fn_lower = (field_name or '').lower()
        if fn_lower:
            if ('mail' in fn_lower or 'email' in fn_lower) and '@' not in val_str:
                return False, 'name_value_mismatch: mail field requires @'
            if ('tel' in fn_lower or 'phone' in fn_lower) and val_str:
                if not re.match(r'^[\d\-\+\(\) ]+$', val_str):
                    return False, 'name_value_mismatch: tel field requires digits'

        return True, None

    def _get_value_for_category(self, product: Product, category: str, company: Company = None, field: dict = None) -> Optional[str]:
        """field_categoryに対応する送信者データを取得"""
        # 電話番号：専用カラムがあればそちらを優先、なければsender_phoneを分割
        if product.sender_phone_1:
            phone1 = product.sender_phone_1
            phone2 = product.sender_phone_2 or ''
            phone3 = product.sender_phone_3 or ''
        else:
            phone = product.sender_phone or ''
            if phone in ('090-0000-0000', '09000000000', '080-0000-0000', '08000000000'):
                phone = '03-6384-2731'
            phone_digits = ''.join(filter(str.isdigit, phone))
            if len(phone_digits) == 10:
                phone1, phone2, phone3 = phone_digits[:2], phone_digits[2:6], phone_digits[6:]
            elif len(phone_digits) == 11:
                phone1, phone2, phone3 = phone_digits[:3], phone_digits[3:7], phone_digits[7:]
            else:
                phone1 = phone_digits[:3] if len(phone_digits) > 3 else phone_digits
                phone2 = phone_digits[3:7] if len(phone_digits) > 7 else phone_digits[3:] if len(phone_digits) > 3 else ''
                phone3 = phone_digits[7:] if len(phone_digits) > 7 else ''
        
        # 携帯電話（担当者用）
        mobile1 = product.sender_mobile_1 or phone1
        mobile2 = product.sender_mobile_2 or phone2
        mobile3 = product.sender_mobile_3 or phone3
        
        # カテゴリとProductフィールドのマッピング
        # IMP-035: ダミー電話番号変換
        _raw_phone = product.sender_phone or f"{phone1}-{phone2}-{phone3}".strip('-')
        _phone_converted = _raw_phone
        if _raw_phone in ('090-0000-0000', '09000000000', '080-0000-0000', '08000000000'):
            _phone_converted = '03-6384-2731'

        category_mapping = {
            # 名前系
            'name': product.sender_name or f"{product.sender_last_name or ''} {product.sender_first_name or ''}".strip(),
            'full_name': product.sender_name or f"{product.sender_last_name or ''} {product.sender_first_name or ''}".strip(),
            'last_name': product.sender_last_name,
            'first_name': product.sender_first_name,
            'last_name_kana': product.sender_last_name_kana,
            'first_name_kana': product.sender_first_name_kana,
            'name_kana': f"{product.sender_last_name_kana or ''} {product.sender_first_name_kana or ''}".strip() or None,
            'kana': f"{product.sender_last_name_kana or ''} {product.sender_first_name_kana or ''}".strip() or None,
            'gender': product.sender_gender,
            
            # 会社系
            'company': product.sender_company,
            'company_name': product.sender_company,
            'company_kana': product.sender_company_kana,
            'department': product.sender_department,
            'position': product.sender_position,
            'rep_name': product.sender_rep_name,
            'rep_name_kana': product.sender_rep_name_kana,
            
            # 連絡先（会社用）
            'email': product.sender_email,
            'mail': product.sender_email,
            'email_company': product.sender_email_company or product.sender_email,
            'email_personal': product.sender_email_personal or product.sender_email,
            'phone': _phone_converted,  # IMP-035: ダミー変換適用
            'phone1': phone1,
            'phone2': phone2,
            'phone3': phone3,
            'tel': _phone_converted,  # IMP-035: ダミー変換適用
            # 連絡先（担当者用）
            'mobile': f"{mobile1}-{mobile2}-{mobile3}".strip('-'),
            'mobile1': mobile1,
            'mobile2': mobile2,
            'mobile3': mobile3,
            # FAX
            'fax': f"{product.sender_fax_1 or ''}-{product.sender_fax_2 or ''}-{product.sender_fax_3 or ''}".strip('-') or None,
            'fax1': product.sender_fax_1,
            'fax2': product.sender_fax_2,
            'fax3': product.sender_fax_3,
            
            # 住所系
            'zipcode': f"{product.sender_zipcode_1 or ''}-{product.sender_zipcode_2 or ''}".strip('-') or None,
            'zipcode1': product.sender_zipcode_1,
            'zipcode2': product.sender_zipcode_2,
            'prefecture': product.sender_prefecture,
            'city': product.sender_city,
            'address': product.sender_address,
            'full_address': f"{product.sender_prefecture or ''}{product.sender_city or ''}{product.sender_address or ''}",
            
            # 問い合わせ内容（テンプレート変数適用）
            'message': self._apply_template_variables(product.message_template, company, product),
            'inquiry': self._apply_template_variables(product.message_template, company, product),
            'content': self._apply_template_variables(product.message_template, company, product),
            'body': self._apply_template_variables(product.message_template, company, product),
            'subject': self._apply_template_variables(product.sender_inquiry_title, company, product),
            'title': self._apply_template_variables(product.sender_inquiry_title, company, product),
            
            # URL
            'url': product.sender_company_url,
            'website': product.sender_company_url,
        }
        
        value = category_mapping.get(category)
        if value is not None:
            # IMP-035 Mod-2: 電話番号format正規化
            # phone/tel/mobileカテゴリは常にハイフン除去（digits only）
            if value and category in ('phone', 'tel', 'mobile'):
                digits_only = ''.join(filter(str.isdigit, str(value)))
                if digits_only:
                    print(f"  📞 IMP-035: 電話番号digits化: {value} → {digits_only}")
                    value = digits_only
            return value

        # otherカテゴリ: ラベル/placeholderから推測してマッピング
        if category == 'other' and field:
            label = ((field.get('label', '') or '') + ' ' + (field.get('placeholder', '') or '')).lower()
            if any(k in label for k in ['url', 'ホームページ', 'webサイト', 'ウェブサイト']):
                return product.sender_company_url or None
            if any(k in label for k in ['fax', 'ファックス']):
                fax = f"{product.sender_fax_1 or ''}-{product.sender_fax_2 or ''}-{product.sender_fax_3 or ''}".strip('-')
                return fax or None
            if any(k in label for k in ['人数', '従業員', '社員数', '規模']):
                return None  # マッピング不可 → fill_rate分母から除外
            if any(k in label for k in ['その他', '備考', '自由記入', 'ご要望', '補足']):
                return ''  # 空欄で送信可
            # 上記に該当しない → None（fill_rate分母から除外）
            return None

        return None

    def _is_likely_contact_form(self, form_fields: List[Dict]) -> Tuple[bool, str]:
        """form_fieldsが問い合わせフォームらしいかを判定

        Returns:
            (is_contact_form, reason) - Falseの場合reasonに理由を記録
        """
        if not form_fields:
            return False, "no_fields"

        categories = [f.get('field_category', '') for f in form_fields]
        field_types = [f.get('type', '') for f in form_fields]
        field_names = [f.get('name', '').lower() for f in form_fields]

        # passwordフィールドがある → ログインフォーム
        if 'password' in field_types or any('password' in n for n in field_names):
            return False, "login_form_detected"

        # 検索フォーム: フィールド1-2個 + name属性がs/q/keyword等
        SEARCH_NAMES = {'s', 'q', 'query', 'keyword', 'search', 'search_query'}
        if len(form_fields) <= 2 and any(f.get('name', '').lower() in SEARCH_NAMES for f in form_fields):
            return False, "search_form_detected"

        # お問い合わせに必要なカテゴリが1つもない場合
        CONTACT_CATEGORIES = {'email', 'message', 'full_name', 'last_name', 'first_name',
                              'company', 'phone', 'name', 'name_kana', 'inquiry'}
        has_contact_field = any(c in CONTACT_CATEGORIES for c in categories)

        # 全フィールドがcheckbox/other/unknown系のみ → 非問い合わせフォーム
        GENERIC_CATEGORIES = {'checkbox', 'other', 'unknown', 'privacy_agreement',
                              'terms_agreement', 'agreement', ''}
        non_generic = [c for c in categories if c not in GENERIC_CATEGORIES]

        if not has_contact_field and len(non_generic) == 0:
            return False, "no_contact_fields (all checkbox/other)"

        return True, ""

    async def _fill_form_with_analysis(self, page, form_fields: List[Dict], product: Product, company: Company = None) -> Dict:
        """解析結果を使ってフォーム入力（高精度モード）"""
        # P1: フォーム誤検出フィルタ
        is_contact, skip_reason = self._is_likely_contact_form(form_fields)
        if not is_contact:
            print(f"  ⚠️ 問い合わせフォームではないと判定: {skip_reason}")
            return {"__form_skip": {
                "success": False,
                "category": "form_validation",
                "reason": f"not_contact_form: {skip_reason}",
                "excluded": True
            }}

        # IMP-031 Mod-3: フィールドラベルの空白正規化
        # DOMから取得したラベルに不要な空白が含まれる場合がある（例: "必 須ふりがな" → "必須ふりがな"）
        import re as _re031
        for _f in form_fields:
            _lbl = _f.get('label', '')
            if _lbl:
                # 全角スペースと半角スペースの正規化
                _cleaned = _re031.sub(r'\s+', '', _lbl) if len(_lbl) < 30 else _lbl
                # 短いラベルは空白完全除去（"必 須 ふりがな" → "必須ふりがな"）
                # 長いラベルは連続空白のみ縮約
                if len(_lbl) >= 30:
                    _cleaned = _re031.sub(r'\s+', ' ', _lbl).strip()
                if _cleaned != _lbl:
                    _f['label'] = _cleaned
            _ph = _f.get('placeholder', '')
            if _ph:
                _cleaned_ph = _re031.sub(r'\s+', ' ', _ph).strip()
                if _cleaned_ph != _ph:
                    _f['placeholder'] = _cleaned_ph

        fill_results = {}
        custom_select_count = 0  # カスタムセレクトのカウンター
        processed_custom_selects = set()  # 処理済みカスタムセレクトのセレクタ
        
        # 同じname属性のフィールドが複数ある場合のインデックス管理
        field_name_count = {}
        
        for field in form_fields:
            field_name = field.get('name') or field.get('id') or ''
            field_id = field.get('id')
            field_type = field.get('type', 'input')
            category = field.get('field_category', 'unknown')
            label = field.get('label', field_name)
            
            # 同じnameのフィールドのインデックスを取得
            # Note: field_name==""(空文字)もインデックス管理の対象にする
            name_key = field_name if field_name else '__empty__'
            field_name_count[name_key] = field_name_count.get(name_key, 0) + 1
            field_index = field_name_count[name_key] - 1  # 0-indexed
            
            # IMP-029 Mod-5: ラベルテキスト正規化（*, 必須, Required等を除去）
            _raw_label = field.get('label', '')
            if _raw_label:
                import re as _re2
                _clean_label = _re2.sub(r'[\s*※]+$', '', _raw_label).strip()
                _clean_label = _re2.sub(r'（必須）|\(必須\)|必須|Required|Optional', '', _clean_label).strip()
                _clean_label = _re2.sub(r'\s+', ' ', _clean_label).strip()
                if _clean_label != _raw_label:
                    field['label'] = _clean_label

            # IMP-021: HTMLのtype属性によるカテゴリ強制補正（AIよりHTMLが権威）
            html_type = field.get('type', '')
            if html_type == 'email' and category != 'email':
                print(f"  🔧 HTML type=email 検出: {field_name} ({category} → email)")
                category = 'email'
            elif html_type == 'tel' and category not in ('phone', 'phone1', 'phone2', 'phone3'):
                print(f"  🔧 HTML type=tel 検出: {field_name} ({category} → phone)")
                category = 'phone'
            elif html_type == 'url' and category != 'url':
                print(f"  🔧 HTML type=url 検出: {field_name} ({category} → url)")
                category = 'url'


            # IMP-043: name属性からの独立カテゴリ推定 + クロスチェック
            # F-3(Gemini)のlabel-input対応ズレによる入れ違いを防止
            if field_name and category not in ('checkbox', 'radio', 'other', 'unknown', ''):
                _fn_lower = field_name.lower()
                _name_category = None
                # name属性からカテゴリを推定（優先度順）
                if any(k in _fn_lower for k in ('email', 'mail', 'e-mail')):
                    _name_category = 'email'
                elif any(k in _fn_lower for k in ('tel', 'phone', 'denwa')):
                    _name_category = 'phone'
                elif any(k in _fn_lower for k in ('company', 'corp', 'kaisha', 'organization', 'org_name', 'firm')):
                    _name_category = 'company'
                elif any(k in _fn_lower for k in ('message', 'body', 'content', 'inquiry', 'naiyo')):
                    _name_category = 'message'
                elif any(k in _fn_lower for k in ('subject', 'title', 'kenmei')):
                    _name_category = 'subject'
                elif any(k in _fn_lower for k in ('department', 'busho', 'division', 'section')):
                    _name_category = 'department'
                elif any(k in _fn_lower for k in ('position', 'yakushoku', 'job_title', 'jobtitle')):
                    _name_category = 'position'
                elif any(k in _fn_lower for k in ('kana', 'furi', 'reading', 'pronunciation')):
                    _name_category = 'name_kana'
                elif any(k in _fn_lower for k in ('zip', 'post', 'yubin')):
                    _name_category = 'zipcode'
                elif any(k in _fn_lower for k in ('pref',)):
                    _name_category = 'prefecture'
                elif any(k in _fn_lower for k in ('city', 'shiku')):
                    _name_category = 'city'
                elif any(k in _fn_lower for k in ('address', 'addr', 'jyusho', 'jusho')):
                    _name_category = 'address'
                elif any(k in _fn_lower for k in ('sei', 'last_name', 'family_name', 'lastname', 'familyname')):
                    if 'kana' not in _fn_lower and 'furi' not in _fn_lower:
                        _name_category = 'last_name'
                elif any(k in _fn_lower for k in ('mei', 'first_name', 'given_name', 'firstname', 'givenname')):
                    if 'kana' not in _fn_lower and 'furi' not in _fn_lower:
                        _name_category = 'first_name'
                elif any(k in _fn_lower for k in ('name', 'namae', 'shimei')):
                    if not any(k in _fn_lower for k in ('company', 'org', 'corp', 'file', 'user', 'kana', 'furi')):
                        _name_category = 'full_name'
                # クロスチェック: F-3カテゴリとname属性カテゴリが矛盾する場合
                if _name_category and _name_category != category:
                    # 同系統のカテゴリは許容（phone/phone1, last_name/name等）
                    _same_group = {
                        'phone': {'phone', 'phone1', 'phone2', 'phone3'},
                        'full_name': {'full_name', 'name', 'last_name', 'first_name'},
                        'name': {'full_name', 'name', 'last_name', 'first_name'},
                        'last_name': {'full_name', 'name', 'last_name'},
                        'first_name': {'full_name', 'name', 'first_name'},
                        'name_kana': {'name_kana', 'last_name_kana', 'first_name_kana'},
                        'zipcode': {'zipcode', 'zipcode1', 'zipcode2'},
                        'address': {'address', 'city', 'prefecture'},
                    }
                    _group = _same_group.get(_name_category, {_name_category})
                    if category not in _group:
                        print(f"  🔧 IMP-043: name属性クロスチェック: {field_name} (F-3:{category} → name:{_name_category})")
                        category = _name_category
                        field['_category_corrected'] = True

            # ラベルからカテゴリを補正（AI解析の誤分類対策）
            placeholder = field.get('placeholder', '')
            
            # 部署名ラベルがある場合は優先的にdepartmentに補正（同名フィールドで会社名と混同されやすい）
            if '部署' in (label or ''):
                if category != 'department':
                    print(f"  🔄 ラベル「部署」検出: {field_name} → department")
                    category = 'department'
            # 役職ラベルがある場合はpositionに補正
            elif '役職' in (label or ''):
                if category != 'position':
                    print(f"  🔄 ラベル「役職」検出: {field_name} → position")
                    category = 'position'
            # 姓/名の単独ラベルをlast_name/first_nameに補正（AIがnameと誤分類する対策）
            elif field_name == '姓' or (label and label.strip().rstrip('*').strip() == '姓'):
                if category not in ['last_name']:
                    print(f"  🔄 ラベル「姓」検出: {field_name} → last_name")
                    category = 'last_name'
            elif field_name == '名' or (label and label.strip().rstrip('*').strip() == '名'):
                if category not in ['first_name']:
                    print(f"  🔄 ラベル「名」検出: {field_name} → first_name")
                    category = 'first_name'
            elif category in ['other', 'unknown', '']:
                category = self._infer_category_from_label(label, field_name, placeholder)
                if category != 'other':
                    print(f"  🔄 ラベルからカテゴリ補正: {field_name} → {category}")
            
            # subject/inquiry_typeカテゴリでname属性が空の場合、カスタムセレクトの可能性
            if category in ['subject', 'inquiry_type'] and not field_name:
                custom_select_count += 1
                result_key = f'custom_select_{custom_select_count}'
                print(f"  🔄 subjectカテゴリでname属性なし → カスタムセレクト試行 ({result_key})")
                result = await self._handle_custom_select(page, field, result_key, category, product, processed_custom_selects)
                if result.get('selector_used'):
                    processed_custom_selects.add(result['selector_used'])
                fill_results[result_key] = result
                continue
            
            # チェックボックスの場合は特別処理（productを渡して優先キーワード対応）
            if field_type == 'checkbox':
                fill_results[field_name] = await self._handle_checkbox(page, field, field_name, field_id, label, product)
                continue

            # ラジオボタンの場合は専用ハンドラー
            if field_type == 'radio':
                result_key = field_name if field_name else f"__radio_{category}"
                fill_results[result_key] = await self._handle_radio(page, field, field_name, field_id, category, product)
                continue

            # セレクトボックスの場合、ラベルからカテゴリを再補正（問い合わせカテゴリ等）
            if field_type == 'select':
                inquiry_keywords = ['問い合わせ', '問合せ', 'お問い合わせ', 'カテゴリ', '種別', '種類']
                if any(kw in (label or '') for kw in inquiry_keywords) and category not in ['subject', 'inquiry_type', 'prefecture', 'position']:
                    print(f"  🔄 ラベルから問い合わせセレクト検出: {field_name} → subject")
                    category = 'subject'
            
            # セレクトボックスの場合は特別処理（type: "search"も含む - AI誤分類対策）
            if field_type in ['select', 'search'] and category in ['subject', 'inquiry_type', 'prefecture']:
                fill_results[field_name] = await self._handle_select(page, field, field_name, field_id, category, product, company)
                continue
            
            # セレクトボックスの場合は特別処理
            if field_type == 'select':
                result_key = f"{field_name}_{field_index}" if field_index > 0 else field_name
                fill_results[result_key] = await self._handle_select(page, field, field_name, field_id, category, product, company)
                continue
            
            # カテゴリから入力値を取得（companyを渡してテンプレート変数を適用）
            value = self._get_value_for_category(product, category, company, field=field)

            # IMP-019: メッセージ長制限（400文字）
            MAX_MESSAGE_LENGTH = 400
            if category == "message" and value and len(value) > MAX_MESSAGE_LENGTH:
                original_len = len(value)
                # 行単位で切ってMAX_MESSAGE_LENGTH以内に収める
                trunc_lines = []
                char_count = 0
                for tl in value.split("\n"):
                    if char_count + len(tl) + 1 > MAX_MESSAGE_LENGTH:
                        break
                    trunc_lines.append(tl)
                    char_count += len(tl) + 1
                value = "\n".join(trunc_lines)
                if len(value) > MAX_MESSAGE_LENGTH:
                    value = value[:MAX_MESSAGE_LENGTH]
                print(f"  📝 メッセージ短縮: {original_len}文字 → {len(value)}文字")
            
            # 結果キー（同じnameが複数ある場合はインデックスを付加）
            # field_nameが空の場合はcategoryを使ってユニークキーを生成
            base_key = field_name if field_name else f"__{category}"
            result_key = f"{base_key}_{field_index}" if field_index > 0 else base_key
            
            fill_results[result_key] = {
                'success': False,
                'selector_used': None,
                'value': str(value)[:50] if value else None,
                'category': category,
                'label': label,
                'reason': None
            }

            if value is None:
                fill_results[result_key]['reason'] = 'no_value'
                fill_results[result_key]['excluded'] = True  # fill_rate分母から除外
                print(f"  ⚠️ {result_key} ({category}): データなし（分母除外）")
                continue
            if value == '':
                # 空文字は「入力不要」=成功扱い
                fill_results[result_key]['success'] = True
                fill_results[result_key]['excluded'] = True
                print(f"  ⏭️ {result_key} ({category}): 空欄OK（スキップ）")
                continue

            # IMP-015: value-categoryバリデーション（入力前の整合性チェック）
            valid, mismatch_reason = self._validate_value_for_category(category, value, field_name)
            if not valid:
                fill_results[result_key]['reason'] = mismatch_reason
                print(f"  ⛔ {result_key} ({category}): {mismatch_reason}")
                continue

            # 解析結果のセレクタを優先使用
            tag = 'textarea' if field_type == 'textarea' else 'input'

            # Step 1-2: name/id セレクタ（完全一致 → 部分一致）
            primary_selectors = []
            if field_name:
                primary_selectors.append(f'{tag}[name="{field_name}"]')
            if field_id and field_id != field_name:
                primary_selectors.append(f'{tag}[id="{field_id}"]')
            if field_name:
                primary_selectors.append(f'{tag}[name*="{field_name}"]')
                primary_selectors.append(f'{tag}[id*="{field_name}"]')

            # Step 3-4: placeholder / aria-label 属性セレクタ（常に候補に含める）
            fallback_selectors = []
            placeholder = field.get('placeholder', '')
            aria_label = field.get('aria_label', '')
            if placeholder:
                fallback_selectors.append(f'{tag}[placeholder="{placeholder}"]')
                # IMP-029 Mod-3: 正規化プレースホルダーで部分一致
                _norm_ph = placeholder.strip().replace('\n', ' ').replace('\r', '').replace('\t', ' ')
                import re as _re
                _norm_ph = _re.sub(r'\s+', ' ', _norm_ph).strip()
                if _norm_ph != placeholder:
                    fallback_selectors.append(f'{tag}[placeholder="{_norm_ph}"]')
                # 先頭部分の部分一致（エンコーディング差分対策）
                if len(placeholder) > 5:
                    _ph_core = placeholder[:8].strip().replace('"', '')
                    if _ph_core:
                        fallback_selectors.append(f'{tag}[placeholder*="{_ph_core}"]')
            if aria_label:
                fallback_selectors.append(f'{tag}[aria-label="{aria_label}"]')
                # IMP-029: aria-label部分一致
                if len(aria_label) > 5:
                    _al_core = aria_label[:8].strip().replace('"', '')
                    if _al_core:
                        fallback_selectors.append(f'{tag}[aria-label*="{_al_core}"]')

            # Step 5: type属性 + field_category 推定セレクタ
            category_type_map = {
                'email': 'input[type="email"]',
                'phone': 'input[type="tel"]',
                'message': 'textarea',
            }
            if category in category_type_map:
                type_selector = category_type_map[category]
                if type_selector not in fallback_selectors:
                    fallback_selectors.append(type_selector)

            # primary_selectors → fallback_selectors の順で試行
            all_selectors = primary_selectors + fallback_selectors

            if not all_selectors:
                # IMP-039: セレクタ空でもlabel/placeholderフォールバックに進む
                if not label and not field.get('placeholder'):
                    fill_results[result_key]['reason'] = 'no_selector'
                    print(f"  ❌ {result_key} ({category}): セレクタ生成不可（name/id/placeholder/label全て空）")
                    continue
                print(f"  🔄 IMP-039: {result_key} ({category}): name/id空 → label/placeholderフォールバック実行")

            filled = False
            last_fail_reason = 'selector_not_found'
            tried_selectors = []
            for selector in all_selectors:
                tried_selectors.append(selector)
                try:
                    # 同じname属性の要素が複数ある場合、インデックスで選択
                    elements = await page.query_selector_all(selector)
                    if elements and field_index < len(elements):
                        element = elements[field_index]
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()

                        if is_visible and is_enabled:
                            await element.fill(str(value))
                            fill_results[result_key]['success'] = True
                            fill_results[result_key]['selector_used'] = f"{selector}[{field_index}]"
                            print(f"  ✅ {result_key} ({category}): 入力完了 [{selector}[{field_index}]]")
                            filled = True
                            break
                        else:
                            last_fail_reason = f"element_not_interactable (visible={is_visible}, enabled={is_enabled})"
                    elif elements:
                        last_fail_reason = f"index_out_of_range (found={len(elements)}, need_idx={field_index})"
                except Exception as e:
                    last_fail_reason = f"selector_error: {str(e)[:80]}"
                    continue

            # 6. セレクタで見つからない場合、label textでフォールバック（Playwright locator API）
            if not filled and label:
                try:
                    clean_label = label.strip().replace('*', '').replace('必須', '').replace('\n', ' ').strip()
                    # 複数行ラベルの場合、最初の有意な部分を使う
                    if '\n' in label or len(clean_label) > 30:
                        clean_label = clean_label.split()[0] if clean_label.split() else clean_label
                    if clean_label and len(clean_label) >= 2:
                        locator = page.get_by_label(clean_label, exact=False)
                        count = await locator.count()
                        if count > 0:
                            target = locator.nth(min(field_index, count - 1))
                            if await target.is_visible() and await target.is_enabled():
                                await target.fill(str(value))
                                fill_results[result_key]['success'] = True
                                fill_results[result_key]['selector_used'] = f'get_by_label("{clean_label}")'
                                print(f"  ✅ {result_key} ({category}): label fallback入力完了 [{clean_label}]")
                                filled = True
                            else:
                                last_fail_reason = f"label_element_not_interactable"
                        else:
                            # IMP-045: label未発見 → 同じテキストでplaceholder検索を試行
                            try:
                                ph_loc = page.get_by_placeholder(clean_label, exact=False)
                                ph_count = await ph_loc.count()
                                if ph_count > 0:
                                    ph_target = ph_loc.nth(min(field_index, ph_count - 1))
                                    if await ph_target.is_visible() and await ph_target.is_enabled():
                                        await ph_target.fill(str(value))
                                        fill_results[result_key]['success'] = True
                                        fill_results[result_key]['selector_used'] = f'get_by_placeholder("{clean_label}") via label'
                                        print(f"  ✅ IMP-045: {result_key} ({category}): label→placeholder fallback成功 [{clean_label}]")
                                        filled = True
                                    else:
                                        last_fail_reason = f"label_not_found: {clean_label[:30]}"
                                else:
                                    last_fail_reason = f"label_not_found: {clean_label[:30]}"
                            except Exception:
                                last_fail_reason = f"label_not_found: {clean_label[:30]}"
                except Exception as e:
                    last_fail_reason = f"label_error: {str(e)[:80]}"

            # 7. placeholder textでフォールバック（IMP-045: labelテキストでもplaceholder検索）
            if not filled:
                placeholder = field.get('placeholder', '')
                if not placeholder or len(placeholder) < 2:
                    # placeholderが空の場合、labelテキストをplaceholder検索にも使用
                    _label_text = field.get('label', '').strip().replace('*', '').replace('必須', '').strip()
                    if _label_text and len(_label_text) >= 2 and len(_label_text) <= 30:
                        placeholder = _label_text
                if placeholder and len(placeholder) >= 2:
                    try:
                        locator = page.get_by_placeholder(placeholder, exact=False)
                        count = await locator.count()
                        if count > 0:
                            target = locator.nth(min(field_index, count - 1))
                            if await target.is_visible() and await target.is_enabled():
                                await target.fill(str(value))
                                fill_results[result_key]['success'] = True
                                fill_results[result_key]['selector_used'] = f'get_by_placeholder("{placeholder[:30]}")'
                                print(f"  ✅ {result_key} ({category}): placeholder fallback入力完了 [{placeholder[:30]}]")
                                filled = True
                            else:
                                last_fail_reason = f"placeholder_element_not_interactable"
                        else:
                            last_fail_reason = f"placeholder_not_found: {placeholder[:30]}"
                    except Exception as e:
                        last_fail_reason = f"placeholder_error: {str(e)[:80]}"

            if not filled:
                fill_results[result_key]['reason'] = last_fail_reason
                fill_results[result_key]['tried_selectors'] = tried_selectors[:5]  # 最大5つ記録
                print(f"  ❌ {result_key} ({category}): {last_fail_reason}")

        return fill_results
    
    async def _handle_select(self, page, field: Dict, field_name: str, field_id: str, category: str, product: Product, company: Company = None) -> Dict:
        """セレクトボックスを処理
        
        カテゴリに応じて適切な選択肢を選ぶ。
        - subject/inquiry_type: 最初の有効な選択肢を選ぶ（「選択してください」以外）
        - prefecture: 都道府県を選択
        - その他: 値があれば部分一致で選択
        
        Note: ラベルに「お問い合わせ先」「種別」等を含む場合も種別として処理
        """
        result = {
            'success': False,
            'selector_used': None,
            'value': None,
            'category': category,
            'error': None
        }
        
        # ラベルから種別セレクトを自動検出（AI解析の誤分類対策）
        label = field.get('label', '') or ''
        inquiry_label_keywords = ['お問い合わせ先', 'お問い合わせ種別', '種別', 'お問合せ先', '問い合わせ先', '問合せ先']
        is_inquiry_select = any(kw in label for kw in inquiry_label_keywords)
        if is_inquiry_select and category not in ['subject', 'inquiry_type', 'category']:
            print(f"  🔄 ラベルから種別セレクトを検出: {label[:30]}... (category: {category} → subject)")
            category = 'subject'  # カテゴリを上書き
        
        try:
            # セレクトボックスを探す
            selectors = []
            if field_name:
                selectors.append(f'select[name="{field_name}"]')
            if field_id:
                selectors.append(f'select[id="{field_id}"]')
            
            select_element = None
            used_selector = None
            for selector in selectors:
                element = await page.query_selector(selector)
                if element:
                    select_element = element
                    used_selector = selector
                    break
            
            if not select_element:
                # 標準selectが見つからない場合、カスタムセレクトを試行
                print(f"  ⚠️ {field_name} ({category}): 標準selectが見つからない → カスタムセレクト試行")
                custom_result = await self._handle_custom_select(page, field, field_name, category, product)
                if not custom_result.get('success') and not custom_result.get('reason'):
                    custom_result['reason'] = 'select_custom_not_found' if custom_result.get('error') == 'カスタムセレクトが見つかりません' else 'select_custom_failed'
                return custom_result
            
            # 選択肢を取得
            options = await page.evaluate('''(selector) => {
                const select = document.querySelector(selector);
                if (!select) return [];
                return Array.from(select.options).map(opt => ({
                    value: opt.value,
                    text: opt.textContent.trim(),
                    index: opt.index
                }));
            }''', used_selector)
            
            print(f"  📋 {field_name}: 選択肢 {len(options)}件")
            
            if not options:
                result['error'] = "選択肢がありません"
                result['reason'] = 'select_no_option'
                return result
            
            # 都道府県リスト（自動検出用）
            prefectures = ['北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
                          '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
                          '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
                          '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
                          '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
                          '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
                          '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県']
            
            # 都道府県セレクトかどうか自動検出
            is_prefecture_select = False
            pref_count = sum(1 for opt in options if any(p in opt['text'] for p in prefectures))
            if pref_count >= 10:  # 10個以上の都道府県があれば都道府県セレクト
                is_prefecture_select = True
                print(f"  🗾 都道府県セレクトを自動検出")
            
            # カテゴリに応じて選択肢を決定
            target_value = None
            
            if category in ['subject', 'inquiry_type', 'category']:
                # お問い合わせ種別: 優先キーワードマッチング
                skip_texts = ['選択してください', '選択', '---', '--', '-', '']
                
                # 優先キーワードがあれば優先的にマッチ
                priority_keywords = []
                if hasattr(product, 'inquiry_type_priority') and product.inquiry_type_priority:
                    priority_keywords = [kw.strip() for kw in product.inquiry_type_priority.split(',') if kw.strip()]
                    print(f"  📋 種別優先キーワード: {priority_keywords}")
                
                # 優先キーワード順にマッチを試みる
                for keyword in priority_keywords:
                    for opt in options:
                        if opt['value'] and opt['text'] not in skip_texts:
                            if keyword in opt['text']:
                                target_value = opt['value']
                                print(f"  🎯 優先選択: {opt['text']} (キーワード: {keyword})")
                                break
                    if target_value:
                        break
                
                # マッチしなければ最初の有効な選択肢
                if not target_value:
                    for opt in options:
                        if opt['value'] and opt['text'] not in skip_texts:
                            target_value = opt['value']
                            print(f"  🎯 デフォルト選択: {opt['text']} (value={opt['value']})")
                            break
            
            elif category == 'prefecture' or is_prefecture_select:
                # 都道府県
                pref = product.sender_prefecture
                if pref:
                    for opt in options:
                        if pref in opt['text'] or opt['text'] in pref:
                            target_value = opt['value']
                            print(f"  🎯 都道府県選択: {opt['text']}")
                            break
            
            else:
                # その他: カテゴリに対応する値で部分一致
                value = self._get_value_for_category(product, category, company)
                if value:
                    for opt in options:
                        if value in opt['text'] or opt['text'] in value:
                            target_value = opt['value']
                            print(f"  🎯 選択: {opt['text']}")
                            break
                
                # 役職セレクト、または未知のセレクト（other）で値がマッチしなかった場合
                # 「その他」または最初の有効選択肢を選ぶ（必須フィールド対策）
                if not target_value and category in ['position', 'department', 'other', 'unknown', '']:
                    # 「その他」を探す
                    for opt in options:
                        if 'その他' in opt['text']:
                            target_value = opt['value']
                            print(f"  🎯 フォールバック「その他」を選択: {opt['text']}")
                            break
                    # 「その他」もなければ最初の有効な選択肢
                    if not target_value:
                        for opt in options:
                            if opt['value'] and '選択' not in opt['text'] and 'お選び' not in opt['text']:
                                target_value = opt['value']
                                print(f"  🎯 フォールバック選択: {opt['text']}")
                                break
            
            if target_value:
                await select_element.select_option(value=target_value)
                result['success'] = True
                result['selector_used'] = used_selector
                result['value'] = target_value
                print(f"  ✅ {field_name} ({category}): 選択完了")
            else:
                result['error'] = "適切な選択肢が見つかりません"
                result['reason'] = 'select_no_option'
                # IMP-040: デバッグ用に選択肢を記録（最大10件）
                result['available_options'] = [opt['text'][:30] for opt in options[:10] if opt.get('text')]
                print(f"  ⚠️ {field_name} ({category}): 適切な選択肢が見つかりません (候補: {[o['text'][:20] for o in options[:5]]})")

        except Exception as e:
            # IMP-040: 標準select操作失敗時、カスタムセレクトにフォールバック
            print(f"  ⚠️ IMP-040: {field_name} ({category}): 標準select失敗 → カスタムセレクト試行")
            try:
                custom_result = await self._handle_custom_select(page, field, field_name, category, product)
                if custom_result.get('success'):
                    return custom_result
            except Exception:
                pass
            result['error'] = str(e)[:200]
            result['reason'] = 'select_option_failed'
            print(f"  ❌ {field_name} ({category}): エラー - {e}")

        return result

    async def _handle_custom_select(self, page, field: Dict, field_name: str, category: str, product: Product, processed_selectors: set = None) -> Dict:
        """カスタムセレクト（Mantine UI等）を処理
        
        標準のselect要素が見つからない場合、カスタムコンポーネントを試行する。
        - Mantine Select: input.mantine-Select-input + [role=option]
        - Mantine MultiSelect: input.mantine-MultiSelect-searchInput + [role=option]
        - React Select: div.select__control + div.select__option
        - その他のカスタムセレクト
        
        Args:
            processed_selectors: 既に処理済みのセレクタ（スキップ用）
        """
        if processed_selectors is None:
            processed_selectors = set()
            
        result = {
            'success': False,
            'selector_used': None,
            'value': None,
            'category': category,
            'error': None
        }
        
        label = field.get('label', '') or ''
        print(f"  🔄 カスタムセレクト処理開始: {field_name} (label: {label})")
        print(f"    処理済みセレクタ: {processed_selectors}")
        
        # 優先キーワードを取得
        priority_keywords = []
        if hasattr(product, 'inquiry_type_priority') and product.inquiry_type_priority:
            priority_keywords = [kw.strip() for kw in product.inquiry_type_priority.split(',') if kw.strip()]
        
        try:
            # --- Mantine MultiSelect（複数選択）---
            if 'mantine-MultiSelect' not in processed_selectors:
                mantine_multi = await page.query_selector('input.mantine-MultiSelect-searchInput')
                if mantine_multi:
                    print(f"    🔍 Mantine MultiSelect検出")
                    # クリックしてドロップダウンを開く
                    await mantine_multi.click()
                    await page.wait_for_timeout(300)
                    
                    # オプションを取得
                    options = await page.query_selector_all('[role="option"]')
                    if options:
                        print(f"    📋 MultiSelectオプション数: {len(options)}")
                        
                        # 選択するオプションを決定
                        target_option = None
                        target_text = None
                        
                        # 優先キーワードでマッチ
                        for keyword in priority_keywords:
                            for opt in options:
                                text = await opt.inner_text()
                                if keyword in text:
                                    target_option = opt
                                    target_text = text
                                    print(f"    🎯 優先マッチ: {text} (keyword: {keyword})")
                                    break
                            if target_option:
                                break
                        
                        # マッチしなければ最初のオプション
                        if not target_option and options:
                            target_option = options[0]
                            target_text = await target_option.inner_text()
                            print(f"    🎯 デフォルト選択: {target_text}")
                        
                        if target_option:
                            await target_option.click()
                            await page.wait_for_timeout(200)
                            result['success'] = True
                            result['selector_used'] = 'mantine-MultiSelect'
                            result['value'] = target_text
                            print(f"  ✅ {field_name} (MultiSelect): {target_text} 選択完了")
                            return result
            
            # --- Mantine Select（単一選択）---
            if 'mantine-Select' not in processed_selectors:
                mantine_select = await page.query_selector('input.mantine-Select-input')
                if mantine_select:
                    print(f"    🔍 Mantine Select検出")
                    # クリックしてドロップダウンを開く
                    await mantine_select.click()
                    await page.wait_for_timeout(300)
                    
                    # オプションを取得
                    options = await page.query_selector_all('[role="option"]')
                    if options:
                        print(f"    📋 オプション数: {len(options)}")
                        
                        # 選択するオプションを決定
                        target_option = None
                        target_text = None
                        
                        # 優先キーワードでマッチ
                        for keyword in priority_keywords:
                            for opt in options:
                                text = await opt.inner_text()
                                if keyword in text:
                                    target_option = opt
                                    target_text = text
                                    print(f"    🎯 優先マッチ: {text} (keyword: {keyword})")
                                    break
                            if target_option:
                                break
                        
                        # マッチしなければ最初のオプション
                        if not target_option and options:
                            target_option = options[0]
                            target_text = await target_option.inner_text()
                            print(f"    🎯 デフォルト選択: {target_text}")
                        
                        if target_option:
                            await target_option.click()
                            await page.wait_for_timeout(200)
                            result['success'] = True
                            result['selector_used'] = 'mantine-Select'
                            result['value'] = target_text
                            print(f"  ✅ {field_name} (カスタムセレクト): {target_text} 選択完了")
                            return result
            
            # --- React Select / 汎用カスタムセレクト ---
            custom_selects = [
                ('div.select__control', 'div.select__option'),  # React Select
                ('div[class*="select"]', '[role="option"]'),    # 汎用
                ('div[class*="dropdown"]', '[role="option"]'),  # ドロップダウン
            ]
            
            for trigger_selector, option_selector in custom_selects:
                if trigger_selector in processed_selectors:
                    continue
                trigger = await page.query_selector(trigger_selector)
                if trigger:
                    print(f"    🔍 カスタムセレクト検出: {trigger_selector}")
                    await trigger.click()
                    await page.wait_for_timeout(300)
                    
                    options = await page.query_selector_all(option_selector)
                    if options:
                        # 最初のオプションを選択
                        target_option = options[0]
                        target_text = await target_option.inner_text()
                        await target_option.click()
                        await page.wait_for_timeout(200)
                        
                        result['success'] = True
                        result['selector_used'] = trigger_selector
                        result['value'] = target_text
                        print(f"  ✅ {field_name} (カスタムセレクト): {target_text} 選択完了")
                        return result
            
            result['error'] = "カスタムセレクトが見つかりません"
            result['reason'] = 'select_custom_not_found'
            print(f"  ❌ カスタムセレクト処理失敗: 対応するコンポーネントが見つかりません")

        except Exception as e:
            result['error'] = str(e)
            result['reason'] = 'select_custom_failed'
            print(f"  ❌ カスタムセレクト処理エラー: {e}")
        
        return result

    async def _handle_radio(self, page, field: Dict, field_name: str, field_id: str, category: str, product: Product) -> Dict:
        """ラジオボタングループを処理（問い合わせ種別等の選択）"""
        result = {
            'success': False,
            'selector_used': None,
            'value': None,
            'category': category,
            'label': field.get('label', field_name),
            'error': None
        }

        try:
            debug_log(f"📻 _handle_radio開始: name={field_name}, id={field_id}, category={category}")

            # ラジオボタンを検索（name属性 → id → label）
            radios = []
            if field_name:
                radios = await page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
            if not radios and field_id:
                radios = await page.query_selector_all(f'input[type="radio"][id="{field_id}"]')
                # 単一要素の場合、name属性を取得して再検索
                if len(radios) == 1:
                    name_attr = await radios[0].get_attribute('name')
                    if name_attr:
                        radios = await page.query_selector_all(f'input[type="radio"][name="{name_attr}"]')

            if not radios:
                result['error'] = 'ラジオボタンが見つかりません'
                result['reason'] = 'radio_not_found'
                debug_log(f"  ❌ ラジオボタン未検出: name={field_name}, id={field_id}")
                return result

            # 各選択肢のlabel/valueを取得
            options = []
            for radio in radios:
                value = await radio.get_attribute('value') or ''
                radio_id = await radio.get_attribute('id') or ''

                # ラベル取得: 1) for属性のlabel 2) 親要素のテキスト 3) value
                label_text = ''
                if radio_id:
                    label_el = await page.query_selector(f'label[for="{radio_id}"]')
                    if label_el:
                        label_text = (await label_el.inner_text()).strip()
                if not label_text:
                    # 親要素（label）のテキスト
                    parent = await radio.evaluate('el => el.closest("label")?.innerText?.trim() || ""')
                    label_text = parent
                if not label_text:
                    label_text = value

                options.append({'element': radio, 'value': value, 'label': label_text})

            debug_log(f"  📻 選択肢: {[o['label'] or o['value'] for o in options]}")

            # 優先キーワードで選択
            priority_keywords = []
            if hasattr(product, 'inquiry_type_priority') and product.inquiry_type_priority:
                priority_keywords = [k.strip() for k in product.inquiry_type_priority.split(',') if k.strip()]

            # デフォルト優先キーワード（営業問い合わせ向け）
            default_priorities = ['その他', '一般', 'お問い合わせ', 'サービス', '提案', '協業',
                                  '取引', '営業', 'パートナー', 'other', 'general', 'inquiry']

            # IMP-030 Mod-2: 同意/プライバシー系ラジオは「同意する」を強制選択
            _radio_label = (field.get('label', '') or '').lower()
            _radio_combined = _radio_label + ' ' + (field_name or '').lower()
            if any(kw in _radio_combined for kw in ['同意', 'プライバシー', '個人情報', 'privacy', 'agree', 'consent', '規約', 'terms']):
                consent_priorities = ['同意する', '同意します', '同意', 'agree', 'accept', 'はい', 'yes']
                all_priorities = consent_priorities + priority_keywords
            else:
                all_priorities = priority_keywords + default_priorities

            # 優先順で選択
            selected = None
            for keyword in all_priorities:
                keyword_lower = keyword.lower()
                for opt in options:
                    if keyword_lower in opt['label'].lower() or keyword_lower in opt['value'].lower():
                        selected = opt
                        break
                if selected:
                    break

            # 該当なし → 最後の選択肢
            if not selected and options:
                selected = options[-1]

            if selected:
                try:
                    await selected['element'].click()
                    result['success'] = True
                    result['value'] = selected['label'] or selected['value']
                    result['selector_used'] = f'radio[name="{field_name}"] value="{selected["value"]}"'
                    debug_log(f"  ✅ ラジオ選択: 「{result['value']}」")
                except Exception as click_err:
                    # click失敗時はJavaScriptでチェック
                    try:
                        await selected['element'].evaluate('el => el.checked = true')
                        await selected['element'].dispatch_event('change')
                        result['success'] = True
                        result['value'] = selected['label'] or selected['value']
                        result['selector_used'] = f'radio[name="{field_name}"] JS fallback'
                        debug_log(f"  ✅ ラジオ選択(JS): 「{result['value']}」")
                    except Exception as js_err:
                        result['error'] = f'クリック失敗: {str(click_err)[:60]}'
                        result['reason'] = 'radio_js_fallback_failed'
                        debug_log(f"  ❌ ラジオ選択失敗: {click_err}")

        except Exception as e:
            result['error'] = str(e)[:80]
            result['reason'] = 'radio_click_failed'
            debug_log(f"  ❌ _handle_radio例外: {e}")

        return result

    async def _handle_checkbox(self, page, field: Dict, field_name: str, field_id: str, label: str, product: Product = None) -> Dict:
        """チェックボックスを処理（同意チェックボックス・選択式チェックボックス対応）
        
        - 同意チェックボックス（1つのみ）: 通常通りチェック
        - 選択式チェックボックス（同名で複数）: inquiry_type_priorityのキーワードでフィルタ
        
        多くのサイトではカスタムスタイルのため、input[type="checkbox"]は非表示で
        関連するlabel要素をクリックすることでチェックが入る仕組みになっている。
        """
        debug_log(f"🔲 _handle_checkbox開始: field_name={field_name}, field_id={field_id}, label={label}")
        debug_log(f"   field全体: {field}")
        
        # チェックボックスのカテゴリを推測（プライバシーポリシー等を識別）
        checkbox_category = self._infer_checkbox_category(field, field_name, field_id, label)
        debug_log(f"   チェックボックスカテゴリ: {checkbox_category}")
        
        result = {
            'success': False,
            'selector_used': None,
            'value': 'checked',
            'category': checkbox_category,
            'label': label,
            'error': None
        }
        
        # 優先キーワードを取得
        priority_keywords = []
        if product and hasattr(product, 'inquiry_type_priority') and product.inquiry_type_priority:
            priority_keywords = [kw.strip() for kw in product.inquiry_type_priority.split(',') if kw.strip()]
            debug_log(f"   優先キーワード: {priority_keywords}")
        
        # IDセレクタ用のエスケープ（#id形式のみ必要）
        def escape_id_selector(s):
            return s.replace('[', '\\[').replace(']', '\\]')
        
        # --- Phase 1: 通常のチェックボックス検索 ---
        checkbox_selectors = []
        
        if field_id:
            checkbox_selectors.append(f'input[type="checkbox"][id="{field_id}"]')
            if '[' not in field_id and ']' not in field_id:
                checkbox_selectors.append(f'#{field_id}')
            else:
                checkbox_selectors.append(f'#{escape_id_selector(field_id)}')
        
        if field_name:
            checkbox_selectors.append(f'input[type="checkbox"][name="{field_name}"]')
            base_name = field_name.split('[')[0]
            if base_name != field_name:
                checkbox_selectors.append(f'input[type="checkbox"][name^="{base_name}"]')
        
        debug_log(f"   チェックボックスセレクタ候補: {checkbox_selectors}")

        any_element_found = False
        for selector in checkbox_selectors:
            try:
                debug_log(f"    🔍 チェックボックス検索中: {selector}")
                elements = await page.query_selector_all(selector)
                debug_log(f"    📍 マッチした要素数: {len(elements)}")
                
                if not elements:
                    continue

                any_element_found = True
                # --- 選択式チェックボックス判定（同名で複数ある場合）---
                if len(elements) > 1:
                    debug_log(f"    📋 選択式チェックボックス検出（{len(elements)}個）")
                    
                    # 各チェックボックスのvalue/labelを取得してフィルタ
                    checkbox_items = []
                    for i, element in enumerate(elements):
                        value = await element.get_attribute('value') or ''
                        # ラベルを取得
                        cb_label = await element.evaluate("""(el) => {
                            const label = el.closest('label');
                            if (label) return label.textContent.trim();
                            const next = el.nextSibling;
                            if (next && next.textContent) return next.textContent.trim();
                            return '';
                        }""")
                        checkbox_items.append({
                            'index': i,
                            'element': element,
                            'value': value,
                            'label': cb_label
                        })
                        debug_log(f"      [{i}] value={value}, label={cb_label[:30] if cb_label else 'なし'}")
                    
                    # 優先キーワードでフィルタ
                    items_to_check = []
                    for keyword in priority_keywords:
                        for item in checkbox_items:
                            if keyword in item['value'] or keyword in item['label']:
                                if item not in items_to_check:
                                    items_to_check.append(item)
                                    debug_log(f"    🎯 キーワードマッチ: {item['label'] or item['value']} (keyword: {keyword})")
                    
                    # マッチしない場合は「その他」を探す
                    if not items_to_check:
                        for item in checkbox_items:
                            if 'その他' in item['value'] or 'その他' in item['label'] or 'other' in item['value'].lower():
                                items_to_check.append(item)
                                debug_log(f"    🎯 デフォルト選択: {item['label'] or item['value']}")
                                break
                    
                    # それでもない場合は最初の項目
                    if not items_to_check and checkbox_items:
                        items_to_check.append(checkbox_items[0])
                        debug_log(f"    🎯 最初の項目を選択: {checkbox_items[0]['label'] or checkbox_items[0]['value']}")
                    
                    # 選択した項目だけをチェック
                    checked_values = []
                    for item in items_to_check:
                        element = item['element']
                        is_checked = await element.is_checked()
                        if is_checked:
                            debug_log(f"    ℹ️ [{item['index']}]: 既にチェック済み")
                            checked_values.append(item['value'] or item['label'])
                            continue
                        
                        try:
                            await element.check(timeout=5000)
                            checked_values.append(item['value'] or item['label'])
                            debug_log(f"    ✅ [{item['index']}]: {item['label'] or item['value']} チェック完了")
                        except Exception as e:
                            debug_log(f"    ⚠️ [{item['index']}] check()失敗: {e}")
                            try:
                                await element.click(force=True, timeout=3000)
                                checked_values.append(item['value'] or item['label'])
                                debug_log(f"    ✅ [{item['index']}]: force click完了")
                            except Exception as e2:
                                debug_log(f"    ⚠️ [{item['index']}] force click失敗: {e2}")
                    
                    if checked_values:
                        result['success'] = True
                        result['selector_used'] = selector
                        result['value'] = ', '.join(checked_values)
                        debug_log(f"  ✅ {field_name} (選択式checkbox): {result['value']} チェック完了")
                        return result
                
                else:
                    # --- 単一チェックボックス（同意チェックボックス等）---
                    element = elements[0]
                    is_visible = await element.is_visible()
                    is_checked = await element.is_checked()
                    debug_log(f"    📍 単一チェックボックス: visible={is_visible}, checked={is_checked}")
                    
                    if is_checked:
                        result['success'] = True
                        result['selector_used'] = selector
                        result['reason'] = 'checkbox_already_checked'
                        debug_log(f"  ✅ {field_name} (checkbox): 既にチェック済み [{selector}]")
                        return result
                    
                    if is_visible:
                        try:
                            await element.check(timeout=5000)
                            result['success'] = True
                            result['selector_used'] = selector
                            debug_log(f"  ✅ {field_name} (checkbox): チェック完了 [{selector}]")
                            return result
                        except Exception as e:
                            debug_log(f"    ⚠️ check()失敗: {e}")
                            try:
                                await element.click(force=True, timeout=3000)
                                if await element.is_checked():
                                    result['success'] = True
                                    result['selector_used'] = selector
                                    debug_log(f"  ✅ {field_name} (checkbox): force click完了 [{selector}]")
                                    return result
                            except Exception as e2:
                                debug_log(f"    ⚠️ force click失敗: {e2}")
                    else:
                        try:
                            await element.dispatch_event('click')
                            if await element.is_checked():
                                result['success'] = True
                                result['selector_used'] = selector
                                debug_log(f"  ✅ {field_name} (checkbox): dispatch_event完了 [{selector}]")
                                return result
                        except Exception as e:
                            debug_log(f"    ⚠️ dispatch_event失敗: {e}")
                            
            except Exception as e:
                debug_log(f"    ❌ セレクタエラー: {selector} - {e}")
                continue
        
        # --- Phase 2: ラベル要素をクリック（非表示チェックボックス対応） ---
        label_selectors = []
        
        if field_id:
            label_selectors.append(f'label[for="{field_id}"]')
        if field_name:
            base_name = field_name.split('[')[0]
            label_selectors.append(f'label[for^="{base_name}"]')
        
        # 同意系のラベルを探す
        if label and ('同意' in label or '規約' in label):
            label_selectors.append('label:has(input[type="checkbox"])')
            label_selectors.append('span:has(input[type="checkbox"])')
            label_selectors.append('div:has(input[type="checkbox"])')
        
        debug_log(f"   ラベルセレクタ候補: {label_selectors}")
        
        for selector in label_selectors:
            try:
                debug_log(f"    🔍 ラベル検索中: {selector}")
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    debug_log(f"    📍 ラベル発見: visible={is_visible}")
                    
                    if is_visible:
                        await element.click()
                        await page.wait_for_timeout(300)  # クリック後少し待機
                        
                        # チェック状態を確認
                        for cb_selector in checkbox_selectors:
                            cb = await page.query_selector(cb_selector)
                            if cb and await cb.is_checked():
                                result['success'] = True
                                result['selector_used'] = f"label_click:{selector}"
                                debug_log(f"  ✅ {field_name} (checkbox): ラベルクリックでチェック完了 [{selector}]")
                                return result
                        
                        debug_log(f"    ⚠️ ラベルクリック後もチェックされていない")
            except Exception as e:
                debug_log(f"    ❌ ラベルクリックエラー: {selector} - {e}")
                continue
        
        # --- Phase 3: force=True でclick()を試す（最終手段） ---
        for selector in checkbox_selectors:
            try:
                debug_log(f"    🔍 force click試行: {selector}")
                element = await page.query_selector(selector)
                if element:
                    # Playwrightのdispatch_eventでクリックイベントを発火
                    await element.dispatch_event('click')
                    await page.wait_for_timeout(300)
                    
                    if await element.is_checked():
                        result['success'] = True
                        result['selector_used'] = f"dispatch_event:{selector}"
                        debug_log(f"  ✅ {field_name} (checkbox): dispatch_event完了 [{selector}]")
                        return result
            except Exception as e:
                debug_log(f"    ❌ dispatch_eventエラー: {selector} - {e}")
                continue
        
        # 失敗reason判定: セレクタで1つも見つからなかったか、操作失敗か
        if not result.get('reason'):
            result['reason'] = 'checkbox_click_failed' if any_element_found else 'checkbox_not_found'
        debug_log(f"  ❌ {field_name} (checkbox): 全ての方法で失敗 (reason={result['reason']})")
        return result
    
    async def _submit_form(self, page) -> Dict:
        """submitボタンを検出してクリック

        検出優先順位:
        1. 入力済みフォーム要素内の button[type="submit"] / input[type="submit"]
        2. 入力済みフォーム要素内の「送信」「確認」テキストを含むボタン
        3. フォーム要素内で見つからない場合、ページ全体からフォールバック検索
        4. form.submit() による強制送信

        JS alert/confirm ダイアログは自動的にacceptする。
        """
        result = {'success': False, 'method': None, 'error': None}

        # JS alert/confirm を自動accept
        page.on('dialog', lambda dialog: asyncio.ensure_future(dialog.accept()))

        # ターゲットフォームを特定（入力済みフィールドが最も多いform要素）
        target_form = await page.evaluate_handle('''() => {
            const forms = document.querySelectorAll('form');
            if (forms.length === 0) return null;
            if (forms.length === 1) return forms[0];

            let bestForm = null;
            let maxFilled = 0;

            for (const form of forms) {
                const inputs = form.querySelectorAll('input, textarea, select');
                let filled = 0;
                for (const input of inputs) {
                    if (input.type === 'hidden' || input.type === 'submit') continue;
                    if (input.tagName === 'SELECT') {
                        if (input.selectedIndex > 0) filled++;
                    } else if (input.type === 'checkbox' || input.type === 'radio') {
                        if (input.checked) filled++;
                    } else if (input.value && input.value.trim()) {
                        filled++;
                    }
                }
                if (filled > maxFilled) {
                    maxFilled = filled;
                    bestForm = form;
                }
            }
            return bestForm;
        }''')

        # ElementHandleが有効か確認
        form_scope = None
        try:
            tag = await target_form.get_property('tagName')
            tag_val = await tag.json_value()
            if tag_val:
                form_scope = target_form
                form_id = await page.evaluate('(el) => el.id || el.action || "(no id)"', target_form)
                print(f"  🎯 ターゲットフォーム特定: {form_id}")
        except Exception:
            form_scope = None
            print(f"  ⚠️ ターゲットフォーム特定失敗 → ページ全体から検索")

        # IMP-022 Mod-2: 未選択の必須selectを自動選択（送信前）
        try:
            auto_selected = await page.evaluate('''() => {
                let count = 0;
                const selects = document.querySelectorAll('select');
                for (const sel of selects) {
                    // 未選択（value空 or selectedIndex=0でfirst optionが空）かチェック
                    const isUnselected = !sel.value ||
                        (sel.selectedIndex === 0 && sel.options[0] && !sel.options[0].value);
                    // required属性 or aria-required or 親にrequiredクラス
                    const isRequired = sel.required || sel.getAttribute('aria-required') === 'true' ||
                        (sel.closest && sel.closest('.required, .must, [data-required]'));

                    if (isUnselected) {
                        // 最初の有効なoption（空でないvalue）を選択
                        for (let i = 1; i < sel.options.length; i++) {
                            if (sel.options[i].value) {
                                sel.selectedIndex = i;
                                sel.value = sel.options[i].value;
                                sel.dispatchEvent(new Event('change', { bubbles: true }));
                                sel.dispatchEvent(new Event('input', { bubbles: true }));
                                count++;
                                break;
                            }
                        }
                    }
                }
                return count;
            }''')
            if auto_selected > 0:
                print(f"  📋 IMP-022: 未選択select {auto_selected}件を自動選択")
                await asyncio.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ IMP-022 select自動選択エラー: {e}")

        # IMP-023 Mod-1: 初回送信前のチェックボックス自動チェック（プライバシー同意等）
        try:
            pre_submit_cb = await page.evaluate("""() => {
                let count = 0;
                // Pass 1: name/id属性でマッチ
                const selectors = [
                    'input[type="checkbox"][name*="privacy"]',
                    'input[type="checkbox"][name*="agree"]',
                    'input[type="checkbox"][name*="consent"]',
                    'input[type="checkbox"][name*="policy"]',
                    'input[type="checkbox"][name*="terms"]',
                    'input[type="checkbox"][name*="personal"]',
                    'input[type="checkbox"][name*="confirm"]',
                    'input[type="checkbox"][id*="privacy"]',
                    'input[type="checkbox"][id*="agree"]',
                    'input[type="checkbox"][id*="consent"]',
                    'input[type="checkbox"][id*="policy"]'
                ];
                for (const sel of selectors) {
                    for (const cb of document.querySelectorAll(sel)) {
                        if (!cb.checked) {
                            // IMP-026 Mod-1: label要素経由でクリック（React/Vue対応）
                            const label = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                            if (label) {
                                label.click();
                            } else {
                                cb.click();
                            }
                            // click()で切り替わらなかった場合のフォールバック
                            if (!cb.checked) {
                                cb.checked = true;
                            }
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                            cb.dispatchEvent(new Event('input', { bubbles: true }));
                            count++;
                        }
                    }
                }
                // Pass 2: ラベルテキストでマッチ（IMP-025 Mod-1: キーワード拡充）
                if (count === 0) {
                    for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
                        if (cb.checked) continue;
                        const label = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                        const text = (label ? label.textContent : '').toLowerCase();
                        const nearText = cb.parentElement ? cb.parentElement.textContent.toLowerCase() : '';
                        // 3階層上まで探索（ラッパーdivの外にラベルがある場合）
                        let grandText = '';
                        let el = cb.parentElement;
                        for (let i = 0; i < 3 && el; i++) {
                            grandText += ' ' + (el.textContent || '').toLowerCase();
                            el = el.parentElement;
                        }
                        const combined = text + ' ' + nearText + ' ' + grandText;
                        if (combined.includes('同意') || combined.includes('プライバシー') ||
                            combined.includes('個人情報') || combined.includes('agree') ||
                            combined.includes('privacy') || combined.includes('規約') ||
                            combined.includes('承諾') || combined.includes('了承') ||
                            combined.includes('accept') || combined.includes('terms') ||
                            combined.includes('policy') || combined.includes('confirm') ||
                            combined.includes('i have read') || combined.includes('i understand') ||
                            combined.includes('利用規約') || combined.includes('ポリシー') ||
                            combined.includes('確認しました') || combined.includes('了解')) {
                            const label2 = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                            if (label2) {
                                label2.click();
                            } else {
                                cb.click();
                            }
                            if (!cb.checked) {
                                cb.checked = true;
                            }
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                            cb.dispatchEvent(new Event('input', { bubbles: true }));
                            count++;
                        }
                    }
                }
                // Pass 3: 残りの未チェックCBが1-2個なら全チェック（必須CBの可能性）
                if (count === 0) {
                    const unchecked = [...document.querySelectorAll('input[type="checkbox"]')].filter(cb => {
                        if (cb.checked) return false;
                        const style = window.getComputedStyle(cb);
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        // 多選択グループ（同じname）は除外
                        if (cb.name) {
                            const sameGroup = document.querySelectorAll('input[type="checkbox"][name="' + cb.name + '"]');
                            if (sameGroup.length > 3) return false;
                        }
                        return true;
                    });
                    if (unchecked.length > 0 && unchecked.length <= 2) {
                        for (const cb of unchecked) {
                            const label3 = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                            if (label3) {
                                label3.click();
                            } else {
                                cb.click();
                            }
                            if (!cb.checked) {
                                cb.checked = true;
                            }
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                            cb.dispatchEvent(new Event('input', { bubbles: true }));
                            count++;
                        }
                    }
                }
                return count;
            }""")
            if pre_submit_cb > 0:
                print(f"  ☑️ IMP-023: 送信前チェックボックス {pre_submit_cb}件を自動チェック")
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # IMP-027 Mod-3b: 未入力visible inputフィールドへの自動入力（label/placeholderベース推測）
        try:
            auto_filled = await page.evaluate("""(formDataStr) => {
                const formData = JSON.parse(formDataStr);
                let filled = 0;
                const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]):not([type="file"]):not([type="image"])');
                for (const input of inputs) {
                    if (input.value && input.value.trim()) continue;  // 既に値があるならスキップ
                    const style = window.getComputedStyle(input);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    // label/placeholderからカテゴリを推測
                    const label = input.closest('label') || document.querySelector('label[for="' + input.id + '"]');
                    const labelText = (label ? label.textContent : '').toLowerCase();
                    const ph = (input.placeholder || '').toLowerCase();
                    const name = (input.name || '').toLowerCase();
                    const hint = labelText + ' ' + ph + ' ' + name;
                    let value = '';
                    if (hint.match(/mail|メール|eメール|e-mail/)) value = formData.email || '';
                    else if (hint.match(/会社|company|法人|社名|勤務先/)) value = formData.company || '';
                    else if (hint.match(/電話|tel|phone/)) value = formData.phone || '';
                    else if (hint.match(/姓|last.?name|苗字|sei/)) value = formData.last_name || '';
                    else if (hint.match(/名(?!前)|first.?name|mei/)) value = formData.first_name || '';
                    else if (hint.match(/名前|氏名|お名前|name|full.?name/)) value = formData.full_name || '';
                    else if (hint.match(/url|ウェブ|web|ホームページ|hp/)) value = formData.url || '';
                    if (!value) continue;
                    const nativeSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    );
                    if (nativeSetter && nativeSetter.set) {
                        nativeSetter.set.call(input, value);
                    } else {
                        input.value = value;
                    }
                    input.dispatchEvent(new Event('focus', { bubbles: true }));
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                    input.dispatchEvent(new Event('blur', { bubbles: true }));
                    input.setAttribute('data-fill-value', value);
                    filled++;
                }
                return filled;
            }""", self._get_form_data_json())
            if auto_filled and auto_filled > 0:
                print(f"  📝 IMP-027: 未入力フィールド {auto_filled}件にlabelベース自動入力")
        except Exception:
            pass

        # IMP-026 Mod-2: 未入力textareaフォールバック（お問い合わせ内容等の入力漏れ対策）
        try:
            message_text = getattr(self, '_message_text', '')
            if message_text:
                unfilled_ta = await page.evaluate("""(msg) => {
                    let filled = 0;
                    const textareas = document.querySelectorAll('textarea');
                    for (const ta of textareas) {
                        if (ta.value && ta.value.trim().length > 0) continue;
                        const style = window.getComputedStyle(ta);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                        // textareaが空なのでメッセージを入力
                        const nativeSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLTextAreaElement.prototype, 'value'
                        );
                        if (nativeSetter && nativeSetter.set) {
                            nativeSetter.set.call(ta, msg);
                        } else {
                            ta.value = msg;
                        }
                        ta.dispatchEvent(new Event('focus', { bubbles: true }));
                        ta.dispatchEvent(new Event('input', { bubbles: true }));
                        ta.dispatchEvent(new Event('change', { bubbles: true }));
                        ta.dispatchEvent(new Event('blur', { bubbles: true }));
                        ta.setAttribute('data-fill-value', msg);
                        filled++;
                    }
                    return filled;
                }""", message_text)
                if unfilled_ta and unfilled_ta > 0:
                    print(f"  📝 IMP-026: 未入力textarea {unfilled_ta}件にメッセージ自動入力")
        except Exception:
            pass

        # IMP-026 Mod-3: ふりがなフィールドのカタカナ→ひらがな自動変換
        try:
            kana_fixed = await page.evaluate("""() => {
                let fixed = 0;
                const kanaFields = document.querySelectorAll(
                    'input[name*="kana"], input[name*="furi"], input[name*="reading"],' +
                    'input[id*="kana"], input[id*="furi"], input[id*="reading"],' +
                    'input[placeholder*="ひらがな"], input[placeholder*="ふりがな"]'
                );
                for (const field of kanaFields) {
                    if (!field.value) continue;
                    const style = window.getComputedStyle(field);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    // ひらがな要求かどうかを判定
                    const placeholder = (field.placeholder || '').toLowerCase();
                    const label = field.closest('label') || document.querySelector('label[for="' + field.id + '"]');
                    const labelText = label ? label.textContent : '';
                    const nearText = field.parentElement ? field.parentElement.textContent : '';
                    const context = placeholder + ' ' + labelText + ' ' + nearText;
                    const wantsHiragana = context.includes('ひらがな') || context.includes('ふりがな') ||
                                          context.includes('せい') || context.includes('めい') ||
                                          (placeholder && /^[ぁ-ん\s]+$/.test(placeholder));
                    if (wantsHiragana) {
                        // カタカナ→ひらがな変換
                        const converted = field.value.replace(/[\u30A1-\u30F6]/g, (ch) =>
                            String.fromCharCode(ch.charCodeAt(0) - 0x60)
                        );
                        if (converted !== field.value) {
                            const nativeSetter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value'
                            );
                            if (nativeSetter && nativeSetter.set) {
                                nativeSetter.set.call(field, converted);
                            } else {
                                field.value = converted;
                            }
                            field.dispatchEvent(new Event('input', { bubbles: true }));
                            field.dispatchEvent(new Event('change', { bubbles: true }));
                            fixed++;
                        }
                    }
                }
                return fixed;
            }""")
            if kana_fixed and kana_fixed > 0:
                print(f"  🔤 IMP-026: ふりがな カタカナ→ひらがな変換 ({kana_fixed}件)")
        except Exception:
            pass

        # IMP-035: カタカナ要求フィールドのひらがな→カタカナ自動変換
        try:
            katakana_fixed = await page.evaluate("""() => {
                let fixed = 0;
                const kanaFields = document.querySelectorAll(
                    'input[name*="kana"], input[name*="furi"], input[name*="reading"],' +
                    'input[id*="kana"], input[id*="furi"], input[id*="reading"],' +
                    'input[placeholder*="カタカナ"], input[placeholder*="フリガナ"]'
                );
                for (const field of kanaFields) {
                    if (!field.value) continue;
                    const style = window.getComputedStyle(field);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    const placeholder = (field.placeholder || '');
                    const label = field.closest('label') || document.querySelector('label[for="' + field.id + '"]');
                    const labelText = label ? label.textContent : '';
                    const nearText = field.parentElement ? field.parentElement.textContent : '';
                    const context = placeholder + ' ' + labelText + ' ' + nearText;
                    const wantsKatakana = context.includes('カタカナ') || context.includes('フリガナ') ||
                                          context.includes('セイ') || context.includes('メイ') ||
                                          (placeholder && /^[\u30A1-\u30F6\s]+$/.test(placeholder));
                    if (wantsKatakana) {
                        const converted = field.value.replace(/[\u3041-\u3096]/g, (ch) =>
                            String.fromCharCode(ch.charCodeAt(0) + 0x60)
                        );
                        if (converted !== field.value) {
                            const nativeSetter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value'
                            );
                            if (nativeSetter && nativeSetter.set) {
                                nativeSetter.set.call(field, converted);
                            } else {
                                field.value = converted;
                            }
                            field.dispatchEvent(new Event('input', { bubbles: true }));
                            field.dispatchEvent(new Event('change', { bubbles: true }));
                            fixed++;
                        }
                    }
                }
                return fixed;
            }""")
            if katakana_fixed and katakana_fixed > 0:
                print(f"  🔤 IMP-035: フリガナ ひらがな→カタカナ変換 ({katakana_fixed}件)")
        except Exception:
            pass

        # IMP-025 Mod-3b: 全入力フィールドの現在値をdata-fill-valueに保存（JSfw復元用）
        try:
            await page.evaluate("""() => {
                const fields = document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]), textarea');
                for (const f of fields) {
                    if (f.value) f.setAttribute('data-fill-value', f.value);
                }
            }""")
        except Exception:
            pass

        # IMP-024 Mod-3 + IMP-025 Mod-3: JSフレームワーク値保持・復元強化
        try:
            jsfw_fixed = await page.evaluate("""() => {
                let fixed = 0;
                let restored = 0;
                const fields = document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]), textarea');

                const getNativeSetter = (field) => {
                    const proto = field.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                    return desc && desc.set ? desc.set : null;
                };

                for (const field of fields) {
                    const style = window.getComputedStyle(field);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;

                    const setter = getNativeSetter(field);

                    // IMP-025 Mod-3: data-fill-value属性に保存された値で復元
                    const savedValue = field.getAttribute('data-fill-value');
                    if (!field.value && savedValue) {
                        // Reactが値をクリアした場合 → native setterで復元
                        if (setter) {
                            setter.call(field, savedValue);
                        } else {
                            field.value = savedValue;
                        }
                        field.dispatchEvent(new Event('focus', { bubbles: true }));
                        field.dispatchEvent(new InputEvent('input', { bubbles: true, data: savedValue, inputType: 'insertText' }));
                        field.dispatchEvent(new Event('change', { bubbles: true }));
                        field.dispatchEvent(new Event('blur', { bubbles: true }));
                        restored++;
                        fixed++;
                        continue;
                    }

                    if (!field.value) continue;

                    // 既存: 値があるフィールドにイベント再発火
                    if (setter) {
                        setter.call(field, field.value);
                    }
                    field.dispatchEvent(new Event('focus', { bubbles: true }));
                    field.dispatchEvent(new Event('input', { bubbles: true }));
                    field.dispatchEvent(new Event('change', { bubbles: true }));
                    field.dispatchEvent(new Event('blur', { bubbles: true }));
                    fixed++;
                }
                const selects = document.querySelectorAll('select');
                for (const sel of selects) {
                    if (!sel.value) continue;
                    // IMP-025 Mod-4: selectにもnative setter + InputEvent
                    const nativeSelectSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLSelectElement.prototype, 'value'
                    );
                    if (nativeSelectSetter && nativeSelectSetter.set) {
                        nativeSelectSetter.set.call(sel, sel.value);
                    }
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                    sel.dispatchEvent(new Event('input', { bubbles: true }));
                    fixed++;
                }
                return {fixed, restored};
            }""")
            if isinstance(jsfw_fixed, dict):
                total = jsfw_fixed.get('fixed', 0)
                rest = jsfw_fixed.get('restored', 0)
                if total > 0:
                    msg = f"  🔧 IMP-024/025: JSフレームワーク イベント再発火 ({total}件"
                    if rest > 0:
                        msg += f", 値復元{rest}件"
                    msg += ")"
                    print(msg)
                    await asyncio.sleep(0.5)
            elif jsfw_fixed and jsfw_fixed > 0:
                print(f"  🔧 IMP-024: JSフレームワーク向けイベント再発火 ({jsfw_fixed}件)")
                await asyncio.sleep(0.5)
        except Exception:
            pass

        # IMP-024 Mod-1: submit前のbodyテキストを保存（DOM差分検出用）
        try:
            result['_pre_submit_body'] = await page.inner_text('body')
        except Exception:
            result['_pre_submit_body'] = ''

        # submitボタン検出（優先度順）
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("送信")',
            'button:has-text("確認")',
            'button:has-text("入力内容を確認")',
            'button:has-text("確認する")',
            'button:has-text("確認画面へ")',
            'input[value="送信"]',
            'input[value="確認"]',
            'input[value="送信する"]',
            'input[value="確認する"]',
            'input[value="確認画面へ"]',
            'a:has-text("送信")',
            'a:has-text("確認")',
        ]

        # Phase 1: フォームスコープ内で検索
        if form_scope:
            for selector in submit_selectors:
                try:
                    element = await form_scope.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            print(f"  🔘 submitボタン検出（フォーム内）: {selector}")
                            await element.click()
                            result['success'] = True
                            result['method'] = f'{selector} (scoped)'
                            break
                except Exception as e:
                    continue

        # Phase 2: フォーム内で見つからない場合、ページ全体からフォールバック
        if not result['success']:
            if form_scope:
                print(f"  ⚠️ フォーム内にsubmitボタンなし → ページ全体からフォールバック検索")
            for selector in submit_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            print(f"  🔘 submitボタン検出（ページ全体）: {selector}")
                            await element.click()
                            result['success'] = True
                            result['method'] = f'{selector} (page-wide fallback)'
                            break
                except Exception as e:
                    continue

        # Phase 3: セレクタで見つからない場合、ターゲットフォームのform.submit()を試行
        # Note: HTMLFormElement.prototype.submit.call() を使用して
        # name="submit" 要素による form.submit() の衝突を回避
        if not result['success']:
            try:
                if form_scope:
                    await page.evaluate('(form) => HTMLFormElement.prototype.submit.call(form)', form_scope)
                    print(f"  🔘 ターゲットフォーム.submit() で送信")
                    result['success'] = True
                    result['method'] = 'target_form.submit()'
                else:
                    submitted = await page.evaluate('''() => {
                        const form = document.querySelector('form');
                        if (form) {
                            HTMLFormElement.prototype.submit.call(form);
                            return true;
                        }
                        return false;
                    }''')
                    if submitted:
                        print(f"  🔘 form.submit() で送信")
                        result['success'] = True
                        result['method'] = 'form.submit()'
            except Exception as e:
                result['error'] = f"form.submit()失敗: {e}"

        if not result['success']:
            result['error'] = result.get('error') or 'submitボタンが見つかりません'
            print(f"  ❌ submitボタン検出失敗")
            return result

        # ページ遷移 or Ajax完了を待機
        try:
            await page.wait_for_load_state('networkidle', timeout=15000)
        except PlaywrightTimeout:
            print(f"  ⚠️ networkidle待機タイムアウト（続行）")

        await asyncio.sleep(2)  # 追加安定化待機
        print(f"  ✅ submit完了: {result['method']}")
        return result

    async def _handle_confirmation(self, page, pre_submit_url: str = '', pre_submit_body: str = '') -> Dict:
        """確認ページを検出して最終送信ボタンをクリック

        対応パターン:
        - 入力→確認→送信の3ステップ（日本のフォームに多い）
        - 1ページ完結型（確認ページなし → そのまま成功）
        - SPA非同期送信（ページ遷移なし → 完了メッセージ検出）
        """
        result = {
            'success': False,
            'confirmation_detected': False,
            'completion_detected': False,
            'method': None,
            'error': None
        }

        # IMP-010 + IMP-013: エラーキーワード
        error_keywords = [
            '必須項目に記入もれ', '必須項目を入力してください',
            '入力内容にエラー', 'この質問は必須です',
            'One or more fields have an error', 'Please check and try again',
            'required field', 'is required',
            '未入力の項目があります', '正しく入力してください',
            # IMP-013追加: 日本語
            '入力されたコードが正しくありません',
            '迷惑ポットとしてブロック', 'ブロックされました',
            'メッセージの送信に失敗', '送信に失敗しました',
            '入力に誤りがあります',
            '正しいメールアドレスを入力', '有効なメールアドレスを入力',
            '文字数が超えています', '文字以内で入力',
            '入力内容に問題があります',
            # IMP-013追加: 英語
            'Please fill out this field',
            "is missing an '@'", "Please include an '@'",
            'is not allowed',
            '414 ERROR', '413 ERROR', 'Request-URI Too Long',
            'Access Denied', 'Forbidden',
            'bot detected', 'spam detected', 'captcha',
            # IMP-029 Mod-4: 追加バリデーションエラーパターン
            'この項目は必須です', 'この欄は必須です',
            '電話番号の形式', '有効な電話番号',
            'メールアドレスの形式が', 'メールアドレスが正しくありません',
            '郵便番号を正しく', '半角数字で入力',
            '全角カタカナで入力', 'カタカナで入力してください',
            '入力に不備があります', '入力に不備が',
            'エラーがあります', 'もう一度ご確認',
            'Submission failed', 'submission error',
            'form could not be submitted',
            'フォームの送信に失敗',
            # IMP-032 Mod-4: 削除済み（常設テキスト誤検出のため IMP-034で差分方式に移行）
            # 以下は差分比較で検出するため、全文マッチからは除外
            '項目にエラー', '入力エラー',
            'Validation error', 'validation failed',
        ]

        # 送信完了キーワード
        completion_keywords = [
            'ありがとうございます', '送信が完了', '送信しました',
            '受け付けました', '受付完了', 'お問い合わせを受け付け',
            '送信完了', 'Thank you', 'successfully submitted',
            'お問い合わせいただき', '自動返信メール',
            # IMP-018追加: AJAXフォームの完了メッセージ
            'お問い合わせありがとう',  # 「ありがとう」のみだと広すぎるのでフォーム文脈限定
            'メッセージは送信されました',  # CF7デフォルト
            'Your message has been sent',  # CF7英語デフォルト
            'has been submitted',
            'was sent successfully',
            'メールを送信しました',
            '正常に送信',
            '送信されました',
            # IMP-032 Mod-3: 追加完了キーワード
            '完了しました', '完了いたしました',
            '承りました', '受信しました',
            '登録が完了', '登録しました', '登録完了',
            'お問い合わせ内容を送信',
            '正常に受け付け',
            '送信手続き',
            'お問い合わせが完了',
            'フォームが送信',
            '内容を受け付け',
            'お申し込みありがとう',
            'お申込みありがとう',
            'We have received',
            'Your inquiry has been',
            'Your request has been',
            'Message sent',
            'Successfully sent',
            'お問い合わせを承り',
        ]

        # IMP-011 + IMP-017: 確認ページキーワード（拡充）
        confirmation_keywords = [
            '入力内容の確認', '入力内容をご確認', '確認画面',
            '以下の内容で', 'ご確認ください', '内容をご確認',
            '送信してよろしいですか', '下記の内容で',
            # IMP-011追加
            'この内容で送信する', 'この内容で送信',
            '前の画面に戻る', '入力内容のご確認', '入力内容を確認',
            '以下の内容でお送りします', '上記の内容で送信',
            '内容をご確認のうえ',
            # IMP-017追加
            'よろしければ', '下記内容で', '以下の内容でよろしいですか',
            '入力内容に間違い', '間違いがなければ', '修正する場合',
            '上記の内容で', '上記内容で', '内容に間違い',
            'お問い合わせ内容の確認', 'お問い合せ内容の確認',
            'Confirm', 'confirm your', 'review your',
        ]

        # ページテキスト取得
        page_text = ''
        try:
            page_text = await page.inner_text('body')
        except Exception:
            page_text = ''

        # 判定ロジック（IMP-010 + IMP-011統合）
        detect_result = self._detect_page_state(page_text, error_keywords, completion_keywords, confirmation_keywords, pre_submit_body)

        if detect_result == 'error':
            matched = [kw for kw in error_keywords if kw in page_text]
            print(f"  ❌ 送信後エラー検出: {matched[0]}")
            result['error'] = f"form_submission_error: {matched[0]}"
            return result

        if detect_result == 'completed':
            print(f"  🎉 送信完了ページを検出")
            result['success'] = True
            result['completion_detected'] = True
            return result

        if detect_result == 'confirmation':
            print(f"  📋 確認ページを検出 → 最終送信ボタンを探索")
            result['confirmation_detected'] = True
            return await self._click_final_submit(page, result, error_keywords, completion_keywords)

        # IMP-018: キーワード未検出 → AJAX成功パターンをチェック
        ajax_success = await self._check_ajax_success(page)
        if ajax_success:
            print(f"  🎉 AJAX送信成功を検出（CF7/success要素）")
            result['success'] = True
            result['completion_detected'] = True
            return result

        # IMP-011: URL変化を確認
        current_url = page.url
        if pre_submit_url and current_url != pre_submit_url:
            # IMP-018: Hash-only変化はページ遷移として扱わない
            if self._is_same_page_hash_change(pre_submit_url, current_url):
                print(f"  ℹ️ Hash変化のみ検出: {pre_submit_url} → {current_url}")
                # AJAXフォームの可能性大 → 追加待機してDOMを再チェック
                await asyncio.sleep(2)
                try:
                    page_text = await page.inner_text('body')
                except Exception:
                    page_text = ''
                detect_result2 = self._detect_page_state(page_text, error_keywords, completion_keywords, confirmation_keywords, pre_submit_body)
                if detect_result2 == 'completed':
                    print(f"  🎉 Hash変化後に送信完了を検出")
                    result['success'] = True
                    result['completion_detected'] = True
                    return result
                if detect_result2 == 'error':
                    matched = [kw for kw in error_keywords if kw in page_text]
                    print(f"  ❌ Hash変化後にエラー検出: {matched[0]}")
                    result['error'] = f"form_submission_error: {matched[0]}"
                    return result
                # 再度AJAXチェック
                ajax_success2 = await self._check_ajax_success(page)
                if ajax_success2:
                    print(f"  🎉 Hash変化後にAJAX送信成功を検出")
                    result['success'] = True
                    result['completion_detected'] = True
                    return result
                # Hash変化のみでキーワードもAJAXも未検出 → 送信未確認
                print(f"  📋 送信未確認だがエラーなし → 暫定成功（Gemini Vision判定へ）")
                result['success'] = True
                result['completion_unverified'] = True
                result['reason'] = 'completion_unverified: Hash変化のみ・完了未検出'
                return result
            else:
                print(f"  🔄 URL変化検出: {pre_submit_url} → {current_url}")

                # IMP-027 Mod-1: URLに成功系パスが含まれていれば即成功判定
                url_lower = current_url.lower()
                success_url_patterns = ['/thanks', '/thank-you', '/thankyou', '/complete',
                                        '/success', '/done', '/finished', '/sent',
                                        '/contact_thanks', '/inquiry_thanks', '/form_thanks',
                                        'thanks.html', 'thankyou.html', 'complete.html']
                if any(pat in url_lower for pat in success_url_patterns):
                    print(f"  🎉 IMP-027: 成功URLパターン検出 → 送信完了")
                    result['success'] = True
                    result['completion_detected'] = True
                    result['method'] = f'url_success_pattern: {current_url}'
                    return result

                # 実際のページ遷移 → 追加待機してから再判定
                await asyncio.sleep(2)
                try:
                    page_text = await page.inner_text('body')
                except Exception:
                    page_text = ''

                detect_result2 = self._detect_page_state(page_text, error_keywords, completion_keywords, confirmation_keywords, pre_submit_body)

                if detect_result2 == 'error':
                    matched = [kw for kw in error_keywords if kw in page_text]
                    print(f"  ❌ 遷移先でエラー検出: {matched[0]}")
                    result['error'] = f"form_submission_error: {matched[0]}"
                    return result

                if detect_result2 == 'completed':
                    print(f"  🎉 遷移先で送信完了を検出")
                    result['success'] = True
                    result['completion_detected'] = True
                    return result

                if detect_result2 == 'confirmation':
                    print(f"  📋 遷移先で確認ページを検出 → 最終送信ボタンを探索")
                    result['confirmation_detected'] = True
                    return await self._click_final_submit(page, result, error_keywords, completion_keywords)

                # IMP-017: 遷移先でキーワード未検出 → 送信ボタン有無で確認画面を推定
                has_submit_btn = await self._has_submit_button(page)
                if has_submit_btn:
                    print(f"  📋 遷移先に送信ボタン検出 → 確認画面と推定")
                    result['confirmation_detected'] = True
                    return await self._click_final_submit(page, result, error_keywords, completion_keywords)

                # IMP-031 Mod-1b: 送信ボタンは未検出だが、修正/戻るボタンがあれば確認ページ
                try:
                    _has_back_btn = await page.evaluate('''() => {
                        const btns = document.querySelectorAll('button, input[type="submit"], input[type="button"], a');
                        const backWords = ['戻る', '修正', '修正する', '入力画面に戻る', '入力画面へ戻る'];
                        for (const btn of btns) {
                            const style = window.getComputedStyle(btn);
                            if (style.display === 'none' || style.visibility === 'hidden') continue;
                            const text = (btn.textContent || btn.value || '').trim();
                            if (backWords.some(w => text.includes(w))) return true;
                        }
                        return false;
                    }''')
                    if _has_back_btn:
                        print(f"  📋 IMP-031: 遷移先に修正/戻るボタン検出 → 確認ページと推定")
                        result['confirmation_detected'] = True
                        return await self._click_final_submit(page, result, error_keywords, completion_keywords)
                except Exception:
                    pass

                print(f"  ℹ️ 遷移先でキーワード未検出・送信ボタンなし → 送信完了として処理")
                result['success'] = True
                return result

        # IMP-024 Mod-1: DOM差分検出 → AJAX送信済みかを判定
        try:
            post_submit_body = await page.inner_text('body')
        except Exception:
            post_submit_body = ''

        # pre_submit_bodyは呼び出し元から引数で渡される
        dom_changed = False
        if pre_submit_body and post_submit_body:
            # テキストの差分量を計算（新しく出現したテキスト）
            pre_lines = set(pre_submit_body.split('\n'))
            post_lines = set(post_submit_body.split('\n'))
            new_lines = post_lines - pre_lines
            new_text = ' '.join(l.strip() for l in new_lines if l.strip())
            if len(new_text) > 10:
                dom_changed = True
                print(f"  🔍 IMP-024: DOM変化検出 ({len(new_text)}文字の新テキスト)")
                # 新テキストに完了キーワードがないか再チェック
                for kw in completion_keywords:
                    if kw in new_text:
                        print(f"  🎉 IMP-024: DOM変化内に完了キーワード検出: {kw}")
                        result['success'] = True
                        result['completion_detected'] = True
                        return result
                # 新テキストにエラーキーワードがないか再チェック
                for kw in error_keywords:
                    if kw in new_text:
                        print(f"  ❌ IMP-024: DOM変化内にエラーキーワード検出: {kw}")
                        result['error'] = f"form_submission_error: {kw}"
                        return result

        # IMP-024: DOM変化あり → 確認ページか完了ページかを追加判定
        if dom_changed:
            # IMP-031 Mod-1: DOM変化後に確認ページパターンをチェック
            # 修正/戻るボタン + 送信ボタンが共存 → 確認ページ
            try:
                _is_confirm_page = await page.evaluate('''() => {
                    const bodyText = document.body.innerText || '';
                    const allBtns = document.querySelectorAll('button, input[type="submit"], input[type="button"], a[role="button"], [role="button"]');
                    let hasBack = false;
                    let hasSubmit = false;
                    const backWords = ['戻る', '修正', '戻って', 'back', '修正する', '入力画面に戻る'];
                    const submitWords = ['送信', '送信する', 'submit', 'Submit', 'SEND', 'Send'];
                    for (const btn of allBtns) {
                        const style = window.getComputedStyle(btn);
                        if (style.display === 'none' || style.visibility === 'hidden' || !btn.offsetParent) continue;
                        const text = (btn.textContent || btn.value || '').trim();
                        if (backWords.some(w => text.includes(w))) hasBack = true;
                        if (submitWords.some(w => text.includes(w))) hasSubmit = true;
                    }
                    // Also check for step indicators
                    const stepPattern = /(ステップ|step|STEP)\s*(2|２|3|３)|確認/i;
                    const hasStepIndicator = stepPattern.test(bodyText.substring(0, 500));
                    return (hasBack && hasSubmit) || (hasStepIndicator && hasSubmit);
                }''')
                if _is_confirm_page:
                    print(f"  📋 IMP-031: DOM変化後に確認ページ検出（修正+送信ボタン共存）→ 最終送信へ")
                    result['confirmation_detected'] = True
                    return await self._click_final_submit(page, result, error_keywords, completion_keywords)
            except Exception:
                pass

            # IMP-032 Mod-3b: DOM変化後にフォーム消失をチェック
            try:
                _form_disappeared = await page.evaluate('''() => {
                    const forms = document.querySelectorAll('form');
                    if (forms.length === 0) return true;
                    let totalVisible = 0;
                    for (const f of forms) {
                        const inputs = f.querySelectorAll('input:not([type="hidden"]), textarea, select');
                        for (const inp of inputs) {
                            try {
                                const s = window.getComputedStyle(inp);
                                if (s.display !== 'none' && s.visibility !== 'hidden' && inp.offsetParent) totalVisible++;
                            } catch(e) {}
                        }
                    }
                    return totalVisible === 0;
                }''')
                if _form_disappeared:
                    print(f"  ✅ IMP-032: DOM変化後にフォーム消失検出 → 送信成功と判定")
                    result['success'] = True
                    result['completion_detected'] = True
                    result['reason'] = 'ajax_dom_changed: form disappeared after DOM change'
                    return result
            except Exception:
                pass

            # IMP-032 Mod-3b: ページタイトルに完了パターンがないかチェック
            try:
                _title = await page.evaluate('() => document.title || ""')
                _title_keywords = ['ありがとう', '完了', 'thank', 'Thank', 'complete', 'Complete', 'success', 'Success']
                for _tk in _title_keywords:
                    if _tk in _title:
                        print(f"  ✅ IMP-032: ページタイトルに完了パターン検出: {_title}")
                        result['success'] = True
                        result['completion_detected'] = True
                        result['reason'] = f'ajax_dom_changed: title contains {_tk}'
                        return result
            except Exception:
                pass

            print(f"  📋 IMP-024: DOM変化ありだが判定キーワードなし → 暫定成功")
            result['success'] = True
            result['completion_unverified'] = True
            result['reason'] = 'ajax_dom_changed: DOM変化あり・キーワード未検出'
            return result

        # IMP-017 + IMP-018: URLも変わらない場合、AJAX成功チェック済みなので送信ボタン有無で確認画面を推定
        has_submit_btn = await self._has_submit_button(page)
        if has_submit_btn:
            # IMP-024: DOM変化がない場合のみ確認画面と推定
            print(f"  📋 送信ボタン検出・DOM変化なし → 確認画面と推定（SPA/モーダル型）")
            result['confirmation_detected'] = True
            return await self._click_final_submit(page, result, error_keywords, completion_keywords)

        # IMP-012: URLも変わらない + 完了キーワードなし → 送信未確認
        print(f"  📋 送信未確認だがエラーなし → 暫定成功（Gemini Vision判定へ）")
        result['success'] = True
        result['completion_unverified'] = True
        result['reason'] = 'completion_unverified: 完了キーワード未検出・URL変化なし'
        return result

    def _detect_page_state(self, page_text: str, error_keywords: list,
                           completion_keywords: list, confirmation_keywords: list,
                           pre_submit_text: str = '') -> str:
        """ページテキストから状態を判定: 'error' / 'completed' / 'confirmation' / 'unknown'
        
        IMP-034: 差分比較方式
        - completion/confirmationキーワードを先にチェック（成功判定優先）
        - errorキーワードは送信後に新たに出現したもののみ検出
        - 送信前から存在する常設テキスト（必須ラベル等）は無視
        """
        # Step 1: completion/confirmationを先にチェック（成功優先）
        has_completion = any(kw in page_text for kw in completion_keywords)
        has_confirmation = any(kw in page_text for kw in confirmation_keywords)
        
        if has_completion and has_confirmation:
            print(f"  ⚠️ IMP-023: completion/confirmation両方検出 → confirmation優先")
            return 'confirmation'
        if has_completion:
            return 'completed'
        if has_confirmation:
            return 'confirmation'
        
        # Step 2: エラーチェック（IMP-034: 差分比較方式）
        # 送信前テキストがある場合、送信後に新たに出現したエラーのみ検出
        if pre_submit_text:
            new_errors = [kw for kw in error_keywords if kw in page_text and kw not in pre_submit_text]
            if new_errors:
                print(f"  ❌ IMP-034: 送信後に新規エラー出現: {new_errors[0]}")
                return 'error'
        else:
            # 送信前テキストがない場合は従来方式（後方互換）
            if any(kw in page_text for kw in error_keywords):
                return 'error'
        
        return 'unknown'

    async def _has_submit_button(self, page) -> bool:
        """IMP-017: ページ上に送信ボタンが存在するか確認（確認画面の推定用）

        確認画面には通常「送信」「送信する」等のボタンがある。
        初回submitで使った「確認」「確認画面へ」等のボタンは除外する。
        """
        try:
            has_btn = await page.evaluate('''() => {
                const elements = document.querySelectorAll(
                    'button, input[type="submit"], input[type="button"], a[role="button"], [role="button"]'
                );
                const skipTexts = ['戻る', '修正', '戻って', 'back', '確認画面', '確認へ'];
                const submitTexts = ['送信', '送信する', 'submit', 'Submit', 'SEND', 'Send', 'この内容で', '上記内容で', '上記の内容で', '以上の内容で', 'はい'];
                for (const el of elements) {
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || !el.offsetParent) continue;
                    const text = (el.textContent || el.value || '').trim();
                    if (skipTexts.some(s => text.includes(s))) continue;
                    if (submitTexts.some(s => text.includes(s))) return true;
                }
                return false;
            }''')
            return has_btn
        except Exception:
            return False

    def _is_same_page_hash_change(self, url1: str, url2: str) -> bool:
        """IMP-018: Hash部分のみの変化かを判定"""
        p1 = urlparse(url1)
        p2 = urlparse(url2)
        return (p1.scheme == p2.scheme and p1.netloc == p2.netloc
                and p1.path.rstrip('/') == p2.path.rstrip('/')
                and p1.query == p2.query)

    async def _check_ajax_success(self, page) -> bool:
        """IMP-018: AJAX送信の成功レスポンスを検出"""
        try:
            return await page.evaluate('''() => {
                // Contact Form 7 成功パターン
                const cf7Form = document.querySelector('form.wpcf7-form[data-status="mail_sent"]');
                if (cf7Form) return true;
                const cf7Ok = document.querySelector('.wpcf7-mail-sent-ok');
                if (cf7Ok) return true;

                // 汎用パターン: success系クラスが可視状態
                const successSelectors = [
                    '.success-message', '.form-success', '.submit-success',
                    '.contact-success', '.form-complete', '.thanks-message'
                ];
                for (const sel of successSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden'
                            && el.textContent.trim().length > 0) {
                            return true;
                        }
                    }
                }

                // submitボタンが全てdisabled/非表示になった場合
                const submitBtns = document.querySelectorAll('button[type="submit"], input[type="submit"]');
                if (submitBtns.length > 0) {
                    let allDisabled = true;
                    for (const btn of submitBtns) {
                        if (!btn.disabled && btn.offsetParent !== null) {
                            allDisabled = false;
                            break;
                        }
                    }
                    if (allDisabled) return true;
                }

                // IMP-024 Mod-2: Toast/Snackbar/Alert検出
                const toastSelectors = [
                    '[role="alert"]', '[role="status"]', '[aria-live="polite"]', '[aria-live="assertive"]',
                    '.toast', '.snackbar', '.notification', '.alert-success', '.alert-info',
                    '.flash-message', '.notice', '.message-success',
                    '[class*="toast"]', '[class*="snack"]', '[class*="notif"]',
                    '.swal2-popup', '.swal-modal'
                ];
                for (const sel of toastSelectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const style = window.getComputedStyle(el);
                        const text = el.textContent.trim();
                        if (style.display !== 'none' && style.visibility !== 'hidden' && text.length > 3) {
                            // 成功系キーワードを含むか確認
                            const successWords = ['ありがとう', '送信', '完了', '受付', 'thank', 'success', 'sent', 'submitted'];
                            if (successWords.some(w => text.toLowerCase().includes(w))) {
                                return true;
                            }
                        }
                    }
                }

                // IMP-024 Mod-2: フォームがdisplay:none/hidden化された場合（送信後にフォーム非表示化）
                const forms = document.querySelectorAll('form');
                if (forms.length > 0) {
                    let allHidden = true;
                    for (const form of forms) {
                        const style = window.getComputedStyle(form);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            allHidden = false;
                            break;
                        }
                    }
                    if (allHidden) return true;
                }

                return false;
            }''')
        except Exception:
            return False

    async def _click_final_submit(self, page, result: Dict,
                                  error_keywords: list, completion_keywords: list) -> Dict:
        """確認ページで最終送信ボタンをクリックし、完了を待つ"""

        # IMP-017: クリック前のURLを記録（完了検証用）
        result['_pre_click_url'] = page.url

        # IMP-027 Mod-1b: 最終送信前にURLチェック（/thanks/等に既に遷移済みなら成功）
        current_url_check = page.url
        url_lower_check = current_url_check.lower()
        success_url_patterns_check = ['/thanks', '/thank-you', '/thankyou', '/complete',
                                       '/success', '/done', '/finished', '/sent',
                                       '/contact_thanks', '/inquiry_thanks', '/form_thanks',
                                       'thanks.html', 'thankyou.html', 'complete.html']
        if any(pat in url_lower_check for pat in success_url_patterns_check):
            print(f"  🎉 IMP-027: 成功URL検出（最終送信不要）→ {current_url_check}")
            result['success'] = True
            result['completion_detected'] = True
            result['method'] = f'url_success_pattern: {current_url_check}'
            return result

        # IMP-020 + IMP-026: 確認画面のチェックボックス自動チェック（送信ボタンクリック前）
        try:
            checked_count = await page.evaluate("""() => {
                let count = 0;
                // Pass 1: name/id属性でマッチ
                const selectors = [
                    'input[type="checkbox"][name*="privacy"]', 'input[type="checkbox"][name*="agree"]',
                    'input[type="checkbox"][name*="consent"]', 'input[type="checkbox"][name*="policy"]',
                    'input[type="checkbox"][name*="terms"]', 'input[type="checkbox"][name*="personal"]',
                    'input[type="checkbox"][name*="confirm"]',
                    'input[type="checkbox"][id*="privacy"]', 'input[type="checkbox"][id*="agree"]',
                    'input[type="checkbox"][id*="consent"]', 'input[type="checkbox"][id*="policy"]'
                ];
                for (const sel of selectors) {
                    for (const cb of document.querySelectorAll(sel)) {
                        if (!cb.checked) {
                            const label = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                            if (label) { label.click(); } else { cb.click(); }
                            if (!cb.checked) cb.checked = true;
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                            count++;
                        }
                    }
                }
                // Pass 2: ラベルテキストでマッチ（IMP-025+026同等）
                if (count === 0) {
                    for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
                        if (cb.checked) continue;
                        const label = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                        const text = (label ? label.textContent : '').toLowerCase();
                        const nearText = cb.parentElement ? cb.parentElement.textContent.toLowerCase() : '';
                        let grandText = '';
                        let el = cb.parentElement;
                        for (let i = 0; i < 3 && el; i++) { grandText += ' ' + (el.textContent || '').toLowerCase(); el = el.parentElement; }
                        const combined = text + ' ' + nearText + ' ' + grandText;
                        if (combined.includes('同意') || combined.includes('プライバシー') ||
                            combined.includes('個人情報') || combined.includes('agree') ||
                            combined.includes('privacy') || combined.includes('規約') ||
                            combined.includes('承諾') || combined.includes('了承') ||
                            combined.includes('accept') || combined.includes('terms') ||
                            combined.includes('policy') || combined.includes('confirm') ||
                            combined.includes('利用規約') || combined.includes('ポリシー')) {
                            const label2 = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                            if (label2) { label2.click(); } else { cb.click(); }
                            if (!cb.checked) cb.checked = true;
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                            count++;
                        }
                    }
                }
                // Pass 3: 残り1-2個なら全チェック
                if (count === 0) {
                    const unchecked = [...document.querySelectorAll('input[type="checkbox"]')].filter(cb => {
                        if (cb.checked) return false;
                        const style = window.getComputedStyle(cb);
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        if (cb.name) {
                            const sameGroup = document.querySelectorAll('input[type="checkbox"][name="' + cb.name + '"]');
                            if (sameGroup.length > 3) return false;
                        }
                        return true;
                    });
                    if (unchecked.length > 0 && unchecked.length <= 2) {
                        for (const cb of unchecked) {
                            const label3 = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                            if (label3) { label3.click(); } else { cb.click(); }
                            if (!cb.checked) cb.checked = true;
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                            count++;
                        }
                    }
                }
                return count;
            }""")
            if checked_count > 0:
                print(f"  ☑️ 確認画面のチェックボックス {checked_count}件を自動チェック")
                await asyncio.sleep(0.5)
        except Exception:
            pass


        # IMP-011 + IMP-017: 最終送信ボタン検出パターン（拡充）
        final_submit_selectors = [
            'button:has-text("この内容で送信する")',
            'button:has-text("この内容で送信")',
            'button:has-text("上記内容で送信する")',
            'button:has-text("上記の内容で送信する")',
            'button:has-text("上記の内容で送信")',
            'button:has-text("上記内容で送信")',
            # IMP-017追加: 個別サイト対応
            'button:has-text("お問い合わせ送信")',
            'button:has-text("お問い合わせを送信")',
            'button:has-text("問い合わせを送信")',
            'button:has-text("送信する")',
            'button:has-text("送信")',
            'input[type="submit"][value*="この内容"]',
            'input[type="submit"][value*="送信"]',
            'input[type="button"][value*="送信"]',
            # IMP-017追加: input[value]パターン
            'input[value*="お問い合わせ送信"]',
            'input[value*="お問い合わせを送信"]',
            'input[value="送信する"]',
            'input[value="送信"]',
            'button:has-text("Submit")',
            'a:has-text("送信する")',
            'a:has-text("送信")',
            # div/spanベースのカスタムボタン
            'div[role="button"]:has-text("送信")',
            'span[role="button"]:has-text("送信")',
            # IMP-023追加: 英語ボタン + モーダル対応
            'button:has-text("SEND")',
            'button:has-text("Send")',
            'input[value="SEND"]',
            'input[value="Send"]',
            'a:has-text("SEND")',
            # モーダルの「はい」ボタン
            'button:has-text("はい")',
            'a:has-text("はい")',
            # 「以上の内容で送信する」パターン
            'button:has-text("以上の内容で送信")',
            'input[value*="以上の内容"]',
            # IMP-025 Mod-2: 「登録する」「登録」パターン追加
            'button:has-text("登録する")',
            'button:has-text("登録")',
            'input[type="submit"][value*="登録"]',
            'input[type="button"][value*="登録"]',
            'input[value="登録する"]',
            'input[value="登録"]',
            'a:has-text("登録する")',
            # 「確定」パターン
            'button:has-text("確定する")',
            'button:has-text("確定")',
            'input[value="確定"]',
            'input[value="確定する"]',
            # 「完了」パターン
            'button:has-text("完了する")',
            'button:has-text("完了")',
            'input[value="完了"]',
        ]

        skip_texts = ['戻る', '修正', '戻って', '編集']

        for selector in final_submit_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        # 「戻る」「修正」「編集」ボタンを除外
                        text = await element.inner_text()
                        if any(skip in text for skip in skip_texts):
                            continue
                        # IMP-017: ビューポート外対策 - scroll into view
                        await element.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        print(f"  🔘 最終送信ボタン検出: {selector}")
                        try:
                            await element.click()
                        except Exception:
                            # IMP-023 Mod-2: Playwright click失敗時にJS clickフォールバック
                            print(f"  ⚠️ Playwright click失敗 → JS clickフォールバック")
                            await page.evaluate('el => el.click()', element)
                        result['success'] = True
                        result['method'] = selector
                        break
            except Exception:
                continue

        # IMP-011 + IMP-017: セレクタで見つからない場合、JSでボタンを探してscroll+click
        if not result['success']:
            try:
                clicked = await page.evaluate('''() => {
                    const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a'))
                        .filter(b => {
                            const style = window.getComputedStyle(b);
                            return style.display !== 'none' && style.visibility !== 'hidden' && b.offsetParent !== null;
                        });
                    const skipWords = ['戻る', '修正', '戻って', '編集', 'back', 'Back'];
                    const submitWords = ['送信', 'submit', 'Submit', 'お問い合わせ送信'];
                    const submitBtn = buttons.find(b => {
                        const t = (b.textContent || b.value || '').trim();
                        return !skipWords.some(skip => t.includes(skip))
                            && submitWords.some(kw => t.includes(kw));
                    });
                    if (submitBtn) {
                        submitBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
                        submitBtn.click();
                        return true;
                    }
                    return false;
                }''')
                if clicked:
                    print(f"  🔘 最終送信ボタン検出: JS button filter")
                    result['success'] = True
                    result['method'] = 'js_button_filter'
            except Exception:
                pass

        if not result['success']:
            # form.submit()フォールバック
            try:
                submitted = await page.evaluate('''() => {
                    const form = document.querySelector('form');
                    if (form) {
                        HTMLFormElement.prototype.submit.call(form);
                        return true;
                    }
                    return false;
                }''')
                if submitted:
                    print(f"  🔘 確認ページ: form.submit() で送信")
                    result['success'] = True
                    result['method'] = 'confirmation_form.submit()'
            except Exception:
                pass

        if not result['success']:
            result['error'] = '確認ページの送信ボタンが見つかりません'
            print(f"  ❌ 確認ページの最終送信ボタン検出失敗")
            return result

        # ページ遷移待機
        try:
            await page.wait_for_load_state('networkidle', timeout=15000)
        except PlaywrightTimeout:
            print(f"  ⚠️ networkidle待機タイムアウト（続行）")

        await asyncio.sleep(2)

        # IMP-017: 最終確認 - 完了ページに到達したかを厳密に検証
        pre_click_url = result.get('_pre_click_url', '')
        post_click_url = page.url
        try:
            final_text = await page.inner_text('body')
            # IMP-010: 確認ページ突破後のエラー検出
            if any(kw in final_text for kw in error_keywords):
                matched = [kw for kw in error_keywords if kw in final_text]
                print(f"  ❌ 確認ページ突破後エラー検出: {matched[0]}")
                result['success'] = False
                result['error'] = f"form_submission_error: {matched[0]}"
                return result
            if any(kw in final_text for kw in completion_keywords):
                print(f"  🎉 送信完了ページに到達")
                result['completion_detected'] = True
            elif pre_click_url and post_click_url != pre_click_url:
                # IMP-018: Hash-only変化はページ遷移として扱わない
                if not self._is_same_page_hash_change(pre_click_url, post_click_url):
                    # URL変化あり → 完了ページへ遷移したとみなす
                    print(f"  🔄 確認画面突破後URL変化: {pre_click_url} → {post_click_url}")
                    result['completion_detected'] = True
                else:
                    print(f"  ℹ️ 確認画面突破後Hash変化のみ: {pre_click_url} → {post_click_url}")
                    # Hash変化のみ → AJAXチェック
                    ajax_ok = await self._check_ajax_success(page)
                    if ajax_ok:
                        print(f"  🎉 確認画面突破後AJAX送信成功を検出")
                        result['completion_detected'] = True
                    else:
                        print(f"  ℹ️ Hash変化のみ・AJAX未検出 → 完了とみなす")
            else:
                # IMP-018: 完了キーワードもURL変化もない → AJAXチェックを先に行う
                ajax_ok = await self._check_ajax_success(page)
                if ajax_ok:
                    print(f"  🎉 確認画面突破後AJAX送信成功を検出")
                    result['completion_detected'] = True
                else:
                    # 送信ボタンがまだ存在するか確認
                    still_has_submit = await self._has_submit_button(page)
                    if still_has_submit:
                        # IMP-032 Mod-1: ボタン残存時に検証エラースキャン＋自動修正＋再click試行
                        print(f"  🔄 IMP-032: ボタン残存 → 検証エラースキャン開始")

                        # Phase A: 検証エラーの検出と自動修正
                        try:
                            _fix_count = await page.evaluate('''() => {
                                let fixes = 0;

                                // A-1: 未チェックの全checkbox をチェック（確認ページでは全チェックが安全）
                                for (const cb of document.querySelectorAll('input[type="checkbox"]')) {
                                    if (cb.checked) continue;
                                    try {
                                        const style = window.getComputedStyle(cb);
                                        if (style.display === 'none' && !cb.closest('label')) continue;
                                    } catch(e) { continue; }
                                    const label = cb.closest('label') || document.querySelector('label[for="' + cb.id + '"]');
                                    if (label) { label.click(); } else { cb.click(); }
                                    if (!cb.checked) cb.checked = true;
                                    cb.dispatchEvent(new Event('change', {bubbles: true}));
                                    fixes++;
                                }

                                // A-2: 未選択のradioグループを選択
                                const radioGroups = {};
                                for (const r of document.querySelectorAll('input[type="radio"]')) {
                                    const name = r.name || r.id;
                                    if (!name) continue;
                                    if (!radioGroups[name]) radioGroups[name] = {checked: false, radios: []};
                                    if (r.checked) radioGroups[name].checked = true;
                                    radioGroups[name].radios.push(r);
                                }
                                for (const [name, group] of Object.entries(radioGroups)) {
                                    if (group.checked || group.radios.length === 0) continue;
                                    const agreeWords = ['同意', '承諾', '了承', 'はい', 'agree', 'yes'];
                                    let target = null;
                                    for (const r of group.radios) {
                                        const label = r.closest('label') || document.querySelector('label[for="' + r.id + '"]');
                                        const text = (label ? label.textContent : r.value || '').toLowerCase();
                                        if (agreeWords.some(w => text.includes(w))) { target = r; break; }
                                    }
                                    if (!target) target = group.radios[0];
                                    const label = target.closest('label') || document.querySelector('label[for="' + target.id + '"]');
                                    if (label) { label.click(); } else { target.click(); }
                                    if (!target.checked) target.checked = true;
                                    target.dispatchEvent(new Event('change', {bubbles: true}));
                                    fixes++;
                                }

                                return fixes;
                            }''')
                            if _fix_count > 0:
                                print(f"  🔄 IMP-032: 確認ページで {_fix_count}件の入力を自動修正")
                        except Exception:
                            pass

                        await asyncio.sleep(2)
                        print(f"  🔄 IMP-032: 修正後に再click試行")
                        try:
                            retry_clicked = await page.evaluate("""() => {
                                const skipWords = ['戻る', '修正', '戻って', '編集', 'back', 'Back'];
                                const visible = (el) => {
                                    const style = window.getComputedStyle(el);
                                    return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null;
                                };
                                // Phase 1: モーダル/ダイアログ内の「はい」「OK」「Yes」ボタンを優先
                                const modalSelectors = [
                                    '.modal', '.dialog', '[role="dialog"]', '[role="alertdialog"]',
                                    '.overlay', '.popup', '.confirm', '.swal2-container',
                                    '[class*="modal"]', '[class*="dialog"]', '[class*="popup"]'
                                ];
                                for (const msel of modalSelectors) {
                                    const modal = document.querySelector(msel);
                                    if (!modal) continue;
                                    const btns = modal.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
                                    for (const b of btns) {
                                        if (!visible(b)) continue;
                                        const t = (b.textContent || b.value || '').trim();
                                        if (skipWords.some(s => t.includes(s))) continue;
                                        if (['はい', 'OK', 'Yes', 'YES', 'yes', 'ok'].includes(t) ||
                                            t.includes('送信する') || t.includes('送信します')) {
                                            b.scrollIntoView({ behavior: 'instant', block: 'center' });
                                            b.click();
                                            return 'modal:' + t;
                                        }
                                    }
                                }
                                // Phase 2: ページ全体から短い「はい」「OK」ボタンを探す（モーダル外でも）
                                const allBtns = Array.from(document.querySelectorAll('button, a, input[type="button"]'))
                                    .filter(visible);
                                const yesBtn = allBtns.find(b => {
                                    const t = (b.textContent || b.value || '').trim();
                                    return ['はい', 'OK', 'Yes', 'YES'].includes(t);
                                });
                                if (yesBtn) {
                                    yesBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
                                    yesBtn.click();
                                    return 'yes:' + (yesBtn.textContent || '').trim();
                                }
                                // Phase 3: 通常の送信ボタン（従来のロジック）
                                const submitWords = ['送信', 'submit', 'Submit', 'SEND', 'Send', 'この内容で送信', '以上の内容'];
                                const btn = allBtns.find(b => {
                                    const t = (b.textContent || b.value || '').trim();
                                    return !skipWords.some(s => t.includes(s)) && submitWords.some(k => t.includes(k));
                                });
                                if (btn) {
                                    btn.scrollIntoView({ behavior: 'instant', block: 'center' });
                                    btn.click();
                                    return 'submit:' + (btn.textContent || '').trim();
                                }
                                return false;
                            }""")
                            if retry_clicked:
                                print(f"  🔘 IMP-023: 再click成功 → 3秒待機")
                                await asyncio.sleep(3)
                                still_has_submit = await self._has_submit_button(page)
                        except Exception as e:
                            print(f"  ⚠️ IMP-023 再click失敗: {e}")

                    if still_has_submit:
                        # IMP-032 Mod-2: 最終手段としてform.submit()を試行
                        try:
                            _form_submitted = await page.evaluate('''() => {
                                const forms = document.querySelectorAll('form');
                                if (forms.length === 0) return false;
                                let targetForm = forms[0];
                                let maxInputs = 0;
                                for (const form of forms) {
                                    const inputs = form.querySelectorAll('input, textarea, select');
                                    if (inputs.length > maxInputs) {
                                        maxInputs = inputs.length;
                                        targetForm = form;
                                    }
                                }
                                try {
                                    HTMLFormElement.prototype.submit.call(targetForm);
                                    return true;
                                } catch(e) {
                                    return false;
                                }
                            }''')
                            if _form_submitted:
                                print(f"  🔄 IMP-032: form.submit()フォールバック実行")
                                try:
                                    await page.wait_for_load_state('networkidle', timeout=10000)
                                except Exception:
                                    pass
                                await asyncio.sleep(2)
                                try:
                                    _body2 = await page.evaluate('() => document.body.innerText || ""')
                                    for kw in completion_keywords:
                                        if kw in _body2:
                                            print(f"  ✅ IMP-032: form.submit()後に完了キーワード検出: {kw}")
                                            result['success'] = True
                                            result['completion_detected'] = True
                                            result['reason'] = f'form_submit_fallback: {kw}'
                                            return result
                                    _url2 = page.url
                                    if _url2 != result.get('_pre_click_url', ''):
                                        print(f"  ✅ IMP-032: form.submit()後にURL変化検出")
                                        result['success'] = True
                                        result['completion_detected'] = True
                                        result['reason'] = f'form_submit_fallback: URL changed to {_url2}'
                                        return result
                                    _form_gone = await page.evaluate('''() => {
                                        const forms = document.querySelectorAll('form');
                                        if (forms.length === 0) return true;
                                        let totalInputs = 0;
                                        for (const f of forms) {
                                            totalInputs += f.querySelectorAll('input:not([type="hidden"]), textarea, select').length;
                                        }
                                        return totalInputs === 0;
                                    }''')
                                    if _form_gone:
                                        print(f"  ✅ IMP-032: form.submit()後にフォーム消失検出")
                                        result['success'] = True
                                        result['completion_detected'] = True
                                        result['reason'] = 'form_submit_fallback: form disappeared'
                                        return result
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # IMP-020: エラー未検出なら暫定成功 → Gemini Vision判定へ
                        print(f"  ℹ️ 確認画面突破後も送信ボタン存在 → 暫定成功（Gemini Vision判定へ）")
                        result['success'] = True
                        result['completion_unverified'] = True
                        result['reason'] = 'confirmation_not_passed_but_no_error: ボタン残存・エラーなし'
                        return result
                    print(f"  ℹ️ 完了キーワード未検出だが送信ボタンも消失 → 完了とみなす")
        except Exception:
            pass

        print(f"  ✅ 確認ページ突破完了: {result['method']}")
        # _pre_click_url は内部用なので削除
        result.pop('_pre_click_url', None)
        return result

    async def _take_screenshot(self, page, task_id: int, stage: str) -> Optional[str]:
        """スクリーンショットを撮影して保存"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"task_{task_id}_{stage}_{timestamp}.png"
            filepath = os.path.join(SCREENSHOT_DIR, filename)
            
            await page.screenshot(path=filepath, full_page=True)
            print(f"📸 スクリーンショット保存: {filepath}")
            return filepath
        except Exception as e:
            print(f"⚠️ スクリーンショット失敗: {e}")
            return None
    
    def _get_form_data_json(self) -> str:
        """IMP-027+028: JSに渡すためのform_data JSON文字列"""
        import json
        data = {}
        if hasattr(self, '_form_data_cache') and self._form_data_cache:
            data = dict(self._form_data_cache)  # コピーして元を変更しない
        # IMP-028: テンプレート展開済みメッセージで上書き
        if hasattr(self, '_message_text') and self._message_text:
            data['message'] = self._message_text
        # IMP-028: 派生フィールド追加
        if data.get('last_name') and data.get('first_name'):
            data['full_name'] = data.get('name', data['last_name'] + data['first_name'])
        elif data.get('name'):
            data['full_name'] = data['name']
        if data.get('last_name_kana') and data.get('first_name_kana'):
            data['name_kana'] = data['last_name_kana'] + data['first_name_kana']
        return json.dumps(data, ensure_ascii=False)

    async def _fill_form_fields_with_tracking(self, page, form_data: Dict) -> Dict:
        """フォームフィールドに入力（結果追跡付き・iframe対応）"""
        fill_results = {}
        
        # メインページとiframe両方を対象にする
        contexts_to_try = [page]
        
        # HubSpot Forms iframeを検出
        try:
            frames = page.frames
            for frame in frames:
                if 'hs-form' in frame.url or 'hubspot' in frame.url or 'hsforms' in frame.url:
                    print(f"🔍 HubSpot iframe検出: {frame.url[:80]}...")
                    contexts_to_try.append(frame)
        except:
            pass
        
        for field_name, value in form_data.items():
            if not value:
                continue
                
            fill_results[field_name] = {
                'success': False,
                'selector_used': None,
                'value': str(value)[:50],  # 値の先頭50文字（ログ用）
                'error': None
            }
            
            selectors = [
                f'input[name="{field_name}"]',
                f'input[id="{field_name}"]',
                f'textarea[name="{field_name}"]',
                f'textarea[id="{field_name}"]',
                f'input[name*="{field_name}"]',
                f'textarea[name*="{field_name}"]',
                f'input[placeholder*="{field_name}"]',
                f'textarea[placeholder*="{field_name}"]',
            ]
            
            # メインページとiframe両方で試行
            for context in contexts_to_try:
                if fill_results[field_name]['success']:
                    break
                    
                for selector in selectors:
                    try:
                        element = await context.query_selector(selector)
                        if element:
                            # 入力可能か確認
                            is_visible = await element.is_visible()
                            is_enabled = await element.is_enabled()
                            
                            if is_visible and is_enabled:
                                await element.fill(str(value))
                                fill_results[field_name]['success'] = True
                                fill_results[field_name]['selector_used'] = selector
                                context_type = 'iframe' if context != page else 'main'
                                print(f"  ✅ {field_name}: 入力完了 ({context_type}: {selector})")
                                break
                    except Exception as e:
                        fill_results[field_name]['error'] = str(e)
                        continue
            
            if not fill_results[field_name]['success']:
                print(f"  ⚠️ {field_name}: フィールドが見つかりません")
        
        return fill_results
    
    def _update_task_status(self, db, task_id: int, status: str):
        """タスクステータスを更新"""
        try:
            if db:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.status = status
                    db.commit()
        except Exception as e:
            print(f"⚠️ ステータス更新失敗: {e}")
    
    async def execute_batch(self, company_id: int, limit: int = 10) -> Dict:
        """企業の自動実行可能タスクを一括実行"""
        start_time = time.time()
        result = {
            'success': False, 'company_id': company_id,
            'total_tasks': 0, 'completed': 0, 'failed': 0,
            'total_fill_rate': 0.0,
            'results': [], 'execution_time': 0
        }
        
        db = None
        try:
            db = get_db_session()
            tasks = db.query(Task).filter(
                Task.company_id == company_id,
                Task.automation_type == 'auto',
                Task.status == 'pending'
            ).order_by(Task.id).limit(limit).all()
            
            task_ids = [task.id for task in tasks]
            result['total_tasks'] = len(task_ids)
            
            if not task_ids:
                result['success'] = True
                print(f"ℹ️ 企業ID {company_id} に自動実行可能タスクがありません")
                db.close()
                return result
            
            print(f"🤖 バッチ実行開始: 企業ID {company_id} | {len(task_ids)}タスク")
            db.close()
            db = None
            
            fill_rates = []
            for task_id in task_ids:
                task_result = await self.execute_task(task_id)
                result['results'].append(task_result)
                if task_result['success']:
                    result['completed'] += 1
                    fill_rates.append(task_result.get('fill_rate', 0))
                else:
                    result['failed'] += 1
                await asyncio.sleep(2)
            
            # 平均入力率
            if fill_rates:
                result['total_fill_rate'] = round(sum(fill_rates) / len(fill_rates), 1)
            
            result['success'] = True
            print(f"✅ バッチ実行完了: 完了={result['completed']}, 失敗={result['failed']}, 平均入力率={result['total_fill_rate']}%")
        except Exception as e:
            result['error_message'] = str(e)
            print(f"❌ バッチ実行エラー: 企業ID {company_id} - {e}")
        finally:
            if db:
                db.close()
            result['execution_time'] = round(time.time() - start_time, 3)
        return result


# 同期版ラッパー（Flask用）
def execute_task_sync(task_id: int, headless: bool = False, display: str = ":99",
                      dry_run: bool = True) -> Dict:
    """同期的にタスクを自動実行（Flask用ラッパー）"""
    executor = AutoExecutor(headless=headless, display=display, dry_run=dry_run)
    return asyncio.run(executor.execute_task(task_id))


def execute_batch_sync(company_id: int, limit: int = 10, headless: bool = False,
                       display: str = ":99", dry_run: bool = True) -> Dict:
    """同期的にバッチ実行（Flask用ラッパー）"""
    executor = AutoExecutor(headless=headless, display=display, dry_run=dry_run)
    return asyncio.run(executor.execute_batch(company_id, limit))
