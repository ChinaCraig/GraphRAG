#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF向量化服务
使用paraphrase-multilingual-mpnet-base-v2模型进行向量化处理
"""

import json
import logging
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from utils.MilvusManager import get_milvus_manager
from utils.MySQLManager import get_mysql_manager

logger = logging.getLogger(__name__)

class PdfVectorService:
    """
    PDF向量化服务
    使用paraphrase-multilingual-mpnet-base-v2模型进行向量化处理
    """
    
    def __init__(self, config_path: str = "config/model.yaml"):
        """
        初始化PDF向量化服务
        
        Args:
            config_path: 模型配置文件路径
        """
        self.config_path = config_path
        self.model = None
        self.milvus_manager = None
        self.mysql_manager = None
        self._load_config()
        self._init_model()
        self._init_managers()
    
    def _load_config(self):
        """
        加载模型配置
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self.embedding_config = config.get('embedding', {})
            logger.info("嵌入模型配置加载成功")
            
        except Exception as e:
            logger.error(f"加载嵌入模型配置失败: {str(e)}")
            raise
    
    def _init_model(self):
        """
        初始化嵌入模型
        """
        try:
            model_name = self.embedding_config.get('model_name', 'paraphrase-multilingual-mpnet-base-v2')
            model_path = self.embedding_config.get('model_path', './models/paraphrase-multilingual-mpnet-base-v2')
            
            # 检查本地模型是否存在
            if Path(model_path).exists():
                logger.info(f"使用本地模型: {model_path}")
                self.model = SentenceTransformer(model_path)
            else:
                logger.info(f"下载模型: {model_name}")
                self.model = SentenceTransformer(model_name)
            
            # 设置模型参数
            self.device = self.embedding_config.get('device', 'cpu')
            self.batch_size = self.embedding_config.get('batch_size', 32)
            self.max_length = self.embedding_config.get('max_length', 512)
            
            logger.info("嵌入模型初始化成功")
            
        except Exception as e:
            logger.error(f"初始化嵌入模型失败: {str(e)}")
            raise
    
    def _init_managers(self):
        """
        初始化数据库管理器
        """
        try:
            self.milvus_manager = get_milvus_manager()
            self.mysql_manager = get_mysql_manager()
            logger.info("数据库管理器初始化成功")
            
        except Exception as e:
            logger.error(f"初始化数据库管理器失败: {str(e)}")
            raise
    
    def vectorize_content(self, json_content: str) -> bool:
        """
        对提取的内容进行向量化处理
        这是唯一的入口函数
        
        Args:
            json_content: JSON字符串（上个步骤产生的结果）
            
        Returns:
            bool: 向量化处理是否成功
        """
        try:
            # 解析JSON内容
            content_data = self._parse_json_content(json_content)
            if not content_data:
                raise ValueError("JSON内容解析失败或为空")
            
            logger.info(f"开始向量化处理，共 {len(content_data)} 个内容块")
            
            # 向量化处理
            vectorized_data = self._vectorize_data(content_data)
            
            # 保存到向量数据库
            success = self._save_to_vector_db(vectorized_data)
            
            # 保存到MySQL数据库
            if success:
                self._save_to_mysql(vectorized_data)
            
            logger.info("向量化处理完成")
            return success
            
        except Exception as e:
            logger.error(f"向量化处理失败: {str(e)}")
            return False
    
    def _parse_json_content(self, json_content: str) -> List[Dict[str, Any]]:
        """
        解析JSON内容
        
        Args:
            json_content: JSON字符串
            
        Returns:
            List[Dict[str, Any]]: 解析后的内容列表
        """
        try:
            # 如果是字符串，解析为JSON
            if isinstance(json_content, str):
                content_data = json.loads(json_content)
            else:
                content_data = json_content
            
            # 验证数据结构
            if not isinstance(content_data, list):
                raise ValueError("JSON内容必须是列表格式")
            
            return content_data
            
        except Exception as e:
            logger.error(f"解析JSON内容失败: {str(e)}")
            raise
    
    def _vectorize_data(self, content_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        向量化数据
        
        Args:
            content_data: 内容数据列表
            
        Returns:
            List[Dict[str, Any]]: 向量化后的数据
        """
        vectorized_data = []
        
        try:
            # 提取文本内容
            texts = []
            for item in content_data:
                if 'content' in item and item['content']:
                    texts.append(item['content'])
            
            if not texts:
                logger.warning("没有找到有效的文本内容")
                return []
            
            # 批量生成向量
            logger.info(f"开始生成向量，共 {len(texts)} 个文本")
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                max_length=self.max_length,
                device=self.device,
                show_progress_bar=True
            )
            
            # 构建向量化数据
            for i, item in enumerate(content_data):
                if 'content' in item and item['content']:
                    vectorized_item = {
                        "file_id": item.get("file_id", 0),
                        "content_type": item.get("type", "text"),
                        "content": item["content"],
                        "embedding": embeddings[i].tolist(),
                        "embedding_model": "paraphrase-multilingual-mpnet-base-v2",
                        "position_info": item.get("position", {})
                    }
                    vectorized_data.append(vectorized_item)
            
            logger.info(f"向量化完成，共生成 {len(vectorized_data)} 个向量")
            
        except Exception as e:
            logger.error(f"向量化数据失败: {str(e)}")
            raise
        
        return vectorized_data
    
    def _save_to_vector_db(self, vectorized_data: List[Dict[str, Any]]) -> bool:
        """
        保存向量到Milvus数据库
        
        Args:
            vectorized_data: 向量化数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            if not vectorized_data:
                logger.warning("没有向量数据需要保存")
                return True
            
            # 保存到Milvus
            success = self.milvus_manager.insert_vectors(vectorized_data)
            
            if success:
                logger.info(f"成功保存 {len(vectorized_data)} 个向量到Milvus")
            else:
                logger.error("保存向量到Milvus失败")
            
            return success
            
        except Exception as e:
            logger.error(f"保存向量到数据库失败: {str(e)}")
            return False
    
    def _save_to_mysql(self, vectorized_data: List[Dict[str, Any]]) -> bool:
        """
        保存向量信息到MySQL数据库
        
        Args:
            vectorized_data: 向量化数据
            
        Returns:
            bool: 保存是否成功
        """
        try:
            if not vectorized_data:
                return True
            
            # 准备插入数据
            for item in vectorized_data:
                sql = """
                INSERT INTO vector_data (file_id, content_type, content, vector_id, embedding_model, position_info)
                VALUES (%(file_id)s, %(content_type)s, %(content)s, %(vector_id)s, %(embedding_model)s, %(position_info)s)
                """
                
                params = {
                    "file_id": item["file_id"],
                    "content_type": item["content_type"],
                    "content": item["content"],
                    "vector_id": f"vec_{item['file_id']}_{hash(item['content'])}",
                    "embedding_model": item["embedding_model"],
                    "position_info": json.dumps(item["position_info"])
                }
                
                self.mysql_manager.execute_insert(sql, params)
            
            logger.info(f"成功保存 {len(vectorized_data)} 条向量信息到MySQL")
            return True
            
        except Exception as e:
            logger.error(f"保存向量信息到MySQL失败: {str(e)}")
            return False
    
    def search_similar_vectors(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_text: 查询文本
            top_k: 返回结果数量
            
        Returns:
            List[Dict[str, Any]]: 搜索结果
        """
        try:
            # 生成查询向量
            query_embedding = self.model.encode([query_text])[0].tolist()
            
            # 在Milvus中搜索
            results = self.milvus_manager.search_vectors(query_embedding, top_k)
            
            return results
            
        except Exception as e:
            logger.error(f"搜索相似向量失败: {str(e)}")
            return []

# 全局PDF向量化服务实例
pdf_vector_service = PdfVectorService()

def vectorize_pdf_content(json_content: str) -> bool:
    """
    PDF内容向量化的全局入口函数
    
    Args:
        json_content: JSON字符串（上个步骤产生的结果）
        
    Returns:
        bool: 向量化处理是否成功
    """
    return pdf_vector_service.vectorize_content(json_content) 