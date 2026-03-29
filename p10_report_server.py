#!/usr/bin/env python3
"""
P10 送信実績レポートサーバー
- /report でレポートページ表示（ページネーション対応）
- /screenshots/<filename> でスクショ配信
- GV判定結果はDBから読み込み
- スクショは起動時にインデックス構築（高速化）
"""

import os, json, html, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse, parse_qs

import psycopg2
import psycopg2.extras

DB_URL = "postgresql://autoform_user:secure_password_123@localhost:5432/ai_autoform"
SS_DIR = "/opt/ai-auto-form/screenshots"
PORT = 8000
PER_PAGE = 100

SS_INDEX = {}
SS_INDEX_LOCK = threading.Lock()

def build_ss_index():
    global SS_INDEX
    idx = {}
    t = time.time()
    for fname in os.listdir(SS_DIR):
        if not fname.startswith('task_') or not fname.endswith('.png'):
            continue
        parts = fname.split('_')
        if len(parts) < 3:
            continue
        try:
            tid = int(parts[1])
        except ValueError:
            continue
        ss_type = parts[2]
        if tid not in idx:
            idx[tid] = {}
        if ss_type in ('after', 'submitted'):
            if ss_type not in idx[tid] or fname > idx[tid][ss_type]:
                idx[tid][ss_type] = fname
    with SS_INDEX_LOCK:
        SS_INDEX = idx
    print(f"Screenshot index: {len(idx)} tasks in {time.time()-t:.1f}s")

def refresh_ss_index_periodically():
    while True:
        time.sleep(300)
        build_ss_index()


def get_p10_summary():
    """集計のみ（高速）"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT form_data::jsonb->>'gv_grade' as grade, count(*)
        FROM simple_tasks
        WHERE product_id = 10 AND status = 'completed'
          AND form_data::jsonb->>'gv_grade' IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """)
    counts = {r[0]: r[1] for r in cur.fetchall()}
    cur.close()
    conn.close()
    return counts


def get_p10_page(page, per_page, grade_filter=None):
    """ページネーション付きデータ取得"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    offset = (page - 1) * per_page

    grade_clause = ""
    params = []
    if grade_filter and grade_filter in ('A', 'B', 'C', 'D'):
        grade_clause = "AND form_data::jsonb->>'gv_grade' = %s"
        params.append(grade_filter)

    cur.execute(f"""
        SELECT t.id, c.name as company_name, c.form_url,
               t.completed_at,
               t.form_data::jsonb->>'gv_grade' as gv_grade
        FROM simple_tasks t
        JOIN simple_companies c ON c.id = t.company_id
        WHERE t.product_id = 10 AND t.status = 'completed'
          AND t.form_data::jsonb->>'gv_grade' IS NOT NULL
          {grade_clause}
        ORDER BY t.completed_at ASC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def build_report_html(counts, rows, page, grade_filter):
    a_count = counts.get('A', 0)
    b_count = counts.get('B', 0)
    c_count = counts.get('C', 0)
    d_count = counts.get('D', 0)
    total = sum(counts.values())

    filtered_total = counts.get(grade_filter, total) if grade_filter else total
    total_pages = (filtered_total + PER_PAGE - 1) // PER_PAGE

    with SS_INDEX_LOCK:
        ss_idx = dict(SS_INDEX)

    table_rows = []
    start_num = (page - 1) * PER_PAGE + 1
    for i, r in enumerate(rows, start_num):
        tid = r['id']
        company = html.escape(r['company_name'] or '')
        form_url = html.escape(r['form_url'] or '')
        grade = r['gv_grade'] or '-'
        completed = str(r['completed_at'])[:16] if r['completed_at'] else ''

        ss = ss_idx.get(tid, {})
        after_fn = ss.get('after', '')
        submitted_fn = ss.get('submitted', '')
        after_link = f'<a href="/screenshots/{after_fn}" target="_blank">入力後</a>' if after_fn else '-'
        submitted_link = f'<a href="/screenshots/{submitted_fn}" target="_blank">送信完了</a>' if submitted_fn else '-'

        grade_class = {'A': 'grade-a', 'B': 'grade-b', 'C': 'grade-c', 'D': 'grade-d'}.get(grade, '')

        table_rows.append(f"<tr><td>{i}</td><td>{company}</td><td><a href=\"{form_url}\" target=\"_blank\" class=\"url-link\">{form_url[:50]}{'...' if len(form_url)>50 else ''}</a></td><td class=\"{grade_class}\">{grade}</td><td>{after_link}</td><td>{submitted_link}</td><td>{completed}</td></tr>")

    # ページネーション
    gf = f"&grade={grade_filter}" if grade_filter else ""
    pages_html = []
    if page > 1:
        pages_html.append(f'<a href="/report?page={page-1}{gf}">&laquo; 前</a>')
    for p in range(1, total_pages + 1):
        if p == page:
            pages_html.append(f'<span class="current">{p}</span>')
        elif abs(p - page) <= 3 or p == 1 or p == total_pages:
            pages_html.append(f'<a href="/report?page={p}{gf}">{p}</a>')
        elif abs(p - page) == 4:
            pages_html.append('...')
    if page < total_pages:
        pages_html.append(f'<a href="/report?page={page+1}{gf}">次 &raquo;</a>')

    filter_links = [f'<a href="/report" class="{"active" if not grade_filter else ""}">全て({total})</a>']
    for g, label in [('A', f'A({a_count})'), ('B', f'B({b_count})'), ('C', f'C({c_count})'), ('D', f'D({d_count})')]:
        active = 'active' if grade_filter == g else ''
        filter_links.append(f'<a href="/report?grade={g}" class="{active}">{label}</a>')

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TheSide - フォーム送信実績レポート</title>
<style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:'Helvetica Neue',Arial,'Hiragino Sans',sans-serif;background:#f5f7fa;color:#333}}
    .header{{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:40px 0;text-align:center}}
    .header h1{{font-size:28px;font-weight:300;letter-spacing:2px;margin-bottom:8px}}
    .header p{{font-size:14px;opacity:.7}}
    .container{{max-width:1200px;margin:0 auto;padding:30px 20px}}
    .stats{{display:flex;gap:20px;margin-bottom:30px;flex-wrap:wrap}}
    .stat-card{{background:#fff;border-radius:12px;padding:24px;flex:1;min-width:150px;box-shadow:0 2px 8px rgba(0,0,0,.06);text-align:center}}
    .stat-card .number{{font-size:36px;font-weight:700;color:#1a1a2e}}
    .stat-card .label{{font-size:13px;color:#888;margin-top:4px}}
    .stat-card.highlight{{background:linear-gradient(135deg,#0f3460,#1a1a2e);color:#fff}}
    .stat-card.highlight .number{{color:#4ade80}}
    .stat-card.highlight .label{{color:rgba(255,255,255,.7)}}
    table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
    th{{background:#1a1a2e;color:#fff;padding:14px 16px;text-align:left;font-size:13px;font-weight:500}}
    td{{padding:12px 16px;border-bottom:1px solid #f0f0f0;font-size:14px}}
    tr:hover{{background:#f8f9fb}}
    .grade-a{{color:#16a34a;font-weight:700}} .grade-b{{color:#2563eb;font-weight:700}}
    .grade-c{{color:#dc2626;font-weight:700}} .grade-d{{color:#9ca3af;font-weight:700}}
    a{{color:#2563eb;text-decoration:none}} a:hover{{text-decoration:underline}}
    .url-link{{color:#666;font-size:12px}}
    .footer{{text-align:center;padding:40px;color:#aaa;font-size:12px}}
    .pagination{{display:flex;gap:8px;justify-content:center;margin:20px 0;flex-wrap:wrap}}
    .pagination a,.pagination span{{padding:8px 14px;border-radius:8px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08);font-size:14px}}
    .pagination .current{{background:#1a1a2e;color:#fff}}
    .filters{{display:flex;gap:10px;justify-content:center;margin-bottom:20px;flex-wrap:wrap}}
    .filters a{{padding:6px 16px;border-radius:20px;background:#e5e7eb;font-size:13px;color:#333}}
    .filters a.active{{background:#1a1a2e;color:#fff}}
</style>
</head>
<body>
<div class="header">
    <h1>TheSide</h1>
    <p>フォーム自動送信 実績レポート — 案件: RPO_OOOP_1</p>
</div>
<div class="container">
    <div class="stats">
        <div class="stat-card highlight"><div class="number">{a_count}</div><div class="label">送信成功（A判定）</div></div>
        <div class="stat-card"><div class="number">{b_count}</div><div class="label">おそらく成功（B）</div></div>
        <div class="stat-card"><div class="number">{c_count}</div><div class="label">要確認（C）</div></div>
        <div class="stat-card"><div class="number">{d_count}</div><div class="label">判定不能（D）</div></div>
        <div class="stat-card"><div class="number">{total}</div><div class="label">GV判定済み合計</div></div>
    </div>
    <div class="filters">{''.join(filter_links)}</div>
    <div class="pagination">{''.join(pages_html)}</div>
    <table>
        <thead><tr><th>#</th><th>企業名</th><th>送信先URL</th><th>判定</th><th>入力後</th><th>送信完了</th><th>送信日時</th></tr></thead>
        <tbody>{''.join(table_rows)}</tbody>
    </table>
    <div class="pagination">{''.join(pages_html)}</div>
</div>
<div class="footer">Generated by TheSide Automation System &mdash; {total} companies processed</div>
</body>
</html>"""


class ReportHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path in ('/', '/report'):
            page = int(qs.get('page', ['1'])[0])
            grade_filter = qs.get('grade', [None])[0]
            if page < 1:
                page = 1

            counts = get_p10_summary()
            rows = get_p10_page(page, PER_PAGE, grade_filter)
            html_content = build_report_html(counts, rows, page, grade_filter)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))

        elif parsed.path.startswith('/screenshots/'):
            filename = unquote(parsed.path.split('/screenshots/')[-1])
            filepath = os.path.join(SS_DIR, filename)
            if os.path.exists(filepath) and '..' not in filename:
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        elif parsed.path.endswith('.html'):
            filepath = os.path.join('/opt/ai-auto-form', parsed.path.lstrip('/'))
            if os.path.exists(filepath) and '..' not in parsed.path:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == '__main__':
    print(f"P10 Report Server starting on port {PORT}...")
    print("Building screenshot index...")
    build_ss_index()
    t = threading.Thread(target=refresh_ss_index_periodically, daemon=True)
    t.start()
    print(f"Access: http://153.126.154.158:{PORT}/report")
    server = HTTPServer(('0.0.0.0', PORT), ReportHandler)
    server.serve_forever()
