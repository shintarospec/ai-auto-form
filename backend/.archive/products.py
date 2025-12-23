"""
Products API endpoints.
CRUD operations for product management.
"""

from flask import jsonify, request
from backend.api import products_bp
from backend.database import get_db_session
from backend.models import Product


@products_bp.route('', methods=['GET'])
def get_products():
    """Get all products"""
    db = get_db_session()
    try:
        products = db.query(Product).order_by(Product.created_at.desc()).all()
        return jsonify([p.to_dict() for p in products]), 200
    finally:
        db.close()


@products_bp.route('/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Get a specific product by ID"""
    db = get_db_session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return jsonify({'error': '商品が見つかりません'}), 404
        return jsonify(product.to_dict()), 200
    finally:
        db.close()


@products_bp.route('', methods=['POST'])
def create_product():
    """Create a new product"""
    data = request.get_json()
    
    # Validation
    if not data.get('name') or not data.get('price'):
        return jsonify({'error': '商品名と価格は必須です'}), 400
    
    db = get_db_session()
    try:
        product = Product(
            name=data['name'],
            price=data['price'],
            description=data.get('description')
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return jsonify(product.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@products_bp.route('/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update an existing product"""
    data = request.get_json()
    
    db = get_db_session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return jsonify({'error': '商品が見つかりません'}), 404
        
        # Update fields
        if 'name' in data:
            product.name = data['name']
        if 'price' in data:
            product.price = data['price']
        if 'description' in data:
            product.description = data['description']
        
        db.commit()
        db.refresh(product)
        return jsonify(product.to_dict()), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@products_bp.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Delete a product"""
    db = get_db_session()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return jsonify({'error': '商品が見つかりません'}), 404
        
        db.delete(product)
        db.commit()
        return jsonify({'message': '商品を削除しました'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
