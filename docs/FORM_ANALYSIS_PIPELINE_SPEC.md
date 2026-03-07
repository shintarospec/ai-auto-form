# AI AutoForm フォーム解析パイプライン仕様書
**作成日:** 2026年2月22日
**バージョン:** 1.2

---

## 1. 概要

フォーム解析パイプラインは、企業リスト（CSV）から問い合わせフォームへの自動送信までを実現する4ステップの処理フローです。

```
F-1: CSVインポート → F-2: タスク生成 → F-3: フォーム解析 → F-4: フォーム送信
```

AI（Gemini 2.5 Flash）によるフォーム構造解析と、ルールベースの自動入力を組み合わせたハイブリッド方式で、reCAPTCHAの有無に応じて自動/手動を振り分けます。

---

## 2. パイプラインフロー

```
┌─────────────────────────────────────────────────────────────────┐
│ F-1: CSVインポート                                              │
│   入力: 企業CSV（Wantedly形式 or 汎用形式）                       │
│   処理: 重複チェック → simple_companies に INSERT                  │
│   出力: simple_companies レコード                                 │
│   スクリプト: import_wantedly_csv.py / API                       │
│   コスト: 無料                                                    │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ F-2: タスク一括生成                                              │
│   入力: product_id（案件ID）                                      │
│   処理: 全企業に対しタスクレコード生成                              │
│   出力: simple_tasks レコード (status=pending)                    │
│   スクリプト: generate_tasks_bulk.py                              │
│   コスト: 無料                                                    │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ F-3: フォーム解析（バッチ）                                      │
│   入力: form_analysis == NULL のタスク                             │
│   処理: Playwright + Gemini AI でフォーム構造を解析                │
│   出力: form_analysis JSON, automation_type, recaptcha_type      │
│   スクリプト: batch_form_analyze.py → FormAnalyzer                │
│   コスト: 約0.019円/社（Gemini API）                              │
│   成功率: ~95%（タイムアウト・サイト閉鎖除く）                      │
└─────────────────────────┬───────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│               振り分け判定                                        │
│   recaptcha = v3/none  → automation_type = 'auto'                │
│   recaptcha = v2       → automation_type = 'manual'              │
│   ng_flag = True       → automation_type = 'manual'              │
│   iframe (HubSpot等)   → automation_type = 'manual'              │
└────────────┬──────────────────────────┬─────────────────────────┘
             ▼                          ▼
┌──────────────────────┐   ┌──────────────────────┐
│ F-4a: 自動送信       │   │ F-4b: 手動送信       │
│  AutoExecutor         │   │  VNC経由ワーカー       │
│  ・AI解析結果で入力   │   │  ・simple-console      │
│  ・確認画面突破       │   │    -v2.html            │
│  ・dry-run対応        │   │                        │
│  コスト: 無料         │   │                        │
└──────────────────────┘   └──────────────────────┘
```

---

## 3. F-1: CSVインポート

### 3.1 概要

| 項目 | 値 |
|------|-----|
| **スクリプト（CLI）** | `import_wantedly_csv.py` |
| **スクリプト（API）** | `POST /api/simple/companies/import-csv` |
| **入力** | CSV（UTF-8 BOM対応） |
| **出力** | `simple_companies` レコード |
| **重複判定** | CLIは name+website_url / APIは id→name 順に検索 |

### 3.2 CLIオプション（import_wantedly_csv.py）

| オプション | 説明 | 例 |
|-----------|------|-----|
| `csv_file` | CSVファイルパス（必須） | `inport/wantedly.csv` |
| `--limit N` | 先頭N件のみインポート | `--limit 100` |
| `--dry-run` | DB変更なし、検証のみ | |

### 3.3 CSV入力フォーマット

#### Wantedly形式（import_wantedly_csv.py用）

| カラム | 必須 | マッピング先 |
|--------|------|-------------|
| `company_name` | ✅ | `simple_companies.name` |
| `website_url` | ✅ | `simple_companies.website_url` |
| `inquiry_url` | ✅ | `simple_companies.form_url` |
| `email` | - | 未使用 |
| `address` | - | 未使用 |
| `employee_count` | - | 未使用 |
| `founded_date` | - | 未使用 |
| `detection_method` | - | 未使用 |
| `wantedly_url` | - | 未使用 |

#### 汎用形式（API用）

| カラム | 必須 | マッピング先 |
|--------|------|-------------|
| `name` | ✅ | `simple_companies.name` |
| `website_url` | - | `simple_companies.website_url` |
| `form_url` or `inquiry_url` | - | `simple_companies.form_url` |
| `industry` | - | `simple_companies.industry` |
| `id` | - | DeepBiz IDとして使用（既存レコード更新用） |

### 3.4 処理フロー

```
1. CSVロード（UTF-8 BOM対応、csv.DictReader）
2. バリデーション（name必須、form_url必須）
3. 既存レコードとの重複チェック
   - CLI: (name, website_url) のタプルで判定
   - API: id → name の順で既存検索、あれば UPDATE
4. チャンク INSERT（500件ずつコミット）
5. サマリー出力（新規/更新/スキップ件数）
```

### 3.5 実行コマンド

```bash
# CLI: Wantedly CSVインポート
cd /opt/ai-auto-form
source venv/bin/activate
python import_wantedly_csv.py inport/wantedly_confirmed_20260221.csv

# CLI: dry-run（検証のみ）
python import_wantedly_csv.py inport/wantedly.csv --dry-run --limit 50

# API: curlでインポート
curl -X POST http://153.126.154.158:5001/api/simple/companies/import-csv \
  -F "file=@companies.csv"
```

---

## 4. F-2: タスク一括生成

### 4.1 概要

| 項目 | 値 |
|------|-----|
| **スクリプト** | `generate_tasks_bulk.py` |
| **入力** | `product_id`（案件ID） |
| **出力** | `simple_tasks` レコード (status=pending) |
| **重複防止** | 同一 company_id + product_id の組み合わせはスキップ |

### 4.2 CLIオプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `product_id` | 案件ID（位置引数） | 8 |

### 4.3 処理フロー

```
1. Product読み込み（sender_*フィールド取得）
2. 全simple_companiesのID取得
3. 既存タスクのcompany_id取得（重複排除）
4. 新規分のタスクをチャンクINSERT（500件ずつ）
5. form_data JSONにsender情報を格納
```

### 4.4 form_data構造

```json
{
  "name": "佐藤 太郎",
  "last_name": "佐藤",
  "first_name": "太郎",
  "last_name_kana": "サトウ",
  "first_name_kana": "タロウ",
  "company": "株式会社テスト",
  "department": "営業部",
  "position": "部長",
  "phone": "03-1234-5678",
  "phone_1": "03", "phone_2": "1234", "phone_3": "5678",
  "email": "test@example.com",
  "zipcode_1": "106", "zipcode_2": "0032",
  "prefecture": "東京都",
  "city": "港区",
  "address": "六本木1-2-3",
  "message": "お問い合わせ内容..."
}
```

### 4.5 実行コマンド

```bash
cd /opt/ai-auto-form
source venv/bin/activate
python generate_tasks_bulk.py 8
```

---

## 5. F-3: フォーム解析

### 5.1 概要

| 項目 | 値 |
|------|-----|
| **バッチスクリプト** | `batch_form_analyze.py` |
| **解析エンジン** | `backend/services/form_analyzer.py` → `FormAnalyzer` |
| **AIサービス** | `backend/services/gemini_service.py` → `GeminiService` |
| **入力** | `Task.form_analysis == NULL` のレコード |
| **出力** | `Task.form_analysis` (JSON), `Task.automation_type`, `Task.recaptcha_type` |
| **AIモデル** | Gemini 2.5 Flash（temperature=0.0, max_tokens=8000） |
| **コスト** | 約0.019円/フォーム |

### 5.2 CLIオプション（batch_form_analyze.py）

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--dry-run` | 対象タスク表示のみ（解析しない） | false |
| `--limit N` | N件のみ処理 | 0（全件） |
| `--resume` | チェックポイントから再開 | false |
| `--product-id N` | 対象の案件ID | 8 |

### 5.3 解析フロー（FormAnalyzer.analyze_form）

```
1. ページ読み込み（Playwright Chromium, headless）
   ├─ viewport: 1280x720
   └─ 初期待機: 3000ms

2. SPA検出・ハイドレーション待機
   ├─ React: [data-reactroot], #__next, __REACT_DEVTOOLS_GLOBAL_HOOK__
   ├─ Vue: [data-v-], #app[data-v-app], window.__VUE__
   ├─ Nuxt: window.__NUXT__, #__nuxt
   └─ Gatsby: #___gatsby
   → フォーム要素の出現を最大5000ms待機

3. iframe検出（外部フォームサービス）
   ├─ HubSpot: hs-form, hubspot.com
   ├─ Google Forms: docs.google.com/forms
   ├─ MS Forms: forms.office.com, forms.microsoft.com
   ├─ Bownow: bownow.jp/forms
   ├─ K3R: form.k3r.jp
   ├─ Formrun: form.run
   ├─ Formmailer: formmailer.jp
   └─ Typeform: typeform.com

4. reCAPTCHA検出（優先順）
   ├─ v2 checkbox: .g-recaptcha → 'v2'
   ├─ v2 iframe: iframe[src*="recaptcha/api2/anchor"] → 'v2'
   ├─ v3 badge: .grecaptcha-badge → 'v3'
   ├─ v3 script: script[src*="recaptcha"] + grecaptcha.execute → 'v3'
   ├─ v3 script only（execute無し）→ 'v2'（安全側に倒す）
   └─ なし → 'none'

5. フィールド解析
   ├─ AI解析（優先）: Gemini APIで構造解析
   │  ├─ 0件の場合: 5000ms追加待機 → リトライ
   │  └─ AI失敗時: ルールベースにフォールバック
   └─ ルールベース（フォールバック）: CSSセレクタで検出

6. iframe内フォーム処理
   └─ メインページで0件 & iframe検出 → iframe URLを再解析

7. NG判定（営業対象外フォームの除外）
   └─ URL + フィールドラベルで判定

8. 結果をDBに保存
   ├─ Task.form_analysis = 解析結果JSON
   ├─ Task.automation_type = 'auto' or 'manual'
   ├─ Task.recaptcha_type = 'v2' / 'v3' / 'none' / etc
   └─ Task.estimated_time = 推定処理時間（秒）
```

### 5.4 ラベル取得（6段階、AI解析時）

フォーム解析の精度を左右する最重要ロジック。以下の優先順で取得:

| 優先度 | 方式 | 対象 |
|--------|------|------|
| 0 | WPCF7 wrapper | `.wpcf7-form-control-wrap` の前要素 |
| 1 | label[for] | `<label for="field_id">` マッチ |
| 2 | 親要素label | 最大5階層上の `<label>` タグ内テキスト |
| 3 | 前の兄弟要素 | `previousElementSibling` のテキスト |
| 4 | 親要素クローン | 親からinput/select等を除去した残テキスト |
| 5 | aria-label | `aria-label` 属性 |
| 6 | title | `title` 属性 |

### 5.5 field_category一覧（AIが判定）

#### 名前系（6カテゴリ）

| カテゴリ | 説明 | 入力例 |
|---------|------|--------|
| `last_name` | 姓 | 佐藤 |
| `first_name` | 名 | 太郎 |
| `full_name` | 氏名（結合） | 佐藤 太郎 |
| `last_name_kana` | 姓カナ | サトウ |
| `first_name_kana` | 名カナ | タロウ |
| `name_kana` | ふりがな（結合） | サトウ タロウ |

#### 会社系（4カテゴリ）

| カテゴリ | 説明 | 入力例 |
|---------|------|--------|
| `company` | 会社名 | 株式会社テスト |
| `company_kana` | 会社名カナ | カブシキガイシャテスト |
| `department` | 部署名 | 営業部 |
| `position` | 役職 | 部長 |

#### 連絡先（7カテゴリ）

| カテゴリ | 説明 | 入力例 |
|---------|------|--------|
| `email` | メールアドレス | test@example.com |
| `phone` | 電話番号（結合） | 03-1234-5678 |
| `phone1` / `phone_1` | 市外局番 | 03 |
| `phone2` / `phone_2` | 市内局番 | 1234 |
| `phone3` / `phone_3` | 加入者番号 | 5678 |

#### 住所系（6カテゴリ）

| カテゴリ | 説明 | 入力例 |
|---------|------|--------|
| `zipcode` | 郵便番号（結合） | 106-0032 |
| `zipcode1` / `zipcode_1` | 郵便番号前半 | 106 |
| `zipcode2` / `zipcode_2` | 郵便番号後半 | 0032 |
| `prefecture` | 都道府県（select） | 東京都 |
| `city` | 市区町村 | 港区 |
| `address` | 番地・建物名 | 六本木1-2-3 |

#### 問い合わせ系（2カテゴリ）

| カテゴリ | 説明 | 入力例 |
|---------|------|--------|
| `subject` | 種別・タイトル（select） | その他 |
| `message` | 本文・内容 | お問い合わせ内容... |

#### 同意・その他（5カテゴリ）

| カテゴリ | 説明 |
|---------|------|
| `privacy_agreement` | プライバシーポリシー同意チェック |
| `terms_agreement` | 利用規約同意チェック |
| `checkbox` | その他チェックボックス |
| `gender` | 性別 |
| `url` | URL |
| `other` | 上記いずれにも該当しない（最後の手段） |

### 5.6 AI解析プロンプト設計（Gemini）

**重要な判定ルール**（gemini_service.pyに明示）:

1. **ラベル最優先**: labelフィールドの日本語テキストを最優先で使う
2. **ふりがな判定**: 「ふりがな」「フリガナ」「カナ」を含む → `name_kana`
3. **name属性判定**: "furi"/"kana"を含む → `name_kana`（companyは除く）
4. **select判定**: 「お問い合わせ先」「種別」→ `subject` / 47都道府県 → `prefecture`
5. **連続フィールド**: 姓→名、phone1→phone2→phone3 の順序推論
6. **チェックボックス**: プライバシー→`privacy_agreement` / 利用規約→`terms_agreement` / 他→`checkbox`
7. **other禁止**: 明確に該当しない場合のみ使用

**JSONレスポンス修復機能**: AIが不完全なJSONを返した場合、最後の完全なオブジェクトまでを切り出して修復。

### 5.7 NG判定（営業対象外フォームの除外）

#### NG判定ロジック

**データソース**: URLパスとフォームフィールド情報のみ（本文・タイトルは誤判定防止のため不使用）

**判定アルゴリズム**:
1. URLパスにNGパターンが含まれる → 即NG
2. フィールドラベル・name・placeholder・select選択肢にNGパターンが **2件以上** マッチ → NG
3. いずれにも該当しない → OK

#### NGパターン一覧

| カテゴリ | URLパスパターン | フィールドラベルパターン |
|---------|---------------|----------------------|
| `recruitment`（採用） | recruit, career, entry, jobs, hiring, saiyo, boshu | 応募, エントリー, 志望動機, 履歴書, 職務経歴, 希望職種, 希望勤務地, 入社希望日, 現在の年収, 学歴, 卒業年, 在籍企業 |
| `reservation`（予約） | reserve, booking, reservation, yoyaku | 予約日, 予約時間, 来店日, 来店時間, 人数, チェックイン, チェックアウト, 宿泊日, 宿泊数, 希望日時, 来院日 |
| `medical`（医療） | patient, shinryo, jushin | 患者, 症状, 診察, 保険証, 受診, 問診, 既往歴, 服用中, 診療科, お薬, 病歴, 保険証番号, 受診希望 |
| `registration`（会員登録） | signup, register, touroku, create-account | パスワード確認, パスワード再入力, 会員登録, ユーザーID, ログインID, パスワード設定, 秘密の質問 |

### 5.8 automation_type振り分けルール

| 条件 | automation_type | 理由 |
|------|----------------|------|
| `ng_flag = True` | manual | 営業NG（手動確認が必要） |
| `recaptcha_type = 'v2'` | manual | 人間の操作が必要 |
| `recaptcha_type = 'hubspot-iframe'` | manual | iframe内フォーム |
| `recaptcha_type = 'v3'` | auto | 自動検証可能 |
| `recaptcha_type = 'none'` | auto | reCAPTCHAなし |
| その他 | manual | 安全側に倒す |

### 5.9 推定処理時間の計算

```python
base_time = field_count × 2  # 2秒/フィールド

if recaptcha_type == 'v2':   return base_time + 60  # 手動CAPTCHA解決
elif recaptcha_type == 'v3': return base_time + 5   # 自動検証
else:                        return base_time + 3   # 送信+確認
```

### 5.10 バッチ処理パラメータ

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| `CHECKPOINT_EVERY` | 50件 | 結果JSONを中間保存 |
| `DISCORD_NOTIFY_EVERY` | 500件 | Discord進捗通知 |
| `form_url timeout` | 45,000ms | 1フォームあたりのタイムアウト |
| URLキャッシュ | あり | 同一form_urlは再解析しない |
| 結果ファイル | `/opt/ai-auto-form/test-results/YYYYMMDD-batch-analyze.json` | |
| ログファイル | `/opt/ai-auto-form/test-results/YYYYMMDD-batch-analyze.log` | |

### 5.11 実行コマンド

```bash
# テスト（5件のみ、dry-run）
cd /opt/ai-auto-form
source venv/bin/activate
python batch_form_analyze.py --dry-run --limit 5

# 本番実行（バックグラウンド）
nohup python -u batch_form_analyze.py --product-id 8 \
  > test-results/20260222-batch-analyze.log 2>&1 &

# チェックポイントから再開
nohup python -u batch_form_analyze.py --product-id 8 --resume \
  > test-results/20260222-batch-analyze.log 2>&1 &

# プロセス確認
ps aux | grep batch_form | grep -v grep

# 進捗確認
python3 -c "
import json
with open('test-results/20260222-batch-analyze.json') as f:
    d = json.load(f)
print(f'Progress: {d[\"progress\"]}/{d[\"total_target\"]}')
"
```

---

## 6. F-4: フォーム送信

### 6.1 概要

| 項目 | 値 |
|------|-----|
| **エンジン** | `backend/services/auto_executor.py` → `AutoExecutor` |
| **API** | `POST /api/simple/tasks/{id}/auto-execute` |
| **入力** | `Task.form_analysis` + `Product.sender_*` |
| **出力** | `Task.status`, `Task.submitted`, スクリーンショット |
| **コスト** | 無料（AI不使用、ルールベースマッピング） |

### 6.2 処理パラメータ

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| `EXECUTION_TIMEOUT` | 120秒 | タスク全体のタイムアウト |
| `MAX_RETRIES` | 3回 | 自動リトライ回数 |
| `RETRY_DELAY` | 5秒 | リトライ間隔 |
| ページロード | 30秒 | page.goto タイムアウト |
| networkidle待機 | 15秒 | 送信後の待機 |
| fill_rate閾値 | 50% | これ以下は送信中止 |

### 6.3 3段階送信フロー

#### Stage 1: フォーム入力

```
1. form_analysisのform_fieldsを順次処理
2. 各フィールドのfield_categoryに対応するProduct値を取得
   → _get_value_for_category(product, category, company)
3. セレクタ優先順:
   ① input[name="xxx"] / textarea[name="xxx"]
   ② input[id="xxx"] / textarea[id="xxx"]
   ③ input[name*="xxx"]（部分一致）
   ④ input[id*="xxx"]（部分一致）
4. 特殊処理:
   - select → _handle_select()（都道府県自動検出、種別優先キーワード）
   - checkbox → _handle_checkbox()（同意/選択式の自動判別）
   - カスタムセレクト → Mantine/React Select対応
5. ハニーポットフィールドは除外（_wpcf7_ak, honeypot, is_bot等）
6. fill_rate計算（成功数/対象数 × 100）
```

#### Stage 2: 送信ボタン検出・クリック

送信ボタンの検出優先順:

| 優先度 | セレクタ |
|--------|---------|
| 1 | `button[type="submit"]` |
| 2 | `input[type="submit"]` |
| 3 | `button:has-text("送信")` |
| 4 | `button:has-text("確認")` |
| 5 | `button:has-text("入力内容を確認")` |
| 6 | `button:has-text("確認する")` |
| 7 | `button:has-text("確認画面へ")` |
| 8 | `input[value="送信"]` / `input[value="確認"]` |
| 9 | `a:has-text("送信")` / `a:has-text("確認")` |

- JSダイアログ（alert/confirm）は自動accept
- 送信後、networkidle + 2秒安定化待機

#### Stage 3: 確認画面突破

```
1. 完了検出（以下キーワードがあれば終了）:
   ありがとうございます, 送信が完了, 送信しました, 受け付けました,
   受付完了, 送信完了, Thank you, successfully submitted, 自動返信メール

2. 確認画面検出（以下キーワードがあれば送信ボタンを再探索）:
   入力内容の確認, 入力内容をご確認, 確認画面, 以下の内容で,
   ご確認ください, 送信してよろしいですか, 下記の内容で

3. 最終送信ボタン検出:
   ① button:has-text("送信する")
   ② button:has-text("この内容で送信")
   ③ button:has-text("送信")
   ④ input[type="submit"][value*="送信"]
   ⑤ a:has-text("送信する") / a:has-text("送信")
   ⑥ フォールバック: form.submit() JS実行

4. 送信後に完了キーワードを再チェック
```

### 6.4 dry-runモード

| 処理 | dry-run=true | dry-run=false |
|------|-------------|---------------|
| フォーム入力 | ✅ 実行 | ✅ 実行 |
| スクリーンショット | ✅ 保存 | ✅ 保存 |
| 送信ボタンクリック | ❌ スキップ | ✅ 実行 |
| 確認画面突破 | ❌ スキップ | ✅ 実行 |
| Task.submitted | false | true |

### 6.5 メッセージテンプレート変数

`message_template` 内で使用可能な変数:

| 変数 | 展開先 |
|------|--------|
| `{{company_name}}` | 送信先企業名 |
| `{{company_url}}` | 送信先WebサイトURL |
| `{{company_form_url}}` | 送信先フォームURL |
| `{{company_industry}}` | 送信先企業の業種 |
| `{{sender_company}}` | 送信者の会社名 |
| `{{sender_name}}` | 送信者名 |
| `{{product_name}}` | 案件名 |

### 6.6 メッセージ生成パイプライン（3層構造）

メッセージ（問い合わせ本文）は以下の3層で生成される。各層は独立しており、上位の層が下位を上書きする。

```
┌─────────────────────────────────────────────────────────┐
│ 層3: 企業公式サイト解析→高精度メッセージ【デッドコード】    │
│   analyze_company_website() → generate_personalized_message()│
│   → generate_insight()                                   │
│   状態: 未接続（DB側の公式サイト解析パイプラインが前提）     │
│   接続予定: Phase 2以降                                   │
└─────────────────────────────────────────────────────────┘
                          ▲ 上書き
┌─────────────────────────────────────────────────────────┐
│ 層2: DB情報ベースAIカスタマイズ【実装済み・オプトイン】     │
│   gemini_service.py → generate_custom_message_simple()   │
│   Gemini 2.5 Flash, temperature=0.7                      │
│   コスト: 約0.019円/件                                    │
└─────────────────────────────────────────────────────────┘
                          ▲ 上書き
┌─────────────────────────────────────────────────────────┐
│ 層1: テンプレート変数展開【稼働中】                        │
│   _apply_template_variables() → str.replace()            │
│   AI不使用、コスト0円                                     │
└─────────────────────────────────────────────────────────┘
```

#### 層1: テンプレート変数展開（稼働中）

| 項目 | 値 |
|------|-----|
| **状態** | ✅ 稼働中（全タスクで実行） |
| **実装箇所** | `auto_executor.py` → `_apply_template_variables()` |
| **方式** | `str.replace()` による単純置換 |
| **AI使用** | なし |
| **コスト** | 0円 |

対応変数（7種）:

| 変数 | 展開先 |
|------|--------|
| `{{company_name}}` | 送信先企業名 |
| `{{company_url}}` | 送信先WebサイトURL |
| `{{company_form_url}}` | 送信先フォームURL |
| `{{company_industry}}` | 送信先企業の業種 |
| `{{sender_company}}` | 送信者の会社名 |
| `{{sender_name}}` | 送信者名 |
| `{{product_name}}` | 案件名 |

`message_template` に上記変数を埋め込むことで、企業ごとにパーソナライズされたメッセージを生成する。AI不使用のため追加コストは発生しない。

#### 層2: DB情報ベースAIカスタマイズ（実装済み・オプトイン）

| 項目 | 値 |
|------|-----|
| **状態** | ✅ 実装済み（オプトイン） |
| **実装箇所** | `backend/services/gemini_service.py` → `generate_custom_message_simple()` |
| **AIモデル** | Gemini 2.5 Flash |
| **temperature** | 0.7 |
| **コスト** | 約0.019円/件 |

**パスA: タスク一括生成時（バッチ）**
- `generate_tasks_bulk.py` で `use_ai: true` を指定した場合に実行
- タスク生成と同時にAIカスタマイズメッセージを `form_data.message` に格納

**パスB: 個別タスクのAI再生成（API）**
- `POST /api/simple/tasks/<id>/regenerate-message`
- 既存タスクのメッセージをAIで再生成

**入力情報（DB由来）**:

| 情報 | ソース |
|------|--------|
| 企業名 | `simple_companies.name` |
| 業種 | `simple_companies.industry` |
| 企業説明 | `simple_companies.description` |
| 従業員数 | `simple_companies.employee_count` |
| 設立年 | `simple_companies.established_year` |

これらのDB情報をもとに、Gemini APIがテンプレートをベースにしつつ企業特性に合わせたメッセージを生成する。

#### 層3: 企業公式サイト解析→高精度メッセージ（デッドコード）

| 項目 | 値 |
|------|-----|
| **状態** | ⚠️ デッドコード（未接続） |
| **実装箇所** | `backend/services/gemini_service.py` |
| **関数群** | `analyze_company_website()` → `generate_personalized_message()` → `generate_insight()` |
| **前提条件** | DB側の公式サイト解析パイプライン（未構築） |
| **接続予定** | Phase 2以降 |

企業の公式Webサイトを解析し、事業内容・サービス・ニュースなどの情報を抽出した上で、高精度なパーソナライズメッセージを生成する。現時点ではコードは存在するが、呼び出し元が接続されていないデッドコードの状態。DB側のWebサイトクローリング・解析基盤が構築された後に接続予定。

---

## 7. データモデル

### 7.1 simple_companies

| カラム | 型 | NULL | 説明 |
|--------|-----|------|------|
| `id` | Integer | NOT NULL | PK |
| `name` | String(200) | NOT NULL | 企業名 |
| `website_url` | Text | NOT NULL | WebサイトURL |
| `form_url` | Text | NOT NULL | お問い合わせフォームURL |
| `industry` | String(100) | NULL | 業種 |
| `created_at` | DateTime | DEFAULT | 作成日時 |

### 7.2 simple_products

| カラム | 型 | 説明 |
|--------|-----|------|
| `id` | Integer | PK |
| `name` | String(200) | 商材名 |
| `description` | Text | 説明 |
| `message_template` | Text | メッセージテンプレート |
| **送信者基本情報** | | |
| `sender_name` | String(100) | フルネーム |
| `sender_last_name` | String(50) | 姓 |
| `sender_first_name` | String(50) | 名 |
| `sender_last_name_kana` | String(50) | 姓カナ |
| `sender_first_name_kana` | String(50) | 名カナ |
| `sender_gender` | String(10) | 性別 |
| **送信者会社情報** | | |
| `sender_company` | String(200) | 会社名 |
| `sender_company_kana` | String(200) | 会社名カナ |
| `sender_company_url` | String(500) | 会社URL |
| `sender_department` | String(100) | 部署名 |
| `sender_position` | String(100) | 役職 |
| **連絡先（分割対応）** | | |
| `sender_phone` | String(50) | 電話番号（統合） |
| `sender_phone_1/2/3` | String(10) | 電話番号（分割） |
| `sender_mobile_1/2/3` | String(10) | 携帯番号（分割） |
| `sender_fax_1/2/3` | String(10) | FAX番号（分割） |
| `sender_email` | String(200) | メール |
| `sender_email_company` | String(200) | 会社用メール |
| `sender_email_personal` | String(200) | 担当者用メール |
| **住所（分割対応）** | | |
| `sender_zipcode_1/2` | String(10) | 郵便番号（前半/後半） |
| `sender_prefecture` | String(50) | 都道府県 |
| `sender_city` | String(100) | 市区 |
| `sender_address` | String(500) | 町名以降 |
| **問い合わせ** | | |
| `sender_inquiry_title` | String(500) | タイトル |
| `sender_inquiry_detail` | Text | 詳細 |
| `inquiry_type_priority` | String(500) | 種別優先キーワード（カンマ区切り） |
| `created_at` | DateTime | 作成日時 |

### 7.3 simple_tasks

| カラム | 型 | 説明 |
|--------|-----|------|
| `id` | Integer | PK |
| `company_id` | Integer | FK → simple_companies |
| `product_id` | Integer | FK → simple_products |
| `status` | String(20) | pending / in_progress / completed / failed |
| `form_data` | JSON | sender情報のスナップショット |
| `screenshot_path` | Text | 結果スクリーンショットのパス |
| `submitted` | Boolean | 実際に送信されたか（dry-run=false） |
| `created_at` | DateTime | 作成日時 |
| `completed_at` | DateTime | 完了日時 |
| **Phase 2-B拡張** | | |
| `automation_type` | String(20) | 'auto' or 'manual' |
| `recaptcha_type` | String(20) | 'v2' / 'v3' / 'none' / etc |
| `estimated_time` | Integer | 推定処理時間（秒） |
| `form_analysis` | JSON | フォーム解析結果（全情報格納） |

### 7.4 form_analysis JSON構造

```json
{
  "url": "https://example.com/contact",
  "recaptcha_type": "none",
  "has_recaptcha": false,
  "recaptcha_details": {
    "v2_checkbox": false,
    "v2_iframe": false,
    "v3_badge": false,
    "v3_script": false
  },
  "form_fields": [
    {
      "type": "input",
      "name": "company",
      "id": "company",
      "label": "会社名 *",
      "placeholder": "株式会社〇〇",
      "required": true,
      "field_category": "company",
      "ai_confidence": 0.95,
      "ai_reasoning": "ラベル「会社名」から判定"
    }
  ],
  "field_count": 8,
  "estimated_time": 19,
  "analysis_status": "success",
  "analyzed_at": "2026-02-22 10:15:27",
  "analysis_duration": 12.3,
  "ai_analyzed": true,
  "ng_flag": false,
  "ng_reason": null
}
```

---

## 8. コスト構造

### 8.1 実績コスト（2026年2月実績）

| パイプライン | 当初見積もり | 実績単価 | 乖離 | 備考 |
|------------|-----------|---------|------|------|
| F-3: フォーム解析（Gemini 2.5 Flash） | ¥0.019/件 | **¥1.6/件** | **84倍** | Output tokenが高コスト |
| F-4: フォーム送信（ルールベース） | ¥0/件 | **¥0/件** | - | AI不使用 |

**2月実績（約12,500件処理）:**

| 項目 | 値 |
|------|-----|
| F-3 総費用 | ¥20,139 |
| 1件あたり | ¥1.6 |
| Input tokens合計 | 63.6M |
| Output tokens合計 | 49.9M |

### 8.2 F-3 高コストの原因分析

| 指標 | 値 | 費用 | 構成比 |
|------|-----|------|-------|
| Input tokens/件 | ~5,088 | ¥0.22/件 | **14%** |
| Output tokens/件 | ~3,992 | ¥1.39/件 | **86%** |

**高コストの主因:**
- Output単価がInput単価の**約8倍**（¥0.348 vs ¥0.043 /1K tokens）
- AIがフィールドごとに `ai_reasoning`, `ai_confidence` 等の詳細JSONを生成
- 1フォーム平均8フィールド × 約500トークン/フィールド = ~4,000 Output tokens

**参考比較（DB側 E1 Gemini 2.0 Flash）:**

| 指標 | E1 (2.0 Flash) | F-3 (2.5 Flash) |
|------|---------------|------------------|
| Input tokens/件 | ~4,045 | ~5,088 |
| Output tokens/件 | **~112** | **~3,992** |
| Output比率 | 2.7% | 44% |
| 実績単価 | ¥0.069/件 | ¥1.6/件 |

E1はHTMLを送って短い回答（URL）を返すだけなのでOutputが少ない。F-3はフィールドごとの詳細JSON生成が必要なためOutputが膨大。

### 8.3 コスト削減TODO

| 施策 | 削減見込み | 影響 |
|------|----------|------|
| `ai_reasoning` 廃止 | Output 30-40%削減 | デバッグ時の判定理由が不明に |
| `ai_confidence` 廃止 | Output 10%削減 | 信頼度による振り分けが不可に |
| `max_tokens` 8,000→3,000 | 異常な長文レスポンス防止 | 大規模フォームで切り捨てリスク |
| Gemini 2.0 Flashへ変更 | Output単価大幅削減 | 解析精度への影響要検証 |

### 8.4 月間コスト見積もり（実績ベース）

| シナリオ | 件数 | 月額 |
|---------|------|------|
| 現状規模 | 12,000件 | **約¥19,200** |
| 最適化後（推定） | 12,000件 | **約¥8,000〜12,000** |
| 規模拡大 | 50,000件 | **約¥80,000**（最適化前） |

### 8.5 備考

- フォーム送信（F-4）はAI不使用のためコスト0円
- URLキャッシュにより同一form_urlの企業は1回のみ解析
- Gemini APIリトライは最大2回（指数バックオフ: 1秒, 3秒）
- **大規模バッチ実行前は必ず実績単価ベースでコスト見積もりを提示し、承認を得てから実行すること**

---

## 9. 処理速度・パフォーマンス

### 9.1 ステップ別パフォーマンス

| ステップ | 1件あたり時間 | 推定スループット | ボトルネック |
|---------|-------------|-----------------|-------------|
| F-1: CSVインポート | <1ms | 10,000件/分 | DB INSERT |
| F-2: タスク生成 | <1ms | 10,000件/分 | DB INSERT |
| F-3: フォーム解析 | 10〜45秒 | 80〜360件/時 | ページロード + AI解析 |
| F-4: フォーム送信 | 15〜120秒 | 30〜240件/時 | ページロード + 入力 + 確認画面 |

### 9.2 バッチ実績（2026-02-25時点）

| 指標 | 初回バッチ | 再開バッチ | 合計 |
|------|----------|----------|------|
| 対象件数 | 12,489件 | 3,025件 | - |
| 処理済み | 9,450件 | 3,003件 | 12,453件 |
| 処理速度 | 約200件/時 | 約200件/時 | - |
| Auto判定 | - | 2,040 (67.4%) | ~7,300件 |
| Manual判定 | - | 985 (32.6%) | ~3,700件 |
| NG検出 | - | 46 | ~150件 |
| エラー | - | 22 | ~70件 |

**再解析バッチ（ai_analyzed=false分）:**

| 指標 | 値 |
|------|-----|
| 対象件数 | 6,070件 |
| 理由 | Gemini API無料枠超過によりルールベースフォールバック |
| 状態 | 実行中（2026-02-25開始） |

---

## 10. 運用ルール

### 10.1 Discord通知

| タイミング | 内容 |
|-----------|------|
| バッチ開始 | 対象件数、product_id、resume状況 |
| 500件ごと | 進捗率、auto/manual/NG件数、経過時間、残り推定 |
| エラー時 | エラー内容（即時） |
| バッチ完了 | サマリー（件数・成功率・処理時間・結果ファイルパス） |

- **プレフィックス**: `[DeepBiz Send]`
- **Webhook**: 環境変数 `DEEPBIZ_DISCORD_WEBHOOK_URL` から読み込み

### 10.2 バックグラウンド実行

```bash
# 推奨: nohup + python -u（バッファなし出力）
nohup python -u batch_form_analyze.py --product-id 8 \
  > test-results/YYYYMMDD-batch-analyze.log 2>&1 &

# resume対応
nohup python -u batch_form_analyze.py --product-id 8 --resume \
  > test-results/YYYYMMDD-batch-analyze.log 2>&1 &
```

### 10.3 結果ファイルの保存先

| 種類 | パス |
|------|------|
| バッチ結果JSON | `/opt/ai-auto-form/test-results/YYYYMMDD-batch-analyze.json` |
| バッチログ | `/opt/ai-auto-form/test-results/YYYYMMDD-batch-analyze.log` |
| スクリーンショット | `/opt/ai-auto-form/screenshots/task_{id}_*.png` |

---

## 11. 関連ファイル一覧

### スクリプト

| ファイル | ステップ | 状態 |
|---------|---------|------|
| `import_wantedly_csv.py` | F-1 (CLI) | ✅ 現役 |
| `generate_tasks_bulk.py` | F-2 | ✅ 現役 |
| `batch_form_analyze.py` | F-3 (バッチ) | ✅ 現役 |
| `test_ng_filter_v2.py` | F-3 (NGテスト) | ユーティリティ |

### バックエンドサービス

| ファイル | 役割 |
|---------|------|
| `backend/services/form_analyzer.py` | フォーム解析エンジン（FormAnalyzer） |
| `backend/services/gemini_service.py` | Gemini AI連携（GeminiService） |
| `backend/services/auto_executor.py` | フォーム送信エンジン（AutoExecutor） |
| `backend/simple_models.py` | データモデル定義 |
| `backend/api/simple_api.py` | REST API（インポート・解析・送信） |
| `backend/database.py` | DB接続（SessionLocal） |

### フロントエンド

| ファイル | 役割 |
|---------|------|
| `simple-console-v2.html` | ワーカー用コンソール（手動送信） |
| `admin-phase2a.html` | 管理コンソール（案件・企業管理） |

### データ

| ファイル | 内容 |
|---------|------|
| `inport/wantedly_confirmed_20260221.csv` | Wantedlyインポート用CSV（12,925件） |
| `sample_data/companies_template.csv` | CSVテンプレート |

### ドキュメント

| ファイル | 内容 |
|---------|------|
| `docs/FORM_AUTOMATION_SPEC.md` | フォーム解析・自動入力の詳細仕様 |
| `docs/CURRENT_STATE.md` | システム状態・TODO管理 |
| `docs/DATA_IMPORT_GUIDE.md` | CSVインポートガイド |
| `docs/MVP_SPEC.md` | MVP機能仕様 |

---

## 12. 既知の問題・TODO

| 課題 | 影響 | 優先度 | 対策案 |
|------|------|--------|--------|
| ラジオボタン未対応 | 一部フォームで選択不可 | 🟡中 | radio要素のハンドラー追加 |
| ファイルアップロード未対応 | 添付必須フォームで送信不可 | 🟢低 | 対象外として除外 |
| date picker未対応 | 日付入力フォームで失敗 | 🟢低 | 予約フォームはNGフィルタで除外済み |
| Discord通知が成功時にログ出力しない | 通知成否の確認が困難 | 🟡中 | discord_notify()に成功ログ追加 |
| gmap_checked_at相当のフラグがない | 解析済み・フォームなしの区別不可 | 🟢低 | form_analysisのanalysis_statusで代替可 |
| 2Captcha未統合 | reCAPTCHA v2は手動のみ | 🟢低 | コスト+30,000円/月の投資判断が必要 |

---

## 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|----------|
| 1.0 | 2026-02-22 | 初版作成（コード調査に基づく） |
| 1.1 | 2026-02-22 | セクション6.6 メッセージ生成パイプライン（3層構造）を追加 |
| 1.2 | 2026-02-25 | セクション8 コスト構造を実績データに基づき全面改訂（単価84倍乖離の原因分析、削減TODO追加）、バッチ実績を最新化 |
