"""
Service包初始化文件
包含所有业务服务模块
"""

from .FileService import FileService

# 导入搜索相关服务
try:
    from .search.SearchRouteService import SearchRouteService
    from .search.SearchFormatService import SearchFormatService
    from .search.SearchAnswerService import SearchAnswerService
    
    search_services_available = True
except ImportError as e:
    print(f"搜索服务导入失败: {e}")
    search_services_available = False
    SearchRouteService = None
    SearchFormatService = None
    SearchAnswerService = None

__all__ = [
    'FileService'
]

# 如果搜索服务可用，添加到导出列表
if search_services_available:
    __all__.extend([
        'SearchRouteService',
        'SearchFormatService', 
        'SearchAnswerService'
    ])