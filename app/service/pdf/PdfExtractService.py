"""
PDF内容提取服务 - 基于Unstructured库实现
负责从PDF文件中提取文本、图片、表格等内容
"""

import logging
import os
import yaml
from typing import Dict, Any, List
from datetime import datetime
import json

from unstructured.partition.pdf import partition_pdf


class PdfExtractService:
    """PDF内容提取服务类 - 基于Unstructured库"""
    
    def __init__(self, unstructured_config_path: str = 'config/Unstructured.yaml'):
        """
        初始化PDF提取服务
        
        Args:
            unstructured_config_path: Unstructured配置文件路径
        """
        self.unstructured_config_path = unstructured_config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载Unstructured配置
        self._load_unstructured_config()
        
        # 创建必要的目录
        self._create_directories()
    

    
    def _load_unstructured_config(self) -> None:
        """加载Unstructured配置文件"""
        try:
            with open(self.unstructured_config_path, 'r', encoding='utf-8') as file:
                self.unstructured_config = yaml.safe_load(file)
                self.logger.info("Unstructured配置加载成功")
        except Exception as e:
            self.logger.error(f"加载Unstructured配置失败: {str(e)}")
            # 使用默认配置
            self.unstructured_config = {
                'basic': {'output_format': 'application/json', 'encoding': 'utf-8'},
                'pdf': {'strategy': 'auto'},
                'performance': {'multiprocessing': False}
            }
    
    def _create_directories(self) -> None:
        """创建必要的目录"""
        try:
            # 创建缓存目录
            cache_dir = self.unstructured_config.get('performance', {}).get('cache_dir', './temp/unstructured_cache')
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
                self.logger.info(f"创建Unstructured缓存目录: {cache_dir}")
            
            # 创建JSON输出目录
            pdf_config = self.unstructured_config.get('pdf', {})
            json_output_dir = pdf_config.get('pdf_json_output_dir_path')
            if json_output_dir and json_output_dir != 'null':
                if not os.path.exists(json_output_dir):
                    os.makedirs(json_output_dir, exist_ok=True)
                    self.logger.info(f"创建JSON输出目录: {json_output_dir}")
            
            # 创建调试输出目录
            debug_config = self.unstructured_config.get('debug', {})
            if debug_config.get('save_intermediate_results', False):
                debug_dir = debug_config.get('debug_output_dir', './logs/unstructured_debug')
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir, exist_ok=True)
                    self.logger.info(f"创建调试输出目录: {debug_dir}")
                    
        except Exception as e:
            self.logger.error(f"创建目录失败: {str(e)}")
    
    def extract_pdf_content(self, file_path: str, document_id: int) -> Dict[str, Any]:
        """
        提取PDF文件内容 - 使用Unstructured库
        
        Args:
            file_path: PDF文件路径
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 提取结果
        """
        try:
            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'message': '文件不存在',
                    'extracted_data': {}
                }
            
            self.logger.info(f"开始使用Unstructured库提取PDF内容: {file_path}")
            
            # 使用Unstructured库解析PDF
            elements = self._partition_pdf_with_unstructured(file_path)
            
            if not elements:
                return {
                    'success': False,
                    'message': 'PDF内容提取失败，未获取到任何元素',
                    'extracted_data': {}
                }
            
            # 转换为JSON格式，添加ID和层次关系
            elements_json = self._elements_to_json(elements, document_id)
            
            # 重新命名图片文件（如果有图片）
            elements_json = self._rename_extracted_images(elements_json, file_path, document_id)
            
            # 保存JSON数据到文件（如果配置了输出目录）
            self._save_json_to_file(elements_json, file_path, document_id)
            
            self.logger.info(f"PDF内容提取完成，文档ID: {document_id}, 元素数量: {len(elements)}")
            
            return {
                'success': True,
                'message': 'PDF内容提取成功',
                'extracted_data': elements_json
            }
            
        except Exception as e:
            self.logger.error(f"PDF内容提取失败: {str(e)}")
            return {
                'success': False,
                'message': f'PDF内容提取失败: {str(e)}',
                'extracted_data': {}
            }
    
    def _partition_pdf_with_unstructured(self, file_path: str) -> List:
        """
        使用Unstructured库解析PDF文件
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            List: Unstructured元素列表
        """
        try:
            # 获取PDF配置
            pdf_config = self.unstructured_config.get('pdf', {})
            basic_config = self.unstructured_config.get('basic', {})
            filtering_config = self.unstructured_config.get('filtering', {})
            output_config = self.unstructured_config.get('output', {})
            
            # 构建partition_pdf参数
            partition_kwargs = {
                'filename': file_path,
                'strategy': pdf_config.get('strategy', 'auto'),
                'include_page_breaks': filtering_config.get('include_page_breaks', False),
                'infer_table_structure': pdf_config.get('pdf_infer_table_structure', True),
                # 移除coordinates参数避免冲突
                # 'coordinates': basic_config.get('coordinates', True),
                'metadata_include': output_config.get('metadata_include', []),
                'metadata_exclude': output_config.get('metadata_exclude', [])
            }
            
            # 可选参数
            if pdf_config.get('ocr_languages'):
                partition_kwargs['languages'] = pdf_config['ocr_languages']
            
            if pdf_config.get('hi_res_model_name'):
                partition_kwargs['hi_res_model_name'] = pdf_config['hi_res_model_name']
            
            if pdf_config.get('starting_page_number') is not None:
                partition_kwargs['starting_page_number'] = pdf_config['starting_page_number']
            
            if pdf_config.get('ending_page_number') is not None:
                partition_kwargs['ending_page_number'] = pdf_config['ending_page_number']
            
            # 图片提取配置
            if pdf_config.get('pdf_extract_images', False):
                partition_kwargs['extract_images_in_pdf'] = True
                if pdf_config.get('pdf_image_output_dir_path'):
                    partition_kwargs['extract_image_block_output_dir'] = pdf_config['pdf_image_output_dir_path']
            
            # 执行PDF解析
            elements = partition_pdf(**partition_kwargs)
            
            self.logger.info(f"Unstructured解析完成，获取到{len(elements)}个元素")
            return elements
            
        except Exception as e:
            self.logger.error(f"Unstructured PDF解析失败: {str(e)}")
            return []
    
    def _elements_to_json(self, elements: List, document_id: int) -> List[Dict]:
        """
        将Unstructured元素转换为JSON格式，添加ID和层次关系
        
        Args:
            elements: Unstructured元素列表
            document_id: 文档ID
            
        Returns:
            List[Dict]: 包含ID和层次关系的JSON格式元素列表
        """
        try:
            json_elements = []
            current_title_id = None  # 当前标题的ID
            title_stack = []  # 标题栈，用于处理多级标题
            
            for index, element in enumerate(elements):
                # 生成唯一ID：文档ID_序列号
                element_id = f"{document_id}_{index + 1:04d}"
                
                element_dict = {
                    'id': element_id,
                    'type': str(type(element).__name__),
                    'text': str(element),
                    'parent_id': None,  # 默认没有父级
                    'metadata': {}
                }
                
                # 提取元数据
                if hasattr(element, 'metadata'):
                    metadata = element.metadata.to_dict() if hasattr(element.metadata, 'to_dict') else dict(element.metadata)
                    element_dict['metadata'] = metadata
                
                # 提取坐标信息
                if hasattr(element, 'metadata') and hasattr(element.metadata, 'coordinates'):
                    coordinates = element.metadata.coordinates
                    if coordinates:
                        coords_dict = {
                            'points': coordinates.points if hasattr(coordinates, 'points') else None,
                            'system': str(coordinates.system) if hasattr(coordinates, 'system') else None
                        }
                        element_dict['coordinates'] = coords_dict
                
                # 提取类别信息
                if hasattr(element, 'category'):
                    element_dict['category'] = element.category
                
                # 处理层次关系
                element_type = element_dict['type']
                
                if element_type in ['Title', 'Header']:
                    # 这是标题元素，更新当前标题ID
                    current_title_id = element_id
                    
                    # 处理多级标题层次（可以根据字体大小、位置等判断层级）
                    title_level = self._get_title_level(element)
                    
                    # 清理标题栈，保留合适的父级标题
                    while title_stack and title_stack[-1]['level'] >= title_level:
                        title_stack.pop()
                    
                    # 如果有父级标题，设置parent_id
                    if title_stack:
                        element_dict['parent_id'] = title_stack[-1]['id']
                    
                    # 将当前标题添加到栈中
                    title_stack.append({
                        'id': element_id,
                        'level': title_level,
                        'text': str(element)
                    })
                    
                    # 添加标题层级信息到metadata
                    element_dict['metadata']['title_level'] = title_level
                    
                else:
                    # 这是内容元素，如果有当前标题，则设置其为父级
                    if current_title_id:
                        element_dict['parent_id'] = current_title_id
                    
                    # 为内容元素添加归属信息
                    if title_stack:
                        element_dict['metadata']['belongs_to_titles'] = [
                            {'id': title['id'], 'text': title['text'][:50] + ('...' if len(title['text']) > 50 else '')}
                            for title in title_stack
                        ]
                
                # 添加层次深度信息
                element_dict['metadata']['hierarchy_depth'] = len(title_stack)
                
                json_elements.append(element_dict)
            
            # 添加统计信息
            self.logger.info(f"JSON转换完成: 共{len(json_elements)}个元素，标题数: {len([e for e in json_elements if e['type'] in ['Title', 'Header']])}")
            
            return json_elements
            
        except Exception as e:
            self.logger.error(f"元素转换为JSON失败: {str(e)}")
            return []
    
    def _get_title_level(self, element) -> int:
        """
        获取标题层级
        
        Args:
            element: Unstructured元素
            
        Returns:
            int: 标题层级（1-6，1为最高级）
        """
        try:
            # 尝试从metadata获取层级信息
            if hasattr(element, 'metadata'):
                # 检查是否有明确的层级信息
                if hasattr(element.metadata, 'header_level'):
                    return int(element.metadata.header_level)
                
                # 根据字体大小判断层级
                if hasattr(element.metadata, 'emphasized_text_contents'):
                    emphasized = element.metadata.emphasized_text_contents
                    if emphasized:
                        # 如果有强调文本，可能是高级标题
                        return 1
                
                # 根据文本长度和位置判断
                text_length = len(str(element))
                if text_length < 50:  # 短文本更可能是高级标题
                    return 1
                elif text_length < 100:
                    return 2
                else:
                    return 3
            
            # 默认返回2级标题
            return 2
            
        except Exception as e:
            self.logger.warning(f"获取标题层级失败: {str(e)}")
            return 2
    
    def _save_json_to_file(self, elements_json: List[Dict], file_path: str, document_id: int) -> None:
        """
        保存JSON数据到文件
        
        Args:
            elements_json: JSON格式的元素列表
            file_path: 原始PDF文件路径
            document_id: 文档ID
        """
        try:
            # 获取JSON输出目录配置
            pdf_config = self.unstructured_config.get('pdf', {})
            json_output_dir = pdf_config.get('pdf_json_output_dir_path')
            
            # 如果没有配置输出目录或配置为null，则不保存
            if not json_output_dir or json_output_dir == 'null':
                return
            
            # 生成输出文件名
            import os
            pdf_filename = os.path.basename(file_path)
            pdf_name_without_ext = os.path.splitext(pdf_filename)[0]
            json_filename = f"{pdf_name_without_ext}_doc_{document_id}.json"
            json_file_path = os.path.join(json_output_dir, json_filename)
            
            # 构建完整的JSON数据结构
            full_json_data = {
                'document_info': {
                    'document_id': document_id,
                    'source_file': file_path,
                    'filename': pdf_filename,
                    'extraction_time': datetime.now().isoformat(),
                    'total_elements': len(elements_json)
                },
                'extraction_config': {
                    'strategy': pdf_config.get('strategy', 'auto'),
                    'ocr_languages': pdf_config.get('ocr_languages', []),
                    'extract_images': pdf_config.get('pdf_extract_images', False),
                    'infer_table_structure': pdf_config.get('pdf_infer_table_structure', True)
                },
                'elements': elements_json
            }
            
            # 保存JSON文件，使用自定义编码器处理特殊对象
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(full_json_data, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"JSON数据已保存到: {json_file_path}")
            
        except Exception as e:
            self.logger.error(f"保存JSON数据到文件失败: {str(e)}")
    
    def _rename_extracted_images(self, elements_json: List[Dict], file_path: str, document_id: int) -> List[Dict]:
        """
        重新命名提取的图片文件，使用更有意义的命名规则
        
        Args:
            elements_json: JSON格式的元素列表
            file_path: 原始PDF文件路径
            document_id: 文档ID
            
        Returns:
            List[Dict]: 更新了图片路径的元素列表
        """
        try:
            # 获取图片命名配置
            pdf_config = self.unstructured_config.get('pdf', {})
            image_naming_config = pdf_config.get('image_naming', {})
            
            # 默认配置
            pattern = image_naming_config.get('pattern', '{doc_name}_page{page:03d}_img{index:02d}_{timestamp}')
            timestamp_format = image_naming_config.get('timestamp_format', '%Y%m%d_%H%M%S')
            include_coordinates = image_naming_config.get('include_coordinates', True)
            max_filename_length = image_naming_config.get('max_filename_length', 100)
            
            # 获取文档名称
            doc_name = os.path.splitext(os.path.basename(file_path))[0]
            # 清理文档名称，移除特殊字符
            doc_name = "".join(c for c in doc_name if c.isalnum() or c in ('-', '_')).rstrip()[:20]
            
            # 生成时间戳
            timestamp = datetime.now().strftime(timestamp_format)
            
            # 计数器，按页面分组
            page_image_counters = {}
            
            for element in elements_json:
                if element.get('type') == 'Image' and element.get('metadata', {}).get('image_path'):
                    old_image_path = element['metadata']['image_path']
                    
                    # 检查文件是否存在
                    if not os.path.exists(old_image_path):
                        continue
                    
                    # 获取页码
                    page_number = element.get('metadata', {}).get('page_number', 1)
                    
                    # 页面图片计数
                    if page_number not in page_image_counters:
                        page_image_counters[page_number] = 0
                    page_image_counters[page_number] += 1
                    
                    # 构建新的文件名
                    format_dict = {
                        'doc_name': doc_name,
                        'page': page_number,
                        'index': page_image_counters[page_number],
                        'timestamp': timestamp,
                        'doc_id': document_id
                    }
                    
                    new_filename = pattern.format(**format_dict)
                    
                    # 添加坐标信息（如果启用）
                    if include_coordinates and element.get('coordinates', {}).get('points'):
                        points = element['coordinates']['points']
                        if points and len(points) >= 2:
                            x = int(points[0][0])
                            y = int(points[0][1])
                            new_filename += f'_pos{x}x{y}'
                    
                    # 限制文件名长度
                    if len(new_filename) > max_filename_length - 4:  # 保留.jpg的空间
                        new_filename = new_filename[:max_filename_length - 4]
                    
                    new_filename += '.jpg'
                    
                    # 构建新的完整路径
                    old_dir = os.path.dirname(old_image_path)
                    new_image_path = os.path.join(old_dir, new_filename)
                    
                    # 重命名文件
                    try:
                        os.rename(old_image_path, new_image_path)
                        element['metadata']['image_path'] = new_image_path
                        self.logger.info(f"图片重命名: {os.path.basename(old_image_path)} -> {new_filename}")
                    except OSError as e:
                        self.logger.warning(f"图片重命名失败: {old_image_path} -> {new_image_path}, 错误: {e}")
            
            return elements_json
            
        except Exception as e:
            self.logger.error(f"重命名提取的图片失败: {str(e)}")
            return elements_json
