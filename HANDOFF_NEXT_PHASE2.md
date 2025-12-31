# AI AutoForm - Phase 2 タスク生成機能 開発引き継ぎ 🚀

**作成日**: 2025年12月31日  
**前フェーズ**: Phase 1 MVP完成 + スキップ機能実装済み  
**次フェーズ**: Phase 2-A タスク生成機能（企業DB + 案件DB + AI文面カスタマイズ）

---

## 🎯 Phase 2-A の目標

### 実装する機能
1. **企業DB拡張** - 大量企業データの管理
2. **案件DB実装** - simple_projectsテーブル新設
3. **AI文面カスタマイズ** - Gemini API統合
4. **タスク一括生成** - 案件×企業で数百〜数千タスク生成

### なぜこの順序？
- 現在のテストデータ: **10タスクのみ**（5企業 × 2商品）
- これではワーカー管理機能のテストが不可能
- 先に大量タスクを用意 → ワーカー1人で運用テスト → Phase 3でワーカー管理

---

## ✅ Phase 1 完成状況（継承すべき資産）

### データベース（PostgreSQL）
```sql
-- 既存テーブル（変更禁止）
simple_companies (5件のテストデータ)
  - id, name, form_url, industry, website_url, created_at

simple_products (2件のテストデータ)
  - id, name, description, message_template, created_at

simple_tasks (10件)
  - id, company_id, product_id, form_data, status, screenshot_path
  - submitted, completed_at, created_at
```

### API（Flask 5001）
```
GET  /api/simple/tasks          - タスク一覧
GET  /api/simple/tasks/<id>     - タスク詳細
POST /api/simple/tasks/<id>/execute - 自動入力実行
POST /api/simple/tasks/<id>/complete - 完了
POST /api/simple/tasks/<id>/skip - スキップ（pending戻し）
POST /api/simple/tasks/reset    - 全リセット
POST /api/simple/vnc/auto-paste - VNC自動ペースト
```

### フロントエンド
- **simple-console-v2.html** - ダークモードUI、チュートリアル、スキップ機能
- **アクセス**: http://153.126.154.158:8000/simple-console-v2.html

### VNC環境
- **noVNC**: http://153.126.154.158:6080/vnc.html
- **自動ペースト**: xdotool + xsel（インストール済み）
- **タイムアウト**: 削除済み（無限待機）

---

## 🏗️ Phase 2-A 実装計画

### Step 1: 案件DBテーブル作成

```sql
CREATE TABLE simple_projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,  -- 例: "Webサイト制作営業2025Q1"
    target_industry VARCHAR(100), -- 対象業界
    message_template TEXT,        -- 基本メッセージテンプレート
    status VARCHAR(20) DEFAULT 'active', -- active/paused/completed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Step 2: 企業DB拡張（収集機能）

#### オプションA: CSV一括取り込み
```python
# backend/api/simple_api.py に追加
@simple_bp.route('/companies/import', methods=['POST'])
def import_companies():
    """CSVから企業データを一括インポート"""
    # CSVファイル: name, form_url, industry, website_url
    # 重複チェック（form_urlで判定）
    # 一括INSERT
```

#### オプションB: スクレイピング（後回し可）
- Google検索結果から企業情報収集
- 問い合わせフォームURL検出

### Step 3: AI文面カスタマイズ

```python
# backend/services/gemini_service.py を拡張
def generate_custom_message(company_info: dict, project: dict) -> str:
    """
    企業情報とプロジェクトテンプレートから最適化メッセージ生成
    
    Args:
        company_info: {name, industry, website_url}
        project: {name, message_template}
    
    Returns:
        カスタマイズされたメッセージ
    """
    prompt = f"""
以下の企業向けに営業メッセージをカスタマイズしてください。

【企業情報】
- 企業名: {company_info['name']}
- 業界: {company_info['industry']}
- Webサイト: {company_info['website_url']}

【メッセージテンプレート】
{project['message_template']}

【要件】
- 企業の業界に合わせた具体例を含める
- 300文字以内
- 丁寧なビジネス文書として
"""
    # Gemini API呼び出し
```

### Step 4: タスク一括生成API

```python
# backend/api/simple_api.py に追加
@simple_bp.route('/tasks/generate', methods=['POST'])
def generate_tasks():
    """
    案件×企業リストから大量タスク生成
    
    Request Body:
    {
        "project_id": 1,
        "company_ids": [1, 2, 3, ...], または "all"
        "use_ai": true  // AI文面カスタマイズを使用
    }
    
    Response:
    {
        "success": true,
        "tasks_created": 300,
        "project_id": 1
    }
    """
    # 1. プロジェクト情報取得
    # 2. 企業リスト取得
    # 3. 各企業ごとにAI文面生成（use_ai=trueの場合）
    # 4. simple_tasksにINSERT
```

---

## 🚨 重要な制約・注意点

### MVP戦略厳守
- ✅ 既存の`simple_*`テーブル構造は変更禁止
- ✅ 新規テーブルは`simple_projects`として追加
- ✅ SQLAlchemy継続使用（新しいORM導入禁止）

### VPS環境
- **VPSアドレス**: 153.126.154.158
- **ユーザー**: `ubuntu@`（root@は使用禁止）
- **プロジェクトパス**: `/opt/ai-auto-form`
- **Flask再起動**: `bash restart-flask-vps.sh`

### Gemini API
- **設定ファイル**: `config/deepbiz_config.py`
- **環境変数**: `GEMINI_API_KEY`（.envに設定済み）
- **既存サービス**: `backend/services/gemini_service.py`（拡張可能）

---

## 📋 実装優先順位

### 優先度1（今週）
1. ✅ simple_projectsテーブル作成
2. ✅ 案件マスター管理API（CRUD）
3. ✅ CSV企業一括インポート機能

### 優先度2（来週）
4. ✅ AI文面カスタマイズ関数
5. ✅ タスク一括生成API
6. ✅ フロントエンドに案件選択UI追加

### 優先度3（テスト）
7. ✅ 300タスク生成テスト
8. ✅ ワーカー1人での運用テスト
9. ✅ パフォーマンス・エラーハンドリング改善

---

## 🎯 Phase 2-A 成功基準

### 定量的目標
- ✅ 企業データ: 100社以上
- ✅ 案件データ: 3案件以上
- ✅ 生成タスク: 300タスク以上
- ✅ AI文面生成成功率: 95%以上

### 定性的目標
- ✅ ワーカー1人で1日50タスク処理可能
- ✅ UI/UX問題を全て洗い出し
- ✅ エラーハンドリング完備
- ✅ Phase 3（ワーカー管理）への準備完了

---

## 📂 重要なファイルパス

```
/opt/ai-auto-form/
├── backend/
│   ├── app.py                         # Flask起動
│   ├── simple_models.py               # DB モデル（拡張対象）
│   ├── simple_migrate.py              # マイグレーション（拡張対象）
│   ├── api/
│   │   └── simple_api.py              # API（拡張対象）
│   └── services/
│       ├── gemini_service.py          # AI（拡張対象）
│       └── automation_service.py      # Playwright
├── simple-console-v2.html             # フロントエンド
├── restart-flask-vps.sh               # Flask再起動
└── .env                               # 環境変数（GEMINI_API_KEY）
```

---

## 🔧 開発フロー

### コード変更時の手順
```bash
# 1. ローカルで編集
# backend/simple_models.py 等を編集

# 2. VPSに転送
scp backend/simple_models.py ubuntu@153.126.154.158:/opt/ai-auto-form/backend/

# 3. Flask再起動（確実な方法）
bash restart-flask-vps.sh

# 4. 動作確認
# http://153.126.154.158:8000/simple-console-v2.html
```

### マイグレーション実行
```bash
# VPSで実行
ssh ubuntu@153.126.154.158
cd /opt/ai-auto-form
export PYTHONPATH=/opt/ai-auto-form
python backend/simple_migrate.py
```

---

## 📚 参照ドキュメント

### 必読
1. **HANDOFF.md** - 現在の完成状態（最新）
2. **PROJECT_SPEC.md** - プロジェクト全体仕様
3. **.github/copilot-instructions.md** - 開発規約・禁止事項

### 参考
- **docs/ARCHITECTURE.md** - システム構成
- **docs/API.md** - API仕様
- **PHASE1_MVP_GUIDE.md** - Phase 1実装ガイド

---

## 🚀 次の行動

### まず最初にやること
1. **simple_projectsテーブル定義** - simple_models.pyに追加
2. **マイグレーション実行** - テーブル作成
3. **CRUD API実装** - 案件の登録・取得・更新・削除

### 実装順序（推奨）
```
Day 1: simple_projectsテーブル + CRUD API
Day 2: CSV企業インポート機能
Day 3: AI文面カスタマイズ関数
Day 4: タスク一括生成API
Day 5: フロントエンドUI追加 + テスト
```

---

## 💡 Tips

### AI文面生成のコツ
- プロンプトに企業の業界・規模を含める
- 具体例を1つ必ず入れる
- 文字数制限を明示（300文字推奨）

### パフォーマンス
- タスク一括生成は非同期処理推奨
- 100タスクごとにコミット
- 進捗表示UI実装推奨

### エラーハンドリング
- Gemini API失敗時はテンプレートそのまま使用
- 企業情報不足時のデフォルト値設定
- リトライロジック実装

---

## ✅ Phase 2-A チェックリスト

完成時に以下をチェック：

- [ ] simple_projectsテーブル作成完了
- [ ] 案件CRUD API実装完了
- [ ] CSV企業インポート機能実装完了
- [ ] AI文面カスタマイズ関数実装完了
- [ ] タスク一括生成API実装完了
- [ ] フロントエンドUI更新完了
- [ ] 100社以上の企業データ登録完了
- [ ] 300タスク以上の生成テスト完了
- [ ] ワーカー1人での運用テスト完了
- [ ] HANDOFF.md更新完了

---

**次のチャットで「Phase 2-A開発を始めます」と伝えてください。**  
**このドキュメント（HANDOFF_NEXT_PHASE2.md）を参照して開発を進めます。**

Good luck! 🚀
