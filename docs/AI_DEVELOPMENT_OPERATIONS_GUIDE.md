# AI駆動開発 運用ガイド
**バージョン:** 1.0  
**作成日:** 2026年1月8日  
**対象:** GitHub Copilot / Claude等のAIアシスタントを活用した開発プロジェクト

---

## 1. 概要

### 1.1 このガイドの目的

AIコーディングアシスタントと効率的に協働するための運用ルールを定義します。
以下の課題を解決します：

- **コンテキストの断絶**: セッションが切れるとAIが状況を忘れる
- **知識の散逸**: 重要な決定事項が会話の中に埋もれる
- **重複作業**: 同じ説明を何度もする必要がある
- **品質の不安定**: 重要機能が意図せず壊れる

### 1.2 3つの柱

```
┌─────────────────────────────────────────────────────────────┐
│                    AI駆動開発の3つの柱                        │
├─────────────────┬─────────────────┬─────────────────────────┤
│  📋 指示書       │  📊 現状把握     │  🛡️ 品質保護            │
│  (Instructions) │  (State)        │  (Quality)             │
├─────────────────┼─────────────────┼─────────────────────────┤
│ copilot-        │ CURRENT_STATE   │ MCF (Mission           │
│ instructions.md │ .md             │ Critical Functions)    │
├─────────────────┼─────────────────┼─────────────────────────┤
│ プロジェクト固有 │ 動的な状態      │ 壊してはいけない        │
│ のルール・知識   │ TODO・進捗      │ 重要機能の保護          │
└─────────────────┴─────────────────┴─────────────────────────┘
```

---

## 2. ファイル構成

### 2.1 推奨ディレクトリ構造

```
project/
├── .github/
│   └── copilot-instructions.md    # ★ AIアシスタント用指示書（プロジェクトルール）
│
├── docs/
│   ├── CURRENT_STATE.md           # ★ 現状把握・TODO・MCF管理（毎セッション更新）
│   ├── MVP_SPEC.md                # ★ MVP仕様書（ユーザーストーリー・機能一覧）
│   ├── AI_DEVELOPMENT_OPERATIONS_GUIDE.md  # 本ガイド（運用ルール・テンプレート）
│   ├── [機能名]_SPEC.md           # 機能別詳細仕様（PUBLIC_SITE_SPEC.md等）
│   └── archive/                   # 旧バージョンのドキュメント保管
│       └── [ファイル名]_YYYY-MM.md
│
├── scripts/                        # 運用スクリプト
├── src/                            # ソースコード
└── README.md                       # プロジェクト概要（外部向け）
```

### 2.2 コアドキュメント（★必須）

| ファイル | 役割 | 主な読者 | 更新タイミング |
|----------|------|----------|---------------|
| `copilot-instructions.md` | プロジェクト固有のルール・制約 | AI | 方針変更時 |
| `CURRENT_STATE.md` | 技術的な現状・TODO・MCF | AI・開発者 | **毎セッション** |
| `MVP_SPEC.md` | 何ができるか（ユーザー視点） | AI・PM・開発者 | MVP更新時 |

### 2.3 補助ドキュメント

| ファイル | 役割 | 更新タイミング |
|----------|------|---------------|
| `[機能名]_SPEC.md` | 機能別の詳細仕様 | 機能追加・変更時 |
| `ARCHITECTURE.md` | システム構成・データフロー | 設計変更時 |
| `DEPLOYMENT_GUIDE.md` | デプロイ手順 | 環境変更時 |
| `archive/*.md` | 旧ドキュメント保管 | 大幅改訂時 |

### 2.4 ドキュメントライフサイクル

```
【新規作成】
  copilot-instructions.md  ← プロジェクト開始時
  CURRENT_STATE.md         ← プロジェクト開始時
  MVP_SPEC.md              ← MVP定義時

【定期更新】
  CURRENT_STATE.md         ← 毎セッション（TODO・進捗）
  MVP_SPEC.md              ← 機能追加時（状態列を更新）

【アーカイブ】
  大幅改訂時 → docs/archive/[ファイル名]_YYYY-MM.md に移動
  例: SPECIFICATION.md → archive/SPECIFICATION_2025-12.md
```

### 2.5 各ファイルの役割（詳細）

| ファイル | 更新頻度 | 内容 |
|----------|----------|------|
| `copilot-instructions.md` | 低（方針変更時） | プロジェクトルール、技術スタック、コーディング規約 |
| `CURRENT_STATE.md` | 高（毎セッション） | DB状態、TODO、進捗、MCF一覧 |
| `MVP_SPEC.md` | 中（MVP更新時） | MVP機能一覧、ユーザーストーリー、完成基準 |
| `ARCHITECTURE.md` | 中（設計変更時） | システム構成、データフロー |
| `*_SPEC.md` | 低（機能完成時） | 機能別の詳細仕様 |

---

## 3. copilot-instructions.md テンプレート

```markdown
# [プロジェクト名] - AI開発アシスタント用指示書

## ⚠️ 最重要：現状把握
**最新のシステム状態は必ず `docs/CURRENT_STATE.md` を参照してください。**

---

## 📌 プロジェクト概要
- **プロジェクト名:** 
- **目的:** 
- **現在フェーズ:** 
- **技術スタック:** 

---

## 🏗️ アーキテクチャ
[システム構成図、DB構成、主要コンポーネント]

---

## 📦 データモデル
[主要なモデル定義]

---

## 🔧 開発ルール

### コーディング規約
[命名規則、ファイル構成ルール]

### 重要な制約
[API制限、セキュリティ要件、パフォーマンス要件]

---

## 🚀 開発ワークフロー
[デプロイ手順、テスト方法]

---

## 💡 コード生成時のヒント
[AIがコード生成する際の注意点、参考にすべき既存コード]
```

---

## 4. CURRENT_STATE.md テンプレート

```markdown
# [プロジェクト名] 現状整理書
**最終更新:** YYYY-MM-DD

---

## 0. クイックリファレンス

### 環境情報
| 項目 | 値 |
|------|-----|
| 本番URL | |
| VPS/サーバー | |
| DB | |

### よく使うコマンド
\`\`\`bash
# デプロイ
# ログ確認
# DB確認
\`\`\`

---

## 1. システム状態

### DB状態（YYYY-MM-DD時点）
| テーブル | レコード数 | 備考 |
|----------|-----------|------|

### 最新マイグレーション
- バージョン: 
- 内容: 

---

## 2. MCF（ミッションクリティカル機能）

### MCF一覧
| ID | 機能 | 関連ファイル | 最終テスト日 |
|----|------|-------------|-------------|

### MCF変更時のルール
1. 変更前にテスト実行
2. 変更後に同じテスト実行
3. PR時に「MCF変更」ラベル付与

---

## 3. TODO（マスターリスト）

### 🔥 進行中
| ID | タスク | 状態 | 担当 | 期限 |
|----|--------|------|------|------|

### 📋 バックログ
| ID | タスク | 優先度 | 説明 |
|----|--------|--------|------|

### ✅ 完了（直近）
| ID | タスク | 完了日 |
|----|--------|--------|

---

## 4. 既知の課題・技術的負債
| 課題 | 影響 | 優先度 |
|------|------|--------|

---

## 変更履歴
| 日付 | 変更内容 |
|------|----------|
```

---

## 5. MVP_SPEC.md テンプレート

```markdown
# [プロジェクト名] MVP仕様書
**最終更新:** YYYY-MM-DD
**バージョン:** X.X
**ステータス:** [開発中/MVP完成/運用中]

---

## 1. MVP概要

### 1.1 プロダクトビジョン
[何を解決するプロダクトか]

### 1.2 ターゲットユーザー
| ユーザー | ニーズ | 提供価値 |
|----------|--------|----------|

### 1.3 解決する課題
[箇条書きで3-5個]

---

## 2. 機能一覧（MVP）

| 機能 | 画面 | MVP | 状態 | 説明 |
|------|------|-----|------|------|
| 機能A | /path | ✅ | ✅完了 | 説明 |
| 機能B | /path | ✅ | 🔄進行中 | 説明 |
| 機能C | /path | ❌ | 未着手 | 将来実装 |

---

## 3. ユーザーストーリー

| ID | ユーザー | やりたいこと | 理由 | 完成基準 | 状態 |
|----|----------|-------------|------|----------|------|
| US-01 | [誰が] | [何を]したい | [なぜ] | [どうなったら完成] | ✅/🔄/❌ |

---

## 4. 画面一覧

### 4.1 画面遷移図
\`\`\`
[ASCII図で画面遷移を表現]
\`\`\`

### 4.2 画面別要素
[各画面の構成要素を記載]

---

## 5. データ仕様

### 5.1 データ件数
| カテゴリ | 件数 | 備考 |
|----------|------|------|

### 5.2 データフィールド
| フィールド | 説明 | 取得方法 | MVP |
|-----------|------|----------|-----|

---

## 6. 非機能要件

### パフォーマンス
| 項目 | 目標 | 現状 |
|------|------|------|

### セキュリティ
| 項目 | 対応 | 状態 |
|------|------|------|

---

## 変更履歴
| バージョン | 日付 | 変更内容 |
|-----------|------|----------|
```

---

## 6. MCF（ミッションクリティカル機能）管理

### 5.1 MCFとは

**絶対に壊してはいけない重要機能**を明示し、変更時に追加の保護・確認を義務付ける仕組み。

### 5.2 MCF指定基準

以下のいずれかに該当する機能をMCFに指定：

1. **収益直結**: 課金、決済、契約処理
2. **データ損失リスク**: DB操作、バックアップ、マイグレーション
3. **外部連携**: API連携、認証、データ同期
4. **コア機能**: そのサービスの存在意義となる機能

### 5.3 MCF変更プロセス

```
1. 変更前
   └─ テスト実行 → 結果記録

2. 変更実施
   └─ コード変更

3. 変更後
   └─ 同じテスト実行 → 結果比較

4. レビュー
   └─ MCF変更であることを明示
```

---

## 6. セッション運用

### 6.1 セッション開始時

AIアシスタントに以下を伝える：

```
1. プロジェクト名
2. 今日やりたいこと（具体的なタスク）
3. 前回の続きの場合は、前回の状態
```

### 6.2 セッション終了時

以下を更新：

- [ ] `CURRENT_STATE.md` のTODO状態
- [ ] 変更履歴に本日の作業を追記
- [ ] 未完了タスクの引き継ぎ事項をメモ

### 6.3 長時間バックグラウンド処理

```bash
# nohupで実行した場合
nohup command > output.log 2>&1 &

# → セッション終了してもVPSで処理継続
# → 次回セッションで進捗確認
```

---

## 7. グローバル開発チームでの一般的な運用

### 7.1 ドキュメント管理

| 手法 | 説明 | 本ガイドでの対応 |
|------|------|-----------------|
| **ADR** (Architecture Decision Records) | 設計決定の記録 | `CURRENT_STATE.md`の変更履歴 |
| **RFC** (Request for Comments) | 大きな変更の提案プロセス | MCF変更プロセス |
| **Runbook** | 運用手順書 | `copilot-instructions.md`のワークフロー |

### 7.2 品質管理

| 手法 | 説明 | 本ガイドでの対応 |
|------|------|-----------------|
| **CODEOWNERS** | 特定ファイルの変更時にレビュー必須 | MCF管理 |
| **Feature Flags** | 機能の段階的リリース | Phase管理 |
| **Canary Release** | 一部ユーザーへの先行リリース | テストモード（--test） |

### 7.3 進捗管理

| 手法 | 説明 | 本ガイドでの対応 |
|------|------|-----------------|
| **Sprint Planning** | 2週間単位の計画 | TODOマスターリスト |
| **Daily Standup** | 毎日の進捗共有 | セッション開始時の状況共有 |
| **Retrospective** | 振り返り | 変更履歴 |

### 7.4 インシデント管理

| 手法 | 説明 | 本ガイドでの対応 |
|------|------|-----------------|
| **Postmortem** | 障害後の振り返り | 既知の課題セクション |
| **SLO/SLA** | サービスレベル目標 | MCFのテスト基準 |
| **On-call** | 当番制での監視 | バックグラウンド処理の監視 |

---

## 8. Tips: GitHub Codespaces環境設定

### 8.1 GitHub Secretsの設定

Codespacesで環境変数やSSH鍵を安全に使うために、**GitHub Secrets**を活用します。

**設定場所:** https://github.com/settings/codespaces

#### APIキーの設定

```
1. GitHub → Settings → Codespaces → Secrets
2. 「New secret」をクリック
3. 以下を登録:

   Name: DEEPBIZ_GOOGLE_MAPS_API_KEY
   Value: [APIキー]
   Repository access: [対象リポジトリを選択]

   Name: DEEPBIZ_GEMINI_API_KEY
   Value: [APIキー]

   Name: DEEPBIZ_API_KEY
   Value: [認証用APIキー]
```

**コード内での参照:**
```python
import os
api_key = os.environ.get('DEEPBIZ_GOOGLE_MAPS_API_KEY')
```

#### SSH秘密鍵の設定（VPS接続用）

```
1. GitHub → Settings → Codespaces → Secrets
2. 「New secret」をクリック
3. 以下を登録:

   Name: DEEPBIZ_VPS_SSH_KEY
   Value: [秘密鍵の内容をそのまま貼り付け]
         -----BEGIN OPENSSH PRIVATE KEY-----
         ...
         -----END OPENSSH PRIVATE KEY-----
```

**Codespaces起動時の設定スクリプト（`.devcontainer/postCreateCommand.sh`）:**
```bash
#!/bin/bash
# SSH鍵の設定
if [ -n "$DEEPBIZ_VPS_SSH_KEY" ]; then
  mkdir -p ~/.ssh
  echo "$DEEPBIZ_VPS_SSH_KEY" > ~/.ssh/id_ed25519_deepbiz
  chmod 600 ~/.ssh/id_ed25519_deepbiz
  
  # SSH config設定
  cat >> ~/.ssh/config << EOF
Host deepbiz-vps
  HostName 133.167.116.58
  User ubuntu
  IdentityFile ~/.ssh/id_ed25519_deepbiz
  StrictHostKeyChecking no
EOF
  chmod 600 ~/.ssh/config
fi
```

### 8.2 VPS側の設定

#### SSH公開鍵の登録

```bash
# VPSで実行
echo "ssh-ed25519 AAAA... your-email@example.com" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### 環境変数の設定（`.env`ファイル）

```bash
# /var/www/app_name/.env
GOOGLE_MAPS_API_KEY=...
GEMINI_API_KEY=...
DEEPBIZ_API_KEY=...
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_password
```

### 8.3 接続テスト

```bash
# Codespacesから実行
ssh deepbiz-vps "echo 'Connection successful!'"
```

### 8.4 Secrets更新後の反映

**重要:** Secretsを追加・変更した後は、Codespaceを再ビルドする必要があります。

```
1. VS Code → Command Palette (Cmd+Shift+P)
2. 「Codespaces: Rebuild Container」を実行
3. 再起動後、環境変数が反映される
```

### 8.5 セキュリティベストプラクティス

| 項目 | 推奨 |
|------|------|
| 命名規則 | `[PROJECT]_[PURPOSE]` 形式（例: `DEEPBIZ_GOOGLE_MAPS_API_KEY`） |
| APIキー制限 | Google CloudでIP/リファラー制限を設定 |
| 定期ローテーション | 3-6ヶ月ごとにキーを更新 |
| 最小権限 | 必要なAPIのみ有効化 |
| 漏洩時対応 | 即座にキーを無効化→再生成 |

### 8.6 Python venv環境の設定

#### なぜvenvを使うか

- システムPythonを汚さない
- プロジェクトごとに依存関係を分離
- 本番環境と開発環境で同じパッケージバージョンを使用

#### Codespaces（開発環境）での設定

```bash
# venv作成
python3 -m venv venv

# 有効化
source venv/bin/activate

# パッケージインストール
pip install -r requirements.txt

# 確認
which python  # → /workspaces/project/venv/bin/python
```

#### VPS（本番環境）での設定

```bash
# venv作成
cd /var/www/app_name
python3 -m venv venv

# 有効化
source venv/bin/activate

# パッケージインストール
pip install -r requirements.txt

# Gunicorn起動（venv内のPythonを使用）
venv/bin/gunicorn --workers 3 --bind unix:app.sock -m 007 app:app --daemon
```

#### ⚠️ 絶対禁止: venvをGitにコミットしない

**理由:**
- CodespacesとVPSでPythonパスが異なる
- `git pull`でVPSのvenvがCodespaces用に上書きされ、環境が壊れる
- バイナリファイルでリポジトリが肥大化

**`.gitignore`に必ず追加:**
```
venv/
__pycache__/
*.pyc
.env
```

**確認方法:**
```bash
# venvがトラッキングされていないことを確認
git ls-files | grep "^venv/" | wc -l
# → 0 であること
```

**もし誤ってコミットした場合の復旧:**
```bash
# Gitから削除（ファイルは残す）
git rm -r --cached venv/
git commit -m "fix: Remove venv from git"
git push

# VPSでvenv再作成
ssh your-vps 'cd /var/www/app_name && rm -rf venv && python3 -m venv venv && venv/bin/pip install -r requirements.txt'
```

#### requirements.txtの管理

```bash
# 現在の環境からrequirements.txtを生成
pip freeze > requirements.txt

# 本番環境で同期
ssh your-vps 'cd /var/www/app_name && source venv/bin/activate && pip install -r requirements.txt'
```

---

## 9. よくある落とし穴と解決策

実際のプロジェクトで発生した問題とその解決策をまとめています。

### 9.1 API課金の罠

#### 問題: 詳細ページでAPI課金が発生
```python
# ❌ 悪い例: 詳細ページ表示のたびにAPI呼び出し
@app.route('/detail/<id>')
def detail(id):
    place_details = gmaps.place(place_id=biz.place_id)  # $0.017/回！
    return render_template('detail.html', details=place_details)
```

#### 解決策: DBキャッシュを使用
```python
# ✅ 良い例: 事前にDBに保存、表示時はDBから読み込み
@app.route('/detail/<id>')
def detail(id):
    biz = Biz.query.get(id)  # DBから読み込み（無料）
    return render_template('detail.html', biz=biz)
```

#### Google API課金一覧（要注意）
| API | 料金 | 対策 |
|-----|------|------|
| Places API (Text Search) | $5/1000件 | バッチ処理時のみ使用 |
| Places API (Details) | $17/1000件 | **使用禁止**、DBキャッシュ使用 |
| Maps Embed API | **無料** | 地図表示はこれを使用 |
| Maps JavaScript API | 有料 | 必要時のみ |

### 9.2 URL/エンドポイント変更時の参照エラー

#### 問題: エンドポイント名変更後に500エラー
```python
# 変更前
@app.route('/search')
def salon_search(): ...

# 変更後
@app.route('/clinic')
def clinic_search(): ...  # 名前変更
```

```html
<!-- テンプレートが古いまま → 500エラー -->
<a href="{{ url_for('salon_search') }}">検索</a>
```

#### 解決策: grep で全参照を確認
```bash
# 変更前に全参照箇所を確認
grep -r "url_for('salon_search')" templates/

# 一括置換
find templates/ -name "*.html" -exec sed -i 's/salon_search/clinic_search/g' {} \;
```

### 9.3 DB同期の問題

#### 問題: マイグレーションエラー `Can't locate revision`

ローカルとVPSでDBのalembic_versionが不一致の場合に発生。

#### 解決策: 同期チェックスクリプト
```bash
# マイグレーション前に必ず実行
python scripts/check_db_sync.py

# 不一致があればVPSから同期
python scripts/check_db_sync.py --sync

# その後マイグレーション
flask db migrate -m "説明"
flask db upgrade
```

### 9.4 Maps Embed APIの制限設定

#### 問題: 地図が表示されない

Maps Embed APIはブラウザから呼び出されるため、**IPアドレス制限ではなくHTTPリファラー制限**が必要。

| 制限タイプ | 用途 | 対象API |
|-----------|------|---------|
| IPアドレス制限 | サーバーサイドAPI | Places API |
| HTTPリファラー制限 | ブラウザ呼び出しAPI | Maps Embed API |

#### 解決策: APIキーを分離
```
# サーバー用キー
制限: IPアドレス（VPSのIP）
対象: Places API

# ブラウザ用キー
制限: HTTPリファラー（http://your-domain/*）
対象: Maps Embed API, Maps JavaScript API
```

### 9.5 テーブル/モデル名変更時の参照漏れ

#### 問題: `salon` → `biz` 変更で参照漏れ

```python
# モデル名変更
class Biz(db.Model):  # 旧: Salon
    __tablename__ = 'biz'  # 旧: 'salon'
```

以下の箇所で参照漏れが発生しやすい：
- テンプレート変数名
- ルート関数名
- URL（`/salon/<id>`）
- 外部キー名（`salon_id` → `biz_id`）

#### 解決策: 計画的なリネーム
```bash
# 1. 全参照箇所を事前確認
grep -r "salon" --include="*.py" --include="*.html" .

# 2. 段階的に変更（一度に全部変えない）
# - Phase 1: モデル名・テーブル名
# - Phase 2: テンプレート変数
# - Phase 3: URL・ルート名

# 3. 変更後に動作確認
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/
```

### 9.6 バックグラウンド処理の管理

#### nohupでの長時間処理
```bash
# VPSでバックグラウンド実行
nohup venv/bin/python scripts/long_task.py > output.log 2>&1 &

# → セッションを閉じても処理は継続
# → Codespacesのスピナーはキャンセル可能
```

#### 進捗確認コマンド
```bash
# プロセス確認
ssh your-vps "ps aux | grep long_task | grep -v grep"

# ログ確認
ssh your-vps "tail -30 /var/www/app/output.log"

# DB件数確認
ssh your-vps "sqlite3 /path/to/db.db 'SELECT COUNT(*) FROM table'"
```

---

## 10. チェックリスト

### 新規プロジェクト開始時

- [ ] `.github/copilot-instructions.md` 作成
- [ ] `docs/CURRENT_STATE.md` 作成
- [ ] `docs/MVP_SPEC.md` 作成
- [ ] MCF候補の洗い出し
- [ ] デプロイ手順の文書化
- [ ] GitHub SecretsにAPIキー設定
- [ ] GitHub SecretsにSSH鍵設定（VPS使用時）
- [ ] venv環境構築
- [ ] `.gitignore`にvenv/追加確認

### 毎セッション

- [ ] `CURRENT_STATE.md` を最新化
- [ ] 完了タスクのチェック
- [ ] 新規課題の記録

### 週次

- [ ] TODOの優先度見直し
- [ ] MCFのテスト実行
- [ ] 技術的負債の棚卸し

---

## 11. 用語集

| 用語 | 説明 |
|------|------|
| **MCF** | Mission Critical Functions - 壊してはいけない重要機能 |
| **ADR** | Architecture Decision Records - 設計決定の記録文書 |
| **RFC** | Request for Comments - 変更提案のプロセス |
| **Runbook** | 運用手順書 |
| **Postmortem** | 障害発生後の振り返り文書 |
| **SLO** | Service Level Objective - サービスレベル目標 |

---

## 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|----------|
| 1.2 | 2026-01-08 | よくある落とし穴セクション追加（API課金、URL変更、DB同期等） |
| 1.1 | 2026-01-08 | Tips追加（GitHub Secrets、SSH鍵、APIキー、venv設定） |
| 1.0 | 2026-01-08 | 初版作成（DeepBizプロジェクトの運用を元に策定） |
