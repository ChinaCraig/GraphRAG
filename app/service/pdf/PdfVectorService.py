"""
PDF向量化服务
负责将PDF文档中的标题和正文内容进行向量化处理，支持GraphRAG查询
"""

import logging
import yaml
import json
import os
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from sentence_transformers import SentenceTransformer

from utils.MilvusManager import MilvusManager
from utils.MySQLManager import MySQLManager


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
        
        # 初始化嵌入模型
        self._init_embedding_model()
        
        # 初始化数据库管理器
        self.milvus_manager = MilvusManager()
        self.mysql_manager = MySQLManager()
    
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
    
    def process_pdf_json_to_vectors(self, json_file_path: str, document_id: int) -> Dict[str, Any]:
        """
        将PDF提取的JSON文件处理为向量数据
        
        Args:
            json_file_path: JSON文件路径
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 加载JSON数据
            with open(json_file_path, 'r', encoding='utf-8') as file:
                pdf_data = json.load(file)
            
            # 解析并构建内容单元
            content_units = self._parse_pdf_json_to_content_units(pdf_data)
            
            if not content_units:
                return {
                    'success': False,
                    'message': '未找到可向量化的内容',
                    'vectorized_count': 0
                }
            
            # 向量化内容单元
            vector_data = []
            for idx, unit in enumerate(content_units):
                # 调试：检查unit类型
                if not isinstance(unit, dict):
                    self.logger.error(f"内容单元 {idx} 不是字典类型: {type(unit)}")
                    continue
                
                vector = self._get_text_embedding(unit['content'])
                if vector:
                    vector_id = f"{document_id}_{idx}"
                    
                    # 调试：验证数据类型
                    self.logger.debug(f"构建向量数据 {idx}: id={vector_id} (类型: {type(vector_id)})")
                    
                    vector_data.append({
                        'id': vector_id,
                        'vector': vector,
                        'document_id': document_id,
                        'chunk_index': idx,
                        'content': unit['content'],
                        'metadata': {
                            'content_type': unit['content_type'],
                            'title': unit.get('title', ''),
                            'page_number': unit.get('page_number', 1),
                            'element_ids': unit.get('element_ids', []),
                            'hierarchy_info': unit.get('hierarchy_info', {}),
                            'coordinates': unit.get('coordinates', {}),
                            'process_time': datetime.now().isoformat()
                        }
                    })
            
            if not vector_data:
                return {
                    'success': False,
                    'message': '向量化失败，未能生成有效向量',
                    'vectorized_count': 0
                }
            
            # 调试：验证向量数据
            self.logger.info(f"准备插入 {len(vector_data)} 条向量数据")
            for i, data in enumerate(vector_data):
                id_value = data.get('id')
                self.logger.debug(f"向量数据 {i}: id={id_value} (类型: {type(id_value)})")
                
                # 检查是否有异常的字段类型
                for key, value in data.items():
                    if isinstance(value, list) and key not in ['vector']:
                        self.logger.warning(f"向量数据 {i}: 字段 {key} 是列表类型: {value}")
            
            # 存储向量到Milvus
            success = self.milvus_manager.insert_vectors(vector_data)
            
            if success:
                # 存储分块信息到MySQL
                self._store_chunks_to_mysql(vector_data, document_id)
                
                self.logger.info(f"PDF向量化完成，文档ID: {document_id}, 向量数量: {len(vector_data)}")
                
                return {
                    'success': True,
                    'message': 'PDF向量化成功',
                    'vectorized_count': len(vector_data),
                    'document_id': document_id
                }
            else:
                return {
                    'success': False,
                    'message': '向量存储失败',
                    'vectorized_count': 0
                }
            
        except Exception as e:
            self.logger.error(f"PDF向量化处理失败: {str(e)}")
            return {
                'success': False,
                'message': f'PDF向量化处理失败: {str(e)}',
                'vectorized_count': 0
            }
    
    def _parse_pdf_json_to_content_units(self, pdf_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析PDF JSON数据，构建完整的内容单元
        每个内容单元包含标题+完整内容，确保查询结果的完整性
        
        Args:
            pdf_data: PDF提取的JSON数据
            
        Returns:
            List[Dict[str, Any]]: 内容单元列表
        """
        try:
            elements = pdf_data.get('elements', [])
            content_units = []
            
            # 构建层级结构：标题 -> 内容段落
            current_title = None
            current_content_parts = []
            
            for element in elements:
                element_type = element.get('type', '').lower()
                element_category = element.get('category', '').lower()
                text = element.get('text', '').strip()
                element_id = element.get('id', '')
                parent_id = element.get('parent_id')
                page_number = element.get('metadata', {}).get('page_number', 1)
                coordinates = element.get('coordinates', {})
                
                # 只有在既没有文本又不是图片的情况下才跳过
                if not text and element_type not in ['image', 'figure']:
                    continue
                
                # 处理标题元素
                if element_type == 'title' or element_category == 'title':
                    # 如果有当前标题和内容，先保存
                    if current_title and current_content_parts:
                        content_unit = self._create_content_unit(
                            current_title, 
                            current_content_parts,
                            'title_with_content'
                        )
                        if content_unit:
                            # 检查是否是分段内容（如果返回多个单元）
                            if isinstance(content_unit, list):
                                content_units.extend(content_unit)
                            else:
                                content_units.append(content_unit)
                    
                    # 设置新标题
                    current_title = {
                        'text': text,
                        'id': element_id,
                        'page_number': page_number,
                        'coordinates': coordinates,
                        'hierarchy_info': {
                            'title_level': element.get('metadata', {}).get('title_level', 1),
                            'hierarchy_depth': element.get('metadata', {}).get('hierarchy_depth', 1)
                        }
                    }
                    current_content_parts = []
                
                # 处理正文内容
                elif element_type in ['narrativetext', 'text'] or element_category in ['narrativetext', 'text']:
                    # 检查是否属于当前标题
                    belongs_to_current_title = (
                        parent_id == (current_title['id'] if current_title else None) or
                        self._is_content_related_to_title(element, current_title)
                    )
                    
                    if belongs_to_current_title and current_title:
                        current_content_parts.append({
                            'text': text,
                            'id': element_id,
                            'page_number': page_number,
                            'coordinates': coordinates,
                            'element_type': element_type
                        })
                    else:
                        # 独立内容段落（没有明确标题）
                        standalone_unit = self._create_content_unit(
                            None,
                            [{
                                'text': text,
                                'id': element_id,
                                'page_number': page_number,
                                'coordinates': coordinates,
                                'element_type': element_type
                            }],
                            'standalone_content'
                        )
                        if standalone_unit:
                            # 检查是否是分段内容
                            if isinstance(standalone_unit, list):
                                content_units.extend(standalone_unit)
                            else:
                                content_units.append(standalone_unit)
                
                # 处理其他类型（表格、图片等）
                elif element_type in ['table', 'image', 'figure'] or element_category in ['table', 'image', 'figure']:
                    if current_title:
                        current_content_parts.append({
                            'text': text,
                            'id': element_id,
                            'page_number': page_number,
                            'coordinates': coordinates,
                            'element_type': element_type
                        })
                    else:
                        # 独立的表格或图片
                        standalone_unit = self._create_content_unit(
                            None,
                            [{
                                'text': text,
                                'id': element_id,
                                'page_number': page_number,
                                'coordinates': coordinates,
                                'element_type': element_type
                            }],
                            element_type
                        )
                        if standalone_unit:
                            # 检查是否是分段内容
                            if isinstance(standalone_unit, list):
                                content_units.extend(standalone_unit)
                            else:
                                content_units.append(standalone_unit)
            
            # 处理最后的标题和内容
            if current_title and current_content_parts:
                content_unit = self._create_content_unit(
                    current_title, 
                    current_content_parts,
                    'title_with_content'
                )
                if content_unit:
                    # 检查是否是分段内容
                    if isinstance(content_unit, list):
                        content_units.extend(content_unit)
                    else:
                        content_units.append(content_unit)
            
            self.logger.info(f"解析PDF JSON完成，生成内容单元: {len(content_units)}")
            
            # 保存content_units到JSON文件
            self._save_content_units_to_json(content_units, pdf_data.get('document_info', {}))

            return content_units
            
        except Exception as e:
            self.logger.error(f"解析PDF JSON失败: {str(e)}")
            return []
    
    def _is_content_related_to_title(self, element: Dict[str, Any], current_title: Optional[Dict[str, Any]]) -> bool:
        """
        判断内容是否与当前标题相关
        
        Args:
            element: 元素
            current_title: 当前标题
            
        Returns:
            bool: 是否相关
        """
        if not current_title:
            return False
        
        try:
            # 检查belongs_to_titles字段
            belongs_to_titles = element.get('metadata', {}).get('belongs_to_titles', [])
            if belongs_to_titles:
                for title_info in belongs_to_titles:
                    if title_info.get('id') == current_title['id']:
                        return True
            
            # 检查页面位置关系（同一页面且位置在标题之后）
            element_page = element.get('metadata', {}).get('page_number', 1)
            title_page = current_title.get('page_number', 1)
            
            if element_page == title_page:
                return True
            elif element_page == title_page + 1:  # 下一页的内容也可能属于当前标题
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"判断内容关联性失败: {str(e)}")
            return False
    
    def _create_content_unit(self, title: Optional[Dict[str, Any]], content_parts: List[Dict[str, Any]], content_type: str) -> Optional[Dict[str, Any]]:
        """
        创建内容单元
        
        Args:
            title: 标题信息
            content_parts: 内容部分列表
            content_type: 内容类型
            
        Returns:
            Optional[Dict[str, Any]]: 内容单元
        """
        try:
            if not content_parts and not title:
                return None
            
            # 构建向量化优化的内容
            vectorizable_parts = []
            element_ids = []
            page_numbers = set()
            coordinates_list = []
            
            # 添加标题
            if title:
                vectorizable_parts.append(f"标题: {title['text']}")
                element_ids.append(title['id'])
                page_numbers.add(title['page_number'])
                if title.get('coordinates'):
                    coordinates_list.append(title['coordinates'])
            
            # 添加内容，根据类型优化处理
            for part in content_parts:
                element_ids.append(part['id'])
                page_numbers.add(part['page_number'])
                if part.get('coordinates'):
                    coordinates_list.append(part['coordinates'])
                
                element_type = part.get('element_type', '').lower()
                
                if element_type in ['text', 'narrativetext'] and part['text']:
                    # 文本内容直接添加
                    vectorizable_parts.append(part['text'])
                
                elif element_type == 'table' and part['text']:
                    # 表格：提取关键信息用于向量化
                    table_keywords = self._extract_table_keywords(part['text'])
                    vectorizable_parts.append(f"表格数据: {table_keywords}")
                
                elif element_type in ['image', 'figure']:
                    if part['text']:
                        # 有OCR文本的图片
                        cleaned_text = self._clean_ocr_text(part['text'])
                        if cleaned_text:
                            vectorizable_parts.append(f"图片内容: {cleaned_text}")
                    else:
                        # 空图片，生成描述
                        image_desc = self._generate_image_description(part)
                        vectorizable_parts.append(f"图片: {image_desc}")
                
                elif part['text']:
                    # 其他类型有文本的元素
                    vectorizable_parts.append(part['text'])
            
            if not vectorizable_parts:
                return None
            
            # 合并优化后的向量化内容
            full_content = '\n'.join(vectorizable_parts)
            
            # 检查内容长度
            max_chunk_size = self.model_config['embedding']['preprocessing']['max_chunk_size']
            if len(full_content) > max_chunk_size:
                # 如果内容太长，进行智能分段 - 返回所有分段单元
                split_units = self._split_long_content(title, content_parts, content_type, max_chunk_size)
                # 返回所有分段单元
                return split_units if split_units else None
            
            content_unit = {
                'content': full_content,
                'content_type': content_type,
                'title': title['text'] if title else '',
                'page_number': min(page_numbers) if page_numbers else 1,
                'element_ids': element_ids,
                'hierarchy_info': title.get('hierarchy_info', {}) if title else {},
                'coordinates': coordinates_list[0] if coordinates_list else {}
            }
            
            return content_unit
            
        except Exception as e:
            self.logger.error(f"创建内容单元失败: {str(e)}")
            return None
    
    def _split_long_content(self, title: Optional[Dict[str, Any]], content_parts: List[Dict[str, Any]], content_type: str, max_size: int) -> List[Dict[str, Any]]:
        """
        分割长内容为多个单元，确保每个单元都包含标题信息
        
        Args:
            title: 标题信息
            content_parts: 内容部分列表
            content_type: 内容类型
            max_size: 最大大小
            
        Returns:
            List[Dict[str, Any]]: 分割后的内容单元列表
        """
        try:
            title_text = f"标题: {title['text']}" if title else ""
            title_length = len(title_text)
            
            # 为内容留出空间
            available_size = max_size - title_length - 10  # 留出一些缓冲
            
            units = []
            current_parts = []
            current_length = 0
            
            for part in content_parts:
                part_text = part['text']
                part_length = len(part_text)
                
                # 如果加上这个部分会超出长度限制
                if current_length + part_length > available_size and current_parts:
                    # 创建当前单元
                    unit = self._create_single_unit(title, current_parts, content_type)
                    if unit:
                        units.append(unit)
                    
                    # 开始新单元
                    current_parts = [part]
                    current_length = part_length
                else:
                    current_parts.append(part)
                    current_length += part_length
            
            # 处理最后的部分
            if current_parts:
                unit = self._create_single_unit(title, current_parts, content_type)
                if unit:
                    units.append(unit)
            
            return units
            
        except Exception as e:
            self.logger.error(f"分割长内容失败: {str(e)}")
            return []
    
    def _create_single_unit(self, title: Optional[Dict[str, Any]], content_parts: List[Dict[str, Any]], content_type: str) -> Optional[Dict[str, Any]]:
        """创建单个内容单元"""
        try:
            full_content_parts = []
            element_ids = []
            page_numbers = set()
            
            # 添加标题
            if title:
                full_content_parts.append(f"标题: {title['text']}")
                element_ids.append(title['id'])
                page_numbers.add(title['page_number'])
            
            # 添加内容
            for part in content_parts:
                if part['text']:
                    full_content_parts.append(part['text'])
                    element_ids.append(part['id'])
                    page_numbers.add(part['page_number'])
            
            if not full_content_parts:
                return None
            
            return {
                'content': '\n'.join(full_content_parts),
                'content_type': content_type,
                'title': title['text'] if title else '',
                'page_number': min(page_numbers) if page_numbers else 1,
                'element_ids': element_ids,
                'hierarchy_info': title.get('hierarchy_info', {}) if title else {},
                'coordinates': title.get('coordinates', {}) if title else {}
            }
            
        except Exception as e:
            self.logger.error(f"创建单个内容单元失败: {str(e)}")
            return None
    
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
            
            if not processed_text:
                return None
            
            # 生成向量
            embedding = self.embedding_model.encode(
                processed_text,
                normalize_embeddings=self.normalize
            )
            
            return embedding.tolist()
            
        except Exception as e:
            self.logger.error(f"获取文本向量失败: {str(e)}")
            return None
    
    def _extract_table_keywords(self, table_text: str) -> str:
        """
        从表格文本中提取关键信息用于向量化
        
        Args:
            table_text: 表格的扁平化文本
            
        Returns:
            str: 提取的关键词字符串
        """
        try:
            import re
            
            keywords = []
            
            # 提取百分比数据
            percentages = re.findall(r'\d+%-\d+%|\d+%', table_text)
            keywords.extend(percentages)
            
            # 提取数值数据
            numbers = re.findall(r'\d+\.\d+|\d+', table_text)
            keywords.extend(numbers[:5])  # 只取前5个数值，避免过多
            
            # 提取中文关键词
            chinese_terms = re.findall(r'[\u4e00-\u9fff]+', table_text)
            keywords.extend([term for term in chinese_terms if len(term) >= 2][:8])
            
            # 提取英文关键词
            english_terms = re.findall(r'[A-Za-z]{2,}', table_text)
            keywords.extend(english_terms[:5])
            
            return ' '.join(keywords)
            
        except Exception as e:
            self.logger.warning(f"提取表格关键词失败: {str(e)}")
            return table_text[:100]  # 失败时返回前100字符
    
    def _clean_ocr_text(self, ocr_text: str) -> str:
        """
        清理OCR识别的文本，移除明显错误
        
        Args:
            ocr_text: OCR识别的原始文本
            
        Returns:
            str: 清理后的文本
        """
        try:
            import re
            
            if not ocr_text:
                return ""
            
            # 移除明显的OCR错误模式
            # 移除单个字符和乱码
            text = re.sub(r'\b[a-zA-Z]\b', '', ocr_text)  # 移除单个英文字母
            text = re.sub(r'[^\w\s\u4e00-\u9fff%()-]', ' ', text)  # 保留基本字符
            text = re.sub(r'\s+', ' ', text)  # 合并多个空格
            
            # 保留有意义的内容（数字、百分比、中英文词汇）
            meaningful_parts = []
            parts = text.split()
            
            for part in parts:
                # 保留数字、百分比
                if re.match(r'\d+%?|\d+\.\d+', part):
                    meaningful_parts.append(part)
                # 保留2个字符以上的中文词
                elif re.match(r'[\u4e00-\u9fff]{2,}', part):
                    meaningful_parts.append(part)
                # 保留3个字符以上的英文词
                elif re.match(r'[A-Za-z]{3,}', part):
                    meaningful_parts.append(part)
            
            cleaned = ' '.join(meaningful_parts)
            return cleaned.strip() if len(cleaned) >= 3 else ""
            
        except Exception as e:
            self.logger.warning(f"清理OCR文本失败: {str(e)}")
            return ocr_text
    
    def _generate_image_description(self, image_part: Dict[str, Any]) -> str:
        """
        为空图片生成描述
        
        Args:
            image_part: 图片元素信息
            
        Returns:
            str: 图片描述
        """
        try:
            element_id = image_part.get('id', '')
            coordinates = image_part.get('coordinates', {})
            
            # 根据位置和ID推断图片类型
            if '0041' in element_id or '0042' in element_id or '0043' in element_id or '0044' in element_id:
                return "[二维码图片]"
            elif coordinates:
                # 根据坐标位置推断
                points = coordinates.get('points', [])
                if points and len(points) >= 2:
                    width = abs(points[2][0] - points[0][0]) if len(points) > 2 else 0
                    height = abs(points[1][1] - points[0][1]) if len(points) > 1 else 0
                    
                    if width < 200 and height < 200:
                        return "[小图标/Logo]"
                    else:
                        return "[图表/示意图]"
            
            return "[图片内容]"
            
        except Exception as e:
            self.logger.warning(f"生成图片描述失败: {str(e)}")
            return "[图片内容]"
    
    def _preprocess_text(self, text: str) -> str:
        """
        文本预处理
        
        Args:
            text: 原始文本
            
        Returns:
            str: 预处理后的文本
        """
        try:
            if not text:
                return ""
            
            preprocessing_config = self.model_config['embedding']['preprocessing']
            
            # 清理文本
            if preprocessing_config.get('clean_text', True):
                # 移除多余的空白字符
                text = ' '.join(text.split())
                
                # 移除特殊字符（如果配置要求）
                if preprocessing_config.get('remove_special_chars', False):
                    import re
                    text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
            
            # 转换为小写（如果配置要求）
            if preprocessing_config.get('lowercase', False):
                text = text.lower()
            
            # 限制最大长度
            max_length = self.model_config['embedding']['max_length']
            if len(text) > max_length:
                text = text[:max_length]
            
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"文本预处理失败: {str(e)}")
            return text
    
    def _store_chunks_to_mysql(self, vector_data: List[Dict[str, Any]], document_id: int) -> None:
        """
        存储分块信息到MySQL
        
        Args:
            vector_data: 向量数据列表
            document_id: 文档ID
        """
        try:
            for data in vector_data:
                chunk_data = {
                    'document_id': document_id,
                    'chunk_index': data['chunk_index'],
                    'content': data['content'],
                    'vector_id': data['id'],
                    'create_time': datetime.now()
                }
                
                self.mysql_manager.insert_data('document_chunks', chunk_data)
            
            self.logger.info(f"文档分块信息存储成功，文档ID: {document_id}, 分块数量: {len(vector_data)}")
            
        except Exception as e:
            self.logger.error(f"存储文档分块信息失败: {str(e)}")
    
    def search_similar_content(self, query: str, top_k: int = 10, document_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        搜索相似内容
        
        Args:
            query: 查询文本
            top_k: 返回的相似内容数量
            document_id: 可选的文档ID过滤
            
        Returns:
            List[Dict[str, Any]]: 相似内容列表
        """
        try:
            # 生成查询向量
            query_vector = self._get_text_embedding(query)
            if not query_vector:
                return []
            
            # 构建过滤表达式
            expr = None
            if document_id is not None:
                expr = f"document_id == {document_id}"
            
            # 向量搜索
            search_results = self.milvus_manager.search_vectors(
                query_vectors=[query_vector],
                top_k=top_k,
                expr=expr
            )
            
            # 增强结果信息
            enhanced_results = []
            for result in search_results:
                metadata = result.get('metadata', {})
                enhanced_result = {
                    'id': result['id'],
                    'content': result['content'],
                    'score': result['score'],
                    'document_id': result['document_id'],
                    'chunk_index': result['chunk_index'],
                    'content_type': metadata.get('content_type', 'unknown'),
                    'title': metadata.get('title', ''),
                    'page_number': metadata.get('page_number', 1),
                    'hierarchy_info': metadata.get('hierarchy_info', {})
                }
                enhanced_results.append(enhanced_result)
            
            self.logger.info(f"相似内容搜索完成，查询: {query[:50]}..., 结果数量: {len(enhanced_results)}")
            return enhanced_results
            
        except Exception as e:
            self.logger.error(f"搜索相似内容失败: {str(e)}")
            return []
    
    def get_document_vector_stats(self, document_id: int) -> Dict[str, Any]:
        """
        获取文档的向量统计信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 向量统计信息
        """
        try:
            # 查询向量数量
            expr = f"document_id == {document_id}"
            results = self.milvus_manager.search_vectors(
                query_vectors=[[0.0] * self.dimension],  # 使用零向量进行查询以获取所有匹配的向量
                top_k=10000,  # 设置一个足够大的值
                expr=expr
            )
            
            total_vectors = len(results)
            
            # 统计内容类型分布
            content_types = {}
            for result in results:
                metadata = result.get('metadata', {})
                content_type = metadata.get('content_type', 'unknown')
                content_types[content_type] = content_types.get(content_type, 0) + 1
            
            # 查询MySQL中的分块信息
            chunk_query = "SELECT COUNT(*) as count FROM document_chunks WHERE document_id = :doc_id"
            chunk_result = self.mysql_manager.execute_query(chunk_query, {'doc_id': document_id})
            mysql_chunks = chunk_result[0]['count'] if chunk_result else 0
            
            stats = {
                'document_id': document_id,
                'total_vectors': total_vectors,
                'mysql_chunks': mysql_chunks,
                'content_types': content_types,
                'dimension': self.dimension
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取文档向量统计信息失败: {str(e)}")
            return {}
    
    def delete_document_vectors(self, document_id: int) -> bool:
        """
        删除文档的所有向量数据
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            # 删除Milvus中的向量
            expr = f"document_id == {document_id}"
            success = self.milvus_manager.delete_vectors(expr)
            
            if success:
                # 删除MySQL中的分块信息
                self.mysql_manager.delete_data(
                    'document_chunks',
                    'document_id = :doc_id',
                    {'doc_id': document_id}
                )
                
                self.logger.info(f"文档向量数据删除成功，文档ID: {document_id}")
                return True
            else:
                return False
            
        except Exception as e:
            self.logger.error(f"删除文档向量数据失败: {str(e)}")
            return False
    
    def _save_content_units_to_json(self, content_units: List[Dict[str, Any]], document_info: Dict[str, Any]) -> None:
        """
        将content_units保存为JSON文件
        
        Args:
            content_units: 内容单元列表
            document_info: 文档信息
        """
        try:
            # 加载Unstructured配置
            with open('config/Unstructured.yaml', 'r', encoding='utf-8') as file:
                unstructured_config = yaml.safe_load(file)
            
            # 获取输出目录路径
            output_dir = unstructured_config['pdf']['pdf_json_output_dir_path']
            if not output_dir:
                self.logger.warning("pdf_json_output_dir_path 未配置，跳过保存content_units")
                return
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 获取文件名（去除扩展名）
            filename = document_info.get('filename', 'unknown_document')
            if filename.endswith('.pdf'):
                filename = filename[:-4]  # 移除.pdf扩展名
            
            # 构建输出文件路径
            output_filename = f"{filename}_content_units.json"
            output_path = os.path.join(output_dir, output_filename)
            
            # 将content_units转换为JSON并保存
            with open(output_path, 'w', encoding='utf-8') as file:
                json.dump(content_units, file, ensure_ascii=False, indent=2)
            
            self.logger.info(f"content_units已保存到: {output_path}")
            
        except Exception as e:
            self.logger.error(f"保存content_units到JSON文件失败: {str(e)}")