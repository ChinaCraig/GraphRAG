"""
PDF向量化服务
负责将PDF文档内容向量化并存储到向量数据库
"""

import logging
import yaml
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from utils.MySQLManager import MySQLManager
from utils.MilvusManager import MilvusManager
from sentence_transformers import SentenceTransformer
import numpy as np


class PdfVectorService:
    """PDF向量化服务类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化PDF向量化服务
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_configs()
        
        # 初始化数据库管理器
        self.mysql_manager = MySQLManager()
        self.milvus_manager = MilvusManager()
        
        # 初始化嵌入模型
        self._init_embedding_model()
    
    def _load_configs(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
            
            with open('config/model.yaml', 'r', encoding='utf-8') as file:
                self.model_config = yaml.safe_load(file)
            
            self.logger.info("PDF向量化服务配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载PDF向量化服务配置失败: {str(e)}")
            raise
    
    def _init_embedding_model(self) -> None:
        """初始化嵌入模型"""
        try:
            model_name = self.model_config['embedding']['model_name']
            cache_dir = self.model_config['embedding']['cache_dir']
            
            self.embedding_model = SentenceTransformer(
                model_name,
                cache_folder=cache_dir
            )
            
            self.dimension = self.model_config['embedding']['dimension']
            self.batch_size = self.model_config['embedding']['batch_size']
            self.normalize = self.model_config['embedding']['normalize']
            
            self.logger.info(f"嵌入模型初始化成功: {model_name}")
            
        except Exception as e:
            self.logger.error(f"初始化嵌入模型失败: {str(e)}")
            raise
    
    def vectorize_pdf_document(self, document_id: int) -> Dict[str, Any]:
        """
        对PDF文档进行向量化处理
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 向量化结果
        """
        try:
            # 获取文档信息
            doc_info = self._get_document_info(document_id)
            if not doc_info:
                return {
                    'success': False,
                    'message': '文档不存在',
                    'vector_count': 0
                }
            
            # 获取文档分块
            chunks = self._get_document_chunks(document_id)
            if not chunks:
                return {
                    'success': False,
                    'message': '文档分块不存在，请先进行内容提取',
                    'vector_count': 0
                }
            
            # 批量生成向量
            vector_data = self._generate_vectors_for_chunks(chunks, document_id)
            
            if not vector_data:
                return {
                    'success': False,
                    'message': '向量生成失败',
                    'vector_count': 0
                }
            
            # 存储向量到Milvus
            success = self._store_vectors_to_milvus(vector_data)
            
            if success:
                # 更新数据库中的向量ID
                self._update_chunk_vector_ids(vector_data)
                
                # 更新文档处理状态
                self.mysql_manager.update_data(
                    'documents',
                    {'process_status': 'vectorized'},
                    'id = :doc_id',
                    {'doc_id': document_id}
                )
                
                self.logger.info(f"PDF文档向量化完成，文档ID: {document_id}, 向量数量: {len(vector_data)}")
                
                return {
                    'success': True,
                    'message': 'PDF文档向量化成功',
                    'vector_count': len(vector_data),
                    'document_id': document_id
                }
            else:
                return {
                    'success': False,
                    'message': '向量存储失败',
                    'vector_count': 0
                }
                
        except Exception as e:
            self.logger.error(f"PDF文档向量化失败: {str(e)}")
            return {
                'success': False,
                'message': f'PDF文档向量化失败: {str(e)}',
                'vector_count': 0
            }
    
    def _get_document_info(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        获取文档信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Optional[Dict[str, Any]]: 文档信息
        """
        try:
            query = "SELECT * FROM documents WHERE id = :doc_id"
            result = self.mysql_manager.execute_query(query, {'doc_id': document_id})
            return result[0] if result else None
            
        except Exception as e:
            self.logger.error(f"获取文档信息失败: {str(e)}")
            return None
    
    def _get_document_chunks(self, document_id: int) -> List[Dict[str, Any]]:
        """
        获取文档分块
        
        Args:
            document_id: 文档ID
            
        Returns:
            List[Dict[str, Any]]: 文档分块列表
        """
        try:
            query = """
            SELECT id, document_id, chunk_index, content, content_hash
            FROM document_chunks 
            WHERE document_id = :doc_id 
            ORDER BY chunk_index
            """
            
            result = self.mysql_manager.execute_query(query, {'doc_id': document_id})
            return result
            
        except Exception as e:
            self.logger.error(f"获取文档分块失败: {str(e)}")
            return []
    
    def _generate_vectors_for_chunks(self, chunks: List[Dict[str, Any]], document_id: int) -> List[Dict[str, Any]]:
        """
        为文档分块生成向量
        
        Args:
            chunks: 文档分块列表
            document_id: 文档ID
            
        Returns:
            List[Dict[str, Any]]: 包含向量的数据列表
        """
        try:
            vector_data = []
            
            # 准备文本列表
            texts = [chunk['content'] for chunk in chunks]
            
            # 批量生成向量
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                batch_chunks = chunks[i:i + self.batch_size]
                
                # 生成向量
                embeddings = self.embedding_model.encode(
                    batch_texts,
                    batch_size=len(batch_texts),
                    normalize_embeddings=self.normalize,
                    show_progress_bar=False
                )
                
                # 处理每个向量
                for j, embedding in enumerate(embeddings):
                    chunk = batch_chunks[j]
                    vector_id = str(uuid.uuid4())
                    
                    vector_item = {
                        'id': vector_id,
                        'vector': embedding.tolist(),
                        'document_id': document_id,
                        'chunk_index': chunk['chunk_index'],
                        'content': chunk['content'][:500],  # 限制内容长度
                        'metadata': {
                            'chunk_id': chunk['id'],
                            'content_hash': chunk['content_hash'],
                            'full_content_length': len(chunk['content']),
                            'creation_time': datetime.now().isoformat()
                        }
                    }
                    
                    vector_data.append(vector_item)
                
                self.logger.info(f"批量向量生成完成，批次: {i//self.batch_size + 1}, 向量数: {len(embeddings)}")
            
            return vector_data
            
        except Exception as e:
            self.logger.error(f"生成向量失败: {str(e)}")
            return []
    
    def _store_vectors_to_milvus(self, vector_data: List[Dict[str, Any]]) -> bool:
        """
        将向量存储到Milvus
        
        Args:
            vector_data: 向量数据列表
            
        Returns:
            bool: 存储成功返回True
        """
        try:
            # 批量插入向量
            batch_size = 100  # Milvus批量插入大小
            
            for i in range(0, len(vector_data), batch_size):
                batch_data = vector_data[i:i + batch_size]
                success = self.milvus_manager.insert_vectors(batch_data)
                
                if not success:
                    self.logger.error(f"向量批量插入失败，批次: {i//batch_size + 1}")
                    return False
                
                self.logger.info(f"向量批量插入成功，批次: {i//batch_size + 1}, 数量: {len(batch_data)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"存储向量到Milvus失败: {str(e)}")
            return False
    
    def _update_chunk_vector_ids(self, vector_data: List[Dict[str, Any]]) -> bool:
        """
        更新分块的向量ID
        
        Args:
            vector_data: 向量数据列表
            
        Returns:
            bool: 更新成功返回True
        """
        try:
            for vector_item in vector_data:
                chunk_id = vector_item['metadata']['chunk_id']
                vector_id = vector_item['id']
                
                success = self.mysql_manager.update_data(
                    'document_chunks',
                    {'vector_id': vector_id},
                    'id = :chunk_id',
                    {'chunk_id': chunk_id}
                )
                
                if not success:
                    self.logger.warning(f"更新分块向量ID失败，分块ID: {chunk_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"更新分块向量ID失败: {str(e)}")
            return False
    
    def search_similar_chunks(self, query_text: str, document_id: Optional[int] = None, 
                            top_k: int = 10) -> List[Dict[str, Any]]:
        """
        搜索相似的文档分块
        
        Args:
            query_text: 查询文本
            document_id: 限定文档ID（可选）
            top_k: 返回结果数量
            
        Returns:
            List[Dict[str, Any]]: 相似分块列表
        """
        try:
            # 生成查询向量
            query_embedding = self.embedding_model.encode(
                [query_text],
                normalize_embeddings=self.normalize
            )[0]
            
            # 构建过滤条件
            expr = None
            if document_id:
                expr = f"document_id == {document_id}"
            
            # 执行向量搜索
            search_results = self.milvus_manager.search_vectors(
                query_vectors=[query_embedding.tolist()],
                top_k=top_k,
                expr=expr
            )
            
            # 获取完整的分块内容
            enhanced_results = []
            for result in search_results:
                chunk_id = result['metadata']['chunk_id']
                
                # 获取完整的分块信息
                chunk_query = """
                SELECT dc.*, d.filename, d.file_type
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.id
                WHERE dc.id = :chunk_id
                """
                
                chunk_info = self.mysql_manager.execute_query(
                    chunk_query, 
                    {'chunk_id': chunk_id}
                )
                
                if chunk_info:
                    enhanced_result = {
                        'chunk_info': chunk_info[0],
                        'similarity_score': result['score'],
                        'vector_id': result['id'],
                        'metadata': result['metadata']
                    }
                    enhanced_results.append(enhanced_result)
            
            self.logger.info(f"相似分块搜索完成，查询: {query_text}, 结果数: {len(enhanced_results)}")
            return enhanced_results
            
        except Exception as e:
            self.logger.error(f"搜索相似分块失败: {str(e)}")
            return []
    
    def get_document_vectors_stats(self, document_id: int) -> Dict[str, Any]:
        """
        获取文档向量统计信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 向量统计信息
        """
        try:
            # 获取分块数量
            chunk_query = """
            SELECT COUNT(*) as total_chunks,
                   COUNT(vector_id) as vectorized_chunks
            FROM document_chunks 
            WHERE document_id = :doc_id
            """
            
            chunk_result = self.mysql_manager.execute_query(
                chunk_query, 
                {'doc_id': document_id}
            )
            
            stats = {
                'document_id': document_id,
                'total_chunks': 0,
                'vectorized_chunks': 0,
                'vectorization_rate': 0.0
            }
            
            if chunk_result:
                stats['total_chunks'] = chunk_result[0]['total_chunks']
                stats['vectorized_chunks'] = chunk_result[0]['vectorized_chunks']
                
                if stats['total_chunks'] > 0:
                    stats['vectorization_rate'] = stats['vectorized_chunks'] / stats['total_chunks']
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取文档向量统计信息失败: {str(e)}")
            return {}
    
    def delete_document_vectors(self, document_id: int) -> bool:
        """
        删除文档的所有向量
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            # 从Milvus中删除向量
            expr = f"document_id == {document_id}"
            success = self.milvus_manager.delete_vectors(expr)
            
            if success:
                # 清空分块的向量ID
                self.mysql_manager.update_data(
                    'document_chunks',
                    {'vector_id': None},
                    'document_id = :doc_id',
                    {'doc_id': document_id}
                )
                
                self.logger.info(f"文档向量删除成功，文档ID: {document_id}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"删除文档向量失败: {str(e)}")
            return False
    
    def re_vectorize_document(self, document_id: int) -> Dict[str, Any]:
        """
        重新向量化文档
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 重新向量化结果
        """
        try:
            # 先删除现有向量
            delete_success = self.delete_document_vectors(document_id)
            
            if not delete_success:
                return {
                    'success': False,
                    'message': '删除现有向量失败',
                    'vector_count': 0
                }
            
            # 重新向量化
            result = self.vectorize_pdf_document(document_id)
            
            if result['success']:
                self.logger.info(f"文档重新向量化成功，文档ID: {document_id}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"重新向量化文档失败: {str(e)}")
            return {
                'success': False,
                'message': f'重新向量化文档失败: {str(e)}',
                'vector_count': 0
            }
    
    def batch_vectorize_documents(self, document_ids: List[int]) -> Dict[str, Any]:
        """
        批量向量化文档
        
        Args:
            document_ids: 文档ID列表
            
        Returns:
            Dict[str, Any]: 批量向量化结果
        """
        try:
            results = {
                'total_documents': len(document_ids),
                'successful': 0,
                'failed': 0,
                'details': []
            }
            
            for document_id in document_ids:
                try:
                    result = self.vectorize_pdf_document(document_id)
                    
                    if result['success']:
                        results['successful'] += 1
                    else:
                        results['failed'] += 1
                    
                    results['details'].append({
                        'document_id': document_id,
                        'success': result['success'],
                        'message': result['message'],
                        'vector_count': result['vector_count']
                    })
                    
                    self.logger.info(f"文档 {document_id} 向量化完成: {result['success']}")
                    
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'document_id': document_id,
                        'success': False,
                        'message': str(e),
                        'vector_count': 0
                    })
                    
                    self.logger.error(f"文档 {document_id} 向量化失败: {str(e)}")
            
            self.logger.info(f"批量向量化完成，成功: {results['successful']}, 失败: {results['failed']}")
            return results
            
        except Exception as e:
            self.logger.error(f"批量向量化失败: {str(e)}")
            return {
                'total_documents': len(document_ids),
                'successful': 0,
                'failed': len(document_ids),
                'details': [],
                'error': str(e)
            }