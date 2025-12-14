"""
SQLAlchemy models for AI AutoForm.

Defines database tables and their relationships using SQLAlchemy ORM.
"""

from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean,
    ForeignKey, Table, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from backend.database import Base


# Association table for many-to-many relationship between Projects and Workers
project_workers = Table(
    'project_workers',
    Base.metadata,
    Column('project_id', Integer, ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True),
    Column('worker_id', Integer, ForeignKey('workers.id', ondelete='CASCADE'), primary_key=True)
)


class Worker(Base):
    """
    作業者テーブル
    フォーム送信を担当するワーカーの情報を管理
    """
    __tablename__ = 'workers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    skill_level = Column(
        SQLEnum('beginner', 'intermediate', 'advanced', name='skill_level_enum'),
        default='beginner',
        nullable=False
    )
    points = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    tasks = relationship('Task', back_populates='worker', cascade='all, delete-orphan')
    projects = relationship('Project', secondary=project_workers, back_populates='workers')

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'skill_level': self.skill_level,
            'points': self.points,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Worker(id={self.id}, name='{self.name}', email='{self.email}')>"


class Product(Base):
    """
    商品テーブル
    営業対象の商品・サービス情報を管理
    """
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    price = Column(Integer, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    projects = relationship('Project', back_populates='product')

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', price={self.price})>"


class TargetList(Base):
    """
    ターゲットリストテーブル
    営業先企業リストを管理
    """
    __tablename__ = 'target_lists'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    companies = relationship('TargetCompany', back_populates='target_list', cascade='all, delete-orphan')
    projects = relationship('Project', back_populates='target_list')

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'company_count': len(self.companies) if self.companies else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<TargetList(id={self.id}, name='{self.name}')>"


class TargetCompany(Base):
    """
    ターゲット企業テーブル
    営業先企業の詳細情報を管理
    """
    __tablename__ = 'target_companies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_list_id = Column(Integer, ForeignKey('target_lists.id', ondelete='CASCADE'), nullable=False, index=True)
    company_name = Column(String(200), nullable=False)
    company_url = Column(Text, nullable=False)
    industry = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    target_list = relationship('TargetList', back_populates='companies')

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'target_list_id': self.target_list_id,
            'company_name': self.company_name,
            'company_url': self.company_url,
            'industry': self.industry,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<TargetCompany(id={self.id}, name='{self.company_name}')>"


class Project(Base):
    """
    プロジェクトテーブル
    営業キャンペーンの管理（ターゲットリスト × 商品 × 作業者）
    """
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    target_list_id = Column(Integer, ForeignKey('target_lists.id', ondelete='SET NULL'), index=True)
    product_id = Column(Integer, ForeignKey('products.id', ondelete='SET NULL'), index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    target_list = relationship('TargetList', back_populates='projects')
    product = relationship('Product', back_populates='projects')
    workers = relationship('Worker', secondary=project_workers, back_populates='projects')
    tasks = relationship('Task', back_populates='project', cascade='all, delete-orphan')

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'target_list_id': self.target_list_id,
            'target_list_name': self.target_list.name if self.target_list else None,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'worker_ids': [w.id for w in self.workers] if self.workers else [],
            'worker_names': [w.name for w in self.workers] if self.workers else [],
            'task_count': len(self.tasks) if self.tasks else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}')>"


class Task(Base):
    """
    タスクテーブル
    個別のフォーム送信タスクを管理
    """
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True)
    worker_id = Column(Integer, ForeignKey('workers.id', ondelete='SET NULL'), index=True)
    company_name = Column(String(200), nullable=False)
    company_url = Column(Text, nullable=False)
    status = Column(
        SQLEnum('pending', 'in_progress', 'completed', 'ng', 'skipped', name='task_status_enum'),
        default='pending',
        nullable=False,
        index=True
    )
    message = Column(Text)
    submitted = Column(Boolean, default=False, nullable=False)
    screenshot_path = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship('Project', back_populates='tasks')
    worker = relationship('Worker', back_populates='tasks')

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'worker_id': self.worker_id,
            'worker_name': self.worker.name if self.worker else None,
            'company_name': self.company_name,
            'company_url': self.company_url,
            'status': self.status,
            'message': self.message,
            'submitted': self.submitted,
            'screenshot_path': self.screenshot_path,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Task(id={self.id}, company='{self.company_name}', status='{self.status}')>"
