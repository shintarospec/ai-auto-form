# VPS移行チェックリスト

## 📦 現在の実装状況（Codespaces）

### ✅ 完成済み
- PostgreSQL DB（7テーブル）
- Flask API（全エンドポイント）
- Worker Console（HTML UI）
- Admin Console（HTML UI）
- Playwright自動化（フォーム入力）
- Gemini AI連携準備
- VNCスクリプト（start-vnc.sh）

### ⚠️ VPS環境で検証必要
- noVNC接続（Codespacesでは動作不可）
- リアルタイムブラウザビュー
- reCAPTCHA対応
- 大量タスク並行処理

---

## 🔄 VPS移行時の変更点

### 1. 環境変数

**Codespaces → VPS**

```bash
# Codespaces（自動設定）
CODESPACE_NAME=laughing-spoon-x5gwpjvxr5w72vpv4

# VPS（手動設定）
USE_VNC=true
DISPLAY=:99
DATABASE_URL=postgresql://aiuser:password@localhost:5432/ai_autoform
SECRET_KEY=your_random_secret_key
```

### 2. URL生成ロジック

**frontend/js/api.js**
```javascript
// Codespaces
if (currentHost.includes('app.github.dev')) {
    API_BASE_URL = window.location.protocol + '//' + 
        currentHost.replace('-8000.', '-5001.') + '/api';
}
// VPS追加
else if (currentHost.includes('your-domain.com')) {
    API_BASE_URL = 'http://your-domain.com/api';
}
```

**worker-console.html**
```javascript
// VNC URL生成
if (hostname.includes('app.github.dev')) {
    // Codespaces
    noVncUrl = `https://${baseHost}-6080.app.github.dev/vnc.html`;
} else {
    // VPS
    noVncUrl = `http://${hostname}/vnc/vnc.html?autoconnect=true`;
}
```

### 3. Nginx設定

Codespacesでは不要だったリバースプロキシが必要：

```nginx
location /api { proxy_pass http://localhost:5001; }
location /vnc { proxy_pass http://localhost:6080; }
```

---

## 📂 VPSで必要なファイル

### 移行済み
- ✅ `start-vnc.sh` - VNC起動スクリプト
- ✅ `VPS_DEPLOYMENT.md` - セットアップガイド
- ✅ `HANDOFF.md` - 技術仕様
- ✅ `requirements.txt` - Python依存関係
- ✅ `docker-compose.yml` - PostgreSQL

### VPSで追加作成
- [ ] `systemd/ai-autoform-vnc.service`
- [ ] `systemd/ai-autoform-api.service`
- [ ] `nginx/ai-autoform.conf`
- [ ] `.env` (本番環境変数)

---

## 🧪 VPS展開後のテスト手順

### Phase 1: 基本動作確認（30分）

```bash
# 1. サービス起動確認
sudo systemctl status ai-autoform-vnc
sudo systemctl status ai-autoform-api
sudo systemctl status nginx

# 2. API疎通確認
curl http://localhost:5001/api/health
curl http://YOUR_VPS_IP/api/health

# 3. VNC表示確認
# ブラウザで http://YOUR_VPS_IP/vnc/vnc.html にアクセス
```

### Phase 2: フロントエンド確認（30分）

```bash
# 1. Worker Consoleアクセス
http://YOUR_VPS_IP/worker-console.html

# 2. ワーカー選択可能か確認

# 3. ブラウザビュー（VNC iframe）が表示されるか確認
```

### Phase 3: 自動化テスト（1時間）

```bash
# 1. テストフォームアクセス
http://YOUR_VPS_IP/test-contact-form.html

# 2. 「自動送信スタート」実行

# 3. VNC画面でChromium表示確認

# 4. フォーム自動入力確認

# 5. reCAPTCHA対応テスト（手動突破）

# 6. 送信完了検知確認
```

### Phase 4: 負荷テスト（1時間）

```bash
# 複数ワーカーで同時タスク実行
# - 3人のワーカーが3タスクを同時実行
# - VNC画面が正常に表示されるか
# - Playwright衝突がないか
# - PostgreSQL接続プール問題ないか
```

---

## ⚠️ 想定される問題と対策

### 問題1: VNC画面が表示されない
**原因**: Xvfb未起動、ポート競合
**対策**: 
```bash
ps aux | grep Xvfb
sudo systemctl restart ai-autoform-vnc
tail -f /tmp/x11vnc.log
```

### 問題2: Playwright起動失敗
**原因**: Chromiumパッケージ不足
**対策**:
```bash
playwright install-deps chromium
sudo apt install -y chromium-browser fonts-noto-cjk
```

### 問題3: DB接続エラー
**原因**: PostgreSQL認証設定
**対策**:
```bash
sudo vim /etc/postgresql/*/main/pg_hba.conf
# local all all trust → md5 に変更
sudo systemctl restart postgresql
```

### 問題4: Nginx 502 Bad Gateway
**原因**: Flask API未起動
**対策**:
```bash
sudo journalctl -u ai-autoform-api -n 50
sudo systemctl restart ai-autoform-api
```

---

## 🎯 成功基準

VPS展開が成功したと言えるのは：

- [ ] すべてのサービスが`systemctl`で自動起動
- [ ] Worker Consoleでワーカー選択可能
- [ ] VNC画面でChromiumブラウザが表示される
- [ ] 「自動送信スタート」でフォーム自動入力成功
- [ ] ワーカーがVNC画面でreCAPTCHA対応可能
- [ ] 送信完了後、ポイントが正しく付与される
- [ ] 3人の同時タスク実行で問題なし

---

## 📞 次のステップ

1. **VPS準備**（ユーザー作業）
   - さくらVPS契約
   - Ubuntu 22.04/24.04インストール
   - SSH接続設定

2. **初期セットアップ**（30分）
   - `VPS_DEPLOYMENT.md` の手順1-5を実行
   - PostgreSQL、Python環境構築

3. **サービス起動**（30分）
   - 手順6-8を実行
   - systemdサービス設定

4. **動作確認**（2時間）
   - Phase 1-4のテスト実行
   - 問題があれば修正

5. **本番運用開始**
   - SSL証明書設定
   - ドメイン設定
   - 監視・バックアップ設定

---

**VPS準備ができたら、`VPS_DEPLOYMENT.md`の手順に沿って展開してください！**
