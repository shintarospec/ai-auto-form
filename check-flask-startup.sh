#!/bin/bash
# Flask起動確認スクリプト
# VPSでFlaskが正しく仮想環境で起動されているか確認

echo "🔍 Flask起動状態を確認します..."
echo ""

ssh ubuntu@153.126.154.158 'bash -s' <<'EOF'
echo "=== プロセス確認 ==="
FLASK_PID=$(pgrep -f "python.*app.py")
if [ -z "$FLASK_PID" ]; then
  echo "❌ Flaskプロセスが見つかりません"
  exit 1
else
  echo "✅ Flaskプロセス検出: PID $FLASK_PID"
  ps aux | grep "$FLASK_PID" | grep -v grep
fi

echo ""
echo "=== 仮想環境確認 ==="
# プロセスのコマンドライン引数から実行パスを確認
FLASK_CMD=$(ps -p $FLASK_PID -o args= | head -1)
if [[ "$FLASK_CMD" == *"/opt/ai-auto-form/venv/"* ]] || [[ "$FLASK_CMD" == *"./venv/"* ]]; then
  echo "✅ 仮想環境で起動されています: $FLASK_CMD"
else
  echo "❌ 警告: システムPythonで起動されています: $FLASK_CMD"
  echo "   正しい起動方法: bash start-flask.sh"
  exit 1
fi

echo ""
echo "=== API動作確認 ==="
RESPONSE=$(curl -s http://localhost:5001/api/simple/companies | head -100)
if [ -n "$RESPONSE" ]; then
  echo "✅ API正常応答"
  echo "$RESPONSE" | head -3
else
  echo "❌ API無応答"
  exit 1
fi

echo ""
echo "=== 起動ログ確認 ==="
if [ -f /opt/ai-auto-form/flask.log ]; then
  echo "最新ログ（直近10行）:"
  tail -10 /opt/ai-auto-form/flask.log
else
  echo "⚠️ flask.log が見つかりません"
fi
EOF

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ Flask起動状態: 正常"
else
  echo ""
  echo "❌ Flask起動状態: 異常"
  echo ""
  echo "修正方法:"
  echo "  ssh ubuntu@153.126.154.158 'cd /opt/ai-auto-form && pkill -9 -f python.*app.py && bash start-flask.sh'"
  exit 1
fi
