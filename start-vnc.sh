#!/bin/bash
# AI AutoForm - VNC Server Startup Script
# Phase 1: VNC環境セットアップ

echo "🚀 Starting VNC environment for AI AutoForm..."

# 既存のプロセスをクリーンアップ
pkill -f Xvfb
pkill -f x11vnc
pkill -f websockify
sleep 2

# 1. Xvfb起動（仮想ディスプレイ :99, 解像度 1920x1080）
echo "📺 Starting Xvfb (virtual display :99, 1920x1080)..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension RANDR +extension GLX +render -noreset &
XVFB_PID=$!
sleep 2

# DISPLAY環境変数を設定
export DISPLAY=:99

# キーボード設定を適用
echo "⌨️  Configuring keyboard layout..."
export DISPLAY=:99
setxkbmap -display :99 us 2>/dev/null || echo "⚠️  setxkbmap not available (will use defaults)"

# 2. VNCサーバー起動（ポート5900）
echo "🖥️  Starting VNC server (port 5900)..."
x11vnc -display :99 -forever -shared -rfbport 5900 -nopw &
VNC_PID=$!
sleep 2

# 3. noVNC起動（ポート6080、Webブラウザアクセス用）
echo "🌐 Starting noVNC (port 6080)..."
websockify --web /usr/share/novnc 6080 localhost:5900 &
WEBSOCKIFY_PID=$!
sleep 2

# 動作確認
if ps -p $XVFB_PID > /dev/null && ps -p $VNC_PID > /dev/null && ps -p $WEBSOCKIFY_PID > /dev/null; then
    echo "✅ VNC environment started successfully!"
    echo ""
    echo "📋 Process Information:"
    echo "  - Xvfb: PID $XVFB_PID (DISPLAY=:99)"
    echo "  - x11vnc: PID $VNC_PID (port 5900)"
    echo "  - websockify: PID $WEBSOCKIFY_PID (port 6080)"
    echo ""
    echo "🌐 Access noVNC:"
    echo "  - Local: http://localhost:6080/vnc.html"
    echo "  - Codespaces: https://[your-codespace]-6080.app.github.dev/vnc.html"
    echo ""
    echo "⚠️  Important: Set port 6080 to 'Public' in VS Code Ports panel"
    echo ""
    echo "🔍 To test the display:"
    echo "  DISPLAY=:99 xterm &"
    echo ""
else
    echo "❌ Failed to start VNC environment"
    exit 1
fi
