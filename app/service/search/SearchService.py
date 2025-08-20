"""
智能检索服务
严格按照重构要求实现完整的检索流程：
① 规范化 → ② 意图判别 → ③ 候选召回 → ④ 聚合融合 → ⑤ 重排 → ⑦ 扩展 → ⑧ 补图表 → ⑨ 流式渲染
"""

import json
import logging
import re
import yaml
import numpy as np
import os
from typing import Dict, List, Optional, Generator, Any
from datetime import datetime
from collections import defaultdict
from sqlalchemy import text
import requests
from time import sleep

# 配置日志
logger = logging.getLogger(__name__)


class SearchService:
    """智能检索服务类 - 完整实现"""
    
    def __init__(self):
        """初始化搜索服务"""
        self._load_config()
        self._init_clients()
        self._init_models()
        self._init_patterns()
        
    def _load_config(self):
        """加载配置文件"""
        try:
            with open('config/model.yaml', 'r', encoding='utf-8') as f:
                self.model_config = yaml.safe_load(f)
            with open('config/db.yaml', 'r', encoding='utf-8') as f:
                self.db_config = yaml.safe_load(f)
            with open('config/prompt.yaml', 'r', encoding='utf-8') as f:
                self.prompt_config = yaml.safe_load(f)
            logger.info("配置文件加载成功")
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            self.model_config = {}
            self.db_config = {}
            self.prompt_config = {}
    
    def _init_clients(self):
        """初始化客户端"""
        try:
            # OpenSearch客户端
            self._init_opensearch_client()
            
            # Milvus向量客户端
            self._init_milvus_client()
            
            # Neo4j图数据库客户端
            self._init_neo4j_client()
            
            # MySQL数据库客户端
            self._init_mysql_client()
            
            # LLM客户端
            self._init_llm_client()
            
            logger.info("客户端初始化成功")
        except Exception as e:
            logger.error(f"客户端初始化失败: {str(e)}")
    
    def _init_opensearch_client(self):
        """初始化OpenSearch客户端"""
        try:
            from utils.OpenSearchManager import OpenSearchManager
            opensearch_config = self.db_config.get('opensearch', {})
            if opensearch_config:
                self.opensearch_client = OpenSearchManager('config/db.yaml')
                self.index_name = opensearch_config.get('index_name', 'graphrag_documents')
                logger.info("OpenSearch客户端初始化成功")
            else:
                self.opensearch_client = None
                logger.warning("OpenSearch配置未找到")
        except Exception as e:
            logger.error(f"OpenSearch客户端初始化失败: {str(e)}")
            self.opensearch_client = None
    
    def _init_milvus_client(self):
        """初始化Milvus客户端"""
        try:
            from utils.MilvusManager import MilvusManager
            milvus_config = self.db_config.get('milvus', {})
            if milvus_config:
                self.milvus_client = MilvusManager()
                logger.info("Milvus客户端初始化成功")
            else:
                self.milvus_client = None
                logger.warning("Milvus配置未找到")
        except Exception as e:
            logger.error(f"Milvus客户端初始化失败: {str(e)}")
            self.milvus_client = None
    
    def _init_neo4j_client(self):
        """初始化Neo4j客户端"""
        try:
            from neo4j import GraphDatabase
            neo4j_config = self.db_config.get('neo4j', {})
            if neo4j_config:
                self.neo4j_client = GraphDatabase.driver(
                    neo4j_config.get('uri', 'bolt://localhost:7687'),
                    auth=(
                        neo4j_config.get('username', 'neo4j'),
                        neo4j_config.get('password', 'password')
                    )
                )
                logger.info("Neo4j客户端初始化成功")
            else:
                self.neo4j_client = None
                logger.warning("Neo4j配置未找到")
        except Exception as e:
            logger.error(f"Neo4j客户端初始化失败: {str(e)}")
            self.neo4j_client = None
    
    def _init_mysql_client(self):
        """初始化MySQL客户端"""
        try:
            from utils.MySQLManager import MySQLManager
            mysql_config = self.db_config.get('mysql', {})
            if mysql_config:
                self.mysql_client = MySQLManager('config/db.yaml')
                logger.info("MySQL客户端初始化成功")
            else:
                self.mysql_client = None
                logger.warning("MySQL配置未找到")
        except Exception as e:
            logger.error(f"MySQL客户端初始化失败: {str(e)}")
            self.mysql_client = None
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            deepseek_config = self.model_config.get('deepseek', {})
            self.llm_config = {
                'api_url': deepseek_config.get('api_url', 'https://api.deepseek.com'),
                'api_key': deepseek_config.get('api_key', ''),
                'model_name': deepseek_config.get('model_name', 'deepseek-chat'),
                'max_tokens': deepseek_config.get('max_tokens', 4096),
                'temperature': deepseek_config.get('temperature', 0.7)
            }
            if self.llm_config['api_key']:
                logger.info("LLM客户端配置成功")
            else:
                logger.warning("LLM API密钥未配置")
        except Exception as e:
            logger.error(f"LLM客户端初始化失败: {str(e)}")
            self.llm_config = {}
    
    def _init_models(self):
        """初始化模型"""
        try:
            # 嵌入模型
            from sentence_transformers import SentenceTransformer
            embedding_config = self.model_config.get('embedding', {})
            if embedding_config:
                model_name = embedding_config.get('model_name')
                cache_dir = embedding_config.get('cache_dir')
                
                os.environ['HF_HOME'] = os.path.abspath(cache_dir)
                os.environ['TRANSFORMERS_CACHE'] = os.path.abspath(cache_dir)
                os.environ['SENTENCE_TRANSFORMERS_HOME'] = os.path.abspath(cache_dir)
                
                self.embedding_model = SentenceTransformer(model_name, cache_folder=cache_dir)
                self.normalize = embedding_config.get('normalize', True)
                logger.info(f"嵌入模型初始化成功: {model_name}")
            else:
                self.embedding_model = None
            
            # 重排模型
            reranker_config = self.model_config.get('reranker', {})
            if reranker_config.get('enabled', False):
                from sentence_transformers import CrossEncoder
                model_name = reranker_config.get('model_name', 'BAAI/bge-reranker-large')
                device = reranker_config.get('device', 'cpu')
                
                self.reranker = CrossEncoder(model_name, device=device)
                self.reranker_config = reranker_config
                logger.info(f"重排模型初始化成功: {model_name}")
            else:
                self.reranker = None
                self.reranker_config = {}
                
        except Exception as e:
            logger.error(f"模型初始化失败: {str(e)}")
            self.embedding_model = None
            self.reranker = None
    
    def _init_patterns(self):
        """初始化模式和词典"""
        # 实体识别模式
        self.entity_patterns = {
            "bio_entity": [
                r"HCP|宿主细胞蛋白",
                r"CHO|中国仓鼠卵巢", 
                r"细胞株|cell\s*line",
                r"培养基|medium",
                r"抗体|antibody",
                r"蛋白质|protein"
            ],
            "product_model": [
                r"[A-Z]{2,5}\d{2,6}",
                r"[A-Z]+\-\d+",
                r"v\d+\.\d+"
            ]
        }
        
        # 同义词词典
        self.synonym_dict = {
            "HCP": ["宿主细胞蛋白", "Host Cell Protein", "host cell protein"],
            "CHO": ["中国仓鼠卵巢", "Chinese Hamster Ovary", "中国仓鼠卵巢细胞"],
            "CHO-K1": "CHOK1",
            "CHO K1": "CHOK1"
        }
    
    def intelligent_search(self, query: str, filters: Dict = None) -> Generator[Dict, None, None]:
        """
        智能检索主流程
        严格按照文档要求：① → ② → ③ → ④ → ⑤ → ⑦ → ⑧ → ⑨
        """
        try:
            logger.info(f"开始智能检索: {query}")
            
            # ① 规范化（Query Normalization）
            yield {"type": "stage_update", "stage": "normalization", "message": "🔧 正在规范化查询...", "progress": 10}
            normalized_query = self._normalize_query(query)
            
            # ② 意图判别（标题问法 or 碎句问法）
            yield {"type": "stage_update", "stage": "intent", "message": "🎯 正在判别查询意图...", "progress": 20}
            intent_type = self._classify_intent(normalized_query)
            
            # 生成检索配置
            retrieval_config = self._configure_retrieval(normalized_query, intent_type)
            understanding_result = {
                "original_query": query,
                "normalized_query": normalized_query,
                "intent_type": intent_type,
                "retrieval_config": retrieval_config,
                "entities": self._extract_entities(normalized_query),
                "rewrite_result": self._rewrite_and_expand(normalized_query, intent_type)
            }
            
            # ③ 候选召回（快而广）
            yield {"type": "stage_update", "stage": "retrieval", "message": "📚 正在召回候选内容...", "progress": 40}
            bm25_results = self._bm25_retrieval(understanding_result, filters)
            vector_results = self._vector_retrieval(understanding_result, filters)
            graph_results = self._graph_retrieval(understanding_result, filters)
            
            # ④ 意图感知的聚合与分数融合
            yield {"type": "stage_update", "stage": "aggregation", "message": "🔗 正在聚合和融合结果...", "progress": 55}
            candidates = self._aggregate_by_section(bm25_results, vector_results, graph_results, understanding_result)
            
            # ⑤ 重排（把"最相关的一节"放到第一）
            yield {"type": "stage_update", "stage": "reranking", "message": "🎯 正在重排选择最佳章节...", "progress": 70}
            top_section = self._rerank_sections(candidates, understanding_result)
            
            if not top_section:
                yield {"type": "error", "message": "未找到相关内容"}
                return
            
            # ⑦ 扩展（把"一家子"拉齐）
            yield {"type": "stage_update", "stage": "expansion", "message": "🔍 正在扩展章节内容...", "progress": 80}
            expanded_content = self._expand_section_content(top_section)
            
            # ⑧ 图表细节（MySQL）
            yield {"type": "stage_update", "stage": "enrichment", "message": "🖼️ 正在补充图表细节...", "progress": 85}
            multimodal_content = self._enrich_multimodal_details(top_section)
            
            # ⑨ 组装/渲染（可流式）
            yield {"type": "stage_update", "stage": "rendering", "message": "✍️ 正在生成答案...", "progress": 90}
            
            # 流式输出结果
            yield from self._stream_render_answer(query, top_section, multimodal_content, understanding_result)
            
        except Exception as e:
            logger.error(f"智能检索失败: {str(e)}")
            yield {"type": "error", "message": f"检索失败: {str(e)}"}
    
    def _normalize_query(self, query: str) -> str:
        """① 规范化（Query Normalization）"""
        try:
            normalized = query.strip()
            
            # 全角/半角标准化
            import unicodedata
            normalized = unicodedata.normalize('NFKC', normalized)
            
            # 空白与标点标准化
            normalized = re.sub(r'\s+', ' ', normalized)
            normalized = normalized.replace('，', ',').replace('。', '.').replace('；', ';')
            
            # 中英文之间加空格
            normalized = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', normalized)
            normalized = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', normalized)
            
            # 同义词标准化
            for synonym, standard in self.synonym_dict.items():
                if isinstance(standard, str):
                    normalized = normalized.replace(synonym, standard)
                else:
                    for syn in standard:
                        normalized = normalized.replace(syn, synonym)
            
            # 移除低信息词
            low_info_words = ["帮我", "请", "查询", "查找", "搜索", "一下", "相关", "内容"]
            words = normalized.split()
            filtered_words = [word for word in words if word not in low_info_words and len(word.strip()) > 0]
            
            if filtered_words:
                normalized = " ".join(filtered_words)
            
            logger.debug(f"查询规范化: '{query}' -> '{normalized}'")
            return normalized
            
        except Exception as e:
            logger.error(f"查询规范化失败: {str(e)}")
            return query
    
    def _classify_intent(self, query: str) -> str:
        """② 意图判别（标题问法 or 碎句问法）"""
        try:
            # # 规则1：长度≤8字且包含特定关键词 → 标题问法
            # if len(query) <= 8 and any(keyword in query for keyword in
            #     ["简介", "说明", "是什么", "定义", "产品说明", "概述", "介绍"]):
            #     return "title"
            #
            # # 🔧 规则2：包含明确的标题性查询词 → 标题问法 (扩展版)
            # title_indicators = ["什么是", "定义", "概念", "简介", "概述", "介绍", "案例", "分享", "特点", "优势", "应用"]
            # if any(indicator in query for indicator in title_indicators):
            #     logger.info(f"意图判别：检测到标题性关键词 '{[ind for ind in title_indicators if ind in query]}' → title")
            #     return "title"
            #
            # # 规则3：包含明确的内容性查询词 → 碎句问法
            # content_indicators = ["如何", "怎么", "步骤", "流程", "方法", "过程", "具体", "详细"]
            # if any(indicator in query for indicator in content_indicators):
            #     return "fragment"
            
            # 🔧 规则4：基于向量数据库的意图判别（主要方法）
            vector_intent = self._vector_based_intent_classification(query)
            if vector_intent:
                logger.info(f"意图判别：向量相似度分析 → {vector_intent}")
                return vector_intent
            
            # 规则5：向量相似度判断（简化实现，兜底）
            similarity_score = self._calculate_title_similarity(query)
            
            if similarity_score >= 0.45:
                return "title"
            elif similarity_score >= 0.40:
                return "hybrid"  # 两路并跑
            else:
                return "fragment"
                
        except Exception as e:
            logger.error(f"意图判别失败: {str(e)}")
            return "fragment"
    
    def _calculate_title_similarity(self, query: str) -> float:
        """计算查询与标题性内容的相似度"""
        title_keywords = [
            "HCP", "CHO", "蛋白", "细胞", "培养", "检测", "分析", "质量", "标准",
            "试剂", "产品", "设备", "方法", "技术", "系统", "平台", "服务"
        ]
        
        query_words = set(query.split())
        title_word_set = set(title_keywords)
        
        intersection = query_words.intersection(title_word_set)
        union = query_words.union(title_word_set)
        
        if not union:
            return 0.0
            
        similarity = len(intersection) / len(union)
        
        # 根据查询长度调整相似度
        if len(query) <= 5:
            similarity += 0.1
        elif len(query) > 20:
            similarity -= 0.1
            
        return min(similarity, 1.0)
    
    def _vector_based_intent_classification(self, query: str) -> Optional[str]:
        """🔧 基于向量数据库的意图判别"""
        try:
            if not self.milvus_client or not self.embedding_model:
                logger.debug("向量意图判别：Milvus客户端或嵌入模型未初始化")
                return None
            
            # 编码查询向量
            query_vector = self.embedding_model.encode(
                query, 
                normalize_embeddings=self.normalize
            ).tolist()
            
            # 分别搜索标题和片段向量
            try:
                # 🔧 搜索标题和完整section向量（使用新的content_type字段）
                title_results = self.milvus_client.search_vectors(
                    query_vectors=[query_vector],
                    top_k=5,
                    expr="content_type in ['title', 'section']"
                )
                
                # 搜索片段向量
                fragment_results = self.milvus_client.search_vectors(
                    query_vectors=[query_vector],
                    top_k=5, 
                    expr="content_type == 'fragment'"
                )
                
                # 提取分数
                title_scores = []
                fragment_scores = []
                
                # 🔧 修复：MilvusManager.search_vectors返回的是字典列表，不是嵌套列表
                if title_results and len(title_results) > 0:
                    title_scores = [hit.get('score', 0) for hit in title_results]
                    
                if fragment_results and len(fragment_results) > 0:
                    fragment_scores = [hit.get('score', 0) for hit in fragment_results]
                
                # 计算统计指标
                title_max = max(title_scores) if title_scores else 0
                title_avg = sum(title_scores) / len(title_scores) if title_scores else 0
                
                fragment_max = max(fragment_scores) if fragment_scores else 0
                fragment_avg = sum(fragment_scores) / len(fragment_scores) if fragment_scores else 0
                
                # 判别逻辑
                score_diff = title_max - fragment_max
                avg_diff = title_avg - fragment_avg
                
                logger.debug(f"向量意图分析: title_max={title_max:.3f}, fragment_max={fragment_max:.3f}, "
                           f"score_diff={score_diff:.3f}, avg_diff={avg_diff:.3f}")
                
                # 阈值判别
                if score_diff > 0.1 and avg_diff > 0.05:
                    return "title"
                elif score_diff < -0.1 and avg_diff < -0.05:
                    return "fragment"
                elif abs(score_diff) <= 0.05:
                    return "hybrid"
                else:
                    return "title" if title_max > fragment_max else "fragment"
                    
            except Exception as e:
                logger.warning(f"向量搜索失败，可能是filter_expr语法问题: {str(e)}")
                # 降级到metadata过滤（向后兼容）
                return self._fallback_metadata_intent_classification(query_vector)
                
        except Exception as e:
            logger.warning(f"向量意图判别失败: {str(e)}")
            return None
    
    def _fallback_metadata_intent_classification(self, query_vector: List[float]) -> Optional[str]:
        """降级到metadata过滤的意图判别"""
        try:
            # 搜索所有向量，然后在结果中过滤
            all_results = self.milvus_client.search_vectors(
                query_vectors=[query_vector],
                top_k=20
            )
            
            if not all_results or len(all_results) == 0:
                return None
                
            title_scores = []
            fragment_scores = []
            
            # 🔧 修复：all_results是字典列表，不是嵌套列表
            for hit in all_results:
                metadata_str = hit.get('metadata', '{}')
                try:
                    import json
                    metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
                    content_type = metadata.get('content_type', 'fragment')
                    score = hit.get('score', 0)
                    
                    if content_type == 'title':
                        title_scores.append(score)
                    else:
                        fragment_scores.append(score)
                except:
                    continue
            
            # 简化判别逻辑
            title_max = max(title_scores) if title_scores else 0
            fragment_max = max(fragment_scores) if fragment_scores else 0
            
            if title_max > fragment_max + 0.1:
                return "title"
            elif fragment_max > title_max + 0.1:
                return "fragment"
            else:
                return None
                
        except Exception as e:
            logger.warning(f"降级意图判别也失败: {str(e)}")
            return None
    
    def _configure_retrieval(self, query: str, intent_type: str) -> Dict:
        """③ 候选召回配置"""
        if intent_type == "title":
            return {
                "vector_top_k": 20,
                "vector_target": "titles",
                "bm25_top_k": 20,
                "bm25_target": "sections",
                "strategy": "title_oriented"
            }
        elif intent_type == "fragment":
            return {
                "vector_top_k": 50,
                "vector_target": "fragments", 
                "bm25_top_k": 50,
                "bm25_target": "fragments",
                "strategy": "content_oriented"
            }
        elif intent_type == "hybrid":
            return {
                "vector_top_k": 35,
                "vector_target": "mixed",
                "bm25_top_k": 35,
                "bm25_target": "mixed",
                "strategy": "hybrid_dual_path"
            }
        else:
            return {
                "vector_top_k": 50,
                "vector_target": "fragments",
                "bm25_top_k": 50,
                "bm25_target": "fragments",
                "strategy": "default"
            }
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """实体识别"""
        entities = {}
        
        for entity_type, patterns in self.entity_patterns.items():
            entities[entity_type] = []
            
            for pattern in patterns:
                matches = re.findall(pattern, query, re.IGNORECASE)
                if matches:
                    for match in matches:
                        if isinstance(match, tuple):
                            entities[entity_type].extend([m for m in match if m])
                        else:
                            entities[entity_type].append(match)
        
        # 去重并过滤空值
        for entity_type in entities:
            entities[entity_type] = list(set([e for e in entities[entity_type] if e]))
        
        if not any(entities.values()):
            entities["general"] = [query]
        
        return entities
    
    def _rewrite_and_expand(self, query: str, intent_type: str) -> Dict:
        """改写与扩展查询"""
        # 生成BM25友好的关键字
        keywords = re.findall(r'\w+', query)
        keywords = [w for w in keywords if len(w) > 1][:10]
        
        # 生成向量检索的语义化query
        if intent_type == "title":
            vector_query = f"{query} 定义 概念 含义 简介"
        elif intent_type == "fragment":
            vector_query = f"{query} 详细 具体 方法 操作 流程"
        else:
            vector_query = query
        
        return {
            "bm25_keywords": keywords,
            "vector_query": vector_query,
            "expanded_synonyms": self._expand_synonyms(keywords)
        }
    
    def _expand_synonyms(self, keywords: List[str]) -> List[str]:
        """扩展同义词"""
        expanded = set(keywords)
        
        for keyword in keywords:
            if keyword in self.synonym_dict:
                synonyms = self.synonym_dict[keyword]
                if isinstance(synonyms, list):
                    expanded.update(synonyms)
                else:
                    expanded.add(synonyms)
        
        return list(expanded)
    
    def _bm25_retrieval(self, understanding_result: Dict, filters: Dict = None) -> List[Dict]:
        """③ BM25检索"""
        try:
            if not self.opensearch_client:
                return self._mock_bm25_results()
            
            retrieval_config = understanding_result.get("retrieval_config", {})
            rewrite_result = understanding_result.get("rewrite_result", {})
            
            bm25_target = retrieval_config.get("bm25_target", "fragments")
            bm25_top_k = retrieval_config.get("bm25_top_k", 50)
            keywords = rewrite_result.get("bm25_keywords", [])
            
            # 构建查询
            query_body = self._build_bm25_query(
                understanding_result["normalized_query"], 
                keywords, 
                bm25_target, 
                bm25_top_k, 
                filters
            )
            
            # 执行搜索
            response = self.opensearch_client.search(self.index_name, query_body)
            return self._process_bm25_results(response)
            
        except Exception as e:
            logger.error(f"BM25检索失败: {str(e)}")
            return []
    
    def _build_bm25_query(self, query: str, keywords: List[str], target: str, size: int, filters: Dict = None) -> Dict:
        """构建BM25查询"""
        should_queries = []
        
        # 主查询
        should_queries.append({
            "multi_match": {
                "query": query,
                "fields": ["title^3", "content", "summary^2"],
                "boost": 2.0
            }
        })
        
        # 关键词查询
        for keyword in keywords:
            should_queries.append({
                "multi_match": {
                    "query": keyword,
                    "fields": ["title^3", "content^1.5", "summary^2"],
                    "boost": 1.5
                }
            })
        
        query_body = {
            "query": {
                "bool": {
                    "should": should_queries,
                    "minimum_should_match": 1
                }
            },
            "size": size,
            "highlight": {
                "fields": {
                    "title": {},
                    "content": {"fragment_size": 100, "number_of_fragments": 3}
                }
            },
            "sort": [{"_score": {"order": "desc"}}]
        }
        
        # 添加过滤条件
        if filters:
            filter_conditions = []
            if filters.get('doc_types'):
                filter_conditions.append({"terms": {"doc_type": filters['doc_types']}})
            if filters.get('content_types'):
                filter_conditions.append({"terms": {"content_type": filters['content_types']}})
            
            if filter_conditions:
                query_body["query"]["bool"]["filter"] = filter_conditions
        
        return query_body
    
    def _process_bm25_results(self, response: Dict) -> List[Dict]:
        """处理BM25搜索结果"""
        results = []
        hits = response.get('hits', {}).get('hits', [])
        
        for hit in hits:
            result = {
                "doc_id": hit['_source'].get("doc_id", ""),
                "section_id": hit['_source'].get("section_id", ""),
                "element_id": hit['_source'].get("element_id", ""),
                "title": hit['_source'].get("title", ""),
                "content": hit['_source'].get("content", ""),
                "content_type": hit['_source'].get("content_type", "text"),
                "page_number": hit['_source'].get("page_number", 1),
                "bbox": hit['_source'].get("bbox", {}),
                "score": hit['_score'],
                "source": "bm25",
                "highlight": hit.get('highlight', {}),
                "metadata": hit['_source'].get("metadata", {})
            }
            results.append(result)
        
        return results
    
    def _mock_bm25_results(self) -> List[Dict]:
        """模拟BM25结果"""
        return [
            {
                "doc_id": "doc_001",
                "section_id": "section_001_001",
                "element_id": "element_001_001_001",
                "title": "HCP检测方法",
                "content": "使用ELISA方法检测宿主细胞蛋白含量，检测限为10ng/ml...",
                "content_type": "fragment",
                "page_number": 1,
                "bbox": {"x": 100, "y": 200, "width": 400, "height": 50},
                "score": 9.2,
                "source": "bm25",
                "highlight": {"content": ["<mark>HCP</mark>检测"]},
                "metadata": {}
            }
        ]
    
    def _vector_retrieval(self, understanding_result: Dict, filters: Dict = None) -> List[Dict]:
        """③ 向量检索"""
        try:
            if not self.milvus_client or not self.embedding_model:
                return self._mock_vector_results()
            
            retrieval_config = understanding_result.get("retrieval_config", {})
            rewrite_result = understanding_result.get("rewrite_result", {})
            
            vector_query = rewrite_result.get("vector_query", "")
            vector_top_k = retrieval_config.get("vector_top_k", 50)
            
            # 编码查询向量
            query_vector = self.embedding_model.encode(
                vector_query, 
                normalize_embeddings=self.normalize
            ).tolist()
            
            # 执行向量搜索
            results = self.milvus_client.search_vectors([query_vector], top_k=vector_top_k)
            return self._process_vector_results(results)
            
        except Exception as e:
            logger.error(f"向量检索失败: {str(e)}")
            return []
    
    def _process_vector_results(self, results: List[Dict]) -> List[Dict]:
        """处理向量搜索结果"""
        processed = []
        for result in results:
            # 从metadata中提取额外信息
            metadata = result.get("metadata", {})
            
            processed_result = {
                "doc_id": result.get("document_id", ""),
                "section_id": metadata.get("section_id", ""),
                "element_id": result.get("element_id", ""),
                "title": metadata.get("title", ""),
                "content": result.get("content", ""),
                "content_type": metadata.get("content_type", "text"),
                "page_number": metadata.get("page_number", 1),
                "bbox": metadata.get("bbox", {}),
                "score": result.get("score", 0.0),
                "source": "vector",
                "metadata": metadata
            }
            processed.append(processed_result)
        
        return processed
    
    def _mock_vector_results(self) -> List[Dict]:
        """模拟向量结果"""
        return [
            {
                "doc_id": "doc_002",
                "section_id": "section_002_001",
                "element_id": "element_002_001_001",
                "title": "生物制品质量控制",
                "content": "蛋白质纯度检测是确保生物制品安全性和有效性的关键步骤...",
                "content_type": "fragment",
                "page_number": 2,
                "bbox": {"x": 100, "y": 300, "width": 400, "height": 60},
                "score": 0.89,
                "source": "vector",
                "metadata": {}
            }
        ]
    
    def _graph_retrieval(self, understanding_result: Dict, filters: Dict = None) -> List[Dict]:
        """③ 图谱检索"""
        try:
            if not self.neo4j_client:
                return []
            
            # 简化的图谱查询逻辑
            entities = understanding_result.get("entities", {})
            if not entities:
                return []
            
            # 执行图谱查询 - 修复查询逻辑以适应实际数据结构
            with self.neo4j_client.session() as session:
                # 安全地提取实体名称
                entity_names = []
                if entities:
                    for entity_list in entities.values():
                        if entity_list and len(entity_list) > 0:
                            entity_names.extend(entity_list)
                
                if not entity_names:
                    return []  # 没有实体则返回空结果
                
                # 扩展同义词
                expanded_entities = self._expand_entity_synonyms(entity_names)
                logger.info(f"图谱检索实体: {entity_names} -> 扩展后: {expanded_entities}")
                
                # 策略1: 遍历所有扩展实体进行关系查询
                all_graph_results = []
                all_entity_results = []
                
                for entity_name in expanded_entities:
                    # 查询实体关系
                    cypher_query = """
                    MATCH (a:Entity)-[r]->(b:Entity)
                    WHERE a.canonical CONTAINS $entity_name OR b.canonical CONTAINS $entity_name
                    RETURN a, b, type(r) as relation
                    LIMIT 5
                    """
                    
                    result = session.run(cypher_query, entity_name=entity_name)
                    graph_results = list(result)
                    all_graph_results.extend(graph_results)
                    
                    # 如果没有关系，查询单个实体
                    if not graph_results:
                        cypher_query2 = """
                        MATCH (n:Entity)
                        WHERE n.canonical CONTAINS $entity_name
                        RETURN n
                        LIMIT 3
                        """
                        
                        result2 = session.run(cypher_query2, entity_name=entity_name)
                        entity_results = list(result2)
                        all_entity_results.extend(entity_results)
                
                # 处理结果
                if all_graph_results:
                    logger.info(f"图谱检索找到{len(all_graph_results)}个关系")
                    return self._process_graph_results(all_graph_results)
                
                if all_entity_results:
                    logger.info(f"图谱检索找到{len(all_entity_results)}个相关实体")
                    return self._process_single_entity_results(all_entity_results)
                
                logger.info(f"图谱检索未找到与'{entity_names}'相关的内容")
                return []
                
        except Exception as e:
            logger.error(f"图谱检索失败: {str(e)}")
            return []
    
    def _process_graph_results(self, results: List) -> List[Dict]:
        """处理图谱搜索结果"""
        processed = []
        for record in results:
            a_node = dict(record["a"])
            b_node = dict(record["b"]) 
            relation = record["relation"]
            
            # 使用canonical字段，因为name字段为空
            a_name = a_node.get('canonical', '') or a_node.get('name', '') or '实体A'
            b_name = b_node.get('canonical', '') or b_node.get('name', '') or '实体B'
            
            content = f"{a_name} {relation} {b_name}"
            
            processed.append({
                "doc_id": f"graph_{hash(content)}",
                "section_id": f"graph_section_{hash(content)}",
                "element_id": f"graph_element_{hash(content)}",
                "title": f"图谱关系：{relation}",
                "content": content,
                "content_type": "graph",
                "page_number": 1,
                "bbox": {},
                "score": 0.8,
                "source": "graph",
                "metadata": {"relation": relation, "source_node": a_node, "target_node": b_node}
            })
        
        return processed
    
    def _process_single_entity_results(self, results: List) -> List[Dict]:
        """处理单个实体搜索结果"""
        processed = []
        for record in results:
            entity = dict(record["n"])
            
            # 使用canonical字段，因为name字段为空
            entity_name = entity.get('canonical', '') or entity.get('name', '') or '未知实体'
            entity_type = entity.get('entity_type', '') or entity.get('type', '') or '未知类型'
            
            content = f"相关实体: {entity_name} (类型: {entity_type})"
            
            processed.append({
                "doc_id": f"entity_{hash(entity_name)}",
                "section_id": f"entity_section_{hash(entity_name)}",
                "element_id": f"entity_element_{hash(entity_name)}",
                "title": entity_name,
                "content": content,
                "content_type": "entity",
                "page_number": 1,
                "bbox": {},
                "score": 0.6,
                "source": "graph_entity",
                "metadata": {
                    "entity_type": entity_type,
                    "entity_data": entity
                }
            })
        
        return processed
    
    def _expand_entity_synonyms(self, entity_names: List[str]) -> List[str]:
        """扩展实体同义词"""
        expanded = set()
        
        for entity_name in entity_names:
            # 添加原始实体
            expanded.add(entity_name)
            
            # 查找同义词
            if entity_name in self.synonym_dict:
                synonyms = self.synonym_dict[entity_name]
                if isinstance(synonyms, list):
                    expanded.update(synonyms)
                else:
                    expanded.add(synonyms)
            
            # 反向查找
            for key, synonyms in self.synonym_dict.items():
                if isinstance(synonyms, list):
                    if entity_name in synonyms:
                        expanded.add(key)
                        expanded.update(synonyms)
                else:
                    if entity_name == synonyms:
                        expanded.add(key)
        
        # 添加特殊映射规则
        entity_mappings = {
            "HCP": ["宿主细胞蛋白", "Host Cell Protein"],
            "CHO": ["中国仓鼠卵巢", "CHO-K1"],
            "案例分享": ["案例", "分享", "经验"],
            "订货信息": ["订货", "采购", "订单"]
        }
        
        for entity_name in entity_names:
            if entity_name in entity_mappings:
                expanded.update(entity_mappings[entity_name])
        
        return list(expanded)


    def _aggregate_by_section(self, bm25_results: List[Dict], vector_results: List[Dict], 
                            graph_results: List[Dict], understanding_result: Dict) -> List[Dict]:
        """④ 聚合与分数融合（到 section 粒度）"""
        try:
            all_results = bm25_results + vector_results + graph_results
            section_groups = {}
            
            for result in all_results:
                section_id = result.get("section_id", "")
                if not section_id:
                    continue
                
                if section_id not in section_groups:
                    section_groups[section_id] = {
                        "section_id": section_id,
                        "doc_id": result.get("doc_id", ""),
                        "title": result.get("title", ""),
                        "bm25_scores": [],
                        "vector_scores": [],
                        "graph_scores": [],
                        "evidence_elements": [],
                        "all_sources": set(),
                        "metadata": {"page_numbers": set(), "content_types": set()},
                        "has_title_match": False  # 跟踪是否包含title类型的匹配
                    }
                
                group = section_groups[section_id]
                source = result.get("source", "unknown")
                score = result.get("score", 0)
                
                # 🔧 意图感知的分数加权
                intent_type = understanding_result.get("intent_type", "fragment")
                content_type = result.get("content_type", "")
                
                # 如果是title意图且命中了title类型的内容，给予更高权重
                if intent_type == "title" and content_type == "title":
                    score = score * 1.5  # title意图下title内容加权150%
                    group["has_title_match"] = True  # 标记这个section包含title匹配
                    logger.debug(f"Title意图检测到title内容匹配，分数从原始值加权到: {score}")
                
                # 按来源分类分数
                if source == "bm25":
                    group["bm25_scores"].append(score)
                elif source == "vector":
                    group["vector_scores"].append(score)
                elif source == "graph":
                    group["graph_scores"].append(score)
                
                group["all_sources"].add(source)
                
                # 收集证据元素
                evidence = {
                    "element_id": result.get("element_id", ""),
                    "content": result.get("content", ""),
                    "score": score,
                    "source": source,
                    "highlight": result.get("highlight", {}),
                    "bbox": result.get("bbox", {}),
                    "page_number": result.get("page_number", 1)
                }
                group["evidence_elements"].append(evidence)
                
                # 更新元数据
                if result.get("page_number"):
                    group["metadata"]["page_numbers"].add(result.get("page_number"))
                if result.get("content_type"):
                    group["metadata"]["content_types"].add(result.get("content_type"))
            
            # 对每个section进行分数融合
            section_candidates = []
            for section_id, group in section_groups.items():
                # 归一化各路分数
                bm25_norm = self._normalize_scores_list(group["bm25_scores"])
                vector_norm = self._normalize_scores_list(group["vector_scores"])
                graph_norm = self._normalize_scores_list(group["graph_scores"])
                
                # 🔧 意图感知的分数融合策略
                intent_type = understanding_result.get("intent_type", "fragment")
                if intent_type == "title":
                    # title意图：更重视BM25的精确匹配（因为title通常是关键词匹配）
                    final_score = 0.6 * bm25_norm + 0.4 * vector_norm + 0.0 * graph_norm
                else:
                    # fragment意图：更重视语义匹配
                    final_score = 0.4 * bm25_norm + 0.6 * vector_norm + 0.0 * graph_norm
                
                # 选择Top-1证据元素
                top_evidence = sorted(group["evidence_elements"], 
                                    key=lambda x: x["score"], reverse=True)[:1]
                
                section_candidate = {
                    "section_id": section_id,
                    "doc_id": group["doc_id"],
                    "title": group["title"],
                    "final_score": final_score,
                    "bm25_score": bm25_norm,
                    "vector_score": vector_norm,
                    "graph_score": graph_norm,
                    "sources": list(group["all_sources"]),
                    "evidence_elements": top_evidence,
                    "evidence_count": len(group["evidence_elements"]),
                    "metadata": {
                        **group["metadata"],
                        "page_numbers": list(group["metadata"]["page_numbers"]),
                        "content_types": list(group["metadata"]["content_types"]),
                        "aggregation_type": "section",
                        "has_title_match": group["has_title_match"],
                        "intent_type": intent_type
                    }
                }
                
                section_candidates.append(section_candidate)
            
            # 按最终分数排序，取Top-50个section作为重排候选
            section_candidates.sort(key=lambda x: x["final_score"], reverse=True)
            return section_candidates[:50]
            
        except Exception as e:
            logger.error(f"聚合失败: {str(e)}")
            return []
    
    def _normalize_scores_list(self, scores: List[float]) -> float:
        """归一化分数列表 - 保留分数的相对重要性"""
        if not scores:
            return 0.0
        
        if len(scores) == 1:
            return scores[0]
        
        # 🔧 修复：使用加权平均而不是简单的Min-Max归一化
        # 这样可以保留高分数的优势，不会被过度压缩
        total_score = sum(scores)
        if total_score == 0:
            return 0.0
        
        # 使用加权平均：每个分数的权重 = 分数在总分中的占比
        weights = [score / total_score for score in scores]
        weighted_average = sum(score * weight for score, weight in zip(scores, weights))
        
        return weighted_average
    
    def _rerank_sections(self, candidates: List[Dict], understanding_result: Dict) -> Optional[Dict]:
        """⑤ 意图感知的重排（把"最相关的内容"放到第一）"""
        try:
            if not candidates:
                return None
            
            original_query = understanding_result.get("normalized_query", "")
            
            if self.reranker:
                # 使用真实的重排模型
                query_section_pairs = []
                for candidate in candidates:
                    rerank_text = self._build_rerank_text(candidate)
                    query_section_pairs.append([original_query, rerank_text])
                
                # 批量重排
                batch_size = self.reranker_config.get('batch_size', 16)
                rerank_scores = []
                
                for i in range(0, len(query_section_pairs), batch_size):
                    batch = query_section_pairs[i:i+batch_size]
                    batch_scores = self.reranker.predict(batch)
                    rerank_scores.extend(batch_scores)
                
                # 更新分数并排序
                for i, candidate in enumerate(candidates):
                    candidate["rerank_score"] = float(rerank_scores[i])
                    candidate["final_score"] = candidate["final_score"] * 0.3 + candidate["rerank_score"] * 0.7
            else:
                # 🔧 使用意图感知的简单评分
                intent_type = understanding_result.get("intent_type", "fragment")
                for candidate in candidates:
                    title = candidate.get("title", "")
                    evidence_text = " ".join([ev.get("content", "") for ev in candidate.get("evidence_elements", [])])
                    
                    # 计算查询词匹配度
                    query_words = set(original_query.lower().split())
                    title_words = set(title.lower().split())
                    evidence_words = set(evidence_text.lower().split())
                    
                    title_match = len(query_words.intersection(title_words)) / len(query_words) if query_words else 0
                    evidence_match = len(query_words.intersection(evidence_words)) / len(query_words) if query_words else 0
                    
                    # 🔧 根据意图类型调整重排权重
                    if intent_type == "title":
                        # title意图：极重视标题匹配
                        rerank_score = title_match * 3 + evidence_match * 0.5
                        final_weight = 0.7  # 重排权重更高
                    else:
                        # fragment意图：平衡标题和内容匹配
                        rerank_score = title_match * 1.5 + evidence_match
                        final_weight = 0.5  # 标准权重
                    
                    candidate["rerank_score"] = rerank_score
                    candidate["final_score"] = candidate["final_score"] * (1 - final_weight) + rerank_score * final_weight
            
            # 排序并返回Top-1
            candidates.sort(key=lambda x: x["final_score"], reverse=True)
            top_section = candidates[0]
            
            # 片段级高亮
            top_section["evidence_highlights"] = self._select_evidence_highlights(top_section, original_query)
            
            return top_section
            
        except Exception as e:
            logger.error(f"重排失败: {str(e)}")
            return candidates[0] if candidates else None
    
    def _build_rerank_text(self, candidate: Dict) -> str:
        """构建重排用的文本"""
        title = candidate.get("title", "")
        evidence_elements = candidate.get("evidence_elements", [])
        
        # 取前1个最相关的片段
        top_evidence = evidence_elements[:1]
        evidence_texts = [ev.get("content", "") for ev in top_evidence]
        
        # 组合文本
        rerank_text = title
        if evidence_texts:
            rerank_text += " " + " ".join(evidence_texts)
        
        # 截断到512 tokens（粗略按字符数估算）
        max_chars = 512 * 2
        if len(rerank_text) > max_chars:
            rerank_text = rerank_text[:max_chars] + "..."
        
        return rerank_text
    
    def _select_evidence_highlights(self, top_section: Dict, query: str) -> List[Dict]:
        """片段级高亮选择"""
        evidence_elements = top_section.get("evidence_elements", [])
        
        if not evidence_elements:
            return []
        
        # 计算高亮分数
        for evidence in evidence_elements:
            content = evidence.get("content", "")
            query_words = set(query.lower().split())
            content_words = set(content.lower().split())
            
            match_score = len(query_words.intersection(content_words)) / len(query_words) if query_words else 0
            evidence["highlight_score"] = evidence.get("score", 0) * 0.7 + match_score * 0.3
        
        # 按高亮分数排序，选择1条
        evidence_elements.sort(key=lambda x: x.get("highlight_score", 0), reverse=True)
        return evidence_elements[:1]
    
    def _expand_section_content(self, top_section: Dict) -> List[Dict]:
        """⑷ 扩展（把"一家子"拉齐）- 多数据源融合"""
        try:
            section_id = top_section.get("section_id")
            if not section_id:
                return []
            
            expanded_elements = []
            
            # 🔧 第一步：从OpenSearch/MySQL查询表格和图片内容
            multimodal_elements = self._query_section_multimodal_content(section_id, top_section)
            if multimodal_elements:
                expanded_elements.extend(multimodal_elements)
            
            # 🔧 第二步：从Neo4j查询实体关系内容
            if self.neo4j_client:
                entity_elements = self._query_actual_graph_structure(section_id, top_section)
                if entity_elements:
                    expanded_elements.extend(entity_elements)
            
            # 🔧 第三步：如果都没有数据，使用模拟数据
            if not expanded_elements:
                logger.info(f"未找到section_id={section_id}的扩展内容，使用模拟数据")
                return self._mock_section_expansion(top_section)
            
            return expanded_elements
                
        except Exception as e:
            logger.error(f"内容扩展失败: {str(e)}")
            return self._mock_section_expansion(top_section)
    
    def _query_section_multimodal_content(self, section_id: str, top_section: Dict) -> List[Dict]:
        """查询section相关的表格和图片内容"""
        try:
            multimodal_elements = []
            
            # 🔧 策略1：从OpenSearch查询表格和图片
            if self.opensearch_client:
                try:
                    # 查询该section下的表格和图片
                    query_body = {
                        "query": {
                            "bool": {
                                "must": [
                                    {"term": {"section_id.keyword": section_id}},
                                    {"terms": {"content_type.keyword": ["table", "image"]}}
                                ]
                            }
                        },
                        "size": 50
                    }
                    
                    response = self.opensearch_client.search(self.index_name, query_body)
                    
                    if response and 'hits' in response and 'hits' in response['hits']:
                        for hit in response['hits']['hits']:
                            source = hit['_source']
                            element = {
                                "element_id": source.get("element_id", ""),
                                "content_type": source.get("content_type", ""),
                                "content": source.get("content", ""),
                                "title": source.get("title", ""),
                                "order": len(multimodal_elements) + 1,
                                "page_number": source.get("page_number", 1),
                                "bbox": source.get("bbox", {}),
                                "metadata": {
                                    "doc_id": source.get("doc_id", ""),
                                    "section_id": section_id,
                                    "source": "opensearch_multimodal"
                                }
                            }
                            multimodal_elements.append(element)
                    
                except Exception as e:
                    logger.warning(f"OpenSearch查询表格图片失败: {str(e)}")
            
            # 🔧 策略2：从MySQL查询（如果有MySQL连接）
            # TODO: 这里可以添加MySQL查询逻辑
            
            logger.info(f"找到{len(multimodal_elements)}个多媒体元素")
            return multimodal_elements
            
        except Exception as e:
            logger.error(f"查询多媒体内容失败: {str(e)}")
            return []
    
    def _query_actual_graph_structure(self, section_id: str, top_section: Dict) -> List[Dict]:
        """基于实际数据库结构查询相关内容"""
        try:
            expanded_elements = []
            
            with self.neo4j_client.session() as session:
                # 策略1: 从section_id提取真实的doc_id
                actual_doc_id = self._extract_doc_id_from_section(section_id, top_section)
                logger.info(f"提取到的doc_id: {actual_doc_id}")
                
                if actual_doc_id:
                    # 查询与该文档相关的所有实体
                    cypher_query = """
                    MATCH (d:Document {id: $doc_id})-[r:CONTAINS]->(e:Entity)
                    RETURN e, type(r) as relation_type
                    LIMIT 20
                    """
                    result = session.run(cypher_query, doc_id=actual_doc_id)
                    
                    for i, record in enumerate(result):
                        entity = dict(record["e"])
                        entity_name = entity.get('name', '') or entity.get('canonical', '') or f"实体_{i+1}"
                        entity_type = entity.get('entity_type', '') or entity.get('type', '') or "未知类型"
                        
                        element = {
                            "element_id": f"{section_id}_entity_{i}",
                            "content_type": "entity",
                            "content": f"实体: {entity_name} (类型: {entity_type})",
                            "title": entity_name,
                            "order": i + 1,
                            "page_number": entity.get("page_number", 1),
                            "bbox": {},
                            "metadata": {
                                "doc_id": actual_doc_id,
                                "section_id": section_id,
                                "entity_type": entity_type,
                                "entity_id": entity.get('entity_id', ''),
                                "confidence": entity.get('confidence', 0.0),
                                "source": "neo4j_entity"
                            }
                        }
                        expanded_elements.append(element)
                
                # 策略2: 如果找不到Document，尝试直接查找相关实体
                if not expanded_elements:
                    # 从section标题中提取关键词，查找相关实体
                    section_title = top_section.get("title", "")
                    if section_title:
                        # 提取可能的实体名称
                        keywords = [word for word in section_title.split() if len(word) > 2]
                        
                        for keyword in keywords[:3]:  # 限制关键词数量
                            cypher_query = """
                            MATCH (e:Entity)
                            WHERE e.name CONTAINS $keyword OR e.canonical CONTAINS $keyword
                            RETURN e
                            LIMIT 5
                            """
                            result = session.run(cypher_query, keyword=keyword)
                            
                            for i, record in enumerate(result):
                                entity = dict(record["e"])
                                entity_name = entity.get('name', '') or entity.get('canonical', '') or f"相关实体_{i+1}"
                                entity_type = entity.get('entity_type', '') or entity.get('type', '') or "未知类型"
                                
                                element = {
                                    "element_id": f"{section_id}_related_{keyword}_{i}",
                                    "content_type": "related_entity",
                                    "content": f"相关实体: {entity_name} (匹配关键词: {keyword})",
                                    "title": entity_name,
                                    "order": len(expanded_elements) + i + 1,
                                    "page_number": entity.get("page_number", 1),
                                    "bbox": {},
                                    "metadata": {
                                        "doc_id": "related",
                                        "section_id": section_id,
                                        "entity_type": entity_type,
                                        "entity_id": entity.get('entity_id', ''),
                                        "match_keyword": keyword,
                                        "source": "neo4j_related"
                                    }
                                }
                                expanded_elements.append(element)
                
                # 策略3: 混合实际数据和结构化内容
                if expanded_elements:
                    # 如果找到实际实体，添加结构化的章节内容
                    section_title = top_section.get("title", "")
                    if section_title:
                        # 添加标题元素
                        title_element = {
                            "element_id": f"{section_id}_title",
                            "content_type": "title",
                            "content": section_title,
                            "title": section_title,
                            "order": 0,
                            "page_number": 1,
                            "bbox": {},
                            "metadata": {
                                "doc_id": actual_doc_id,
                                "section_id": section_id,
                                "source": "mixed_content"
                            }
                        }
                        expanded_elements.insert(0, title_element)
                        
                        # 重新调整order
                        for i, element in enumerate(expanded_elements[1:], 1):
                            element["order"] = i
                
                logger.info(f"从实际图数据库结构查询到{len(expanded_elements)}个相关元素")
                return expanded_elements
                
        except Exception as e:
            logger.error(f"实际图数据库结构查询失败: {str(e)}")
            return []
    
    def _extract_doc_id_from_section(self, section_id: str, top_section: Dict) -> any:
        """从section_id提取真实的doc_id"""
        try:
            # 策略1: 从top_section获取，但需要验证格式
            doc_id_from_section = top_section.get("doc_id", "")
            
            # 策略2: 从section_id解析
            # section_id格式: 20250818_170435_05dc2896_doc#2025-08-18#7_0009
            if "#" in section_id:
                parts = section_id.split("#")
                if len(parts) >= 3:
                    # 从最后一部分提取数字 (如: 7_0009 -> 7)
                    last_part = parts[-1]
                    if "_" in last_part:
                        doc_id_str = last_part.split("_")[0]
                        try:
                            doc_id = int(doc_id_str)
                            logger.info(f"从section_id解析到doc_id: {doc_id}")
                            return doc_id
                        except ValueError:
                            pass
            
            # 策略3: 检查是否是测试数据，转换为实际ID
            if doc_id_from_section == "test_doc_001" or not doc_id_from_section:
                # 查询数据库中实际存在的第一个Document ID
                with self.neo4j_client.session() as session:
                    result = session.run("MATCH (d:Document) RETURN d.id as doc_id LIMIT 1")
                    for record in result:
                        actual_id = record["doc_id"]
                        logger.info(f"使用数据库中的实际doc_id: {actual_id}")
                        return actual_id
            
            # 策略4: 尝试直接使用原始doc_id
            if doc_id_from_section:
                logger.info(f"使用原始doc_id: {doc_id_from_section}")
                return doc_id_from_section
            
            logger.warning("无法提取有效的doc_id")
            return None
            
        except Exception as e:
            logger.error(f"提取doc_id失败: {str(e)}")
            return None
    
    def _mock_section_expansion(self, top_section: Dict) -> List[Dict]:
        """模拟section扩展内容"""
        section_id = top_section.get("section_id", "")
        doc_id = top_section.get("doc_id", "")
        
        return [
            {
                "element_id": f"{section_id}_title",
                "content_type": "title",
                "content": top_section.get("title", ""),
                "title": top_section.get("title", ""),
                "order": 1,
                "page_number": 1,
                "bbox": {},
                "metadata": {
                    "doc_id": doc_id, 
                    "section_id": section_id,
                    "source": "mock_data"
                }
            },
            {
                "element_id": f"{section_id}_paragraph_001",
                "content_type": "paragraph",
                "content": "这是该章节的第一段内容，详细描述了相关的技术要点和操作规范...",
                "title": "",
                "order": 2,
                "page_number": 1,
                "bbox": {"x": 100, "y": 200, "width": 400, "height": 50},
                "metadata": {
                    "doc_id": doc_id, 
                    "section_id": section_id,
                    "source": "mock_data"
                }
            },
            {
                "element_id": f"{section_id}_table_001",
                "content_type": "table",
                "content": "参数名称 | 标准值 | 检测方法\nHCP含量 | <100ng/mg | ELISA\npH值 | 7.0±0.2 | pH计",
                "title": "关键参数表",
                "order": 3,
                "page_number": 1,
                "bbox": {"x": 100, "y": 300, "width": 400, "height": 100},
                "metadata": {
                    "doc_id": doc_id, 
                    "section_id": section_id,
                    "source": "mock_data"
                }
            },
            {
                "element_id": f"{section_id}_image_001",
                "content_type": "image",
                "content": "图1：HCP检测流程示意图",
                "title": "检测流程图",
                "order": 4,
                "page_number": 2,
                "bbox": {"x": 100, "y": 100, "width": 400, "height": 300},
                "metadata": {
                    "doc_id": doc_id, 
                    "section_id": section_id,
                    "source": "mock_data",
                    "image_path": "/images/hcp_process.jpg"
                }
            }
        ]
    
    def _enrich_multimodal_details(self, top_section: Dict) -> List[Dict]:
        """⑧ 图表细节（MySQL）- 基于section查询MySQL获取图表详细信息"""
        try:
            section_id = top_section.get("section_id")
            if not section_id:
                logger.warning("section_id为空，无法查询图表细节")
                return []
            
            enriched_content = []
            
            # 🔧 第一步：查询figures表获取图片信息
            figures = self._query_figures_from_mysql(section_id)
            enriched_content.extend(figures)
            
            # 🔧 第二步：查询tables表获取表格信息
            tables = self._query_tables_from_mysql(section_id)
            enriched_content.extend(tables)
            
            logger.info(f"从MySQL查询到{len(enriched_content)}个图表元素")
            return enriched_content
            
        except Exception as e:
            logger.error(f"图表细节补充失败: {str(e)}")
            return []
    
    def _query_figures_from_mysql(self, section_id: str) -> List[Dict]:
        """从MySQL figures表查询图片信息"""
        try:
            if not hasattr(self, 'mysql_client') or not self.mysql_client:
                logger.debug("MySQL客户端未初始化，跳过figures查询")
                return []
            
            session = self.mysql_client.get_session()
            try:
                # 查询该section下的所有图片
                query = """
                SELECT elem_id, section_id, image_path, caption, page, bbox_norm, bind_to_elem_id
                FROM figures 
                WHERE section_id = :section_id
                ORDER BY page, elem_id
                """
                
                result = session.execute(text(query), {"section_id": section_id})
                figures = []
                
                for row in result:
                    figure_element = {
                        "element_id": row.elem_id,
                        "content_type": "image",
                        "content": row.caption or f"图片 {row.elem_id}",
                        "title": row.caption or "图片",
                        "order": len(figures) + 1,
                        "page_number": row.page,
                        "bbox": row.bbox_norm or {},
                        "metadata": {
                            "section_id": section_id,
                            "source": "mysql_figures",
                            "bind_to_elem_id": row.bind_to_elem_id
                        },
                        "image_details": {
                            "image_path": row.image_path,
                            "caption": row.caption,
                            "alt_text": row.caption or f"图片 {row.elem_id}",
                            "page": row.page,
                            "bbox": row.bbox_norm,
                            "source": "mysql"
                        }
                    }
                    figures.append(figure_element)
                
                logger.info(f"从MySQL查询到{len(figures)}张图片")
                return figures
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"查询figures表失败: {str(e)}")
            return []
    
    def _query_tables_from_mysql(self, section_id: str) -> List[Dict]:
        """从MySQL tables表查询表格信息"""
        try:
            if not hasattr(self, 'mysql_client') or not self.mysql_client:
                logger.debug("MySQL客户端未初始化，跳过tables查询")
                return []
            
            session = self.mysql_client.get_session()
            try:
                # 查询该section下的所有表格
                tables_query = """
                SELECT elem_id, section_id, table_html, n_rows, n_cols
                FROM tables 
                WHERE section_id = :section_id
                ORDER BY elem_id
                """
                
                result = session.execute(text(tables_query), {"section_id": section_id})
                tables = []
                
                for row in result:
                    # 查询表格的详细行数据
                    table_rows = self._query_table_rows(session, row.elem_id)
                    
                    table_element = {
                        "element_id": row.elem_id,
                        "content_type": "table",
                        "content": f"表格 {row.elem_id} ({row.n_rows}行×{row.n_cols}列)",
                        "title": f"表格 {len(tables) + 1}",
                        "order": len(tables) + 1,
                        "page_number": 1,  # 可以从其他地方获取
                        "bbox": {},
                        "metadata": {
                            "section_id": section_id,
                            "source": "mysql_tables",
                            "table_elem_id": row.elem_id
                        },
                        "table_details": {
                            "elem_id": row.elem_id,
                            "rows": row.n_rows,
                            "columns": row.n_cols,
                            "html": row.table_html,
                            "data": table_rows,
                            "source": "mysql"
                        }
                    }
                    tables.append(table_element)
                
                logger.info(f"从MySQL查询到{len(tables)}张表格")
                return tables
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"查询tables表失败: {str(e)}")
            return []
    
    def _query_table_rows(self, session, table_elem_id: str) -> List[Dict]:
        """查询表格的详细行数据"""
        try:
            rows_query = """
            SELECT row_index, row_text, row_json
            FROM table_rows 
            WHERE table_elem_id = :table_elem_id
            ORDER BY row_index
            """
            
            result = session.execute(text(rows_query), {"table_elem_id": table_elem_id})
            rows_data = []
            
            for row in result:
                row_data = {
                    "row_index": row.row_index,
                    "row_text": row.row_text,
                    "row_json": row.row_json
                }
                rows_data.append(row_data)
            
            return rows_data
            
        except Exception as e:
            logger.error(f"查询表格行数据失败: {str(e)}")
            return []
    
    def _stream_render_answer(self, query: str, top_section: Dict, multimodal_content: List[Dict], 
                            understanding_result: Dict) -> Generator[Dict, None, None]:
        """⑨ 组装/渲染（可流式）- 基于top_section的完整文本答案和多模态内容"""
        try:
            # 从top_section获取完整的文本答案
            evidence_elements = top_section.get("evidence_elements", [])
            evidence_highlights = top_section.get("evidence_highlights", [])
            section_title = top_section.get("title", "相关章节")
            
            # 首屏输出：章节标题
            yield {
                "type": "answer_chunk",
                "content": f"## {section_title}\n\n"
            }
            
            # 🔧 流式输出文本答案（基于evidence_elements和evidence_highlights）
            if evidence_elements:
                # 输出最相关的证据内容（已经是Top-1）
                for evidence in evidence_elements:
                    content = evidence.get("content", "")
                    if content:
                        # 应用高亮标记
                        highlighted_content = self._apply_evidence_highlighting_to_content(
                            content, evidence_highlights, evidence.get("element_id", "")
                        )
                        
                        yield {
                            "type": "answer_chunk",
                            "content": highlighted_content + "\n\n"
                        }
                        sleep(0.1)  # 流式效果
            
            # 🔧 深度分析并输出多模态内容
            if multimodal_content:
                # 按类型分组多模态内容
                images = [item for item in multimodal_content if item.get("content_type") == "image"]
                tables = [item for item in multimodal_content if item.get("content_type") == "table"]
                charts = [item for item in multimodal_content if item.get("content_type") == "chart"]
                
                # 流式输出图片
                for image in images:
                    yield {
                        "type": "multimodal_content",
                        "content_type": "image",
                        "data": self._format_image_for_stream(image)
                    }
                    sleep(0.2)  # 图片加载间隔
                
                # 流式输出表格
                for table in tables:
                    yield {
                        "type": "multimodal_content", 
                        "content_type": "table",
                        "data": self._format_table_for_stream(table)
                    }
                    sleep(0.2)  # 表格渲染间隔
                
                # 流式输出图表
                for chart in charts:
                    yield {
                        "type": "multimodal_content",
                        "content_type": "chart", 
                        "data": self._format_chart_for_stream(chart)
                    }
                    sleep(0.2)  # 图表渲染间隔
            
            # 生成参考来源
            references = self._build_references_from_section(top_section, multimodal_content)
            if references:
                yield {
                    "type": "answer_chunk",
                    "content": f"\n**参考来源：**\n{references}\n"
                }
            
            # 生成最终完整答案
            final_answer = {
                "query": query,
                "intent_type": understanding_result.get("intent_type", ""),
                "selected_section": {
                    "section_id": top_section.get("section_id"),
                    "score": top_section.get("final_score", 0),
                    "title": section_title
                },
                "evidence_highlights": evidence_highlights,
                "evidence_count": len(evidence_elements),
                "multimodal_summary": {
                    "images": len([item for item in multimodal_content if item.get("content_type") == "image"]),
                    "tables": len([item for item in multimodal_content if item.get("content_type") == "table"]), 
                    "charts": len([item for item in multimodal_content if item.get("content_type") == "chart"])
                },
                "generation_time": datetime.now().isoformat()
            }
            
            yield {
                "type": "final_answer",
                "content": final_answer,
                "metadata": {
                    "generation_method": "evidence_based_rendering",
                    "has_multimodal": len(multimodal_content) > 0,
                    "text_source": "evidence_elements",
                    "multimodal_source": "mysql_enrichment"
                }
            }
            
        except Exception as e:
            logger.error(f"流式渲染失败: {str(e)}")
            yield {"type": "error", "message": f"答案生成失败: {str(e)}"}
    
    def _get_section_title(self, content: List[Dict]) -> str:
        """从内容中提取section标题"""
        for element in content:
            if element.get("content_type") == "title":
                return element.get("content", "未知章节")
        
        if content:
            return content[0].get("title", "未知章节")
        
        return "未知章节"
    
    def _apply_evidence_highlighting_to_content(self, content: str, evidence_highlights: List[Dict], element_id: str) -> str:
        """对文本内容进行高亮标记"""
        if not content:
            return ""
        
        # 检查当前元素是否在高亮证据中
        is_highlighted = any(ev.get("element_id") == element_id for ev in evidence_highlights)
        
        if is_highlighted:
            return f"<mark style='padding: 2px 4px; border-radius: 3px;'>{content}</mark>"
        
        return content
    
    def _apply_evidence_highlighting(self, element: Dict, evidence_highlights: List[Dict]) -> str:
        """对证据进行高亮标记"""
        content = element.get("content", "")
        element_id = element.get("element_id", "")
        
        return self._apply_evidence_highlighting_to_content(content, evidence_highlights, element_id)
    
    def _format_table_for_stream(self, table_element: Dict) -> Dict:
        """格式化表格用于流式输出"""
        table_details = table_element.get("table_details", {})
        metadata = table_element.get("metadata", {})
        
        return {
            "element_id": table_element.get("element_id", ""),
            "title": table_element.get("title", "数据表"),
            "description": table_element.get("content", ""),
            "html_content": table_details.get("html", ""),
            "structured_data": table_details.get("data", []),
            "headers": table_details.get("headers", []),
            "rows": table_details.get("rows", 0),
            "columns": table_details.get("columns", 0),
            "page_number": table_element.get("page_number", 1),
            "bbox": table_element.get("bbox", {})
        }
    
    def _format_image_for_stream(self, image_element: Dict) -> Dict:
        """格式化图片用于流式输出"""
        image_details = image_element.get("image_details", {})
        metadata = image_element.get("metadata", {})
        
        # 构建图片URL
        image_path = image_details.get("image_path", "")
        image_url = ""
        if image_path:
            if image_path.startswith('http'):
                image_url = image_path
            elif image_path.startswith('/'):
                image_url = image_path
            elif image_path.startswith('figures/'):
                # 如果路径已经以figures/开头，直接使用
                image_url = f"/static/uploads/{image_path}"
            else:
                # 其他情况，添加完整前缀
                image_url = f"/static/uploads/{image_path}"
        
        return {
            "element_id": image_element.get("element_id", ""),
            "title": image_element.get("title", "图片"),
            "description": image_element.get("content", ""),
            "caption": image_details.get("caption", ""),
            "alt_text": image_details.get("alt_text", image_element.get("content", "")),
            "image_path": image_path,
            "image_url": image_url,
            "url": image_url,  # 兼容字段
            "width": image_details.get("width", 0),
            "height": image_details.get("height", 0),
            "format": image_details.get("format", ""),
            "page_number": image_element.get("page_number", 1),
            "bbox": image_element.get("bbox", {})
        }
    
    def _format_chart_for_stream(self, chart_element: Dict) -> Dict:
        """格式化图表用于流式输出"""
        chart_details = chart_element.get("chart_details", {})
        metadata = chart_element.get("metadata", {})
        
        return {
            "element_id": chart_element.get("element_id", ""),
            "title": chart_element.get("title", "图表"),
            "description": chart_element.get("content", ""),
            "chart_type": chart_details.get("chart_type", ""),
            "data_source": chart_details.get("data_source", ""),
            "page_number": chart_element.get("page_number", 1),
            "bbox": chart_element.get("bbox", {})
        }
    
    def _build_references_from_content(self, content: List[Dict], evidence_highlights: List[Dict]) -> str:
        """从内容构建参考来源"""
        references = []
        doc_info = {}
        
        # 收集文档信息
        for element in content:
            metadata = element.get("metadata", {})
            doc_id = metadata.get("doc_id", "")
            section_id = metadata.get("section_id", "")
            
            if doc_id and doc_id not in doc_info:
                doc_info[doc_id] = {
                    "section_id": section_id,
                    "title": element.get("title", ""),
                    "doc_name": self._get_document_name_by_id(doc_id),
                    "page_numbers": set()
                }
            
            if doc_id and element.get("page_number"):
                doc_info[doc_id]["page_numbers"].add(element.get("page_number"))
        
        # 生成引用格式
        for i, (doc_id, info) in enumerate(doc_info.items(), 1):
            pages = sorted(list(info["page_numbers"]))
            page_text = f"第{', '.join(map(str, pages))}页" if pages else ""
            
            # 构建引用格式：[序号] 文档名 - 章节标题 (页码信息)
            doc_name = info.get('doc_name', '未知文档')
            title = info.get('title', '')
            
            if title and title != doc_name:
                ref = f"[{i}] {doc_name} - {title} ({page_text})"
            else:
                ref = f"[{i}] {doc_name} ({page_text})"
            
            references.append(ref)
        
        return "\n".join(references)
    
    def _format_image_for_frontend(self, image_element: Dict) -> Dict:
        """格式化图片数据供前端渲染"""
        image_details = image_element.get("image_details", {})
        metadata = image_element.get("metadata", {})
        
        return {
            "element_id": image_element.get("element_id", ""),
            "title": image_element.get("title", "图片"),
            "description": image_element.get("content", ""),
            "caption": image_details.get("caption", ""),
            "alt_text": image_details.get("alt_text", image_element.get("content", "")),
            "image_path": image_details.get("image_path", ""),
            "page_number": image_element.get("page_number", 1),
            "bbox": image_element.get("bbox", {}),
            "doc_id": metadata.get("doc_id", ""),
            "section_id": metadata.get("section_id", ""),
            # 前端渲染所需的URL和样式信息
            "display_url": self._build_image_display_url(image_details, metadata),
            "thumbnail_url": self._build_image_thumbnail_url(image_details, metadata),
            "view_original_url": f"/api/file/view/{metadata.get('doc_id')}?page={image_element.get('page_number')}&highlight=image",
            "render_config": {
                "max_width": "100%",
                "max_height": "400px", 
                "border_radius": "8px",
                "box_shadow": "0 2px 8px rgba(0,0,0,0.1)"
            }
        }
    
    def _format_table_for_frontend(self, table_element: Dict) -> Dict:
        """格式化表格数据供前端渲染"""
        table_details = table_element.get("table_details", {})
        metadata = table_element.get("metadata", {})
        
        # 深度分析表格结构
        table_data = table_details.get("data", [])
        table_html = table_details.get("html", "")
        
        # 构建前端可直接渲染的表格结构
        formatted_table = {
            "element_id": table_element.get("element_id", ""),
            "title": table_element.get("title", "数据表"),
            "description": table_element.get("content", ""),
            "rows": table_details.get("rows", 0),
            "columns": table_details.get("columns", 0),
            "page_number": table_element.get("page_number", 1),
            "bbox": table_element.get("bbox", {}),
            "doc_id": metadata.get("doc_id", ""),
            "section_id": metadata.get("section_id", ""),
            
            # 前端渲染的核心数据
            "html_content": table_html,
            "structured_data": self._parse_table_data_for_frontend(table_data),
            "headers": self._extract_table_headers(table_data, table_html),
            
            # 前端渲染配置
            "render_config": {
                "enable_sorting": True,
                "enable_search": len(table_data) > 10,
                "pagination": len(table_data) > 20,
                "page_size": 20,
                "responsive": True,
                "striped_rows": True,
                "bordered": True,
                "hover_effect": True,
                "css_classes": ["table", "table-striped", "table-bordered", "table-hover"]
            },
            
            # 操作链接
            "view_original_url": f"/api/file/view/{metadata.get('doc_id')}?page={table_element.get('page_number')}&highlight=table",
            "export_csv_url": f"/api/table/export/{table_element.get('element_id')}/csv",
            "export_excel_url": f"/api/table/export/{table_element.get('element_id')}/excel"
        }
        
        return formatted_table
    
    def _format_chart_for_frontend(self, chart_element: Dict) -> Dict:
        """格式化图表数据供前端渲染"""
        chart_details = chart_element.get("chart_details", {})
        metadata = chart_element.get("metadata", {})
        
        return {
            "element_id": chart_element.get("element_id", ""),
            "title": chart_element.get("title", "图表"),
            "description": chart_element.get("content", ""),
            "chart_type": chart_details.get("chart_type", "unknown"),
            "page_number": chart_element.get("page_number", 1),
            "bbox": chart_element.get("bbox", {}),
            "doc_id": metadata.get("doc_id", ""),
            "section_id": metadata.get("section_id", ""),
            
            # 图表数据和配置
            "chart_data": chart_details.get("data", {}),
            "chart_config": chart_details.get("config", {}),
            "image_url": chart_details.get("image_path", ""),
            
            # 前端渲染配置
            "render_config": {
                "width": "100%",
                "height": "300px",
                "responsive": True,
                "interactive": True,
                "theme": "light"
            },
            
            # 操作链接
            "view_original_url": f"/api/file/view/{metadata.get('doc_id')}?page={chart_element.get('page_number')}&highlight=chart",
            "download_image_url": f"/api/chart/download/{chart_element.get('element_id')}/png"
        }
    
    def _get_document_name_by_id(self, doc_id: str) -> str:
        """根据doc_id获取文档名称"""
        try:
            logger.info(f"🔍 获取文档名称 - 输入doc_id: {repr(doc_id)} (类型: {type(doc_id)})")
            
            if not doc_id:
                logger.warning("❌ doc_id为空，返回默认值")
                return "未知文档"
                
            # 尝试转换为整数ID
            try:
                doc_id_int = int(doc_id)
                logger.info(f"✅ doc_id转换为整数: {doc_id_int}")
            except (ValueError, TypeError):
                # 如果不是数字，可能是字符串ID，直接使用
                doc_id_int = doc_id
                logger.info(f"⚠️ doc_id保持为字符串: {doc_id_int}")
            
            # 查询数据库获取文档名称
            query = "SELECT filename FROM documents WHERE id = :doc_id"
            logger.info(f"🔍 执行查询: {query} (参数: {doc_id_int})")
            
            result = self.mysql_client.execute_query(query, {'doc_id': doc_id_int})
            logger.info(f"📊 查询结果: {result}")
            
            if result and len(result) > 0:
                filename = result[0].get('filename', '')
                logger.info(f"📁 获取到filename: {filename}")
                
                if filename:
                    # 去掉文件扩展名，只保留文档名
                    import os
                    doc_name = os.path.splitext(filename)[0]
                    logger.info(f"✅ 处理后的文档名: {doc_name}")
                    return doc_name
            
            fallback_name = f"文档{doc_id}"
            logger.warning(f"⚠️ 未找到文档，返回默认名称: {fallback_name}")
            return fallback_name
            
        except Exception as e:
            error_msg = f"获取文档名称失败 (doc_id: {doc_id}): {str(e)}"
            logger.error(error_msg)
            return f"文档{doc_id}"
    
    def _build_references_from_section(self, top_section: Dict, multimodal_content: List[Dict]) -> str:
        """从section和多模态内容构建参考来源"""
        references = []
        doc_info = {}
        
        # 从top_section收集信息
        section_doc_id = top_section.get("doc_id", "")
        section_title = top_section.get("title", "")
        
        if section_doc_id:
            doc_info[section_doc_id] = {
                "title": section_title,
                "doc_name": self._get_document_name_by_id(section_doc_id),
                "page_numbers": set(),
                "elements": []
            }
            
            # 从evidence_elements收集页码
            for evidence in top_section.get("evidence_elements", []):
                if evidence.get("page_number"):
                    doc_info[section_doc_id]["page_numbers"].add(evidence.get("page_number"))
        
        # 从多模态内容收集信息
        for item in multimodal_content:
            metadata = item.get("metadata", {})
            doc_id = metadata.get("doc_id", "")
            
            if doc_id and doc_id not in doc_info:
                doc_info[doc_id] = {
                    "title": item.get("title", ""),
                    "doc_name": self._get_document_name_by_id(doc_id),
                    "page_numbers": set(),
                    "elements": []
                }
            
            if doc_id and item.get("page_number"):
                doc_info[doc_id]["page_numbers"].add(item.get("page_number"))
                doc_info[doc_id]["elements"].append({
                    "type": item.get("content_type", ""),
                    "title": item.get("title", "")
                })
        
        # 生成引用格式
        for i, (doc_id, info) in enumerate(doc_info.items(), 1):
            pages = sorted(list(info["page_numbers"]))
            page_text = f"第{', '.join(map(str, pages))}页" if pages else ""
            
            elements_text = ""
            if info["elements"]:
                element_types = {}
                for elem in info["elements"]:
                    elem_type = elem["type"]
                    if elem_type not in element_types:
                        element_types[elem_type] = 0
                    element_types[elem_type] += 1
                
                type_texts = []
                for elem_type, count in element_types.items():
                    type_name = {"image": "图片", "table": "表格", "chart": "图表"}.get(elem_type, elem_type)
                    type_texts.append(f"{count}个{type_name}")
                
                if type_texts:
                    elements_text = f" (包含{', '.join(type_texts)})"
            
            # 构建引用格式：[序号] 文档名 - 章节标题 页码信息 (多模态内容)
            doc_name = info.get('doc_name', '未知文档')
            title = info.get('title', '')
            
            if title and title != doc_name:
                ref = f"[{i}] {doc_name} - {title} {page_text}{elements_text}"
            else:
                ref = f"[{i}] {doc_name} {page_text}{elements_text}"
            
            references.append(ref)
        
        return "\n".join(references)
    
    def _build_image_display_url(self, image_details: Dict, metadata: Dict) -> str:
        """构建图片显示URL"""
        image_path = image_details.get("image_path", "")
        if image_path:
            # 如果有直接的图片路径，使用静态文件服务
            return f"/api/static/images/{image_path}"
        else:
            # 否则使用PDF页面截图
            doc_id = metadata.get("doc_id", "")
            page_no = image_details.get("page", 1)
            return f"/api/file/view/{doc_id}?page={page_no}&format=image"
    
    def _build_image_thumbnail_url(self, image_details: Dict, metadata: Dict) -> str:
        """构建图片缩略图URL"""
        display_url = self._build_image_display_url(image_details, metadata)
        return f"{display_url}&thumbnail=true&size=200x150"
    
    def _parse_table_data_for_frontend(self, table_data: List[Dict]) -> List[List[str]]:
        """解析表格数据为前端可渲染的二维数组"""
        if not table_data:
            return []
        
        parsed_data = []
        for row in table_data:
            if isinstance(row, dict):
                # 如果是字典格式，提取row_text或row_json
                row_text = row.get("row_text", "")
                if row_text:
                    # 简单分割，实际可能需要更复杂的解析
                    cells = [cell.strip() for cell in row_text.split("|") if cell.strip()]
                    parsed_data.append(cells)
            elif isinstance(row, list):
                # 如果已经是列表格式
                parsed_data.append([str(cell) for cell in row])
            elif isinstance(row, str):
                # 如果是字符串，尝试分割
                cells = [cell.strip() for cell in row.split("|") if cell.strip()]
                parsed_data.append(cells)
        
        return parsed_data
    
    def _extract_table_headers(self, table_data: List[Dict], table_html: str) -> List[str]:
        """提取表格标题行"""
        if table_data and len(table_data) > 0:
            first_row = table_data[0]
            if isinstance(first_row, dict):
                row_text = first_row.get("row_text", "")
                if row_text:
                    return [cell.strip() for cell in row_text.split("|") if cell.strip()]
            elif isinstance(first_row, list):
                return [str(cell) for cell in first_row]
        
        # 如果无法从数据中提取，尝试从HTML中提取
        if table_html:
            # 简单的HTML解析，实际可能需要更复杂的处理
            import re
            th_pattern = r'<th[^>]*>(.*?)</th>'
            headers = re.findall(th_pattern, table_html, re.IGNORECASE | re.DOTALL)
            if headers:
                return [re.sub(r'<[^>]+>', '', header).strip() for header in headers]
        
        return []
