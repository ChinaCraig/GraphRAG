"""
OpenSearch管理器
负责OpenSearch连接、索引管理和BM25检索功能
"""

import json
import logging
import yaml
from typing import Dict, List, Optional, Any
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import RequestError, NotFoundError

logger = logging.getLogger(__name__)


class OpenSearchManager:
    """OpenSearch管理器类"""
    
    def __init__(self, config_path: str = 'config/db.yaml'):
        """
        初始化OpenSearch管理器
        
        Args:
            config_path: 数据库配置文件路径
        """
        self.config_path = config_path
        self.client = None
        self.config = None
        self._load_config()
        self._init_client()
    
    def _load_config(self) -> None:
        """加载OpenSearch配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                db_config = yaml.safe_load(f)
            
            self.config = db_config.get('opensearch', {})
            if not self.config:
                raise ValueError("OpenSearch配置未找到")
            
            logger.info("OpenSearch配置加载成功")
            
        except Exception as e:
            logger.error(f"加载OpenSearch配置失败: {str(e)}")
            raise
    
    def _init_client(self) -> None:
        """初始化OpenSearch客户端"""
        try:
            # 构建连接配置
            client_config = {
                'hosts': [{'host': self.config['host'], 'port': self.config['port']}],
                'http_auth': (self.config['username'], self.config['password']),
                'use_ssl': self.config.get('use_ssl', False),
                'verify_certs': self.config.get('verify_certs', False),
                'ssl_show_warn': self.config.get('ssl_show_warn', False),
                'connection_class': RequestsHttpConnection,
                'timeout': self.config.get('timeout', 30),
                'max_retries': self.config.get('max_retries', 3),
                'retry_on_timeout': True
            }
            
            self.client = OpenSearch(**client_config)
            
            # 测试连接
            info = self.client.info()
            logger.info(f"OpenSearch连接成功: {info['version']['distribution']} {info['version']['number']}")
            
        except Exception as e:
            logger.error(f"OpenSearch客户端初始化失败: {str(e)}")
            raise
    
    def create_index(self) -> bool:
        """
        创建文档索引
        
        Returns:
            bool: 创建是否成功
        """
        try:
            index_name = self.config['index_name']
            
            # 检查索引是否已存在
            if self.client.indices.exists(index=index_name):
                logger.info(f"索引 {index_name} 已存在")
                return True
            
            # 构建索引映射
            mapping = {
                "settings": {
                    "number_of_shards": self.config['index_settings']['number_of_shards'],
                    "number_of_replicas": self.config['index_settings']['number_of_replicas'],
                    "refresh_interval": self.config['index_settings']['refresh_interval'],
                    "analysis": {
                        "analyzer": {
                            "multilingual_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": ["lowercase", "stop", "cjk_width"]
                            }
                        }
                    },
                    "similarity": {
                        "custom_bm25": {
                            "type": "BM25",
                            "k1": self.config['search_settings']['bm25_k1'],
                            "b": self.config['search_settings']['bm25_b']
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "doc_id": {
                            "type": "keyword"
                        },
                        "section_id": {
                            "type": "keyword"
                        },
                        "title": {
                            "type": "text",
                            "analyzer": "multilingual_analyzer",
                            "search_analyzer": "multilingual_analyzer",
                            "similarity": "custom_bm25",
                            "fields": {
                                "keyword": {
                                    "type": "keyword"
                                }
                            }
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "multilingual_analyzer", 
                            "search_analyzer": "multilingual_analyzer",
                            "similarity": "custom_bm25"
                        },
                        "summary": {
                            "type": "text",
                            "analyzer": "multilingual_analyzer",
                            "search_analyzer": "multilingual_analyzer", 
                            "similarity": "custom_bm25"
                        },
                        "doc_type": {
                            "type": "keyword"
                        },
                        "page_number": {
                            "type": "integer"
                        },
                        "created_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
                        },
                        "updated_time": {
                            "type": "date",
                            "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
                        },
                        "file_path": {
                            "type": "keyword"
                        },
                        "metadata": {
                            "type": "object",
                            "dynamic": True
                        }
                    }
                }
            }
            
            # 创建索引
            response = self.client.indices.create(
                index=index_name,
                body=mapping
            )
            
            logger.info(f"索引 {index_name} 创建成功: {response}")
            return True
            
        except RequestError as e:
            if e.error == 'resource_already_exists_exception':
                logger.info(f"索引 {index_name} 已存在")
                return True
            else:
                logger.error(f"创建索引失败: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
            return False
    
    def index_document(self, doc_id: str, document: Dict[str, Any]) -> bool:
        """
        索引单个文档
        
        Args:
            doc_id: 文档ID
            document: 文档内容
            
        Returns:
            bool: 索引是否成功
        """
        try:
            index_name = self.config['index_name']
            
            # 添加时间戳
            document['updated_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            response = self.client.index(
                index=index_name,
                id=doc_id,
                body=document,
                refresh=False
            )
            
            logger.debug(f"文档 {doc_id} 索引成功: {response['result']}")
            return True
            
        except Exception as e:
            logger.error(f"索引文档失败 {doc_id}: {str(e)}")
            return False
    
    def bulk_index_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """
        批量索引文档
        
        Args:
            documents: 文档列表，每个文档需包含_id字段
            
        Returns:
            bool: 批量索引是否成功
        """
        try:
            index_name = self.config['index_name']
            
            # 构建批量操作
            bulk_data = []
            for doc in documents:
                doc_id = doc.pop('_id')  # 移除_id字段
                doc['updated_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 添加索引操作
                bulk_data.append({
                    "index": {
                        "_index": index_name,
                        "_id": doc_id
                    }
                })
                bulk_data.append(doc)
            
            # 执行批量操作
            response = self.client.bulk(
                body=bulk_data,
                timeout=self.config['bulk_settings']['timeout'],
                refresh=self.config['bulk_settings']['refresh']
            )
            
            # 检查错误
            if response.get('errors'):
                error_count = 0
                for item in response['items']:
                    if 'index' in item and item['index'].get('error'):
                        error_count += 1
                        logger.error(f"批量索引错误: {item['index']['error']}")
                
                logger.warning(f"批量索引完成，但有 {error_count} 个错误")
                return error_count == 0
            else:
                logger.info(f"批量索引成功: {len(documents)} 个文档")
                return True
                
        except Exception as e:
            logger.error(f"批量索引失败: {str(e)}")
            return False
    
    def search_bm25(self, query: str, filters: Optional[Dict] = None, size: int = 50) -> List[Dict]:
        """
        BM25检索
        
        Args:
            query: 查询字符串
            filters: 过滤条件
            size: 返回结果数量
            
        Returns:
            List[Dict]: 检索结果列表
        """
        try:
            index_name = self.config['index_name']
            search_config = self.config['search_settings']
            
            # 限制返回数量
            size = min(size, search_config['max_size'])
            
            # 构建多字段查询
            field_weights = search_config['field_weights']
            should_queries = []
            
            # 标题字段查询（高权重）
            should_queries.append({
                "match": {
                    "title": {
                        "query": query,
                        "boost": field_weights['title']
                    }
                }
            })
            
            # 内容字段查询
            should_queries.append({
                "match": {
                    "content": {
                        "query": query,
                        "boost": field_weights['content']
                    }
                }
            })
            
            # 摘要字段查询（中权重）
            should_queries.append({
                "match": {
                    "summary": {
                        "query": query,
                        "boost": field_weights['summary']
                    }
                }
            })
            
            # 短语匹配（精确匹配加分）
            should_queries.append({
                "multi_match": {
                    "query": query,
                    "type": "phrase",
                    "fields": ["title^2", "content", "summary^1.5"],
                    "boost": 1.5
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
                "track_total_hits": search_config['track_total_hits'],
                "_source": {
                    "includes": ["doc_id", "section_id", "title", "content", "summary", 
                               "doc_type", "page_number", "file_path", "created_time"]
                }
            }
            
            # 添加过滤条件
            if filters:
                filter_conditions = []
                
                if filters.get('doc_types'):
                    filter_conditions.append({
                        "terms": {"doc_type": filters['doc_types']}
                    })
                
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
                
                if filter_conditions:
                    query_body["query"]["bool"]["filter"] = filter_conditions
            
            # 添加高亮
            if search_config['highlight_enabled']:
                query_body["highlight"] = {
                    "fields": {
                        "title": {},
                        "content": {"fragment_size": 100, "number_of_fragments": 3},
                        "summary": {}
                    },
                    "pre_tags": ["<mark>"],
                    "post_tags": ["</mark>"]
                }
            
            # 执行搜索
            response = self.client.search(
                index=index_name,
                body=query_body
            )
            
            # 处理结果
            results = []
            for hit in response['hits']['hits']:
                result = {
                    'id': hit['_id'],
                    'score': hit['_score'],
                    'source': 'bm25',
                    **hit['_source']
                }
                
                # 添加高亮信息
                if 'highlight' in hit:
                    result['highlight'] = hit['highlight']
                
                results.append(result)
            
            total_hits = response['hits']['total']['value']
            logger.info(f"BM25搜索完成: 查询='{query}', 总命中={total_hits}, 返回={len(results)}")
            
            return results
            
        except Exception as e:
            logger.error(f"BM25搜索失败: {str(e)}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            index_name = self.config['index_name']
            
            response = self.client.delete(
                index=index_name,
                id=doc_id
            )
            
            logger.info(f"文档 {doc_id} 删除成功: {response['result']}")
            return True
            
        except NotFoundError:
            logger.warning(f"文档 {doc_id} 不存在")
            return True
        except Exception as e:
            logger.error(f"删除文档失败 {doc_id}: {str(e)}")
            return False
    
    def refresh_index(self) -> bool:
        """
        刷新索引
        
        Returns:
            bool: 刷新是否成功
        """
        try:
            index_name = self.config['index_name']
            
            response = self.client.indices.refresh(index=index_name)
            logger.info(f"索引刷新成功: {response}")
            return True
            
        except Exception as e:
            logger.error(f"刷新索引失败: {str(e)}")
            return False
    
    def get_index_stats(self) -> Optional[Dict]:
        """
        获取索引统计信息
        
        Returns:
            Optional[Dict]: 索引统计信息
        """
        try:
            index_name = self.config['index_name']
            
            response = self.client.indices.stats(index=index_name)
            stats = response['indices'][index_name]['total']
            
            return {
                'docs_count': stats['docs']['count'],
                'docs_deleted': stats['docs']['deleted'],
                'store_size': stats['store']['size_in_bytes'],
                'indexing_total': stats['indexing']['index_total'],
                'search_query_total': stats['search']['query_total']
            }
            
        except Exception as e:
            logger.error(f"获取索引统计失败: {str(e)}")
            return None
    
    def close(self) -> None:
        """关闭连接"""
        if self.client:
            self.client.close()
            logger.info("OpenSearch连接已关闭")
