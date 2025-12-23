# AI AutoForm - 新チャット引き継ぎ文書 📋

**最終更新**: 2025年12月21日  
**プロジェクト状態**: Phase 1 MVP完成、VPS移行準備中

---

## 🎯 プロジェクト概要

**ハイブリッド自動化システム**: Playwrightでフォーム自動入力 + 作業者が目視確認してreCAPTCHA対応＆送信ボタンクリック

**2つの主要機能**:
1. **企業DB**: データ収集・管理・AI解析
2. **ワーカーフォーム送信**: タスク振り分け・VNC統合・成果管理

**アーキテクチャ戦略**: モノリシック（Phase 2）→ モジュラーモノリス（Phase 3）→ マイクロサービス（Phase 4）
- 詳細は [PROJECT_SPEC.md](PROJECT_SPEC.md) の「アーキテクチャ戦略」セクション参照

---

## ✅ Phase 1 MVP完成状況

### 1. データベース層（完成✅）
- **PostgreSQL 16**: Docker稼働中（`ai-autoform-db`）
- **テーブル**: 3テーブル（simple_companies, simple_products, simple_tasks）
- **テストデータ**: 投入済み
  - 企業5社（株式会社テストカンパニー等）
  - 商品2件（Webサイト制作、SEOコンサルティング）
  - タスク10件
- **確認コマンド**: 
  ```bash
  docker exec -it ai-autoform-db psql -U postgres -d ai_autoform -c "SELECT * FROM simple_companies;"
  ```

### 2. API層（動作中✅）
- **Flask 3.0.0**: ポート5001で稼働中
- **起動コマンド**:
  ```bash
  cd /workspaces/ai-auto-form
  lsof -ti:5001 | xargs kill -9 2>/dev/null
  FLASK_APP=backend.app FLASK_ENV=development python -m flask run --host=0.0.0.0 --port=5001
  ```
- **4つのエンドポイント**:
  - `GET /api/simple/tasks` - タスク一覧
  - `GET /api/simple/tasks/<id>` - タスク詳細
  - `POST /api/simple/tasks/<id>/execute` - 自動入力実行
  - `POST /api/simple/tasks/<id>/complete` - 完了マーク
- **動作確認**:
  ```bash
  curl http://localhost:5001/api/simple/tasks
  ```

### 3. フロントエンド層（動作中✅）
- **Simple Console**: `simple-console.html`（Phase 1専用UI）
- **起動中のHTTPサーバー**: ポート8000
  ```bash
  cd /workspaces/ai-auto-form
  lsof -ti:8000 | xargs kill -9 2>/dev/null
  nohup python -m http.server 8000 > http-server.log 2>&1 &
  ```
- **アクセス**: Codespacesのポート8000を「Public」に設定後、`simple-console.html`を開く
- **機能**: 統計情報、タスク一覧、詳細表示、自動入力実行、完了マーク

### 4. Playwright層（動作中✅）
- **ファイル**: `backend/services/automation_service.py`
- **現在の設定**: `headless=True`（画面非表示モード）
- **動作確認済み**: test-contact-form.htmlに自動入力、スクリーンショット保存

---

## 🔄 環境の起動手順

### 1回目（コンテナ起動）:
```bash
cd /workspaces/ai-auto-form
docker compose up -d
sleep 5
docker exec -it ai-autoform-db psql -U postgres -d ai_autoform -c "\dt"
```

### 2回目以降（サービス起動）:
```bash
# PostgreSQL確認
docker ps -a | grep ai-autoform-db

# Flask API起動
cd /workspaces/ai-auto-form
lsof -ti:5001 | xargs kill -9 2>/dev/null
FLASK_APP=backend.app FLASK_ENV=development python -m flask run --host=0.0.0.0 --port=5001

# HTMLサーバー起動（別ターミナル）
cd /workspaces/ai-auto-form
lsof -ti:8000 | xargs kill -9 2>/dev/null
nohup python -m http.server 8000 > http-server.log 2>&1 &

# 動作確認
curl http://localhost:5001/api/simple/tasks | jq
```

---

## 📁 重要なファイル構成

### Phase 1 MVP（現在使用中）
- `simple-console.html` - MVPコンソールUI
- `backend/simple_api.py` - 4つのエンドポイント
- `backend/simple_models.py` - 3テーブルモデル
- `backend/app.py` - Flaskアプリケーション（simple_api登録済み）
- `backend/database.py` - DB接続（simple_models使用）
- `backend/services/automation_service.py` - Playwright自動入力

### Phase 2以降（アーカイブ済み）
- `.archive/` - 23ファイル保管（admin-console.html、worker-console.html、models.py等）

### ドキュメント
- `README.md` - プロジェクト概要、クイックスタート
- `PROJECT_SPEC.md` - 企画・仕様書、アーキテクチャ戦略
- `VPS_SETUP_GUIDE.md` - VPS初期セットアップ完全手順
- `DEVELOPMENT_LOG.md` - 開発作業ログ
- `HANDOFF.md` - 本ファイル（引き継ぎ文書）

---

## ❌ Phase 2で実装予定の未完成部分

### 1. VNC/リモートデスクトップ統合
- **目的**: ワーカーがブラウザを目視確認できる環境
- **現状**: Playwrightがheadless=Trueで画面非表示
- **実装予定**: VPS移行後に実装（Xvfb + x11vnc + noVNC）
- **詳細**: [VPS_SETUP_GUIDE.md](VPS_SETUP_GUIDE.md) の「Phase 2: VNC環境構築」参照

### 2. ワーカー管理機能
- ワーカー登録・認証
- タスク振り分けロジック
- 成果管理・評価

### 3. バッチ処理機能
- 定期実行（cron）
- エラーリトライ
- 通知機能

---

## 📋 プロジェクト整理の記録

### 削減効果（Phase 1 MVPに最適化）
- **HTML**: 14ファイル → 2ファイル（86%削減）
- **API**: 6ファイル → 1ファイル（83%削減）
- **DB**: 11テーブル → 3テーブル（73%削減）

### アーカイブファイル（.archive/）
Phase 2以降で復元予定:
- admin-console.html, worker-console.html, admin-console-old.html, worker-console-old.html
- api-test.html, api-test-standalone.html, api-integration-test.html, automation-test.html
- test-db.html, test-form.html, test-contact-form.html, Dockerfile.playwright-vnc
- docker-compose-kasm.yml, setup-novnc.sh
- backend/models.py, database_old.py, app_backup.py, seed_test_data.py
- backend/api/*.py（products, projects, targets, tasks, workers）

---

## 🎯 次のチャットで実装すべきこと

### Phase 2実装（VPS環境で実施）

#### 1. VNC環境構築（最優先）
```bash
# VPS上で実行
sudo apt install -y xvfb x11vnc novnc
export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 &
x11vnc -display :99 -forever -shared &
websockify --web=/usr/share/novnc 6080 localhost:5900 &
```

#### 2. Playwright VNC統合
```python
# automation_service.py修正
browser = playwright.chromium.launch(
    headless=False,  # headless=Trueから変更
    args=['--display=:99']
)
```

#### 3. ワーカーコンソール統合
```html
<!-- worker-console.htmlに追加 -->
<iframe src="http://localhost:6080/vnc.html" width="100%" height="600px"></iframe>
```

#### 4. データベース拡張
```sql
-- worker_*テーブル追加（接頭辞で論理分離）
CREATE TABLE worker_accounts (...);
CREATE TABLE worker_tasks (...);
CREATE TABLE worker_performance (...);
```

### 実装の順序
1. ✅ VNC環境構築（VPS_SETUP_GUIDE.md参照）
2. ⬜ Playwright headless=False設定
3. ⬜ worker-console.html復元・統合
4. ⬜ ワーカー管理API実装
5. ⬜ 動作確認・デバッグ

---

## 🔍 技術的な注意点

### データベース命名規則
```sql
-- Phase 1 MVP（simple_*接頭辞）
simple_companies, simple_products, simple_tasks

-- Phase 2（接頭辞で論理分離）
company_lists, company_info, company_scrape_logs
worker_accounts, worker_tasks, worker_performance
```

### Flask Blueprint分離
```python
# app.py
from backend.simple_api import bp as simple_bp  # Phase 1
from backend.api.companies import bp as companies_bp  # Phase 2
from backend.api.workers import bp as workers_bp  # Phase 2

app.register_blueprint(simple_bp, url_prefix='/api/simple')
app.register_blueprint(companies_bp, url_prefix='/api/companies')
app.register_blueprint(workers_bp, url_prefix='/api/workers')
```

### 環境変数管理
```bash
# .env（未作成、Phase 2で作成予定）
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_autoform
FLASK_SECRET_KEY=your-secret-key
GEMINI_API_KEY=your-gemini-api-key
VNC_DISPLAY=:99
```

### Codespacesポート設定
- **5001**: Flask API（必須、Public）
- **5432**: PostgreSQL（必須、Private）
- **8000**: HTMLサーバー（必須、Public）
- **5900**: VNC（Phase 2で必要、Private）
- **6080**: noVNC（Phase 2で必要、Public）

---

## 📚 重要ドキュメントの読み方

### 1. プロジェクトを理解したい
→ [README.md](README.md) → [PROJECT_SPEC.md](PROJECT_SPEC.md)

### 2. VPSセットアップしたい
→ [VPS_SETUP_GUIDE.md](VPS_SETUP_GUIDE.md)（完全手順書）

### 3. 過去の作業を振り返りたい
→ [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)（Phase 1-A〜Phase 1-D記録済み）

### 4. アーキテクチャ戦略を確認したい
→ [PROJECT_SPEC.md](PROJECT_SPEC.md)の「アーキテクチャ戦略」セクション

### 5. 環境を再起動したい
→ 本ファイルの「環境の起動手順」セクション

---

## 🚀 VPS移行チェックリスト

### VPS準備（ユーザー側）
- [ ] さくらVPS 2-4GB契約
- [ ] Ubuntu 22.04インストール
- [ ] SSH公開鍵設定

### VPS初期セットアップ（VPS_SETUP_GUIDE.md参照）
- [ ] 基本環境構築（Git、Docker、Python）
- [ ] PostgreSQL 16セットアップ
- [ ] Flaskアプリデプロイ
- [ ] systemdサービス作成
- [ ] Nginx設定
- [ ] VNC環境構築

### Phase 2実装
- [ ] Playwright headless=False設定
- [ ] worker-console.html復元・統合
- [ ] ワーカー管理API実装
- [ ] 動作確認

---

## 💡 よくある質問

### Q1: 環境が起動しない
**A**: 以下の順序で確認
```bash
# 1. PostgreSQL確認
docker ps -a | grep ai-autoform-db

# 2. Flaskプロセス確認
lsof -ti:5001

# 3. ポート設定確認（Codespaces）
# ポートタブで5001, 5432, 8000がPublic/Private適切に設定されているか
```

### Q2: APIが404エラー
**A**: simple_api.pyはurl_prefix='/api/simple'で登録
```bash
# 正: http://localhost:5001/api/simple/tasks
# 誤: http://localhost:5001/api/tasks
```

### Q3: データが表示されない
**A**: テストデータ確認
```bash
docker exec -it ai-autoform-db psql -U postgres -d ai_autoform -c "SELECT COUNT(*) FROM simple_tasks;"
# 結果: 10行あればOK
```

### Q4: .archiveのファイルはいつ使う？
**A**: Phase 2実装時に復元
- worker-console.html: ワーカーUI
- admin-console.html: 管理者UI
- backend/api/*.py: 各種APIエンドポイント
- models.py: 完全なデータモデル定義

---

## 🎉 Phase 1 MVP達成内容

### 動作確認済み機能
- ✅ PostgreSQL 3テーブル（企業5社、商品2件、タスク10件）
- ✅ Flask 4エンドポイント（一覧、詳細、実行、完了）
- ✅ Simple Console UI（統計、リスト、詳細、実行ボタン）
- ✅ Playwright自動入力（test-contact-form.html確認済み）
- ✅ スクリーンショット保存（screenshots/ディレクトリ）

### ドキュメント整備完了
- ✅ README.md（プロジェクト概要、クイックスタート）
- ✅ PROJECT_SPEC.md（企画、仕様、アーキテクチャ戦略）
- ✅ VPS_SETUP_GUIDE.md（VPS完全手順書）
- ✅ DEVELOPMENT_LOG.md（Phase 1-A〜1-D記録）
- ✅ HANDOFF.md（本ファイル、引き継ぎ文書）

### プロジェクト整理完了
- ✅ HTML 86%削減（14→2ファイル）
- ✅ API 83%削減（6→1ファイル）
- ✅ DB 73%削減（11→3テーブル）
- ✅ .archiveに23ファイル保管

---

## 📞 次のチャットでの最初の一言

```
「Phase 1 MVP完成状態です。HANDOFF.mdを確認してください。
VPS環境でPhase 2実装を開始します。VNC統合から始めましょう。」
```

または

```
「Phase 1 MVP完成状態です。HANDOFF.mdを確認してください。
Codespaces環境で○○の機能を追加したいです。」
```

---

**引き継ぎ完了！次のチャットでスムーズに再開できます 🚀**
   
2. **起動スクリプト**（`start-vnc.sh`）:
   ```bash
   #!/bin/bash
   # Xvfb起動（仮想ディスプレイ）
   Xvfb :99 -screen 0 1920x1080x24 &
   export DISPLAY=:99
   
   # VNCサーバー起動
   x11vnc -display :99 -forever -shared -rfbport 5900 &
   
   # websockify起動（noVNCアクセス用）
   websockify --web /usr/share/novnc 6080 localhost:5900 &
   
   echo "VNC起動完了: ポート6080でnoVNCアクセス可能"
   ```

3. **確認手順**:
   - ポート6080をPublicに設定
   - `https://[codespace]-6080.app.github.dev/vnc.html`にアクセス
   - 黒い画面が表示されればOK

#### Phase 2: Playwright統合
1. **automation_service.py修正**:
   ```python
   def __init__(self):
       self.headless = False  # GUI表示モードに変更
       self.display = ':99'   # Xvfbディスプレイ指定
   
   def start(self):
       import os
       os.environ['DISPLAY'] = self.display
       
       self.playwright = sync_playwright().start()
       self.browser = self.playwright.chromium.launch(
           headless=False  # GUI表示
       )
   ```

2. **動作確認**:
   ```bash
   # VNC画面を見ながらPlaywright実行
   DISPLAY=:99 python -c "
   from playwright.sync_api import sync_playwright
   p = sync_playwright().start()
   browser = p.chromium.launch(headless=False)
   page = browser.new_page()
   page.goto('https://google.com')
   page.screenshot(path='test.png')
   browser.close()
   p.stop()
   "
   ```

#### Phase 3: Worker Console統合
1. **worker-console.html修正**:
   ```javascript
   function getNoVncUrl() {
       const hostname = window.location.hostname;
       if (hostname.includes('app.github.dev')) {
           const baseHost = hostname.split('-').slice(0, -1).join('-');
           return `https://${baseHost}-6080.app.github.dev/vnc.html?autoconnect=true&resize=scale`;
       }
       return 'http://localhost:6080/vnc.html?autoconnect=true&resize=scale';
   }
   
   function loadBrowserView() {
       const iframe = document.getElementById('browser-view');
       iframe.src = getNoVncUrl();
   }
   ```

2. **自動送信フロー**:
   ```
   ユーザー「自動送信スタート」クリック
   ↓
   Worker Console: noVNCビューを読み込み（iframe）
   ↓
   API: POST /api/tasks/{id}/submit
   ↓
   FormAutomationService: 
     - DISPLAY=:99でChromium起動（VNC画面に表示される）
     - フォーム自動入力
     - reCAPTCHA検出 → 60秒待機
   ↓
   作業者: VNC画面でreCAPTCHA対応 & 送信ボタンクリック
   ↓
   Playwright: 送信完了検知（URL変化 or 成功メッセージ）
   ↓
   API: タスク完了 & ポイント付与
   ```

## 📋 現在のファイル構成

```
/workspaces/ai-auto-form/
├── backend/
│   ├── app.py                          # Flask APIサーバー（稼働中✅）
│   ├── database.py                     # DB接続設定（pool_pre_ping=False）
│   ├── models.py                       # SQLAlchemyモデル
│   ├── api/
│   │   ├── workers.py                  # 作業者API
│   │   ├── tasks.py                    # タスクAPI（automation_service呼び出し）
│   │   └── ...
│   └── services/
│       └── automation_service.py       # Playwright自動化（headless=True⚠️）
├── worker-console.html                 # 作業者画面（表示可能✅）
├── admin-console.html                  # 管理者画面
├── docker-compose.yml                  # PostgreSQL設定
├── docker-compose-kasm.yml            # KasmVNC設定（未使用❌）
└── setup-novnc.sh                     # noVNCセットアップスクリプト（未実行⚠️）
```

## 🚨 注意事項

### 動作中のプロセス
- Flask API: PID確認 `ps aux | grep python | grep app.py`
- HTTP Server: PID確認 `ps aux | grep "http.server 8000"`
- PostgreSQL: `docker ps | grep ai-autoform-db`

### 再起動が必要な場合
```bash
# Flask API再起動
killall python
cd /workspaces/ai-auto-form
PYTHONPATH=/workspaces/ai-auto-form nohup python -u backend/app.py > flask.log 2>&1 &

# HTTPサーバー再起動
pkill -f "http.server 8000"
python -m http.server 8000 &
```

### ポート設定（必ずPublicに）
- **5001**: Flask API
- **8000**: フロントエンドHTTPサーバー
- **6080**: noVNC（Phase 1で設定予定）

## 🎯 新チャットでの第一声（推奨）

```
「AI AutoFormプロジェクトの続きです。
HANDOFF.mdを読んで現状を把握してください。

次のタスク:
Phase 1として、VNCサーバー（TigerVNC + noVNC + Xvfb）を
Codespaces内で直接セットアップしてください。
Dockerは使わず、シンプルな構成で進めましょう。

まず現在動作中のプロセス（Flask API、PostgreSQL）を確認してから始めてください。」
```

## 💡 設計のポイント

### なぜDockerを使わないか
- Codespaces自体がDocker環境
- Docker-in-Dockerは権限問題やネットワーク複雑化の原因
- 直接インストールの方がトラブルシューティングしやすい

### なぜKasmVNCを諦めるか
- SSL証明書問題がCodespacesと相性悪い
- 高機能すぎて設定が複雑
- シンプルなnoVNCで十分要件を満たせる

### なぜSeleniumではなくPlaywright
- 既にPlaywrightで実装済み
- Playwrightの方が高速で安定
- VNC統合はどちらでも同じ方法で可能

## 📊 現在の達成度

```
[████████░░] 80% 完成

✅ データベース設計・実装
✅ API開発（CRUD）
✅ フロントエンド（Worker Console）
✅ Playwright自動化ロジック
⚠️  VNC統合（未完成）
⬜ 本番デプロイ
⬜ AI文章生成（Gemini API）
```

---

**次のチャットでは、Phase 1のVNCセットアップから確実に進めましょう！**
