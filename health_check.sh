#\!/bin/bash
WEBHOOK_URL=$(grep DEEPBIZ_DISCORD_WEBHOOK_URL /opt/ai-auto-form/.env | cut -d= -f2)
LOG="/opt/ai-auto-form/test-results/20260302-retry-resume.log"

# 1. メモリチェック（available 100MB以下で警告）
AVAIL=$(free -m | awk '/Mem:/{print $7}')
if [ "$AVAIL" -lt 100 ]; then
    curl -s -H "Content-Type: application/json" \
      -d "{\"content\":\"🚨 [DeepBiz Send] メモリ警告: available=${AVAIL}MB. OOMリスクあり。\"}" \
      "$WEBHOOK_URL"
fi

# 2. Chromeプロセス数チェック（50以上で警告+自動掃除）
CHROME_COUNT=$(pgrep -c chrome 2>/dev/null || echo 0)
if [ "$CHROME_COUNT" -gt 50 ]; then
    curl -s -H "Content-Type: application/json" \
      -d "{\"content\":\"🚨 [DeepBiz Send] ゾンビChrome検出: ${CHROME_COUNT}個. 自動クリーンアップ実行。\"}" \
      "$WEBHOOK_URL"
    pkill -o chrome 2>/dev/null
    rm -rf /tmp/tmp* /tmp/.com.google.Chrome* 2>/dev/null
fi

# 3. バッチプロセス死活チェック
BATCH_PID=$(pgrep -f batch_send_all)
if [ -z "$BATCH_PID" ]; then
    if [ -f "$LOG" ] && find "$LOG" -mmin -30 | grep -q .; then
        curl -s -H "Content-Type: application/json" \
          -d "{\"content\":\"🚨 [DeepBiz Send] バッチプロセスが停止しています。手動確認が必要です。\"}" \
          "$WEBHOOK_URL"
    fi
fi
