"""
PDF向量化服务
负责将PDF文档中的标题和正文内容进行向量化处理，支持GraphRAG查询
"""

import logging
import yaml
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from sentence_transformers import SentenceTransformer

from utils.MilvusManager import MilvusManager


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
            
            # 设置HuggingFace缓存目录环境变量
            os.environ['HF_HOME'] = os.path.abspath(cache_dir)
            os.environ['TRANSFORMERS_CACHE'] = os.path.abspath(cache_dir)
            os.environ['SENTENCE_TRANSFORMERS_HOME'] = os.path.abspath(cache_dir)
            
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
    
    def process_pdf_json_to_vectors(self, json_data: Dict[str, Any], document_id: int) -> Dict[str, Any]:
        """
        将PDF提取的JSON数据处理为向量数据
        titles 用 full_text；fragments 用 blocks[*].text/row_text/caption
        
        Args:
            json_data: JSON数据（包含sections）
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 解析并构建内容单元
            content_units = self._parse_sections_to_content_units(json_data)
            
            if not content_units:
                return {
                    'success': False,
                    'message': '未找到可向量化的内容',
                    'vectorized_count': 0
                }
            
            # 向量化内容单元
            vector_data = []
            for idx, unit in enumerate(content_units):
                if not isinstance(unit, dict):
                    self.logger.error(f"内容单元 {idx} 不是字典类型: {type(unit)}")
                    continue
                
                vector = self._get_text_embedding(unit['content'])
                if vector:
                    vector_id = f"{document_id}_{idx}"
                    
                    # 🔧 提取content_type到独立字段
                    content_type = unit['content_type']
                    
                    vector_data.append({
                        'id': vector_id,
                        'vector': vector,
                        'document_id': document_id,
                        'element_id': unit.get('element_id', ''),
                        'chunk_index': idx,
                        'content': unit['content'],
                        # 🔧 新增：独立的content_type字段
                        'content_type': content_type,
                        'metadata': {
                            'content_type': content_type,  # 保持向后兼容
                            'title': unit.get('title', ''),
                            'page_number': unit.get('page_number', 1),
                            'element_ids': unit.get('element_ids', []),
                            'section_id': unit.get('section_id', ''),
                            'block_type': unit.get('block_type', ''),
                            'process_time': datetime.now().isoformat()
                        }
                    })
            
            if not vector_data:
                return {
                    'success': False,
                    'message': '向量化失败，未能生成有效向量',
                    'vectorized_count': 0
                }
            
            # 存储向量到Milvus
            self.logger.info(f"开始存储 {len(vector_data)} 条向量数据到Milvus")
            success = self.milvus_manager.insert_vectors(vector_data)
            
            if success:
                self.logger.info("Milvus向量存储成功")
                
                self.logger.info(f"PDF向量化完成，文档ID: {document_id}, 向量数量: {len(vector_data)}")
                
                return {
                    'success': True,
                    'message': 'PDF向量化成功',
                    'vectorized_count': len(vector_data),
                    'document_id': document_id
                }
            else:
                self.logger.error("Milvus向量存储失败")
                return {
                    'success': False,
                    'message': 'Milvus向量存储失败',
                    'vectorized_count': 0
                }
            
        except Exception as e:
            self.logger.error(f"PDF向量化处理失败: {str(e)}")
            return {
                'success': False,
                'message': f'PDF向量化处理失败: {str(e)}',
                'vectorized_count': 0
            }
    
    def _parse_sections_to_content_units(self, json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        基于新的section格式解析JSON数据为内容单元
        titles 用 full_text；fragments 用 blocks[*].text/row_text/caption
        
        Args:
            json_data: 新格式的JSON数据（包含sections）
            
        Returns:
            List[Dict[str, Any]]: 内容单元列表
        """
        try:
            sections = json_data.get('sections', [])
            content_units = []
            
            for section in sections:
                section_id = section.get('section_id', '')
                title = section.get('title', '')
                full_text = section.get('full_text', '')
                page_start = section.get('page_start', 1)
                blocks = section.get('blocks', [])
                
                # 1. 创建title级别的内容单元（🔧 修复：只使用标题文本）
                if title.strip():
                    title_unit = {
                        'content': title,  # 🔧 修复：只存储标题文本，不是full_text
                        'content_type': 'title',
                        'title': title,
                        'page_number': page_start,
                        'element_id': section_id,
                        'element_ids': section.get('elem_ids', []),
                        'section_id': section_id
                    }
                    content_units.append(title_unit)
                
                # 🔧 新增：创建section级别的完整内容单元（用于获取完整上下文）
                if full_text.strip() and full_text != title:
                    section_unit = {
                        'content': full_text,
                        'content_type': 'section',  # 新的类型：完整section
                        'title': title,
                        'page_number': page_start,
                        'element_id': section_id + '_full',
                        'element_ids': section.get('elem_ids', []),
                        'section_id': section_id
                    }
                    content_units.append(section_unit)
                
                # 2. 创建fragment级别的内容单元（处理blocks）
                for block in blocks:
                    block_type = block.get('type', '').lower()
                    elem_id = block.get('elem_id', '')
                    page = block.get('page', page_start)
                    
                    # 🔧 修复：跳过标题类型的block，避免重复存储
                    # 标题已经在上面作为title类型处理过了
                    if block_type == 'title':
                        continue
                    
                    # 根据block类型提取文本内容
                    fragment_text = self._extract_block_text(block, block_type)
                    
                    if fragment_text.strip():
                        fragment_unit = {
                            'content': fragment_text,
                            'content_type': 'fragment',
                            'title': title,  # 继承section的title
                            'page_number': page,
                            'element_id': elem_id,
                            'element_ids': [elem_id],
                            'section_id': section_id,
                            'block_type': block_type
                        }
                        content_units.append(fragment_unit)
            
            self.logger.info(f"解析sections完成，生成内容单元: {len(content_units)}")
            return content_units
            
        except Exception as e:
            self.logger.error(f"解析sections失败: {str(e)}")
            return []
    
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
    



