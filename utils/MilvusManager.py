#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milvus数据库管理器
"""

import yaml
import logging
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import os

logger = logging.getLogger(__name__)

class MilvusManager:
    """
    Milvus数据库管理器
    """
    
    def __init__(self, config_path: str = "config/db.yaml"):
        """
        初始化Milvus管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.connection = None
        self.collection = None
        self._load_config()
        self._init_connection()
    
    def _load_config(self):
        """
        加载Milvus配置
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self.milvus_config = config.get('milvus', {})
            logger.info("Milvus配置加载成功")
            
        except Exception as e:
            logger.error(f"加载Milvus配置失败: {str(e)}")
            raise
    
    def _init_connection(self):
        """
        初始化Milvus连接
        """
        try:
            host = self.milvus_config.get('host', 'localhost')
            port = self.milvus_config.get('port', 19530)
            database = self.milvus_config.get('database', 'graph_rag')
            collection = self.milvus_config.get('collection', 'graph_rag')
            
            # 连接Milvus
            self.connection = connections.connect(
                alias="default",
                host=host,
                port=port
            )
            
            # 设置数据库
            if database != "default":
                connections.set_database(database)
            
            self.collection_name = collection
            logger.info("Milvus连接初始化成功")
            
        except Exception as e:
            logger.error(f"初始化Milvus连接失败: {str(e)}")
            raise
    
    def create_collection(self, dimension: int = 768) -> bool:
        """
        创建集合
        
        Args:
            dimension: 向量维度
            
        Returns:
            bool: 创建是否成功
        """
        try:
            # 检查集合是否已存在
            if utility.has_collection(self.collection_name):
                logger.info(f"集合 {self.collection_name} 已存在")
                return True
            
            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="file_id", dtype=DataType.INT64, description="文件ID"),
                FieldSchema(name="content_type", dtype=DataType.VARCHAR, max_length=50, description="内容类型"),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535, description="原始内容"),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension, description="向量"),
                FieldSchema(name="embedding_model", dtype=DataType.VARCHAR, max_length=100, description="嵌入模型"),
                FieldSchema(name="position_info", dtype=DataType.JSON, description="位置信息")
            ]
            
            # 创建集合模式
            schema = CollectionSchema(fields, description="GraphRAG向量集合")
            
            # 创建集合
            self.collection = Collection(self.collection_name, schema)
            
            # 创建索引
            index_params = {
                "metric_type": "COSINE",
                "index_type": self.milvus_config.get('index_type', 'IVFFLAT'),
                "params": {"nlist": self.milvus_config.get('nlist', 1024)}
            }
            
            self.collection.create_index("embedding", index_params)
            logger.info(f"集合 {self.collection_name} 创建成功")
            
            return True
            
        except Exception as e:
            logger.error(f"创建集合失败: {str(e)}")
            return False
    
    def insert_vectors(self, data: List[Dict[str, Any]]) -> bool:
        """
        插入向量数据
        
        Args:
            data: 向量数据列表，每个元素包含file_id, content_type, content, embedding, embedding_model, position_info
            
        Returns:
            bool: 插入是否成功
        """
        try:
            if not self.collection:
                self.create_collection()
            
            # 准备插入数据
            insert_data = {
                "file_id": [item["file_id"] for item in data],
                "content_type": [item["content_type"] for item in data],
                "content": [item["content"] for item in data],
                "embedding": [item["embedding"] for item in data],
                "embedding_model": [item["embedding_model"] for item in data],
                "position_info": [item.get("position_info", {}) for item in data]
            }
            
            # 插入数据
            self.collection.insert(insert_data)
            self.collection.flush()
            
            logger.info(f"成功插入 {len(data)} 条向量数据")
            return True
            
        except Exception as e:
            logger.error(f"插入向量数据失败: {str(e)}")
            return False
    
    def search_vectors(self, query_vector: List[float], top_k: int = 10, 
                      filter_expr: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        搜索向量
        
        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            filter_expr: 过滤表达式
            
        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        try:
            if not self.collection:
                logger.error("集合不存在")
                return []
            
            # 加载集合
            self.collection.load()
            
            # 搜索参数
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            
            # 执行搜索
            results = self.collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["file_id", "content_type", "content", "embedding_model", "position_info"]
            )
            
            # 格式化结果
            search_results = []
            for hits in results:
                for hit in hits:
                    search_results.append({
                        "id": hit.id,
                        "distance": hit.distance,
                        "file_id": hit.entity.get("file_id"),
                        "content_type": hit.entity.get("content_type"),
                        "content": hit.entity.get("content"),
                        "embedding_model": hit.entity.get("embedding_model"),
                        "position_info": hit.entity.get("position_info")
                    })
            
            return search_results
            
        except Exception as e:
            logger.error(f"搜索向量失败: {str(e)}")
            return []
    
    def delete_vectors(self, file_id: int) -> bool:
        """
        删除指定文件的向量数据
        
        Args:
            file_id: 文件ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            if not self.collection:
                logger.error("集合不存在")
                return False
            
            # 删除表达式
            expr = f"file_id == {file_id}"
            
            # 执行删除
            self.collection.delete(expr)
            self.collection.flush()
            
            logger.info(f"成功删除文件ID为 {file_id} 的向量数据")
            return True
            
        except Exception as e:
            logger.error(f"删除向量数据失败: {str(e)}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            Dict[str, Any]: 集合统计信息
        """
        try:
            if not self.collection:
                return {}
            
            stats = self.collection.get_statistics()
            return {
                "collection_name": self.collection_name,
                "num_entities": stats.get("row_count", 0),
                "indexed_entities": stats.get("indexed_entities", 0)
            }
            
        except Exception as e:
            logger.error(f"获取集合统计信息失败: {str(e)}")
            return {}
    
    def test_connection(self) -> bool:
        """
        测试数据库连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 检查连接
            if not self.connection:
                return False
            
            # 获取服务器版本
            version = utility.get_server_version()
            logger.info(f"Milvus服务器版本: {version}")
            return True
            
        except Exception as e:
            logger.error(f"Milvus连接测试失败: {str(e)}")
            return False
    
    def close(self):
        """
        关闭数据库连接
        """
        try:
            if self.collection:
                self.collection.release()
            if self.connection:
                connections.disconnect("default")
            logger.info("Milvus连接已关闭")
        except Exception as e:
            logger.error(f"关闭Milvus连接失败: {str(e)}")

# 全局Milvus管理器实例
milvus_manager = None

def get_milvus_manager() -> MilvusManager:
    """
    获取Milvus管理器实例（单例模式）
    
    Returns:
        MilvusManager: Milvus管理器实例
    """
    global milvus_manager
    if milvus_manager is None:
        milvus_manager = MilvusManager()
    return milvus_manager 