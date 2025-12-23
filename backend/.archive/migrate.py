"""
Migration script to transfer data from LocalStorage to PostgreSQL.

This script helps migrate existing LocalStorage data (from browser)
to the new PostgreSQL database.

Usage:
    1. Export LocalStorage data from browser console:
       localStorage.getItem('workers')  // Copy the output
       localStorage.getItem('products')
       localStorage.getItem('targetLists')
       localStorage.getItem('targets')
       localStorage.getItem('projects')
       localStorage.getItem('tasks')
    
    2. Save each as JSON files in migration_data/ directory
    
    3. Run this script:
       python backend/migrate.py
"""

import os
import json
from datetime import datetime
from backend.database import get_db_session, init_db
from backend.models import (
    Worker, Product, TargetList, TargetCompany,
    Project, Task
)


def load_json_file(filename):
    """Load JSON data from file"""
    filepath = os.path.join('migration_data', filename)
    if not os.path.exists(filepath):
        print(f"⚠️  File not found: {filepath}")
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"✅ Loaded {len(data) if isinstance(data, list) else 1} items from {filename}")
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Error loading {filename}: {e}")
        return []


def migrate_workers(db):
    """Migrate workers from LocalStorage"""
    print("\n🔄 Migrating workers...")
    workers_data = load_json_file('workers.json')
    
    for worker_data in workers_data:
        worker = Worker(
            id=worker_data.get('id'),
            name=worker_data.get('name'),
            email=worker_data.get('email'),
            skill_level=worker_data.get('skillLevel', 'beginner'),
            points=worker_data.get('points', 0)
        )
        db.add(worker)
    
    db.commit()
    print(f"✅ Migrated {len(workers_data)} workers")


def migrate_products(db):
    """Migrate products from LocalStorage"""
    print("\n🔄 Migrating products...")
    products_data = load_json_file('products.json')
    
    for product_data in products_data:
        product = Product(
            id=product_data.get('id'),
            name=product_data.get('name'),
            price=product_data.get('price'),
            description=product_data.get('description')
        )
        db.add(product)
    
    db.commit()
    print(f"✅ Migrated {len(products_data)} products")


def migrate_target_lists_and_companies(db):
    """Migrate target lists and companies from LocalStorage"""
    print("\n🔄 Migrating target lists and companies...")
    
    # Load target lists
    target_lists_data = load_json_file('targetLists.json')
    
    # Load targets (companies)
    targets_data = load_json_file('targets.json')
    
    # Create target lists
    list_id_map = {}
    for list_data in target_lists_data:
        target_list = TargetList(
            id=list_data.get('id'),
            name=list_data.get('name')
        )
        db.add(target_list)
        db.flush()
        list_id_map[list_data.get('id')] = target_list.id
    
    db.commit()
    print(f"✅ Migrated {len(target_lists_data)} target lists")
    
    # Create companies
    for target_data in targets_data:
        company = TargetCompany(
            target_list_id=target_data.get('targetListId'),
            company_name=target_data.get('companyName'),
            company_url=target_data.get('companyUrl'),
            industry=target_data.get('industry')
        )
        db.add(company)
    
    db.commit()
    print(f"✅ Migrated {len(targets_data)} target companies")


def migrate_projects(db):
    """Migrate projects from LocalStorage"""
    print("\n🔄 Migrating projects...")
    projects_data = load_json_file('projects.json')
    
    for project_data in projects_data:
        project = Project(
            id=project_data.get('id'),
            name=project_data.get('name'),
            target_list_id=project_data.get('targetListId'),
            product_id=project_data.get('productId')
        )
        db.add(project)
        db.flush()
        
        # Add workers to project (many-to-many relationship)
        worker_ids = project_data.get('workerIds', [])
        if worker_ids:
            workers = db.query(Worker).filter(Worker.id.in_(worker_ids)).all()
            project.workers = workers
    
    db.commit()
    print(f"✅ Migrated {len(projects_data)} projects")


def migrate_tasks(db):
    """Migrate tasks from LocalStorage"""
    print("\n🔄 Migrating tasks...")
    tasks_data = load_json_file('tasks.json')
    
    for task_data in tasks_data:
        task = Task(
            id=task_data.get('id'),
            project_id=task_data.get('projectId'),
            worker_id=task_data.get('workerId'),
            company_name=task_data.get('companyName'),
            company_url=task_data.get('companyUrl'),
            status=task_data.get('status', 'pending'),
            message=task_data.get('message'),
            submitted=task_data.get('submitted', False)
        )
        db.add(task)
    
    db.commit()
    print(f"✅ Migrated {len(tasks_data)} tasks")


def create_sample_data(db):
    """Create sample data if migration_data directory doesn't exist"""
    print("\n🔄 Creating sample data...")
    
    # Sample workers
    workers = [
        Worker(name="田中太郎", email="tanaka@example.com", skill_level="advanced", points=1500),
        Worker(name="佐藤花子", email="sato@example.com", skill_level="intermediate", points=800),
        Worker(name="鈴木次郎", email="suzuki@example.com", skill_level="beginner", points=300),
    ]
    for worker in workers:
        db.add(worker)
    db.commit()
    print(f"✅ Created {len(workers)} sample workers")
    
    # Sample products
    products = [
        Product(name="AIチャットボット導入パッケージ", price=500000, description="導入から運用まで完全サポート"),
        Product(name="Webサイト制作サービス", price=300000, description="レスポンシブ対応の高品質サイト"),
    ]
    for product in products:
        db.add(product)
    db.commit()
    print(f"✅ Created {len(products)} sample products")
    
    # Sample target list
    target_list = TargetList(name="2025年1月営業先リスト")
    db.add(target_list)
    db.commit()
    print(f"✅ Created sample target list")
    
    # Sample companies
    companies = [
        TargetCompany(
            target_list_id=target_list.id,
            company_name="株式会社ABC",
            company_url="http://localhost:8000/test-form.html",
            industry="IT"
        ),
        TargetCompany(
            target_list_id=target_list.id,
            company_name="株式会社XYZ",
            company_url="http://localhost:8000/test-form.html",
            industry="製造業"
        ),
    ]
    for company in companies:
        db.add(company)
    db.commit()
    print(f"✅ Created {len(companies)} sample companies")
    
    # Sample project
    project = Project(
        name="2025年1月営業キャンペーン",
        target_list_id=target_list.id,
        product_id=products[0].id
    )
    db.add(project)
    db.flush()
    
    # Assign all workers to project
    project.workers = workers
    db.commit()
    print(f"✅ Created sample project")
    
    # Sample tasks (auto-generated from companies)
    for i, company in enumerate(companies):
        assigned_worker = workers[i % len(workers)]
        task = Task(
            project_id=project.id,
            worker_id=assigned_worker.id,
            company_name=company.company_name,
            company_url=company.company_url,
            status='pending'
        )
        db.add(task)
    
    db.commit()
    print(f"✅ Created {len(companies)} sample tasks")


def main():
    """Main migration function"""
    print("""
    ╔═══════════════════════════════════════════╗
    ║   AI AutoForm - Data Migration            ║
    ║   LocalStorage → PostgreSQL               ║
    ╚═══════════════════════════════════════════╝
    """)
    
    # Initialize database (create tables)
    print("\n📋 Initializing database...")
    init_db()
    
    db = get_db_session()
    
    try:
        # Check if migration_data directory exists
        if os.path.exists('migration_data'):
            print("\n📁 Found migration_data directory. Starting migration...\n")
            
            # Migrate in order (respecting foreign key constraints)
            migrate_workers(db)
            migrate_products(db)
            migrate_target_lists_and_companies(db)
            migrate_projects(db)
            migrate_tasks(db)
            
            print("\n✅ Migration completed successfully!")
        else:
            print("\n📁 migration_data directory not found.")
            print("Creating sample data instead...\n")
            create_sample_data(db)
            print("\n✅ Sample data created successfully!")
        
        # Print summary
        print("\n📊 Database Summary:")
        print(f"   Workers: {db.query(Worker).count()}")
        print(f"   Products: {db.query(Product).count()}")
        print(f"   Target Lists: {db.query(TargetList).count()}")
        print(f"   Target Companies: {db.query(TargetCompany).count()}")
        print(f"   Projects: {db.query(Project).count()}")
        print(f"   Tasks: {db.query(Task).count()}")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
    
    print("\n🎉 Done!\n")


if __name__ == '__main__':
    main()
