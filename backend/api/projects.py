"""
Projects API endpoints.
CRUD operations for project management.
"""

from flask import jsonify, request
from backend.api import projects_bp
from backend.database import get_db_session
from backend.models import Project, Worker, TargetList, TargetCompany, Task


@projects_bp.route('', methods=['GET'])
def get_projects():
    """Get all projects"""
    db = get_db_session()
    try:
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        return jsonify([p.to_dict() for p in projects]), 200
    finally:
        db.close()


@projects_bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):
    """Get a specific project by ID"""
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({'error': 'プロジェクトが見つかりません'}), 404
        
        # Include tasks in response
        result = project.to_dict()
        result['tasks'] = [t.to_dict() for t in project.tasks]
        return jsonify(result), 200
    finally:
        db.close()


@projects_bp.route('', methods=['POST'])
def create_project():
    """
    Create a new project and auto-generate tasks.
    
    Request body:
    {
        "name": "Project Name",
        "target_list_id": 1,
        "product_id": 1,
        "worker_ids": [1, 2, 3]
    }
    """
    data = request.get_json()
    
    # Validation
    if not data.get('name') or not data.get('target_list_id') or not data.get('product_id') or not data.get('worker_ids'):
        return jsonify({'error': 'プロジェクト名、ターゲットリスト、商品、作業者は必須です'}), 400
    
    db = get_db_session()
    try:
        # Verify target list exists
        target_list = db.query(TargetList).filter(TargetList.id == data['target_list_id']).first()
        if not target_list:
            return jsonify({'error': 'ターゲットリストが見つかりません'}), 404
        
        # Verify workers exist
        workers = db.query(Worker).filter(Worker.id.in_(data['worker_ids'])).all()
        if len(workers) != len(data['worker_ids']):
            return jsonify({'error': '一部の作業者が見つかりません'}), 404
        
        # Create project
        project = Project(
            name=data['name'],
            target_list_id=data['target_list_id'],
            product_id=data['product_id']
        )
        db.add(project)
        db.flush()  # Get project ID before creating tasks
        
        # Add workers to project
        project.workers = workers
        
        # Auto-generate tasks from target companies
        companies = db.query(TargetCompany).filter(
            TargetCompany.target_list_id == data['target_list_id']
        ).all()
        
        # Round-robin task assignment
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
        db.refresh(project)
        
        result = project.to_dict()
        result['tasks_created'] = len(created_tasks)
        return jsonify(result), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@projects_bp.route('/<int:project_id>', methods=['PUT'])
def update_project(project_id):
    """Update an existing project"""
    data = request.get_json()
    
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({'error': 'プロジェクトが見つかりません'}), 404
        
        # Update fields
        if 'name' in data:
            project.name = data['name']
        if 'target_list_id' in data:
            project.target_list_id = data['target_list_id']
        if 'product_id' in data:
            project.product_id = data['product_id']
        
        # Update workers if provided
        if 'worker_ids' in data:
            workers = db.query(Worker).filter(Worker.id.in_(data['worker_ids'])).all()
            project.workers = workers
        
        db.commit()
        db.refresh(project)
        return jsonify(project.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@projects_bp.route('/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project and all its tasks"""
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({'error': 'プロジェクトが見つかりません'}), 404
        
        db.delete(project)
        db.commit()
        return jsonify({'message': 'プロジェクトを削除しました'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@projects_bp.route('/<int:project_id>/stats', methods=['GET'])
def get_project_stats(project_id):
    """Get project statistics"""
    db = get_db_session()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({'error': 'プロジェクトが見つかりません'}), 404
        
        # Count tasks by status
        tasks = project.tasks
        stats = {
            'total': len(tasks),
            'pending': sum(1 for t in tasks if t.status == 'pending'),
            'in_progress': sum(1 for t in tasks if t.status == 'in_progress'),
            'completed': sum(1 for t in tasks if t.status == 'completed'),
            'ng': sum(1 for t in tasks if t.status == 'ng'),
            'skipped': sum(1 for t in tasks if t.status == 'skipped'),
            'submitted': sum(1 for t in tasks if t.submitted),
            'completion_rate': (sum(1 for t in tasks if t.status == 'completed') / len(tasks) * 100) if tasks else 0
        }
        
        return jsonify(stats), 200
    finally:
        db.close()
