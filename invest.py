#!/usr/bin/env python3
"""
汎用タスク投入スクリプト

使い方:
  python3 invest.py --product-id 11 --source all_auto --dry-run
  python3 invest.py --product-id 11 --source all_auto --limit 100
  python3 invest.py --product-id 11 --source product:9:completed --dry-run
  python3 invest.py --product-id 11 --source csv:/tmp/company_ids.csv

企業ソース:
  all_auto                 全auto企業
  product:<ID>             特定Productのタスクを持つ企業
  product:<ID>:completed   特定Productのcompleted企業のみ
  csv:<path>               CSVからcompany_id読み込み

安全装置:
  - 同一Product重複チェック（既存タスクがある企業は除外）
  - NGリスト照合（/tmp/ng_only_domains.json）
  - automation_type='auto'チェック（manual企業は除外）
  - dry-run & 実行前確認（y/N）
"""
import os, json, sys, argparse, csv
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

DB_URL = 'postgresql://autoform_user:secure_password_123@localhost:5432/ai_autoform'
NG_FILE = '/tmp/ng_only_domains.json'
SCRIPT_VERSION = '1.0'

# --- Args ---
parser = argparse.ArgumentParser(description='汎用タスク投入')
parser.add_argument('--product-id', type=int, required=True, help='投入先Product ID')
parser.add_argument('--source', type=str, required=True, help='企業ソース (all_auto, product:N, product:N:completed, csv:path)')
parser.add_argument('--limit', type=int, default=0, help='投入件数上限 (0=全件)')
parser.add_argument('--dry-run', action='store_true', help='サマリー表示のみ')
args = parser.parse_args()


def get_domain(url):
    try:
        return urlparse(url).netloc.lower().replace('www.', '')
    except:
        return ''


def get_source_companies(cur, source):
    """ソース指定から対象企業IDを取得"""
    if source == 'all_auto':
        cur.execute("""
            SELECT DISTINCT t.company_id
            FROM simple_tasks t
            WHERE t.automation_type = 'auto'
        """)
        return set(r[0] for r in cur.fetchall())

    elif source.startswith('product:'):
        parts = source.split(':')
        src_product_id = int(parts[1])
        if len(parts) >= 3 and parts[2] == 'completed':
            cur.execute("""
                SELECT DISTINCT t.company_id
                FROM simple_tasks t
                WHERE t.product_id = %s AND t.status = 'completed'
                  AND t.automation_type = 'auto'
            """, (src_product_id,))
        else:
            cur.execute("""
                SELECT DISTINCT t.company_id
                FROM simple_tasks t
                WHERE t.product_id = %s AND t.automation_type = 'auto'
            """, (src_product_id,))
        return set(r[0] for r in cur.fetchall())

    elif source.startswith('csv:'):
        csv_path = source[4:]
        if not os.path.exists(csv_path):
            print(f"ERROR: CSV file not found: {csv_path}")
            sys.exit(1)
        company_ids = set()
        with open(csv_path) as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip().isdigit():
                    company_ids.add(int(row[0].strip()))
        return company_ids

    else:
        print(f"ERROR: Unknown source: {source}")
        sys.exit(1)


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # --- 1. 投入先Product確認 ---
    cur.execute("SELECT id, name FROM simple_products WHERE id = %s", (args.product_id,))
    product = cur.fetchone()
    if not product:
        print(f"ERROR: Product {args.product_id} not found")
        sys.exit(1)
    product_name = product[1]

    # --- 2. ソースから対象企業取得 ---
    source_companies = get_source_companies(cur, args.source)
    total_source = len(source_companies)

    # --- 3. auto企業フィルタ（manual除外） ---
    cur.execute("""
        SELECT DISTINCT company_id FROM simple_tasks
        WHERE automation_type = 'auto'
    """)
    auto_companies = set(r[0] for r in cur.fetchall())
    manual_excluded = source_companies - auto_companies
    candidates = source_companies & auto_companies

    # --- 4. 同一Product重複チェック ---
    cur.execute("""
        SELECT DISTINCT company_id FROM simple_tasks
        WHERE product_id = %s
    """, (args.product_id,))
    existing = set(r[0] for r in cur.fetchall())
    dup_excluded = candidates & existing
    candidates = candidates - existing

    # --- 5. NGリスト照合 ---
    ng_domains = set()
    if os.path.exists(NG_FILE):
        with open(NG_FILE) as f:
            ng_domains = set(json.load(f))

    ng_excluded = set()
    if ng_domains:
        # 企業のform_url/website_urlを取得してドメインチェック
        if candidates:
            placeholders = ','.join(['%s'] * len(candidates))
            cur.execute(f"""
                SELECT id, form_url, website_url FROM simple_companies
                WHERE id IN ({placeholders})
            """, list(candidates))
            for cid, form_url, website_url in cur.fetchall():
                d1 = get_domain(form_url) if form_url else ''
                d2 = get_domain(website_url) if website_url else ''
                if d1 in ng_domains or d2 in ng_domains:
                    ng_excluded.add(cid)
    candidates = candidates - ng_excluded

    # --- 6. Limit適用 ---
    candidates_list = sorted(candidates)
    if args.limit > 0:
        candidates_list = candidates_list[:args.limit]

    # --- 7. サマリー表示 ---
    print(f"\n{'='*50}")
    print(f"invest.py 投入サマリー")
    print(f"{'='*50}")
    print(f"投入先Product: {args.product_id} ({product_name})")
    print(f"企業ソース: {args.source}")
    print(f"対象企業数: {total_source}")
    print(f"除外（manual）: {len(manual_excluded)}")
    print(f"除外（重複）: {len(dup_excluded)}（Product {args.product_id}で既にタスクあり）")
    print(f"除外（NG）: {len(ng_excluded)}")
    if args.limit > 0:
        print(f"上限: {args.limit}")
    print(f"→ 投入件数: {len(candidates_list)}")

    if args.dry_run:
        print(f"\n[dry-run] 実行はスキップされました。")
        cur.close()
        conn.close()
        return

    if not candidates_list:
        print("\n投入対象なし。終了。")
        cur.close()
        conn.close()
        return

    # --- 8. 実行前確認 ---
    answer = input("\n続行しますか？ (y/N): ").strip().lower()
    if answer != 'y':
        print("中止しました。")
        cur.close()
        conn.close()
        return

    # --- 9. タスク作成 ---
    invested_at = datetime.now().isoformat()
    created = 0
    fa_copied = 0
    fa_missing = 0
    created_ids = []

    for cid in candidates_list:
        # form_analysisを既存タスクからコピー（最新のものを取得）
        cur.execute("""
            SELECT form_analysis, automation_type, recaptcha_type
            FROM simple_tasks
            WHERE company_id = %s AND form_analysis IS NOT NULL
            ORDER BY created_at DESC NULLS LAST
            LIMIT 1
        """, (cid,))
        existing_task = cur.fetchone()

        form_analysis = existing_task[0] if existing_task else None
        automation_type = existing_task[1] if existing_task else 'auto'
        recaptcha_type = existing_task[2] if existing_task else None

        form_data = json.dumps({
            "invested_at": invested_at,
            "invested_from": args.source,
            "invest_script_version": SCRIPT_VERSION
        })

        cur.execute("""
            INSERT INTO simple_tasks
                (company_id, product_id, status, form_data, form_analysis,
                 automation_type, recaptcha_type, created_at)
            VALUES (%s, %s, 'pending', %s, %s, %s, %s, NOW())
            RETURNING id
        """, (cid, args.product_id, form_data,
              json.dumps(form_analysis) if form_analysis and isinstance(form_analysis, dict) else form_analysis,
              automation_type, recaptcha_type))

        new_id = cur.fetchone()[0]
        created_ids.append(new_id)
        created += 1
        if form_analysis:
            fa_copied += 1
        else:
            fa_missing += 1

    conn.commit()

    # --- 10. 結果表示 ---
    print(f"\n{'='*50}")
    print(f"投入完了: {created}件")
    if created_ids:
        print(f"ID範囲: {min(created_ids)}-{max(created_ids)}")
    print(f"form_analysisコピー成功: {fa_copied}件")
    print(f"form_analysis未取得（F-3実行必要）: {fa_missing}件")
    print(f"{'='*50}")

    # 確認クエリ
    cur.execute("""
        SELECT status, count(*) FROM simple_tasks
        WHERE product_id = %s GROUP BY 1 ORDER BY 1
    """, (args.product_id,))
    print(f"\nProduct {args.product_id} ステータス:")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
