# AI AutoForm - 再構成開発スケジュール

**最終更新**: 2025年12月20日

---

## 🎯 開発方針の転換

### ❌ 旧方針の問題点
- VNC統合で開発が停滞（Codespaces制限）
- 複数の機能を同時実装→混乱
- コア機能の動作確認ができていない
- ワーカー管理、AI機能が未完成のまま進行

### ✅ 新方針（MVP First）
1. **コア機能に集中**：シンプルな自動化フローの確立
2. **段階的開発**：Phase 1 → 2 → 3 と順次実装
3. **動作確認優先**：各Phaseで必ず動作する状態を維持

---

## 📋 Phase 1: コア自動化機能（2-3日）

**目標**: ブラウザで完結する「自動入力→目視確認→手動送信」の実装

### 実装内容

#### 1.1 シンプルなDB構造

```sql
-- 企業マスター（ターゲットリスト）
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    website_url TEXT NOT NULL,
    form_url TEXT NOT NULL,
    industry VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 案件マスター（商材）
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    message_template TEXT,  -- メッセージテンプレート
    created_at TIMESTAMP DEFAULT NOW()
);

-- タスク（実行単位）
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(id),
    product_id INT REFERENCES products(id),
    status VARCHAR(20) DEFAULT 'pending',  -- pending, in_progress, completed, failed
    form_data JSONB,  -- 入力データ（名前、メール、メッセージ等）
    screenshot_path TEXT,
    submitted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

#### 1.2 シンプルなUI（単一ワーカー）

```
┌─────────────────────────────────────────────┐
│  簡易コンソール                              │
│                                             │
│  [タスク選択] ▼ 株式会社ABC × 商材A         │
│                                             │
│  企業情報:                                   │
│  - 社名: 株式会社ABC                         │
│  - URL: https://abc.com                     │
│  - フォームURL: https://abc.com/contact     │
│                                             │
│  送信内容:                                   │
│  - 名前: [入力済み]                          │
│  - メール: [入力済み]                        │
│  - メッセージ: [AI生成テキスト表示]          │
│                                             │
│  [自動入力開始] ボタン                       │
│                                             │
│  ブラウザプレビュー:                         │
│  [スクリーンショット画像]                    │
│                                             │
│  確認して問題なければ:                       │
│  [送信実行] [スキップ] [NG]                  │
└─────────────────────────────────────────────┘
```

#### 1.3 実装フロー

```python
# 1. タスク取得
task = get_next_pending_task()

# 2. Playwright起動（headlessモード）
browser = playwright.chromium.launch(headless=True)

# 3. フォームに自動入力
page.goto(task.company.form_url)
page.fill('input[name="name"]', task.form_data['name'])
page.fill('input[name="email"]', task.form_data['email'])
page.fill('textarea[name="message"]', task.form_data['message'])

# 4. スクリーンショット撮影
screenshot = page.screenshot()
task.screenshot_path = save_screenshot(screenshot)

# 5. ブラウザを一時停止（送信ボタンは押さない）
# ユーザーが画面で確認

# 6. ユーザーが「送信実行」ボタンクリック
# → API経由で送信指示

# 7. Playwrightが送信ボタンをクリック
page.click('button[type="submit"]')

# 8. 送信完了検知
wait_for_success_message()
task.status = 'completed'
task.submitted = True
```

#### 1.4 実装ファイル

- **簡易UI**: `simple-console.html`
- **API**: `backend/api/simple_tasks.py`
- **自動化サービス**: `backend/services/simple_automation.py`（既存を簡素化）
- **DBマイグレーション**: `backend/migrate_simple.py`

---

## 📋 Phase 2: ワーカー管理機能（2-3日）

**目標**: 複数ワーカーによるタスク並行処理

### 追加DB構造

```sql
-- ワーカーテーブル
CREATE TABLE workers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    points INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- タスク割り当て追加
ALTER TABLE tasks ADD COLUMN worker_id INT REFERENCES workers(id);
ALTER TABLE tasks ADD COLUMN assigned_at TIMESTAMP;
```

### 実装内容

1. **Worker Console**: 複数ワーカーが同時ログイン可能
2. **タスク割り当て**: プロジェクト単位でワーカーにタスク配分
3. **ポイントシステム**: 送信成功でポイント付与
4. **進捗ダッシュボード**: Admin Consoleで全体状況を可視化

---

## 📋 Phase 3: AI機能（2-3日）

**目標**: Gemini APIによる文面自動生成

### 実装内容

1. **企業サイト解析**: 
   ```python
   company_info = scrape_website(company.website_url)
   insight = gemini_analyze(company_info)
   ```

2. **メッセージ生成**:
   ```python
   message = gemini_generate_message(
       company=company,
       product=product,
       insight=insight
   )
   ```

3. **A/Bテスト**: 複数パターン生成して効果測定

---

## 📊 開発スケジュール（1週間）

| Phase | 日数 | 内容 | 成果物 |
|-------|------|------|--------|
| **Phase 1** | 2-3日 | コア自動化 | 動作するMVP |
| **Phase 2** | 2-3日 | ワーカー管理 | マルチユーザー対応 |
| **Phase 3** | 2-3日 | AI機能 | 完全自動化 |

---

## ✅ Phase 1 の成功基準

Phase 1が完成したと言えるのは：

- [ ] DBに企業10件、商材2件、タスク20件を投入
- [ ] 簡易コンソールでタスクを選択できる
- [ ] 「自動入力開始」でフォームに入力される
- [ ] スクリーンショットが表示される
- [ ] 「送信実行」で実際に送信される
- [ ] タスクステータスが'completed'になる
- [ ] 連続して次のタスクを処理できる

---

## 🔧 現在の実装の整理

### 残すもの（Phase 1で使用）
- ✅ PostgreSQL基本構造
- ✅ Flask API（簡素化）
- ✅ Playwright自動化（headlessモード）
- ✅ スクリーンショット機能

### 一時無効化（Phase 2以降）
- ⏸️ Worker管理機能（ログイン不要に）
- ⏸️ プロジェクト機能
- ⏸️ ポイントシステム
- ⏸️ VNC統合

### 削除（不要）
- ❌ KasmVNC関連
- ❌ 複雑なCORS設定
- ❌ 使用していないAPI

---

## 🚀 明日からの作業

### Day 1（今日）
1. ✅ 開発スケジュール再構成（完了）
2. [ ] シンプルなDB構造を設計
3. [ ] `simple-console.html` のモックアップ作成
4. [ ] 既存コードの不要部分をコメントアウト

### Day 2
1. [ ] `migrate_simple.py` でDB作成
2. [ ] テストデータ投入（企業10件、商材2件）
3. [ ] `simple_tasks.py` API実装
4. [ ] 簡易コンソールの基本UI実装

### Day 3
1. [ ] Playwright統合（スクリーンショット方式）
2. [ ] エンドツーエンドテスト
3. [ ] バグ修正
4. [ ] **Phase 1 完成🎉**

---

## 💡 この方針のメリット

1. **確実な進捗**: 各Phaseで必ず動作する状態を維持
2. **早期フィードバック**: Phase 1完成時点で実用可能
3. **リスク分散**: VNC問題に依存しない
4. **学習効果**: シンプルから複雑へ段階的に理解

---

**Phase 1から確実に進めましょう！次は simple-console.html のUIモックを作成します。**
