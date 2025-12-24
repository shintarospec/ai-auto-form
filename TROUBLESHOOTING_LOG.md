# トラブルシューティングログ - 青いパネルUI更新問題

**問題**: VNC内の青いパネルUIが古いテキスト「📋 フォームデータ（クリックでコピー）」のまま
**期待**: 新しいテキスト「📋 フォーム入力データ」+ 3ステップ説明

**日時**: 2025年12月24日

---

## ✅ 確認済み事項

### コード検証
- ✅ ローカルファイル `automation_service.py` 154行目: `title.textContent = '📋 フォーム入力データ';`
- ✅ VPSファイル `/opt/ai-auto-form/backend/services/automation_service.py` 154行目: 同上
- ✅ MD5ハッシュ一致: `aa8aec4f9fa4c3a75bfb8868946ac9cd`
- ✅ コードは正しく転送・更新されている

### 基本機能
- ✅ クリック→コピー機能: 動作
- ✅ 右クリック→ペースト機能: 動作
- ✅ フォーム送信: 動作

---

## 🔄 試したアプローチ（効果なし）

### 1回目: Pythonキャッシュ削除 + Flask再起動
```bash
ssh ubuntu@153.126.154.158 'cd /opt/ai-auto-form && rm -rf backend/__pycache__ backend/services/__pycache__'
bash start-flask.sh
```
**結果**: ❌ UI変更なし

### 2回目: VNC再起動
```bash
ssh ubuntu@153.126.154.158 'pkill -f Xvfb; pkill -f x11vnc; pkill -f websockify'
# VNC再起動コマンド実行
```
**結果**: ❌ UI変更なし

### 3回目: Playwrightプロセス確認
```bash
ps aux | grep playwright  # プロセスなし確認
ps aux | grep chromium    # ブラウザプロセスなし確認
```
**結果**: ❌ UI変更なし（新ブラウザインスタンスでも古いUI表示）

### 4回目: タスクリセット + 再実行
```bash
curl -X POST http://localhost:5001/api/simple/tasks/reset
curl -X POST http://localhost:5001/api/simple/tasks/30/execute
```
**結果**: ❌ UI変更なし

### 5回目: Flask完全再起動 + 全キャッシュ削除
```bash
pkill -f "python.*app.py"
rm -rf backend/__pycache__ backend/services/__pycache__ backend/api/__pycache__
bash start-flask.sh  # PID: 117272で起動
```
**結果**: ❌ UI変更なし

### 6回目: Playwrightキャッシュ無効化オプション追加
```bash
# automation_service.pyに以下を追加:
--disable-cache
--disk-cache-size=0
--disable-application-cache
```
**結果**: ❌ UI変更なし

### 7回目: DOM直接読み取り機能追加
```python
# page.evaluate()でパネルのtitle/instruction/fullTextを取得
panel_content = page.evaluate("() => { ... }")
```
**結果**: ⚠️ ログ出力が確認できず（printが表示されない）

---

## 🤔 根本原因の仮説

### 仮説1: ブラウザJavaScriptキャッシュ（最有力）
- Playwrightが起動するChromiumブラウザ自体がJavaScriptをキャッシュ
- `page.evaluate()`で実行されるJSコードはキャッシュの影響を受けないはずだが...
- **ユーザーデータディレクトリ**に古いデータが残っている可能性

### 仮説2: 別のコード箇所が実行されている
- 実は154行目のコードが実行されていない？
- 条件分岐で別のパスを通っている？

### 仮説3: Playwright Contextキャッシュ
- BrowserContextに古いデータが残っている
- `context.clear_cookies()`では消えないキャッシュ

---

## 🎯 次に試すべきアプローチ

### 優先度1: Playwright起動オプション確認・修正
- `--disable-cache`オプション追加
- `--incognito`モード追加
- ユーザーデータディレクトリを削除

### 優先度2: 直接JavaScriptコード実行確認
- VNCでブラウザコンソールを開いて手動実行
- `title.textContent`が実際に何になっているか確認

### 優先度3: 完全なコード再読み込み
- automation_service.pyを別名で保存→元に戻す（inode変更）
- Flaskをデバッグモードで起動してリロード

---

## 📊 作業時間
- 1日（約8時間以上）

## 😤 フラストレーションレベル
- 🔴🔴🔴🔴🔴 MAX

---

## MVP戦略の提案
**基本機能は完全に動作している**ため、UIテキストの問題のみで運用開始を検討すべき。
「完璧なUI < 動作する機能」の原則に従う。
