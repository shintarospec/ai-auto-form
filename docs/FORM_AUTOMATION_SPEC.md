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
| その他 | 対応する値で部分一致検索 |

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

#### 複数チェックボックス対応

同一name属性で複数チェックボックスがある場合、全てにチェック：

```python
elements = await page.query_selector_all(selector)
for element in elements:
    await element.check()  # または force click
```

### 2.7 実装ファイル

- `backend/services/auto_executor.py` - 自動入力メイン

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

### 5.2 デバッグ方法

1. **VNC画面で確認**: 実際の入力状況を目視確認
2. **スクリーンショット**: task実行後に自動保存
3. **fill_results**: API/DBで入力結果詳細を確認

---

## 6. バージョン履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| 1.0 | 2026-01-30 | 初版：基本的なfield_category対応 |
| 1.1 | 2026-01-31 | 種別優先キーワード機能追加 |
| 1.2 | 2026-01-31 | name_kana（ふりがな一体型）対応、AI精度向上方針を明文化 |
| 1.3 | 2026-01-31 | カスタムセレクト対応（Mantine/React Select）、チェックボックスカテゴリ分類、複数セレクト処理済みスキップ |