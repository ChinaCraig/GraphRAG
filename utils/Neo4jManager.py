#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neo4j数据库管理器
"""

import yaml
import logging
from neo4j import GraphDatabase
from typing import Optional, Dict, Any, List
import os

logger = logging.getLogger(__name__)

class Neo4jManager:
    """
    Neo4j数据库管理器
    """
    
    def __init__(self, config_path: str = "config/db.yaml"):
        """
        初始化Neo4j管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.driver = None
        self._load_config()
        self._init_driver()
    
    def _load_config(self):
        """
        加载Neo4j配置
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self.neo4j_config = config.get('neo4j', {})
            logger.info("Neo4j配置加载成功")
            
        except Exception as e:
            logger.error(f"加载Neo4j配置失败: {str(e)}")
            raise
    
    def _init_driver(self):
        """
        初始化Neo4j驱动
        """
        try:
            host = self.neo4j_config.get('host', 'localhost')
            port = self.neo4j_config.get('port', 7687)
            username = self.neo4j_config.get('username', 'neo4j')
            password = self.neo4j_config.get('password', '')
            database = self.neo4j_config.get('database', 'neo4j')
            
            # 构建连接URI
            uri = f"bolt://{host}:{port}"
            
            # 连接配置
            max_connection_lifetime = self.neo4j_config.get('max_connection_lifetime', 3600)
            max_connection_pool_size = self.neo4j_config.get('max_connection_pool_size', 50)
            connection_timeout = self.neo4j_config.get('connection_timeout', 30)
            
            # 创建驱动
            self.driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
                max_connection_lifetime=max_connection_lifetime,
                max_connection_pool_size=max_connection_pool_size,
                connection_timeout=connection_timeout
            )
            
            logger.info("Neo4j驱动初始化成功")
            
        except Exception as e:
            logger.error(f"初始化Neo4j驱动失败: {str(e)}")
            raise
    
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行Cypher查询
        
        Args:
            query: Cypher查询语句
            parameters: 查询参数
            
        Returns:
            List[Dict[str, Any]]: 查询结果
        """
        try:
            with self.driver.session(database=self.neo4j_config.get('database', 'neo4j')) as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"执行Neo4j查询失败: {str(e)}")
            raise
    
    def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建节点
        
        Args:
            label: 节点标签
            properties: 节点属性
            
        Returns:
            Dict[str, Any]: 创建的节点信息
        """
        try:
            query = f"CREATE (n:{label} $properties) RETURN n"
            result = self.execute_query(query, {"properties": properties})
            return result[0] if result else {}
        except Exception as e:
            logger.error(f"创建节点失败: {str(e)}")
            raise
    
    def create_relationship(self, from_node_id: int, to_node_id: int, 
                          relationship_type: str, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        创建关系
        
        Args:
            from_node_id: 起始节点ID
            to_node_id: 目标节点ID
            relationship_type: 关系类型
            properties: 关系属性
            
        Returns:
            Dict[str, Any]: 创建的关系信息
        """
        try:
            query = """
            MATCH (a), (b)
            WHERE id(a) = $from_id AND id(b) = $to_id
            CREATE (a)-[r:$relationship_type $properties]->(b)
            RETURN r
            """
            result = self.execute_query(query, {
                "from_id": from_node_id,
                "to_id": to_node_id,
                "relationship_type": relationship_type,
                "properties": properties or {}
            })
            return result[0] if result else {}
        except Exception as e:
            logger.error(f"创建关系失败: {str(e)}")
            raise
    
    def find_nodes(self, label: str, properties: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        查找节点
        
        Args:
            label: 节点标签
            properties: 查找条件
            
        Returns:
            List[Dict[str, Any]]: 节点列表
        """
        try:
            if properties:
                where_clause = " AND ".join([f"n.{k} = ${k}" for k in properties.keys()])
                query = f"MATCH (n:{label}) WHERE {where_clause} RETURN n"
                result = self.execute_query(query, properties)
            else:
                query = f"MATCH (n:{label}) RETURN n"
                result = self.execute_query(query)
            
            return result
        except Exception as e:
            logger.error(f"查找节点失败: {str(e)}")
            raise
    
    def find_relationships(self, from_label: str = None, to_label: str = None, 
                         relationship_type: str = None) -> List[Dict[str, Any]]:
        """
        查找关系
        
        Args:
            from_label: 起始节点标签
            to_label: 目标节点标签
            relationship_type: 关系类型
            
        Returns:
            List[Dict[str, Any]]: 关系列表
        """
        try:
            match_clause = "MATCH (a)"
            if from_label:
                match_clause += f":{from_label}"
            
            match_clause += "-[r"
            if relationship_type:
                match_clause += f":{relationship_type}"
            match_clause += "]->(b)"
            
            if to_label:
                match_clause += f":{to_label}"
            
            query = f"{match_clause} RETURN a, r, b"
            return self.execute_query(query)
        except Exception as e:
            logger.error(f"查找关系失败: {str(e)}")
            raise
    
    def delete_node(self, node_id: int) -> bool:
        """
        删除节点
        
        Args:
            node_id: 节点ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            query = "MATCH (n) WHERE id(n) = $node_id DETACH DELETE n"
            self.execute_query(query, {"node_id": node_id})
            return True
        except Exception as e:
            logger.error(f"删除节点失败: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """
        测试数据库连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            query = "RETURN 1 as test"
            result = self.execute_query(query)
            return len(result) > 0
        except Exception as e:
            logger.error(f"Neo4j连接测试失败: {str(e)}")
            return False
    
    def close(self):
        """
        关闭数据库连接
        """
        if self.driver:
            self.driver.close()
            logger.info("Neo4j连接已关闭")

# 全局Neo4j管理器实例
neo4j_manager = None

def get_neo4j_manager() -> Neo4jManager:
    """
    获取Neo4j管理器实例（单例模式）
    
    Returns:
        Neo4jManager: Neo4j管理器实例
    """
    global neo4j_manager
    if neo4j_manager is None:
        neo4j_manager = Neo4jManager()
    return neo4j_manager 