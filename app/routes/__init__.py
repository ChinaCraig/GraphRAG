"""
Routes包初始化文件
包含所有路由模块
"""

from .FileRoutes import file_bp
from .SearchRoutes import search_bp

__all__ = [
    'file_bp',
    'search_bp'
]