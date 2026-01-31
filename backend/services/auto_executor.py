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
                 timeout: int = EXECUTION_TIMEOUT, max_retries: int = MAX_RETRIES):
        self.headless = headless
        self.display = display
        self.timeout = timeout
        self.max_retries = max_retries
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
                
                if 'タイムアウト' in str(last_error) or '対象外' in str(last_error):
                    break
            
            result['error_message'] = f"全{self.max_retries}回のリトライ失敗: {last_error}"
            return result
            
        finally:
            task_lock.release()
    
    async def _execute_task_internal(self, task_id: int, retry_count: int = 0) -> Dict:
        """タスク実行の内部処理（Async版）"""
        start_time = time.time()
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
                    
                    # スクリーンショット: フォーム入力前
                    screenshot_before = await self._take_screenshot(page, task_id, 'before')
                    if screenshot_before:
                        result['screenshots'].append(screenshot_before)
                    
                    # フォーム入力（解析結果を活用）
                    if form_fields:
                        # 解析結果を使った高精度入力
                        fill_results = await self._fill_form_with_analysis(page, form_fields, product, company)
                    else:
                        # フォールバック：従来の汎用入力
                        print("⚠️ 解析結果なし - フォールバックモードで実行")
                        form_data = self._build_form_data(product, company)
                        fill_results = await self._fill_form_fields_with_tracking(page, form_data)
                    
                    result['fill_results'] = fill_results
                    result['filled_fields'] = len([r for r in fill_results.values() if r['success']])
                    result['total_fields'] = len(fill_results)
                    
                    if result['total_fields'] > 0:
                        result['fill_rate'] = round(result['filled_fields'] / result['total_fields'] * 100, 1)
                    
                    # スクリーンショット: フォーム入力後
                    screenshot_after = await self._take_screenshot(page, task_id, 'after')
                    if screenshot_after:
                        result['screenshots'].append(screenshot_after)
                    
                    print(f"📊 入力結果: {result['filled_fields']}/{result['total_fields']} フィールド ({result['fill_rate']}%)")
                    
                    # 成功判定（入力率50%以上で成功とみなす）
                    if result['fill_rate'] >= 50:
                        result['success'] = True
                        result['status'] = 'completed'
                        task.status = 'completed'
                        task.completed_at = datetime.now()
                        task.submitted = True  # 送信フラグ
                        task.screenshot_path = screenshot_after  # スクリーンショットパス
                        # 入力結果をform_analysisに保存（SQLAlchemy JSON更新対応）
                        updated_analysis = dict(task.form_analysis) if task.form_analysis else {}
                        updated_analysis['fill_results'] = fill_results
                        updated_analysis['fill_rate'] = result['fill_rate']
                        updated_analysis['filled_fields'] = result['filled_fields']
                        updated_analysis['total_fields'] = result['total_fields']
                        updated_analysis['executed_at'] = result['executed_at']
                        task.form_analysis = updated_analysis  # 全体を再代入
                        db.commit()
                        print(f"✅ 自動実行完了: Task#{task_id} (入力率: {result['fill_rate']}%)")
                    else:
                        raise Exception(f"入力率が低すぎます: {result['fill_rate']}% (閾値: 50%)")
                        
                finally:
                    if browser:
                        await browser.close()
                        print("✅ ブラウザ終了")
            
        except TimeoutError as e:
            result['error_message'] = str(e)
            print(f"⏰ タイムアウト: Task#{task_id} - {e}")
            self._update_task_status(db, task_id, 'failed')
                    
        except Exception as e:
            result['error_message'] = str(e)
            print(f"❌ 自動実行エラー: Task#{task_id} - {e}")
            if db:
                status = 'pending' if retry_count < self.max_retries - 1 else 'failed'
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
            form_data['phone'] = product.sender_phone
            form_data['tel'] = product.sender_phone
        
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
    
    def _infer_category_from_label(self, label: str, field_name: str) -> str:
        """ラベルやフィールド名からカテゴリを推測（AI解析の誤分類対策）"""
        text = (label or '') + ' ' + (field_name or '')
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
            # 部署・役職
            (['部署', 'department'], 'department'),
            (['役職', 'position'], 'position'),
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
    
    def _get_value_for_category(self, product: Product, category: str, company: Company = None) -> Optional[str]:
        """field_categoryに対応する送信者データを取得"""
        # 電話番号：専用カラムがあればそちらを優先、なければsender_phoneを分割
        if product.sender_phone_1:
            phone1 = product.sender_phone_1
            phone2 = product.sender_phone_2 or ''
            phone3 = product.sender_phone_3 or ''
        else:
            phone = product.sender_phone or ''
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
            'phone': product.sender_phone or f"{phone1}-{phone2}-{phone3}".strip('-'),
            'phone1': phone1,
            'phone2': phone2,
            'phone3': phone3,
            'tel': product.sender_phone or f"{phone1}-{phone2}-{phone3}".strip('-'),
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
        
        return category_mapping.get(category)
    
    async def _fill_form_with_analysis(self, page, form_fields: List[Dict], product: Product, company: Company = None) -> Dict:
        """解析結果を使ってフォーム入力（高精度モード）"""
        fill_results = {}
        custom_select_count = 0  # カスタムセレクトのカウンター
        processed_custom_selects = set()  # 処理済みカスタムセレクトのセレクタ
        
        for field in form_fields:
            field_name = field.get('name') or field.get('id') or ''
            field_id = field.get('id')
            field_type = field.get('type', 'input')
            category = field.get('field_category', 'unknown')
            label = field.get('label', field_name)
            
            # ラベルからカテゴリを補正（AI解析の誤分類対策）
            if category in ['other', 'unknown', '']:
                category = self._infer_category_from_label(label, field_name)
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
            
            # チェックボックスの場合は特別処理
            if field_type == 'checkbox':
                fill_results[field_name] = await self._handle_checkbox(page, field, field_name, field_id, label)
                continue
            
            # セレクトボックスの場合は特別処理（type: "search"も含む - AI誤分類対策）
            if field_type in ['select', 'search'] and category in ['subject', 'inquiry_type', 'prefecture']:
                fill_results[field_name] = await self._handle_select(page, field, field_name, field_id, category, product, company)
                continue
            
            # セレクトボックスの場合は特別処理
            if field_type == 'select':
                fill_results[field_name] = await self._handle_select(page, field, field_name, field_id, category, product, company)
                continue
            
            # カテゴリから入力値を取得（companyを渡してテンプレート変数を適用）
            value = self._get_value_for_category(product, category, company)
            
            fill_results[field_name] = {
                'success': False,
                'selector_used': None,
                'value': str(value)[:50] if value else None,
                'category': category,
                'label': label,
                'error': None
            }
            
            if not value:
                fill_results[field_name]['error'] = f"カテゴリ '{category}' に対応するデータがありません"
                print(f"  ⚠️ {field_name} ({category}): データなし")
                continue
            
            # 解析結果のセレクタを優先使用
            tag = 'textarea' if field_type == 'textarea' else 'input'
            selectors = []
            
            # 1. 解析結果のname/idを直接使用（最優先）
            if field_name:
                selectors.append(f'{tag}[name="{field_name}"]')
            if field_id and field_id != field_name:
                selectors.append(f'{tag}[id="{field_id}"]')
            
            # 2. フォールバック（部分一致）
            if field_name:
                selectors.append(f'{tag}[name*="{field_name}"]')
                selectors.append(f'{tag}[id*="{field_name}"]')
            
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()
                        
                        if is_visible and is_enabled:
                            await element.fill(str(value))
                            fill_results[field_name]['success'] = True
                            fill_results[field_name]['selector_used'] = selector
                            print(f"  ✅ {field_name} ({category}): 入力完了 [{selector}]")
                            break
                except Exception as e:
                    fill_results[field_name]['error'] = str(e)
                    continue
            
            if not fill_results[field_name]['success']:
                print(f"  ❌ {field_name} ({category}): セレクタが見つかりません")
        
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
                return await self._handle_custom_select(page, field, field_name, category, product)
            
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
            
            if target_value:
                await select_element.select_option(value=target_value)
                result['success'] = True
                result['selector_used'] = used_selector
                result['value'] = target_value
                print(f"  ✅ {field_name} ({category}): 選択完了")
            else:
                result['error'] = "適切な選択肢が見つかりません"
                print(f"  ⚠️ {field_name} ({category}): 適切な選択肢が見つかりません")
                
        except Exception as e:
            result['error'] = str(e)
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
            print(f"  ❌ カスタムセレクト処理失敗: 対応するコンポーネントが見つかりません")
            
        except Exception as e:
            result['error'] = str(e)
            print(f"  ❌ カスタムセレクト処理エラー: {e}")
        
        return result

    async def _handle_checkbox(self, page, field: Dict, field_name: str, field_id: str, label: str) -> Dict:
        """チェックボックスを処理（同意チェックボックス等）
        
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
        
        # 全ての同名チェックボックスをチェック（複数ある場合に対応）
        for selector in checkbox_selectors:
            try:
                debug_log(f"    🔍 チェックボックス検索中: {selector}")
                # 全てのマッチする要素を取得
                elements = await page.query_selector_all(selector)
                debug_log(f"    📍 マッチした要素数: {len(elements)}")
                
                for i, element in enumerate(elements):
                    is_visible = await element.is_visible()
                    is_checked = await element.is_checked()
                    debug_log(f"    📍 要素[{i}]: visible={is_visible}, checked={is_checked}")
                    
                    if is_checked:
                        # 既にチェック済みならスキップ
                        debug_log(f"    ℹ️ 要素[{i}]: 既にチェック済み")
                        continue
                    
                    # 表示されている場合は通常のcheck()
                    if is_visible:
                        try:
                            await element.check(timeout=5000)  # タイムアウトを5秒に短縮
                            debug_log(f"    ✅ 要素[{i}]: チェック完了")
                        except Exception as e:
                            debug_log(f"    ⚠️ 要素[{i}] check()失敗: {e}")
                            # force=Trueでクリックを試す
                            try:
                                await element.click(force=True, timeout=3000)
                                debug_log(f"    ✅ 要素[{i}]: force click完了")
                            except Exception as e2:
                                debug_log(f"    ⚠️ 要素[{i}] force click失敗: {e2}")
                    else:
                        # 非表示の場合はdispatch_eventを試す
                        try:
                            await element.dispatch_event('click')
                            debug_log(f"    ✅ 要素[{i}]: dispatch_eventでチェック完了")
                        except Exception as e:
                            debug_log(f"    ⚠️ 要素[{i}] dispatch_event失敗: {e}")
                
                # 全てチェック後、最終状態を確認
                if elements:
                    # 少なくとも1つがチェックされていれば成功
                    for element in elements:
                        if await element.is_checked():
                            result['success'] = True
                            result['selector_used'] = selector
                            debug_log(f"  ✅ {field_name} (checkbox): チェック完了 [{selector}]")
                            return result
                    
                    # まだチェックされていない場合、最初の可視要素に再試行
                    debug_log(f"    ⚠️ チェックされていない、ラベルクリックを試行...")
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
        
        debug_log(f"  ❌ {field_name} (checkbox): 全ての方法で失敗")
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
def execute_task_sync(task_id: int, headless: bool = False, display: str = ":99") -> Dict:
    """同期的にタスクを自動実行（Flask用ラッパー）"""
    executor = AutoExecutor(headless=headless, display=display)
    return asyncio.run(executor.execute_task(task_id))


def execute_batch_sync(company_id: int, limit: int = 10, headless: bool = False, display: str = ":99") -> Dict:
    """同期的にバッチ実行（Flask用ラッパー）"""
    executor = AutoExecutor(headless=headless, display=display)
    return asyncio.run(executor.execute_batch(company_id, limit))
