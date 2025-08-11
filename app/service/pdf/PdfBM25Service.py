"""
PDF BM25倒排索引服务
负责基于BM25算法构建文档的倒排索引，支持关键词检索
"""

import logging
import yaml
import os
import json
import jieba
import math
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from collections import defaultdict, Counter


class PdfBM25Service:
    """PDF BM25倒排索引服务类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化PDF BM25服务
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_configs()
        
        # BM25参数
        self.k1 = 1.5  # 词频饱和参数
        self.b = 0.75  # 长度归一化参数
        
        # 停用词
        self.stop_words = self._load_stop_words()
    
    def _load_configs(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
            
            self.logger.info("PDF BM25服务配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载PDF BM25服务配置失败: {str(e)}")
            raise
    
    def _load_stop_words(self) -> Set[str]:
        """
        加载停用词表
        
        Returns:
            Set[str]: 停用词集合
        """
        try:
            # 基础停用词
            stop_words = {
                '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '个', '上', '也', '很', '到', '说', 
                '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '只', '能', '下', '对', '于', '为',
                '与', '及', '或', '但', '可', '以', '而', '且', '所', '其', '如', '若', '等', '即', '又', '还', '更',
                '最', '很', '非常', '十分', '相当', '比较', '太', '挺', '蛮', '特别', '尤其', '格外', '异常'
            }
            
            self.logger.info(f"停用词加载完成，共{len(stop_words)}个")
            return stop_words
            
        except Exception as e:
            self.logger.error(f"加载停用词失败: {str(e)}")
            return set()
    
    def process_pdf_json_to_bm25(self, json_data: Dict[str, Any], document_id: int) -> Dict[str, Any]:
        """
        将PDF提取的JSON数据处理为BM25倒排索引
        
        Args:
            json_data: JSON数据（包含sections）
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 解析并构建文档单元（分为sections和fragments两类）
            document_groups = self._parse_sections_to_documents(json_data)
            
            sections_docs = document_groups.get('sections', [])
            fragments_docs = document_groups.get('fragments', [])
            
            if not sections_docs and not fragments_docs:
                return {
                    'success': False,
                    'message': '未找到可索引的内容',
                    'indexed_count': 0
                }
            
            # 分别构建两类BM25索引
            bm25_indexes = {}
            total_indexed = 0
            
            if sections_docs:
                sections_index = self._build_bm25_index(sections_docs, 'sections')
                bm25_indexes['sections_bm25'] = sections_index
                total_indexed += len(sections_docs)
            
            if fragments_docs:
                fragments_index = self._build_bm25_index(fragments_docs, 'fragments')
                bm25_indexes['fragments_bm25'] = fragments_index
                total_indexed += len(fragments_docs)
            
            # 保存索引
            index_saved = self._save_bm25_indexes(bm25_indexes, document_id)
            
            if index_saved:
                self.logger.info(f"BM25索引构建完成，文档ID: {document_id}, sections: {len(sections_docs)}, fragments: {len(fragments_docs)}")
                
                return {
                    'success': True,
                    'message': 'BM25倒排索引构建成功',
                    'indexed_count': total_indexed,
                    'document_id': document_id,
                    'sections_count': len(sections_docs),
                    'fragments_count': len(fragments_docs)
                }
            else:
                return {
                    'success': False,
                    'message': 'BM25索引保存失败',
                    'indexed_count': 0
                }
            
        except Exception as e:
            self.logger.error(f"BM25倒排索引处理失败: {str(e)}")
            return {
                'success': False,
                'message': f'BM25倒排索引处理失败: {str(e)}',
                'indexed_count': 0
            }
    
    def _parse_sections_to_documents(self, json_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        解析JSON数据为BM25文档单元，区分sections和fragments两类
        
        Args:
            json_data: 新格式的JSON数据（包含sections）
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: 分类的文档单元 {'sections': [...], 'fragments': [...]}
        """
        try:
            sections = json_data.get('sections', [])
            sections_docs = []  # sections_bm25类型文档
            fragments_docs = []  # fragments_bm25类型文档
            
            for section_idx, section in enumerate(sections):
                section_id = section.get('section_id', '')
                title = section.get('title', '')
                full_text = section.get('full_text', '')
                page_start = section.get('page_start', 1)
                blocks = section.get('blocks', [])
                
                # 1. Sections类型：将section的full_text作为一个文档（对标titles）
                if full_text.strip():
                    doc = {
                        'id': f"{section_id}_full",
                        'content': full_text,
                        'content_type': 'section',  # 使用content_type字段
                        'title': title,
                        'page_number': page_start,
                        'section_id': section_id,
                        'element_ids': section.get('elem_ids', [])
                    }
                    sections_docs.append(doc)
                
                # 2. Fragments类型：将每个block作为独立文档（对标fragments）
                for block_idx, block in enumerate(blocks):
                    block_type = block.get('type', '').lower()
                    elem_id = block.get('elem_id', '')
                    page = block.get('page', page_start)
                    
                    # 根据block类型提取文本内容
                    block_text = self._extract_block_text(block, block_type)
                    
                    if block_text.strip():
                        doc = {
                            'id': f"{section_id}_{elem_id}",
                            'content': block_text,
                            'content_type': 'fragment',  # 使用content_type字段
                            'block_type': block_type,
                            'title': title,
                            'page_number': page,
                            'section_id': section_id,
                            'element_id': elem_id
                        }
                        fragments_docs.append(doc)
            
            result = {
                'sections': sections_docs,
                'fragments': fragments_docs
            }
            
            self.logger.info(f"解析sections完成，sections_bm25: {len(sections_docs)}, fragments_bm25: {len(fragments_docs)}")
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
                    # 如果没有rows，回退到text
                    return block.get('text', '')
            
            elif block_type == 'figure':
                # 对于figure类型，使用caption
                caption = block.get('caption', '')
                if caption.strip():
                    return caption
                else:
                    # 如果没有caption，回退到text
                    return block.get('text', '')
            
            else:
                # 对于其他类型（paragraph等），使用text
                return block.get('text', '')
                
        except Exception as e:
            self.logger.warning(f"提取block文本失败: {str(e)}")
            return block.get('text', '')
    
    def _build_bm25_index(self, documents: List[Dict[str, Any]], index_type: str) -> Dict[str, Any]:
        """
        构建BM25倒排索引
        
        Args:
            documents: 文档列表
            index_type: 索引类型（'sections'或'fragments'）
            
        Returns:
            Dict[str, Any]: BM25索引
        """
        try:
            # 分词和预处理所有文档
            processed_docs = []
            doc_lengths = []
            
            for doc in documents:
                tokens = self._tokenize_and_filter(doc['content'])
                processed_docs.append({
                    'id': doc['id'],
                    'tokens': tokens,
                    'length': len(tokens),
                    'metadata': {
                        'content_type': doc.get('content_type', ''),
                        'title': doc.get('title', ''),
                        'page_number': doc.get('page_number', 1),
                        'section_id': doc.get('section_id', ''),
                        'element_id': doc.get('element_id', ''),
                        'block_type': doc.get('block_type', '')
                    }
                })
                doc_lengths.append(len(tokens))
            
            # 计算平均文档长度
            avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0
            
            # 构建词汇表和倒排索引
            vocabulary = set()
            inverted_index = defaultdict(list)
            
            for doc_idx, doc in enumerate(processed_docs):
                doc_id = doc['id']
                tokens = doc['tokens']
                token_counts = Counter(tokens)
                
                for token in token_counts:
                    vocabulary.add(token)
                    inverted_index[token].append({
                        'doc_id': doc_id,
                        'doc_idx': doc_idx,
                        'tf': token_counts[token],
                        'doc_length': doc['length']
                    })
            
            # 计算IDF值
            total_docs = len(processed_docs)
            idf_values = {}
            
            for term in vocabulary:
                df = len(inverted_index[term])  # 包含该词的文档数
                idf = math.log((total_docs - df + 0.5) / (df + 0.5))
                idf_values[term] = idf
            
            # 构建完整的BM25索引
            bm25_index = {
                'index_type': index_type,  # 添加索引类型标识
                'documents': processed_docs,
                'inverted_index': dict(inverted_index),
                'idf_values': idf_values,
                'vocabulary': list(vocabulary),
                'total_documents': total_docs,
                'avg_doc_length': avg_doc_length,
                'parameters': {
                    'k1': self.k1,
                    'b': self.b
                },
                'created_time': datetime.now().isoformat()
            }
            
            self.logger.info(f"{index_type}_bm25索引构建完成，词汇量: {len(vocabulary)}, 文档数: {total_docs}")
            return bm25_index
            
        except Exception as e:
            self.logger.error(f"构建BM25索引失败: {str(e)}")
            return {}
    
    def _tokenize_and_filter(self, text: str) -> List[str]:
        """
        分词和过滤
        
        Args:
            text: 输入文本
            
        Returns:
            List[str]: 分词结果
        """
        try:
            if not text or not text.strip():
                return []
            
            # 使用jieba分词
            tokens = jieba.lcut(text)
            
            # 过滤停用词、标点符号和长度过短的词
            filtered_tokens = []
            for token in tokens:
                token = token.strip()
                if (len(token) >= 2 and 
                    token not in self.stop_words and 
                    not token.isspace() and
                    not all(c in '，。；：""''（）【】！？、' for c in token)):
                    filtered_tokens.append(token.lower())
            
            return filtered_tokens
            
        except Exception as e:
            self.logger.warning(f"分词过滤失败: {str(e)}")
            return []
    
    def _save_bm25_indexes(self, bm25_indexes: Dict[str, Dict[str, Any]], document_id: int) -> bool:
        """
        保存分类的BM25索引到文件
        
        Args:
            bm25_indexes: 分类的BM25索引数据 {'sections_bm25': {...}, 'fragments_bm25': {...}}
            document_id: 文档ID
            
        Returns:
            bool: 保存成功返回True
        """
        try:
            # 获取输出目录
            upload_folder = self.config.get('file', {}).get('upload_folder', 'upload')
            bm25_dir = os.path.join(upload_folder, 'bm25')
            
            # 确保目录存在
            if not os.path.exists(bm25_dir):
                os.makedirs(bm25_dir, exist_ok=True)
                self.logger.info(f"创建BM25输出目录: {bm25_dir}")
            
            # 保存每个分类的索引
            saved_count = 0
            for index_name, index_data in bm25_indexes.items():
                # 生成输出文件名：bm25_sections_123.json, bm25_fragments_123.json
                index_filename = f"bm25_{index_name.replace('_bm25', '')}_{document_id}.json"
                index_file_path = os.path.join(bm25_dir, index_filename)
                
                # 保存索引文件
                with open(index_file_path, 'w', encoding='utf-8') as f:
                    json.dump(index_data, f, ensure_ascii=False, indent=2, default=str)
                
                self.logger.info(f"{index_name}索引已保存到: {index_file_path}")
                saved_count += 1
            
            # 同时保存一个合并的索引文件（保持兼容性）
            combined_index = {
                'document_id': document_id,
                'indexes': bm25_indexes,
                'created_time': datetime.now().isoformat()
            }
            
            combined_filename = f"bm25_combined_{document_id}.json"
            combined_path = os.path.join(bm25_dir, combined_filename)
            
            with open(combined_path, 'w', encoding='utf-8') as f:
                json.dump(combined_index, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"合并BM25索引已保存到: {combined_path}")
            
            return saved_count > 0
            
        except Exception as e:
            self.logger.error(f"保存BM25索引失败: {str(e)}")
            return False
    
    def search(self, query: str, document_id: int, search_type: str = 'both', top_k: int = 10) -> Dict[str, Any]:
        """
        BM25搜索，支持指定搜索类型
        
        Args:
            query: 查询文本
            document_id: 文档ID
            search_type: 搜索类型 ('sections', 'fragments', 'both')
            top_k: 返回结果数量
            
        Returns:
            Dict[str, Any]: 搜索结果，包含各类型的结果
        """
        try:
            query_tokens = self._tokenize_and_filter(query)
            if not query_tokens:
                return {'sections': [], 'fragments': [], 'query': query}
            
            results = {'sections': [], 'fragments': [], 'query': query}
            
            # 搜索sections索引
            if search_type in ['sections', 'both']:
                sections_index = self._load_bm25_index(document_id, 'sections')
                if sections_index:
                    sections_scores = self._calculate_bm25_scores(query_tokens, sections_index)
                    sections_results = self._format_search_results(sections_scores, sections_index, top_k, 'sections')
                    results['sections'] = sections_results
            
            # 搜索fragments索引
            if search_type in ['fragments', 'both']:
                fragments_index = self._load_bm25_index(document_id, 'fragments')
                if fragments_index:
                    fragments_scores = self._calculate_bm25_scores(query_tokens, fragments_index)
                    fragments_results = self._format_search_results(fragments_scores, fragments_index, top_k, 'fragments')
                    results['fragments'] = fragments_results
            
            total_results = len(results['sections']) + len(results['fragments'])
            self.logger.info(f"BM25搜索完成，查询: {query}, 类型: {search_type}, 结果数量: {total_results}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"BM25搜索失败: {str(e)}")
            return {'sections': [], 'fragments': [], 'query': query, 'error': str(e)}
    
    def _load_bm25_index(self, document_id: int, index_type: str) -> Dict[str, Any]:
        """
        加载指定类型的BM25索引
        
        Args:
            document_id: 文档ID
            index_type: 索引类型（'sections'或'fragments'）
            
        Returns:
            Dict[str, Any]: BM25索引
        """
        try:
            upload_folder = self.config.get('file', {}).get('upload_folder', 'upload')
            bm25_dir = os.path.join(upload_folder, 'bm25')
            index_filename = f"bm25_{index_type}_{document_id}.json"
            index_file_path = os.path.join(bm25_dir, index_filename)
            
            if not os.path.exists(index_file_path):
                self.logger.warning(f"{index_type}_bm25索引文件不存在: {index_file_path}")
                return {}
            
            with open(index_file_path, 'r', encoding='utf-8') as f:
                bm25_index = json.load(f)
            
            return bm25_index
            
        except Exception as e:
            self.logger.error(f"加载{index_type}_bm25索引失败: {str(e)}")
            return {}
    
    def _calculate_bm25_scores(self, query_tokens: List[str], bm25_index: Dict[str, Any]) -> Dict[str, float]:
        """
        计算BM25分数
        
        Args:
            query_tokens: 查询词列表
            bm25_index: BM25索引
            
        Returns:
            Dict[str, float]: 文档ID到分数的映射
        """
        try:
            inverted_index = bm25_index['inverted_index']
            idf_values = bm25_index['idf_values']
            avg_doc_length = bm25_index['avg_doc_length']
            k1 = bm25_index['parameters']['k1']
            b = bm25_index['parameters']['b']
            
            scores = defaultdict(float)
            
            for token in query_tokens:
                if token not in inverted_index:
                    continue
                
                idf = idf_values.get(token, 0)
                
                for posting in inverted_index[token]:
                    doc_id = posting['doc_id']
                    tf = posting['tf']
                    doc_length = posting['doc_length']
                    
                    # BM25公式
                    numerator = tf * (k1 + 1)
                    denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))
                    
                    bm25_score = idf * (numerator / denominator)
                    scores[doc_id] += bm25_score
            
            return dict(scores)
            
        except Exception as e:
            self.logger.error(f"计算BM25分数失败: {str(e)}")
            return {}
    
    def _format_search_results(self, scores: Dict[str, float], bm25_index: Dict[str, Any], 
                              top_k: int, result_type: str) -> List[Dict[str, Any]]:
        """
        格式化搜索结果
        
        Args:
            scores: 文档分数字典
            bm25_index: BM25索引数据
            top_k: 返回结果数量
            result_type: 结果类型标识
            
        Returns:
            List[Dict[str, Any]]: 格式化的搜索结果
        """
        try:
            # 排序并返回前top_k个结果
            sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            
            # 构建文档映射
            documents = {doc['id']: doc for doc in bm25_index.get('documents', [])}
            
            results = []
            for doc_id, score in sorted_results:
                if doc_id in documents:
                    doc = documents[doc_id]
                    
                    # 获取内容摘要（前100个字符）
                    content = doc.get('content', '')
                    content_preview = content[:100] + '...' if len(content) > 100 else content
                    
                    result = {
                        'doc_id': doc_id,
                        'score': round(score, 4),
                        'content_preview': content_preview,
                        'content_type': doc.get('content_type', result_type),
                        'metadata': doc.get('metadata', {}),
                        'title': doc.get('title', ''),
                        'page_number': doc.get('page_number', 1),
                        'section_id': doc.get('section_id', ''),
                        'element_id': doc.get('element_id', ''),
                        'block_type': doc.get('block_type', '')
                    }
                    results.append(result)
            
            return results
            
        except Exception as e:
            self.logger.error(f"格式化搜索结果失败: {str(e)}")
            return []
