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
    
    def _parse_deepseek_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析DeepSeek API返回的JSON响应 - 增强容错处理
        
        Args:
            response: DeepSeek API的原始响应
            
        Returns:
            Optional[Dict[str, Any]]: 解析后的JSON对象，失败时返回None
        """
        if not response or not response.strip():
            return None
            
        try:
            # 方法1：直接解析（适用于标准JSON响应）
            return json.loads(response.strip())
        except json.JSONDecodeError:
            pass
        
        try:
            # 方法2：提取JSON块（适用于包含解释文字的响应）
            import re
            
            # 查找JSON块模式：{...}
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue
                    
        except Exception:
            pass
        
        try:
            # 方法3：逐行查找JSON（适用于多行响应）
            lines = response.strip().split('\n')
            json_lines = []
            in_json = False
            
            for line in lines:
                line = line.strip()
                if line.startswith('{'):
                    in_json = True
                    json_lines = [line]
                elif in_json:
                    json_lines.append(line)
                    if line.endswith('}'):
                        try:
                            json_str = '\n'.join(json_lines)
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            in_json = False
                            json_lines = []
                            
        except Exception:
            pass
        
        # 方法4：手动构建JSON（应急方案）
        try:
            # 尝试从响应中提取关键信息
            result = {}
            
            # 查找核心关键词
            if '"core_keywords"' in response:
                # 提取core_keywords值
                import re
                pattern = r'"core_keywords":\s*"([^"]*)"'
                match = re.search(pattern, response)
                if match:
                    result['core_keywords'] = match.group(1)
                    result['refined_query'] = match.group(1)  # 使用核心关键词作为优化查询
                    result['search_intent'] = f"查找{match.group(1)}相关信息"
                    return result
                    
        except Exception:
            pass
        
        # 所有方法都失败，记录详细错误信息
        self.logger.error(f"JSON解析完全失败，响应内容: '{response[:500]}...'")
        return None
    
    def _optimize_query_for_retrieval(self, user_query: str) -> Dict[str, Any]:
        """
        查询优化 - 使用DeepSeek分析用户查询，提取核心检索关键词
        
        Args:
            user_query: 用户原始查询
            
        Returns:
            Dict[str, Any]: 包含优化结果的字典
        """
        try:
            # 构建查询优化提示词
            prompt_template = self.prompt_config['query_optimization']['query_rewrite']
            prompt = prompt_template.format(user_query=user_query)
            
            # 调用DeepSeek API进行查询分析
            response = self._call_deepseek_api(prompt)
            
            if response:
                try:
                    # 🔧 改进的JSON解析逻辑 - 支持多种响应格式
                    optimization_result = self._parse_deepseek_json_response(response)
                    
                    # 验证必要字段
                    if optimization_result and 'refined_query' in optimization_result and optimization_result['refined_query'].strip():
                        self.logger.info(f"查询优化成功: '{user_query}' -> '{optimization_result['refined_query']}'")
                        return {
                            'success': True,
                            'original_query': user_query,
                            'optimized_query': optimization_result['refined_query'],
                            'core_keywords': optimization_result.get('core_keywords', ''),
                            'search_intent': optimization_result.get('search_intent', ''),
                            'removed_noise': optimization_result.get('removed_noise', [])
                        }
                    else:
                        self.logger.warning("DeepSeek返回的优化结果无效，使用原始查询")
                        
                except Exception as e:
                    self.logger.error(f"查询优化失败: {str(e)}, 原始响应: {response[:200]}...")
            
            # 降级处理：返回原始查询
            return {
                'success': False,
                'original_query': user_query,
                'optimized_query': user_query,
                'core_keywords': user_query,
                'search_intent': '原始查询',
                'removed_noise': []
            }
            
        except Exception as e:
            self.logger.error(f"查询优化失败: {str(e)}")
            # 降级处理：返回原始查询
            return {
                'success': False,
                'original_query': user_query,
                'optimized_query': user_query,
                'core_keywords': user_query,
                'search_intent': '查询优化失败，使用原始查询',
                'removed_noise': []
            }
    
    def vector_search(self, query: str, top_k: int = 10, filters: Optional[Dict] = None, optimize_query: bool = True) -> List[Dict]:
        """
        向量相似性搜索 - 支持查询优化
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 过滤条件
            optimize_query: 是否启用查询优化（默认True）
            
        Returns:
            List[Dict]: 搜索结果
        """
        try:
            # 🎯 查询优化：在向量化之前先分析并优化查询
            # 检查配置是否启用查询优化
            query_optimization_enabled = self.model_config.get('query_optimization', {}).get('enabled', True)
            
            if optimize_query and query_optimization_enabled:
                optimization_result = self._optimize_query_for_retrieval(query)
                search_query = optimization_result['optimized_query']
                
                # 记录优化信息
                log_details = self.model_config.get('query_optimization', {}).get('log_optimization_details', True)
                if log_details:
                    if optimization_result['success']:
                        self.logger.info(f"✅ 查询优化: '{query}' -> '{search_query}'")
                    else:
                        self.logger.info(f"⚠️ 查询优化失败，使用原始查询: '{query}'")
            else:
                search_query = query
                optimization_result = None
                if optimize_query and not query_optimization_enabled:
                    self.logger.info("📴 查询优化已在配置中禁用")
            
            # 获取查询向量（使用优化后的查询）
            query_vector = self._get_text_embedding(search_query)
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
                
                # 🔥 添加chunk_id用于多模态内容关联
                result['chunk_id'] = result['id']  # Milvus的id就是document_chunks表的主键
                
                # 🎯 为每个结果添加查询优化信息
                if optimize_query and optimization_result:
                    result['query_optimization'] = {
                        'original_query': optimization_result['original_query'],
                        'optimized_query': optimization_result['optimized_query'],
                        'optimization_applied': optimization_result['success']
                    }
                
                enhanced_results.append(result)
            
            # 更新日志信息
            if optimize_query and optimization_result and optimization_result['success']:
                self.logger.info(f"向量搜索完成，原始查询: '{query}' -> 优化查询: '{search_query}'，返回{len(enhanced_results)}个结果")
            else:
                self.logger.info(f"向量搜索完成，查询: '{query}'，返回{len(enhanced_results)}个结果")
            
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
            
            # 🎯 向量搜索 - 启用查询优化
            vector_results = self.vector_search(query, top_k, filters, optimize_query=True)
            result['vector_results'] = vector_results
            
            # 知识图谱搜索
            if enable_graph:
                # 🎯 从优化查询或原始查询中提取实体
                # 如果向量搜索有优化结果，优先使用优化后的查询进行实体提取
                if vector_results and len(vector_results) > 0 and 'query_optimization' in vector_results[0]:
                    optimization_info = vector_results[0]['query_optimization']
                    if optimization_info['optimization_applied']:
                        entity_query = optimization_info['optimized_query']
                        self.logger.info(f"使用优化查询进行实体提取: '{entity_query}'")
                    else:
                        entity_query = query
                else:
                    entity_query = query
                
                entities = self._extract_entities_from_query(entity_query)
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
                # 🔧 使用增强的JSON解析方法
                try:
                    entities_data = self._parse_deepseek_json_response(response)
                    if entities_data:
                        all_entities = []
                        for entity_type, entities in entities_data.items():
                            if isinstance(entities, list):
                                all_entities.extend(entities)
                        return all_entities
                    else:
                        self.logger.warning(f"无法解析实体识别结果: {response[:200]}...")
                except Exception as e:
                    self.logger.error(f"实体识别JSON解析失败: {str(e)}, 响应: {response[:200]}...")
            
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
        基于检索的问答 - 支持多模态内容返回
        
        Args:
            question: 用户问题
            context_limit: 上下文文档数量限制
            
        Returns:
            Dict[str, Any]: 问答结果，包含多模态数据
        """
        try:
            # 检索相关文档
            search_results = self.hybrid_search(question, top_k=context_limit)
            
            # 🎯 提取多模态内容和准备上下文
            relevant_docs = []
            multimodal_content = {
                'images': [],
                'tables': [],
                'charts': []
            }
            
            for result in search_results['combined_results'][:context_limit]:
                if result['type'] == 'vector':
                    relevant_docs.append(result['content'])
                    
                    # 🔍 从MySQL获取完整的多模态数据
                    if 'chunk_id' in result:
                        chunk_multimodal = self._get_chunk_multimodal_content(result['chunk_id'])
                        if chunk_multimodal:
                            multimodal_content['images'].extend(chunk_multimodal.get('img', []))
                            multimodal_content['tables'].extend(chunk_multimodal.get('table', []))
                            multimodal_content['charts'].extend(chunk_multimodal.get('chars', []))
                            
                elif result['type'] == 'graph':
                    # 将图信息转换为文本描述
                    graph_desc = f"实体: {result['entity']}, 邻居: {len(result['neighbors'])}个"
                    relevant_docs.append(graph_desc)
            
            context = "\n\n".join(relevant_docs)
            
            # 🎯 构建增强的问答提示词（包含多模态信息）
            multimodal_context = self._build_multimodal_context(multimodal_content)
            enhanced_context = context
            if multimodal_context:
                enhanced_context += f"\n\n相关多媒体内容:\n{multimodal_context}"
            
            prompt = self.prompt_config['question_answering']['doc_qa'].format(
                relevant_docs=enhanced_context,
                question=question
            )
            
            # 调用大模型生成答案
            answer = self._call_deepseek_api(prompt)
            
            # 🎯 提取查询优化信息
            query_optimization_info = None
            if (search_results.get('vector_results') and 
                len(search_results['vector_results']) > 0 and 
                'query_optimization' in search_results['vector_results'][0]):
                query_optimization_info = search_results['vector_results'][0]['query_optimization']
            
            result = {
                'question': question,
                'answer': answer,
                'context': relevant_docs,
                'search_results': search_results,
                'multimodal_content': multimodal_content,  # 🔥 新增多模态内容
                'query_optimization': query_optimization_info,  # 🎯 添加查询优化信息
                'timestamp': datetime.now().isoformat()
            }
            
            # 🎯 更新日志，显示查询优化效果和多模态内容
            multimodal_stats = f"图片{len(multimodal_content['images'])}个, 表格{len(multimodal_content['tables'])}个, 图表{len(multimodal_content['charts'])}个"
            
            if query_optimization_info and query_optimization_info['optimization_applied']:
                self.logger.info(f"问答完成，原始问题: '{question}' -> 优化查询: '{query_optimization_info['optimized_query']}', 多模态内容: {multimodal_stats}")
            else:
                self.logger.info(f"问答完成，问题: '{question}', 多模态内容: {multimodal_stats}")
            
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
    
    def _get_chunk_multimodal_content(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """
        从MySQL获取文档块的多模态内容
        
        Args:
            chunk_id: 文档块ID
            
        Returns:
            Optional[Dict[str, Any]]: 多模态内容，包含img、table、chars等
        """
        try:
            query = """
            SELECT content 
            FROM document_chunks 
            WHERE id = :chunk_id
            """
            
            result = self.mysql_manager.execute_query(query, {'chunk_id': chunk_id})
            
            if result and len(result) > 0:
                content_json = result[0]['content']
                
                # 解析JSON内容
                if isinstance(content_json, str):
                    content_data = json.loads(content_json)
                else:
                    content_data = content_json
                
                # 提取结构化数据
                structured_data = {
                    'img': content_data.get('img', []),
                    'table': content_data.get('table', []),
                    'chars': content_data.get('chars', [])
                }
                
                return structured_data
                
        except Exception as e:
            self.logger.error(f"获取块多模态内容失败: {str(e)}")
            
        return None
    
    def _build_multimodal_context(self, multimodal_content: Dict[str, List]) -> str:
        """
        构建多模态内容的文本描述，用于增强上下文
        
        Args:
            multimodal_content: 多模态内容字典
            
        Returns:
            str: 多模态内容的文本描述
        """
        try:
            context_parts = []
            
            # 处理图片信息
            if multimodal_content['images']:
                img_descriptions = []
                for img in multimodal_content['images']:
                    desc = f"图片 {img.get('element_id', '')}"
                    if img.get('description'):
                        desc += f": {img['description']}"
                    if img.get('file_path'):
                        desc += f" (路径: {img['file_path']})"
                    img_descriptions.append(desc)
                
                if img_descriptions:
                    context_parts.append(f"相关图片: {'; '.join(img_descriptions)}")
            
            # 处理表格信息
            if multimodal_content['tables']:
                table_descriptions = []
                for table in multimodal_content['tables']:
                    desc = f"表格 {table.get('element_id', '')}"
                    if table.get('title'):
                        desc += f": {table['title']}"
                    if table.get('summary'):
                        desc += f" - {table['summary']}"
                    elif table.get('table_data'):
                        # 简化显示表格结构
                        rows = len(table['table_data'])
                        cols = len(table['table_data'][0]) if rows > 0 else 0
                        desc += f" ({rows}行x{cols}列)"
                    table_descriptions.append(desc)
                
                if table_descriptions:
                    context_parts.append(f"相关表格: {'; '.join(table_descriptions)}")
            
            # 处理图表信息
            if multimodal_content['charts']:
                chart_descriptions = []
                for chart in multimodal_content['charts']:
                    desc = f"图表 {chart.get('element_id', '')}"
                    if chart.get('description'):
                        desc += f": {chart['description']}"
                    chart_descriptions.append(desc)
                
                if chart_descriptions:
                    context_parts.append(f"相关图表: {'; '.join(chart_descriptions)}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            self.logger.error(f"构建多模态上下文失败: {str(e)}")
            return ""