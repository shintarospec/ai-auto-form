#!/bin/bash
# xdotoolをVPSにインストール

echo "📦 xdotoolのインストールを開始します..."
sudo apt-get update
sudo apt-get install -y xdotool

echo "✅ インストール完了"
which xdotool
xdotool --version
