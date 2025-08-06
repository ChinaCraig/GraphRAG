"""
Neo4j图数据库管理器
负责图数据的存储、查询和管理
"""

import yaml
import logging
from typing import Optional, Dict, Any, List, Union
from neo4j import GraphDatabase, Driver, Session, Result
from neo4j.exceptions import Neo4jError
import json

class Neo4jManager:
    """Neo4j图数据库管理器"""
    
    def __init__(self, config_path: str = 'config/db.yaml'):
        """
        初始化Neo4j管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.driver = None
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_config()
        
        # 初始化连接
        self._init_connection()
    
    def _load_config(self) -> None:
        """加载Neo4j配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.neo4j_config = config['neo4j']
                self.logger.info("Neo4j配置加载成功")
        except Exception as e:
            self.logger.error(f"加载Neo4j配置失败: {str(e)}")
            raise
    
    def _init_connection(self) -> None:
        """初始化Neo4j连接"""
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_config['uri'],
                auth=(self.neo4j_config['username'], self.neo4j_config['password']),
                max_connection_lifetime=self.neo4j_config.get('max_connection_lifetime', 3600),
                max_connection_pool_size=self.neo4j_config.get('max_connection_pool_size', 50),
                connection_timeout=self.neo4j_config.get('connection_timeout', 30),
                trust=self.neo4j_config.get('trust', 'TRUST_ALL_CERTIFICATES')
            )
            
            # 测试连接
            self._test_connection()
            
            self.logger.info(f"Neo4j连接成功: {self.neo4j_config['uri']}")
            
        except Neo4jError as e:
            self.logger.error(f"Neo4j连接失败: {str(e)}")
            raise
    
    def _test_connection(self) -> None:
        """测试Neo4j连接"""
        try:
            with self.driver.session(database=self.neo4j_config.get('database', 'neo4j')) as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            self.logger.info("Neo4j连接测试成功")
        except Neo4jError as e:
            self.logger.error(f"Neo4j连接测试失败: {str(e)}")
            raise
    
    def get_session(self) -> Session:
        """
        获取Neo4j会话
        
        Returns:
            Session: Neo4j数据库会话
        """
        return self.driver.session(database=self.neo4j_config.get('database', 'neo4j'))
    
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """
        执行Cypher查询
        
        Args:
            query: Cypher查询语句
            parameters: 查询参数
            
        Returns:
            List[Dict]: 查询结果
        """
        try:
            with self.get_session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
                
        except Neo4jError as e:
            self.logger.error(f"执行Cypher查询失败: {str(e)}")
            raise
    
    def execute_transaction(self, queries: List[str], parameters_list: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        执行事务
        
        Args:
            queries: Cypher语句列表
            parameters_list: 参数列表
            
        Returns:
            bool: 执行成功返回True
        """
        def _run_transaction(tx):
            for i, query in enumerate(queries):
                params = parameters_list[i] if parameters_list and i < len(parameters_list) else {}
                tx.run(query, params)
        
        try:
            with self.get_session() as session:
                session.execute_write(_run_transaction)
                
            self.logger.info(f"事务执行成功，共执行{len(queries)}条Cypher语句")
            return True
            
        except Neo4jError as e:
            self.logger.error(f"事务执行失败: {str(e)}")
            return False
    
    def create_node(self, label: str, properties: Dict[str, Any]) -> Optional[str]:
        """
        创建节点
        
        Args:
            label: 节点标签
            properties: 节点属性
            
        Returns:
            Optional[str]: 节点ID，创建失败返回None
        """
        try:
            query = f"""
            CREATE (n:{label} $properties)
            RETURN elementId(n) AS node_id
            """
            
            result = self.execute_query(query, {"properties": properties})
            if result:
                node_id = result[0]['node_id']
                self.logger.info(f"节点创建成功，标签: {label}，ID: {node_id}")
                return node_id
            return None
            
        except Exception as e:
            self.logger.error(f"创建节点失败: {str(e)}")
            return None
    
    def create_relationship(self, start_node_id: str, end_node_id: str, 
                          relationship_type: str, properties: Optional[Dict[str, Any]] = None) -> bool:
        """
        创建关系
        
        Args:
            start_node_id: 起始节点ID
            end_node_id: 结束节点ID
            relationship_type: 关系类型
            properties: 关系属性
            
        Returns:
            bool: 创建成功返回True
        """
        try:
            query = f"""
            MATCH (a), (b)
            WHERE elementId(a) = $start_id AND elementId(b) = $end_id
            CREATE (a)-[r:{relationship_type} $properties]->(b)
            RETURN r
            """
            
            params = {
                "start_id": start_node_id,
                "end_id": end_node_id,
                "properties": properties or {}
            }
            
            result = self.execute_query(query, params)
            if result:
                self.logger.info(f"关系创建成功，类型: {relationship_type}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"创建关系失败: {str(e)}")
            return False
    
    def find_nodes(self, label: str, properties: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """
        查找节点
        
        Args:
            label: 节点标签
            properties: 匹配属性
            
        Returns:
            List[Dict]: 节点列表
        """
        try:
            if properties:
                where_clause = " AND ".join([f"n.{key} = ${key}" for key in properties.keys()])
                query = f"""
                MATCH (n:{label})
                WHERE {where_clause}
                RETURN elementId(n) AS node_id, labels(n) AS labels, properties(n) AS properties
                """
                result = self.execute_query(query, properties)
            else:
                query = f"""
                MATCH (n:{label})
                RETURN elementId(n) AS node_id, labels(n) AS labels, properties(n) AS properties
                """
                result = self.execute_query(query)
            
            self.logger.info(f"节点查找完成，标签: {label}，找到{len(result)}个节点")
            return result
            
        except Exception as e:
            self.logger.error(f"查找节点失败: {str(e)}")
            return []
    
    def find_relationships(self, relationship_type: str, start_label: Optional[str] = None, 
                         end_label: Optional[str] = None) -> List[Dict]:
        """
        查找关系
        
        Args:
            relationship_type: 关系类型
            start_label: 起始节点标签
            end_label: 结束节点标签
            
        Returns:
            List[Dict]: 关系列表
        """
        try:
            start_pattern = f"(a:{start_label})" if start_label else "(a)"
            end_pattern = f"(b:{end_label})" if end_label else "(b)"
            
            query = f"""
            MATCH {start_pattern}-[r:{relationship_type}]->{end_pattern}
            RETURN elementId(a) AS start_node_id, elementId(b) AS end_node_id, 
                   labels(a) AS start_labels, labels(b) AS end_labels,
                   properties(a) AS start_properties, properties(b) AS end_properties,
                   type(r) AS relationship_type, properties(r) AS relationship_properties
            """
            
            result = self.execute_query(query)
            self.logger.info(f"关系查找完成，类型: {relationship_type}，找到{len(result)}个关系")
            return result
            
        except Exception as e:
            self.logger.error(f"查找关系失败: {str(e)}")
            return []
    
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> bool:
        """
        更新节点属性
        
        Args:
            node_id: 节点ID
            properties: 新属性
            
        Returns:
            bool: 更新成功返回True
        """
        try:
            query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            SET n += $properties
            RETURN n
            """
            
            result = self.execute_query(query, {"node_id": node_id, "properties": properties})
            if result:
                self.logger.info(f"节点更新成功，ID: {node_id}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"更新节点失败: {str(e)}")
            return False
    
    def delete_node(self, node_id: str, delete_relationships: bool = True) -> bool:
        """
        删除节点
        
        Args:
            node_id: 节点ID
            delete_relationships: 是否同时删除相关关系
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            if delete_relationships:
                query = """
                MATCH (n)
                WHERE elementId(n) = $node_id
                DETACH DELETE n
                """
            else:
                query = """
                MATCH (n)
                WHERE elementId(n) = $node_id
                DELETE n
                """
            
            result = self.execute_query(query, {"node_id": node_id})
            self.logger.info(f"节点删除成功，ID: {node_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除节点失败: {str(e)}")
            return False
    
    def delete_relationship(self, start_node_id: str, end_node_id: str, relationship_type: str) -> bool:
        """
        删除关系
        
        Args:
            start_node_id: 起始节点ID
            end_node_id: 结束节点ID
            relationship_type: 关系类型
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            query = f"""
            MATCH (a)-[r:{relationship_type}]->(b)
            WHERE elementId(a) = $start_id AND elementId(b) = $end_id
            DELETE r
            """
            
            params = {
                "start_id": start_node_id,
                "end_id": end_node_id
            }
            
            result = self.execute_query(query, params)
            self.logger.info(f"关系删除成功，类型: {relationship_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除关系失败: {str(e)}")
            return False
    
    def get_node_neighbors(self, node_id: str, relationship_types: Optional[List[str]] = None) -> List[Dict]:
        """
        获取节点的邻居节点
        
        Args:
            node_id: 节点ID
            relationship_types: 关系类型列表，None表示所有类型
            
        Returns:
            List[Dict]: 邻居节点列表
        """
        try:
            if relationship_types:
                rel_pattern = "|".join(relationship_types)
                query = f"""
                MATCH (n)-[r:{rel_pattern}]-(neighbor)
                WHERE elementId(n) = $node_id
                RETURN elementId(neighbor) AS neighbor_id, labels(neighbor) AS labels, 
                       properties(neighbor) AS properties, type(r) AS relationship_type
                """
            else:
                query = """
                MATCH (n)-[r]-(neighbor)
                WHERE elementId(n) = $node_id
                RETURN elementId(neighbor) AS neighbor_id, labels(neighbor) AS labels, 
                       properties(neighbor) AS properties, type(r) AS relationship_type
                """
            
            result = self.execute_query(query, {"node_id": node_id})
            self.logger.info(f"邻居节点查找完成，节点ID: {node_id}，找到{len(result)}个邻居")
            return result
            
        except Exception as e:
            self.logger.error(f"获取邻居节点失败: {str(e)}")
            return []
    
    def get_shortest_path(self, start_node_id: str, end_node_id: str, max_depth: int = 5) -> List[Dict]:
        """
        获取两个节点之间的最短路径
        
        Args:
            start_node_id: 起始节点ID
            end_node_id: 结束节点ID
            max_depth: 最大深度
            
        Returns:
            List[Dict]: 最短路径信息
        """
        try:
            query = f"""
            MATCH path = shortestPath((start)-[*1..{max_depth}]-(end))
            WHERE elementId(start) = $start_id AND elementId(end) = $end_id
            RETURN path, length(path) AS path_length
            """
            
            params = {
                "start_id": start_node_id,
                "end_id": end_node_id
            }
            
            result = self.execute_query(query, params)
            self.logger.info(f"最短路径查找完成，找到{len(result)}条路径")
            return result
            
        except Exception as e:
            self.logger.error(f"获取最短路径失败: {str(e)}")
            return []
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """
        获取图数据库统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            queries = {
                "node_count": "MATCH (n) RETURN count(n) AS count",
                "relationship_count": "MATCH ()-[r]->() RETURN count(r) AS count",
                "labels": "CALL db.labels() YIELD label RETURN collect(label) AS labels",
                "relationship_types": "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS types"
            }
            
            stats = {}
            for key, query in queries.items():
                result = self.execute_query(query)
                if result:
                    if key in ["labels", "relationship_types"]:
                        stats[key] = result[0][list(result[0].keys())[0]]
                    else:
                        stats[key] = result[0]['count']
            
            self.logger.info("图数据库统计信息获取成功")
            return stats
            
        except Exception as e:
            self.logger.error(f"获取图数据库统计信息失败: {str(e)}")
            return {}
    
    def clear_database(self) -> bool:
        """
        清空数据库（慎用）
        
        Returns:
            bool: 清空成功返回True
        """
        try:
            query = "MATCH (n) DETACH DELETE n"
            self.execute_query(query)
            self.logger.warning("数据库已清空")
            return True
            
        except Exception as e:
            self.logger.error(f"清空数据库失败: {str(e)}")
            return False
    
    def close(self) -> None:
        """关闭连接"""
        try:
            if self.driver:
                self.driver.close()
                self.logger.info("Neo4j连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭Neo4j连接失败: {str(e)}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()