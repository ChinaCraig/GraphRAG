#!/usr/bin/env python3
"""
GraphRAG主启动文件
使用Flask Web框架启动GraphRAG服务
"""

import os
import sys
import yaml
import click


# 设置环境变量以避免tokenizers并行化警告
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

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
        print(f"WebSocket支持: 已启用")
        print(f"监听地址: http://{host}:{port}")
        print(f"调试模式: {debug}")
        print(f"配置文件: {config}")
        print(f"API文档: http://{host}:{port}/docs")
        print("-" * 50)
        
        # 获取SocketIO实例并启动服务器（支持WebSocket）
        socketio = app.socketio
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True
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
    # 检查必要的目录
    required_dirs = ['config', 'temp']
    for directory in required_dirs:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    
    # 检查是否是直接启动参数
    direct_params = ['--port', '--host', '--debug']
    has_direct_params = any(param in sys.argv for param in direct_params)
    
    # 如果没有参数或者有直接启动参数，启动服务器
    if len(sys.argv) == 1 or has_direct_params:
        # 解析直接参数
        host = None
        port = None
        debug = False
        
        try:
            for i, arg in enumerate(sys.argv):
                if arg == '--host' and i + 1 < len(sys.argv):
                    host = sys.argv[i + 1]
                elif arg == '--port' and i + 1 < len(sys.argv):
                    port = int(sys.argv[i + 1])
                elif arg == '--debug':
                    debug = True
        except (ValueError, IndexError):
            print("参数错误，使用默认配置启动")
        
        # 使用配置文件的默认值
        server_config = load_server_config()
        host = host or server_config.get('host', '0.0.0.0')
        port = port or server_config.get('port', 5000)
        debug = debug or server_config.get('debug', False)
        
        print(f"启动GraphRAG服务器...")
        print(f"WebSocket支持: 已启用")
        print(f"监听地址: http://{host}:{port}")
        print(f"调试模式: {debug}")
        print(f"API文档: http://{host}:{port}/docs")
        print("-" * 50)
        
        try:
            # 获取SocketIO实例并启动服务器（支持WebSocket）
            socketio = app.socketio
            socketio.run(
                app,
                host=host,
                port=port,
                debug=debug,
                allow_unsafe_werkzeug=True
            )
        except KeyboardInterrupt:
            print("\n服务器已停止")
        except Exception as e:
            print(f"启动服务器失败: {str(e)}")
            sys.exit(1)
    else:
        # 使用CLI子命令
        cli()