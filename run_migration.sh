#!/bin/bash
# VPSでマイグレーションを実行

ssh ubuntu@153.126.154.158 << 'ENDSSH'
cd /opt/ai-auto-form

# Flaskアプリのコンテキストでマイグレーション実行
export PYTHONPATH=/opt/ai-auto-form

python3 << 'EOF'
import sys
sys.path.insert(0, '/opt/ai-auto-form')

from backend.database import get_db_session
from sqlalchemy import text

print("📝 マイグレーション開始: simple_products に送信者情報カラム追加")

db = get_db_session()

try:
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
    result = db.execute(text("""
        UPDATE simple_products 
        SET 
            sender_name = COALESCE(sender_name, '山田太郎'),
            sender_email = COALESCE(sender_email, 'yamada@example.com'),
            sender_company = COALESCE(sender_company, '株式会社テスト'),
            sender_phone = COALESCE(sender_phone, '03-1234-5678')
    """))
    
    db.commit()
    print(f"✅ デフォルト値設定完了 (更新: {result.rowcount}行)")
    
    # 確認
    result = db.execute(text("""
        SELECT id, name, sender_name, sender_email, sender_company, sender_phone 
        FROM simple_products
    """))
    
    print("\n📋 更新後のデータ:")
    for row in result:
        print(f"  ID {row[0]}: {row[1]}")
        print(f"    送信者: {row[2]} ({row[4]})")
        print(f"    Email: {row[3]}, Tel: {row[5]}")
    
    print("\n🎉 マイグレーション完了!")
    
except Exception as e:
    db.rollback()
    print(f"❌ エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
EOF

ENDSSH
