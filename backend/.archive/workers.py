"""
Workers API endpoints.
CRUD operations for worker management.
"""

from flask import jsonify, request
from sqlalchemy.exc import IntegrityError
from backend.api import workers_bp
from backend.database import get_db_session
from backend.models import Worker


@workers_bp.route('', methods=['GET'])
def get_workers():
    """Get all workers"""
    db = get_db_session()
    try:
        workers = db.query(Worker).order_by(Worker.created_at.desc()).all()
        return jsonify([w.to_dict() for w in workers]), 200
    finally:
        db.close()


@workers_bp.route('/<int:worker_id>', methods=['GET'])
def get_worker(worker_id):
    """Get a specific worker by ID"""
    db = get_db_session()
    try:
        worker = db.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            return jsonify({'error': '作業者が見つかりません'}), 404
        return jsonify(worker.to_dict()), 200
    finally:
        db.close()


@workers_bp.route('', methods=['POST'])
def create_worker():
    """Create a new worker"""
    data = request.get_json()
    
    # Validation
    if not data.get('name') or not data.get('email'):
        return jsonify({'error': '名前とメールアドレスは必須です'}), 400
    
    db = get_db_session()
    try:
        worker = Worker(
            name=data['name'],
            email=data['email'],
            skill_level=data.get('skill_level', 'beginner'),
            points=data.get('points', 0)
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)
        return jsonify(worker.to_dict()), 201
    except IntegrityError:
        db.rollback()
        return jsonify({'error': 'このメールアドレスは既に登録されています'}), 409
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@workers_bp.route('/<int:worker_id>', methods=['PUT'])
def update_worker(worker_id):
    """Update an existing worker"""
    data = request.get_json()
    
    db = get_db_session()
    try:
        worker = db.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            return jsonify({'error': '作業者が見つかりません'}), 404
        
        # Update fields
        if 'name' in data:
            worker.name = data['name']
        if 'email' in data:
            worker.email = data['email']
        if 'skill_level' in data:
            worker.skill_level = data['skill_level']
        if 'points' in data:
            worker.points = data['points']
        
        db.commit()
        db.refresh(worker)
        return jsonify(worker.to_dict()), 200
    except IntegrityError:
        db.rollback()
        return jsonify({'error': 'このメールアドレスは既に使用されています'}), 409
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@workers_bp.route('/<int:worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    """Delete a worker"""
    db = get_db_session()
    try:
        worker = db.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            return jsonify({'error': '作業者が見つかりません'}), 404
        
        db.delete(worker)
        db.commit()
        return jsonify({'message': '作業者を削除しました'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@workers_bp.route('/<int:worker_id>/add-points', methods=['POST'])
def add_points(worker_id):
    """Add points to a worker"""
    data = request.get_json()
    points = data.get('points', 0)
    
    if not isinstance(points, int) or points < 0:
        return jsonify({'error': 'ポイントは0以上の整数である必要があります'}), 400
    
    db = get_db_session()
    try:
        worker = db.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            return jsonify({'error': '作業者が見つかりません'}), 404
        
        worker.points += points
        db.commit()
        db.refresh(worker)
        return jsonify(worker.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
