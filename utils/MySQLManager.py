#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL数据库管理器
使用SQLAlchemy实现高性能连接
"""

import yaml
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
import os

logger = logging.getLogger(__name__)

class MySQLManager:
    """
    MySQL数据库管理器
    使用SQLAlchemy实现高性能连接池
    """
    
    def __init__(self, config_path: str = "config/db.yaml"):
        """
        初始化MySQL管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.engine = None
        self.session_factory = None
        self._load_config()
        self._init_engine()
    
    def _load_config(self):
        """
        加载数据库配置
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self.mysql_config = config.get('mysql', {})
            logger.info("MySQL配置加载成功")
            
        except Exception as e:
            logger.error(f"加载MySQL配置失败: {str(e)}")
            raise
    
    def _init_engine(self):
        """
        初始化数据库引擎
        """
        try:
            # 构建数据库URL
            host = self.mysql_config.get('host', 'localhost')
            port = self.mysql_config.get('port', 3306)
            username = self.mysql_config.get('username', 'root')
            password = self.mysql_config.get('password', '')
            database = self.mysql_config.get('database', 'graph_rag')
            charset = self.mysql_config.get('charset', 'utf8mb4')
            
            # 构建连接URL
            db_url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset={charset}"
            
            # 连接池配置
            pool_size = self.mysql_config.get('pool_size', 10)
            max_overflow = self.mysql_config.get('max_overflow', 20)
            pool_timeout = self.mysql_config.get('pool_timeout', 30)
            pool_recycle = self.mysql_config.get('pool_recycle', 3600)
            
            # 创建引擎
            self.engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
                echo=False,  # 设置为True可以看到SQL语句
                pool_pre_ping=True  # 连接前ping测试
            )
            
            # 创建会话工厂
            self.session_factory = sessionmaker(bind=self.engine)
            
            logger.info("MySQL引擎初始化成功")
            
        except Exception as e:
            logger.error(f"初始化MySQL引擎失败: {str(e)}")
            raise
    
    @contextmanager
    def get_session(self):
        """
        获取数据库会话的上下文管理器
        
        Yields:
            Session: 数据库会话对象
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {str(e)}")
            raise
        finally:
            session.close()
    
    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行查询语句
        
        Args:
            sql: SQL查询语句
            params: 查询参数
            
        Returns:
            List[Dict[str, Any]]: 查询结果
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(sql), params or {})
                return [dict(row._mapping) for row in result]
        except Exception as e:
            logger.error(f"执行查询失败: {str(e)}")
            raise
    
    def execute_update(self, sql: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        执行更新语句
        
        Args:
            sql: SQL更新语句
            params: 更新参数
            
        Returns:
            int: 影响的行数
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(sql), params or {})
                return result.rowcount
        except Exception as e:
            logger.error(f"执行更新失败: {str(e)}")
            raise
    
    def execute_insert(self, sql: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        执行插入语句
        
        Args:
            sql: SQL插入语句
            params: 插入参数
            
        Returns:
            int: 插入的ID
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(sql), params or {})
                session.commit()
                return result.lastrowid
        except Exception as e:
            logger.error(f"执行插入失败: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """
        测试数据库连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {str(e)}")
            return False
    
    def close(self):
        """
        关闭数据库连接
        """
        if self.engine:
            self.engine.dispose()
            logger.info("MySQL连接已关闭")

# 全局MySQL管理器实例
mysql_manager = None

def get_mysql_manager() -> MySQLManager:
    """
    获取MySQL管理器实例（单例模式）
    
    Returns:
        MySQLManager: MySQL管理器实例
    """
    global mysql_manager
    if mysql_manager is None:
        mysql_manager = MySQLManager()
    return mysql_manager 