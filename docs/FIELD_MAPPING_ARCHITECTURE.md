# フィールドマッピングアーキテクチャ

## 質問：フィールド分割はAIマッピングでも必要か？

### 結論：**YES - 分割フィールドは必須です**

---

## 🎯 なぜ分割フィールドが必要か

### ケース1: AIがフォーム構造を解析した結果

**対象フォーム（DeepBiz風）:**
```html
<form>
  <input name="tel1" placeholder="090">
  <input name="tel2" placeholder="1234">
  <input name="tel3" placeholder="5678">
</form>
```

**AIの解析結果:**
```json
{
  "fields": [
    {"selector": "input[name='tel1']", "value_key": "phone1", "type": "text"},
    {"selector": "input[name='tel2']", "value_key": "phone2", "type": "text"},
    {"selector": "input[name='tel3']", "value_key": "phone3", "type": "text"}
  ]
}
```

**必要なデータ:**
- `phone1`: "090"
- `phone2`: "1234"
- `phone3`: "5678"

**もし結合データ（"090-1234-5678"）しかない場合:**
```python
# 毎回split処理が必要になる
phone_parts = phone.split('-')  # ["090", "1234", "5678"]
# しかし "-" で分割できない電話番号もある
# "09012345678" の場合は？ → 分割ロジックが複雑化
```

### ケース2: 逆パターン（結合フィールド）

**対象フォーム:**
```html
<form>
  <input name="phone" placeholder="090-1234-5678">
</form>
```

**AIの解析結果:**
```json
{
  "fields": [
    {"selector": "input[name='phone']", "value_key": "phone", "type": "text"}
  ]
}
```

**必要なデータ:**
- `phone`: "090-1234-5678"

**もし分割データ（phone1/2/3）しかない場合:**
```python
# 結合処理が必要
phone = f"{phone1}-{phone2}-{phone3}"
# しかしセパレータは "-" とは限らない
# "090.1234.5678" や "09012345678" のパターンも
```

---

## 🧠 自動マッピングの具体的な仕組み

### アーキテクチャ全体図

```
┌─────────────────────────────────────────────────────────────┐
│                      Product Database                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 分割データ（粒度が細かい）                           │   │
│  │ - sender_phone_1: "090"                             │   │
│  │ - sender_phone_2: "1234"                            │   │
│  │ - sender_phone_3: "5678"                            │   │
│  │ - sender_last_name: "山田"                          │   │
│  │ - sender_first_name: "太郎"                         │   │
│  │ - sender_zipcode_1: "106"                           │   │
│  │ - sender_zipcode_2: "0032"                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│        prepare_form_data_from_product()                      │
│                  ↓                                           │
│  両形式を自動生成（50+フィールド）                           │
│  ┌──────────────────┬──────────────────────────┐          │
│  │ 分割形式          │ 結合形式                  │          │
│  ├──────────────────┼──────────────────────────┤          │
│  │ phone1: "090"    │ phone: "090-1234-5678"   │          │
│  │ phone2: "1234"   │ name: "山田 太郎"         │          │
│  │ phone3: "5678"   │ zipcode: "106-0032"      │          │
│  │ last_name: "山田" │ full_address: "東京都..." │          │
│  │ first_name: "太郎"│                          │          │
│  └──────────────────┴──────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   フォームマッピング                          │
│         【静的マッピング】＋【AIマッピング】                  │
└─────────────────────────────────────────────────────────────┘
                    ↓                   ↓
      ┌─────────────────────┐  ┌──────────────────────┐
      │   静的マッピング      │  │    AIマッピング       │
      │   (Phase 1)          │  │    (Phase 2)         │
      └─────────────────────┘  └──────────────────────┘
```

---

## 📋 Phase別実装詳細

### Phase 1: 静的マッピング（現在実装中）

**仕組み:**
企業ごとに事前定義されたセレクタパターン

**データ構造（simple_companies）:**
```python
company = {
    "id": 1,
    "name": "DeepBiz株式会社",
    "contact_url": "https://deepbiz.co.jp/contact",
    "form_config": {
        "selectors": {
            # 結合形式（自社サイトに多い）
            "name": "input[name='name']",
            "email": "input[name='email']",
            "phone": "input[name='tel']",
            
            # 分割形式（DeepBizに多い）
            "phone1": "input[name='tel1']",
            "phone2": "input[name='tel2']",
            "phone3": "input[name='tel3']",
            "last_name": "input[name='sei']",
            "first_name": "input[name='mei']"
        },
        "priority": "split"  # 分割を優先的に試す
    }
}
```

**automation_service.pyの処理:**
```python
def fill_form(self, page: Page, form_data: Dict, company_config: Dict):
    """
    1. 企業のform_configを取得
    2. priority設定に従って試行順序を決定
    3. セレクタに従ってフィールドに入力
    """
    config = company_config.get('form_config', {})
    selectors = config.get('selectors', {})
    priority = config.get('priority', 'combined')  # デフォルトは結合
    
    # 分割優先の場合
    if priority == 'split':
        # まず分割フィールドを試す
        if self._try_fill_split_fields(page, form_data, selectors):
            return True
        # 失敗したら結合フィールドを試す
        if self._try_fill_combined_fields(page, form_data, selectors):
            return True
    else:
        # 結合優先の場合（逆順）
        if self._try_fill_combined_fields(page, form_data, selectors):
            return True
        if self._try_fill_split_fields(page, form_data, selectors):
            return True
    
    raise Exception("フィールド入力に失敗しました")
```

**メリット:**
- ✅ 高速（API呼び出し不要）
- ✅ 確実性が高い（事前検証済み）
- ✅ コスト0（Gemini API不使用）

**デメリット:**
- ❌ 企業ごとに手動設定が必要
- ❌ サイト構造変更時に再設定必要

---

### Phase 2: AIマッピング（次期実装）

**仕組み:**
Gemini APIでページのDOM構造を解析し、動的にマッピング

#### Step 1: DOM構造の取得

**automation_service.py:**
```python
def analyze_form_structure(self, page: Page) -> Dict:
    """
    ページのフォーム構造をJavaScriptで解析
    """
    form_structure = page.evaluate("""
        () => {
            const forms = Array.from(document.querySelectorAll('form'));
            return forms.map(form => {
                const fields = Array.from(form.querySelectorAll('input, select, textarea'));
                return {
                    action: form.action,
                    method: form.method,
                    fields: fields.map(field => ({
                        tag: field.tagName.toLowerCase(),
                        type: field.type,
                        name: field.name,
                        id: field.id,
                        placeholder: field.placeholder,
                        label: field.labels?.[0]?.textContent || '',
                        required: field.required
                    }))
                };
            });
        }
    """)
    return form_structure
```

**取得例（DeepBizのフォーム）:**
```json
{
  "action": "https://deepbiz.co.jp/contact/submit",
  "method": "POST",
  "fields": [
    {
      "tag": "input",
      "type": "text",
      "name": "sei",
      "placeholder": "山田",
      "label": "お名前（姓）",
      "required": true
    },
    {
      "tag": "input",
      "type": "text",
      "name": "mei",
      "placeholder": "太郎",
      "label": "お名前（名）",
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
    }
  ]
}
```

#### Step 2: Gemini APIでマッピング生成

**gemini_service.py（新機能）:**
```python
def generate_field_mapping(self, form_structure: Dict, available_data: Dict) -> Dict:
    """
    フォーム構造と利用可能なデータからマッピングを生成
    
    Args:
        form_structure: analyze_form_structure()の結果
        available_data: prepare_form_data_from_product()の結果
    
    Returns:
        マッピング情報
    """
    prompt = f"""
あなたはフォーム自動入力の専門家です。

【タスク】
以下のフォーム構造に対して、利用可能なデータをマッピングしてください。

【フォーム構造】
{json.dumps(form_structure, ensure_ascii=False, indent=2)}

【利用可能なデータ】
{json.dumps(available_data, ensure_ascii=False, indent=2)}

【出力形式】
以下のJSON形式で出力してください:
{{
  "mappings": [
    {{
      "selector": "input[name='sei']",
      "value_key": "last_name",
      "confidence": 0.95,
      "reasoning": "labelに「姓」が含まれる + nameが'sei'"
    }},
    {{
      "selector": "input[name='mei']",
      "value_key": "first_name",
      "confidence": 0.95,
      "reasoning": "labelに「名」が含まれる + nameが'mei'"
    }},
    {{
      "selector": "input[name='tel1']",
      "value_key": "phone1",
      "confidence": 0.90,
      "reasoning": "type='tel' + placeholder='090' + 3連続フィールド"
    }},
    {{
      "selector": "input[name='tel2']",
      "value_key": "phone2",
      "confidence": 0.90,
      "reasoning": "type='tel' + placeholder='1234' + tel1の次"
    }},
    {{
      "selector": "input[name='tel3']",
      "value_key": "phone3",
      "confidence": 0.90,
      "reasoning": "type='tel' + placeholder='5678' + tel2の次"
    }}
  ],
  "unmapped_fields": [
    {{
      "selector": "textarea[name='message']",
      "reason": "利用可能なデータに対応するものがない"
    }}
  ],
  "missing_data": [
    {{
      "field": "company_name",
      "reason": "フォームに会社名フィールドがあるがデータがない"
    }}
  ]
}}

【重要なルール】
1. labelのテキストを最優先で考慮する
2. name属性のセマンティクスを考慮する（sei→姓、mei→名）
3. type属性を考慮する（tel→電話、email→メール）
4. placeholderから分割フィールドかを判断する
5. confidence（信頼度）を0.0～1.0で付与する
6. 不明な場合は無理にマッピングせず、unmapped_fieldsに記載する
"""
    
    response = self.model.generate_content(prompt)
    return json.loads(response.text)
```

**Geminiの出力例:**
```json
{
  "mappings": [
    {
      "selector": "input[name='sei']",
      "value_key": "last_name",
      "confidence": 0.95,
      "reasoning": "labelに「姓」が含まれる"
    },
    {
      "selector": "input[name='tel1']",
      "value_key": "phone1",
      "confidence": 0.90,
      "reasoning": "3連続のtelフィールド、placeholder='090'"
    }
  ],
  "unmapped_fields": [],
  "missing_data": []
}
```

#### Step 3: マッピング適用＋検証

**automation_service.py:**
```python
def fill_form_with_ai_mapping(self, page: Page, form_data: Dict, company_url: str):
    """
    AIマッピングを使用したフォーム入力
    """
    # 1. フォーム構造解析
    form_structure = self.analyze_form_structure(page)
    
    # 2. Gemini APIでマッピング生成
    from backend.services.gemini_service import GeminiService
    gemini = GeminiService()
    mapping = gemini.generate_field_mapping(form_structure, form_data)
    
    # 3. 信頼度の高いマッピングから入力
    success_count = 0
    for m in sorted(mapping['mappings'], key=lambda x: x['confidence'], reverse=True):
        if m['confidence'] < 0.8:
            print(f"⚠️ 信頼度が低いためスキップ: {m['selector']} (confidence={m['confidence']})")
            continue
        
        selector = m['selector']
        value_key = m['value_key']
        value = form_data.get(value_key)
        
        if not value:
            print(f"⚠️ データが見つかりません: {value_key}")
            continue
        
        try:
            page.fill(selector, value)
            print(f"✅ {selector} ← {value_key}='{value}' (confidence={m['confidence']})")
            success_count += 1
        except Exception as e:
            print(f"❌ 入力失敗: {selector} - {e}")
    
    # 4. 未マッピングフィールドをログ出力
    if mapping['unmapped_fields']:
        print(f"⚠️ 未マッピングフィールド: {len(mapping['unmapped_fields'])}件")
        for field in mapping['unmapped_fields']:
            print(f"  - {field['selector']}: {field['reason']}")
    
    # 5. マッピングをDBに保存（学習データとして）
    self._save_mapping_to_db(company_url, form_structure, mapping)
    
    return success_count
```

**メリット:**
- ✅ 未知のフォームにも対応可能
- ✅ サイト構造変更に自動対応
- ✅ 設定不要（初回から動作）

**デメリット:**
- ❌ Gemini API呼び出しコスト（約$0.01/回）
- ❌ レスポンスタイム増加（+2～3秒）
- ❌ 信頼度が100%ではない

---

### Phase 3: ハイブリッド方式（推奨）

**静的マッピング（キャッシュ）+ AIマッピング（フォールバック）**

```python
def smart_fill_form(self, page: Page, form_data: Dict, company: Dict):
    """
    ハイブリッドマッピングによるフォーム入力
    """
    company_id = company['id']
    company_url = company['contact_url']
    
    # 1. 静的マッピングの確認
    static_mapping = company.get('form_config', {})
    
    if static_mapping and static_mapping.get('verified', False):
        # 検証済みの静的マッピングが存在
        print(f"✅ 静的マッピングを使用: {company['name']}")
        try:
            return self.fill_form_static(page, form_data, static_mapping)
        except Exception as e:
            print(f"⚠️ 静的マッピング失敗: {e}")
            # AIマッピングにフォールバック
    
    # 2. 学習済みマッピングの確認
    learned_mapping = self._get_learned_mapping(company_id, company_url)
    
    if learned_mapping and learned_mapping.get('success_rate', 0) > 0.9:
        # 成功率90%以上の学習済みマッピング
        print(f"✅ 学習済みマッピングを使用: 成功率{learned_mapping['success_rate']*100}%")
        try:
            return self.fill_form_learned(page, form_data, learned_mapping)
        except Exception as e:
            print(f"⚠️ 学習済みマッピング失敗: {e}")
    
    # 3. AIマッピング（初回 or フォールバック）
    print(f"🤖 AIマッピングを実行: {company['name']}")
    result = self.fill_form_with_ai_mapping(page, form_data, company_url)
    
    # 4. 成功したマッピングを学習データとして保存
    if result['success_count'] > 0:
        self._update_learned_mapping(company_id, company_url, result['mapping'])
    
    return result
```

**データベース構造（学習用）:**
```sql
CREATE TABLE learned_mappings (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES simple_companies(id),
    company_url TEXT NOT NULL,
    form_structure JSONB,  -- analyze_form_structure()の結果
    mapping JSONB,         -- Geminiが生成したマッピング
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    success_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN (success_count + failure_count) > 0
             THEN success_count::float / (success_count + failure_count)
             ELSE 0 END
    ) STORED,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🎯 なぜ分割フィールドが必要か（再確認）

### データの粒度と柔軟性

```
粒度：細かい ────────────────────► 粗い
      phone1, phone2, phone3 ────► phone
      
変換：容易   ◄──────────────────── 困難
      結合は簡単                     分割は困難
      (phone1+phone2+phone3)        (規則が不明)
```

**例：電話番号の分割が困難な理由**

```python
# 結合データのみの場合
phone = "09012345678"  # セパレータなし
# どう分割する？
# - "090" / "1234" / "5678" ？
# - "090" / "123" / "45678" ？
# - 市外局番の桁数が不明（東京は03、携帯は090/080/070）

phone = "03-3333-3333"  # セパレータあり
# split('-') で分割できるが...
phone = "03.3333.3333"  # セパレータが異なる
phone = "0333333333"    # セパレータなし
# 汎用的な処理が困難
```

**分割データがあれば:**
```python
# 常に正確に結合可能
phone = f"{phone1}-{phone2}-{phone3}"  # 090-1234-5678
phone = f"{phone1}{phone2}{phone3}"    # 09012345678
phone = f"{phone1}.{phone2}.{phone3}"  # 090.1234.5678
# どんなフォーマットにも対応できる
```

---

## 📊 コスト・パフォーマンス比較

| 方式 | 初回設定コスト | 1回あたりコスト | 精度 | 保守性 | 推奨用途 |
|------|----------------|-----------------|------|--------|----------|
| **静的マッピング** | 高（手動設定） | 無料 | 100% | 低（変更時再設定） | 頻繁に使う企業 |
| **AIマッピング** | 無料 | $0.01～0.02 | 85～95% | 高（自動適応） | 初回・未知企業 |
| **ハイブリッド** | 無料 | $0.01（初回のみ） | 95～100% | 高（自動学習） | **推奨** |

---

## 🚀 実装ロードマップ

### Phase 1（現在）: 基礎実装
- ✅ 分割フィールド対応（33フィールド追加）
- ✅ prepare_form_data_from_product()実装
- ⬜ 静的マッピング拡張（simple_companiesにform_config追加）

### Phase 2（次期）: AIマッピング
- ⬜ analyze_form_structure()実装
- ⬜ gemini_service.generate_field_mapping()実装
- ⬜ fill_form_with_ai_mapping()実装

### Phase 3（将来）: 学習機能
- ⬜ learned_mappingsテーブル作成
- ⬜ smart_fill_form()実装（ハイブリッド）
- ⬜ 成功率ベースの自動最適化

---

## 💡 結論

**Q: フィールドを細かく分けておくことは、AIマッピングでも必要か？**

**A: YES - 必須です**

理由：
1. **AIの解析結果を活用できる**
   - AIが「3つに分かれた電話番号フィールド」と判断しても、分割データがないと対応不可
   
2. **変換の方向性**
   - 分割 → 結合：簡単（join, format）
   - 結合 → 分割：困難（規則が不明、国際電話、市外局番の桁数）
   
3. **フォーマットの柔軟性**
   - 分割データがあれば、どんなセパレータにも対応可能
   - "090-1234-5678" / "09012345678" / "090.1234.5678" 全て生成可能
   
4. **AI精度の向上**
   - AIがlabel="姓"とlabel="名"を個別認識できる
   - 分割データがあれば、AIの判断を直接適用可能

**prepare_form_data_from_product()の設計は正解**
- 分割データを保存
- 使用時に両形式を自動生成
- AIマッピングが「どちらの形式が必要か」を判断
- 該当するvalue_keyからデータを取得
