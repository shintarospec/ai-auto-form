# フォーム解析・自動入力 仕様書

## 概要

本システムは「AI解析」と「ルールベース入力」のハイブリッド方式を採用し、
高精度かつ低コストでフォーム自動入力を実現します。

### 基本方針

| 優先度 | アプローチ | 役割 |
|-------|-----------|------|
| **1st** | Gemini AI | 正確なfield_category分類（精度向上を最優先） |
| **2nd** | フォールバック | AI誤分類時の補正（保険として機能） |

**AIの精度向上を基本とし、フォールバックは最後の保険とする。**

```
┌─────────────────────────────────────────────────────────────┐
│                    処理フロー                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  【STEP 1】フォーム解析（AI使用）                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Gemini 2.5 Flash                                    │   │
│  │  - HTMLを解析してフィールド構造を認識                   │   │
│  │  - field_category を判定（last_name, phone_1, etc）   │   │
│  │  - セレクトボックスの選択肢も取得                       │   │
│  │  コスト: 約0.019円/社                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│                    解析結果をDBに保存                         │
│                          ↓                                  │
│  【STEP 2】自動入力（AI不使用 → ルールベースマッチング）        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  auto_executor.py                                    │   │
│  │  - field_category と product の値をマッピング          │   │
│  │  - _get_value_for_category() で対応する値を取得        │   │
│  │  - セレクトボックスは条件分岐で選択                      │   │
│  │  コスト: 0円                                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. フォーム解析（AI解析）

### 1.1 使用AI

- **モデル**: Gemini 2.5 Flash
- **コスト**: 約0.019円/フォーム
- **処理時間**: 2-3秒
- **設定ファイル**: `backend/services/gemini_service.py`

### 1.2 AI精度向上のためのプロンプト設計

プロンプトでは以下を明示的に指定：

```
【重要な判定ルール】
1. ラベルを最優先で判定 - labelフィールドの日本語を最優先で使う
2. 「ふりがな」「フリガナ」「カナ」「よみがな」を含むラベル → name_kana
3. name属性に「furi」「kana」を含む → name_kana
4. チェックボックスの分類:
   - 「プライバシー」「個人情報」「Privacy」を含む → privacy_agreement
   - 「利用規約」「terms」を含む → terms_agreement
   - 上記以外 → checkbox
5. otherは最後の手段 - 明らかに上記のどれにも該当しない場合のみ
```

**新しいカテゴリを追加する場合は、必ずGeminiプロンプトにも追加すること。**

### 1.3 解析対象

| 要素 | 検出内容 |
|------|---------|
| input[type="text"] | name, id, placeholder, label |
| input[type="email"] | メールアドレス欄 |
| input[type="tel"] | 電話番号欄 |
| textarea | 本文・メッセージ欄 |
| select | プルダウン選択肢（options含む） |
| checkbox | 同意チェックボックス等 |
| reCAPTCHA | v2/v3の検出 |

### 1.3 出力（field_category）

AIが各フィールドに付与するカテゴリ：

| カテゴリ | 説明 | 例 |
|---------|------|-----|
| `last_name` | 姓 | 佐藤 |
| `first_name` | 名 | 太郎 |
| `last_name_kana` | 姓（カナ） | サトウ |
| `first_name_kana` | 名（カナ） | タロウ |
| `name_kana` | ふりがな（結合） | サトウ タロウ |
| `full_name` | 氏名（結合） | 佐藤 太郎 |
| `company` | 会社名 | 株式会社テスト |
| `company_kana` | 会社名（カナ） | カブシキガイシャテスト |
| `department` | 部署名 | 営業部 |
| `position` | 役職 | 部長 |
| `email` | メールアドレス | test@example.com |
| `phone_1` / `phone1` | 電話番号（市外局番） | 03 |
| `phone_2` / `phone2` | 電話番号（市内局番） | 1234 |
| `phone_3` / `phone3` | 電話番号（加入者番号） | 5678 |
| `phone` | 電話番号（結合） | 03-1234-5678 |
| `mobile_1` | 携帯番号（1） | 090 |
| `mobile_2` | 携帯番号（2） | 1234 |
| `mobile_3` | 携帯番号（3） | 5678 |
| `fax_1` | FAX番号（1） | 03 |
| `fax_2` | FAX番号（2） | 1234 |
| `fax_3` | FAX番号（3） | 5678 |
| `zipcode_1` / `zipcode1` | 郵便番号（前半） | 106 |
| `zipcode_2` / `zipcode2` | 郵便番号（後半） | 0032 |
| `zipcode` | 郵便番号（結合） | 106-0032 |
| `prefecture` | 都道府県（select） | 東京都 |
| `city` | 市区町村 | 港区 |
| `address` | 番地・建物名 | 六本木1-2-3 |
| `subject` | お問い合わせ種別・先（select） | その他 |
| `inquiry_type` | お問い合わせ種別（別名） | サービスについて |
| `message` | 本文・内容 | お問い合わせ内容... |
| `url` | URL | https://example.com |
| `gender` | 性別 | 男性 |
| `privacy_agreement` | プライバシーポリシー同意 | ✓ |
| `terms_agreement` | 利用規約同意 | ✓ |
| `checkbox` | その他チェックボックス | ✓ |
| `other` | その他 | - |

### 1.4 実装ファイル

- `backend/services/form_analyzer.py` - フォーム解析メイン
- `backend/services/gemini_service.py` - Gemini API呼び出し

---

## 2. 自動入力（ルールベース）

### 2.1 マッピングルール

`auto_executor.py` の `_get_value_for_category()` で定義：

```python
def _get_value_for_category(self, product, category, company):
    """field_categoryに対応する値を返す"""
    
    # 名前系
    if category == 'last_name':
        return product.sender_last_name
    if category == 'first_name':
        return product.sender_first_name
    if category == 'full_name':
        return product.sender_name
    # ... 以下同様
```

### 2.2 セレクトボックス処理

`_handle_select()` で処理：

| カテゴリ | 処理ロジック |
|---------|-------------|
| `prefecture` | 47都道府県リストと照合、product.sender_prefectureを選択 |
| `subject` / `inquiry_type` | 優先キーワードマッチ → なければ最初の有効な選択肢 |
| `gender` | product.sender_genderを選択 |
| `position` | 部分一致 → 「その他」 → 最初の有効な選択肢（v1.3.3） |
| `other` / 未知 | 「その他」 → 最初の有効な選択肢（v1.3.4） |
| その他 | 対応する値で部分一致検索 |

#### 役職セレクトのフォールバック（v1.3.3追加）

役職セレクトは企業ごとに選択肢が異なるため、マッチしないケースが多い。

```
問題例:
  sender_position = "編集員"
  選択肢 = ["経営者・役員", "部長", "課長", "その他"]
  → "編集員"は選択肢にない！
```

**フォールバック処理**:

```python
# 1. まず部分一致を試行
for opt in options:
    if value in opt['text'] or opt['text'] in value:
        target_value = opt['value']
        break

# 2. マッチしない場合 → 「その他」を選択
if not target_value and category == 'position':
    for opt in options:
        if 'その他' in opt['text']:
            target_value = opt['value']
            break
    
    # 3. 「その他」もない場合 → 最初の有効な選択肢
    if not target_value:
        for opt in options:
            if opt['value'] and '選択' not in opt['text']:
                target_value = opt['value']
                break
```

このフォールバックにより、どんな役職でも必ず何かが選択される。

#### 未知セレクトのフォールバック（v1.3.4追加）

「主な担当業務」など、システムが知らないセレクトに対応。

```
問題例:
  フィールド: 「主な担当業務をお選びください」
  category = "other"  ← AIが分類できない
  選択肢 = ["経営企画", "営業", "マーケティング", "その他"]
```

**対応**:
- `category in ['position', 'other', 'unknown', '']` の場合にフォールバック適用
- 「その他」を優先的に選択、なければ最初の有効な選択肢

#### ラベルからのカテゴリ補正（セレクト用）

セレクトボックスのラベルからカテゴリを補正：

| ラベルキーワード | 補正先カテゴリ |
|------------------|-------------|
| 役職 | `position` |
| 問い合わせ, 問合せ, カテゴリ, 種別, 種類 | `subject` |
| 姓（単独） | `last_name`（v1.3.5） |
| 名（単独） | `first_name`（v1.3.5） |

```python
# セレクトボックスのラベル補正
if field_type == 'select':
    inquiry_keywords = ['問い合わせ', '問合せ', 'カテゴリ', '種別', '種類']
    if any(kw in label for kw in inquiry_keywords):
        category = 'subject'
```

### 2.3 都道府県自動検出

セレクトボックスの選択肢に都道府県が10個以上含まれていれば、
自動的に都道府県セレクトと判定：

```python
prefectures = ['北海道', '青森県', ... '沖縄県']  # 47都道府県
pref_count = sum(1 for opt in options if any(p in opt['text'] for p in prefectures))
if pref_count >= 10:
    is_prefecture_select = True
```

### 2.4 種別優先キーワード（v1.1追加）

案件（Product）に `inquiry_type_priority` を設定可能：

```
例: その他,一般,お問い合わせ
```

処理順序：
1. 優先キーワードを順番にチェック
2. マッチする選択肢があれば選択
3. マッチしなければ最初の有効な選択肢を選択

### 2.5 カスタムセレクト対応（v1.3追加）

モダンなUIフレームワーク（Mantine、React Select等）のカスタムセレクトに対応。

#### 対応UIコンポーネント

| フレームワーク | セレクタ | 種類 |
|---------------|---------|------|
| Mantine MultiSelect | `input.mantine-MultiSelect-searchInput` | 複数選択 |
| Mantine Select | `input.mantine-Select-input` | 単一選択 |
| React Select | `div.select__control` | 単一/複数 |
| 汎用 | `div[class*="select"]` | 汎用 |

#### 処理フロー

```
1. 標準<select>要素を検索
2. 見つからない場合 → カスタムセレクト処理へ
3. 処理済みセレクタをスキップ（重複処理防止）
4. クリックでドロップダウン展開 → [role="option"]を選択
```

#### 複数カスタムセレクトがある場合

同一ページに複数のカスタムセレクトがある場合、処理済みセレクタを記録してスキップ：

```python
processed_custom_selects = set()  # {'mantine-MultiSelect', 'mantine-Select'}
```

これにより、1つ目のMultiSelect処理後は2つ目のSelect処理に進む。

### 2.6 チェックボックス処理（v1.3追加）

`_handle_checkbox()` で処理。カテゴリ自動分類機能あり：

| カテゴリ | 検出条件 | 例 |
|---------|---------|----|
| `privacy_agreement` | プライバシー, privacy, 個人情報 | プライバシーポリシーに同意 |
| `terms_agreement` | 利用規約, terms, 規約 | 利用規約に同意 |
| `agreement` | 同意, agree, consent, confirm | 上記に同意します |
| `checkbox` | 上記以外 | メルマガ購読 |

#### 同意チェックボックス vs 選択式チェックボックス

| 種類 | 判定条件 | 動作 |
|------|---------|------|
| **同意チェックボックス** | 同名で1つだけ | 全てチェック ✅ |
| **選択式チェックボックス** | 同名で複数ある | `inquiry_type_priority`でフィルタ 🎯 |

#### 選択式チェックボックスの処理フロー

```
1. 同名チェックボックスを全て取得
2. 要素数が1 → 同意チェックボックス → 全てチェック
3. 要素数が2以上 → 選択式チェックボックス
4. 各要素のvalue/labelを取得
5. inquiry_type_priorityのキーワードでマッチング
6. マッチした項目だけをチェック
7. マッチなしの場合は「その他」をチェック
```

#### 例：お問い合わせ種別（選択式）

```html
<input type="checkbox" name="category[]" value="顧問契約の相談">
<input type="checkbox" name="category[]" value="法律相談">
<input type="checkbox" name="category[]" value="取材・講演">
<input type="checkbox" name="category[]" value="その他">
```

`inquiry_type_priority = "取材,その他"` の場合：
- 「取材・講演」✅ チェック（"取材"にマッチ）
- 「その他」✅ チェック（"その他"にマッチ）
- 他の項目はスキップ

### 2.7 同名フィールド対応（v1.3.2追加）

同じ`name`属性を持つフィールドが複数ある場合の対応。

#### 問題例

```html
<!-- 両方とも name="company" だが、意味が異なる -->
<input name="company" placeholder="株式会社〇〇">  <!-- 会社名 -->
<input name="company" placeholder="経営企画部">   <!-- 部署名 -->
```

#### 解決策

1. **フィールドインデックス管理**
   - 同名フィールドを出現順にインデックス付け（0, 1, 2...）
   - `query_selector_all`で全要素取得 → インデックスで選択

2. **ラベルによるカテゴリ強制補正**
   - ラベルに「部署」を含む → `department`に強制変更
   - AIが`company`と判定しても、ルールで上書き

```python
# カテゴリ強制補正
if '部署' in (label or ''):
    category = 'department'  # AIの判定を上書き
```

#### ラベル取得の強化（WPCF7対応）

WordPress Contact Form 7の構造に対応：

```javascript
// wpcf7-form-control-wrapの前の要素からラベルを取得
const wrap = el.closest('.wpcf7-form-control-wrap');
if (wrap) {
    const prevEl = wrap.previousElementSibling;
    if (prevEl) label = prevEl.textContent.trim();
}
```

### 2.8 実装ファイル

- `backend/services/auto_executor.py` - 自動入力メイン
- `backend/services/form_analyzer.py` - フォーム解析・ラベル取得

---

## 3. 案件（Product）データ構造

### 3.1 送信者情報フィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| sender_name | String | 氏名（フルネーム） |
| sender_last_name | String | 姓 |
| sender_first_name | String | 名 |
| sender_last_name_kana | String | 姓（カナ） |
| sender_first_name_kana | String | 名（カナ） |
| sender_gender | String | 性別 |
| sender_company | String | 会社名 |
| sender_company_kana | String | 会社名（カナ） |
| sender_department | String | 部署名 |
| sender_position | String | 役職 |
| sender_phone | String | 電話番号（結合） |
| sender_phone_1 | String | 電話番号（1） |
| sender_phone_2 | String | 電話番号（2） |
| sender_phone_3 | String | 電話番号（3） |
| sender_mobile_1 | String | 携帯番号（1） |
| sender_mobile_2 | String | 携帯番号（2） |
| sender_mobile_3 | String | 携帯番号（3） |
| sender_fax_1 | String | FAX番号（1） |
| sender_fax_2 | String | FAX番号（2） |
| sender_fax_3 | String | FAX番号（3） |
| sender_email | String | メールアドレス |
| sender_email_personal | String | メールアドレス（個人） |
| sender_zipcode_1 | String | 郵便番号（前半） |
| sender_zipcode_2 | String | 郵便番号（後半） |
| sender_prefecture | String | 都道府県 |
| sender_city | String | 市区町村 |
| sender_address | String | 番地・建物名 |
| sender_company_url | String | 会社URL |
| sender_inquiry_title | String | お問い合わせ題名 |
| inquiry_type_priority | String | 種別優先キーワード（カンマ区切り） |

---

## 4. ルール拡張ガイド

### 4.1 新しいfield_categoryを追加する場合

1. **Geminiプロンプトを更新** (`gemini_service.py`)
   - カテゴリ定義に新カテゴリを追加

2. **マッピングを追加** (`auto_executor.py`)
   - `_get_value_for_category()` に条件を追加

3. **Productフィールドを追加**（必要な場合）
   - `simple_models.py` にカラム追加
   - マイグレーション実行
   - `admin-phase2a.html` にUI追加
   - `simple_api.py` にAPI対応追加

### 4.2 セレクトボックスの新パターンを追加する場合

`_handle_select()` に条件分岐を追加：

```python
elif category == 'new_category':
    # 新しいカテゴリの処理ロジック
    for opt in options:
        if some_condition(opt):
            target_value = opt['value']
            break
```

---

## 5. 成功率向上のTips

### 5.1 よくある失敗パターンと対策

| 失敗パターン | 原因 | 対策 |
|-------------|------|------|
| 電話番号が入力されない | 3分割フォームに結合値を入力 | phone_1/2/3カテゴリで対応 |
| 都道府県が選択されない | prefecture未設定 | 案件登録時に必須化 |
| 種別が不適切 | 最初の選択肢が選ばれる | inquiry_type_priorityで制御 |
| カナが入力されない | kanaフィールド未設定 | 案件登録時に入力 |
| ふりがなが入力されない | AIがotherと誤分類 | gemini_service.pyのプロンプトにname_kana追加、フォールバックでfuri/kana検出 |
| カスタムセレクトが選択されない | 標準selectのみ対応 | _handle_custom_select()でMantine/React Select対応 |
| 複数セレクトの2つ目が失敗 | 同一要素を重複処理 | processed_selectorsで処理済みをスキップ |
| 選択式チェックボックスが全選択される | 同名チェックボックスを全てチェック | inquiry_type_priorityでフィルタ（v1.3.1） |
| 部署名に会社名が入力される | 同名フィールドでAIがcompanyと判定 | ラベル「部署」検出で強制補正（v1.3.2） |
| 役職セレクトが未選択 | sender_positionが選択肢にない | 「その他」フォールバック（v1.3.3） |
| 未知セレクトが未選択 | AIがotherと分類、対応値なし | 「その他」フォールバック（v1.3.4） |
| 問い合わせカテゴリが未選択 | AIがmessageと誤分類 | ラベル補正でsubjectに（v1.3.4） |
| 姓名にフルネームが入る | AIが姓/名をnameと誤分類 | ラベル「姓」「名」で補正（v1.3.5） |

### 5.2 デバッグ方法

1. **VNC画面で確認**: 実際の入力状況を目視確認
2. **スクリーンショット**: task実行後に自動保存
3. **fill_results**: API/DBで入力結果詳細を確認

---

## 6. メッセージ生成パイプライン

フォームの「本文」「お問い合わせ内容」欄に入力するメッセージの生成は、3層構造で設計されている。
各層は独立しており、上位の層が有効な場合はその結果が優先される。

```
┌───────────────────────────────────────────────────────┐
│              メッセージ生成の3層構造                      │
├───────────────────────────────────────────────────────┤
│                                                       │
│  【層3】企業公式サイト解析→高精度メッセージ ❌ 未接続     │
│  ┌─────────────────────────────────────────────────┐ │
│  │  analyze_company_website()                       │ │
│  │  → generate_personalized_message()               │ │
│  │  → generate_insight()                            │ │
│  │  入力: 企業公式サイトHTML（リアルタイム解析）        │ │
│  │  コスト: 未定（サイト解析+メッセージ生成の2回呼出）   │ │
│  └─────────────────────────────────────────────────┘ │
│                     ↑ 未接続                          │
│  【層2】DB情報ベースAIカスタマイズ ✅ 実装済み（オプトイン）│
│  ┌─────────────────────────────────────────────────┐ │
│  │  generate_custom_message_simple()                │ │
│  │  入力: company.{name,industry,description,       │ │
│  │        employee_count,established_year}           │ │
│  │  モデル: Gemini 2.5 Flash (temperature=0.7)      │ │
│  │  コスト: 約0.019円/件                              │ │
│  └─────────────────────────────────────────────────┘ │
│                     ↑ use_ai=trueで有効               │
│  【層1】テンプレート変数展開 ✅ 稼働中（デフォルト）       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  _apply_template_variables()                     │ │
│  │  入力: product.message_template + 7変数           │ │
│  │  処理: str.replace() による単純置換               │ │
│  │  コスト: 0円（AI不使用）                           │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### 6.1 層1: テンプレート変数展開（稼働中）

**状態**: ✅ 稼働中（デフォルト動作）
**実装**: `backend/services/auto_executor.py` — `_apply_template_variables()`
**コスト**: 0円（AI不使用）

`product.message_template` に含まれる `{{変数名}}` を `str.replace()` で単純置換する。
すべてのタスクで自動実行され、層2・層3が無効でも必ず動作する。

#### 対応変数一覧

| 変数 | データソース | 例 |
|------|-------------|-----|
| `{{company_name}}` | `company.name` | 株式会社テスト |
| `{{company_url}}` | `company.website_url` | https://example.com |
| `{{company_form_url}}` | `company.form_url` | https://example.com/contact |
| `{{company_industry}}` | `company.industry` | IT・通信 |
| `{{sender_company}}` | `product.sender_company` | 株式会社自社 |
| `{{sender_name}}` | `product.sender_name` | 佐藤太郎 |
| `{{product_name}}` | `product.name` | SEOコンサルティング |

#### 適用対象カテゴリ

変数展開は以下の `field_category` に対して実行される:
- `message`, `inquiry`, `content`, `body`, `subject`, `title`

### 6.2 層2: DB情報ベースAIカスタマイズ（実装済み・オプトイン）

**状態**: ✅ 実装済み（`use_ai: true` でオプトイン）
**実装**: `backend/services/gemini_service.py` — `generate_custom_message_simple()`
**モデル**: Gemini 2.5 Flash（temperature=0.7, max_output_tokens=2048）
**コスト**: 約0.019円/件

DBに登録済みの企業情報をもとに、Geminiがテンプレート全体を企業に合わせてリライトする。
テンプレートの構成・トーン・文字数を維持しつつ、企業の業界・事業内容に合わせた具体的な提案を含める。

#### AIへの入力データ

| 入力 | ソース | 必須 |
|------|--------|------|
| 企業名 | `company.name` | ✅ |
| 業界 | `company.industry` | - |
| 事業内容 | `company.description` | - |
| 従業員数 | `company.employee_count` | - |
| 設立年 | `company.established_year` | - |
| テンプレート文 | `product.message_template` | ✅ |

#### 利用パス

**パスA: タスク一括生成時**
- エンドポイント: `POST /api/simple/tasks/generate-bulk`
- パラメータ: `use_ai: true`
- UI: `admin-phase2a.html` の「AI文面カスタマイズ」チェックボックス（`#ai-toggle`）
- 処理: `backend/api/simple_api.py` — タスク生成ループ内で各企業ごとにGemini呼び出し
- 結果: `task.form_data['message']` にAI生成テキストを格納

**パスB: 個別タスクのAI再生成**
- エンドポイント: `POST /api/simple/tasks/<task_id>/regenerate-message`
- UI: タスク編集モーダルの「AI再生成」ボタン
- 処理: `backend/api/simple_api.py` — 既存タスクのcompany+productからGemini再呼び出し
- 結果: `task.form_data['message']` を上書き

#### フォールバック

AI呼び出しが失敗した場合（APIエラー、タイムアウト等）、層1のテンプレート変数展開にフォールバックする。

#### 層1との優先関係

`task.form_data['message']` にAI生成テキストが格納されている場合、auto_executor はその値を使用する。
層1の変数展開は `product.message_template` に対して実行されるため、AI生成テキストが存在する場合は層2が優先される。

### 6.3 層3: 企業公式サイト解析→高精度メッセージ（未接続・デッドコード）

**状態**: ❌ 未接続（メソッド定義のみ、呼び出し元なし）
**実装**: `backend/services/gemini_service.py` に3メソッド定義済み
**前提**: DB側の公式サイト解析パイプライン（別途構築予定）

#### 設計済みパイプライン

```
企業公式サイトHTML取得
        ↓
analyze_company_website(html, url)
  → 業種、事業内容、強み、課題をJSON抽出
        ↓
generate_personalized_message(product_info, company_analysis, sender_info)
  → 300-500字のパーソナライズメッセージ生成
        ↓
generate_insight(company_analysis, product_info)
  → 100字以内のワーカー向けヒント生成
```

#### 定義済みメソッド

| メソッド | 目的 | 状態 |
|---------|------|------|
| `analyze_company_website(html_content, company_url)` | サイトHTMLからJSON形式で企業情報を抽出 | デッドコード |
| `generate_personalized_message(product_info, company_analysis, sender_info)` | 解析結果からパーソナライズメッセージ生成 | デッドコード |
| `generate_insight(company_analysis, product_info)` | ワーカー向け短文ヒント生成 | デッドコード |

#### 接続に必要な前提条件

1. 企業公式サイトのHTML取得機構（スクレイピング or キャッシュ）
2. `analyze_company_website()` を呼び出すAPIエンドポイントまたはバッチ処理
3. 解析結果の保存先（`simple_companies` にカラム追加 or 別テーブル）
4. `generate_personalized_message()` をタスク生成フローに組み込み

Phase 2以降で接続予定。

---

## 7. バージョン履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| 1.0 | 2026-01-30 | 初版：基本的なfield_category対応 |
| 1.1 | 2026-01-31 | 種別優先キーワード機能追加 |
| 1.2 | 2026-01-31 | name_kana（ふりがな一体型）対応、AI精度向上方針を明文化 |
| 1.3 | 2026-01-31 | カスタムセレクト対応（Mantine/React Select）、チェックボックスカテゴリ分類、複数セレクト処理済みスキップ || 1.3.1 | 2026-01-31 | 選択式チェックボックス対応（inquiry_type_priorityでフィルタ） |
| 1.3.2 | 2026-01-31 | 同名フィールド対応（インデックス管理、ラベル強制補正、WPCF7ラベル取得） |
| 1.3.3 | 2026-01-31 | 役職セレクトフォールバック（マッチしない場合は「その他」を選択） |
| 1.3.4 | 2026-01-31 | 未知セレクトフォールバック、ラベル補正（役職/問い合わせカテゴリ） |
| 1.3.5 | 2026-01-31 | 姓名ラベル補正（「姓」→last_name、「名」→first_name） |
| 1.4 | 2026-02-22 | メッセージ生成パイプライン仕様追加（3層構造: 変数展開/AIカスタマイズ/サイト解析） |