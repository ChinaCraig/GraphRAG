#!/usr/bin/env python3
"""
GraphRAG快速启动脚本
提供简单的项目启动和管理功能
"""

import os
import sys
import subprocess
import yaml
import time
from pathlib import Path


def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 11):
        print("❌ 错误: GraphRAG需要Python 3.11或更高版本")
        print(f"当前版本: {sys.version}")
        sys.exit(1)
    print(f"✅ Python版本检查通过: {sys.version.split()[0]}")


def check_directories():
    """检查并创建必要的目录"""
    required_dirs = [
        'config', 'logs', 'uploads', 'temp', 'processed',
        'app', 'utils', 'install', 'templates/css', 
        'templates/js', 'templates/html'
    ]
    
    created_dirs = []
    for directory in required_dirs:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            created_dirs.append(directory)
    
    if created_dirs:
        print(f"✅ 创建目录: {', '.join(created_dirs)}")
    else:
        print("✅ 目录结构检查通过")


def check_config_files():
    """检查配置文件"""
    config_files = [
        'config/config.yaml',
        'config/db.yaml', 
        'config/model.yaml',
        'config/prompt.yaml'
    ]
    
    missing_files = []
    invalid_files = []
    
    for config_file in config_files:
        if not os.path.exists(config_file):
            missing_files.append(config_file)
        else:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
            except yaml.YAMLError:
                invalid_files.append(config_file)
    
    if missing_files:
        print(f"❌ 缺少配置文件: {', '.join(missing_files)}")
        return False
    
    if invalid_files:
        print(f"❌ 配置文件格式错误: {', '.join(invalid_files)}")
        return False
    
    print("✅ 配置文件检查通过")
    return True


def check_dependencies():
    """检查Python依赖"""
    if not os.path.exists('requirements.txt'):
        print("❌ 未找到requirements.txt文件")
        return False
    
    try:
        # 检查关键依赖
        import flask
        import sqlalchemy
        import pymysql
        import sentence_transformers
        print("✅ 核心依赖检查通过")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {str(e)}")
        print("请运行: pip install -r requirements.txt")
        return False


def install_dependencies():
    """安装Python依赖"""
    print("📦 安装Python依赖...")
    try:
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ], check=True)
        print("✅ 依赖安装完成")
        return True
    except subprocess.CalledProcessError:
        print("❌ 依赖安装失败")
        return False


def test_database_connections():
    """测试数据库连接"""
    print("🔍 测试数据库连接...")
    
    try:
        from utils.MySQLManager import MySQLManager
        mysql_manager = MySQLManager()
        mysql_manager._test_connection()
        print("✅ MySQL连接正常")
    except Exception as e:
        print(f"❌ MySQL连接失败: {str(e)}")
        return False
    
    try:
        from utils.MilvusManager import MilvusManager
        milvus_manager = MilvusManager()
        print("✅ Milvus连接正常")
    except Exception as e:
        print(f"❌ Milvus连接失败: {str(e)}")
        return False
    
    try:
        from utils.Neo4jManager import Neo4jManager
        neo4j_manager = Neo4jManager()
        neo4j_manager._test_connection()
        print("✅ Neo4j连接正常")
    except Exception as e:
        print(f"❌ Neo4j连接失败: {str(e)}")
        return False
    
    return True


def start_server():
    """启动GraphRAG服务器"""
    print("🚀 启动GraphRAG服务器...")
    
    try:
        # 加载配置
        with open('config/config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            app_config = config.get('app', {})
        
        host = app_config.get('host', '0.0.0.0')
        port = app_config.get('port', 5000)
        debug = app_config.get('debug', False)
        
        print(f"监听地址: http://{host}:{port}")
        print(f"调试模式: {debug}")
        print(f"API文档: http://{host}:{port}/docs")
        print("-" * 50)
        
        # 启动服务器
        subprocess.run([sys.executable, 'app.py'], check=True)
        
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
    except Exception as e:
        print(f"❌ 启动服务器失败: {str(e)}")
        sys.exit(1)


def main():
    """主函数"""
    print("=" * 60)
    print("🤖 GraphRAG 系统启动检查")
    print("=" * 60)
    
    # 1. 检查Python版本
    check_python_version()
    
    # 2. 检查目录结构
    check_directories()
    
    # 3. 检查配置文件
    if not check_config_files():
        print("\n请确保配置文件存在且格式正确")
        sys.exit(1)
    
    # 4. 检查依赖
    if not check_dependencies():
        choice = input("\n是否自动安装依赖? (y/N): ").lower()
        if choice == 'y':
            if not install_dependencies():
                sys.exit(1)
        else:
            print("请手动安装依赖: pip install -r requirements.txt")
            sys.exit(1)
    
    # 5. 测试数据库连接（可选）
    choice = input("\n是否测试数据库连接? (y/N): ").lower()
    if choice == 'y':
        if not test_database_connections():
            print("⚠️  数据库连接测试失败，但仍可启动服务器")
            choice = input("是否继续启动? (y/N): ").lower()
            if choice != 'y':
                sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ 所有检查完成，准备启动服务器...")
    print("=" * 60)
    
    time.sleep(2)
    
    # 6. 启动服务器
    start_server()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 用户取消操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 启动脚本异常: {str(e)}")
        sys.exit(1)