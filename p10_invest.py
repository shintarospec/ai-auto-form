#!/usr/bin/env python3
"""
P10投入スクリプト（汎用・再利用可能）

使い方:
  python3 p10_invest.py                    # P9のGV=A判定 → P10投入（重複・NG除外）
  python3 p10_invest.py --dry-run          # 対象確認のみ、投入しない
  python3 p10_invest.py --include-b        # A+B判定を対象にする

特徴:
  - DBのform_data->>'gv_grade'から判定結果を読む（JSONファイル不要）
  - company_id + ドメイン重複チェック
  - NGリスト照合
  - P10タスクのform_dataにsource_p9_task_idを記録
"""
import os, json, sys, argparse
from datetime import datetime
from urllib.parse import urlparse

import psycopg2

# --- Args ---
parser = argparse.ArgumentParser(description='P9 A判定 → P10投入')
parser.add_argument('--dry-run', action='store_true', help='対象確認のみ')
parser.add_argument('--include-b', action='store_true', help='B判定も含める')
args = parser.parse_args()

DB_URL = 'postgresql://autoform_user:secure_password_123@localhost:5432/ai_autoform'
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# --- 1. P9のGV=A判定タスク取得（DBから） ---
if args.include_b:
    grade_filter = "IN ('A', 'B')"
    grade_label = 'A+B'
else:
    grade_filter = "= 'A'"
    grade_label = 'A'

cur.execute(f'''
    SELECT t.id, t.company_id, c.name, c.form_url, c.website_url
    FROM simple_tasks t
    JOIN simple_companies c ON c.id = t.company_id
    WHERE t.product_id = 9
      AND t.status = 'completed'
      AND t.form_data::jsonb->>'gv_grade' {grade_filter}
    ORDER BY t.id
''')
p9_a_tasks = cur.fetchall()
print(f'P9 {grade_label}判定（DB照合）: {len(p9_a_tasks)}件')

if not p9_a_tasks:
    print('投入対象なし。終了。')
    cur.close()
    conn.close()
    sys.exit(0)

# --- 2. P10既存タスク取得（重複防止） ---
cur.execute('''
    SELECT t.company_id, c.form_url
    FROM simple_tasks t
    JOIN simple_companies c ON c.id = t.company_id
    WHERE t.product_id = 10
''')
p10_existing = cur.fetchall()
p10_company_ids = set(r[0] for r in p10_existing)

def get_domain(url):
    try: return urlparse(url).netloc.lower().replace('www.', '')
    except: return ''

p10_domains = set(get_domain(r[1]) for r in p10_existing if r[1])
print(f'P10 既存: {len(p10_existing)}件, ユニーク企業: {len(p10_company_ids)}, ユニークドメイン: {len(p10_domains)}')

# --- 3. 重複除外（company_id + ドメイン） ---
new_candidates = []
dup_count = 0
for r in p9_a_tasks:
    domain = get_domain(r[3]) if r[3] else ''
    if r[1] in p10_company_ids or (domain and domain in p10_domains):
        dup_count += 1
    else:
        new_candidates.append(r)
print(f'重複除外: {dup_count}件')

# --- 4. NGリスト照合 ---
ng_domains = set()
ng_file = '/tmp/ng_only_domains.json'
if os.path.exists(ng_file):
    with open(ng_file) as f:
        ng_domains = set(json.load(f))

ng_blocked = []
safe_candidates = []
for r in new_candidates:
    domain = get_domain(r[3]) if r[3] else ''
    website_domain = get_domain(r[4]) if r[4] else ''
    if domain in ng_domains or website_domain in ng_domains:
        ng_blocked.append(r)
    else:
        safe_candidates.append(r)

print(f'NGリスト該当: {len(ng_blocked)}件')
if ng_blocked:
    for r in ng_blocked:
        print(f'  NG: {r[0]} {r[2]} {r[3]}')

print(f'\n★ 新規P10投入可能: {len(safe_candidates)}件')

if args.dry_run:
    if safe_candidates:
        print(f'  ID範囲: {safe_candidates[0][0]}-{safe_candidates[-1][0]}')
    cur.close()
    conn.close()
    sys.exit(0)

if not safe_candidates:
    print('投入対象なし。終了。')
    cur.close()
    conn.close()
    sys.exit(0)

# --- 5. P10タスク作成 ---
created = 0
created_ids = []
for r in safe_candidates:
    p9_task_id, company_id = r[0], r[1]
    cur.execute('''
        INSERT INTO simple_tasks (company_id, product_id, status, form_data, created_at)
        VALUES (%s, 10, 'pending', %s::jsonb, NOW())
        RETURNING id
    ''', (company_id, json.dumps({"source_p9_task_id": p9_task_id})))
    new_id = cur.fetchone()[0]

    # P9タスクからメタデータコピー
    cur.execute('''
        UPDATE simple_tasks SET
            automation_type = p9.automation_type,
            recaptcha_type = p9.recaptcha_type,
            form_analysis = p9.form_analysis
        FROM simple_tasks p9
        WHERE simple_tasks.id = %s AND p9.id = %s
    ''', (new_id, p9_task_id))
    created += 1
    created_ids.append(new_id)

conn.commit()

# --- 6. 結果確認 ---
print(f'\n{"="*60}')
print(f'P10投入完了: {created}件')
if created_ids:
    print(f'P10新規ID範囲: {min(created_ids)}-{max(created_ids)}')
print(f'{"="*60}')

cur.execute("SELECT status, count(*) FROM simple_tasks WHERE product_id = 10 GROUP BY status ORDER BY status")
print(f'\nP10ステータス:')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]}')

cur.close()
conn.close()
