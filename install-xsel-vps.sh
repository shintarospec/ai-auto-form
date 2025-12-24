#!/bin/bash
# xselをVPSにインストール

echo "📦 xselのインストールを開始します..."
sudo apt-get update
sudo apt-get install -y xsel

echo "✅ インストール完了"
which xsel
