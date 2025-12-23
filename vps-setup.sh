#!/bin/bash
# AI AutoForm - VPS自動セットアップスクリプト
# 対象: Worker VPS (ubuntu@153.126.154.158)

set -e  # エラー時に停止

echo "=========================================="
echo "AI AutoForm - VPS Setup Script"
echo "=========================================="

# 1. システム更新
echo "[1/7] システム更新中..."
sudo apt update && sudo apt upgrade -y

# 2. 必要なパッケージインストール
echo "[2/7] パッケージインストール中..."
sudo apt install -y \
    python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    docker.io docker-compose \
    git curl wget jq \
    xvfb x11vnc \
    chromium-browser \
    fonts-noto-cjk fonts-noto-cjk-extra

# 3. Dockerサービス開始
echo "[3/7] Docker設定中..."
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# 4. PostgreSQL設定
echo "[4/7] PostgreSQL設定中..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 5. プロジェクトクローン
echo "[5/7] プロジェクトクローン中..."
cd /opt
sudo git clone https://github.com/shintarospec/ai-auto-form.git || echo "既にクローン済み"
sudo chown -R ubuntu:ubuntu /opt/ai-auto-form

# 6. Python仮想環境構築
echo "[6/7] Python環境構築中..."
cd /opt/ai-auto-form
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install playwright
playwright install chromium

# 7. PostgreSQLデータベース作成
echo "[7/7] データベース作成中..."
sudo -u postgres psql << EOF
CREATE DATABASE ai_autoform;
CREATE USER autoform_user WITH PASSWORD 'secure_password_123';
GRANT ALL PRIVILEGES ON DATABASE ai_autoform TO autoform_user;
EOF

echo ""
echo "=========================================="
echo "✅ セットアップ完了！"
echo "=========================================="
echo ""
echo "次のステップ："
echo "1. 環境変数設定: cp .env.example .env"
echo "2. DB初期化: python backend/simple_migrate.py"
echo "3. サーバー起動: FLASK_APP=backend.app flask run --host=0.0.0.0 --port=5001"
echo ""
