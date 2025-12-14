"""
API routes package for AI AutoForm.
"""

from flask import Blueprint

# Create blueprints for different resources
workers_bp = Blueprint('workers', __name__, url_prefix='/api/workers')
products_bp = Blueprint('products', __name__, url_prefix='/api/products')
projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')
tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')
targets_bp = Blueprint('targets', __name__, url_prefix='/api/targets')

# Import routes to register them with blueprints
from backend.api import workers, products, projects, tasks, targets

__all__ = ['workers_bp', 'products_bp', 'projects_bp', 'tasks_bp', 'targets_bp']
