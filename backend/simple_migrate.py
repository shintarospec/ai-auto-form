"""
Simple Database Migration - Phase 1 MVP
シンプルな3テーブルを作成してテストデータを投入
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.simple_models import Base, Company, Product, Task, Project
from backend.database import engine  # 既存の接続設定を使用
import json

# Use existing engine
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """テーブル作成"""
    print("📦 Creating tables...")
    Base.metadata.create_all(engine)
    print("✅ Tables created successfully!")

def seed_data():
    """テストデータ投入"""
    session = SessionLocal()
    
    try:
        print("\n🌱 Seeding test data...")
        
        # 1. 企業データ
        companies = [
            Company(
                name="株式会社サンプルA",
                website_url="https://example-a.com",
                form_url="http://localhost:8000/test-contact-form.html",
                industry="IT・通信"
            ),
            Company(
                name="株式会社サンプルB",
                website_url="https://example-b.com",
                form_url="http://localhost:8000/test-contact-form.html",
                industry="製造業"
            ),
            Company(
                name="株式会社サンプルC",
                website_url="https://example-c.com",
                form_url="http://localhost:8000/test-contact-form.html",
                industry="小売業"
            ),
            Company(
                name="株式会社サンプルD",
                website_url="https://example-d.com",
                form_url="http://localhost:8000/test-contact-form.html",
                industry="サービス業"
            ),
            Company(
                name="株式会社サンプルE",
                website_url="https://example-e.com",
                form_url="http://localhost:8000/test-contact-form.html",
                industry="金融業"
            ),
        ]
        
        for company in companies:
            session.add(company)
        
        session.commit()
        print(f"✅ Added {len(companies)} companies")
        
        # 2. 商材データ
        products = [
            Product(
                name="Webマーケティング支援サービス",
                description="SEO対策、広告運用、コンテンツ制作を一括サポート",
                message_template="弊社のWebマーケティング支援サービスについてご案内させていただきたく、ご連絡いたしました。"
            ),
            Product(
                name="業務効率化SaaS",
                description="クラウド型業務管理システムで生産性を向上",
                message_template="貴社の業務効率化に貢献できる弊社SaaSツールをご紹介させてください。"
            ),
        ]
        
        for product in products:
            session.add(product)
        
        session.commit()
        print(f"✅ Added {len(products)} products")
        
        # データベースから再取得（正しいIDを取得するため）
        companies = session.query(Company).order_by(Company.id.desc()).limit(5).all()
        companies.reverse()  # 古い順に並び替え
        products = session.query(Product).order_by(Product.id.desc()).limit(2).all()
        products.reverse()  # 古い順に並び替え
        
        # 3. タスクデータ（企業 × 商材の組み合わせ）
        tasks_created = 0
        for company in companies:
            for product in products:
                task = Task(
                    company_id=company.id,
                    product_id=product.id,
                    status='pending',
                    form_data={
                        'name': '山田太郎',
                        'email': 'yamada@example.com',
                        'company': '株式会社テスト',
                        'phone': '03-1234-5678',
                        'message': f"{product.message_template}\n\n{product.description}"
                    }
                )
                session.add(task)
                tasks_created += 1
        
        session.commit()
        print(f"✅ Added {tasks_created} tasks")
        
        print("\n🎉 Seed data completed!")
        print(f"   - Companies: {len(companies)}")
        print(f"   - Products: {len(products)}")
        print(f"   - Tasks: {tasks_created}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()

def add_projects_table():
    """Phase 2-A: simple_projectsテーブル追加"""
    print("\n📦 Adding simple_projects table...")
    Base.metadata.create_all(engine)
    print("✅ simple_projects table created!")

def add_company_fields():
    """Phase 2-A: simple_companiesにAI用フィールド追加"""
    print("\n📝 Adding AI fields to simple_companies...")
    
    with engine.connect() as conn:
        try:
            # ALTER TABLE を実行（既存カラムは無視される）
            conn.execute(text("""
                ALTER TABLE simple_companies 
                ADD COLUMN IF NOT EXISTS description TEXT,
                ADD COLUMN IF NOT EXISTS employee_count INTEGER,
                ADD COLUMN IF NOT EXISTS established_year INTEGER,
                ADD COLUMN IF NOT EXISTS capital VARCHAR(100);
            """))
            conn.commit()
            print("✅ AI fields added successfully!")
        except Exception as e:
            print(f"⚠️  Warning: {e}")
            print("   (カラムが既に存在する場合は無視されます)")

def seed_projects():
    """Phase 2-A: 案件テストデータ投入"""
    session = SessionLocal()
    
    try:
        print("\n🌱 Seeding project data...")
        
        projects = [
            Project(
                name="Webサイト制作営業 2025Q1",
                target_industry="IT・通信",
                message_template="貴社のWebサイトリニューアルについてご提案させていただきたく、ご連絡いたしました。",
                status='active'
            ),
            Project(
                name="業務効率化ツール営業 2025Q1",
                target_industry="製造業",
                message_template="製造業向けの業務効率化ツールのご紹介をさせていただきたく、ご連絡いたしました。",
                status='active'
            ),
        ]
        
        for project in projects:
            session.add(project)
        
        session.commit()
        print(f"✅ Added {len(projects)} projects")
        
        for project in projects:
            print(f"   - {project.name} (ID: {project.id})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 50)
    print("  Simple Database Setup - Phase 2-A")
    print("=" * 50)
    
    # Phase 1テーブル作成（既存）
    init_db()
    
    # Phase 2-A: 案件テーブル追加
    add_projects_table()
    
    # Phase 2-A: 企業テーブルにAI用フィールド追加
    add_company_fields()
    
    # テストデータ投入
    seed_data()
    seed_projects()
    
    print("\n✅ Setup completed!")
    print("Next: python -m http.server 8000")
    print("Then: Open simple-console-v2.html")
