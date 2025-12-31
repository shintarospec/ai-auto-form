#!/usr/bin/env python3
"""VPS上でsimple_projectsテーブルを確認"""

from backend.database import engine
from sqlalchemy import text

def check_table():
    conn = engine.connect()
    
    # テーブル構造確認
    result = conn.execute(text("""
        SELECT column_name, data_type, character_maximum_length 
        FROM information_schema.columns 
        WHERE table_name = 'simple_projects' 
        ORDER BY ordinal_position;
    """))
    
    print("\n📋 Table: simple_projects")
    print("=" * 60)
    for row in result:
        length = f"({row.character_maximum_length})" if row.character_maximum_length else ""
        print(f"{row.column_name:20} {row.data_type}{length}")
    
    # データ確認
    result = conn.execute(text("SELECT * FROM simple_projects;"))
    rows = result.fetchall()
    
    print(f"\n📊 Data Count: {len(rows)} records")
    print("=" * 60)
    for row in rows:
        print(f"ID: {row.id}, Name: {row.name}, Status: {row.status}")
    
    conn.close()

if __name__ == "__main__":
    check_table()
