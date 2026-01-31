# テストデータ提供フロー

**最終更新**: 2026-01-27  
**対象**: 開発者・運用担当者

---

## 📋 概要

AI AutoFormでは、企業データをCSVファイルでインポートできます。このガイドでは、テスト環境・本番環境でのデータ提供フローを説明します。

---

## 🎯 データ提供の流れ

### 1. CSVファイルの準備

#### CSVフォーマット

```csv
name,website_url,form_url,industry,google_place_id,description,employee_count,established_year,capital
```

#### 各フィールドの説明

| フィールド名 | 必須 | 説明 | 例 |
|------------|------|------|-----|
| `name` | ✅ | 企業名 | 株式会社サンプル |
| `website_url` | | 企業Webサイト | https://example.com |
| `form_url` | | 問い合わせフォームURL | https://example.com/contact |
| `industry` | | 業界 | IT・ソフトウェア |
| `google_place_id` | | Google Place ID（重複チェックに使用） | ChIJN1t_tDeuEmsRUsoyG83frY4 |
| `description` | | 企業説明 | 中小企業向けクラウドサービス |
| `employee_count` | | 従業員数 | 50 |
| `established_year` | | 設立年 | 2010 |
| `capital` | | 資本金（円） | 10000000 |

#### サンプルCSV

プロジェクトルートの [`sample_data/companies_template.csv`](../sample_data/companies_template.csv) を参照してください。

---

### 2. CSVインポート方法

#### 方法1: 管理コンソールUI（推奨）

1. **管理コンソールにアクセス**
   - 本番: http://153.126.154.158:8000/admin-phase2a.html
   - ローカル: http://localhost:8000/admin-phase2a.html

2. **「CSV インポート」タブを開く**

3. **CSVファイルを選択**
   - 「CSVファイル」欄でファイルを選択

4. **「CSVインポート」ボタンをクリック**
   - インポート結果が表示されます
   - 新規作成数、更新数、スキップ数が表示されます

#### 方法2: API直接呼び出し（開発用）

```bash
# ローカル環境
curl -X POST http://localhost:5001/api/simple/companies/import-csv \
  -F "file=@sample_data/companies_template.csv"

# 本番環境（VPS）
curl -X POST http://153.126.154.158:5001/api/simple/companies/import-csv \
  -F "file=@sample_data/companies_template.csv"
```

**レスポンス例:**
```json
{
  "success": true,
  "created": 3,
  "updated": 0,
  "skipped": 0,
  "errors": [],
  "message": "インポート完了: 新規3件、更新0件、スキップ0件"
}
```

---

### 3. インポート後の確認

#### 管理コンソールで確認

1. 「企業管理」タブを開く
2. インポートした企業が表示されているか確認

#### API で確認

```bash
# 企業一覧を取得
curl http://localhost:5001/api/simple/companies | jq '.[] | {id, name, form_url}'

# 本番環境
curl http://153.126.154.158:5001/api/simple/companies | jq '.[] | {id, name, form_url}'
```

---

## 🔄 更新・重複処理

### 重複チェックロジック

CSVインポートAPIは以下の順序で既存企業をチェックします：

1. **google_place_id** が一致する企業を検索
2. 見つからない場合、**企業名（name）** が一致する企業を検索
3. 既存企業が見つかった場合 → **更新**
4. 見つからない場合 → **新規作成**

### 更新時の挙動

- CSVに値が設定されているフィールドのみ更新されます
- 空欄のフィールドは既存の値が保持されます

**例:**
```csv
name,website_url,form_url,industry,google_place_id
株式会社サンプル1,https://new-url.com,,,ChIJN1t_tDeuEmsRUsoyG83frY4
```

この場合、`website_url`のみ更新され、`form_url`、`industry`は既存の値が保持されます。

---

## 📊 テストデータのパターン

### パターン1: 基本テスト（3社）

```csv
name,website_url,form_url,industry
株式会社テスト1,https://test1.com,https://test1.com/contact,IT
株式会社テスト2,https://test2.com,https://test2.com/inquiry,製造業
株式会社テスト3,https://test3.com,https://test3.com/form,小売業
```

### パターン2: Google Place ID付き（重複チェック用）

```csv
name,website_url,form_url,google_place_id
株式会社A,https://a.com,https://a.com/contact,ChIJN1t_tDeuEmsRUsoyG83frY4
株式会社B,https://b.com,https://b.com/inquiry,ChIJXxYzN8KuEmsR_WkEKq_6Xq0
```

### パターン3: 詳細情報付き（フル項目）

```csv
name,website_url,form_url,industry,google_place_id,description,employee_count,established_year,capital
株式会社フル,https://full.com,https://full.com/contact,IT・ソフトウェア,ChIJN1t_tDeuEmsRUsoyG83frY4,クラウドサービス提供,100,2010,50000000
```

---

## 🚀 本番環境でのデータ提供フロー

### ステップ1: データ準備

1. **企業リストをExcel/スプレッドシートで作成**
2. **必須項目を入力**
   - 企業名（name）
   - フォームURL（form_url）
3. **CSV形式で保存**
   - 文字コード: UTF-8
   - BOM付きUTF-8も対応

### ステップ2: VPSへのアップロード

**方法A: SCPでアップロード（推奨）**

```bash
# ローカルPCからVPSへCSVをアップロード
scp companies_data.csv ubuntu@153.126.154.158:/tmp/

# VPS上でインポート実行
ssh ubuntu@153.126.154.158
curl -X POST http://localhost:5001/api/simple/companies/import-csv \
  -F "file=@/tmp/companies_data.csv"
```

**方法B: 管理コンソール経由（簡単）**

1. ブラウザでVPSの管理コンソールを開く: http://153.126.154.158:8000/admin-phase2a.html
2. 「CSV インポート」タブを開く
3. ローカルのCSVファイルを選択してアップロード

### ステップ3: タスク生成

1. 管理コンソールの「タスク生成」タブを開く
2. 案件を選択
3. 対象企業を選択（「全企業」または個別選択）
4. 「タスク生成実行」ボタンをクリック

---

## ⚠️ 注意事項

### CSVファイル作成時の注意

1. **文字コード**: UTF-8（BOM付きでも可）
2. **改行コード**: LF推奨（CRLFも対応）
3. **カンマ区切り**: 値にカンマが含まれる場合はダブルクォートで囲む
4. **ヘッダー行**: 必須（1行目にフィールド名）

### インポート時の注意

1. **重複チェック**: google_place_id または 企業名で重複チェック
2. **エラー処理**: エラー行はスキップされ、他の行は処理継続
3. **トランザクション**: 全行処理後にコミット

### トラブルシューティング

#### エラー: 「企業名が空です」

**原因**: name列が空、または列名が間違っている

**対処**: CSVのヘッダー行を確認し、`name`列に値が入っているか確認

#### エラー: 「CSVファイルのみ対応しています」

**原因**: ファイル拡張子が`.csv`ではない

**対処**: ファイルを`.csv`形式で保存し直す

#### エラー: 「ファイルが選択されていません」

**原因**: ファイルが正しくアップロードされていない

**対処**: 再度ファイルを選択してアップロード

---

## 📚 関連ドキュメント

- [API仕様](./API.md) - `/api/simple/companies/import-csv`エンドポイントの詳細
- [CURRENT_STATE.md](./CURRENT_STATE.md) - システム全体の現状
- [MVP_SPEC.md](./MVP_SPEC.md) - 機能仕様

---

## 🔧 開発者向け情報

### APIエンドポイント

```
POST /api/simple/companies/import-csv
Content-Type: multipart/form-data

Parameters:
  file: CSVファイル（multipart/form-data）

Response:
{
  "success": true,
  "created": 10,
  "updated": 5,
  "skipped": 2,
  "errors": ["行3: 企業名が空です"],
  "message": "インポート完了: 新規10件、更新5件、スキップ2件"
}
```

### 実装ファイル

- **APIロジック**: [`backend/api/simple_api.py`](../backend/api/simple_api.py) - `import_companies_csv()`
- **データモデル**: [`backend/simple_models.py`](../backend/simple_models.py) - `Company`クラス
- **フロントエンド**: [`admin-phase2a.html`](../admin-phase2a.html) - CSVインポートタブ

---

**更新履歴**:
- 2026-01-27: 初版作成（CSVインポート機能のドキュメント化）
