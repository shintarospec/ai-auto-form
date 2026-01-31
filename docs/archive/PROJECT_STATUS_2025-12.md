# AI AutoForm - プロジェクト現状と実装方針

**最終更新**: 2025年12月18日  
**進捗率**: 80%完成（VNC統合のみ残り）  
**次のマイルストーン**: Phase 1 VNC統合完了 → 本番運用開始可能

---

## 🎯 プロジェクトビジョン

**「AI入力 + 人間承認」のハイブリッド型フォーム営業支援システム**

- AIが企業情報を解析し、個別最適化された営業文を生成
- Playwrightが自動でフォームに入力
- 作業者がVNC画面で最終確認・reCAPTCHA対応・送信ボタンクリック
- ポイント制報酬システムで複数ワーカーを効率的に運用

### ビジネスモデル（新企画書 Strategic Master v8.0より）
```
売上: 65円/件 × 30,000件/月 = 1,950,000円
├─ ワーカー報酬: 2円/件 × 30,000件 = 60,000円
├─ システム原価: 5円/件 × 30,000件 = 150,000円
└─ 粗利: 1,740,000円（利益率 89.2%）
```

---

## ✅ 実装済み機能（80%完成）

### 1. データベース層
- ✅ PostgreSQL 16（Docker稼働中）
- ✅ 7テーブル実装
  - `workers` - 作業者管理（ポイント制）
  - `products` - 商材管理
  - `projects` - プロジェクト管理
  - `tasks` - タスク管理
  - `target_lists` - 企業リスト管理
  - `target_companies` - 企業詳細情報
  - `project_workers` - プロジェクト・作業者紐付け
- ✅ テストデータ投入済み（作業者10名、テストプロジェクト1件）

**確認コマンド**:
```bash
docker exec -it ai-autoform-db psql -U postgres -d ai_autoform -c "SELECT * FROM workers;"
```

### 2. API層（Flask）
- ✅ Flask 3.0.0（ポート5001で稼働）
- ✅ RESTful API実装
  - `/api/workers` - 作業者CRUD
  - `/api/products` - 商材CRUD
  - `/api/projects` - プロジェクトCRUD
  - `/api/tasks` - タスクCRUD
  - `/api/targets` - 企業リストCRUD
  - `/api/tasks/{id}/submit` - フォーム自動送信（メイン機能）
- ✅ CORS設定（Codespaces対応）
- ✅ レート制限（Flask-Limiter）

**起動コマンド**:
```bash
cd /workspaces/ai-auto-form
PYTHONPATH=/workspaces/ai-auto-form nohup python -u backend/app.py > flask.log 2>&1 &
```

**動作確認**:
```bash
curl http://localhost:5001/api/workers
```

### 3. フロントエンド層
- ✅ Admin Console（`admin-console.html`）
  - プロジェクト作成・管理
  - 企業リスト登録
  - タスク一括生成
  - 進捗ダッシュボード
- ✅ Worker Console（`worker-console.html`）
  - **3カラム構成**実装済み
    - 左: 企業情報表示
    - 中: AI生成メッセージ表示
    - 右: ブラウザビュー（iframe - VNC統合待ち⚠️）
  - タスク一覧・選択機能
  - 自動送信ボタン
  - ポイント表示

**起動コマンド**:
```bash
python -m http.server 8000 &
# アクセス: https://[codespace]-8000.app.github.dev/worker-console.html
```

### 4. 自動化層（Playwright）
- ✅ `backend/services/automation_service.py` 実装
- ✅ Playwright 1.40.0
- ✅ フォーム自動入力ロジック
- ✅ reCAPTCHA検出・待機機能（60秒）
- ✅ 送信完了検知（3パターン）
  1. URL変化検知（thank-you, success等）
  2. 成功メッセージ表示
  3. フォームリセット検知
- ⚠️ VNC統合未完成（headless=True状態）

### 5. AI層（Gemini）
- ✅ `backend/services/gemini_service.py` 実装
- ✅ Gemini 1.5 Flash連携
- ✅ 企業サイト解析機能
- ✅ 営業文パーソナライズ生成

---

## ⚠️ 未完成の部分（残り20%）

### Phase 1: VNC統合（最優先 - 今すぐ実装）

現在、Playwrightは`headless=True`で動作しているため、ワーカーがブラウザを見ることができません。

**実装内容**:
1. TigerVNC + noVNC + Xvfb セットアップ
2. Playwrightを`DISPLAY=:99`で起動
3. Worker ConsoleのiframeでnoVNC表示

**完成条件**:
- ワーカーがブラウザでVNC画面を見れる
- 自動入力の様子をリアルタイムで確認できる
- reCAPTCHA対応・送信ボタンをVNC上でクリックできる

---

## 🏗️ 採用技術スタック（確定版）

### Backend
- **Python 3.11+**
- **Flask 3.0.0** - APIサーバー
- **SQLAlchemy** - ORM
- **PostgreSQL 16** - データベース
- **Playwright 1.40.0** - ブラウザ自動化
- **Gemini 1.5 Flash** - AI文面生成

### Frontend
- **Vanilla JavaScript (ES6+)** - シンプル・高速
- **Tailwind CSS** - UI
- **HTML5**

### VNC（Phase 1で実装）
- **TigerVNC** - VNCサーバー
- **noVNC** - WebブラウザでVNC表示（ポート6080）
- **Xvfb** - 仮想ディスプレイ（:99）
- **websockify** - WebSocket変換

### Infrastructure
- **開発**: GitHub Codespaces
- **本番**: さくらVPS（予定）

---

## 🚫 不採用技術（理由）

### ❌ Selenium
- 理由: Playwrightの方が高速・安定・モダン
- 既にPlaywrightで実装済み

### ❌ Docker（selenium/standalone-chrome）
- 理由: Codespaces内のDocker-in-Dockerは複雑化の原因
- 直接インストールの方がトラブルシューティングしやすい

### ❌ KasmVNC
- 理由: SSL証明書問題でCodespacesと相性悪い
- セットアップが複雑（noVNCで十分）
- 本番環境（さくらVPS）で将来的に検討可能

### ❌ Enter待機方式
- 理由: 1スクリプト=1タスクでスケールしない
- 複数ワーカー並行処理が不可能
- API管理方式の方が遥かに優れている

---

## 📋 アーキテクチャ設計（確定版）

### 疎結合アーキテクチャ（2層分離）

```
┌──────────────────────────────────────────────────┐
│  企業インテリジェンス基盤（The Brain）              │
│  ├─ TargetList（企業リスト）                      │
│  ├─ TargetCompany（企業詳細）                     │
│  └─ API: /api/targets/*                          │
│                                                   │
│  ※将来: Google Maps検知 → クローラー → 自動更新   │
└──────────────────────────────────────────────────┘
                    ↓ データ供給
┌──────────────────────────────────────────────────┐
│  送信実行システム（The Factory）                   │
│  ├─ Project（プロジェクト管理）                   │
│  ├─ Task（タスク管理）                            │
│  ├─ Worker（作業者管理）                          │
│  ├─ Playwright（自動入力）                        │
│  ├─ Gemini（AI文面生成）                          │
│  └─ VNC（人間による確認・送信）                   │
└──────────────────────────────────────────────────┘
```

**設計の利点**:
- データ収集の障害 → 送信業務は影響なし
- 送信システムの障害 → データ蓄積は継続
- データは「全社のコア資産」として再利用可能

---

## 🚀 実装ロードマップ

### Phase 1: VNC統合（今すぐ実装 - 最優先）
**目標**: Worker Consoleでブラウザ画面を見ながらフォーム送信

1. VNCサーバー構築
   ```bash
   # Xvfb起動（仮想ディスプレイ 1920x1080）
   Xvfb :99 -screen 0 1920x1080x24 &
   export DISPLAY=:99
   
   # VNCサーバー起動
   x11vnc -display :99 -forever -shared -rfbport 5900 &
   
   # noVNC起動
   websockify --web /usr/share/novnc 6080 localhost:5900 &
   ```

2. Playwright統合
   ```python
   # automation_service.py修正
   automation = FormAutomationService(headless=False, display=':99')
   ```

3. Worker Console統合
   ```javascript
   // worker-console.html修正
   iframe.src = 'https://[codespace]-6080.app.github.dev/vnc.html';
   ```

**完成基準**:
- [ ] VNC画面にブラウザが表示される
- [ ] 自動入力の様子が見える
- [ ] ワーカーがreCAPTCHAをクリックできる
- [ ] 送信ボタンをクリックできる

### Phase 2: Google Maps連携（中期 - 3ヶ月後）
- Google Maps APIで新規企業検知
- クローラーで公式サイト解析
- TargetCompanyテーブル自動更新
- データフレッシュネス管理

### Phase 3: プラットフォーム化（長期 - 1年後）
- 外部クライアント受注機能
- SaaSモデル化
- 企業DB API外販
- KasmVNC移行検討（低遅延化）

---

## 📊 現在の達成度

```
[████████░░] 80% 完成

✅ データベース設計・実装（7テーブル）
✅ Flask API開発（全CRUD完成）
✅ フロントエンド（Admin + Worker Console）
✅ Playwright自動化ロジック
✅ Gemini AI連携
⚠️ VNC統合（未完成 - Phase 1で実装）
⬜ Google Maps自動収集（Phase 2）
⬜ 本番デプロイ（Phase 3）
```

---

## 🎯 次のアクション

### 1. Phase 1 VNC統合を完了させる（最優先）

**手順**:
1. 必要パッケージインストール
   ```bash
   sudo apt-get update
   sudo apt-get install -y xvfb x11vnc websockify
   git clone https://github.com/novnc/noVNC.git /usr/share/novnc
   ```

2. VNCサーバー起動スクリプト作成
   ```bash
   # start-vnc.sh
   ```

3. automation_service.py修正
   ```python
   headless=False, display=':99'
   ```

4. worker-console.html修正
   ```javascript
   // VNC iframeを追加
   ```

5. 動作確認
   - Worker Consoleで「自動送信スタート」クリック
   - VNC画面でブラウザ表示確認
   - reCAPTCHA対応・送信完了

### 2. 詳細な実装はHANDOFF.mdを参照

[HANDOFF.md](HANDOFF.md)に段階的な実装手順が記載されています。

---

## 📁 重要ファイル一覧

### ドキュメント
- `HANDOFF.md` - 新チャット引き継ぎ指示（Phase 1実装手順）
- `PROJECT_STATUS.md` - 本ファイル（現状と方針）
- `README.md` - プロジェクト概要
- `docs/ARCHITECTURE.md` - システム構成
- `docs/WORKFLOW.md` - 運用手順
- `docs/API.md` - API仕様

### Backend
- `backend/app.py` - Flask APIサーバー
- `backend/models.py` - SQLAlchemyモデル（7テーブル）
- `backend/database.py` - DB接続設定
- `backend/api/tasks.py` - タスクAPI（メイン機能）
- `backend/services/automation_service.py` - Playwright自動化
- `backend/services/gemini_service.py` - AI文面生成

### Frontend
- `admin-console.html` - 管理者画面
- `worker-console.html` - 作業者画面（3カラム）

### Infrastructure
- `docker-compose.yml` - PostgreSQL設定
- `database/schema.sql` - DBスキーマ

---

## 🚨 重要な注意事項

### 動作中のプロセス
```bash
# Flask API
ps aux | grep "python.*app.py"

# HTTPサーバー
ps aux | grep "http.server 8000"

# PostgreSQL
docker ps | grep ai-autoform-db
```

### ポート設定（必ずPublicに）
- **5001**: Flask API
- **8000**: フロントエンドHTTPサーバー
- **6080**: noVNC（Phase 1で追加）
- **5432**: PostgreSQL（Docker内部）

### 再起動コマンド
```bash
# Flask API再起動
killall python
cd /workspaces/ai-auto-form
PYTHONPATH=/workspaces/ai-auto-form nohup python -u backend/app.py > flask.log 2>&1 &

# HTTPサーバー再起動
pkill -f "http.server 8000"
python -m http.server 8000 &
```

---

## 💡 設計判断の根拠

### なぜPlaywright？
- Seleniumより2-3倍高速
- auto-waitで安定性が高い
- マルチブラウザ対応が容易
- モダンなAPI設計

### なぜnoVNC？
- ブラウザだけで動作（専用ソフト不要）
- セットアップが簡単
- 枯れた技術で安定
- Codespaces環境と相性が良い

### なぜDockerを使わない？
- Codespaces自体がDocker環境
- Docker-in-Dockerは権限問題・ネットワーク複雑化
- 直接インストールの方がデバッグしやすい

### なぜAPI管理方式？
- 複数ワーカーの並行処理が可能
- リアルタイム進捗管理
- 自動ポイント計算
- スケーラブル（月30,000件対応）

---

## 🎉 完成後の運用イメージ

```
1. 管理者がAdmin Consoleでプロジェクト作成
   - 企業リスト選択（1000社）
   - 商材選択（月額5万円のSaaS）
   - ワーカー割り当て（10名）
   
2. システムが自動でタスク生成（1000件）

3. ワーカーがWorker Consoleにログイン
   - タスク選択
   - 「自動送信スタート」クリック
   
4. Playwrightが自動入力（VNC画面に表示）
   - 企業情報取得
   - AI文面生成
   - フォーム自動入力
   - reCAPTCHA検出 → 60秒待機
   
5. ワーカーがVNC画面で確認
   - 内容チェック
   - reCAPTCHA対応
   - 送信ボタンクリック
   
6. システムが自動処理
   - タスク完了記録
   - ポイント付与（2pt = 2円）
   - 次のタスクを表示

7. 管理者がダッシュボードで確認
   - 進捗: 750/1000件完了
   - コスト: 1,500円（750件 × 2円）
   - 推定効果: アポ7.5件（1%換算）
```

---

**次のステップ**: Phase 1のVNC統合を実装し、完全稼働させる！ 🚀
