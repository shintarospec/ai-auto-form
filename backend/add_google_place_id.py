#!/usr/bin/env python3
"""
マイグレーション: simple_companiesにgoogle_place_idカラム追加

目的:
- DeepBiz連携用のユニークキー追加
- DBリフレッシュ時も企業を同一として認識可能
"""

import sys
import os
import psycopg2

def get_db_connection():
    """PostgreSQL接続取得"""
    return psycopg2.connect(
        host='localhost',
        database='ai_autoform',
        user='autoform_user',
        password='your_password'
    )

def add_google_place_id_column():
    """google_place_idカラムを追加"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("🔧 simple_companiesテーブルにgoogle_place_idカラムを追加中...")
        
        # 1. カラム追加
        cur.execute("""
            ALTER TABLE simple_companies
            ADD COLUMN IF NOT EXISTS google_place_id VARCHAR(255);
        """)
        print("  ✅ google_place_id VARCHAR(255) 追加完了")
        
        # 2. UNIQUE制約追加
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'unique_google_place_id'
                ) THEN
                    ALTER TABLE simple_companies
                    ADD CONSTRAINT unique_google_place_id UNIQUE (google_place_id);
                END IF;
            END $$;
        """)
        print("  ✅ UNIQUE制約 追加完了")
        
        # 3. インデックス作成（検索高速化）
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_google_place_id 
            ON simple_companies(google_place_id);
        """)
        print("  ✅ インデックス 作成完了")
        
        conn.commit()
        print("\n✅ マイグレーション成功！")
        
        # 4. 結果確認
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'simple_companies'
            AND column_name = 'google_place_id';
        """)
        result = cur.fetchone()
        if result:
            print(f"\n📋 確認: {result[0]} | {result[1]} | nullable={result[2]}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    add_google_place_id_column()
