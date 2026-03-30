#!/usr/bin/env python3
"""
F-3 Lite バッチ実行スクリプト
form_analysisがNULLまたは指定条件のタスクにパターンベース解析を実行
"""
import argparse
import asyncio
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor

# form_analyzer_liteのインポート
import sys
sys.path.insert(0, '/opt/ai-auto-form')
from backend.services.form_analyzer_lite import FormAnalyzerLite


def get_db():
    return psycopg2.connect(
        dbname='ai_autoform',
        user='autoform_user',
        password='secure_password_123',
        host='localhost'
    )


def get_target_tasks(args):
    """対象タスクを取得"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if args.task_ids:
        ids = [int(x.strip()) for x in args.task_ids.split(',')]
        cur.execute("""
            SELECT t.id, t.company_id, c.form_url
            FROM simple_tasks t
            JOIN simple_companies c ON t.company_id = c.id
            WHERE t.id = ANY(%s)
        """, (ids,))
    elif args.product_id:
        where_clauses = ["t.product_id = %s"]
        params = [args.product_id]

        if args.reanalyze:
            # 既存解析結果があっても再解析
            pass
        else:
            # form_analysisがNULLのタスクのみ
            where_clauses.append("t.form_analysis IS NULL")

        if args.status:
            where_clauses.append("t.status = %s")
            params.append(args.status)

        query = f"""
            SELECT t.id, t.company_id, c.form_url
            FROM simple_tasks t
            JOIN simple_companies c ON t.company_id = c.id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY t.id
        """
        if args.limit:
            query += f" LIMIT {args.limit}"

        cur.execute(query, params)
    else:
        print("ERROR: --product-id or --task-ids required")
        return []

    tasks = cur.fetchall()
    conn.close()
    return tasks


def save_result(task_id: int, result: dict):
    """form_analysisカラムに保存"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE simple_tasks
        SET form_analysis = %s::jsonb
        WHERE id = %s
    """, (json.dumps(result, ensure_ascii=False), task_id))
    conn.commit()
    conn.close()


async def analyze_batch(tasks, concurrency: int = 5):
    """バッチ解析"""
    analyzer = FormAnalyzerLite(headless=True)
    total = len(tasks)
    completed = 0
    success = 0
    errors = 0
    start_time = time.time()

    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(task):
        nonlocal completed, success, errors
        task_id = task['id']
        url = task['form_url']

        if not url:
            completed += 1
            errors += 1
            return

        async with semaphore:
            try:
                result = await analyzer.analyze_form(url, timeout=30000)
                save_result(task_id, result)

                if result['analysis_status'] == 'success':
                    success += 1
                    field_count = result['field_count']
                    ng = ' [NG]' if result.get('ng_flag') else ''
                    if completed % 100 == 0 or completed < 10:
                        print(f"  [{completed+1}/{total}] Task {task_id}: {field_count}fields{ng} ({result.get('elapsed_seconds', 0)}s)")
                else:
                    errors += 1
                    if completed % 100 == 0 or completed < 10:
                        print(f"  [{completed+1}/{total}] Task {task_id}: ERROR - {result.get('error_message', '')[:60]}")
            except Exception as e:
                errors += 1
                print(f"  [{completed+1}/{total}] Task {task_id}: EXCEPTION - {str(e)[:60]}")
            finally:
                completed += 1

                # 進捗ログ（100件ごと）
                if completed % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    print(f"  📊 進捗: {completed}/{total} ({completed/total*100:.1f}%) "
                          f"成功:{success} エラー:{errors} "
                          f"速度:{rate:.1f}件/s ETA:{eta/60:.0f}分")

    # 並列実行
    await asyncio.gather(*[process_one(t) for t in tasks])

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"F-3 Lite バッチ完了")
    print(f"  合計: {total}件")
    print(f"  成功: {success} ({success/total*100:.1f}%)")
    print(f"  エラー: {errors}")
    print(f"  経過時間: {elapsed/60:.1f}分 ({elapsed/total:.1f}秒/件)")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description='F-3 Lite バッチ解析')
    parser.add_argument('--product-id', type=int, help='対象Product ID')
    parser.add_argument('--task-ids', type=str, help='対象Task ID（カンマ区切り）')
    parser.add_argument('--limit', type=int, help='件数上限')
    parser.add_argument('--status', type=str, help='対象ステータス')
    parser.add_argument('--reanalyze', action='store_true', help='既存解析結果があっても再解析')
    parser.add_argument('--concurrency', type=int, default=5, help='並列度（デフォルト5）')
    parser.add_argument('--dry-run', action='store_true', help='対象件数のみ表示')

    args = parser.parse_args()
    tasks = get_target_tasks(args)

    print(f"F-3 Lite 対象: {len(tasks)}件")
    if args.dry_run:
        print("[dry-run] 実行はスキップされました")
        return

    if not tasks:
        print("対象タスクがありません")
        return

    asyncio.run(analyze_batch(tasks, concurrency=args.concurrency))


if __name__ == '__main__':
    main()
