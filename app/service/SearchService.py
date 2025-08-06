"""
智能检索服务
负责基于向量和知识图谱的智能搜索功能
"""

import logging
import yaml
import json
import numpy as np
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
import requests
import re

from utils.MySQLManager import MySQLManager
from utils.MilvusManager import MilvusManager
from utils.Neo4jManager import Neo4jManager
from sentence_transformers import SentenceTransformer


class SearchService:
    """智能检索服务类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化搜索服务
        
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
        self.neo4j_manager = Neo4jManager()
        
        # 初始化模型
        self._init_models()
    
    def _load_configs(self) -> None:
        """加载配置文件"""
        try:
            # 加载主配置
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
            
            # 加载模型配置
            with open('config/model.yaml', 'r', encoding='utf-8') as file:
                self.model_config = yaml.safe_load(file)
            
            # 加载提示词配置
            with open('config/prompt.yaml', 'r', encoding='utf-8') as file:
                self.prompt_config = yaml.safe_load(file)
            
            self.logger.info("搜索服务配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载搜索服务配置失败: {str(e)}")
            raise
    
    def _init_models(self) -> None:
        """初始化模型"""
        try:
            # 初始化嵌入模型
            model_name = self.model_config['embedding']['model_name']
            self.embedding_model = SentenceTransformer(
                model_name,
                cache_folder=self.model_config['embedding']['cache_dir']
            )
            
            self.logger.info(f"嵌入模型初始化成功: {model_name}")
            
        except Exception as e:
            self.logger.error(f"初始化模型失败: {str(e)}")
            raise
    
    def _get_text_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取文本向量
        
        Args:
            text: 输入文本
            
        Returns:
            Optional[List[float]]: 文本向量，失败返回None
        """
        try:
            # 文本预处理
            processed_text = self._preprocess_text(text)
            
            # 生成向量
            embedding = self.embedding_model.encode(
                processed_text,
                normalize_embeddings=self.model_config['embedding']['normalize']
            )
            
            return embedding.tolist()
            
        except Exception as e:
            self.logger.error(f"获取文本向量失败: {str(e)}")
            return None
    
    def _preprocess_text(self, text: str) -> str:
        """
        文本预处理
        
        Args:
            text: 原始文本
            
        Returns:
            str: 预处理后的文本
        """
        try:
            preprocessing_config = self.model_config['embedding']['preprocessing']
            
            # 清理文本
            if preprocessing_config.get('clean_text', True):
                text = re.sub(r'\s+', ' ', text)  # 合并多个空白字符
                text = text.strip()
            
            # 转小写
            if preprocessing_config.get('lowercase', False):
                text = text.lower()
            
            # 移除特殊字符
            if preprocessing_config.get('remove_special_chars', False):
                text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
            
            # 限制长度
            max_length = preprocessing_config.get('max_chunk_size', 500)
            if len(text) > max_length:
                text = text[:max_length]
            
            return text
            
        except Exception as e:
            self.logger.error(f"文本预处理失败: {str(e)}")
            return text
    
    def _call_deepseek_api(self, prompt: str, max_tokens: Optional[int] = None) -> Optional[str]:
        """
        调用DeepSeek API
        
        Args:
            prompt: 提示词
            max_tokens: 最大生成token数
            
        Returns:
            Optional[str]: API响应内容，失败返回None
        """
        try:
            deepseek_config = self.model_config['deepseek']
            
            headers = {
                'Authorization': f"Bearer {deepseek_config['api_key']}",
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': deepseek_config['model_name'],
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': max_tokens or deepseek_config['max_tokens'],
                'temperature': deepseek_config['temperature'],
                'top_p': deepseek_config['top_p']
            }
            
            response = requests.post(
                f"{deepseek_config['api_url']}/chat/completions",
                headers=headers,
                json=data,
                timeout=deepseek_config['timeout']
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                self.logger.error(f"DeepSeek API调用失败: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"调用DeepSeek API失败: {str(e)}")
            return None
    
    def vector_search(self, query: str, top_k: int = 10, filters: Optional[Dict] = None) -> List[Dict]:
        """
        向量相似性搜索
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 过滤条件
            
        Returns:
            List[Dict]: 搜索结果
        """
        try:
            # 获取查询向量
            query_vector = self._get_text_embedding(query)
            if not query_vector:
                return []
            
            # 构建过滤表达式
            expr = None
            if filters:
                conditions = []
                if 'document_id' in filters:
                    conditions.append(f"document_id == {filters['document_id']}")
                if 'file_type' in filters:
                    # 需要通过document_id关联查询文件类型
                    pass
                
                if conditions:
                    expr = " and ".join(conditions)
            
            # 执行向量搜索
            results = self.milvus_manager.search_vectors(
                query_vectors=[query_vector],
                top_k=top_k,
                expr=expr
            )
            
            # 获取关联的文档信息
            enhanced_results = []
            for result in results:
                # 获取文档信息
                doc_info = self.mysql_manager.execute_query(
                    "SELECT filename, file_type FROM documents WHERE id = :doc_id",
                    {'doc_id': result['document_id']}
                )
                
                if doc_info:
                    result['document_info'] = doc_info[0]
                
                enhanced_results.append(result)
            
            self.logger.info(f"向量搜索完成，查询: {query}，返回{len(enhanced_results)}个结果")
            return enhanced_results
            
        except Exception as e:
            self.logger.error(f"向量搜索失败: {str(e)}")
            return []
    
    def graph_search(self, entity_name: str, relationship_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        知识图谱搜索
        
        Args:
            entity_name: 实体名称
            relationship_types: 关系类型列表
            
        Returns:
            Dict[str, Any]: 搜索结果
        """
        try:
            # 查找实体
            entities = self.neo4j_manager.find_nodes(
                label="Entity",
                properties={"name": entity_name}
            )
            
            if not entities:
                return {
                    'entity': None,
                    'neighbors': [],
                    'relationships': []
                }
            
            entity = entities[0]
            entity_id = entity['node_id']
            
            # 获取邻居节点
            neighbors = self.neo4j_manager.get_node_neighbors(
                entity_id,
                relationship_types
            )
            
            # 获取相关关系
            relationships = []
            if relationship_types:
                for rel_type in relationship_types:
                    rels = self.neo4j_manager.find_relationships(
                        relationship_type=rel_type,
                        start_label="Entity"
                    )
                    relationships.extend(rels)
            
            result = {
                'entity': entity,
                'neighbors': neighbors,
                'relationships': relationships
            }
            
            self.logger.info(f"知识图谱搜索完成，实体: {entity_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"知识图谱搜索失败: {str(e)}")
            return {
                'entity': None,
                'neighbors': [],
                'relationships': []
            }
    
    def hybrid_search(self, query: str, top_k: int = 10, 
                     enable_graph: bool = True, 
                     filters: Optional[Dict] = None) -> Dict[str, Any]:
        """
        混合搜索（向量搜索 + 知识图谱搜索）
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            enable_graph: 是否启用知识图谱搜索
            filters: 过滤条件
            
        Returns:
            Dict[str, Any]: 混合搜索结果
        """
        try:
            result = {
                'query': query,
                'vector_results': [],
                'graph_results': {},
                'combined_results': []
            }
            
            # 向量搜索
            vector_results = self.vector_search(query, top_k, filters)
            result['vector_results'] = vector_results
            
            # 知识图谱搜索
            if enable_graph:
                # 提取查询中的实体
                entities = self._extract_entities_from_query(query)
                graph_results = {}
                
                for entity in entities:
                    entity_result = self.graph_search(entity)
                    if entity_result['entity']:
                        graph_results[entity] = entity_result
                
                result['graph_results'] = graph_results
            
            # 合并结果
            combined_results = self._combine_search_results(vector_results, result['graph_results'])
            result['combined_results'] = combined_results
            
            self.logger.info(f"混合搜索完成，查询: {query}")
            return result
            
        except Exception as e:
            self.logger.error(f"混合搜索失败: {str(e)}")
            return {
                'query': query,
                'vector_results': [],
                'graph_results': {},
                'combined_results': []
            }
    
    def _extract_entities_from_query(self, query: str) -> List[str]:
        """
        从查询中提取实体
        
        Args:
            query: 查询文本
            
        Returns:
            List[str]: 提取的实体列表
        """
        try:
            # 使用DeepSeek API进行实体识别
            prompt = self.prompt_config['entity_recognition']['ner_extraction'].format(
                text_content=query
            )
            
            response = self._call_deepseek_api(prompt)
            if response:
                # 解析JSON响应
                try:
                    entities_data = json.loads(response)
                    all_entities = []
                    for entity_type, entities in entities_data.items():
                        if isinstance(entities, list):
                            all_entities.extend(entities)
                    return all_entities
                except json.JSONDecodeError:
                    self.logger.warning(f"无法解析实体识别结果: {response}")
            
            return []
            
        except Exception as e:
            self.logger.error(f"提取实体失败: {str(e)}")
            return []
    
    def _combine_search_results(self, vector_results: List[Dict], graph_results: Dict) -> List[Dict]:
        """
        合并搜索结果
        
        Args:
            vector_results: 向量搜索结果
            graph_results: 知识图谱搜索结果
            
        Returns:
            List[Dict]: 合并后的结果
        """
        try:
            combined = []
            
            # 添加向量搜索结果
            for result in vector_results:
                combined_item = {
                    'type': 'vector',
                    'score': result['score'],
                    'content': result['content'],
                    'document_id': result['document_id'],
                    'chunk_index': result['chunk_index'],
                    'metadata': result.get('metadata', {}),
                    'document_info': result.get('document_info', {})
                }
                combined.append(combined_item)
            
            # 添加知识图谱结果
            for entity_name, graph_data in graph_results.items():
                if graph_data['entity']:
                    combined_item = {
                        'type': 'graph',
                        'score': 1.0,  # 图搜索结果给予固定分数
                        'entity': entity_name,
                        'entity_properties': graph_data['entity']['properties'],
                        'neighbors': graph_data['neighbors'],
                        'relationships': graph_data['relationships']
                    }
                    combined.append(combined_item)
            
            # 按分数排序
            combined.sort(key=lambda x: x['score'], reverse=True)
            
            return combined
            
        except Exception as e:
            self.logger.error(f"合并搜索结果失败: {str(e)}")
            return []
    
    def question_answering(self, question: str, context_limit: int = 5) -> Dict[str, Any]:
        """
        基于检索的问答
        
        Args:
            question: 用户问题
            context_limit: 上下文文档数量限制
            
        Returns:
            Dict[str, Any]: 问答结果
        """
        try:
            # 检索相关文档
            search_results = self.hybrid_search(question, top_k=context_limit)
            
            # 准备上下文
            relevant_docs = []
            for result in search_results['combined_results'][:context_limit]:
                if result['type'] == 'vector':
                    relevant_docs.append(result['content'])
                elif result['type'] == 'graph':
                    # 将图信息转换为文本描述
                    graph_desc = f"实体: {result['entity']}, 邻居: {len(result['neighbors'])}个"
                    relevant_docs.append(graph_desc)
            
            context = "\n\n".join(relevant_docs)
            
            # 构建问答提示词
            prompt = self.prompt_config['question_answering']['doc_qa'].format(
                relevant_docs=context,
                question=question
            )
            
            # 调用大模型生成答案
            answer = self._call_deepseek_api(prompt)
            
            result = {
                'question': question,
                'answer': answer,
                'context': relevant_docs,
                'search_results': search_results,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.info(f"问答完成，问题: {question}")
            return result
            
        except Exception as e:
            self.logger.error(f"问答失败: {str(e)}")
            return {
                'question': question,
                'answer': f"抱歉，回答您的问题时出现错误: {str(e)}",
                'context': [],
                'search_results': {},
                'timestamp': datetime.now().isoformat()
            }
    
    def semantic_search(self, query: str, search_type: str = "all", 
                       top_k: int = 10, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """
        语义搜索
        
        Args:
            query: 查询文本
            search_type: 搜索类型 (vector, graph, all)
            top_k: 返回结果数量
            filters: 过滤条件
            
        Returns:
            Dict[str, Any]: 搜索结果
        """
        try:
            if search_type == "vector":
                results = self.vector_search(query, top_k, filters)
                return {
                    'search_type': 'vector',
                    'results': results,
                    'total': len(results)
                }
            elif search_type == "graph":
                entities = self._extract_entities_from_query(query)
                graph_results = {}
                for entity in entities:
                    graph_results[entity] = self.graph_search(entity)
                
                return {
                    'search_type': 'graph',
                    'results': graph_results,
                    'total': len(graph_results)
                }
            else:  # all
                results = self.hybrid_search(query, top_k, True, filters)
                return {
                    'search_type': 'hybrid',
                    'results': results,
                    'total': len(results['combined_results'])
                }
                
        except Exception as e:
            self.logger.error(f"语义搜索失败: {str(e)}")
            return {
                'search_type': search_type,
                'results': [],
                'total': 0,
                'error': str(e)
            }
    
    def get_search_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """
        获取搜索建议
        
        Args:
            partial_query: 部分查询文本
            limit: 建议数量限制
            
        Returns:
            List[str]: 搜索建议列表
        """
        try:
            # 从数据库中获取相似的文档标题或内容片段
            query = """
            SELECT DISTINCT content
            FROM document_chunks
            WHERE content LIKE :pattern
            LIMIT :limit
            """
            
            pattern = f"%{partial_query}%"
            results = self.mysql_manager.execute_query(
                query, 
                {'pattern': pattern, 'limit': limit}
            )
            
            suggestions = []
            for result in results:
                content = result['content']
                # 提取包含查询词的句子
                sentences = content.split('。')
                for sentence in sentences:
                    if partial_query in sentence and len(sentence.strip()) > 0:
                        suggestions.append(sentence.strip())
                        if len(suggestions) >= limit:
                            break
                if len(suggestions) >= limit:
                    break
            
            return suggestions[:limit]
            
        except Exception as e:
            self.logger.error(f"获取搜索建议失败: {str(e)}")
            return []