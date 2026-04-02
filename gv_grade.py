#!/usr/bin/env python3
"""
GV判定スクリプト（2段階判定対応）

使い方:
  python3 gv_grade.py --product-id 9 --type submitted     # submitted判定（デフォルト）
  python3 gv_grade.py --product-id 9 --type after          # after判定（入力品質）
  python3 gv_grade.py --product-id 9 --type both           # 両方 + 最終判定
  python3 gv_grade.py --product-id 9 --type after --limit 100
  python3 gv_grade.py --product-id 9 --type both --dry-run
  python3 gv_grade.py --product-id 9 --type after --force  # 判定済みも再実行

特徴:
  - GV判定結果をDBのform_dataに直接書き込む
  - 判定済みは自動スキップ（--forceで再実行可能）
  - 出力JSONはタイムスタンプ付きで絶対に上書きしない
  - 途中中断しても判定済み分はDB保存済み
  - after判定実行時、submitted判定済みなら自動でfinal_gradeを計算
"""
import os, glob, json, time, sys, argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/opt/ai-auto-form/.env')

from google import genai
import psycopg2
import psycopg2.extras

# --- Args ---
parser = argparse.ArgumentParser(description='Gemini Vision GV判定（2段階対応）')
parser.add_argument('--product-id', type=int, required=True, help='対象product_id')
parser.add_argument('--type', choices=['submitted', 'after', 'both'], default='submitted',
                    help='判定タイプ: submitted(送信結果), after(入力品質), both(両方+最終)')
parser.add_argument('--limit', type=int, default=0, help='判定件数上限 (0=全件)')
parser.add_argument('--force', action='store_true', help='判定済みも再実行')
parser.add_argument('--dry-run', action='store_true', help='対象確認のみ、判定しない')
args = parser.parse_args()

# --- Setup ---
api_key = os.environ.get('GEMINI_API_KEY', '')
if not api_key:
    print("ERROR: No GEMINI_API_KEY found")
    sys.exit(1)

client = genai.Client(api_key=api_key)
MODEL_ID = "gemini-2.5-flash"

ss_dir = '/opt/ai-auto-form/screenshots'
results_dir = '/opt/ai-auto-form/test-results'
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

DB_URL = 'postgresql://autoform_user:secure_password_123@localhost:5432/ai_autoform'

# --- プロンプト定義 ---
SUBMITTED_PROMPT = '''このスクリーンショットはWebフォーム送信後の画面です。送信結果を以下の基準で判定してください。

A: 送信完了（ありがとう、送信完了、Thank you 等の完了メッセージが表示されている）
B: おそらく成功（完了メッセージは不明確だが、フォームが消えている等の間接的な証拠あり）
C: 未送信の可能性（エラー表示、確認画面で停止、入力画面のまま等）
D: 判定不能（空白画面、タイムアウト、ページ読み込み失敗等）

回答は「判定: X」の形式で1行で返してください。Xは A/B/C/D のいずれかです。
理由も1行で簡潔に付けてください。'''

AFTER_PROMPT = '''このスクリーンショットはWebフォームに情報を入力した後の画面です。

【重要な前提】
これは企業の問い合わせフォームを使った営業・ビジネス提案の送信です。
営業メッセージであること自体は正常であり、「営業目的だから不適切」という判定はしないでください。
フォームの利用目的（問い合わせ用 vs 営業用）は判定基準に含めません。

【判定基準】入力の技術的品質のみを判定してください。

A: 正常入力（各フィールドに適切な値が入力されている。空欄がなく、フィールドの入れ違いもない）
B: 概ね正常（軽微な問題はあるが、受信者が内容を理解でき連絡が取れるレベル。例: フリガナが漢字、電話番号の軽微なずれ等）
C: 入力品質不良（以下のいずれかに該当）:
   - 必須フィールドが空欄
   - フィールドの入れ違い（会社名欄にURL、メール欄に電話番号等）
   - 文字化けやプレースホルダーの残存
   - メッセージ本文が途中で切れている
   - セレクトボックスが未選択
D: 判定不能（フォームが見えない、スクリーンショットが不鮮明、入力内容が確認できない）

チェックポイント:
- 会社名フィールドに正しい企業名が入っているか
- 氏名フィールドに人名として妥当な値が入っているか
- メールアドレスフィールドにメール形式の値が入っているか
- 電話番号フィールドに妥当な桁数の番号が入っているか
- メッセージ本文が入力されているか（内容の是非は問わない）
- フィールドの入れ違いがないか

回答は「判定: X」の形式で1行で返してください。Xは A/B/C/D のいずれかです。
理由も1行で簡潔に付けてください。'''


def compute_final_grade(submitted, after):
    """2段階GV判定の最終判定を計算"""
    if submitted == 'D':
        return 'D'
    if submitted in ('A', 'B') and after == 'A':
        return 'A'
    if submitted == 'A' and after in ('B', 'C', 'D'):
        return 'B'  # 送信成功だがリトライ禁止、品質問題あり
    if submitted == 'B':
        return 'B'
    if submitted == 'C':
        return 'C'
    return 'D'


def parse_grade(text):
    """GV判定結果テキストからA/B/C/Dを抽出"""
    grade = None
    for line in text.split('\n'):
        if '判定' in line:
            for g in ['A', 'B', 'C', 'D']:
                if g in line.split('判定')[-1][:5]:
                    grade = g
                    break
        if grade:
            break
    if not grade:
        for g in ['A', 'B', 'C', 'D']:
            if f': {g}' in text or text.startswith(g):
                grade = g
                break
    return grade


def find_screenshot(tid, ss_type):
    """スクリーンショットファイルを検索"""
    if ss_type == 'submitted':
        patterns = [f'{ss_dir}/task_{tid}_submitted_*.png', f'{ss_dir}/task_{tid}_after_*.png']
    else:  # after
        patterns = [f'{ss_dir}/task_{tid}_after_*.png']

    for pat in patterns:
        files = sorted(glob.glob(pat))
        if files:
            return files[-1]
    return None


def run_grading(cur, conn, task_ids, grade_type, prompt, db_keys):
    """判定を実行してDB保存"""
    grade_key, reason_key, time_key = db_keys
    results = {"A": [], "B": [], "C": [], "D": []}
    errors = []
    graded_at = datetime.now().isoformat()
    # トークン使用量の累積カウンタ
    total_input_tokens = 0
    total_output_tokens = 0
    total_thinking_tokens = 0
    total_all_tokens = 0

    for i, tid in enumerate(task_ids):
        ss_file = find_screenshot(tid, grade_type)

        if not ss_file:
            errors.append({"task_id": tid, "error": f"no_{grade_type}_screenshot"})
            print(f'[{i+1}/{len(task_ids)}] Task {tid}: SKIP (no {grade_type} screenshot)')
            continue

        with open(ss_file, 'rb') as f:
            img_data = f.read()

        try:
            from google.genai import types
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=img_data, mime_type="image/png"),
                ],
                config=types.GenerateContentConfig(
                    max_output_tokens=256,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            text = response.text.strip()
            # トークン使用量の累積
            try:
                um = response.usage_metadata
                if um:
                    _in = um.prompt_token_count or 0
                    _out = um.candidates_token_count or 0
                    _think = getattr(um, 'thoughts_token_count', 0) or 0
                    _total = um.total_token_count or 0
                    total_input_tokens += _in
                    total_output_tokens += _out
                    total_thinking_tokens += _think
                    total_all_tokens += _total
                    if i < 3:
                        print(f"  tokens: in={_in} out={_out} think={_think} total={_total}")
            except Exception:
                pass
            grade = parse_grade(text)

            if grade:
                results[grade].append(tid)
                # DB書き込み（1件ずつ即座に保存）
                update_data = {
                    grade_key: grade,
                    reason_key: text[:200],
                    time_key: graded_at
                }

                # after判定時、submitted判定済みならfinal_gradeも計算
                if grade_type == 'after':
                    cur.execute(
                        "SELECT form_data::jsonb->>'gv_grade' FROM simple_tasks WHERE id = %s",
                        (tid,)
                    )
                    row = cur.fetchone()
                    submitted_grade = row[0] if row else None
                    if submitted_grade:
                        final = compute_final_grade(submitted_grade, grade)
                        update_data["gv_final_grade"] = final
                        update_data["gv_final_reason"] = f"submitted:{submitted_grade} + after:{grade} → final:{final}"
                        update_data["gv_final_graded_at"] = graded_at

                cur.execute('''
                    UPDATE simple_tasks
                    SET form_data = COALESCE(form_data::jsonb, '{}'::jsonb) || %s::jsonb
                    WHERE id = %s
                ''', (json.dumps(update_data), tid))
                conn.commit()

                final_info = f" → final:{update_data.get('gv_final_grade', '-')}" if 'gv_final_grade' in update_data else ""
                print(f'[{i+1}/{len(task_ids)}] Task {tid}: {grade}{final_info} - {text[:80]}')
            else:
                errors.append({"task_id": tid, "error": f"parse_error: {text[:100]}"})
                print(f'[{i+1}/{len(task_ids)}] Task {tid}: PARSE ERROR - {text[:80]}')

            # 進捗ログ（100件ごとにトークン累積を出力）
            if (i + 1) % 100 == 0:
                _graded = i + 1
                _avg = total_all_tokens / _graded if _graded > 0 else 0
                print(f"  📊 [{_graded}/{len(task_ids)}] tokens累積: in={total_input_tokens:,} out={total_output_tokens:,} think={total_thinking_tokens:,} total={total_all_tokens:,} (avg={_avg:.0f}/件)")

            time.sleep(1)

        except Exception as e:
            errors.append({"task_id": tid, "error": str(e)[:100]})
            print(f'[{i+1}/{len(task_ids)}] Task {tid}: ERROR - {str(e)[:80]}')
            time.sleep(2)

    # トークン使用量サマリ
    graded_count = sum(len(v) for v in results.values())
    if graded_count > 0:
        avg_tokens = total_all_tokens / graded_count
        print(f"\n📊 トークン使用量サマリ:")
        print(f"  input:    {total_input_tokens:,} tokens")
        print(f"  output:   {total_output_tokens:,} tokens")
        print(f"  thinking: {total_thinking_tokens:,} tokens")
        print(f"  total:    {total_all_tokens:,} tokens")
        print(f"  処理件数:  {graded_count}件")
        print(f"  平均:     {avg_tokens:.0f} tokens/件")

    return results, errors


def get_target_ids(cur, product_id, grade_type, limit, force):
    """判定対象のタスクIDを取得"""
    limit_clause = f"LIMIT {limit}" if limit > 0 else ""

    if grade_type == 'submitted':
        null_check = "AND (form_data IS NULL OR form_data::jsonb->>'gv_grade' IS NULL)" if not force else ""
        cur.execute(f'''
            SELECT id FROM simple_tasks
            WHERE product_id = %s AND status = 'completed' {null_check}
            ORDER BY id {limit_clause}
        ''', (product_id,))
    else:  # after
        null_check = "AND (form_data::jsonb->>'gv_after_grade' IS NULL)" if not force else ""
        cur.execute(f'''
            SELECT id FROM simple_tasks
            WHERE product_id = %s AND status = 'completed' {null_check}
            ORDER BY id {limit_clause}
        ''', (product_id,))

    return [r[0] for r in cur.fetchall()]


def print_summary(results, errors, label, product_id, timestamp):
    """結果サマリーを表示"""
    total = sum(len(v) for v in results.values())
    print(f'\n{"="*60}')
    print(f'GV {label}判定結果: P{product_id} ({timestamp})')
    print(f'{"="*60}')
    print(f'Total graded: {total}/{total + len(errors)}')
    for g in ['A', 'B', 'C', 'D']:
        cnt = len(results[g])
        pct = cnt / total * 100 if total > 0 else 0
        print(f'  {g}: {cnt} ({pct:.1f}%)')
    if errors:
        print(f'  Errors/Skipped: {len(errors)}')
    if total > 0:
        a = len(results['A'])
        b = len(results['B'])
        print(f'\nA率: {a}/{total} = {a/total*100:.1f}%')
        print(f'A+B率: {(a+b)}/{total} = {(a+b)/total*100:.1f}%')
    return total


def save_json_backup(results, errors, total, task_count, product_id, grade_type, timestamp):
    """JSONバックアップ保存（タイムスタンプ付き、上書き不可）"""
    output_file = f'{results_dir}/gv_{grade_type}_p{product_id}_{timestamp}.json'
    if os.path.exists(output_file):
        # タイムスタンプにsuffixを追加して回避
        output_file = f'{results_dir}/gv_{grade_type}_p{product_id}_{timestamp}_2.json'

    output = {
        "product_id": product_id,
        "timestamp": timestamp,
        "type": grade_type,
        "results": results,
        "errors": errors,
        "total_graded": total,
        "total_batch": task_count,
    }
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    print(f'\nJSONバックアップ: {output_file}')


# --- Main ---
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

types_to_run = []
if args.type == 'both':
    types_to_run = ['submitted', 'after']
else:
    types_to_run = [args.type]

for grade_type in types_to_run:
    label = 'submitted（送信結果）' if grade_type == 'submitted' else 'after（入力品質）'
    prompt = SUBMITTED_PROMPT if grade_type == 'submitted' else AFTER_PROMPT

    if grade_type == 'submitted':
        db_keys = ('gv_grade', 'gv_reason', 'gv_graded_at')
    else:
        db_keys = ('gv_after_grade', 'gv_after_reason', 'gv_after_graded_at')

    task_ids = get_target_ids(cur, args.product_id, grade_type, args.limit, args.force)

    print(f'\n=== GV {label}: P{args.product_id} ===')
    print(f'対象: {len(task_ids)}件')
    if args.limit:
        print(f'上限: {args.limit}件')
    if args.force:
        print(f'モード: 強制再判定')

    if args.dry_run:
        if task_ids:
            print(f'ID範囲: {min(task_ids)}-{max(task_ids)}')
        continue

    if not task_ids:
        print('判定対象なし。')
        continue

    results, errors = run_grading(cur, conn, task_ids, grade_type, prompt, db_keys)
    total = print_summary(results, errors, grade_type, args.product_id, timestamp)
    save_json_backup(results, errors, total, len(task_ids), args.product_id, grade_type, timestamp)
    print(f'※ GV判定結果はDBに保存済み（form_data->{db_keys[0]}）')

# --- both モード: final_grade未計算分を補完 ---
if args.type == 'both' and not args.dry_run:
    print(f'\n=== 最終判定（final_grade）計算 ===')
    cur.execute('''
        SELECT id,
            form_data::jsonb->>'gv_grade' as submitted,
            form_data::jsonb->>'gv_after_grade' as after_grade
        FROM simple_tasks
        WHERE product_id = %s AND status = 'completed'
          AND form_data::jsonb->>'gv_grade' IS NOT NULL
          AND form_data::jsonb->>'gv_after_grade' IS NOT NULL
          AND form_data::jsonb->>'gv_final_grade' IS NULL
    ''', (args.product_id,))
    rows = cur.fetchall()

    if rows:
        graded_at = datetime.now().isoformat()
        final_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        for tid, submitted, after in rows:
            final = compute_final_grade(submitted, after)
            final_counts[final] += 1
            cur.execute('''
                UPDATE simple_tasks
                SET form_data = COALESCE(form_data::jsonb, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
            ''', (json.dumps({
                "gv_final_grade": final,
                "gv_final_reason": f"submitted:{submitted} + after:{after} → final:{final}",
                "gv_final_graded_at": graded_at
            }), tid))
        conn.commit()

        print(f'計算完了: {len(rows)}件')
        for g in ['A', 'B', 'C', 'D']:
            print(f'  final {g}: {final_counts[g]}')
    else:
        print('追加計算対象なし。')

cur.close()
conn.close()
