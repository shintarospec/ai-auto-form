#!/usr/bin/env python3
"""
全件バッチ送信（dry-run={args.dry_run}）
auto / no reCAPTCHA / ai_analyzed / pending

使い方: cd /opt/ai-auto-form && source venv/bin/activate && python3 batch_send_all.py --product-id 9 [--limit 50]
"""

import argparse
import requests
import json
import time
import os
import sys
import psycopg2
from datetime import datetime

# 引数パース
parser = argparse.ArgumentParser(description="全件バッチ送信")
parser.add_argument('--product-id', type=int, required=True, help="対象Product ID")
parser.add_argument('--limit', type=int, default=0, help="送信件数上限（0=全件）")
parser.add_argument('--dry-run', action='store_true', help='dry-runモード（入力のみ、送信しない）')
args = parser.parse_args()

# 設定
FLASK_URL = "http://localhost:5001"
PRODUCT_ID = args.product_id
RESULT_DIR = "/opt/ai-auto-form/test-results"
LOG_FILE = f"{RESULT_DIR}/20260227-batch-send-all.log"
RESULT_FILE = f"{RESULT_DIR}/20260227-batch-send-all.json"
DISCORD_WEBHOOK = os.environ.get("DEEPBIZ_DISCORD_WEBHOOK_URL", "")

# 通知間隔
DISCORD_INTERVAL = 500    # Discord通知間隔（件数）
SAVE_INTERVAL = 100       # 中間保存間隔（件数）
TASK_DELAY = 1            # タスク間待機（秒）
MAX_TOTAL_RETRIES = 3     # バッチ間の合計リトライ上限


class Logger:
    """stdout + ファイル同時出力"""
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log = open(log_path, "a", buffering=1)

    def write(self, msg):
        self.terminal.write(msg)
        self.log.write(msg)

    def flush(self):
        self.terminal.flush()
        self.log.flush()


def send_discord(message):
    if not DISCORD_WEBHOOK:
        print(f"[Discord skip] {message[:80]}")
        return
    try:
        # Discord 2000文字制限
        requests.post(DISCORD_WEBHOOK, json={"content": message[:2000]}, timeout=10)
    except Exception as e:
        print(f"[Discord error] {e}")


def load_webhook():
    global DISCORD_WEBHOOK
    if not DISCORD_WEBHOOK:
        env_path = "/opt/ai-auto-form/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("DEEPBIZ_DISCORD_WEBHOOK_URL="):
                        DISCORD_WEBHOOK = line.strip().split("=", 1)[1]


def get_target_tasks():
    conn = psycopg2.connect(
        "postgresql://autoform_user:secure_password_123@localhost:5432/ai_autoform"
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, c.name, c.form_url, t.form_data
        FROM simple_tasks t
        JOIN simple_companies c ON t.company_id = c.id
        WHERE t.product_id = %s
          AND t.automation_type = 'auto'
          AND (t.recaptcha_type IS NULL OR t.recaptcha_type IN ('none', 'v3'))
          AND t.form_analysis IS NOT NULL
          AND (t.form_analysis::json->>'field_count')::int > 1
          AND t.status = 'pending'
          AND c.form_url NOT LIKE 'mailto:%%'
          AND c.form_url NOT LIKE '%%herp.careers%%'
          AND c.form_url NOT LIKE '%%wantedly.com%%'
          AND c.form_url NOT LIKE '%%hrmos.co%%'
          AND c.form_url NOT LIKE '%%en-gage.net%%'
          AND c.form_url NOT LIKE '%%.pdf'
          AND c.form_url NOT LIKE '%%.doc%%'
        ORDER BY t.id
    """, (PRODUCT_ID,))
    rows = cur.fetchall()

    # retry_count上限チェック: 超過タスクをpermanently_failedに更新
    tasks = []
    skipped_count = 0
    for task_id, name, url, form_data in rows:
        fd = form_data if isinstance(form_data, dict) else (json.loads(form_data) if form_data else {})
        retry_count = fd.get('retry_count', 0)
        if retry_count >= MAX_TOTAL_RETRIES:
            cur.execute(
                "UPDATE simple_tasks SET status = 'permanently_failed' WHERE id = %s",
                (task_id,)
            )
            skipped_count += 1
        else:
            tasks.append((task_id, name, url))

    if skipped_count > 0:
        conn.commit()
        print(f"⚠️ リトライ上限({MAX_TOTAL_RETRIES}回)超過: {skipped_count}件をpermanently_failedに更新")

    conn.close()
    return tasks


def execute_task(task_id):
    try:
        resp = requests.post(
            f"{FLASK_URL}/api/simple/tasks/{task_id}/auto-execute",
            json={"headless": True, "dry_run": args.dry_run},
            timeout=180
        )
        return resp.json()
    except requests.exceptions.Timeout:
        return {
            "success": False, "task_id": task_id,
            "error_message": "HTTP timeout (180s)", "status": "failed"
        }
    except Exception as e:
        return {
            "success": False, "task_id": task_id,
            "error_message": str(e), "status": "failed"
        }


def classify_failure(result):
    err = result.get("error_message", "unknown")
    status = str(result.get("status", ""))

    if "入力率が低すぎます" in err:
        return "入力率不足(セレクタ不一致)"
    if "submit" in err.lower() and "not a function" in err:
        return "submit送信メソッド衝突"
    if "timeout" in err.lower() or "タイムアウト" in err:
        return "タイムアウト"
    if "locked" in status:
        return "ロック競合"
    if "対象外" in err:
        return "自動実行対象外"
    if "reCAPTCHA" in err:
        return "reCAPTCHA"
    return err[:60]


def save_results(results, success_count, fail_count, skip_count, total, elapsed,
                 fail_patterns, status="in_progress", idx=None):
    success_rate = success_count / max(idx or total, 1) * 100

    summary = {
        "status": status,
        "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "processed": idx or total,
        "success_count": success_count,
        "fail_count": fail_count,
        "skip_count": skip_count,
        "success_rate": round(success_rate, 1),
        "elapsed_seconds": round(elapsed, 1),
        "avg_seconds_per_task": round(elapsed / max(idx or total, 1), 1),
        "fail_patterns": fail_patterns,
        "results": results
    }

    with open(RESULT_FILE, "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    load_webhook()

    # ログ設定
    sys.stdout = Logger(LOG_FILE)

    # 対象タスク取得
    tasks = get_target_tasks()
    if args.limit > 0:
        tasks = tasks[:args.limit]
    total = len(tasks)
    print(f"対象タスク: {total}件")
    print(f"開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"ログ: {LOG_FILE}")
    print(f"結果JSON: {RESULT_FILE}")

    if total == 0:
        print("対象タスクなし。終了。")
        send_discord("[DeepBiz Send] 対象タスクが0件のため終了しました。")
        return

    # 開始通知
    send_discord(
        f"[DeepBiz Send] 🚀 全件バッチ送信開始\n"
        f"対象: {total}件 / Product ID {PRODUCT_ID} / dry-run={args.dry_run}\n"
        f"推定所要時間: 約{total * 23 // 3600}時間{(total * 23 % 3600) // 60}分"
    )

    results = []
    success_count = 0
    fail_count = 0
    skip_count = 0
    fail_patterns = {}
    start_time = time.time()
    last_discord_idx = 0

    for i, (task_id, company_name, form_url) in enumerate(tasks):
        idx = i + 1
        print(f"\n[{idx}/{total}] Task #{task_id}: {company_name}")

        result = execute_task(task_id)
        result["company_name"] = company_name
        result["form_url"] = form_url

        result_status = result.get("status", "")

        if result.get("success"):
            success_count += 1
            fill_rate = result.get("fill_rate", 0)
            submit = result.get("submit_result", {})
            submit_method = submit.get("method", "?") if submit else "?"
            confirm = result.get("confirmation_result", {})
            completion = confirm.get("completion_detected", False) if confirm else False
            print(f"  ✅ 成功 (入力率{fill_rate}%, 送信:{submit_method}, 完了検出:{completion})")

        elif result_status == "skipped":
            skip_count += 1
            error = result.get("error_message", "unknown")[:80]
            print(f"  ⏭️ スキップ ({error})")

        else:
            fail_count += 1
            error = result.get("error_message", "unknown")[:80]
            fill_rate = result.get("fill_rate", 0)
            print(f"  ❌ 失敗 (入力率{fill_rate}%, エラー: {error})")

        # 失敗/スキップパターン集計
        if not result.get("success"):
            pattern = classify_failure(result)
            fail_patterns[pattern] = fail_patterns.get(pattern, 0) + 1

        results.append(result)

        # 500件ごとにDiscord通知
        if idx % DISCORD_INTERVAL == 0 and idx != last_discord_idx:
            last_discord_idx = idx
            elapsed = time.time() - start_time
            rate = success_count / idx * 100
            effective_rate = success_count / max(success_count + fail_count, 1) * 100
            eta_seconds = (total - idx) * (elapsed / idx)
            eta_h = int(eta_seconds // 3600)
            eta_m = int((eta_seconds % 3600) // 60)
            send_discord(
                f"[DeepBiz Send] 📊 進捗 {idx}/{total} ({idx/total*100:.1f}%)\n"
                f"成功: {success_count} / 失敗: {fail_count} / スキップ: {skip_count}\n"
                f"成功率: {rate:.1f}% (実行対象のみ: {effective_rate:.1f}%)\n"
                f"経過: {elapsed/3600:.1f}h / 残り推定: {eta_h}h{eta_m}m"
            )

        # 100件ごとに中間保存
        if idx % SAVE_INTERVAL == 0:
            elapsed = time.time() - start_time
            save_results(results, success_count, fail_count, skip_count,
                         total, elapsed, fail_patterns, "in_progress", idx)

        # タスク間待機
        time.sleep(TASK_DELAY)

    # 最終結果保存
    elapsed = time.time() - start_time
    save_results(results, success_count, fail_count, skip_count,
                 total, elapsed, fail_patterns, "completed", total)

    # 最終出力
    success_rate = success_count / total * 100
    effective_total = success_count + fail_count
    effective_rate = success_count / max(effective_total, 1) * 100

    print(f"\n{'='*60}")
    print(f"全件バッチ送信完了")
    print(f"  合計: {total}件")
    print(f"  成功: {success_count} ({success_rate:.1f}%)")
    print(f"  失敗: {fail_count}")
    print(f"  スキップ: {skip_count}")
    print(f"  実行対象成功率: {effective_rate:.1f}% ({success_count}/{effective_total})")
    print(f"  経過時間: {elapsed/3600:.1f}時間 (平均{elapsed/total:.1f}秒/件)")
    print(f"  失敗パターン: {json.dumps(fail_patterns, ensure_ascii=False)}")
    print(f"  結果ファイル: {RESULT_FILE}")
    print(f"{'='*60}")

    # 完了通知
    pattern_text = "\n".join([f"  {k}: {v}件" for k, v in
                              sorted(fail_patterns.items(), key=lambda x: -x[1])])
    send_discord(
        f"[DeepBiz Send] ✅ 全件バッチ送信完了\n"
        f"合計: {total}件\n"
        f"**成功: {success_count} ({success_rate:.1f}%)**\n"
        f"失敗: {fail_count} / スキップ: {skip_count}\n"
        f"実行対象成功率: {effective_rate:.1f}%\n"
        f"経過時間: {elapsed/3600:.1f}時間 (平均{elapsed/total:.1f}秒/件)\n"
        f"失敗パターン:\n{pattern_text}\n"
        f"結果: {RESULT_FILE}"
    )


if __name__ == "__main__":
    main()
