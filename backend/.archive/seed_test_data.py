"""
AI AutoForm - Test Data Seed Script
テスト用のサンプルデータを生成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.models import Worker, Product, TargetList, TargetCompany, Project, Task
from sqlalchemy import delete

def clear_all_data():
    """既存のテストデータをクリア"""
    db = SessionLocal()
    try:
        print("🗑️  既存データをクリア中...")
        db.execute(delete(Task))
        db.execute(delete(Project).execution_options(synchronize_session=False))
        db.execute(delete(TargetCompany))
        db.execute(delete(TargetList))
        db.execute(delete(Product))
        db.execute(delete(Worker))
        db.commit()
        print("✅ クリア完了")
    except Exception as e:
        db.rollback()
        print(f"❌ エラー: {e}")
    finally:
        db.close()

def seed_workers():
    """作業者データを生成"""
    db = SessionLocal()
    try:
        print("\n👥 作業者データ生成中...")
        workers = [
            # 上級者
            {"name": "田中太郎", "email": "tanaka@example.com", "skill_level": "advanced", "points": 1500},
            {"name": "山田花子", "email": "yamada@example.com", "skill_level": "advanced", "points": 1800},
            
            # 中級者
            {"name": "佐藤健一", "email": "sato@example.com", "skill_level": "intermediate", "points": 800},
            {"name": "鈴木美咲", "email": "suzuki@example.com", "skill_level": "intermediate", "points": 650},
            {"name": "高橋大輔", "email": "takahashi@example.com", "skill_level": "intermediate", "points": 720},
            {"name": "伊藤麻衣", "email": "ito@example.com", "skill_level": "intermediate", "points": 550},
            {"name": "渡辺拓海", "email": "watanabe@example.com", "skill_level": "intermediate", "points": 480},
            
            # 初級者
            {"name": "中村結衣", "email": "nakamura@example.com", "skill_level": "beginner", "points": 200},
            {"name": "小林航平", "email": "kobayashi@example.com", "skill_level": "beginner", "points": 150},
            {"name": "加藤さくら", "email": "kato@example.com", "skill_level": "beginner", "points": 100},
        ]
        
        created_workers = []
        for worker_data in workers:
            worker = Worker(**worker_data)
            db.add(worker)
            created_workers.append(worker)
        
        db.commit()
        print(f"✅ 作業者 {len(created_workers)}名を作成")
        return created_workers
    except Exception as e:
        db.rollback()
        print(f"❌ エラー: {e}")
        return []
    finally:
        db.close()

def seed_products():
    """商材データを生成"""
    db = SessionLocal()
    try:
        print("\n📦 商材データ生成中...")
        products = [
            {
                "name": "AIチャットボット導入パッケージ",
                "price": 500000,
                "description": "24時間365日対応可能なAIチャットボットで顧客対応を自動化。導入から運用まで完全サポート。"
            },
            {
                "name": "Webサイトリニューアルサービス",
                "price": 800000,
                "description": "モバイルファースト対応のレスポンシブデザイン。SEO対策込みで集客力を大幅アップ。"
            },
            {
                "name": "業務効率化コンサルティング",
                "price": 300000,
                "description": "現場診断から改善提案、ツール導入まで一気通貫。3ヶ月で業務時間30%削減を実現。"
            },
            {
                "name": "DX推進支援サービス",
                "price": 1200000,
                "description": "デジタルトランスフォーメーション戦略立案から実行支援まで。中小企業向けパッケージ。"
            },
            {
                "name": "SNSマーケティング代行",
                "price": 200000,
                "description": "Instagram/Twitter/Facebook運用代行。月間100投稿で認知度向上をサポート。"
            }
        ]
        
        created_products = []
        for product_data in products:
            product = Product(**product_data)
            db.add(product)
            created_products.append(product)
        
        db.commit()
        print(f"✅ 商材 {len(created_products)}件を作成")
        return created_products
    except Exception as e:
        db.rollback()
        print(f"❌ エラー: {e}")
        return []
    finally:
        db.close()

def seed_target_lists_and_companies():
    """ターゲットリストと企業データを生成"""
    db = SessionLocal()
    try:
        print("\n🎯 ターゲットリストと企業データ生成中...")
        
        # リスト1: IT企業向け
        list1 = TargetList(name="東京IT企業リスト（テスト用）")
        db.add(list1)
        db.flush()
        
        it_companies = [
            {"company_name": "テックイノベーション株式会社", "industry": "SaaS開発", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社クラウドソリューションズ", "industry": "クラウドサービス", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "デジタルマーケティングラボ", "industry": "マーケティング", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "AIシステムズ株式会社", "industry": "AI開発", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社データアナリティクス", "industry": "データ分析", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "Webソリューション株式会社", "industry": "Web制作", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社モバイルアプリ開発", "industry": "アプリ開発", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "セキュリティテック株式会社", "industry": "セキュリティ", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社IoTイノベーション", "industry": "IoT", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "エンタープライズシステムズ", "industry": "業務システム", "company_url": "http://localhost:8000/test-contact-form.html"},
        ]
        
        for company_data in it_companies:
            company = TargetCompany(target_list_id=list1.id, **company_data)
            db.add(company)
        
        # リスト2: 製造業向け
        list2 = TargetList(name="製造業DX推進リスト（テスト用）")
        db.add(list2)
        db.flush()
        
        manufacturing_companies = [
            {"company_name": "精密機械工業株式会社", "industry": "精密機械製造", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社オートメーション", "industry": "産業機械", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "電子部品製造株式会社", "industry": "電子部品", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社金属加工技研", "industry": "金属加工", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "プラスチック成型株式会社", "industry": "樹脂成型", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社組立システム", "industry": "組立製造", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "品質管理ソリューション", "industry": "品質管理", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社ロボティクス", "industry": "産業用ロボット", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "スマートファクトリー株式会社", "industry": "工場自動化", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "3Dプリンティング技術", "industry": "3D造形", "company_url": "http://localhost:8000/test-contact-form.html"},
        ]
        
        for company_data in manufacturing_companies:
            company = TargetCompany(target_list_id=list2.id, **company_data)
            db.add(company)
        
        # リスト3: 小売・サービス業向け
        list3 = TargetList(name="小売・サービス業EC支援リスト（テスト用）")
        db.add(list3)
        db.flush()
        
        retail_companies = [
            {"company_name": "株式会社ファッションリテール", "industry": "アパレル小売", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "グルメフーズ株式会社", "industry": "食品販売", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "ホームセンター大手", "industry": "生活雑貨", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社コスメティック", "industry": "化粧品販売", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "スポーツ用品専門店", "industry": "スポーツ用品", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社インテリアショップ", "industry": "家具販売", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "ペットショップチェーン", "industry": "ペット用品", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社書籍販売", "industry": "書店", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "おもちゃ専門店", "industry": "玩具販売", "company_url": "http://localhost:8000/test-contact-form.html"},
            {"company_name": "株式会社ギフトショップ", "industry": "ギフト販売", "company_url": "http://localhost:8000/test-contact-form.html"},
        ]
        
        for company_data in retail_companies:
            company = TargetCompany(target_list_id=list3.id, **company_data)
            db.add(company)
        
        db.commit()
        print(f"✅ ターゲットリスト 3件、企業 30社を作成")
        return [list1, list2, list3]
    except Exception as e:
        db.rollback()
        print(f"❌ エラー: {e}")
        return []
    finally:
        db.close()

def seed_test_project():
    """テスト用プロジェクトとタスクを自動生成"""
    db = SessionLocal()
    try:
        print("\n🚀 テストプロジェクト生成中...")
        
        # 作業者を取得（山田花子、田中太郎、佐藤健一）
        workers = db.query(Worker).filter(
            Worker.email.in_(['yamada@example.com', 'tanaka@example.com', 'sato@example.com'])
        ).all()
        
        if len(workers) < 3:
            print("❌ 作業者が見つかりません")
            return None
        
        # 商材を取得（AIチャットボット）
        product = db.query(Product).filter(Product.name.like('%AIチャットボット%')).first()
        if not product:
            print("❌ 商材が見つかりません")
            return None
        
        # ターゲットリストを取得（IT企業向け）
        target_list = db.query(TargetList).filter(TargetList.name.like('%IT企業%')).first()
        if not target_list:
            print("❌ ターゲットリストが見つかりません")
            return None
        
        # プロジェクト作成
        project = Project(
            name="IT企業向けAIチャットボット営業（テスト用）",
            target_list_id=target_list.id,
            product_id=product.id
        )
        db.add(project)
        db.flush()
        
        # 作業者をプロジェクトに割り当て
        project.workers = workers
        
        # ターゲット企業を取得
        companies = db.query(TargetCompany).filter(
            TargetCompany.target_list_id == target_list.id
        ).all()
        
        # タスクを自動生成（ラウンドロビン方式）
        created_tasks = []
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
            created_tasks.append(task)
        
        db.commit()
        print(f"✅ プロジェクト作成完了")
        print(f"   - プロジェクト名: {project.name}")
        print(f"   - タスク数: {len(created_tasks)}件")
        print(f"   - 担当作業者: {', '.join([w.name for w in workers])}")
        
        # 各作業者のタスク数を表示
        for worker in workers:
            task_count = len([t for t in created_tasks if t.worker_id == worker.id])
            print(f"     - {worker.name}: {task_count}件")
        
        return project
    except Exception as e:
        db.rollback()
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

def main():
    """メイン実行"""
    print("=" * 50)
    print("🌱 AI AutoForm - テストデータ生成")
    print("=" * 50)
    
    # データクリア
    clear_all_data()
    
    # データ生成
    workers = seed_workers()
    products = seed_products()
    target_lists = seed_target_lists_and_companies()
    project = seed_test_project()
    
    print("\n" + "=" * 50)
    print("✅ テストデータ生成完了")
    print("=" * 50)
    print(f"\n📊 生成されたデータ:")
    print(f"   - 作業者: {len(workers)}名")
    print(f"   - 商材: {len(products)}件")
    print(f"   - ターゲットリスト: {len(target_lists)}件")
    print(f"   - 企業: 30社")
    if project:
        print(f"   - テストプロジェクト: 1件（タスク自動生成済み）")
    print(f"\n💡 次のステップ:")
    print(f"   1. worker-console.htmlを開く")
    print(f"   2. 「山田花子」を選択")
    print(f"   3. コックピット画面でタスク実行")
    print(f"   4. 「自動送信スタート」をクリック")
    print()

if __name__ == "__main__":
    main()
