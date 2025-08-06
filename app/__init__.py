"""
GraphRAG应用包初始化文件
配置Flask应用和相关组件
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_cors import CORS
import yaml


def create_app(config_path='config/config.yaml'):
    """
    创建Flask应用实例
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        Flask: 配置好的Flask应用实例
    """
    # 创建Flask应用
    app = Flask(__name__)
    
    # 加载配置
    load_config(app, config_path)
    
    # 配置日志
    setup_logging(app)
    
    # 配置CORS
    setup_cors(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 注册before_request和after_request处理器
    register_request_handlers(app)
    
    app.logger.info("GraphRAG应用初始化完成")
    
    return app


def load_config(app, config_path):
    """
    加载应用配置
    
    Args:
        app: Flask应用实例
        config_path: 配置文件路径
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        
        # 应用配置
        app_config = config.get('app', {})
        app.config['SECRET_KEY'] = app_config.get('secret_key', 'your-secret-key-here')
        app.config['DEBUG'] = app_config.get('debug', False)
        
        # 文件配置
        file_config = config.get('file', {})
        app.config['MAX_CONTENT_LENGTH'] = file_config.get('max_file_size', 104857600)
        app.config['UPLOAD_FOLDER'] = file_config.get('upload_folder', './uploads')
        
        # 安全配置
        security_config = config.get('security', {})
        app.config['CORS_ENABLED'] = security_config.get('enable_cors', True)
        app.config['CORS_ORIGINS'] = security_config.get('cors_origins', ['*'])
        
        # 缓存配置
        cache_config = config.get('cache', {})
        app.config['CACHE_TYPE'] = cache_config.get('type', 'memory')
        app.config['CACHE_DEFAULT_TIMEOUT'] = cache_config.get('default_timeout', 3600)
        
        # 性能配置
        performance_config = config.get('performance', {})
        app.config['MAX_WORKERS'] = performance_config.get('max_workers', 4)
        app.config['TIMEOUT'] = performance_config.get('timeout', 300)
        
        app.logger.info("应用配置加载成功")
        
    except Exception as e:
        app.logger.error(f"加载应用配置失败: {str(e)}")
        # 使用默认配置
        app.config['SECRET_KEY'] = 'default-secret-key'
        app.config['DEBUG'] = False


def setup_logging(app):
    """
    设置日志配置
    
    Args:
        app: Flask应用实例
    """
    try:
        # 确保日志目录存在
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 设置日志级别
        if app.config.get('DEBUG'):
            app.logger.setLevel(logging.DEBUG)
        else:
            app.logger.setLevel(logging.INFO)
        
        # 文件处理器
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, 'app.log'),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        app.logger.addHandler(file_handler)
        
        # 控制台处理器（开发环境）
        if app.config.get('DEBUG'):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s'
            ))
            app.logger.addHandler(console_handler)
        
        app.logger.info("日志系统初始化完成")
        
    except Exception as e:
        print(f"设置日志配置失败: {str(e)}")


def setup_cors(app):
    """
    设置CORS配置
    
    Args:
        app: Flask应用实例
    """
    try:
        if app.config.get('CORS_ENABLED', True):
            CORS(
                app,
                origins=app.config.get('CORS_ORIGINS', ['*']),
                methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
                allow_headers=['Content-Type', 'Authorization'],
                supports_credentials=True
            )
            app.logger.info("CORS配置完成")
        
    except Exception as e:
        app.logger.error(f"设置CORS配置失败: {str(e)}")


def register_blueprints(app):
    """
    注册蓝图
    
    Args:
        app: Flask应用实例
    """
    try:
        from app.routes.FileRoutes import file_bp
        from app.routes.SearchRoutes import search_bp
        
        app.register_blueprint(file_bp)
        app.register_blueprint(search_bp)
        
        app.logger.info("蓝图注册完成")
        
    except Exception as e:
        app.logger.error(f"注册蓝图失败: {str(e)}")


def register_error_handlers(app):
    """
    注册错误处理器
    
    Args:
        app: Flask应用实例
    """
    @app.errorhandler(404)
    def not_found(error):
        return {
            'success': False,
            'message': '请求的资源不存在',
            'code': 404
        }, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"内部服务器错误: {str(error)}")
        return {
            'success': False,
            'message': '内部服务器错误',
            'code': 500
        }, 500
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return {
            'success': False,
            'message': '上传文件过大',
            'code': 413
        }, 413
    
    @app.errorhandler(400)
    def bad_request(error):
        return {
            'success': False,
            'message': '请求参数错误',
            'code': 400
        }, 400
    
    app.logger.info("错误处理器注册完成")


def register_request_handlers(app):
    """
    注册请求处理器
    
    Args:
        app: Flask应用实例
    """
    from datetime import datetime
    import time
    
    @app.before_request
    def before_request():
        """请求前处理"""
        from flask import g, request
        g.start_time = time.time()
        g.request_id = str(hash(f"{time.time()}_{request.remote_addr}"))
    
    @app.after_request
    def after_request(response):
        """请求后处理"""
        from flask import g, request
        
        # 计算响应时间
        if hasattr(g, 'start_time'):
            response_time = time.time() - g.start_time
            response.headers['X-Response-Time'] = str(response_time)
        
        # 添加请求ID
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
        
        # 记录访问日志
        if not request.path.startswith('/static'):
            app.logger.info(
                f"{request.method} {request.path} "
                f"{response.status_code} "
                f"{response_time:.3f}s "
                f"{request.remote_addr}"
            )
        
        return response
    
    app.logger.info("请求处理器注册完成")


# 创建应用实例的便捷函数
app = None

def get_app():
    """
    获取应用实例
    
    Returns:
        Flask: Flask应用实例
    """
    global app
    if app is None:
        app = create_app()
    return app