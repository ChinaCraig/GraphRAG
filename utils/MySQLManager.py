"""
MySQL数据库管理器 - SQLAlchemy高性能实现
负责MySQL数据库的连接、操作和管理
"""

import yaml
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Text, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import os

# 创建基础模型类
Base = declarative_base()

class MySQLManager:
    """MySQL数据库管理器"""
    
    def __init__(self, config_path: str = 'config/db.yaml'):
        """
        初始化MySQL管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.engine = None
        self.SessionLocal = None
        self.metadata = MetaData()
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_config()
        
        # 初始化数据库连接
        self._init_database()
    
    def _load_config(self) -> None:
        """加载数据库配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.db_config = config['mysql']
                self.logger.info("MySQL配置加载成功")
        except Exception as e:
            self.logger.error(f"加载MySQL配置失败: {str(e)}")
            raise
    
    def _init_database(self) -> None:
        """初始化数据库连接"""
        try:
            # 构建数据库连接URL
            db_url = (
                f"mysql+pymysql://{self.db_config['username']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}"
                f"/{self.db_config['database']}?charset={self.db_config['charset']}"
            )
            
            # 创建数据库引擎
            self.engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=self.db_config.get('pool_size', 10),
                max_overflow=self.db_config.get('max_overflow', 20),
                pool_timeout=self.db_config.get('pool_timeout', 30),
                pool_recycle=self.db_config.get('pool_recycle', 3600),
                echo=self.db_config.get('echo', False),
                future=True
            )
            
            # 创建会话工厂
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # 测试连接
            self._test_connection()
            
            self.logger.info("MySQL数据库连接初始化成功")
            
        except Exception as e:
            self.logger.error(f"MySQL数据库连接初始化失败: {str(e)}")
            raise
    
    def _test_connection(self) -> None:
        """测试数据库连接"""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                result.fetchone()
            self.logger.info("MySQL数据库连接测试成功")
        except Exception as e:
            self.logger.error(f"MySQL数据库连接测试失败: {str(e)}")
            raise
    
    def get_session(self) -> Session:
        """
        获取数据库会话
        
        Returns:
            Session: SQLAlchemy数据库会话
        """
        return self.SessionLocal()
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """
        执行查询语句
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            List[Dict]: 查询结果
        """
        try:
            with self.get_session() as session:
                result = session.execute(text(query), params or {})
                
                # 如果是SELECT查询，返回结果
                if query.strip().upper().startswith('SELECT'):
                    columns = result.keys()
                    rows = result.fetchall()
                    return [dict(zip(columns, row)) for row in rows]
                else:
                    # 对于非SELECT查询，提交事务
                    session.commit()
                    return []
                    
        except SQLAlchemyError as e:
            self.logger.error(f"执行SQL查询失败: {str(e)}")
            raise
    
    def execute_transaction(self, queries: List[str], params_list: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        执行事务
        
        Args:
            queries: SQL语句列表
            params_list: 参数列表
            
        Returns:
            bool: 执行成功返回True
        """
        try:
            with self.get_session() as session:
                for i, query in enumerate(queries):
                    params = params_list[i] if params_list and i < len(params_list) else {}
                    session.execute(text(query), params)
                session.commit()
                self.logger.info(f"事务执行成功，共执行{len(queries)}条SQL语句")
                return True
                
        except SQLAlchemyError as e:
            self.logger.error(f"事务执行失败: {str(e)}")
            return False
    
    def insert_data(self, table_name: str, data: Dict[str, Any]) -> bool:
        """
        插入数据
        
        Args:
            table_name: 表名
            data: 要插入的数据
            
        Returns:
            bool: 插入成功返回True
        """
        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join([f':{key}' for key in data.keys()])
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            
            with self.get_session() as session:
                session.execute(text(query), data)
                session.commit()
                
            self.logger.info(f"数据插入成功，表: {table_name}")
            return True
            
        except SQLAlchemyError as e:
            self.logger.error(f"数据插入失败: {str(e)}")
            return False
    
    def update_data(self, table_name: str, data: Dict[str, Any], where_clause: str, where_params: Dict[str, Any]) -> bool:
        """
        更新数据
        
        Args:
            table_name: 表名
            data: 要更新的数据
            where_clause: WHERE条件子句
            where_params: WHERE条件参数
            
        Returns:
            bool: 更新成功返回True
        """
        try:
            set_clause = ', '.join([f"{key} = :{key}" for key in data.keys()])
            query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
            
            # 合并参数
            all_params = {**data, **where_params}
            
            with self.get_session() as session:
                result = session.execute(text(query), all_params)
                session.commit()
                
            self.logger.info(f"数据更新成功，表: {table_name}，影响行数: {result.rowcount}")
            return True
            
        except SQLAlchemyError as e:
            self.logger.error(f"数据更新失败: {str(e)}")
            return False
    
    def delete_data(self, table_name: str, where_clause: str, where_params: Dict[str, Any]) -> bool:
        """
        删除数据
        
        Args:
            table_name: 表名
            where_clause: WHERE条件子句
            where_params: WHERE条件参数
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            query = f"DELETE FROM {table_name} WHERE {where_clause}"
            
            with self.get_session() as session:
                result = session.execute(text(query), where_params)
                session.commit()
                
            self.logger.info(f"数据删除成功，表: {table_name}，影响行数: {result.rowcount}")
            return True
            
        except SQLAlchemyError as e:
            self.logger.error(f"数据删除失败: {str(e)}")
            return False
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        获取表信息
        
        Args:
            table_name: 表名
            
        Returns:
            Dict[str, Any]: 表信息
        """
        try:
            query = f"DESCRIBE {table_name}"
            result = self.execute_query(query)
            return {
                'table_name': table_name,
                'columns': result
            }
        except Exception as e:
            self.logger.error(f"获取表信息失败: {str(e)}")
            return {}
    
    def check_table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            bool: 表存在返回True
        """
        try:
            query = """
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = :database_name AND table_name = :table_name
            """
            result = self.execute_query(query, {
                'database_name': self.db_config['database'],
                'table_name': table_name
            })
            return result[0]['count'] > 0
            
        except Exception as e:
            self.logger.error(f"检查表是否存在失败: {str(e)}")
            return False
    
    def close(self) -> None:
        """关闭数据库连接"""
        try:
            if self.engine:
                self.engine.dispose()
                self.logger.info("MySQL数据库连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭MySQL数据库连接失败: {str(e)}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 数据模型定义
class Document(Base):
    """文档表模型"""
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False, comment='文件名')
    file_path = Column(String(500), nullable=False, comment='文件路径')
    file_type = Column(String(50), nullable=False, comment='文件类型')
    file_size = Column(Integer, nullable=False, comment='文件大小(字节)')
    upload_time = Column(DateTime, default=datetime.utcnow, comment='上传时间')
    process_status = Column(String(50), default='pending', comment='处理状态')
    process_time = Column(DateTime, comment='处理时间')
    content_hash = Column(String(64), comment='内容哈希')
    doc_metadata = Column(Text, comment='元数据(JSON格式)')  # 避免与SQLAlchemy的metadata冲突

class DocumentChunk(Base):
    """文档分块表模型"""
    __tablename__ = 'document_chunks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, comment='文档ID')
    chunk_index = Column(Integer, nullable=False, comment='分块索引')
    content = Column(Text, nullable=False, comment='分块内容')
    content_hash = Column(String(64), comment='内容哈希')
    vector_id = Column(String(100), comment='向量ID')
    create_time = Column(DateTime, default=datetime.utcnow, comment='创建时间')

class Entity(Base):
    """实体表模型"""
    __tablename__ = 'entities'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment='实体名称')
    entity_type = Column(String(100), nullable=False, comment='实体类型')
    description = Column(Text, comment='实体描述')
    properties = Column(Text, comment='实体属性(JSON格式)')
    create_time = Column(DateTime, default=datetime.utcnow, comment='创建时间')

class Relation(Base):
    """关系表模型"""
    __tablename__ = 'relations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    head_entity_id = Column(Integer, nullable=False, comment='头实体ID')
    tail_entity_id = Column(Integer, nullable=False, comment='尾实体ID')
    relation_type = Column(String(100), nullable=False, comment='关系类型')
    confidence = Column(Float, comment='置信度')
    source_document_id = Column(Integer, comment='来源文档ID')
    create_time = Column(DateTime, default=datetime.utcnow, comment='创建时间')