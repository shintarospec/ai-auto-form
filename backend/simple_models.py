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
    
    # 送信者情報（案件ごとに異なる）
    # 基本情報（氏名）
    sender_name = Column(String(100))  # 送信者名（フルネーム、後方互換性のため残す）
    sender_last_name = Column(String(50))  # 姓
    sender_first_name = Column(String(50))  # 名
    sender_last_name_kana = Column(String(50))  # 姓フリガナ
    sender_first_name_kana = Column(String(50))  # 名フリガナ
    sender_gender = Column(String(10))  # 性別（男性/女性）
    
    # 会社情報
    sender_company = Column(String(200))  # 送信者会社名
    sender_company_kana = Column(String(200))  # 会社名フリガナ
    sender_company_url = Column(String(500))  # 会社URL
    sender_department = Column(String(100))  # 部署名
    sender_position = Column(String(100))  # 役職
    sender_rep_name = Column(String(100))  # 代表電話番号 氏名
    sender_rep_name_kana = Column(String(100))  # 代表電話番号 氏名フリガナ
    
    # 連絡先（分割対応）
    sender_phone = Column(String(50))  # 電話番号（統合、後方互換性のため残す）
    sender_phone_1 = Column(String(10))  # 電話番号1（市外局番）
    sender_phone_2 = Column(String(10))  # 電話番号2（市内局番）
    sender_phone_3 = Column(String(10))  # 電話番号3（加入者番号）
    sender_mobile_1 = Column(String(10))  # 携帯番号1
    sender_mobile_2 = Column(String(10))  # 携帯番号2
    sender_mobile_3 = Column(String(10))  # 携帯番号3
    sender_fax_1 = Column(String(10))  # FAX番号1
    sender_fax_2 = Column(String(10))  # FAX番号2
    sender_fax_3 = Column(String(10))  # FAX番号3
    
    # メールアドレス
    sender_email = Column(String(200))  # メールアドレス（統合、後方互換性のため残す）
    sender_email_company = Column(String(200))  # 会社用メール
    sender_email_personal = Column(String(200))  # 担当者用メール
    
    # 住所（分割対応）
    sender_zipcode_1 = Column(String(10))  # 郵便番号1（3桁）
    sender_zipcode_2 = Column(String(10))  # 郵便番号2（4桁）
    sender_prefecture = Column(String(50))  # 都道府県
    sender_city = Column(String(100))  # 市区
    sender_address = Column(String(500))  # 町名以降
    
    # お問い合わせ内容
    sender_inquiry_title = Column(String(500))  # お問い合わせタイトル
    sender_inquiry_detail = Column(Text)  # お問い合わせ詳細
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tasks = relationship('Task', back_populates='product')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'message_template': self.message_template,
            # 基本情報
            'sender_name': self.sender_name,
            'sender_last_name': self.sender_last_name,
            'sender_first_name': self.sender_first_name,
            'sender_last_name_kana': self.sender_last_name_kana,
            'sender_first_name_kana': self.sender_first_name_kana,
            'sender_gender': self.sender_gender,
            # 会社情報
            'sender_company': self.sender_company,
            'sender_company_kana': self.sender_company_kana,
            'sender_company_url': self.sender_company_url,
            'sender_department': self.sender_department,
            'sender_position': self.sender_position,
            'sender_rep_name': self.sender_rep_name,
            'sender_rep_name_kana': self.sender_rep_name_kana,
            # 連絡先
            'sender_phone': self.sender_phone,
            'sender_phone_1': self.sender_phone_1,
            'sender_phone_2': self.sender_phone_2,
            'sender_phone_3': self.sender_phone_3,
            'sender_mobile_1': self.sender_mobile_1,
            'sender_mobile_2': self.sender_mobile_2,
            'sender_mobile_3': self.sender_mobile_3,
            'sender_fax_1': self.sender_fax_1,
            'sender_fax_2': self.sender_fax_2,
            'sender_fax_3': self.sender_fax_3,
            # メール
            'sender_email': self.sender_email,
            'sender_email_company': self.sender_email_company,
            'sender_email_personal': self.sender_email_personal,
            # 住所
            'sender_zipcode_1': self.sender_zipcode_1,
            'sender_zipcode_2': self.sender_zipcode_2,
            'sender_prefecture': self.sender_prefecture,
            'sender_city': self.sender_city,
            'sender_address': self.sender_address,
            # お問い合わせ
            'sender_inquiry_title': self.sender_inquiry_title,
            'sender_inquiry_detail': self.sender_inquiry_detail
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
