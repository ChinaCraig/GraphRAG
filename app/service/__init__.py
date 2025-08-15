"""
Service包初始化文件
包含所有业务服务模块
"""

from .FileService import FileService

# 导入搜索相关服务
try:
    from .search.SearchService import SearchService
    
    search_services_available = True
except ImportError as e:
    print(f"搜索服务导入失败: {e}")
    search_services_available = False
    SearchService = None

__all__ = [
    'FileService'
]

# 如果搜索服务可用，添加到导出列表
if search_services_available:
    __all__.extend([
        'SearchService'
    ])