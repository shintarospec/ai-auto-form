# AI AutoForm - VPS手動セットアップ手順

## VPS情報
- IP: 153.126.154.158
- ユーザー: ubuntu
- メモリ: 2GB
- OS: Ubuntu 24.04

## セットアップコマンド（VPS上で実行）

```bash
# SSH接続
ssh ubuntu@153.126.154.158

# 1. システム更新
sudo apt update && sudo apt upgrade -y

# 2. 必要なパッケージ
sudo apt install -y python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    docker.io docker-compose \
    git curl wget jq \
    xvfb x11vnc chromium-browser \
    fonts-noto-cjk fonts-noto-cjk-extra

# 3. Docker設定
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu

# 4. PostgreSQL設定
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 5. プロジェクトクローン
cd /opt
sudo git clone https://github.com/shintarospec/ai-auto-form.git
sudo chown -R ubuntu:ubuntu /opt/ai-auto-form

# 6. Python環境
cd /opt/ai-auto-form
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install playwright
playwright install chromium

# 7. PostgreSQL DB作成
sudo -u postgres psql -c "CREATE DATABASE ai_autoform;"
sudo -u postgres psql -c "CREATE USER autoform_user WITH PASSWORD 'secure_password_123';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ai_autoform TO autoform_user;"

# 8. 環境変数設定
cp .env.example .env
nano .env  # DB接続情報を編集

# 9. DB初期化
python backend/simple_migrate.py

# 10. サーバー起動
FLASK_APP=backend.app flask run --host=0.0.0.0 --port=5001
```

## または簡易版（Docker使用）

```bash
cd /opt/ai-auto-form
docker-compose up -d
```
