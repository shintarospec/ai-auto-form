"""
Simple Database Schema for Phase 1 MVP
シンプルな3テーブル構成
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Company(Base):
    """企業マスター"""
    __tablename__ = 'simple_companies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    website_url = Column(Text, nullable=False)
    form_url = Column(Text, nullable=False)
    industry = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tasks = relationship('Task', back_populates='company')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'website_url': self.website_url,
            'form_url': self.form_url,
            'industry': self.industry
        }


class Product(Base):
    """商材マスター"""
    __tablename__ = 'simple_products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    message_template = Column(Text)  # メッセージテンプレート
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tasks = relationship('Task', back_populates='product')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'message_template': self.message_template
        }


class Task(Base):
    """タスク（実行単位）"""
    __tablename__ = 'simple_tasks'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('simple_companies.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('simple_products.id'), nullable=False)
    status = Column(String(20), default='pending')  # pending, in_progress, completed, failed
    form_data = Column(JSON)  # {'name': '...', 'email': '...', 'message': '...'}
    screenshot_path = Column(Text)
    submitted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    company = relationship('Company', back_populates='tasks')
    product = relationship('Product', back_populates='tasks')
    
    def to_dict(self):
        return {
            'id': self.id,
            'company_id': self.company_id,
            'product_id': self.product_id,
            'company': self.company.to_dict() if self.company else None,
            'product': self.product.to_dict() if self.product else None,
            'status': self.status,
            'form_data': self.form_data,
            'screenshot_path': self.screenshot_path,
            'submitted': self.submitted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
