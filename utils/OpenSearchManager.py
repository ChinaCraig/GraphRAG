"""
OpenSearch管理器
负责OpenSearch连接和基础操作
"""

import logging
import yaml
from typing import Dict, List, Optional, Any
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import RequestError, NotFoundError

logger = logging.getLogger(__name__)


class OpenSearchManager:
    """OpenSearch管理器类 - 只负责连接和基础操作"""
    
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
    
    def create_index(self, index_name: str, mapping: Dict[str, Any]) -> bool:
        """
        创建索引
        
        Args:
            index_name: 索引名称
            mapping: 索引映射配置
            
        Returns:
            bool: 创建是否成功
        """
        try:
            # 检查索引是否已存在
            if self.client.indices.exists(index=index_name):
                logger.info(f"索引 {index_name} 已存在")
                return True
            
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
    
    def index_document(self, index_name: str, doc_id: str, document: Dict[str, Any]) -> bool:
        """
        索引单个文档
        
        Args:
            index_name: 索引名称
            doc_id: 文档ID
            document: 文档内容
            
        Returns:
            bool: 索引是否成功
        """
        try:
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
    
    def bulk_index_documents(self, index_name: str, documents: List[Dict[str, Any]], 
                           timeout = 60, refresh: bool = False) -> bool:
        """
        批量索引文档
        
        Args:
            index_name: 索引名称
            documents: 文档列表，每个文档需包含_id字段
            timeout: 超时时间（秒，可以是int、float或字符串如'60s'）
            refresh: 是否立即刷新
            
        Returns:
            bool: 批量索引是否成功
        """
        try:
            # 解析超时时间
            parsed_timeout = self._parse_timeout(timeout)
            
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
                timeout=parsed_timeout,
                refresh=refresh
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
    
    def search(self, index_name: str, query_body: Dict[str, Any]) -> Optional[Dict]:
        """
        执行搜索查询
        
        Args:
            index_name: 索引名称
            query_body: 查询体
            
        Returns:
            Optional[Dict]: 搜索结果
        """
        try:
            response = self.client.search(
                index=index_name,
                body=query_body
            )
            return response
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return None
    
    def delete_document(self, index_name: str, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            index_name: 索引名称
            doc_id: 文档ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
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
    
    def refresh_index(self, index_name: str) -> bool:
        """
        刷新索引
        
        Args:
            index_name: 索引名称
            
        Returns:
            bool: 刷新是否成功
        """
        try:
            response = self.client.indices.refresh(index=index_name)
            logger.info(f"索引刷新成功: {response}")
            return True
            
        except Exception as e:
            logger.error(f"刷新索引失败: {str(e)}")
            return False
    
    def get_index_stats(self, index_name: str) -> Optional[Dict]:
        """
        获取索引统计信息
        
        Args:
            index_name: 索引名称
            
        Returns:
            Optional[Dict]: 索引统计信息
        """
        try:
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
    
    def _parse_timeout(self, timeout) -> int:
        """
        解析超时时间为秒数
        
        Args:
            timeout: 超时时间，可以是int、float或字符串（如'60s'、'1m'等）
            
        Returns:
            int: 超时秒数
        """
        if isinstance(timeout, (int, float)):
            return int(timeout)
        
        if isinstance(timeout, str):
            import re
            # 解析字符串格式的时间
            match = re.match(r'^(\d+(?:\.\d+)?)([smh]?)$', timeout.lower())
            if match:
                value, unit = match.groups()
                value = float(value)
                
                if unit == 'm':  # 分钟
                    return int(value * 60)
                elif unit == 'h':  # 小时
                    return int(value * 3600)
                else:  # 默认为秒
                    return int(value)
            else:
                logger.warning(f"无法解析超时时间格式: {timeout}，使用默认值60秒")
                return 60
        
        # 默认值
        logger.warning(f"不支持的超时时间类型: {type(timeout)}，使用默认值60秒")
        return 60
    
    def close(self) -> None:
        """关闭连接"""
        if self.client:
            self.client.close()
            logger.info("OpenSearch连接已关闭")
