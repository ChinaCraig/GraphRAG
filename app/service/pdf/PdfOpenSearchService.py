"""
PDF OpenSearch索引服务
负责将PDF文档内容索引到OpenSearch，用于BM25检索
"""

import logging
import yaml
from typing import Dict, List, Optional, Any
from datetime import datetime

from utils.OpenSearchManager import OpenSearchManager

logger = logging.getLogger(__name__)


class PdfOpenSearchService:
    """PDF OpenSearch索引服务类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化PDF OpenSearch服务
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_configs()
        
        # 初始化OpenSearch管理器
        self.opensearch_manager = OpenSearchManager()
        
        # 确保索引存在
        self._ensure_index_exists()
    
    def _load_configs(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
            
            with open('config/db.yaml', 'r', encoding='utf-8') as file:
                self.db_config = yaml.safe_load(file)
            
            self.opensearch_config = self.db_config.get('opensearch', {})
            self.index_name = self.opensearch_config.get('index_name', 'graphrag_documents')
            
            self.logger.info("PDF OpenSearch服务配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载PDF OpenSearch服务配置失败: {str(e)}")
            raise
    
    def _ensure_index_exists(self) -> None:
        """确保索引存在，如果不存在则创建"""
        try:
            # 构建索引映射配置
            mapping = self._build_index_mapping()
            
            # 创建索引
            success = self.opensearch_manager.create_index(self.index_name, mapping)
            if success:
                self.logger.info(f"OpenSearch索引 {self.index_name} 已准备就绪")
            else:
                raise Exception(f"创建索引 {self.index_name} 失败")
                
        except Exception as e:
            self.logger.error(f"确保索引存在失败: {str(e)}")
            raise
    
    def _build_index_mapping(self) -> Dict[str, Any]:
        """构建索引映射配置"""
        search_settings = self.opensearch_config.get('search_settings', {})
        index_settings = self.opensearch_config.get('index_settings', {})
        
        mapping = {
            "settings": {
                "number_of_shards": index_settings.get('number_of_shards', 1),
                "number_of_replicas": index_settings.get('number_of_replicas', 0),
                "refresh_interval": index_settings.get('refresh_interval', '1s'),
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
                        "k1": search_settings.get('bm25_k1', 1.2),
                        "b": search_settings.get('bm25_b', 0.75)
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
                    "element_id": {
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
                    "content_type": {
                        "type": "keyword"
                    },
                    "doc_type": {
                        "type": "keyword"
                    },
                    "block_type": {
                        "type": "keyword"
                    },
                    "page_number": {
                        "type": "integer"
                    },
                    "bbox": {
                        "type": "object",
                        "properties": {
                            "x0": {"type": "float"},
                            "y0": {"type": "float"},
                            "x1": {"type": "float"},
                            "y1": {"type": "float"}
                        }
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
        
        return mapping
    
    def process_pdf_json_to_opensearch(self, json_data: Dict[str, Any], document_id: int) -> Dict[str, Any]:
        """
        将PDF提取的JSON数据索引到OpenSearch
        
        Args:
            json_data: JSON数据（包含sections）
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            self.logger.info(f"开始OpenSearch索引构建，文档ID: {document_id}")
            
            # 解析并构建文档单元
            document_groups = self._parse_sections_to_documents(json_data, document_id)
            
            sections_docs = document_groups.get('sections', [])
            fragments_docs = document_groups.get('fragments', [])
            
            if not sections_docs and not fragments_docs:
                return {
                    'success': False,
                    'message': '未找到可索引的内容',
                    'indexed_count': 0
                }
            
            # 合并所有文档
            all_documents = sections_docs + fragments_docs
            
            # 批量索引到OpenSearch
            bulk_settings = self.opensearch_config.get('bulk_settings', {})
            success = self.opensearch_manager.bulk_index_documents(
                index_name=self.index_name,
                documents=all_documents,
                timeout=bulk_settings.get('timeout', '60s'),
                refresh=bulk_settings.get('refresh', False)
            )
            
            if success:
                self.logger.info(f"OpenSearch索引构建完成，文档ID: {document_id}, "
                               f"sections: {len(sections_docs)}, fragments: {len(fragments_docs)}")
                
                return {
                    'success': True,
                    'message': 'OpenSearch索引构建成功',
                    'indexed_count': len(all_documents),
                    'document_id': document_id,
                    'sections_count': len(sections_docs),
                    'fragments_count': len(fragments_docs)
                }
            else:
                return {
                    'success': False,
                    'message': 'OpenSearch索引保存失败',
                    'indexed_count': 0
                }
            
        except Exception as e:
            self.logger.error(f"OpenSearch索引构建失败: {str(e)}")
            return {
                'success': False,
                'message': f'OpenSearch索引构建失败: {str(e)}',
                'indexed_count': 0
            }
    
    def _parse_sections_to_documents(self, json_data: Dict[str, Any], document_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        解析JSON数据为OpenSearch文档单元
        
        Args:
            json_data: JSON数据
            document_id: 文档ID
            
        Returns:
            Dict[str, List[Dict]]: 包含sections和fragments两类文档
        """
        try:
            sections = json_data.get('sections', [])
            sections_docs = []
            fragments_docs = []
            
            for section in sections:
                section_id = section.get('section_id', '')
                section_title = section.get('title', '')
                blocks = section.get('blocks', [])
                
                # 构建section级别的文档（粗粒度）
                section_content_parts = []
                for block in blocks:
                    block_text = self._extract_block_text(block, block.get('type', ''))
                    if block_text.strip():
                        section_content_parts.append(block_text)
                
                if section_content_parts:
                    section_doc = {
                        '_id': f"{document_id}_section_{section_id}",
                        'doc_id': str(document_id),
                        'section_id': section_id,
                        'element_id': section_id,
                        'title': section_title,
                        'content': ' '.join(section_content_parts),
                        'summary': section_title,  # 使用标题作为摘要
                        'content_type': 'section',
                        'doc_type': 'pdf',
                        'block_type': 'section',
                        'page_number': blocks[0].get('page', 1) if blocks else 1,
                        'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'metadata': {
                            'blocks_count': len(blocks),
                            'section_type': 'aggregated'
                        }
                    }
                    sections_docs.append(section_doc)
                
                # 构建block级别的文档（细粒度）
                for block in blocks:
                    elem_id = block.get('elem_id', '')
                    block_type = block.get('type', '')
                    page = block.get('page', 1)
                    bbox = block.get('bbox', {})
                    
                    block_text = self._extract_block_text(block, block_type)
                    if not block_text.strip():
                        continue
                    
                    fragment_doc = {
                        '_id': f"{document_id}_fragment_{elem_id}",
                        'doc_id': str(document_id),
                        'section_id': section_id,
                        'element_id': elem_id,
                        'title': section_title,  # 继承section标题
                        'content': block_text,
                        'summary': block_text[:200] + '...' if len(block_text) > 200 else block_text,
                        'content_type': 'fragment',
                        'doc_type': 'pdf',
                        'block_type': block_type,
                        'page_number': page,
                        'bbox': bbox,
                        'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'metadata': {
                            'section_title': section_title,
                            'parent_section_id': section_id
                        }
                    }
                    fragments_docs.append(fragment_doc)
            
            result = {
                'sections': sections_docs,
                'fragments': fragments_docs
            }
            
            self.logger.info(f"解析sections完成，sections: {len(sections_docs)}, fragments: {len(fragments_docs)}")
            return result
            
        except Exception as e:
            self.logger.error(f"解析sections失败: {str(e)}")
            return {'sections': [], 'fragments': []}
    
    def _extract_block_text(self, block: Dict[str, Any], block_type: str) -> str:
        """
        根据block类型提取文本内容
        
        Args:
            block: block数据
            block_type: block类型
            
        Returns:
            str: 提取的文本内容
        """
        try:
            if block_type == 'table':
                # 对于table类型，使用rows中的row_text
                rows = block.get('rows', [])
                if rows:
                    row_texts = [row.get('row_text', '') for row in rows if row.get('row_text', '').strip()]
                    return ' '.join(row_texts)
                else:
                    return block.get('text', '')
            
            elif block_type == 'figure':
                # 对于figure类型，使用caption
                caption = block.get('caption', '')
                if caption.strip():
                    return caption
                else:
                    return block.get('text', '')
            
            else:
                # 对于其他类型（paragraph等），使用text
                return block.get('text', '')
                
        except Exception as e:
            self.logger.warning(f"提取block文本失败: {str(e)}")
            return block.get('text', '')
    
    def delete_document_from_opensearch(self, document_id: int) -> bool:
        """
        从OpenSearch中删除文档的所有索引项
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 搜索该文档的所有索引项
            query_body = {
                "query": {
                    "term": {
                        "doc_id": str(document_id)
                    }
                },
                "size": 1000  # 假设单个文档不会超过1000个fragment
            }
            
            response = self.opensearch_manager.search(self.index_name, query_body)
            if not response:
                self.logger.warning(f"未找到文档 {document_id} 的索引项")
                return True
            
            # 删除所有找到的文档
            hits = response.get('hits', {}).get('hits', [])
            deleted_count = 0
            
            for hit in hits:
                doc_id = hit['_id']
                success = self.opensearch_manager.delete_document(self.index_name, doc_id)
                if success:
                    deleted_count += 1
            
            self.logger.info(f"从OpenSearch删除文档 {document_id} 完成，删除了 {deleted_count} 个索引项")
            return True
            
        except Exception as e:
            self.logger.error(f"从OpenSearch删除文档失败: {str(e)}")
            return False
    
    def get_index_stats(self) -> Optional[Dict]:
        """
        获取索引统计信息
        
        Returns:
            Optional[Dict]: 索引统计信息
        """
        return self.opensearch_manager.get_index_stats(self.index_name)
