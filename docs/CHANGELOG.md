# AI AutoForm - 変更履歴

## バージョン管理ポリシー

- **メジャーバージョン（X.0.0）**: 互換性のない大幅な変更
- **マイナーバージョン（0.X.0）**: 後方互換性のある機能追加
- **パッチバージョン（0.0.X）**: バグ修正・細かい改善

---

## [Unreleased]

### 予定されている変更

- PostgreSQLへのマイグレーション
- Gemini API統合
- JWT認証実装
- 管理画面のリアルタイム進捗表示
- reCAPTCHA検出通知機能

---

## [2.0.0] - 2025-01-XX

### 🎉 メジャーアップデート: Form Automation

#### Added（追加）

- **Playwright統合**
  - Webkit（プライマリ）とChromium（フォールバック）のマルチブラウザサポート
  - 5フィールド自動入力（name, email, company, phone, message）
  - 60秒間のHuman-in-the-Loop待機（reCAPTCHA対応）
  - マルチメソッド送信検出
    - URL変化検出
    - 成功メッセージ可視性チェック
    - フォームリセット検出
  - ブラウザクローズ検出

- **タスク送信エンドポイント**
  - `POST /api/tasks/{id}/submit`
  - `submitted: true/false` による完了ステータス
  - フィールド入力リストの返却
  - reCAPTCHA検出フラグ

- **作業者コンソールUI改善**
  - シンプルな単一ボタンUI（"自動送信スタート"）
  - タスクフローガイド（外部タイトル＋青グラデーション）
  - 黄色のCTAメッセージ
  - 送信完了時の自動進行（3秒後）
  - 送信失敗時のリトライボタン

- **ポイントシステム調整**
  - 送信完了：+50ポイント
  - 入力のみ（送信未完）：ポイントなし

#### Changed（変更）

- **Flask APIポート設定**
  - macOS: `PORT=5001`（AirPlayとの競合回避）
  - Codespaces: `PORT=5000`

- **デフォルトフォームURL**
  - ローカル開発用: `http://localhost:8000/test-form.html`

- **headlessモード設定**
  - ローカル開発: `headless=False`（GUI表示）
  - 本番環境: `headless=True`（スクリーンショット保存）

#### Fixed（修正）

- Apple Silicon上のChromiumクラッシュ → Webkit切り替え
- macOS AirPlayポート競合 → PORT=5001に変更
- 非表示成功メッセージの誤検出 → フォームリセット検出追加
- ブラウザ手動クローズ時の60秒待機継続 → `page.is_closed()` チェック追加

#### Removed（削除）

- 作業者コンソールの手動操作ボタン（"ブラウザ起動", "フォーム入力", "送信完了"）
- 不要なボタンを削除し、自動化フローに集約

---

## [1.5.0] - 2025-01-XX

### プロジェクト作成フロー完成

#### Added

- **ターゲットリスト選択機能**
  - プロジェクト作成時にターゲットリストを選択可能
  - 商品・作業者も同時に選択

- **プロジェクト→タスク変換**
  - プロジェクト作成時に全ターゲット企業分のタスクを自動生成
  - タスクにcompanyUrl, companyNameを自動設定

- **管理画面プロジェクト一覧**
  - プロジェクト名、ターゲットリスト、商品、作業者を表示
  - タスク総数カウント

#### Changed

- LocalStorageデータ構造の拡張
  - プロジェクトに`targetListId`, `productId`, `workerIds`を追加

---

## [1.4.0] - 2025-01-XX

### ターゲットリスト管理機能

#### Added

- **CSVアップロード機能**
  - 企業名、URL、業界を一括登録
  - CSV形式バリデーション

- **手動企業追加機能**
  - フォームから1社ずつ追加可能

- **ターゲットリスト一覧表示**
  - リスト名、企業数、作成日を表示
  - 各リストの企業詳細表示

#### Technical

- PapaParse 5.4.1を使用したCSVパース
- LocalStorageにターゲットリストと企業データを保存

---

## [1.3.0] - 2025-01-XX

### Flask API統合

#### Added

- **Flask 3.0.0 バックエンド**
  - `/api/health` ヘルスチェックエンドポイント
  - CORS設定（GitHub Codespaces対応）

- **フロントエンド→バックエンド接続**
  - fetch APIでバックエンド呼び出し
  - エラーハンドリング実装

#### Technical

- Flask-CORS 4.0.0
- Codespacesでポート5000を公開

---

## [1.2.0] - 2025-01-XX

### 商品管理機能

#### Added

- 商品一覧表示（商品名、価格、説明）
- 商品追加フォーム
- 商品編集・削除機能

---

## [1.1.0] - 2025-01-XX

### 作業者管理機能

#### Added

- 作業者一覧表示（名前、メール、スキル、獲得ポイント）
- 作業者追加フォーム
- 作業者編集・削除機能

---

## [1.0.0] - 2025-01-XX

### 🎉 初期リリース

#### Added

- **管理者画面（aiautoform_管理者画面.html）**
  - ダッシュボード（作業者数、商品数、プロジェクト数）
  - タブナビゲーション（作業者、商品、プロジェクト、ターゲットリスト）

- **作業者画面（aiautoform_作業者管理画面.html）**
  - タスクリスト表示
  - ステータスフィルター（全て、未着手、作業中、完了）
  - ポイント表示

- **データ永続化**
  - LocalStorageベースのデータ管理
  - workers, products, projects, tasks, targets, targetListsを保存

- **デザインシステム**
  - Tailwind CSS 3.4.1
  - Chart.js 4.4.1（将来の可視化用）
  - レスポンシブデザイン

#### Technical

- Vanilla JavaScript（フレームワークなし）
- HTML5
- GitHub Codespaces対応

---

## データベーススキーマ変更履歴

### [準備中] PostgreSQL移行

現在LocalStorageで管理しているデータをPostgreSQLに移行予定

**テーブル設計**

```sql
-- workers（作業者）
CREATE TABLE workers (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  skill_level VARCHAR(20) DEFAULT 'beginner',
  points INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- products（商品）
CREATE TABLE products (
  id SERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  price INTEGER NOT NULL,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- target_lists（ターゲットリスト）
CREATE TABLE target_lists (
  id SERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- target_companies（ターゲット企業）
CREATE TABLE target_companies (
  id SERIAL PRIMARY KEY,
  target_list_id INTEGER REFERENCES target_lists(id),
  company_name VARCHAR(200) NOT NULL,
  company_url TEXT NOT NULL,
  industry VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- projects（プロジェクト）
CREATE TABLE projects (
  id SERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  target_list_id INTEGER REFERENCES target_lists(id),
  product_id INTEGER REFERENCES products(id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- tasks（タスク）
CREATE TABLE tasks (
  id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  worker_id INTEGER REFERENCES workers(id),
  company_name VARCHAR(200) NOT NULL,
  company_url TEXT NOT NULL,
  status VARCHAR(20) DEFAULT 'pending',
  message TEXT,
  submitted BOOLEAN DEFAULT FALSE,
  screenshot_path TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP
);

-- project_workers（プロジェクト作業者関連）
CREATE TABLE project_workers (
  project_id INTEGER REFERENCES projects(id),
  worker_id INTEGER REFERENCES workers(id),
  PRIMARY KEY (project_id, worker_id)
);
```

---

## 破壊的変更の記録

### [2.0.0] - API Response Structure

**Before:**
```json
{
  "success": true,
  "message": "..."
}
```

**After:**
```json
{
  "success": true,
  "submitted": true,
  "fields_filled": [...],
  "message": "..."
}
```

**Migration Guide:**
- フロントエンドで `result.submitted` をチェック
- `submitted: true` の場合のみポイント付与
- `submitted: false` の場合はリトライボタン表示

---

## セキュリティアップデート

### [1.3.0] - CORS設定

- `*.app.github.dev` ドメインを許可
- `localhost:*` を許可
- 本番環境では特定ドメインのみ許可すること

---

## パフォーマンス改善

### [2.0.0] - Playwright最適化

- Webkitブラウザ使用でメモリ使用量30%削減
- ヘッドレスモード時のスクリーンショット保存を最適化
- フォーム入力時間を平均2秒以下に短縮

---

## 既知の問題

### [2.0.0]

- [ ] reCAPTCHAの自動検出通知が未実装
- [ ] 管理画面のリアルタイム進捗更新が未実装
- [ ] エラーリトライロジックが未実装
- [ ] スクリーンショット保存パスが `/tmp` 固定（Docker環境で問題の可能性）

---

## コントリビューター向けガイドライン

### コミットメッセージ規約

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type:**
- `feat`: 新機能
- `fix`: バグ修正
- `docs`: ドキュメント変更
- `style`: コードフォーマット
- `refactor`: リファクタリング
- `test`: テスト追加
- `chore`: ビルド・設定変更

**例:**
```
feat(automation): add multi-method submission detection

- URL change detection
- Success message visibility check
- Form reset detection

Closes #123
```

### ブランチ戦略

- `main` - 本番環境
- `develop` - 開発環境
- `feature/*` - 機能開発
- `hotfix/*` - 緊急修正

### リリースプロセス

1. `develop` で機能開発
2. プルリクエスト作成
3. レビュー・テスト
4. `main` へマージ
5. バージョンタグ作成（`v2.0.0`）
6. リリースノート作成
