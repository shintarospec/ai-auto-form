"""
Tasks API endpoints.
CRUD operations and automation for task management.
"""

from datetime import datetime
from flask import jsonify, request
from backend.api import tasks_bp
from backend.database import get_db_session
from backend.models import Task, Worker
from backend.services.automation_service import FormAutomationService


@tasks_bp.route('', methods=['GET'])
def get_tasks():
    """Get all tasks, optionally filtered by worker_id, project_id, or status"""
    worker_id = request.args.get('worker_id', type=int)
    project_id = request.args.get('project_id', type=int)
    status = request.args.get('status')
    
    db = get_db_session()
    try:
        query = db.query(Task)
        
        if worker_id:
            query = query.filter(Task.worker_id == worker_id)
        if project_id:
            query = query.filter(Task.project_id == project_id)
        if status:
            query = query.filter(Task.status == status)
        
        tasks = query.order_by(Task.created_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks]), 200
    finally:
        db.close()


@tasks_bp.route('/<int:task_id>', methods=['GET'])
def get_task(task_id):
    """Get a specific task by ID"""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        return jsonify(task.to_dict()), 200
    finally:
        db.close()


@tasks_bp.route('', methods=['POST'])
def create_task():
    """Create a new task manually"""
    data = request.get_json()
    
    # Validation
    if not data.get('project_id') or not data.get('company_name') or not data.get('company_url'):
        return jsonify({'error': 'プロジェクトID、企業名、URLは必須です'}), 400
    
    db = get_db_session()
    try:
        task = Task(
            project_id=data['project_id'],
            worker_id=data.get('worker_id'),
            company_name=data['company_name'],
            company_url=data['company_url'],
            status=data.get('status', 'pending'),
            message=data.get('message')
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return jsonify(task.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@tasks_bp.route('/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """Update a task"""
    data = request.get_json()
    
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        # Update fields
        if 'worker_id' in data:
            task.worker_id = data['worker_id']
        if 'status' in data:
            task.status = data['status']
            # Set completed_at if status is completed
            if data['status'] == 'completed' and not task.completed_at:
                task.completed_at = datetime.utcnow()
        if 'message' in data:
            task.message = data['message']
        if 'submitted' in data:
            task.submitted = data['submitted']
        
        db.commit()
        db.refresh(task)
        return jsonify(task.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@tasks_bp.route('/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task"""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        db.delete(task)
        db.commit()
        return jsonify({'message': 'タスクを削除しました'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@tasks_bp.route('/<int:task_id>/submit', methods=['POST'])
def submit_task(task_id):
    """
    Execute form automation for a task.
    This is the main endpoint used by the worker console.
    """
    data = request.get_json()
    
    # Validation
    if not data.get('companyUrl') or not data.get('formData'):
        return jsonify({'error': 'URLとフォームデータは必須です'}), 400
    
    db = get_db_session()
    try:
        # Get task
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        # Update task status to in_progress
        task.status = 'in_progress'
        db.commit()
        
        # Execute automation - Use VNC mode (DISPLAY=:99)
        # Browser will be visible in noVNC (port 6080)
        automation = FormAutomationService(headless=False, display=':99')
        automation.start()
        
        # Convert form data to expected format
        message_data = {
            'sender_name': data['formData'].get('name', ''),
            'sender_email': data['formData'].get('email', ''),
            'sender_company': data['formData'].get('company', ''),
            'sender_phone': data['formData'].get('phone', ''),
            'message': data['formData'].get('message', '')
        }
        
        result = automation.fill_contact_form(
            form_url=data['companyUrl'],
            message_data=message_data,
            wait_for_captcha=True
        )
        
        automation.stop()
        
        # Update task based on result
        if result.get('success'):
            task.submitted = result.get('submitted', False)
            task.screenshot_path = result.get('screenshot')
            task.message = result.get('message')
            
            # If submitted successfully, mark as completed and award points
            if task.submitted:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                
                # Add points to worker
                if task.worker:
                    task.worker.points += 50
            else:
                # If only filled but not submitted, keep in_progress
                task.status = 'in_progress'
        else:
            # Error occurred
            task.status = 'in_progress'
            task.message = result.get('error', '不明なエラー')
        
        db.commit()
        db.refresh(task)
        
        # Return both automation result and updated task
        response = result.copy()
        response['task'] = task.to_dict()
        
        return jsonify(response), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@tasks_bp.route('/<int:task_id>/ng', methods=['POST'])
def mark_task_ng(task_id):
    """Mark a task as NG (inappropriate company)"""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        task.status = 'ng'
        task.completed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(task)
        return jsonify(task.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@tasks_bp.route('/<int:task_id>/skip', methods=['POST'])
def skip_task(task_id):
    """Skip a task temporarily"""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        task.status = 'skipped'
        
        db.commit()
        db.refresh(task)
        return jsonify(task.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@tasks_bp.route('/<int:task_id>/reset', methods=['POST'])
def reset_task(task_id):
    """Reset a task back to pending status"""
    db = get_db_session()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return jsonify({'error': 'タスクが見つかりません'}), 404
        
        task.status = 'pending'
        task.submitted = False
        task.completed_at = None
        task.message = None
        
        db.commit()
        db.refresh(task)
        return jsonify(task.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
