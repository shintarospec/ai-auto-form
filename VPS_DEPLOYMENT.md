# AI AutoForm - VPS展開ガイド

## 📋 前提条件

- **VPS**: さくらVPS（Ubuntu 22.04/24.04推奨）
- **メモリ**: 4GB以上推奨
- **CPU**: 2コア以上推奨
- **ストレージ**: 20GB以上

---

## 🚀 セットアップ手順

### 1. システム更新とパッケージインストール

```bash
# システム更新
sudo apt update && sudo apt upgrade -y

# 必要なパッケージ
sudo apt install -y \
    python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    docker.io docker-compose \
    git curl wget \
    xvfb x11vnc \
    chromium-browser chromium-chromedriver \
    fonts-noto-cjk fonts-noto-cjk-extra
```

### 2. noVNCインストール

```bash
# noVNC
sudo apt install -y novnc websockify

# または最新版をGitHubから
cd /opt
sudo git clone https://github.com/novnc/noVNC.git
sudo git clone https://github.com/novnc/websockify.git
cd websockify
sudo python3 setup.py install
```

### 3. プロジェクトデプロイ

```bash
# プロジェクトクローン
cd /opt
sudo git clone https://github.com/shintarospec/ai-auto-form.git
cd ai-auto-form

# 所有権変更
sudo chown -R $USER:$USER /opt/ai-auto-form

# Python仮想環境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 4. PostgreSQL設定

```bash
# PostgreSQLユーザー作成
sudo -u postgres psql -c "CREATE USER aiuser WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "CREATE DATABASE ai_autoform OWNER aiuser;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ai_autoform TO aiuser;"
```

### 5. 環境変数設定

```bash
# .envファイル作成
cat > /opt/ai-auto-form/.env << 'EOF'
# Database
DATABASE_URL=postgresql://aiuser:your_secure_password@localhost:5432/ai_autoform

# Flask
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=your_random_secret_key_here

# Gemini API (オプション)
GEMINI_API_KEY=your_gemini_api_key_here

# VNC設定
USE_VNC=true
DISPLAY=:99
EOF
```

### 6. VNCサービス設定（systemd）

```bash
# VNCサービスファイル
sudo tee /etc/systemd/system/ai-autoform-vnc.service << 'EOF'
[Unit]
Description=AI AutoForm VNC Server
After=network.target

[Service]
Type=forking
User=YOUR_USERNAME
WorkingDirectory=/opt/ai-auto-form
ExecStart=/opt/ai-auto-form/start-vnc.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# YOUR_USERNAMEを実際のユーザー名に置換
sudo sed -i "s/YOUR_USERNAME/$USER/g" /etc/systemd/system/ai-autoform-vnc.service

# サービス有効化
sudo systemctl daemon-reload
sudo systemctl enable ai-autoform-vnc
sudo systemctl start ai-autoform-vnc
```

### 7. Flask APIサービス設定

```bash
# Flaskサービスファイル
sudo tee /etc/systemd/system/ai-autoform-api.service << 'EOF'
[Unit]
Description=AI AutoForm Flask API
After=network.target postgresql.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/opt/ai-auto-form
Environment="PATH=/opt/ai-auto-form/venv/bin"
Environment="PYTHONPATH=/opt/ai-auto-form"
Environment="DISPLAY=:99"
ExecStart=/opt/ai-auto-form/venv/bin/python backend/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# YOUR_USERNAMEを実際のユーザー名に置換
sudo sed -i "s/YOUR_USERNAME/$USER/g" /etc/systemd/system/ai-autoform-api.service

# サービス有効化
sudo systemctl daemon-reload
sudo systemctl enable ai-autoform-api
sudo systemctl start ai-autoform-api
```

### 8. Nginx設定（リバースプロキシ）

```bash
# Nginxインストール
sudo apt install -y nginx

# 設定ファイル
sudo tee /etc/nginx/sites-available/ai-autoform << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # ドメインまたはIPアドレス

    # フロントエンド（静的ファイル）
    location / {
        root /opt/ai-auto-form;
        index worker-console.html admin-console.html;
        try_files $uri $uri/ =404;
    }

    # Flask API
    location /api {
        proxy_pass http://localhost:5001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # noVNC (WebSocket)
    location /vnc {
        proxy_pass http://localhost:6080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

# 設定有効化
sudo ln -s /etc/nginx/sites-available/ai-autoform /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 9. ファイアウォール設定

```bash
# UFWファイアウォール
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (SSL設定後)
sudo ufw enable
```

---

## 🔍 動作確認

### 1. サービス状態確認

```bash
# VNCサーバー
sudo systemctl status ai-autoform-vnc
ps aux | grep -E "Xvfb|x11vnc|websockify"

# Flask API
sudo systemctl status ai-autoform-api
curl http://localhost:5001/api/health

# Nginx
sudo systemctl status nginx
```

### 2. ブラウザアクセス

- **Worker Console**: `http://your-vps-ip/worker-console.html`
- **Admin Console**: `http://your-vps-ip/admin-console.html`
- **noVNC**: `http://your-vps-ip/vnc/vnc.html`
- **API Health**: `http://your-vps-ip/api/health`

---

## 🔧 トラブルシューティング

### VNC画面が表示されない

```bash
# VNCログ確認
tail -f /tmp/x11vnc.log
tail -f /tmp/websockify.log

# プロセス再起動
sudo systemctl restart ai-autoform-vnc
```

### Flask APIが起動しない

```bash
# ログ確認
sudo journalctl -u ai-autoform-api -f

# 手動起動テスト
cd /opt/ai-auto-form
source venv/bin/activate
DISPLAY=:99 python backend/app.py
```

### PostgreSQL接続エラー

```bash
# PostgreSQL起動確認
sudo systemctl status postgresql

# 接続テスト
psql -U aiuser -d ai_autoform -h localhost
```

---

## 🔒 セキュリティ（本番運用時）

### 1. SSL証明書（Let's Encrypt）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 2. VNCパスワード設定

```bash
# start-vnc.shを編集してパスワード追加
x11vnc -display :99 -rfbauth ~/.vnc/passwd ...
```

### 3. ファイアウォール強化

```bash
# 特定IPのみ許可（例：オフィスIP）
sudo ufw allow from YOUR_OFFICE_IP to any port 80
```

---

## 📊 監視・メンテナンス

### ログローテーション

```bash
sudo tee /etc/logrotate.d/ai-autoform << 'EOF'
/opt/ai-auto-form/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

### 自動バックアップ

```bash
# cronでDB自動バックアップ
crontab -e

# 毎日午前3時にバックアップ
0 3 * * * pg_dump -U aiuser ai_autoform > /backup/ai_autoform_$(date +\%Y\%m\%d).sql
```

---

## ✅ チェックリスト

VPS展開前に確認：

- [ ] システムパッケージ更新完了
- [ ] PostgreSQL設定完了
- [ ] Python環境構築完了
- [ ] VNCサービス起動確認
- [ ] Flask API起動確認
- [ ] Nginx設定完了
- [ ] ファイアウォール設定完了
- [ ] ブラウザからアクセス確認
- [ ] noVNC画面表示確認
- [ ] テストタスク実行成功

---

## 🆘 サポート

問題が発生した場合：
1. ログファイルを確認（`/tmp/*.log`, `journalctl`）
2. サービス状態を確認（`systemctl status`）
3. HANDOFF.mdを参照
