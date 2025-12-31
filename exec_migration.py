#!/usr/bin/env python3
"""
VPSのFlask環境でマイグレーションを実行
SQLAlchemyを使わず、psycopg2で直接実行
"""
import os
import psycopg2

# VPS上のデータベース接続情報（app.pyで使われているもの）
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/ai_autoform')

try:
    print("📝 データベースに接続中...")
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    print("✅ 接続成功")
    print("📝 マイグレーション実行中...")
    
    # カラム追加
    cur.execute("""
        ALTER TABLE simple_products 
        ADD COLUMN IF NOT EXISTS sender_name VARCHAR(100),
        ADD COLUMN IF NOT EXISTS sender_email VARCHAR(200),
        ADD COLUMN IF NOT EXISTS sender_company VARCHAR(200),
        ADD COLUMN IF NOT EXISTS sender_phone VARCHAR(50)
    """)
    
    print("✅ カラム追加完了")
    
    # デフォルト値設定
    cur.execute("""
        UPDATE simple_products 
        SET 
            sender_name = COALESCE(sender_name, '山田太郎'),
            sender_email = COALESCE(sender_email, 'yamada@example.com'),
            sender_company = COALESCE(sender_company, '株式会社テスト'),
            sender_phone = COALESCE(sender_phone, '03-1234-5678')
    """)
    
    print(f"✅ デフォルト値設定完了 (更新: {cur.rowcount}行)")
    
    # 確認
    cur.execute("""
        SELECT id, name, sender_name, sender_email, sender_company, sender_phone 
        FROM simple_products
    """)
    
    print("\n📋 更新後のデータ:")
    for row in cur.fetchall():
        print(f"  ID {row[0]}: {row[1]}")
        print(f"    送信者: {row[2]} ({row[4]})")
        print(f"    Email: {row[3]}, Tel: {row[5]}")
    
    conn.commit()
    print("\n🎉 マイグレーション完了!")
    
except Exception as e:
    print(f"❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    if 'conn' in locals():
        conn.rollback()
finally:
    if 'cur' in locals():
        cur.close()
    if 'conn' in locals():
        conn.close()
