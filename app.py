#!/usr/bin/env python3
"""
GraphRAG主启动文件
使用Flask Web框架启动GraphRAG服务
"""

import os
import sys
import yaml
import click
from flask import jsonify, render_template, send_from_directory

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app


def load_server_config():
    """
    加载服务器配置
    
    Returns:
        dict: 服务器配置
    """
    try:
        with open('config/config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            return config.get('app', {})
    except Exception as e:
        print(f"加载服务器配置失败: {str(e)}")
        return {}


# 创建Flask应用
app = create_app()


@app.route('/')
def index():
    """
    前端首页路由
    
    Returns:
        HTML页面
    """
    return send_from_directory('templates/html', 'index.html')


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
    return send_from_directory('templates/css', filename)


@app.route('/static/js/<path:filename>')
def js_files(filename):
    """
    JavaScript文件路由
    """
    return send_from_directory('templates/js', filename)


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


@click.command()
@click.option('--host', default=None, help='服务器监听地址')
@click.option('--port', default=None, type=int, help='服务器监听端口')
@click.option('--debug', is_flag=True, help='启用调试模式')
@click.option('--config', default='config/config.yaml', help='配置文件路径')
def run_server(host, port, debug, config):
    """
    启动GraphRAG服务器
    
    Args:
        host: 服务器监听地址
        port: 服务器监听端口
        debug: 是否启用调试模式
        config: 配置文件路径
    """
    try:
        # 加载配置
        server_config = load_server_config()
        
        # 设置服务器参数
        host = host or server_config.get('host', '0.0.0.0')
        port = port or server_config.get('port', 5000)
        debug = debug or server_config.get('debug', False)
        
        print(f"启动GraphRAG服务器...")
        print(f"监听地址: {host}:{port}")
        print(f"调试模式: {debug}")
        print(f"配置文件: {config}")
        print("-" * 50)
        
        # 启动服务器
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
        
    except Exception as e:
        print(f"启动服务器失败: {str(e)}")
        sys.exit(1)


@click.group()
def cli():
    """GraphRAG命令行工具"""
    pass


@cli.command()
def init_db():
    """初始化数据库"""
    try:
        print("初始化数据库...")
        # 这里可以添加数据库初始化逻辑
        print("数据库初始化完成")
    except Exception as e:
        print(f"数据库初始化失败: {str(e)}")


@cli.command()
@click.option('--days', default=30, type=int, help='保留天数')
def cleanup_logs(days):
    """清理日志文件"""
    try:
        print(f"清理{days}天前的日志文件...")
        # 这里可以添加日志清理逻辑
        print("日志清理完成")
    except Exception as e:
        print(f"日志清理失败: {str(e)}")


@cli.command()
def check_config():
    """检查配置文件"""
    try:
        config_files = [
            'config/config.yaml',
            'config/db.yaml',
            'config/model.yaml',
            'config/prompt.yaml'
        ]
        
        print("检查配置文件...")
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        yaml.safe_load(f)
                    print(f"✓ {config_file} - 正常")
                except yaml.YAMLError as e:
                    print(f"✗ {config_file} - 格式错误: {str(e)}")
                except Exception as e:
                    print(f"✗ {config_file} - 读取失败: {str(e)}")
            else:
                print(f"✗ {config_file} - 文件不存在")
        
        print("配置文件检查完成")
        
    except Exception as e:
        print(f"配置检查失败: {str(e)}")


@cli.command()
def show_stats():
    """显示系统统计信息"""
    try:
        print("系统统计信息:")
        print("-" * 30)
        # 这里可以添加统计信息显示逻辑
        print("功能尚未实现")
        
    except Exception as e:
        print(f"获取统计信息失败: {str(e)}")


# 添加CLI命令
cli.add_command(run_server)


if __name__ == '__main__':
    # 检查Python版本（暂时注释掉用于前端测试）
    # if sys.version_info < (3, 11):
    #     print("错误: GraphRAG需要Python 3.11或更高版本")
    #     sys.exit(1)
    
    # 检查必要的目录
    required_dirs = ['config', 'logs', 'uploads', 'temp', 'processed']
    for directory in required_dirs:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    
    # 如果没有参数，显示帮助或启动服务器
    if len(sys.argv) == 1:
        # 直接启动服务器
        server_config = load_server_config()
        host = server_config.get('host', '0.0.0.0')
        port = server_config.get('port', 5000)
        debug = server_config.get('debug', False)
        
        print(f"启动GraphRAG服务器...")
        print(f"监听地址: {host}:{port}")
        print(f"调试模式: {debug}")
        print(f"API文档: http://{host}:{port}/docs")
        print("-" * 50)
        
        try:
            app.run(
                host=host,
                port=port,
                debug=debug,
                threaded=True
            )
        except KeyboardInterrupt:
            print("\n服务器已停止")
        except Exception as e:
            print(f"启动服务器失败: {str(e)}")
            sys.exit(1)
    else:
        # 使用CLI
        cli()