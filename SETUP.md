# AI AutoForm - Phase 2 セットアップガイド

## 🎯 Phase 2 で実装された機能

### ✅ 完了した実装

1. **Flask API サーバー** (`backend/app.py`)
   - RESTful API エンドポイント
   - CORS対応
   - JWT認証基盤
   - レート制限（DDoS対策）

2. **Gemini AI Service** (`backend/services/gemini_service.py`)
   - 企業Webサイト解析
   - パーソナライズメッセージ生成
   - 作業者向けInsight生成

3. **Playwright 自動化** (`backend/services/automation_service.py`)
   - フォーム自動入力
   - reCAPTCHA検出
   - Human-in-the-Loop対応

4. **データベーススキーマ** (`database/schema.sql`)
   - PostgreSQL完全設計
   - テーブル、インデックス、Trigger

---

## 🚀 セットアップ手順

### 1. 依存パッケージのインストール

```bash
# Python依存関係
pip install -r requirements.txt

# Playwrightブラウザ
playwright install chromium
```

### 2. 環境変数の設定

```bash
# .envファイルを作成
cp .env.example .env
```

`.env` を編集して、以下を設定：

```bash
# Google Gemini API Key（必須）
GEMINI_API_KEY=your-actual-api-key-here

# その他はデフォルトで動作します
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
```

**Gemini API Key の取得方法:**
1. https://makersuite.google.com/app/apikey にアクセス
2. "Create API Key" をクリック
3. 生成されたキーを `.env` に貼り付け

### 3. サーバー起動

#### **オプション A: バックエンドのみテスト**

```bash
# Flask APIサーバーを起動
python backend/app.py

# 別ターミナルでテスト
curl http://localhost:5000/api/health
```

#### **オプション B: フルスタック起動**

**ターミナル1: バックエンドAPI**
```bash
python backend/app.py
# -> http://localhost:5000
```

**ターミナル2: フロントエンド**
```bash
python -m http.server 8000
# -> http://localhost:8000/admin-console.html
```

---

## 🧪 機能テスト

### A. Gemini API テスト

```bash
# Gemini Serviceが動作するかテスト
python backend/services/gemini_service.py
```

**期待される出力:**
```
✅ GEMINI_API_KEY が設定されています
✅ GeminiService が正常に初期化されました
```

### B. Playwright 自動化テスト

```bash
# フォーム自動入力のテスト
python backend/services/automation_service.py
```

プロンプトが表示されたら、テスト用のフォームURLを入力：
```
例: https://www.google.com/search
```

ブラウザが自動で開き、フォーム入力が実行されます。

### C. APIエンドポイントテスト

```bash
# ヘルスチェック
curl http://localhost:5000/api/health

# 企業一覧取得
curl http://localhost:5000/api/companies

# 新規企業登録
curl -X POST http://localhost:5000/api/companies \
  -H "Content-Type: application/json" \
  -d '{"name": "テスト株式会社", "url": "https://example.com"}'
```

---

## 📁 プロジェクト構造

```
/workspaces/ai-auto-form/
├── admin-console.html         # 管理者UI
├── worker-console.html        # 作業者UI
├── js/
│   └── data-manager.js       # フロントエンドデータ管理
├── backend/
│   ├── app.py                # Flask APIサーバー
│   ├── routes/               # APIルート（今後追加）
│   ├── services/
│   │   ├── gemini_service.py    # Gemini AI連携
│   │   └── automation_service.py # Playwright自動化
│   └── models/               # データモデル（今後追加）
├── database/
│   └── schema.sql            # PostgreSQLスキーマ
├── config/                   # 設定ファイル
├── tests/                    # テストコード（今後追加）
├── requirements.txt          # Python依存関係
├── .env.example              # 環境変数テンプレート
└── README.md                 # メインドキュメント
```

---

## 🎓 次のステップ

### Phase 2.5: データベース統合（推奨）

1. **PostgreSQLのセットアップ**
   ```bash
   # Dockerを使う場合
   docker run -d \
     --name aiautoform-db \
     -e POSTGRES_DB=aiautoform \
     -e POSTGRES_USER=admin \
     -e POSTGRES_PASSWORD=password \
     -p 5432:5432 \
     postgres:15
   
   # スキーマ適用
   psql -h localhost -U admin -d aiautoform -f database/schema.sql
   ```

2. **SQLAlchemy モデル作成**
   - `backend/models/company.py`
   - `backend/models/project.py`
   - `backend/models/worker.py`

3. **API と DB 接続**
   - Flask-SQLAlchemy統合
   - CRUD操作の実装

### Phase 3: 本番デプロイ

1. Cloud Run / AWS ECS へのデプロイ
2. Cloud SQL / RDS セットアップ
3. CI/CD パイプライン構築
4. 監視・ログ設定

---

## ⚠️ トラブルシューティング

### `GEMINI_API_KEY is not set` エラー

```bash
# .envファイルが正しく読み込まれているか確認
cat .env | grep GEMINI_API_KEY

# 環境変数を直接セット
export GEMINI_API_KEY=your-key-here
```

### Playwright ブラウザが起動しない

```bash
# ブラウザを再インストール
playwright install --force chromium

# システム依存関係をインストール（Linux）
playwright install-deps chromium
```

### ポート競合エラー

```bash
# 既存のプロセスを確認
lsof -i :5000
lsof -i :8000

# プロセスを終了
kill -9 <PID>
```

---

## 📞 サポート

問題が発生した場合:

1. **ログを確認**
   - Flaskサーバーのコンソール出力
   - ブラウザの開発者ツール（F12）

2. **環境を確認**
   ```bash
   python --version  # 3.10以上推奨
   pip list | grep -E "(flask|gemini|playwright)"
   ```

3. **GitHub Issuesで報告**
   - https://github.com/shintarospec/ai-auto-form/issues

---

**Happy Coding! 🚀**
