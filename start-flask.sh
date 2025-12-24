#!/bin/bash
cd /opt/ai-auto-form
source venv/bin/activate
export PYTHONPATH=/opt/ai-auto-form
export PORT=5001
nohup python backend/app.py > flask.log 2>&1 &
echo "Flask started with PID: $!"
