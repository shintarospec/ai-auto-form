"""
Simple Database Migration - Phase 1 MVP
シンプルな3テーブルを作成してテストデータを投入
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.simple_models import Base, Company, Product, Task
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

if __name__ == "__main__":
    print("=" * 50)
    print("  Simple Database Setup - Phase 1 MVP")
    print("=" * 50)
    
    init_db()
    seed_data()
    
    print("\n✅ Setup completed!")
    print("Next: python -m http.server 8000")
    print("Then: Open simple-console.html")
