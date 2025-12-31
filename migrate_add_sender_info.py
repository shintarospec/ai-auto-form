#!/usr/bin/env python3
"""
案件テーブルに送信者情報カラムを追加するマイグレーション
"""
from backend.database import get_db_session
from sqlalchemy import text

def migrate():
    db = get_db_session()
    
    try:
        print("📝 マイグレーション開始: simple_products に送信者情報カラム追加")
        
        # カラム追加
        db.execute(text("""
            ALTER TABLE simple_products 
            ADD COLUMN IF NOT EXISTS sender_name VARCHAR(100),
            ADD COLUMN IF NOT EXISTS sender_email VARCHAR(200),
            ADD COLUMN IF NOT EXISTS sender_company VARCHAR(200),
            ADD COLUMN IF NOT EXISTS sender_phone VARCHAR(50)
        """))
        
        print("✅ カラム追加完了")
        
        # 既存データにデフォルト値を設定
        db.execute(text("""
            UPDATE simple_products 
            SET 
                sender_name = '山田太郎',
                sender_email = 'yamada@example.com',
                sender_company = '株式会社テスト',
                sender_phone = '03-1234-5678'
            WHERE sender_name IS NULL
        """))
        
        db.commit()
        print("✅ デフォルト値設定完了")
        
        # 確認
        result = db.execute(text("""
            SELECT id, name, sender_name, sender_email, sender_company, sender_phone 
            FROM simple_products
        """))
        
        print("\n📋 更新後のデータ:")
        for row in result:
            print(f"  ID {row[0]}: {row[1]}")
            print(f"    送信者: {row[2]} ({row[4]})")
            print(f"    Email: {row[3]}, Tel: {row[5]}\n")
        
        print("🎉 マイグレーション完了!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    migrate()
