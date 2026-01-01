# AIマッピングのコスト分析

## 📊 Gemini 2.5 Flash 料金体系（2025年12月時点）

| 項目 | 料金 |
|------|------|
| **入力トークン** | $0.00001875 / 1,000 tokens (128K context以下) |
| **出力トークン** | $0.000075 / 1,000 tokens |
| **プロンプトキャッシング（24h有効）** | 入力トークンの1/4のコスト |

**参考**: [Google AI Pricing](https://ai.google.dev/pricing)

---

## 🧮 1フォーム解析あたりのコスト計算

### シナリオ1: DeepBizの問い合わせフォーム（典型例）

#### 入力データ

**1. フォーム構造（DOM解析結果）:**
```json
{
  "action": "https://deepbiz.co.jp/contact/submit",
  "method": "POST",
  "fields": [
    {
      "tag": "input",
      "type": "text",
      "name": "sei",
      "id": "sei",
      "placeholder": "山田",
      "label": "お名前（姓）",
      "required": true
    },
    {
      "tag": "input",
      "type": "text",
      "name": "mei",
      "id": "mei",
      "placeholder": "太郎",
      "label": "お名前（名）",
      "required": true
    },
    {
      "tag": "input",
      "type": "text",
      "name": "sei_kana",
      "placeholder": "ヤマダ",
      "label": "フリガナ（姓）",
      "required": false
    },
    {
      "tag": "input",
      "type": "text",
      "name": "mei_kana",
      "placeholder": "タロウ",
      "label": "フリガナ（名）",
      "required": false
    },
    {
      "tag": "input",
      "type": "email",
      "name": "email",
      "placeholder": "example@company.co.jp",
      "label": "メールアドレス",
      "required": true
    },
    {
      "tag": "input",
      "type": "tel",
      "name": "tel1",
      "placeholder": "090",
      "label": "電話番号",
      "required": true
    },
    {
      "tag": "input",
      "type": "tel",
      "name": "tel2",
      "placeholder": "1234",
      "label": "",
      "required": true
    },
    {
      "tag": "input",
      "type": "tel",
      "name": "tel3",
      "placeholder": "5678",
      "label": "",
      "required": true
    },
    {
      "tag": "input",
      "type": "text",
      "name": "company",
      "placeholder": "株式会社サンプル",
      "label": "会社名",
      "required": false
    },
    {
      "tag": "textarea",
      "name": "message",
      "placeholder": "お問い合わせ内容をご記入ください",
      "label": "お問い合わせ内容",
      "required": true
    }
  ]
}
```
**推定トークン数**: 約600トークン

**2. 利用可能データ（prepare_form_data_from_product）:**
```json
{
  "name": "山田 太郎",
  "last_name": "山田",
  "first_name": "太郎",
  "last_name_kana": "ヤマダ",
  "first_name_kana": "タロウ",
  "email": "test@example.com",
  "email_company": "test@example.com",
  "phone": "090-1234-5678",
  "phone1": "090",
  "phone2": "1234",
  "phone3": "5678",
  "company": "株式会社テスト",
  "company_kana": "カブシキガイシャテスト",
  "zipcode": "106-0032",
  "zipcode1": "106",
  "zipcode2": "0032",
  "prefecture": "東京都",
  "city": "港区",
  "address": "六本木1-1-1",
  "full_address": "東京都港区六本木1-1-1"
}
```
**推定トークン数**: 約400トークン

**3. プロンプト（指示文）:**
```
あなたはフォーム自動入力の専門家です。

【タスク】
以下のフォーム構造に対して、利用可能なデータをマッピングしてください。

【フォーム構造】
{上記JSON}

【利用可能なデータ】
{上記JSON}

【出力形式】
以下のJSON形式で出力してください:
...（約500文字の指示）

【重要なルール】
1. labelのテキストを最優先で考慮する
...（約300文字のルール説明）
```
**推定トークン数**: 約500トークン

#### 入力トークン合計
```
フォーム構造: 600トークン
利用可能データ: 400トークン
プロンプト: 500トークン
───────────────────────
合計: 1,500トークン
```

#### 出力データ（Geminiの応答）

```json
{
  "mappings": [
    {
      "selector": "input[name='sei']",
      "value_key": "last_name",
      "confidence": 0.95,
      "reasoning": "labelに「姓」が含まれている。name属性も'sei'で姓を意味する。placeholderは'山田'で姓の例。"
    },
    {
      "selector": "input[name='mei']",
      "value_key": "first_name",
      "confidence": 0.95,
      "reasoning": "labelに「名」が含まれている。name属性も'mei'で名を意味する。placeholderは'太郎'で名の例。"
    },
    {
      "selector": "input[name='sei_kana']",
      "value_key": "last_name_kana",
      "confidence": 0.90,
      "reasoning": "labelに「フリガナ（姓）」とある。name属性はsei_kanaでカタカナの姓を意味する。"
    },
    {
      "selector": "input[name='mei_kana']",
      "value_key": "first_name_kana",
      "confidence": 0.90,
      "reasoning": "labelに「フリガナ（名）」とある。name属性はmei_kanaでカタカナの名を意味する。"
    },
    {
      "selector": "input[name='email']",
      "value_key": "email",
      "confidence": 1.0,
      "reasoning": "type='email'、labelに「メールアドレス」と明記。非常に明確。"
    },
    {
      "selector": "input[name='tel1']",
      "value_key": "phone1",
      "confidence": 0.90,
      "reasoning": "type='tel'、labelに「電話番号」、placeholder='090'で携帯番号の市外局番。3連続のtelフィールドの1番目。"
    },
    {
      "selector": "input[name='tel2']",
      "value_key": "phone2",
      "confidence": 0.90,
      "reasoning": "type='tel'、placeholder='1234'で電話番号の中間部分。tel1の直後のフィールド。"
    },
    {
      "selector": "input[name='tel3']",
      "value_key": "phone3",
      "confidence": 0.90,
      "reasoning": "type='tel'、placeholder='5678'で電話番号の末尾部分。tel2の直後のフィールド。"
    },
    {
      "selector": "input[name='company']",
      "value_key": "company",
      "confidence": 0.95,
      "reasoning": "labelに「会社名」と明記。name属性も'company'で明確。"
    }
  ],
  "unmapped_fields": [
    {
      "selector": "textarea[name='message']",
      "reason": "お問い合わせ内容は案件データから自動生成するため、マッピング不要"
    }
  ],
  "missing_data": []
}
```
**推定トークン数**: 約1,200トークン

#### コスト計算

```
入力トークン: 1,500 tokens
  → コスト: 1.5 × $0.00001875 = $0.000028125

出力トークン: 1,200 tokens
  → コスト: 1.2 × $0.000075 = $0.000090

合計: $0.000118 ≈ 0.012円（1円=85円換算）
```

---

### シナリオ2: 大規模フォーム（30フィールド）

#### 入力データ推定

```
フォーム構造: 2,000トークン（30フィールド）
利用可能データ: 800トークン（50+フィールド）
プロンプト: 500トークン
───────────────────────
合計: 3,300トークン
```

#### 出力データ推定

```
マッピング結果: 2,500トークン（30フィールド分の詳細reasoning）
```

#### コスト計算

```
入力: 3,300 × $0.00001875 = $0.000062
出力: 2,500 × $0.000075 = $0.000188
───────────────────────────────────
合計: $0.00025 ≈ 0.021円
```

---

### シナリオ3: シンプルフォーム（5フィールド）

#### 入力データ推定

```
フォーム構造: 300トークン（5フィールド）
利用可能データ: 400トークン
プロンプト: 500トークン
───────────────────────
合計: 1,200トークン
```

#### 出力データ推定

```
マッピング結果: 600トークン（5フィールド分）
```

#### コスト計算

```
入力: 1,200 × $0.00001875 = $0.000023
出力: 600 × $0.000075 = $0.000045
───────────────────────────────────
合計: $0.000068 ≈ 0.006円
```

---

## 📊 コストまとめ

| フォームタイプ | フィールド数 | 入力トークン | 出力トークン | コスト（USD） | コスト（円） |
|----------------|--------------|--------------|--------------|---------------|--------------|
| **シンプル** | 5 | 1,200 | 600 | $0.000068 | 0.006円 |
| **標準** | 10 | 1,500 | 1,200 | $0.000118 | 0.010円 |
| **大規模** | 30 | 3,300 | 2,500 | $0.000250 | 0.021円 |

**平均**: **約0.01円/フォーム**

---

## 💰 実運用コスト試算

### ケース1: 月100社 × 各1回送信

```
標準フォーム × 100回 = $0.000118 × 100 = $0.012 ≈ 1円/月
```

### ケース2: 月100社 × 各10回送信（同じフォームに複数案件）

**初回: AIマッピング**
```
100社 × $0.000118 = $0.012 ≈ 1円
```

**2回目以降: キャッシュ利用（静的マッピング化）**
```
900回 × $0 = 無料
```

**合計**: **約1円/月**

### ケース3: 月1000社（大規模運用）

**初回のみAI（その後は学習済みマッピング使用）**
```
1,000社 × $0.000118 = $0.118 ≈ 10円/月
```

---

## 🚀 コスト最適化戦略

### 1. プロンプトキャッシング（24時間有効）

同じプロンプト構造を24時間以内に再利用する場合、入力トークンコストが1/4に削減。

**例: 同じ企業に10回送信（24時間以内）**
```
1回目: 入力1,500トークン × $0.00001875 = $0.000028
2～10回目: 入力1,500トークン × $0.00001875 / 4 = $0.000007（各回）
```

**合計コスト削減:**
```
通常: $0.000028 × 10 = $0.00028
キャッシング: $0.000028 + ($0.000007 × 9) = $0.000091
───────────────────────────────────────────────
削減額: $0.000189（67%削減）
```

### 2. 学習済みマッピングDB

1回AIマッピングが成功したら、learned_mappingsテーブルに保存。

**データ構造:**
```sql
CREATE TABLE learned_mappings (
    company_id INTEGER,
    form_structure JSONB,  -- DOMハッシュ値も保存
    mapping JSONB,         -- AIが生成したマッピング
    success_count INTEGER,
    last_verified TIMESTAMP
);
```

**動作:**
```python
if learned_mapping exists and success_count > 3:
    # 学習済みマッピングを使用（無料）
    return use_static_mapping(learned_mapping)
else:
    # AIマッピング実行（$0.0001）
    mapping = ai_generate_mapping()
    save_to_learned_mappings(mapping)
```

**コスト削減効果:**
```
1社目: $0.000118（AI）
2社目以降: $0（学習済み）
───────────────────────
100社運用: $0.000118（初回のみ）
```

### 3. バッチ処理

複数企業のフォームを1回のAPI呼び出しでまとめて解析。

**通常:**
```
10社 × $0.000118 = $0.00118
```

**バッチ処理:**
```json
{
  "forms": [
    {"company": "A社", "fields": [...]},
    {"company": "B社", "fields": [...]},
    ...
  ]
}
```
```
1回の呼び出し: $0.0003（30%削減）
```

---

## 📈 スケール時のコスト推定

### 年間1万社対応の場合

**シナリオ: 各社平均5回送信**

```
総フォーム解析回数: 10,000社
学習済み活用率: 95%（2回目以降は学習済み）

AIマッピング実行回数: 10,000 × 5% = 500回
学習済み使用回数: 10,000 × 95% = 9,500回（無料）

コスト: 500 × $0.000118 = $0.059 ≈ 5円/年
```

**月額換算: 0.4円/月**

---

## 🎯 他サービスとのコスト比較

### Gemini 2.5 Flash vs 他モデル

| モデル | 入力 (1K tokens) | 出力 (1K tokens) | 標準フォーム/回 |
|--------|------------------|------------------|-----------------|
| **Gemini 2.5 Flash** | $0.000019 | $0.000075 | **$0.000118** |
| GPT-4 Turbo | $0.01 | $0.03 | $0.051 |
| Claude 3.5 Sonnet | $0.003 | $0.015 | $0.023 |
| GPT-3.5 Turbo | $0.0005 | $0.0015 | $0.003 |

**結論: Gemini 2.5 Flashが最もコスパが高い**
- GPT-4比で**430倍安い**
- Claude 3.5比で**195倍安い**
- GPT-3.5比で**25倍安い**

---

## 💡 結論

### 1フォーム解析のコスト

```
最小: 0.006円（シンプルフォーム）
標準: 0.010円（10フィールド）← 最も一般的
最大: 0.021円（大規模フォーム）
```

### 実運用での実効コスト

```
月100社運用: 約1円/月（学習機能あり）
月1000社運用: 約10円/月（学習機能あり）
年間1万社: 約5円/年（95%は学習済み活用）
```

### 推奨事項

1. **Phase 1**: 静的マッピング（無料・高速）
2. **Phase 2**: AIマッピング（初回$0.0001）
3. **Phase 3**: 学習機能（2回目以降無料）

**ハイブリッド方式で、実効コストはほぼゼロ**

---

## 📝 補足: トークン数計算方法

### 日本語の場合

```
目安: 1文字 = 約2～3トークン

例:
"お問い合わせフォーム" (10文字) ≈ 20～30トークン
"電話番号を入力してください" (13文字) ≈ 26～39トークン
```

### JSON構造の場合

```
{
  "name": "山田",
  "email": "test@example.com"
}

推定: 約30トークン（記号・空白・キー・値を含む）
```

### 実際の測定方法

```python
import google.generativeai as genai

# トークン数をカウント
model = genai.GenerativeModel('gemini-2.5-flash')
result = model.count_tokens(prompt_text)
print(f"トークン数: {result.total_tokens}")
```

---

**更新日**: 2025年12月31日  
**料金基準**: [Google AI Pricing](https://ai.google.dev/pricing)
