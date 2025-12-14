"""
Database connection and session management for AI AutoForm.

This module provides SQLAlchemy engine and session configuration,
along with helper functions for database operations.
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL from environment variable
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/ai_autoform'
)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv('FLASK_ENV') == 'development',  # Log SQL queries in development
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=10,  # Maximum number of connections
    max_overflow=20,  # Maximum overflow connections
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Usage:
        with get_db() as db:
            db.query(Worker).all()
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get a database session for dependency injection.
    
    Usage in Flask:
        @app.route('/api/workers')
        def get_workers():
            db = get_db_session()
            try:
                workers = db.query(Worker).all()
                return jsonify([w.to_dict() for w in workers])
            finally:
                db.close()
    
    Returns:
        Session: SQLAlchemy database session
    """
    return SessionLocal()


def init_db():
    """
    Initialize the database by creating all tables.
    Should be called when the application starts.
    """
    from backend.models import (
        Worker, Product, TargetList, TargetCompany,
        Project, Task, project_workers
    )
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


def drop_db():
    """
    Drop all database tables.
    ⚠️ WARNING: This will delete all data!
    """
    Base.metadata.drop_all(bind=engine)
    print("⚠️ All database tables dropped")


# Database event listeners for connection management
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key constraints for SQLite (if used for testing)"""
    if 'sqlite' in DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log when a connection is checked out from the pool"""
    if os.getenv('FLASK_DEBUG') == 'True':
        print(f"🔌 Connection checked out from pool")


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log when a connection is returned to the pool"""
    if os.getenv('FLASK_DEBUG') == 'True':
        print(f"🔌 Connection returned to pool")
