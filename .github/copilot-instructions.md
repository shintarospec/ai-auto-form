# AI AutoForm - Copilot Instructions

## 🎯 MVP戦略（最重要）

このプロジェクトは**MVP（Minimum Viable Product）戦略**を採用しています。

### MVP開発の鉄則

1. **既存の動作するコードを壊さない**
   - Phase 1 MVPは完成し、動作確認済み
   - 新機能は既存機能の上に積み上げる
   
2. **過剰実装を避ける**
   - ユーザーが明確に要求していない機能は追加しない
   - 「あったら便利」ではなく「なければ困る」機能のみ実装
   
3. **段階的に拡張する**
   - Phase 1 → Phase 2 → Phase 3 の順序を守る
   - 各Phaseの完成を待ってから次に進む
   
4. **シンプルさを維持する**
   - 複雑なアーキテクチャより、理解しやすいコード
   - `simple_*` prefixに象徴されるシンプル設計

## プロジェクト概要

AI AutoFormは、ワーカー向けフォーム自動送信システムです。

### システム構成
- **VPS**: 153.126.154.158（ユーザー名: `ubuntu@`、**root@ではない**）
- **Backend**: Flask (Python) - ポート5001（デフォルト）、ポート8000（開発用）
- **Database**: PostgreSQL
- **Automation**: Playwright + VNC
- **AI**: Google Gemini API

## 環境情報（重要）

### VPS接続
```bash
# 正しい接続方法
ssh ubuntu@153.126.154.158
scp file.py ubuntu@153.126.154.158:/path/to/dest

# ❌ 間違い（root@を使わない）
ssh root@153.126.154.158  # 使用禁止
```

### ディレクトリ構造
- プロジェクトルート: `/opt/ai-auto-form`
- Flask起動: `python backend/app.py`
- 環境変数: `export PYTHONPATH=/opt/ai-auto-form`

## コーディング規約

### Python
- **PEP 8準拠**
- 型ヒント推奨
- `simple_*` prefix使用（既存の命名規則を守る）

### API設計
- RESTful設計
- エンドポイント例: `/api/simple/tasks`, `/api/simple/companies`
- `simple_api.py`のパターンに従う

### データベース
- テーブル: `simple_companies`, `simple_products`, `simple_tasks`
- **既存テーブル構造を変更しない**
- SQLAlchemyで統一（新しいORMライブラリ導入禁止）

## 禁止事項（MVP戦略遵守のため）

### 絶対に守ること

1. **既存テーブル構造の変更禁止**
   - Phase 1で確立された`simple_companies`, `simple_products`, `simple_tasks`の定義は不変
   - カラム追加・削除・型変更は事前相談必須
   
2. **VPS接続は必ず`ubuntu@`を使用**
   - `root@153.126.154.158` は使用禁止
   - `ubuntu@153.126.154.158` のみ使用
   
3. **新しい技術スタックの導入禁止**
   - ORM: SQLAlchemyで統一（他のORM導入禁止）
   - フレームワーク: Flask（変更禁止）
   - データベース: PostgreSQL（変更禁止）
   
4. **VNC機能の再実装禁止**
   - 既存ファイル（docker-compose.yml, start-vnc.sh等）を使用
   - 独自のVNC実装は不要

### 実装前に確認すること

- ❓ この機能は本当に今のPhaseで必要か？
- ❓ 既存の実装を壊さないか？
- ❓ ユーザーが明確に要求しているか？
- ❓ より単純な実装方法はないか？

## 優先参照ドキュメント

開発時は以下のドキュメントを優先的に参照：

1. **HANDOFF.md** - 現在の完成状態
2. **PROJECT_SPEC.md** - プロジェクト全体仕様
3. **docs/DEEPBIZ_INTEGRATION.md** - DeepBiz連携仕様
4. **docs/ARCHITECTURE.md** - システムアーキテクチャ

## 開発方針（MVP戦略に基づく）

### 基本姿勢
- **Phase 1 MVPは完成品** - 既存実装を崩さない
- **既存パターンに従う** - `simple_*`モデル、`simple_api.py`の設計を踏襲
- **段階的実装** - 一度に複数機能を追加しない
- **ドキュメント更新** - 実装と同時にHANDOFF.mdを更新

### 実装の優先順位
1. **既存機能の修正・改善**（最優先）
2. **ユーザー明示的要求の実装**（高優先）
3. **Phase計画に含まれる機能**（中優先）
4. **提案ベースの機能追加**（低優先・要相談）

### コード品質より重視すること
- 動作の確実性（完璧なコードより動くコード）
- 既存コードとの一貫性
- 理解しやすさ（複雑なパターンより単純な実装）
- 段階的な改善（一度で完璧を目指さない）
## 🔧 開発・デプロイフロー（重要）

### Flask再起動の確実な手順

**問題**: コード変更後にFlaskを再起動しても、Pythonキャッシュやインポート済みモジュールにより変更が反映されないことがある

**解決策**: 以下の確実な手順を必ず実行

```bash
# 1. コード編集（ローカル）
# automation_service.py等を編集

# 2. VPSに転送
scp backend/services/automation_service.py ubuntu@153.126.154.158:/opt/ai-auto-form/backend/services/

# 3. Flask再起動（確実な方法）
bash restart-flask-vps.sh

# または手動の場合：
ssh ubuntu@153.126.154.158 '
  pkill -9 -f "python.*app.py"
  cd /opt/ai-auto-form
  find . -name "*.pyc" -delete
  find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
  bash start-flask.sh
'

# 4. タスク実行して検証
# simple-console.htmlからタスク実行
# VNC画面で変更が反映されているか確認
```

### ポート設定（固定）

- **Flaskポート**: 5001（`start-flask.sh`で`PORT=5001`設定済み）
- **HTTPサーバーポート**: 8000（simple-console.html配信用）
- **VNCポート**: 6080（noVNC Web UI）

**注意**: simple-console.htmlは5001を期待しているため、Flaskは必ず5001で起動すること

### 変更反映の検証方法

1. **DOM確認**: `debug_screenshots/panel_content_*.txt` でタイムスタンプ確認
2. **スクリーンショット**: `debug_screenshots/panel_debug_*.png` で視覚確認
3. **VNC画面**: 実際のブラウザで目視確認（ブラウザキャッシュに注意）

### トラブルシューティング

**変更が反映されない場合**:
1. VPS上のコードを確認: `ssh ubuntu@153.126.154.158 'grep -n "検索文字列" /opt/ai-auto-form/backend/services/automation_service.py'`
2. Flaskプロセスを確認: `ssh ubuntu@153.126.154.158 'ps aux | grep "python.*app.py"'`
3. Pythonキャッシュ完全削除 + Flask強制再起動（上記手順）
4. ブラウザキャッシュクリア: Ctrl+Shift+R（VNC画面とsimple-console.html両方）