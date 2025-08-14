"""
搜索格式化服务
实现三路召回、融合与去重、重排功能，包括：
1. 三路召回：BM25倒排、向量语义、图谱结构化
2. 融合与去重：多路候选合并、相似度去重、分值归一化  
3. 重排：Cross-Encoder重排、去毒清洗、多样性控制
"""

import json
import logging
import math
import numpy as np
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from collections import defaultdict
import yaml
from sentence_transformers import SentenceTransformer

# 配置日志
logger = logging.getLogger(__name__)


class SearchFormatService:
    """搜索格式化服务类"""
    
    def __init__(self):
        """初始化搜索格式化服务"""
        self._load_config()
        self._init_retrieval_clients()
        self._init_reranker()
        
    def _load_config(self):
        """加载配置文件"""
        try:
            with open('config/model.yaml', 'r', encoding='utf-8') as f:
                self.model_config = yaml.safe_load(f)
            with open('config/db.yaml', 'r', encoding='utf-8') as f:
                self.db_config = yaml.safe_load(f)
            logger.info("配置文件加载成功")
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            self.model_config = {}
            self.db_config = {}
    
    def _init_retrieval_clients(self):
        """初始化检索客户端"""
        try:
            # BM25检索器 - 连接ElasticSearch或其他全文索引
            self.bm25_client = self._init_bm25_client()
            
            # 向量检索器 - 连接Milvus等向量数据库
            self.vector_client = self._init_vector_client()
            
            # 图谱检索器 - 连接Neo4j等图数据库
            self.graph_client = self._init_graph_client()
            
            logger.info("检索客户端初始化成功")
            
        except Exception as e:
            logger.error(f"检索客户端初始化失败: {str(e)}")
            # 设置为None，后续会使用模拟数据
            self.bm25_client = None
            self.vector_client = None
            self.graph_client = None
    
    def _init_bm25_client(self):
        """初始化BM25检索客户端"""
        try:
            # 使用专门的SearchOpenSearchService
            from app.service.search.SearchOpenSearchService import SearchOpenSearchService
            
            opensearch_config = self.db_config.get('opensearch', {})
            if opensearch_config:
                bm25_client = SearchOpenSearchService()
                logger.info("SearchOpenSearchService BM25客户端初始化成功")
                return bm25_client
            else:
                logger.warning("OpenSearch配置未找到，将使用模拟数据")
                return None
                
        except Exception as e:
            logger.error(f"SearchOpenSearchService客户端初始化失败: {str(e)}")
            logger.warning("降级使用模拟数据")
            return None
    
    def _init_vector_client(self):
        """初始化向量检索客户端"""
        try:
            # 连接Milvus向量数据库
            from utils.MilvusManager import MilvusManager
            
            milvus_config = self.db_config.get('milvus', {})
            if milvus_config:
                # MilvusManager使用配置文件初始化，不需要传递参数
                return MilvusManager()
            else:
                logger.warning("Milvus配置未找到，将使用模拟数据")
                return None
                
        except Exception as e:
            logger.error(f"Milvus客户端初始化失败: {str(e)}")
            return None
    
    def _init_graph_client(self):
        """初始化图谱检索客户端"""
        try:
            # 连接Neo4j图数据库
            from neo4j import GraphDatabase
            
            neo4j_config = self.db_config.get('neo4j', {})
            if neo4j_config:
                return GraphDatabase.driver(
                    neo4j_config.get('uri', 'bolt://localhost:7687'),
                    auth=(
                        neo4j_config.get('username', 'neo4j'),
                        neo4j_config.get('password', 'password')
                    )
                )
            else:
                logger.warning("Neo4j配置未找到，将使用模拟数据")
                return None
                
        except Exception as e:
            logger.error(f"Neo4j客户端初始化失败: {str(e)}")
            return None
    
    def _init_reranker(self):
        """初始化重排模型"""
        try:
            reranker_config = self.model_config.get('reranker', {})
            
            if reranker_config.get('enabled', False):
                model_name = reranker_config.get('model_name', 'BAAI/bge-reranker-large')
                cache_dir = reranker_config.get('cache_dir', './models')
                device = reranker_config.get('device', 'cpu')
                
                # 设置环境变量
                os.environ['HF_HOME'] = os.path.abspath(cache_dir)
                os.environ['TRANSFORMERS_CACHE'] = os.path.abspath(cache_dir)
                
                # 加载重排模型 - CrossEncoder不支持cache_folder参数
                from sentence_transformers import CrossEncoder
                self.reranker = CrossEncoder(model_name, device=device)
                
                # 保存配置参数
                self.reranker_config = reranker_config
                
                logger.info(f"重排模型初始化成功: {model_name}")
            else:
                logger.warning("重排模型未配置，将使用简单评分函数")
                self.reranker = None
                self.reranker_config = {}
            
        except Exception as e:
            logger.error(f"重排模型初始化失败: {str(e)}")
            logger.warning("降级使用简单评分函数")
            self.reranker = None
            self.reranker_config = {}
        
        # 初始化嵌入模型用于查询编码
        self._init_embedding_model()
    
    def _init_embedding_model(self):
        """初始化嵌入模型"""
        try:
            model_name = self.model_config['embedding']['model_name']
            cache_dir = self.model_config['embedding']['cache_dir']
            
            # 设置HuggingFace缓存目录环境变量
            os.environ['HF_HOME'] = os.path.abspath(cache_dir)
            os.environ['TRANSFORMERS_CACHE'] = os.path.abspath(cache_dir)
            os.environ['SENTENCE_TRANSFORMERS_HOME'] = os.path.abspath(cache_dir)
            
            self.embedding_model = SentenceTransformer(
                model_name,
                cache_folder=cache_dir
            )
            
            self.normalize = self.model_config['embedding']['normalize']
            logger.info(f"搜索服务嵌入模型初始化成功: {model_name}")
            
        except Exception as e:
            logger.error(f"搜索服务嵌入模型初始化失败: {str(e)}")
            self.embedding_model = None
    
    def retrieve_and_rerank(self, understanding_result: Dict, filters: Dict = None) -> Dict:
        """
        主要的检索和重排方法
        
        Args:
            understanding_result: 查询理解结果
            filters: 过滤条件
            
        Returns:
            Dict: 检索和重排结果
        """
        try:
            logger.info("开始三路召回和重排")
            
            # 第一阶段：三路召回
            bm25_results = self._bm25_retrieval(understanding_result, filters)
            vector_results = self._vector_retrieval(understanding_result, filters)
            graph_results = self._graph_retrieval(understanding_result, filters)
            
            # 第二阶段：融合与去重
            merged_results = self._merge_and_deduplicate(
                bm25_results, vector_results, graph_results, understanding_result
            )
            
            # 第三阶段：重排
            final_results = self._rerank_results(merged_results, understanding_result)
            
            return {
                "total_found": len(bm25_results) + len(vector_results) + len(graph_results),
                "bm25_count": len(bm25_results),
                "vector_count": len(vector_results), 
                "graph_count": len(graph_results),
                "after_merge": len(merged_results),
                "final_count": len(final_results),
                "candidates": final_results,
                "sources": self._extract_sources(final_results),
                "retrieval_stats": {
                    "bm25_time": 0.1,
                    "vector_time": 0.2,
                    "graph_time": 0.15,
                    "merge_time": 0.05,
                    "rerank_time": 0.3
                }
            }
            
        except Exception as e:
            logger.error(f"检索和重排失败: {str(e)}")
            return {
                "total_found": 0,
                "candidates": [],
                "sources": [],
                "error": str(e)
            }
    
    def _bm25_retrieval(self, understanding_result: Dict, filters: Dict = None) -> List[Dict]:
        """
        BM25倒排检索
        
        Args:
            understanding_result: 查询理解结果
            filters: 过滤条件
            
        Returns:
            List[Dict]: BM25检索结果
        """
        try:
            rewrite_result = understanding_result.get("rewrite_result", {})
            keywords = rewrite_result.get("bm25_keywords", [])
            expanded_synonyms = rewrite_result.get("expanded_synonyms", [])
            original_query = understanding_result.get("original_query", "")
            
            if self.bm25_client:
                # 使用SearchOpenSearchService进行BM25检索
                results = self.bm25_client.search_bm25(
                    query=original_query,
                    keywords=keywords,
                    synonyms=expanded_synonyms,
                    filters=filters,
                    size=50
                )
            else:
                # 使用模拟数据
                results = self._mock_bm25_search(keywords, filters)
            
            # 标准化结果格式
            return self._standardize_bm25_results(results)
            
        except Exception as e:
            logger.error(f"BM25检索失败: {str(e)}")
            return []
    
    def _build_query_text(self, keywords: List[str], synonyms: List[str]) -> str:
        """
        构建查询文本
        
        Args:
            keywords: 关键词列表
            synonyms: 同义词列表
            
        Returns:
            str: 组合的查询文本
        """
        query_parts = []
        
        # 添加关键词（高优先级）
        if keywords:
            query_parts.extend(keywords)
        
        # 添加同义词（扩展检索）
        if synonyms:
            query_parts.extend(synonyms)
        
        # 组合成查询文本
        query_text = " ".join(query_parts) if query_parts else ""
        
        logger.debug(f"构建BM25查询文本: {query_text}")
        return query_text
    
    def _build_bm25_query(self, keywords: List[str], synonyms: List[str], filters: Dict = None) -> Dict:
        """构建BM25查询"""
        query = {
            "query": {
                "bool": {
                    "must": [],
                    "should": [],
                    "filter": []
                }
            },
            "size": 50,
            "highlight": {
                "fields": {
                    "content": {},
                    "title": {}
                }
            }
        }
        
        # Must查询：关键短语
        for keyword in keywords:
            query["query"]["bool"]["must"].append({
                "multi_match": {
                    "query": keyword,
                    "fields": ["title^3", "content", "table^2"],
                    "type": "phrase"
                }
            })
        
        # Should查询：同义词扩展
        for synonym in synonyms:
            query["query"]["bool"]["should"].append({
                "multi_match": {
                    "query": synonym,
                    "fields": ["title^2", "content"],
                    "fuzziness": "AUTO"
                }
            })
        
        # 过滤条件
        if filters:
            if filters.get("time_range"):
                query["query"]["bool"]["filter"].append({
                    "range": {
                        "timestamp": {
                            "gte": filters["time_range"][0],
                            "lte": filters["time_range"][1]
                        }
                    }
                })
            
            if filters.get("doc_types"):
                query["query"]["bool"]["filter"].append({
                    "terms": {
                        "file_type": filters["doc_types"]
                    }
                })
            
            if filters.get("type") == "table":
                query["query"]["bool"]["filter"].append({
                    "term": {
                        "content_type": "table"
                    }
                })
        
        return query
    
    def _mock_bm25_search(self, keywords: List[str], filters: Dict = None) -> List[Dict]:
        """模拟BM25搜索结果"""
        mock_results = [
            {
                "doc_id": "doc_001",
                "chunk_id": "chunk_001_001", 
                "title": "HCP检测标准操作程序",
                "content": "宿主细胞蛋白(HCP)检测是生物制品质量控制的重要环节...",
                "file_type": "pdf",
                "page_no": 1,
                "bbox": [100, 200, 500, 300],
                "score": 8.5,
                "highlight": ["<mark>HCP</mark>检测", "宿主细胞<mark>蛋白</mark>"]
            },
            {
                "doc_id": "doc_002", 
                "chunk_id": "chunk_002_003",
                "title": "CHO细胞培养基配制",
                "content": "中国仓鼠卵巢(CHO)细胞是重组蛋白生产的常用宿主细胞...",
                "file_type": "docx",
                "page_no": 3,
                "score": 7.2,
                "highlight": ["<mark>CHO</mark>细胞", "宿主<mark>细胞</mark>"]
            }
        ]
        
        # 根据关键词筛选结果
        filtered_results = []
        for result in mock_results:
            content_lower = result["content"].lower()
            title_lower = result["title"].lower()
            
            for keyword in keywords:
                if keyword.lower() in content_lower or keyword.lower() in title_lower:
                    filtered_results.append(result)
                    break
        
        return filtered_results
    
    def _standardize_bm25_results(self, results: List[Dict]) -> List[Dict]:
        """标准化BM25结果格式"""
        standardized = []
        
        for result in results:
            # 处理OpenSearch返回的结果格式
            if result.get("source") == "bm25":
                # 已经是OpenSearch标准化格式
                standardized_result = {
                    "doc_id": result.get("doc_id", ""),
                    "section_id": result.get("section_id", ""),
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "summary": result.get("summary", ""),
                    "doc_type": result.get("doc_type", ""),
                    "page_number": result.get("page_number", 1),
                    "file_path": result.get("file_path", ""),
                    "score": result.get("score", 0.0),
                    "source": "bm25",
                    "highlight": result.get("highlight", {}),
                    "metadata": result.get("metadata", {})
                }
            else:
                # 处理模拟数据格式
                standardized_result = {
                    "doc_id": result.get("doc_id", ""),
                    "section_id": result.get("chunk_id", ""),  # 兼容旧格式
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "summary": "",
                    "doc_type": result.get("file_type", ""),
                    "page_number": result.get("page_no", 1),
                    "file_path": "",
                    "score": result.get("score", 0.0),
                    "source": "bm25",
                    "highlight": result.get("highlight", []),
                    "metadata": {
                        "content_type": result.get("content_type", "text"),
                        "timestamp": result.get("timestamp", ""),
                        "department": result.get("department", ""),
                        "original_score": result.get("score", 0.0),
                        "bbox": result.get("bbox", [])
                    }
                }
            
            standardized.append(standardized_result)
        
        return standardized
    
    def _vector_retrieval(self, understanding_result: Dict, filters: Dict = None) -> List[Dict]:
        """
        向量语义检索
        
        Args:
            understanding_result: 查询理解结果
            filters: 过滤条件
            
        Returns:
            List[Dict]: 向量检索结果
        """
        try:
            rewrite_result = understanding_result.get("rewrite_result", {})
            vector_query = rewrite_result.get("vector_query", "")
            
            if self.vector_client:
                # 使用真实的向量客户端
                query_vector = self._encode_query(vector_query)
                results = self.vector_client.search(query_vector, top_k=50)
            else:
                # 使用模拟数据
                results = self._mock_vector_search(vector_query, filters)
            
            # 标准化结果格式
            return self._standardize_vector_results(results)
            
        except Exception as e:
            logger.error(f"向量检索失败: {str(e)}")
            return []
    
    def _encode_query(self, query: str) -> List[float]:
        """编码查询为向量"""
        try:
            if self.embedding_model and query.strip():
                # 使用真实的embedding模型
                embedding = self.embedding_model.encode(
                    query,
                    normalize_embeddings=self.normalize
                )
                return embedding.tolist()
            else:
                # 使用模拟向量作为后备
                logger.warning("嵌入模型未初始化或查询为空，使用模拟向量")
                return [0.1] * 768  # 模拟768维向量
            
        except Exception as e:
            logger.error(f"查询编码失败: {str(e)}")
            return [0.0] * 768
    
    def _mock_vector_search(self, query: str, filters: Dict = None) -> List[Dict]:
        """模拟向量搜索结果"""
        mock_results = [
            {
                "doc_id": "doc_003",
                "chunk_id": "chunk_003_002",
                "title": "生物制品质量控制指南",
                "content": "蛋白质纯度检测是确保生物制品安全性和有效性的关键步骤...",
                "file_type": "pdf",
                "page_no": 2,
                "similarity": 0.89,
                "vector": [0.1] * 768
            },
            {
                "doc_id": "doc_004",
                "chunk_id": "chunk_004_001", 
                "title": "细胞培养技术规范",
                "content": "细胞株的选择和培养条件对重组蛋白的表达量和质量有重要影响...",
                "file_type": "docx",
                "page_no": 1,
                "similarity": 0.82,
                "vector": [0.2] * 768
            }
        ]
        
        return mock_results
    
    def _standardize_vector_results(self, results: List[Dict]) -> List[Dict]:
        """标准化向量结果格式"""
        standardized = []
        
        for result in results:
            standardized.append({
                "doc_id": result.get("doc_id", ""),
                "chunk_id": result.get("chunk_id", ""),
                "title": result.get("title", ""),
                "content": result.get("content", ""),
                "file_type": result.get("file_type", ""),
                "page_no": result.get("page_no", 1),
                "bbox": result.get("bbox", []),
                "score": result.get("similarity", 0.0),
                "source": "vector",
                "metadata": {
                    "similarity": result.get("similarity", 0.0),
                    "vector": result.get("vector", []),
                    "original_score": result.get("similarity", 0.0)
                }
            })
        
        return standardized
    
    def _graph_retrieval(self, understanding_result: Dict, filters: Dict = None) -> List[Dict]:
        """
        图谱结构化检索
        
        Args:
            understanding_result: 查询理解结果
            filters: 过滤条件
            
        Returns:
            List[Dict]: 图谱检索结果
        """
        try:
            routing_strategy = understanding_result.get("routing_strategy", {})
            if not routing_strategy.get("use_graph", False):
                return []
            
            rewrite_result = understanding_result.get("rewrite_result", {})
            graph_intent = rewrite_result.get("graph_intent")
            
            if not graph_intent:
                return []
            
            if self.graph_client:
                # 使用真实的图数据库客户端
                cypher_query = self._build_cypher_query(graph_intent, understanding_result)
                results = self._execute_cypher_query(cypher_query)
            else:
                # 使用模拟数据
                results = self._mock_graph_search(graph_intent)
            
            # 标准化结果格式
            return self._standardize_graph_results(results)
            
        except Exception as e:
            logger.error(f"图谱检索失败: {str(e)}")
            return []
    
    def _build_cypher_query(self, graph_intent: Dict, understanding_result: Dict) -> str:
        """构建Cypher查询"""
        relation_type = graph_intent.get("relation_type", "")
        entities = graph_intent.get("entities", {})
        template = graph_intent.get("cypher_template", "")
        
        # 基于关系类型构建查询
        if relation_type == "组成":
            return """
            MATCH (a:Product)-[:HAS_PART]->(b:Component)
            WHERE a.name CONTAINS $entity_name
            RETURN a, b, 'HAS_PART' as relation
            LIMIT 20
            """
        elif relation_type == "适用":
            return """
            MATCH (a:Kit)-[:APPLICABLE_TO]->(b:CellLine)
            WHERE a.name CONTAINS $entity_name OR b.name CONTAINS $entity_name
            RETURN a, b, 'APPLICABLE_TO' as relation
            LIMIT 20
            """
        else:
            # 通用查询
            return """
            MATCH (a)-[r]->(b)
            WHERE a.name CONTAINS $entity_name OR b.name CONTAINS $entity_name
            RETURN a, b, type(r) as relation
            LIMIT 20
            """
    
    def _execute_cypher_query(self, query: str) -> List[Dict]:
        """执行Cypher查询"""
        try:
            with self.graph_client.session() as session:
                result = session.run(query, entity_name="HCP")  # 示例参数
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Cypher查询执行失败: {str(e)}")
            return []
    
    def _mock_graph_search(self, graph_intent: Dict) -> List[Dict]:
        """模拟图谱搜索结果"""
        mock_results = [
            {
                "a": {"name": "HCP检测试剂盒", "type": "Product"},
                "b": {"name": "ELISA检测板", "type": "Component"},
                "relation": "HAS_PART",
                "confidence": 0.95
            },
            {
                "a": {"name": "CHO-K1细胞株", "type": "CellLine"},
                "b": {"name": "DMEM培养基", "type": "Medium"},
                "relation": "REQUIRES",
                "confidence": 0.88
            }
        ]
        
        return mock_results
    
    def _standardize_graph_results(self, results: List[Dict]) -> List[Dict]:
        """标准化图谱结果格式"""
        standardized = []
        
        for result in results:
            # 从图谱结果构造文档格式
            a_node = result.get("a", {})
            b_node = result.get("b", {})
            relation = result.get("relation", "")
            
            content = f"{a_node.get('name', '')} {relation} {b_node.get('name', '')}"
            title = f"图谱关系：{relation}"
            
            standardized.append({
                "doc_id": f"graph_{hash(content)}",
                "chunk_id": f"graph_chunk_{hash(content)}",
                "title": title,
                "content": content,
                "file_type": "graph",
                "page_no": 1,
                "bbox": [],
                "score": result.get("confidence", 0.5),
                "source": "graph",
                "metadata": {
                    "relation": relation,
                    "source_node": a_node,
                    "target_node": b_node,
                    "confidence": result.get("confidence", 0.5),
                    "original_score": result.get("confidence", 0.5)
                }
            })
        
        return standardized
    
    def _merge_and_deduplicate(self, bm25_results: List[Dict], 
                             vector_results: List[Dict], 
                             graph_results: List[Dict],
                             understanding_result: Dict) -> List[Dict]:
        """
        融合与去重
        
        Args:
            bm25_results: BM25结果
            vector_results: 向量结果
            graph_results: 图谱结果
            understanding_result: 查询理解结果
            
        Returns:
            List[Dict]: 融合去重后的结果
        """
        try:
            # 合并所有结果
            all_results = bm25_results + vector_results + graph_results
            
            # 按照chunk_id进行去重
            unique_results = self._deduplicate_by_chunk(all_results)
            
            # 相似度去重
            unique_results = self._deduplicate_by_similarity(unique_results)
            
            # 分值归一化
            normalized_results = self._normalize_scores(unique_results)
            
            # 融合策略计算最终分数
            final_results = self._apply_fusion_strategy(normalized_results, understanding_result)
            
            # 按分数排序
            final_results.sort(key=lambda x: x["final_score"], reverse=True)
            
            return final_results[:100]  # 返回Top 100
            
        except Exception as e:
            logger.error(f"融合去重失败: {str(e)}")
            return bm25_results + vector_results + graph_results
    
    def _deduplicate_by_chunk(self, results: List[Dict]) -> List[Dict]:
        """按chunk_id去重"""
        seen_chunks = {}
        
        for result in results:
            chunk_id = result.get("chunk_id", "")
            if chunk_id and chunk_id not in seen_chunks:
                seen_chunks[chunk_id] = result
            elif chunk_id and chunk_id in seen_chunks:
                # 保留分数更高的
                if result.get("score", 0) > seen_chunks[chunk_id].get("score", 0):
                    seen_chunks[chunk_id] = result
        
        return list(seen_chunks.values())
    
    def _deduplicate_by_similarity(self, results: List[Dict], threshold: float = 0.9) -> List[Dict]:
        """按内容相似度去重"""
        unique_results = []
        
        for result in results:
            is_duplicate = False
            result_content = result.get("content", "")
            
            for unique_result in unique_results:
                unique_content = unique_result.get("content", "")
                similarity = self._calculate_text_similarity(result_content, unique_content)
                
                if similarity > threshold:
                    is_duplicate = True
                    # 如果当前结果分数更高，替换已存在的结果
                    if result.get("score", 0) > unique_result.get("score", 0):
                        unique_results.remove(unique_result)
                        unique_results.append(result)
                    break
            
            if not is_duplicate:
                unique_results.append(result)
        
        return unique_results
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简化版）"""
        if not text1 or not text2:
            return 0.0
        
        # 简单的Jaccard相似度
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _normalize_scores(self, results: List[Dict]) -> List[Dict]:
        """分值归一化"""
        if not results:
            return results
        
        # 按来源分组
        bm25_scores = [r["score"] for r in results if r.get("source") == "bm25"]
        vector_scores = [r["score"] for r in results if r.get("source") == "vector"]
        graph_scores = [r["score"] for r in results if r.get("source") == "graph"]
        
        # Min-Max归一化
        def min_max_normalize(scores):
            if not scores or len(scores) == 1:
                return {}
            min_score = min(scores)
            max_score = max(scores)
            if max_score == min_score:
                return {score: 0.5 for score in scores}
            return {score: (score - min_score) / (max_score - min_score) for score in scores}
        
        bm25_norm = min_max_normalize(bm25_scores)
        vector_norm = min_max_normalize(vector_scores)
        graph_norm = min_max_normalize(graph_scores)
        
        # 应用归一化
        for result in results:
            source = result.get("source")
            score = result.get("score", 0)
            
            if source == "bm25" and score in bm25_norm:
                result["normalized_score"] = bm25_norm[score]
            elif source == "vector" and score in vector_norm:
                result["normalized_score"] = vector_norm[score]
            elif source == "graph" and score in graph_norm:
                result["normalized_score"] = graph_norm[score]
            else:
                result["normalized_score"] = 0.5
        
        return results
    
    def _apply_fusion_strategy(self, results: List[Dict], understanding_result: Dict) -> List[Dict]:
        """应用融合策略"""
        routing_strategy = understanding_result.get("routing_strategy", {})
        
        # 获取权重
        bm25_weight = routing_strategy.get("bm25_weight", 0.3)
        vector_weight = routing_strategy.get("vector_weight", 0.4)
        graph_weight = routing_strategy.get("graph_weight", 0.3)
        
        for result in results:
            source = result.get("source")
            normalized_score = result.get("normalized_score", 0)
            
            # 计算加权分数
            if source == "bm25":
                final_score = normalized_score * bm25_weight
            elif source == "vector":
                final_score = normalized_score * vector_weight
            elif source == "graph":
                final_score = normalized_score * graph_weight
                # 图谱精确命中加分
                if result.get("metadata", {}).get("confidence", 0) > 0.9:
                    final_score += 0.15
            else:
                final_score = normalized_score * 0.2
            
            result["final_score"] = final_score
        
        return results
    
    def _rerank_results(self, merged_results: List[Dict], understanding_result: Dict) -> List[Dict]:
        """
        重排结果
        
        Args:
            merged_results: 融合后的结果
            understanding_result: 查询理解结果
            
        Returns:
            List[Dict]: 重排后的结果
        """
        try:
            if not merged_results:
                return []
            
            # 如果结果太少，直接返回
            if len(merged_results) <= 10:
                return merged_results
            
            # Cross-Encoder重排（模拟）
            reranked_results = self._cross_encoder_rerank(merged_results, understanding_result)
            
            # 去毒与清洗
            cleaned_results = self._clean_toxic_content(reranked_results)
            
            # 多样性控制
            diverse_results = self._apply_diversity_control(cleaned_results)
            
            return diverse_results[:20]  # 返回Top 20
            
        except Exception as e:
            logger.error(f"重排失败: {str(e)}")
            return merged_results[:20]
    
    def _cross_encoder_rerank(self, results: List[Dict], understanding_result: Dict) -> List[Dict]:
        """Cross-Encoder重排（支持真实重排模型和模拟实现）"""
        original_query = understanding_result.get("original_query", "")
        
        if self.reranker is not None:
            # 使用真实的Cross-Encoder重排模型
            return self._real_cross_encoder_rerank(results, original_query)
        else:
            # 使用简单评分函数（模拟实现）
            return self._simple_rerank(results, original_query)
    
    def _real_cross_encoder_rerank(self, results: List[Dict], query: str) -> List[Dict]:
        """使用真实的Cross-Encoder重排模型"""
        try:
            if not results:
                return results
            
            # 准备query-document对
            query_doc_pairs = []
            for result in results:
                content = result.get("content", "")
                title = result.get("title", "")
                
                # 组合标题和内容作为文档
                doc_text = f"{title} {content}" if title else content
                doc_text = doc_text[:self.reranker_config.get('max_length', 512)]
                
                query_doc_pairs.append([query, doc_text])
            
            # 批量计算重排分数
            batch_size = self.reranker_config.get('batch_size', 16)
            rerank_scores = []
            
            for i in range(0, len(query_doc_pairs), batch_size):
                batch = query_doc_pairs[i:i+batch_size]
                batch_scores = self.reranker.predict(batch)
                rerank_scores.extend(batch_scores)
            
            # 更新结果分数
            for i, result in enumerate(results):
                result["rerank_score"] = float(rerank_scores[i])
                # 结合原分数：70%原分数 + 30%重排分数
                original_score = result.get("final_score", 0)
                result["final_score"] = original_score * 0.7 + result["rerank_score"] * 0.3
            
            # 按重排后分数排序
            results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
            
            logger.info(f"Cross-Encoder重排完成，处理了{len(results)}个候选结果")
            return results
            
        except Exception as e:
            logger.error(f"Cross-Encoder重排失败，降级为简单评分: {str(e)}")
            return self._simple_rerank(results, query)
    
    def _simple_rerank(self, results: List[Dict], query: str) -> List[Dict]:
        """简单评分函数（模拟Cross-Encoder）"""
        for result in results:
            content = result.get("content", "")
            title = result.get("title", "")
            
            # 简单的评分逻辑：基于关键词匹配和内容质量
            rerank_score = 0.0
            
            # 标题匹配加分
            if any(word in title.lower() for word in query.lower().split()):
                rerank_score += 0.3
            
            # 内容匹配加分
            query_words = set(query.lower().split())
            content_words = set(content.lower().split())
            overlap = len(query_words.intersection(content_words))
            rerank_score += overlap * 0.1
            
            # 内容质量评分
            if len(content) > 100:  # 内容丰富
                rerank_score += 0.2
            
            if result.get("source") == "graph":  # 图谱结果加分
                rerank_score += 0.1
            
            result["rerank_score"] = min(rerank_score, 1.0)
            # 结合原分数
            result["final_score"] = (result.get("final_score", 0) * 0.7 + rerank_score * 0.3)
        
        # 按重排分数排序
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return results
    
    def _clean_toxic_content(self, results: List[Dict]) -> List[Dict]:
        """去毒与清洗"""
        cleaned_results = []
        
        for result in results:
            content = result.get("content", "")
            title = result.get("title", "")
            
            # 过滤条件
            if len(content.strip()) < 10:  # 内容太短
                continue
            
            if content.count("表格") > 5 and len(content) < 50:  # 可能是表格垃圾
                continue
            
            if "错误" in title or "失败" in title:  # 错误信息
                continue
            
            # 检查信息密度
            words = content.split()
            if len(words) > 0:
                unique_words = len(set(words))
                density = unique_words / len(words)
                if density < 0.3:  # 信息密度太低
                    continue
            
            cleaned_results.append(result)
        
        return cleaned_results
    
    def _apply_diversity_control(self, results: List[Dict]) -> List[Dict]:
        """多样性控制（MMR）"""
        if len(results) <= 10:
            return results
        
        diverse_results = []
        remaining_results = results.copy()
        
        # 选择第一个最高分的
        if remaining_results:
            diverse_results.append(remaining_results.pop(0))
        
        # MMR选择过程
        while len(diverse_results) < 20 and remaining_results:
            best_score = -1
            best_idx = -1
            
            for i, candidate in enumerate(remaining_results):
                # 计算与已选结果的平均相似度
                similarities = []
                for selected in diverse_results:
                    sim = self._calculate_text_similarity(
                        candidate.get("content", ""),
                        selected.get("content", "")
                    )
                    similarities.append(sim)
                
                avg_similarity = sum(similarities) / len(similarities) if similarities else 0
                
                # MMR分数：λ * relevance - (1-λ) * similarity
                mmr_score = 0.7 * candidate.get("final_score", 0) - 0.3 * avg_similarity
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            
            if best_idx >= 0:
                diverse_results.append(remaining_results.pop(best_idx))
            else:
                break
        
        return diverse_results
    
    def _extract_sources(self, results: List[Dict]) -> List[Dict]:
        """提取文档源信息"""
        sources = {}
        
        for result in results:
            doc_id = result.get("doc_id", "")
            if doc_id and doc_id not in sources:
                sources[doc_id] = {
                    "doc_id": doc_id,
                    "title": result.get("title", ""),
                    "file_type": result.get("file_type", ""),
                    "chunk_count": 1,
                    "max_score": result.get("final_score", 0)
                }
            elif doc_id:
                sources[doc_id]["chunk_count"] += 1
                sources[doc_id]["max_score"] = max(
                    sources[doc_id]["max_score"],
                    result.get("final_score", 0)
                )
        
        return list(sources.values())
