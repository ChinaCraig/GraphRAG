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
from app.utils.websocket import init_socketio


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
    
    # 注册前端路由
    register_frontend_routes(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 注册before_request和after_request处理器
    register_request_handlers(app)
    
    # 初始化SocketIO
    socketio = init_socketio(app)
    app.socketio = socketio
    
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
        # 在开发阶段，即使蓝图注册失败也继续运行（仅用于前端测试）
        app.logger.warning("继续运行前端服务，但后端API可能不可用")


def register_frontend_routes(app):
    """
    注册前端路由
    
    Args:
        app: Flask应用实例
    """
    from flask import send_from_directory, jsonify
    
    @app.route('/')
    def index():
        """
        前端首页路由
        
        Returns:
            HTML页面
        """
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html_dir = os.path.join(base_dir, 'app', 'templates', 'html')
        index_file = os.path.join(html_dir, 'index.html')
        
        app.logger.info(f"访问首页路由 - base_dir: {base_dir}")
        app.logger.info(f"访问首页路由 - html_dir: {html_dir}")
        app.logger.info(f"访问首页路由 - index_file exists: {os.path.exists(index_file)}")
        
        if not os.path.exists(index_file):
            app.logger.error(f"index.html文件不存在: {index_file}")
            return {"success": False, "message": f"index.html not found at {index_file}"}, 404
            
        return send_from_directory(html_dir, 'index.html')

    @app.route('/api')
    def api_index():
        """
        API首页路由
        
        Returns:
            JSON响应
        """
        return jsonify({
            'success': True,
            'message': 'GraphRAG服务运行正常',
            'version': '1.0.0',
            'endpoints': {
                'file_management': '/api/file/',
                'search': '/api/search/',
                'health': '/health',
                'docs': '/docs'
            }
        })

    @app.route('/static/css/<path:filename>')
    def css_files(filename):
        """
        CSS文件路由
        """
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        css_dir = os.path.join(base_dir, 'app', 'templates', 'css')
        return send_from_directory(css_dir, filename)

    @app.route('/static/js/<path:filename>')
    def js_files(filename):
        """
        JavaScript文件路由
        """
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        js_dir = os.path.join(base_dir, 'app', 'templates', 'js')
        return send_from_directory(js_dir, filename)

    @app.route('/health')
    def health_check():
        """
        健康检查路由
        
        Returns:
            JSON响应
        """
        try:
            # 这里可以添加数据库连接检查等健康检查逻辑
            health_status = {
                'status': 'healthy',
                'timestamp': '2024-01-01T00:00:00Z',
                'checks': {
                    'database': 'ok',
                    'vector_db': 'ok',
                    'graph_db': 'ok'
                }
            }
            
            return jsonify({
                'success': True,
                'data': health_status
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'健康检查失败: {str(e)}',
                'status': 'unhealthy'
            }), 500

    @app.route('/docs')
    def api_docs():
        """
        API文档路由
        
        Returns:
            JSON响应
        """
        docs = {
            'title': 'GraphRAG API Documentation',
            'version': '1.0.0',
            'description': '基于知识图谱的检索增强生成系统API',
            'endpoints': {
                'file_management': {
                    'POST /api/file/upload': '上传文件',
                    'GET /api/file/list': '获取文件列表',
                    'GET /api/file/<id>': '获取文件详情',
                    'DELETE /api/file/<id>': '删除文件',
                    'POST /api/file/<id>/process': '处理文件',
                    'GET /api/file/stats': '获取文件统计',
                    'POST /api/file/cleanup': '清理临时文件'
                },
                'search': {
                    'POST /api/search/vector': '向量搜索',
                    'POST /api/search/graph': '图谱搜索',
                    'POST /api/search/hybrid': '混合搜索',
                    'POST /api/search/semantic': '语义搜索',
                    'POST /api/search/qa': '智能问答',
                    'GET /api/search/suggestions': '搜索建议',
                    'GET /api/search/history': '搜索历史',
                    'GET /api/search/stats': '搜索统计'
                },
                'system': {
                    'GET /': '系统信息',
                    'GET /health': '健康检查',
                    'GET /docs': 'API文档'
                }
            }
        }
        
        return jsonify(docs)
    
    # 打印所有注册的路由用于调试
    app.logger.info("前端路由注册完成")
    app.logger.info("已注册的路由:")
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/static'):  # 简化输出，忽略静态文件
            app.logger.info(f"  {rule.rule} -> {rule.endpoint}")


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