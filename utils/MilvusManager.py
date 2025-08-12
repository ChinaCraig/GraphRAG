"""
Milvus向量数据库管理器
负责向量数据的存储、检索和管理
"""

import yaml
import logging
import numpy as np
from typing import Optional, Dict, Any, List, Union
from pymilvus import (
    connections, Collection, DataType, FieldSchema, CollectionSchema,
    utility, Index, db
)
from pymilvus.exceptions import MilvusException
import json

class MilvusManager:
    """Milvus向量数据库管理器"""
    
    def __init__(self, config_path: str = 'config/db.yaml'):
        """
        初始化Milvus管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.collection = None
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_config()
        
        # 初始化连接
        self._init_connection()
        
        # 初始化集合
        self._init_collection()
    
    def _load_config(self) -> None:
        """加载Milvus配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.milvus_config = config['milvus']
                self.logger.info("Milvus配置加载成功")
        except Exception as e:
            self.logger.error(f"加载Milvus配置失败: {str(e)}")
            raise
    
    def _init_connection(self) -> None:
        """初始化Milvus连接"""
        try:
            # 连接到Milvus服务器（不指定数据库，先连接后检查数据库）
            connections.connect(
                alias="default",
                host=self.milvus_config['host'],
                port=str(self.milvus_config['port']),
                timeout=self.milvus_config.get('timeout', 30)
            )
            
            self.logger.info(f"Milvus连接成功: {self.milvus_config['host']}:{self.milvus_config['port']}")
            
            # 检查并创建数据库
            self._check_and_create_database()
            
        except MilvusException as e:
            self.logger.error(f"Milvus连接失败: {str(e)}")
            raise
    
    def _check_and_create_database(self) -> None:
        """检查并创建数据库"""
        try:
            database_name = self.milvus_config.get('database', 'default')
            
            # 获取所有数据库列表
            databases = db.list_database()
            self.logger.info(f"现有数据库列表: {databases}")
            
            # 检查目标数据库是否存在
            if database_name not in databases:
                self.logger.info(f"数据库 '{database_name}' 不存在，正在创建...")
                db.create_database(database_name)
                self.logger.info(f"数据库 '{database_name}' 创建成功")
            else:
                self.logger.info(f"数据库 '{database_name}' 已存在")
            
            # 重新连接到指定数据库
            connections.disconnect(alias="default")
            connections.connect(
                alias="default",
                host=self.milvus_config['host'],
                port=str(self.milvus_config['port']),
                db_name=database_name,
                timeout=self.milvus_config.get('timeout', 30)
            )
            
            self.logger.info(f"已连接到数据库: {database_name}")
            
        except MilvusException as e:
            self.logger.error(f"数据库检查和创建失败: {str(e)}")
            raise
    
    def _init_collection(self) -> None:
        """初始化集合"""
        try:
            collection_name = self.milvus_config['collection']
            
            # 检查集合是否存在
            if utility.has_collection(collection_name):
                self.collection = Collection(collection_name)
                self.logger.info(f"找到已存在的集合: {collection_name}")
                
                # 检查集合schema是否匹配当前要求
                if self._check_collection_schema():
                    self.logger.info("集合schema匹配，直接使用")
                    # 加载集合到内存
                    self.collection.load()
                    self.logger.info("集合已加载到内存")
                else:
                    self.logger.warning("集合schema不匹配，需要重新创建集合")
                    # 删除旧集合并创建新集合
                    self._recreate_collection()
            else:
                self.logger.info(f"集合 '{collection_name}' 不存在，正在创建...")
                # 创建集合
                self._create_collection()
                
        except MilvusException as e:
            self.logger.error(f"初始化集合失败: {str(e)}")
            raise
    
    def _create_collection(self) -> None:
        """创建集合"""
        try:
            collection_name = self.milvus_config['collection']
            dimension = self.milvus_config['dimension']
            
            # 定义字段模式
            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.VARCHAR,
                    max_length=100,
                    is_primary=True,
                    description="唯一标识符"
                ),
                FieldSchema(
                    name="vector",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=dimension,
                    description="向量数据"
                ),
                FieldSchema(
                    name="document_id",
                    dtype=DataType.INT64,
                    description="文档ID"
                ),
                FieldSchema(
                    name="element_id",
                    dtype=DataType.VARCHAR,
                    max_length=50,
                    description="一家子的唯一标识符（标题ID）"
                ),
                FieldSchema(
                    name="chunk_index",
                    dtype=DataType.INT64,
                    description="分块索引"
                ),
                FieldSchema(
                    name="content",
                    dtype=DataType.VARCHAR,
                    max_length=65535,
                    description="文本内容"
                ),
                FieldSchema(
                    name="metadata",
                    dtype=DataType.VARCHAR,
                    max_length=65535,
                    description="元数据"
                )
            ]
            
            # 创建集合模式
            schema = CollectionSchema(
                fields=fields,
                description="GraphRAG向量集合"
            )
            
            # 创建集合
            self.collection = Collection(
                name=collection_name,
                schema=schema
            )
            
            # 创建索引
            self._create_index()
            
            # 加载集合到内存
            self.collection.load()
            
            self.logger.info(f"集合创建并加载成功: {collection_name}")
            
        except MilvusException as e:
            self.logger.error(f"创建集合失败: {str(e)}")
            raise
    
    def _create_index(self) -> None:
        """创建向量索引"""
        try:
            index_params = {
                "index_type": self.milvus_config.get('index_type', 'IVF_FLAT'),
                "metric_type": self.milvus_config.get('metric_type', 'COSINE'),
                "params": {
                    "nlist": self.milvus_config.get('nlist', 1024)
                }
            }
            
            self.collection.create_index(
                field_name="vector",
                index_params=index_params
            )
            
            self.logger.info("向量索引创建成功")
            
        except MilvusException as e:
            self.logger.error(f"创建向量索引失败: {str(e)}")
            raise
    
    def _check_collection_schema(self) -> bool:
        """
        检查集合schema是否匹配当前要求
        主要检查字段是否完整，特别是新添加的element_id字段
        
        Returns:
            bool: True表示schema匹配，False表示不匹配
        """
        try:
            if not self.collection:
                return False
            
            # 获取当前集合的schema
            current_schema = self.collection.schema
            current_fields = {field.name: field for field in current_schema.fields}
            
            # 定义期望的字段列表
            expected_fields = [
                "id", "vector", "document_id", "element_id", 
                "chunk_index", "content", "metadata"
            ]
            
            # 检查是否包含所有期望的字段
            missing_fields = []
            for field_name in expected_fields:
                if field_name not in current_fields:
                    missing_fields.append(field_name)
            
            if missing_fields:
                self.logger.warning(f"集合缺少字段: {missing_fields}")
                return False
            
            # 特别检查element_id字段（新添加的字段）
            if "element_id" in current_fields:
                element_id_field = current_fields["element_id"]
                if (element_id_field.dtype != DataType.VARCHAR or 
                    element_id_field.params.get("max_length", 0) != 50):
                    self.logger.warning("element_id字段类型或长度不匹配")
                    return False
            
            self.logger.info("集合schema检查通过")
            return True
            
        except Exception as e:
            self.logger.error(f"检查集合schema失败: {str(e)}")
            return False
    
    def _recreate_collection(self) -> None:
        """重新创建集合（删除旧集合后创建新集合）"""
        try:
            collection_name = self.milvus_config['collection']
            
            self.logger.info(f"开始重新创建集合: {collection_name}")
            
            # 释放并删除旧集合
            if self.collection:
                self.collection.release()
                utility.drop_collection(collection_name)
                self.logger.info("旧集合已删除")
            
            # 创建新集合
            self._create_collection()
            self.logger.info("集合重新创建完成")
            
        except MilvusException as e:
            self.logger.error(f"重新创建集合失败: {str(e)}")
            raise
    
    def insert_vectors(self, data: List[Dict[str, Any]]) -> bool:
        """
        插入向量数据
        
        Args:
            data: 向量数据列表，每个元素包含id, vector, document_id, element_id, chunk_index, content, metadata
            
        Returns:
            bool: 插入成功返回True
        """
        try:
            if not data:
                self.logger.warning("没有数据需要插入")
                return True
            
            # 准备插入数据
            ids = []
            vectors = []
            document_ids = []
            element_ids = []
            chunk_indices = []
            contents = []
            metadatas = []
            
            for i, item in enumerate(data):
                # 调试：检查每个字段的类型
                item_id = item["id"]
                if not isinstance(item_id, str):
                    self.logger.error(f"数据项 {i}: id 不是字符串类型: {type(item_id)}, 值: {item_id}")
                    raise ValueError(f"id字段必须是字符串，但收到: {type(item_id)}")
                
                ids.append(item_id)
                vectors.append(item["vector"])
                document_ids.append(item["document_id"])
                element_ids.append(item["element_id"])
                chunk_indices.append(item["chunk_index"])
                contents.append(item["content"])
                metadatas.append(json.dumps(item.get("metadata", {}), ensure_ascii=False))
            
            # 使用实体列表方式插入（兼容性更好）
            entities = [
                ids,           # id字段
                vectors,       # vector字段
                document_ids,  # document_id字段
                element_ids,   # element_id字段
                chunk_indices, # chunk_index字段
                contents,      # content字段
                metadatas      # metadata字段
            ]
            
            # 调试：验证entities结构
            self.logger.debug(f"entities长度: {len(entities)}")
            self.logger.debug(f"id列表长度: {len(entities[0])}")
            self.logger.debug(f"前3个id: {entities[0][:3]}")
            
            # 插入数据
            self.collection.insert(entities)
            
            # 刷新数据，确保数据被持久化
            self.collection.flush()
            
            self.logger.info(f"向量数据插入成功，共插入{len(data)}条记录")
            return True
            
        except MilvusException as e:
            self.logger.error(f"插入向量数据失败: {str(e)}")
            return False
    
    def search_vectors(self, query_vectors: List[List[float]], top_k: int = 10, 
                      search_params: Optional[Dict] = None, 
                      expr: Optional[str] = None) -> List[Dict]:
        """
        向量相似性搜索
        
        Args:
            query_vectors: 查询向量列表
            top_k: 返回的相似向量数量
            search_params: 搜索参数
            expr: 过滤表达式
            
        Returns:
            List[Dict]: 搜索结果
        """
        try:
            # 加载集合到内存
            self.collection.load()
            
            # 默认搜索参数
            if search_params is None:
                search_params = {
                    "metric_type": self.milvus_config.get('metric_type', 'COSINE'),
                    "params": {"nprobe": 16}
                }
            
            # 执行搜索
            results = self.collection.search(
                data=query_vectors,
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["id", "document_id", "element_id", "chunk_index", "content", "metadata"]
            )
            
            # 处理搜索结果
            search_results = []
            for hits in results:
                for hit in hits:
                    result = {
                        "id": hit.entity.get("id"),
                        "score": hit.score,
                        "document_id": hit.entity.get("document_id"),
                        "element_id": hit.entity.get("element_id"),
                        "chunk_index": hit.entity.get("chunk_index"),
                        "content": hit.entity.get("content"),
                        "metadata": json.loads(hit.entity.get("metadata", "{}"))
                    }
                    search_results.append(result)
            
            self.logger.info(f"向量搜索完成，返回{len(search_results)}条结果")
            return search_results
            
        except MilvusException as e:
            self.logger.error(f"向量搜索失败: {str(e)}")
            return []
    
    def delete_vectors(self, expr: str) -> bool:
        """
        删除向量数据
        
        Args:
            expr: 删除条件表达式
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            self.collection.delete(expr)
            self.collection.flush()
            
            self.logger.info(f"向量数据删除成功，条件: {expr}")
            return True
            
        except MilvusException as e:
            self.logger.error(f"删除向量数据失败: {str(e)}")
            return False
    
    def delete_by_document_id(self, document_id: int) -> bool:
        """
        按文档ID删除所有相关向量数据
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            # 先查询有多少条记录
            count_expr = f"document_id == {document_id}"
            
            # 执行删除
            self.collection.delete(count_expr)
            self.collection.flush()
            
            self.logger.info(f"文档ID {document_id} 的所有向量数据删除成功")
            return True
            
        except MilvusException as e:
            self.logger.error(f"删除文档ID {document_id} 的向量数据失败: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"删除文档向量数据时发生未知错误: {str(e)}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            Dict[str, Any]: 集合统计信息
        """
        try:
            stats = self.collection.num_entities
            return {
                "collection_name": self.collection.name,
                "total_entities": stats,
                "schema": self.collection.schema
            }
            
        except MilvusException as e:
            self.logger.error(f"获取集合统计信息失败: {str(e)}")
            return {}
    
    def create_partition(self, partition_name: str) -> bool:
        """
        创建分区
        
        Args:
            partition_name: 分区名称
            
        Returns:
            bool: 创建成功返回True
        """
        try:
            if self.collection.has_partition(partition_name):
                self.logger.info(f"分区已存在: {partition_name}")
                return True
            
            self.collection.create_partition(partition_name)
            self.logger.info(f"分区创建成功: {partition_name}")
            return True
            
        except MilvusException as e:
            self.logger.error(f"创建分区失败: {str(e)}")
            return False
    
    def query_by_id(self, ids: List[str]) -> List[Dict]:
        """
        根据ID查询向量数据
        
        Args:
            ids: ID列表
            
        Returns:
            List[Dict]: 查询结果
        """
        try:
            self.collection.load()
            
            expr = f"id in {ids}"
            results = self.collection.query(
                expr=expr,
                output_fields=["id", "document_id", "element_id", "chunk_index", "content", "metadata"]
            )
            
            query_results = []
            for result in results:
                query_result = {
                    "id": result.get("id"),
                    "document_id": result.get("document_id"),
                    "element_id": result.get("element_id"),
                    "chunk_index": result.get("chunk_index"),
                    "content": result.get("content"),
                    "metadata": json.loads(result.get("metadata", "{}"))
                }
                query_results.append(query_result)
            
            self.logger.info(f"ID查询完成，返回{len(query_results)}条结果")
            return query_results
            
        except MilvusException as e:
            self.logger.error(f"ID查询失败: {str(e)}")
            return []
    
    def update_vector(self, vector_id: str, new_data: Dict[str, Any]) -> bool:
        """
        更新向量数据（通过删除后重新插入实现）
        
        Args:
            vector_id: 向量ID
            new_data: 新数据
            
        Returns:
            bool: 更新成功返回True
        """
        try:
            # 删除旧数据
            self.delete_vectors(f"id == '{vector_id}'")
            
            # 插入新数据
            self.insert_vectors([new_data])
            
            self.logger.info(f"向量数据更新成功，ID: {vector_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新向量数据失败: {str(e)}")
            return False
    
    def close(self) -> None:
        """关闭连接"""
        try:
            if self.collection:
                self.collection.release()
            connections.disconnect(alias="default")
            self.logger.info("Milvus连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭Milvus连接失败: {str(e)}")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()