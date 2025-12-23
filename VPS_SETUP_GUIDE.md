# VPS初期セットアップガイド

## 📋 目次

1. [VPS契約後の初期設定](#vps契約後の初期設定)
2. [基本環境の構築](#基本環境の構築)
3. [アプリケーションのデプロイ](#アプリケーションのデプロイ)
4. [VNC環境の構築](#vnc環境の構築)
5. [動作確認](#動作確認)
6. [トラブルシューティング](#トラブルシューティング)

---

## VPS契約後の初期設定

### 1. SSH接続の確立

VPS契約後、以下の情報が提供されます：
- IPアドレス: `xxx.xxx.xxx.xxx`
- rootパスワード: (初期パスワード)

```bash
# ローカルマシンからSSH接続
ssh root@xxx.xxx.xxx.xxx
```

### 2. rootパスワードの変更

```bash
passwd
# 新しいパスワードを2回入力
```

### 3. システムアップデート

```bash
apt update && apt upgrade -y
```

### 4. 作業ユーザーの作成

```bash
# ユーザー作成
adduser appuser
# sudoグループに追加
usermod -aG sudo appuser

# SSH鍵認証の設定（推奨）
su - appuser
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# ローカルマシンで公開鍵を生成（既にある場合はスキップ）
# ssh-keygen -t ed25519 -C "your_email@example.com"

# 公開鍵をVPSにコピー（ローカルマシンから実行）
# ssh-copy-id appuser@xxx.xxx.xxx.xxx
```

### 5. ファイアウォールの設定

```bash
# UFWをインストール
apt install ufw -y

# 基本ルール設定
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 5001/tcp  # Flask API（テスト用、後で削除）
ufw allow 6080/tcp  # noVNC（テスト用、後で削除）

# ファイアウォール有効化
ufw enable
ufw status
```

---

## 基本環境の構築

### 1. 必要なパッケージのインストール

```bash
# 基本パッケージ
apt install -y \
    git \
    curl \
    wget \
    vim \
    build-essential \
    software-properties-common

# Python 3.12
apt install -y python3.12 python3.12-venv python3-pip

# Node.js（noVNC用）
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# PostgreSQL 16
apt install -y postgresql postgresql-contrib
```

### 2. PostgreSQLの設定

```bash
# PostgreSQLサービス起動
systemctl start postgresql
systemctl enable postgresql

# データベースとユーザー作成
sudo -u postgres psql << EOF
CREATE DATABASE ai_autoform;
CREATE USER appuser WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE ai_autoform TO appuser;
\q
EOF

# リモート接続設定（必要な場合）
vim /etc/postgresql/16/main/postgresql.conf
# listen_addresses = 'localhost' を確認

vim /etc/postgresql/16/main/pg_hba.conf
# local接続を許可
# local   all             appuser                                 md5

# PostgreSQL再起動
systemctl restart postgresql
```

---

## アプリケーションのデプロイ

### 1. Gitリポジトリのクローン

```bash
# 作業ディレクトリ作成
sudo mkdir -p /opt/ai-auto-form
sudo chown appuser:appuser /opt/ai-auto-form

# appuserでログイン
su - appuser
cd /opt/ai-auto-form

# リポジトリクローン（プライベートリポジトリの場合）
git clone https://github.com/shintarospec/ai-auto-form.git .

# または、GitHub CLIを使用
gh auth login
gh repo clone shintarospec/ai-auto-form .
```

### 2. Python仮想環境の構築

```bash
cd /opt/ai-auto-form

# 仮想環境作成
python3.12 -m venv venv

# 仮想環境有効化
source venv/bin/activate

# 依存パッケージインストール
pip install --upgrade pip
pip install -r requirements.txt

# Playwrightのインストール
playwright install chromium
playwright install-deps chromium
```

### 3. 環境変数の設定

```bash
# .envファイル作成
cat > /opt/ai-auto-form/.env << 'EOF'
# Database
DATABASE_URL=postgresql://appuser:your_secure_password@localhost:5432/ai_autoform

# Flask
FLASK_ENV=production
SECRET_KEY=your-secret-key-here-change-this
JWT_SECRET_KEY=your-jwt-secret-key-here-change-this

# API Keys（Phase 3で使用）
GEMINI_API_KEY=your-gemini-api-key

# VNC Settings
DISPLAY=:99
VNC_PASSWORD=your-vnc-password
EOF

# パーミッション設定
chmod 600 .env
```

### 4. データベース初期化

```bash
source venv/bin/activate
cd /opt/ai-auto-form

# Phase 1 MVPテーブルの作成
PYTHONPATH=/opt/ai-auto-form python backend/simple_migrate.py

# 実行結果を確認
# ✅ Tables created successfully!
# ✅ Added 5 companies
# ✅ Added 2 products
# ✅ Added 10 tasks
```

---

## VNC環境の構築

### 1. VNCパッケージのインストール

```bash
# X Window System
apt install -y \
    xvfb \
    x11vnc \
    x11-utils \
    xfonts-base \
    xfonts-75dpi \
    xfonts-100dpi

# 軽量ウィンドウマネージャー
apt install -y \
    fluxbox \
    xterm

# noVNC（Webブラウザ経由でVNC接続）
apt install -y websockify
cd /opt
git clone https://github.com/novnc/noVNC.git
cd noVNC
npm install
```

### 2. VNCサービスの作成

#### Xvfbサービス

```bash
sudo tee /etc/systemd/system/xvfb.service << 'EOF'
[Unit]
Description=X Virtual Frame Buffer
After=network.target

[Service]
Type=simple
User=appuser
Environment=DISPLAY=:99
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

#### x11vncサービス

```bash
# VNCパスワード作成
su - appuser
x11vnc -storepasswd your-vnc-password ~/.vnc/passwd
exit

sudo tee /etc/systemd/system/x11vnc.service << 'EOF'
[Unit]
Description=x11vnc VNC Server
After=xvfb.service
Requires=xvfb.service

[Service]
Type=simple
User=appuser
Environment=DISPLAY=:99
ExecStart=/usr/bin/x11vnc -display :99 -rfbauth /home/appuser/.vnc/passwd -rfbport 5900 -shared -forever -loop
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

#### noVNCサービス

```bash
sudo tee /etc/systemd/system/novnc.service << 'EOF'
[Unit]
Description=noVNC Web VNC Client
After=x11vnc.service
Requires=x11vnc.service

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/noVNC
ExecStart=/usr/bin/websockify --web=/opt/noVNC 6080 localhost:5900
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 3. サービスの起動

```bash
# systemdリロード
systemctl daemon-reload

# サービス有効化と起動
systemctl enable xvfb x11vnc novnc
systemctl start xvfb
systemctl start x11vnc
systemctl start novnc

# 状態確認
systemctl status xvfb
systemctl status x11vnc
systemctl status novnc
```

---

## アプリケーションサービスの作成

### 1. Flaskサービス

```bash
sudo tee /etc/systemd/system/ai-autoform-api.service << 'EOF'
[Unit]
Description=AI AutoForm Flask API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/ai-auto-form
Environment=PYTHONPATH=/opt/ai-auto-form
Environment=FLASK_APP=backend.app
Environment=FLASK_ENV=production
ExecStart=/opt/ai-auto-form/venv/bin/python -m flask run --host=0.0.0.0 --port=5001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ai-autoform-api
systemctl start ai-autoform-api
systemctl status ai-autoform-api
```

### 2. Nginxリバースプロキシ

```bash
# Nginxインストール
apt install -y nginx

# 設定ファイル作成
sudo tee /etc/nginx/sites-available/ai-autoform << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # ドメインまたはIPアドレス

    # Static files
    location / {
        root /opt/ai-auto-form;
        index simple-console.html;
        try_files $uri $uri/ =404;
    }

    # Flask API
    location /api/ {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Screenshots
    location /screenshots/ {
        alias /opt/ai-auto-form/screenshots/;
    }

    # noVNC WebSocket
    location /vnc/ {
        proxy_pass http://localhost:6080/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
EOF

# シンボリックリンク作成
ln -s /etc/nginx/sites-available/ai-autoform /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Nginx設定テスト
nginx -t

# Nginx再起動
systemctl restart nginx
systemctl enable nginx
```

---

## 動作確認

### 1. サービス状態確認

```bash
# 全サービスの状態確認
systemctl status postgresql
systemctl status xvfb
systemctl status x11vnc
systemctl status novnc
systemctl status ai-autoform-api
systemctl status nginx
```

### 2. ポート確認

```bash
# リスニングポート確認
ss -tulpn | grep -E '5432|5900|6080|5001|80'

# 期待される出力:
# 5432 - PostgreSQL
# 5900 - x11vnc
# 6080 - noVNC
# 5001 - Flask API
# 80   - Nginx
```

### 3. API動作確認

```bash
# ローカルでテスト
curl http://localhost:5001/api/health

# 外部からテスト（ローカルマシンから）
curl http://xxx.xxx.xxx.xxx/api/health
```

### 4. VNC接続テスト

ブラウザで以下のURLにアクセス：
```
http://xxx.xxx.xxx.xxx/vnc/vnc.html
```

パスワードを入力してVNC画面が表示されることを確認

### 5. アプリケーション動作確認

```
http://xxx.xxx.xxx.xxx/simple-console.html
```

1. タスク一覧が表示される
2. タスクをクリックして詳細表示
3. 「🤖 自動入力実行」をクリック
4. VNC画面でブラウザが起動し、フォーム入力される
5. 手動でreCAPTCHAを解決し、送信ボタンをクリック
6. 「✅ 送信完了」をクリックしてタスク完了

---

## トラブルシューティング

### VNC画面が表示されない

```bash
# サービス状態確認
systemctl status xvfb x11vnc novnc

# ログ確認
journalctl -u xvfb -f
journalctl -u x11vnc -f
journalctl -u novnc -f

# DISPLAYが設定されているか確認
echo $DISPLAY  # :99

# Xvfbプロセス確認
ps aux | grep Xvfb
```

### Playwright自動化が動かない

```bash
# Chromiumインストール確認
playwright install chromium
playwright install-deps chromium

# DISPLAYを明示的に設定
export DISPLAY=:99
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); browser = p.chromium.launch(headless=False); browser.close()"
```

### API接続エラー

```bash
# Flaskログ確認
journalctl -u ai-autoform-api -f

# データベース接続確認
psql -U appuser -d ai_autoform -h localhost -c "SELECT COUNT(*) FROM simple_tasks;"

# ファイアウォール確認
ufw status
```

### PostgreSQL接続エラー

```bash
# PostgreSQL状態確認
systemctl status postgresql

# 接続テスト
psql -U appuser -d ai_autoform -h localhost

# pg_hba.conf確認
cat /etc/postgresql/16/main/pg_hba.conf | grep appuser

# ログ確認
tail -f /var/log/postgresql/postgresql-16-main.log
```

---

## セキュリティ強化（本番運用時）

### 1. SSL/TLS証明書（Let's Encrypt）

```bash
apt install -y certbot python3-certbot-nginx

# 証明書取得
certbot --nginx -d your-domain.com

# 自動更新設定
systemctl status certbot.timer
```

### 2. fail2ban（ブルートフォース攻撃対策）

```bash
apt install -y fail2ban

# 設定ファイル作成
cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

# SSH保護を有効化
vim /etc/fail2ban/jail.local
# [sshd]
# enabled = true

systemctl enable fail2ban
systemctl start fail2ban
```

### 3. 定期バックアップ

```bash
# バックアップスクリプト作成
cat > /home/appuser/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/home/appuser/backups
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# データベースバックアップ
pg_dump -U appuser ai_autoform > $BACKUP_DIR/db_$DATE.sql

# 古いバックアップ削除（7日以上前）
find $BACKUP_DIR -name "db_*.sql" -mtime +7 -delete
EOF

chmod +x /home/appuser/backup.sh

# cron設定（毎日3:00にバックアップ）
(crontab -l 2>/dev/null; echo "0 3 * * * /home/appuser/backup.sh") | crontab -
```

---

## 次のステップ

VPS環境が構築できたら：

1. [PHASE1_MVP_GUIDE.md](PHASE1_MVP_GUIDE.md) を参照してPhase 1の動作確認
2. VNC画面でPlaywright自動化をテスト
3. [DEVELOPMENT_SCHEDULE_V2.md](DEVELOPMENT_SCHEDULE_V2.md) に従ってPhase 2を実装

---

**作成日**: 2025年12月21日  
**対象**: さくらVPS 1G/2Gプラン  
**OS**: Ubuntu 22.04/24.04 LTS  
**前提**: Phase 1 MVP完成済み
