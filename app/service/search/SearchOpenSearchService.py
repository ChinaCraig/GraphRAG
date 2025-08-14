"""
OpenSearch检索服务
负责基于OpenSearch的BM25检索逻辑
"""

import logging
import yaml
from typing import Dict, List, Optional, Any
from datetime import datetime

from utils.OpenSearchManager import OpenSearchManager

logger = logging.getLogger(__name__)


class SearchOpenSearchService:
    """OpenSearch检索服务类"""
    
    def __init__(self, config_path: str = 'config/db.yaml'):
        """
        初始化OpenSearch检索服务
        
        Args:
            config_path: 数据库配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_config()
        
        # 初始化OpenSearch管理器
        self.opensearch_manager = OpenSearchManager(config_path)
        
        # 从配置获取索引名称和搜索设置
        self.index_name = self.opensearch_config.get('index_name', 'graphrag_documents')
        self.search_settings = self.opensearch_config.get('search_settings', {})
    
    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                db_config = yaml.safe_load(file)
            
            self.opensearch_config = db_config.get('opensearch', {})
            if not self.opensearch_config:
                raise ValueError("OpenSearch配置未找到")
            
            self.logger.info("OpenSearch检索服务配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载OpenSearch检索服务配置失败: {str(e)}")
            raise
    
    def search_bm25(self, query: str, keywords: List[str] = None, synonyms: List[str] = None, 
                   filters: Optional[Dict] = None, size: int = 50) -> List[Dict]:
        """
        执行BM25检索
        
        Args:
            query: 查询字符串
            keywords: 关键词列表
            synonyms: 同义词列表
            filters: 过滤条件
            size: 返回结果数量
            
        Returns:
            List[Dict]: 检索结果列表
        """
        try:
            # 构建查询体
            query_body = self._build_bm25_query(query, keywords, synonyms, filters, size)
            
            # 执行搜索
            response = self.opensearch_manager.search(self.index_name, query_body)
            
            if not response:
                self.logger.warning(f"OpenSearch搜索返回空结果")
                return []
            
            # 处理结果
            results = self._process_search_results(response)
            
            total_hits = response.get('hits', {}).get('total', {}).get('value', 0)
            self.logger.info(f"BM25搜索完成: 查询='{query}', 总命中={total_hits}, 返回={len(results)}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"BM25搜索失败: {str(e)}")
            return []
    
    def _build_bm25_query(self, query: str, keywords: List[str] = None, synonyms: List[str] = None,
                         filters: Optional[Dict] = None, size: int = 50) -> Dict[str, Any]:
        """
        构建BM25查询体
        
        Args:
            query: 查询字符串
            keywords: 关键词列表
            synonyms: 同义词列表
            filters: 过滤条件
            size: 返回结果数量
            
        Returns:
            Dict[str, Any]: 查询体
        """
        # 限制返回数量
        size = min(size, self.search_settings.get('max_size', 100))
        
        # 构建查询字符串
        query_text = self._build_query_text(query, keywords, synonyms)
        
        # 构建多字段查询
        field_weights = self.search_settings.get('field_weights', {
            'title': 3.0,
            'content': 1.0,
            'summary': 2.0
        })
        
        should_queries = []
        
        # 标题字段查询（高权重）
        should_queries.append({
            "match": {
                "title": {
                    "query": query_text,
                    "boost": field_weights.get('title', 3.0)
                }
            }
        })
        
        # 内容字段查询
        should_queries.append({
            "match": {
                "content": {
                    "query": query_text,
                    "boost": field_weights.get('content', 1.0)
                }
            }
        })
        
        # 摘要字段查询（中权重）
        should_queries.append({
            "match": {
                "summary": {
                    "query": query_text,
                    "boost": field_weights.get('summary', 2.0)
                }
            }
        })
        
        # 短语匹配（精确匹配加分）
        should_queries.append({
            "multi_match": {
                "query": query_text,
                "type": "phrase",
                "fields": ["title^2", "content", "summary^1.5"],
                "boost": 1.5
            }
        })
        
        # 如果有关键词，添加关键词匹配
        if keywords:
            for keyword in keywords:
                should_queries.append({
                    "multi_match": {
                        "query": keyword,
                        "fields": ["title^3", "content^1.5", "summary^2"],
                        "boost": 2.0
                    }
                })
        
        # 构建查询体
        query_body = {
            "query": {
                "bool": {
                    "should": should_queries,
                    "minimum_should_match": 1
                }
            },
            "size": size,
            "track_total_hits": self.search_settings.get('track_total_hits', True),
            "_source": {
                "includes": [
                    "doc_id", "section_id", "element_id", "title", "content", "summary",
                    "content_type", "doc_type", "block_type", "page_number", "bbox",
                    "created_time", "file_path", "metadata"
                ]
            }
        }
        
        # 添加过滤条件
        if filters:
            filter_conditions = self._build_filter_conditions(filters)
            if filter_conditions:
                query_body["query"]["bool"]["filter"] = filter_conditions
        
        # 添加高亮
        if self.search_settings.get('highlight_enabled', True):
            query_body["highlight"] = {
                "fields": {
                    "title": {},
                    "content": {"fragment_size": 100, "number_of_fragments": 3},
                    "summary": {}
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            }
        
        # 添加排序（相关性优先，时间作为次要排序）
        query_body["sort"] = [
            {"_score": {"order": "desc"}},
            {"created_time": {"order": "desc"}}
        ]
        
        return query_body
    
    def _build_query_text(self, query: str, keywords: List[str] = None, synonyms: List[str] = None) -> str:
        """
        构建查询文本
        
        Args:
            query: 原始查询
            keywords: 关键词列表
            synonyms: 同义词列表
            
        Returns:
            str: 组合的查询文本
        """
        query_parts = [query] if query else []
        
        # 添加关键词（高优先级）
        if keywords:
            query_parts.extend(keywords)
        
        # 添加同义词（扩展检索）
        if synonyms:
            query_parts.extend(synonyms[:5])  # 限制同义词数量避免查询过长
        
        # 组合成查询文本
        query_text = " ".join(query_parts) if query_parts else ""
        
        self.logger.debug(f"构建BM25查询文本: {query_text}")
        return query_text
    
    def _build_filter_conditions(self, filters: Dict) -> List[Dict]:
        """
        构建过滤条件
        
        Args:
            filters: 过滤条件字典
            
        Returns:
            List[Dict]: 过滤条件列表
        """
        filter_conditions = []
        
        # 文档类型过滤
        if filters.get('doc_types'):
            filter_conditions.append({
                "terms": {"doc_type": filters['doc_types']}
            })
        
        # 内容类型过滤
        if filters.get('content_types'):
            filter_conditions.append({
                "terms": {"content_type": filters['content_types']}
            })
        
        # 块类型过滤
        if filters.get('block_types'):
            filter_conditions.append({
                "terms": {"block_type": filters['block_types']}
            })
        
        # 时间范围过滤
        if filters.get('time_range'):
            start_time, end_time = filters['time_range']
            filter_conditions.append({
                "range": {
                    "created_time": {
                        "gte": start_time,
                        "lte": end_time
                    }
                }
            })
        
        # 文档ID过滤
        if filters.get('doc_ids'):
            filter_conditions.append({
                "terms": {"doc_id": [str(doc_id) for doc_id in filters['doc_ids']]}
            })
        
        # 表格类型增强权重
        if filters.get('boost_table'):
            # 这里不添加filter，而是在should查询中处理
            pass
        
        # 图像相关过滤
        if filters.get('has_image'):
            filter_conditions.append({
                "exists": {"field": "bbox"}
            })
        
        return filter_conditions
    
    def _process_search_results(self, response: Dict) -> List[Dict]:
        """
        处理搜索结果
        
        Args:
            response: OpenSearch响应
            
        Returns:
            List[Dict]: 标准化的搜索结果
        """
        results = []
        
        hits = response.get('hits', {}).get('hits', [])
        for hit in hits:
            result = {
                'id': hit['_id'],
                'score': hit['_score'],
                'source': 'bm25',
                **hit['_source']
            }
            
            # 添加高亮信息
            if 'highlight' in hit:
                result['highlight'] = hit['highlight']
            
            # 确保必要字段存在
            result.setdefault('doc_id', '')
            result.setdefault('section_id', '')
            result.setdefault('element_id', '')
            result.setdefault('title', '')
            result.setdefault('content', '')
            result.setdefault('content_type', '')
            result.setdefault('doc_type', '')
            result.setdefault('block_type', '')
            result.setdefault('page_number', 1)
            result.setdefault('bbox', {})
            result.setdefault('metadata', {})
            
            results.append(result)
        
        return results
    
    def search_by_document_id(self, doc_id: int, query: str = "", size: int = 20) -> List[Dict]:
        """
        在指定文档中搜索
        
        Args:
            doc_id: 文档ID
            query: 查询字符串
            size: 返回结果数量
            
        Returns:
            List[Dict]: 搜索结果
        """
        try:
            filters = {'doc_ids': [doc_id]}
            return self.search_bm25(query, filters=filters, size=size)
            
        except Exception as e:
            self.logger.error(f"文档内搜索失败: {str(e)}")
            return []
    
    def get_document_sections(self, doc_id: int) -> List[Dict]:
        """
        获取文档的所有sections
        
        Args:
            doc_id: 文档ID
            
        Returns:
            List[Dict]: section列表
        """
        try:
            query_body = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"doc_id": str(doc_id)}},
                            {"term": {"content_type": "section"}}
                        ]
                    }
                },
                "size": 1000,  # 假设单个文档不会超过1000个section
                "sort": [{"section_id": {"order": "asc"}}]
            }
            
            response = self.opensearch_manager.search(self.index_name, query_body)
            if response:
                return self._process_search_results(response)
            return []
            
        except Exception as e:
            self.logger.error(f"获取文档sections失败: {str(e)}")
            return []
    
    def get_document_fragments(self, doc_id: int, section_id: str = None) -> List[Dict]:
        """
        获取文档的fragments
        
        Args:
            doc_id: 文档ID
            section_id: 可选的section ID
            
        Returns:
            List[Dict]: fragment列表
        """
        try:
            must_conditions = [
                {"term": {"doc_id": str(doc_id)}},
                {"term": {"content_type": "fragment"}}
            ]
            
            if section_id:
                must_conditions.append({"term": {"section_id": section_id}})
            
            query_body = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                },
                "size": 1000,
                "sort": [{"element_id": {"order": "asc"}}]
            }
            
            response = self.opensearch_manager.search(self.index_name, query_body)
            if response:
                return self._process_search_results(response)
            return []
            
        except Exception as e:
            self.logger.error(f"获取文档fragments失败: {str(e)}")
            return []
    
    def get_search_suggestions(self, query: str, size: int = 5) -> List[str]:
        """
        获取搜索建议
        
        Args:
            query: 查询字符串
            size: 建议数量
            
        Returns:
            List[str]: 搜索建议列表
        """
        try:
            # 基于标题字段获取建议
            query_body = {
                "suggest": {
                    "title_suggest": {
                        "prefix": query,
                        "completion": {
                            "field": "title.suggest",
                            "size": size,
                            "skip_duplicates": True
                        }
                    }
                }
            }
            
            response = self.opensearch_manager.search(self.index_name, query_body)
            
            suggestions = []
            if response and 'suggest' in response:
                title_suggestions = response['suggest'].get('title_suggest', [])
                for suggestion_group in title_suggestions:
                    for option in suggestion_group.get('options', []):
                        suggestions.append(option['text'])
            
            return suggestions[:size]
            
        except Exception as e:
            self.logger.error(f"获取搜索建议失败: {str(e)}")
            return []
    
    def get_index_stats(self) -> Optional[Dict]:
        """
        获取索引统计信息
        
        Returns:
            Optional[Dict]: 索引统计信息
        """
        return self.opensearch_manager.get_index_stats(self.index_name)
