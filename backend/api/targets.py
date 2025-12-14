"""
Target Lists and Target Companies API endpoints.
CRUD operations for target list management.
"""

from flask import jsonify, request
from backend.api import targets_bp
from backend.database import get_db_session
from backend.models import TargetList, TargetCompany


# Target Lists endpoints

@targets_bp.route('/lists', methods=['GET'])
def get_target_lists():
    """Get all target lists"""
    db = get_db_session()
    try:
        lists = db.query(TargetList).order_by(TargetList.created_at.desc()).all()
        return jsonify([l.to_dict() for l in lists]), 200
    finally:
        db.close()


@targets_bp.route('/lists/<int:list_id>', methods=['GET'])
def get_target_list(list_id):
    """Get a specific target list by ID"""
    db = get_db_session()
    try:
        target_list = db.query(TargetList).filter(TargetList.id == list_id).first()
        if not target_list:
            return jsonify({'error': 'ターゲットリストが見つかりません'}), 404
        
        # Include companies in response
        result = target_list.to_dict()
        result['companies'] = [c.to_dict() for c in target_list.companies]
        return jsonify(result), 200
    finally:
        db.close()


@targets_bp.route('/lists', methods=['POST'])
def create_target_list():
    """Create a new target list"""
    data = request.get_json()
    
    # Validation
    if not data.get('name'):
        return jsonify({'error': 'リスト名は必須です'}), 400
    
    db = get_db_session()
    try:
        target_list = TargetList(name=data['name'])
        db.add(target_list)
        db.commit()
        db.refresh(target_list)
        return jsonify(target_list.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@targets_bp.route('/lists/<int:list_id>', methods=['PUT'])
def update_target_list(list_id):
    """Update a target list name"""
    data = request.get_json()
    
    db = get_db_session()
    try:
        target_list = db.query(TargetList).filter(TargetList.id == list_id).first()
        if not target_list:
            return jsonify({'error': 'ターゲットリストが見つかりません'}), 404
        
        if 'name' in data:
            target_list.name = data['name']
        
        db.commit()
        db.refresh(target_list)
        return jsonify(target_list.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@targets_bp.route('/lists/<int:list_id>', methods=['DELETE'])
def delete_target_list(list_id):
    """Delete a target list and all its companies"""
    db = get_db_session()
    try:
        target_list = db.query(TargetList).filter(TargetList.id == list_id).first()
        if not target_list:
            return jsonify({'error': 'ターゲットリストが見つかりません'}), 404
        
        db.delete(target_list)
        db.commit()
        return jsonify({'message': 'ターゲットリストを削除しました'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# Target Companies endpoints

@targets_bp.route('/companies', methods=['GET'])
def get_companies():
    """Get all target companies, optionally filtered by list_id"""
    list_id = request.args.get('list_id', type=int)
    
    db = get_db_session()
    try:
        query = db.query(TargetCompany)
        if list_id:
            query = query.filter(TargetCompany.target_list_id == list_id)
        
        companies = query.order_by(TargetCompany.created_at.desc()).all()
        return jsonify([c.to_dict() for c in companies]), 200
    finally:
        db.close()


@targets_bp.route('/companies/<int:company_id>', methods=['GET'])
def get_company(company_id):
    """Get a specific target company by ID"""
    db = get_db_session()
    try:
        company = db.query(TargetCompany).filter(TargetCompany.id == company_id).first()
        if not company:
            return jsonify({'error': '企業が見つかりません'}), 404
        return jsonify(company.to_dict()), 200
    finally:
        db.close()


@targets_bp.route('/companies', methods=['POST'])
def create_company():
    """Add a new company to a target list"""
    data = request.get_json()
    
    # Validation
    if not data.get('target_list_id') or not data.get('company_name') or not data.get('company_url'):
        return jsonify({'error': 'リストID、企業名、URLは必須です'}), 400
    
    db = get_db_session()
    try:
        company = TargetCompany(
            target_list_id=data['target_list_id'],
            company_name=data['company_name'],
            company_url=data['company_url'],
            industry=data.get('industry')
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        return jsonify(company.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@targets_bp.route('/companies/bulk', methods=['POST'])
def bulk_create_companies():
    """Bulk add companies to a target list (CSV upload)"""
    data = request.get_json()
    
    # Validation
    if not data.get('target_list_id') or not data.get('companies'):
        return jsonify({'error': 'リストIDと企業データは必須です'}), 400
    
    target_list_id = data['target_list_id']
    companies_data = data['companies']
    
    db = get_db_session()
    try:
        # Verify target list exists
        target_list = db.query(TargetList).filter(TargetList.id == target_list_id).first()
        if not target_list:
            return jsonify({'error': 'ターゲットリストが見つかりません'}), 404
        
        # Create companies
        created_companies = []
        for company_data in companies_data:
            company = TargetCompany(
                target_list_id=target_list_id,
                company_name=company_data['company_name'],
                company_url=company_data['company_url'],
                industry=company_data.get('industry')
            )
            db.add(company)
            created_companies.append(company)
        
        db.commit()
        
        return jsonify({
            'message': f'{len(created_companies)}件の企業を追加しました',
            'count': len(created_companies),
            'companies': [c.to_dict() for c in created_companies]
        }), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@targets_bp.route('/companies/<int:company_id>', methods=['PUT'])
def update_company(company_id):
    """Update a target company"""
    data = request.get_json()
    
    db = get_db_session()
    try:
        company = db.query(TargetCompany).filter(TargetCompany.id == company_id).first()
        if not company:
            return jsonify({'error': '企業が見つかりません'}), 404
        
        # Update fields
        if 'company_name' in data:
            company.company_name = data['company_name']
        if 'company_url' in data:
            company.company_url = data['company_url']
        if 'industry' in data:
            company.industry = data['industry']
        
        db.commit()
        db.refresh(company)
        return jsonify(company.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@targets_bp.route('/companies/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    """Delete a target company"""
    db = get_db_session()
    try:
        company = db.query(TargetCompany).filter(TargetCompany.id == company_id).first()
        if not company:
            return jsonify({'error': '企業が見つかりません'}), 404
        
        db.delete(company)
        db.commit()
        return jsonify({'message': '企業を削除しました'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
