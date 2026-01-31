# テストデータ運用フロー

## 📋 概要

このドキュメントでは、AI AutoFormにテストデータ（および本番データ）を投入するフローを説明します。

---

## 🔄 全体フロー

```
1. CSVで企業データをインポート
        ↓
2. 案件（Product）を登録
        ↓
3. タスクを一括生成
        ↓
4. フォームを一括分析（Phase 2-B）
        ↓
5. 自動実行 または 手動対応
```

---

## 📁 Step 1: 企業データのインポート

### CSVフォーマット

```csv
name,website_url,form_url,industry,google_place_id,description,employee_count,established_year,capital
```

| カラム | 必須 | 説明 | 例 |
|--------|------|------|-----|
| `name` | ✅ | 企業名 | 株式会社サンプル |
| `website_url` | - | 企業サイトURL | https://example.com |
| `form_url` | ✅推奨 | 問い合わせフォームURL | https://example.com/contact |
| `industry` | - | 業種 | IT・ソフトウェア |
| `google_place_id` | - | Google Place ID（重複判定用） | ChIJ... |
| `description` | - | 企業説明 | - |
| `employee_count` | - | 従業員数 | 50 |
| `established_year` | - | 設立年 | 2015 |
| `capital` | - | 資本金 | 10000000 |

### サンプルCSV

`data/sample_companies.csv` を参照してください。

### インポート方法

1. **管理画面**から: `admin-phase2a.html` → 「CSVインポート」タブ
2. **API**から:
   ```bash
   curl -X POST -F "file=@data/sample_companies.csv" \
     http://153.126.154.158:5001/api/simple/companies/import-csv
   ```

### 重複処理

- `google_place_id` または `name` が一致する場合は**更新**
- 一致しない場合は**新規作成**

---

## 📝 Step 2: 案件（Product）の登録

### 管理画面から

1. `admin-phase2a.html` → 「案件登録」タブ
2. 必要事項を入力:
   - 案件名（必須）
   - 送信者情報（名前、メール、会社名は必須）
   - メッセージテンプレート（オプション）

### API から

```bash
curl -X POST http://153.126.154.158:5001/api/simple/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "テスト案件",
    "description": "テスト用の案件です",
    "sender_name": "山田太郎",
    "sender_email": "yamada@example.com",
    "sender_company": "株式会社テスト",
    "sender_phone": "03-1234-5678",
    "message_template": "お世話になっております。\n貴社のサービスに興味があります。"
  }'
```

---

## 🚀 Step 3: タスク一括生成

### 管理画面から

1. `admin-phase2a.html` → 「タスク生成」タブ
2. 案件を選択
3. 対象企業を選択（全企業 or 個別選択）
4. 「タスク生成実行」ボタン

### API から

```bash
curl -X POST http://153.126.154.158:5001/api/simple/tasks/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 1,
    "company_ids": "all",
    "use_ai": true
  }'
```

---

## 🔍 Step 4: フォーム一括分析（Phase 2-B）

### 目的

各企業のフォームを分析し、reCAPTCHA有無を判定して自動実行/手動対応を振り分け

### 管理画面から

1. `admin-phase2a.html` → 「自動化」タブ
2. 「一括分析実行」ボタン

### API から

```bash
# 単一タスク分析
curl -X POST http://153.126.154.158:5001/api/simple/analyze-task/123

# 単一URL分析
curl -X POST http://153.126.154.158:5001/api/simple/analyze-form \
  -H "Content-Type: application/json" \
  -d '{"form_url": "https://example.com/contact"}'
```

### 結果

| recaptcha_type | automation_type | 対応 |
|----------------|-----------------|------|
| `none` | `auto` | 自動実行可能 |
| `v3` | `auto` | 自動実行可能 |
| `v2` | `manual` | 手動対応必要 |

---

## ⚡ Step 5: タスク実行

### 自動実行（reCAPTCHAなしのタスク）

**管理画面**:
1. 「自動化」タブ → 「自動実行開始」

**API**:
```bash
# 単一タスク自動実行
curl -X POST http://153.126.154.158:5001/api/simple/auto-execute/123

# 一括自動実行
curl -X POST http://153.126.154.158:5001/api/simple/auto-execute-batch/COMPANY_ID
```

### 手動実行（reCAPTCHA v2のタスク）

**ワーカーコンソール**:
1. `simple-console-v2.html` を開く
2. タスクを選択
3. 「自動入力」→ VNC画面でreCAPTCHA対応 → 送信

---

## 🧪 テスト用クイックスタート

### 1. サンプルデータをインポート

```bash
curl -X POST -F "file=@data/sample_companies.csv" \
  http://153.126.154.158:5001/api/simple/companies/import-csv
```

### 2. テスト案件を作成

```bash
curl -X POST http://153.126.154.158:5001/api/simple/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "テスト営業案件",
    "sender_name": "テスト担当",
    "sender_email": "test@example.com",
    "sender_company": "テスト株式会社",
    "message_template": "貴社のサービスに興味があります。詳細をお聞かせください。"
  }'
```

### 3. タスク生成

```bash
curl -X POST http://153.126.154.158:5001/api/simple/tasks/generate \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "company_ids": "all", "use_ai": false}'
```

### 4. 確認

```bash
# 企業数
curl -s http://153.126.154.158:5001/api/simple/companies | jq 'length'

# タスク数
curl -s http://153.126.154.158:5001/api/simple/tasks | jq 'length'
```

---

## 📊 本番運用時の注意点

1. **form_urlの必須化**: タスク実行には企業のform_urlが必須
2. **重複チェック**: google_place_idまたはnameで重複判定
3. **バックアップ**: 本番データ投入前にDBバックアップを推奨
4. **テスト環境**: 本番前に開発環境でテスト

---

## 📁 関連ファイル

- `data/sample_companies.csv` - サンプルCSV
- `admin-phase2a.html` - 管理コンソール
- `simple-console-v2.html` - ワーカーコンソール
- `backend/api/simple_api.py` - API実装

---

**最終更新**: 2026-01-27
