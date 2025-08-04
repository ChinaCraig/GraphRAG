#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GraphRAG系统主应用
"""

from flask import Flask
import logging
import yaml
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(__file__))

from app.routes.FileRoutes import file_routes
from app.routes.SearchRoutes import search_routes

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """
    创建Flask应用
    """
    app = Flask(__name__)
    
    # 加载配置
    config_path = "config/config.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        app_config = config.get('app', {})
        app.secret_key = app_config.get('secret_key', 'your-secret-key-here')
        
        logger.info("应用配置加载成功")
        
    except Exception as e:
        logger.error(f"加载应用配置失败: {str(e)}")
        app.secret_key = 'your-secret-key-here'
    
    # 注册蓝图
    app.register_blueprint(file_routes)
    app.register_blueprint(search_routes)
    
    # 根路由
    @app.route('/')
    def index():
        return {
            'success': True,
            'message': 'GraphRAG系统运行正常',
            'data': {
                'version': '1.0.0',
                'description': 'GraphRAG智能文档检索系统'
            }
        }
    
    # 健康检查
    @app.route('/health')
    def health():
        return {
            'success': True,
            'message': '系统健康',
            'data': {
                'status': 'healthy',
                'timestamp': '2024-01-01 00:00:00'
            }
        }
    
    return app

def main():
    """
    主函数
    """
    app = create_app()
    
    # 获取配置
    config_path = "config/config.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        app_config = config.get('app', {})
        host = app_config.get('host', '0.0.0.0')
        port = app_config.get('port', 5000)
        debug = app_config.get('debug', True)
        
    except Exception as e:
        logger.error(f"加载配置失败: {str(e)}")
        host = '0.0.0.0'
        port = 5000
        debug = True
    
    logger.info(f"启动GraphRAG系统，地址: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    main() 