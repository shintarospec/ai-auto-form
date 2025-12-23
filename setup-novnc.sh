#!/bin/bash
set -e

echo "🚀 noVNC環境セットアップ開始..."

# 1. 必要なパッケージをインストール
echo "📦 パッケージインストール中..."
sudo apt update
sudo DEBIAN_FRONTEND=noninteractive apt install -y \
    xfce4 \
    xfce4-goodies \
    tigervnc-standalone-server \
    tigervnc-common \
    novnc \
    websockify \
    dbus-x11

# 2. VNCパスワード設定（自動）
echo "🔐 VNCパスワード設定中..."
mkdir -p ~/.vnc
echo "password" | vncpasswd -f > ~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# 3. VNC起動設定
echo "⚙️  VNC設定ファイル作成中..."
cat > ~/.vnc/xstartup << 'XSTARTUP'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startxfce4
XSTARTUP
chmod +x ~/.vnc/xstartup

# 4. VNCサーバー起動
echo "🖥️  VNCサーバー起動中..."
vncserver :1 -geometry 1920x1080 -depth 24 -localhost no

# 5. noVNC起動
echo "🌐 noVNCサーバー起動中..."
websockify -D --web=/usr/share/novnc/ 6080 localhost:5901

echo ""
echo "✅ セットアップ完了！"
echo ""
echo "📍 アクセス方法:"
echo "   1. Codespacesの「ポート」タブで 6080 を「Public」に変更"
echo "   2. ブラウザで以下にアクセス:"
echo "      https://YOUR-CODESPACE-6080.app.github.dev/vnc.html"
echo ""
echo "🔑 VNCパスワード: password"
echo ""

