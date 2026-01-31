#!/bin/bash
cd /opt/ai-auto-form
source venv/bin/activate

# .envファイルから環境変数を読み込む
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

export PYTHONPATH=/opt/ai-auto-form
export PORT=5001
export PYTHONUNBUFFERED=1  # print出力をバッファリングせずにログに出力
# 仮想環境のPythonを明示的に使用
nohup ./venv/bin/python backend/app.py > flask.log 2>&1 &
echo "Flask started with PID: $!"
