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
    utility, Index
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
            # 连接到Milvus服务器
            connections.connect(
                alias="default",
                host=self.milvus_config['host'],
                port=str(self.milvus_config['port']),
                timeout=self.milvus_config.get('timeout', 30)
            )
            
            self.logger.info(f"Milvus连接成功: {self.milvus_config['host']}:{self.milvus_config['port']}")
            
        except MilvusException as e:
            self.logger.error(f"Milvus连接失败: {str(e)}")
            raise
    
    def _init_collection(self) -> None:
        """初始化集合"""
        try:
            collection_name = self.milvus_config['collection']
            
            # 检查集合是否存在
            if utility.has_collection(collection_name):
                self.collection = Collection(collection_name)
                self.logger.info(f"使用已存在的集合: {collection_name}")
            else:
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
            
            self.logger.info(f"集合创建成功: {collection_name}")
            
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
    
    def insert_vectors(self, data: List[Dict[str, Any]]) -> bool:
        """
        插入向量数据
        
        Args:
            data: 向量数据列表，每个元素包含id, vector, document_id, chunk_index, content, metadata
            
        Returns:
            bool: 插入成功返回True
        """
        try:
            if not data:
                self.logger.warning("没有数据需要插入")
                return True
            
            # 准备插入数据
            insert_data = {
                "id": [item["id"] for item in data],
                "vector": [item["vector"] for item in data],
                "document_id": [item["document_id"] for item in data],
                "chunk_index": [item["chunk_index"] for item in data],
                "content": [item["content"] for item in data],
                "metadata": [json.dumps(item.get("metadata", {}), ensure_ascii=False) for item in data]
            }
            
            # 插入数据
            self.collection.insert(insert_data)
            
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
                output_fields=["id", "document_id", "chunk_index", "content", "metadata"]
            )
            
            # 处理搜索结果
            search_results = []
            for hits in results:
                for hit in hits:
                    result = {
                        "id": hit.entity.get("id"),
                        "score": hit.score,
                        "document_id": hit.entity.get("document_id"),
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
                output_fields=["id", "document_id", "chunk_index", "content", "metadata"]
            )
            
            query_results = []
            for result in results:
                query_result = {
                    "id": result.get("id"),
                    "document_id": result.get("document_id"),
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