#!/bin/bash
# Flask確実再起動スクリプト（VPS用）

echo "🔄 Flask再起動を開始します..."

# 1. automation_service.pyをVPSに転送
echo "📤 コードをVPSに転送中..."
scp /workspaces/ai-auto-form/backend/services/automation_service.py ubuntu@153.126.154.158:/opt/ai-auto-form/backend/services/
if [ $? -ne 0 ]; then
    echo "❌ ファイル転送に失敗しました"
    exit 1
fi
echo "✅ 転送完了"

# 2. Flaskプロセスを強制停止
echo "🛑 既存のFlaskプロセスを停止中..."
ssh ubuntu@153.126.154.158 'pkill -9 -f "python.*app.py"'
sleep 2

# 3. Pythonキャッシュを完全削除
echo "🗑️  Pythonキャッシュを削除中..."
ssh ubuntu@153.126.154.158 'cd /opt/ai-auto-form && find . -name "*.pyc" -delete && find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; echo "キャッシュ削除完了"'

# 4. Flask起動（仮想環境を使用するためstart-flask.shを必ず使う）
echo "🚀 Flaskを起動中..."
ssh ubuntu@153.126.154.158 'cd /opt/ai-auto-form && bash start-flask.sh'
sleep 5
echo "⏳ Flask初期化待機中..."

# 5. 起動確認
echo "✅ プロセス確認中..."
ssh ubuntu@153.126.154.158 'ps aux | grep "python.*app.py" | grep -v grep'
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Flask再起動成功！"
    echo ""
    echo "📋 次のステップ:"
    echo "  1. http://153.126.154.158:8000/simple-console.html を開く"
    echo "  2. タスクを実行してVNC画面で変更を確認"
    echo ""
else
    echo "❌ Flaskの起動に失敗しました"
    exit 1
fi
