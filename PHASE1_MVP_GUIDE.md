# Phase 1 MVP - 完成ガイド

## 🎉 完成状況

Phase 1 MVPが完成しました！以下の機能が実装され、動作確認済みです。

### ✅ 実装済み機能

1. **シンプルな3テーブル構成のデータベース**
   - `simple_companies` - 企業マスター（5件のテストデータ）
   - `simple_products` - 商材マスター（2件のテストデータ）
   - `simple_tasks` - タスク（10件 = 5企業 × 2商材）

2. **シンプルなコンソールUI** (`simple-console.html`)
   - タスク一覧表示
   - タスク詳細表示
   - 統計情報（総数、未処理、完了、失敗）
   - リアルタイム更新（5秒ごと）

3. **4つのシンプルAPI**
   - `GET /api/simple/tasks` - タスク一覧取得
   - `GET /api/simple/tasks/:id` - 特定タスク取得
   - `POST /api/simple/tasks/:id/execute` - 自動入力実行
   - `POST /api/simple/tasks/:id/complete` - 完了マーク

4. **Playwright自動化機能**
   - フォームページを開く
   - フォーム要素を検出（複数のセレクタを試行）
   - データを自動入力（name, email, company, phone, message）
   - スクリーンショット撮影（full_page）
   - Chromium headlessモード

---

## 🚀 起動手順

### 1. PostgreSQLが起動しているか確認

```bash
docker ps | grep ai-autoform-db
```

起動していない場合：

```bash
docker start ai-autoform-db
```

### 2. データベースのセットアップ（初回のみ）

```bash
cd /workspaces/ai-auto-form
PYTHONPATH=/workspaces/ai-auto-form python backend/simple_migrate.py
```

出力例：
```
✅ Tables created successfully!
✅ Added 5 companies
✅ Added 2 products
✅ Added 10 tasks
```

### 3. Flaskサーバーを起動

```bash
cd /workspaces/ai-auto-form
FLASK_APP=backend.app FLASK_ENV=development python -m flask run --host=0.0.0.0 --port=5001
```

### 4. HTMLサーバーを起動

```bash
cd /workspaces/ai-auto-form
python -m http.server 8000
```

### 5. ブラウザで開く

- **コンソールUI**: http://localhost:8000/simple-console.html
- **API Health Check**: http://localhost:5001/api/health

---

## 📋 使い方

### 基本フロー

1. **タスクを選択**
   - 左側のタスク一覧から、未処理（pending）のタスクをクリック

2. **自動入力を実行**
   - 右側の詳細エリアで「🤖 自動入力実行」ボタンをクリック
   - Playwrightが自動的にフォームに入力してスクリーンショットを撮影
   - 処理完了後、ステータスが「処理中 (in_progress)」に変わり、スクリーンショットが表示される

3. **スクリーンショットを確認**
   - 自動入力された内容が正しいか確認
   - 問題があれば「🌐 フォームを開く」で手動修正

4. **送信完了をマーク**
   - 実際にフォームを送信したら「✅ 送信完了」ボタンをクリック
   - ステータスが「完了 (completed)」に変わる

---

## 🗂️ ファイル構成

### Phase 1 MVP専用ファイル

```
/workspaces/ai-auto-form/
├── simple-console.html           # シンプルコンソールUI
├── backend/
│   ├── simple_models.py          # 3テーブルのモデル定義
│   ├── simple_migrate.py         # データベース初期化＆シードデータ
│   └── api/
│       └── simple_api.py         # 4つのAPIエンドポイント
├── screenshots/                   # スクリーンショット保存先
└── PHASE1_MVP_GUIDE.md           # このファイル
```

### データベーステーブル

- **simple_companies** (企業マスター)
  - id, name, website_url, form_url, industry, created_at

- **simple_products** (商材マスター)
  - id, name, description, message_template, created_at

- **simple_tasks** (タスク)
  - id, company_id, product_id, status, form_data (JSON), screenshot_path, submitted, created_at, completed_at

---

## 🧪 テストデータ

### 企業（5件）

1. 株式会社サンプルA - IT・情報通信
2. 株式会社サンプルB - 製造業
3. 株式会社サンプルC - 小売業
4. 株式会社サンプルD - 金融・保険
5. 株式会社サンプルE - 不動産

### 商材（2件）

1. Webマーケティング支援サービス
2. 業務効率化SaaS

### タスク（10件）

5企業 × 2商材 = 10タスク（すべてpending状態で作成）

---

## 🔧 トラブルシューティング

### エラー: "Address already in use"

ポート5001または8000が使用中の場合：

```bash
# Flaskサーバーのポートをクリア
lsof -ti:5001 | xargs kill -9

# HTMLサーバーのポートをクリア
lsof -ti:8000 | xargs kill -9
```

### エラー: "Foreign key constraint violation"

データベースに古いデータが残っている場合：

```bash
docker exec ai-autoform-db psql -U postgres -d ai_autoform -c "DROP TABLE IF EXISTS simple_tasks, simple_products, simple_companies CASCADE;"
PYTHONPATH=/workspaces/ai-auto-form python backend/simple_migrate.py
```

### エラー: "Playwright not installed"

Playwrightが未インストールの場合：

```bash
pip install playwright
playwright install chromium
```

### APIが404を返す

Flaskサーバーが起動していない可能性：

```bash
# プロセス確認
ps aux | grep flask

# 再起動
FLASK_APP=backend.app FLASK_ENV=development python -m flask run --host=0.0.0.0 --port=5001
```

---

## 📊 APIエンドポイント詳細

### 1. タスク一覧取得

```bash
curl http://localhost:5001/api/simple/tasks
```

レスポンス例：
```json
[
  {
    "id": 1,
    "company_id": 1,
    "product_id": 1,
    "company": {
      "id": 1,
      "name": "株式会社サンプルA",
      "form_url": "https://example.com/contact"
    },
    "product": {
      "id": 1,
      "name": "Webマーケティング支援サービス"
    },
    "status": "pending",
    "form_data": {
      "name": "山田太郎",
      "email": "yamada@example.com",
      "company": "株式会社テスト",
      "phone": "03-1234-5678",
      "message": "..."
    },
    "screenshot_path": null,
    "submitted": false
  }
]
```

### 2. タスク実行

```bash
curl -X POST http://localhost:5001/api/simple/tasks/1/execute
```

成功時：
```json
{
  "success": true,
  "message": "Automation completed",
  "screenshot_path": "/screenshots/task_1_1234567890.png"
}
```

失敗時：
```json
{
  "error": "Automation failed: Timeout waiting for page load"
}
```

### 3. タスク完了

```bash
curl -X POST http://localhost:5001/api/simple/tasks/1/complete
```

成功時：
```json
{
  "success": true,
  "message": "Task marked as completed"
}
```

---

## 🎯 次のステップ（Phase 2）

Phase 1 MVPが正常に動作していることを確認したら、Phase 2に進みます。

### Phase 2の目標（2-3日）

1. **ワーカー管理機能**
   - 複数ワーカーの登録・管理
   - ワーカーごとのタスク割り当て
   - 進捗状況のリアルタイム監視

2. **バッチ処理機能**
   - 複数タスクの一括実行
   - エラーハンドリング＆リトライ
   - 実行ログの記録

3. **VNC統合（VPS環境）**
   - TigerVNCサーバーのセットアップ
   - noVNCブラウザビューアー
   - 自動化プロセスの可視化

---

## ⚠️ 重要な注意事項

### Codespaces環境の制約

- **VNC接続は動作しません**（WebSocketプロキシの制約）
- VNC機能のテストはVPS環境で行う必要があります
- Phase 1はheadlessモードなのでCodespacesで完全に動作します

### 既存の複雑な実装について

- `worker-console.html`、`admin-console.html`などは **Phase 2以降** で使用
- 現時点では `simple-console.html` のみを使用
- 既存の複雑なテーブル（workers, projects, targetsなど）は無視

### データベーステーブルの命名

- Phase 1のテーブルは全て `simple_*` プレフィックス
- 既存の複雑なスキーマと競合しないように設計されています
- 将来的に統合する場合は、マイグレーションスクリプトを作成

---

## 📚 関連ドキュメント

- [HANDOFF.md](HANDOFF.md) - VNC統合の技術仕様
- [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md) - さくらVPS デプロイガイド
- [DEVELOPMENT_SCHEDULE_V2.md](DEVELOPMENT_SCHEDULE_V2.md) - 3フェーズ開発計画

---

## ✅ 動作確認チェックリスト

Phase 1 MVPが正常に動作しているか確認：

- [ ] PostgreSQLコンテナが起動している
- [ ] データベースに10件のタスクがある
- [ ] Flaskサーバーが5001ポートで起動している
- [ ] HTMLサーバーが8000ポートで起動している
- [ ] `http://localhost:8000/simple-console.html` でUIが表示される
- [ ] タスク一覧が表示される（統計情報も正しい）
- [ ] タスクをクリックすると詳細が表示される
- [ ] 「🤖 自動入力実行」ボタンをクリックするとPlaywrightが実行される
- [ ] 実行後にスクリーンショットが表示される
- [ ] 「✅ 送信完了」ボタンでステータスが「完了」に変わる

全てチェックが付いたら、Phase 1 MVP完成です！🎉

---

**作成日**: 2025年12月20日  
**バージョン**: Phase 1 MVP  
**ステータス**: ✅ 完成・動作確認済み
