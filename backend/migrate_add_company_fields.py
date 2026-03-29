#!/usr/bin/env python3
"""
Phase 2-A Migration: simple_companiesテーブルにカラム追加
AI文面カスタマイズ用のフィールドを追加
"""

from sqlalchemy import text
from backend.database import engine

def migrate_add_company_fields():
    """simple_companiesにdescription, employee_count, established_year, capitalを追加"""
    
    print("=" * 60)
    print("  Phase 2-A Migration: Add Company Fields")
    print("=" * 60)
    
    # autocommitモードで実行（ハング防止）
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        # 1. description カラム追加
        print("\n📝 Adding 'description' column...")
        conn.execute(text("""
            ALTER TABLE simple_companies 
            ADD COLUMN IF NOT EXISTS description TEXT;
        """))
        print("✅ 'description' column added")
        
        # 2. employee_count カラム追加
        print("\n👥 Adding 'employee_count' column...")
        conn.execute(text("""
            ALTER TABLE simple_companies 
            ADD COLUMN IF NOT EXISTS employee_count INTEGER;
        """))
        print("✅ 'employee_count' column added")
        
        # 3. established_year カラム追加
        print("\n📅 Adding 'established_year' column...")
        conn.execute(text("""
            ALTER TABLE simple_companies 
            ADD COLUMN IF NOT EXISTS established_year INTEGER;
        """))
        print("✅ 'established_year' column added")
        
        # 4. capital カラム追加
        print("\n💰 Adding 'capital' column...")
        conn.execute(text("""
            ALTER TABLE simple_companies 
            ADD COLUMN IF NOT EXISTS capital VARCHAR(100);
        """))
        print("✅ 'capital' column added")
    
    # テーブル構造確認（別接続）
    with engine.connect() as conn:
        print("\n📋 Updated table structure:")
        print("=" * 60)
        result = conn.execute(text("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'simple_companies' 
            ORDER BY ordinal_position;
        """))
        
        for row in result:
            length = f"({row.character_maximum_length})" if row.character_maximum_length else ""
            print(f"  {row.column_name:20} {row.data_type}{length}")
    
    print("\n🎉 Migration completed successfully!")
    print("\n📌 Next Step: Update test data with descriptions")

if __name__ == "__main__":
    migrate_add_company_fields()
