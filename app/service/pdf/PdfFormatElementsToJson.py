"""
PDF元素格式化为JSON服务
负责将Unstructured库提取的元素转换为标准JSON格式
"""

import logging
import os
from typing import List, Dict, Any
from datetime import datetime


class PdfFormatElementsToJson:
    """PDF元素格式化为JSON服务类"""
    
    def __init__(self):
        """初始化服务"""
        self.logger = logging.getLogger(__name__)
    
    def format_elements_to_json(self, elements: List, document_id: int, file_path: str) -> Dict[str, Any]:
        """
        将Unstructured元素格式化为JSON
        
        Args:
            elements: Unstructured元素列表
            document_id: 文档ID
            file_path: 原始PDF文件路径
            
        Returns:
            Dict[str, Any]: 格式化后的JSON数据
        """
        try:
            if not elements:
                return {
                    'success': False,
                    'message': '元素列表为空',
                    'json_data': {}
                }
            
            self.logger.info(f"开始格式化elements为JSON，文档ID: {document_id}, 元素数量: {len(elements)}")
            
            # 转换元素为Section格式的JSON
            sections = self._elements_to_sections(elements, document_id, file_path)
            
            # 构建完整的JSON数据结构
            pdf_filename = os.path.basename(file_path)
            full_json_data = {
                'document_info': {
                    'document_id': document_id,
                    'source_file': file_path,
                    'filename': pdf_filename,
                    'extraction_time': datetime.now().isoformat(),
                    'total_sections': len(sections)
                },
                'sections': sections
            }
            
            self.logger.info(f"元素格式化为JSON完成，文档ID: {document_id}, 生成sections: {len(sections)}")
            
            return {
                'success': True,
                'message': '格式化成功',
                'json_data': full_json_data
            }
            
        except Exception as e:
            self.logger.error(f"格式化elements为JSON失败: {str(e)}")
            return {
                'success': False,
                'message': f'格式化失败: {str(e)}',
                'json_data': {}
            }
    
    def _elements_to_sections(self, elements: List, document_id: int, file_path: str) -> List[Dict]:
        """
        将Unstructured元素转换为Section格式的JSON
        
        Args:
            elements: Unstructured元素列表
            document_id: 文档ID
            file_path: 原始PDF文件路径
            
        Returns:
            List[Dict]: Section格式的JSON列表
        """
        try:
            sections = []
            current_section = None
            section_counter = 1
            block_counter = 1
            
            # 获取文档名前缀（用于生成section_id）
            pdf_filename = os.path.basename(file_path)
            doc_prefix = os.path.splitext(pdf_filename)[0]
            
            for index, element in enumerate(elements):
                element_type = str(type(element).__name__)
                element_text = str(element).strip()
                
                if not element_text:  # 跳过空元素
                    continue
                
                # 获取页码和坐标
                page_num = self._get_page_number(element)
                bbox = self._get_bbox(element)
                
                # 判断是否为新section的开始（Title或Header）
                if element_type in ['Title', 'Header']:
                    # 保存当前section（如果存在）
                    if current_section:
                        sections.append(current_section)
                    
                    # 创建新section
                    section_id = f"{doc_prefix}_doc#{datetime.now().strftime('%Y-%m-%d')}#{document_id}_{section_counter:04d}"
                    current_section = {
                        'section_id': section_id,
                        'title': element_text,
                        'page_start': page_num,
                        'page_end': page_num,
                        'blocks': [],
                        'full_text': element_text,
                        'elem_ids': []
                    }
                    section_counter += 1
                    block_counter = 1
                    
                    # Title/Header也需要作为block添加
                    block = self._create_block(element, element_type, block_counter, page_num, bbox, file_path, document_id)
                    if block:
                        current_section['blocks'].append(block)
                        current_section['elem_ids'].append(block['elem_id'])
                        block_counter += 1
                    
                    continue  # 跳过后面的处理，因为已经处理了
                
                else:
                    # 如果没有当前section，创建一个默认section
                    if current_section is None:
                        section_id = f"{doc_prefix}_doc#{datetime.now().strftime('%Y-%m-%d')}#{document_id}_{section_counter:04d}"
                        current_section = {
                            'section_id': section_id,
                            'title': "文档内容",
                            'page_start': page_num,
                            'page_end': page_num,
                            'blocks': [],
                            'full_text': "",
                            'elem_ids': []
                        }
                        section_counter += 1
                        block_counter = 1
                
                # 更新section的页码范围
                if page_num < current_section['page_start']:
                    current_section['page_start'] = page_num
                if page_num > current_section['page_end']:
                    current_section['page_end'] = page_num
                
                # 创建block
                block = self._create_block(element, element_type, block_counter, page_num, bbox, file_path, document_id)
                
                if block:
                    current_section['blocks'].append(block)
                    current_section['elem_ids'].append(block['elem_id'])
                    
                    # 更新full_text
                    if current_section['full_text']:
                        current_section['full_text'] += "\n" + element_text
                    else:
                        current_section['full_text'] = element_text
                    
                    block_counter += 1
            
            # 保存最后一个section
            if current_section:
                sections.append(current_section)
            
            self.logger.info(f"Section转换完成: 共{len(sections)}个sections")
            return sections
            
        except Exception as e:
            self.logger.error(f"元素转换为Section失败: {str(e)}")
            return []
    
    def _get_page_number(self, element) -> int:
        """
        获取元素的页码
        
        Args:
            element: Unstructured元素
            
        Returns:
            int: 页码，默认为1
        """
        try:
            if hasattr(element, 'metadata') and hasattr(element.metadata, 'page_number'):
                return int(element.metadata.page_number)
            return 1
        except Exception as e:
            self.logger.warning(f"获取页码失败: {str(e)}")
            return 1
    
    def _get_bbox(self, element) -> List[List[int]]:
        """
        获取元素的边界框坐标
        
        Args:
            element: Unstructured元素
            
        Returns:
            List[List[int]]: 边界框坐标 [[x1,y1],[x2,y2]]
        """
        try:
            if hasattr(element, 'metadata') and hasattr(element.metadata, 'coordinates'):
                coordinates = element.metadata.coordinates
                if coordinates and hasattr(coordinates, 'points') and coordinates.points:
                    points = coordinates.points
                    if len(points) >= 2:
                        # 取第一个点和最后一个点作为边界框
                        x1, y1 = int(points[0][0]), int(points[0][1])
                        x2, y2 = int(points[-1][0]), int(points[-1][1])
                        return [[x1, y1], [x2, y2]]
            return [[0, 0], [0, 0]]
        except Exception as e:
            self.logger.warning(f"获取边界框失败: {str(e)}")
            return [[0, 0], [0, 0]]
    
    def _create_block(self, element, element_type: str, order: int, page: int, bbox: List[List[int]], file_path: str, document_id: int) -> Dict:
        """
        创建block对象
        
        Args:
            element: Unstructured元素
            element_type: 元素类型
            order: 顺序
            page: 页码
            bbox: 边界框
            file_path: 文件路径
            document_id: 文档ID
            
        Returns:
            Dict: block对象
        """
        try:
            element_text = str(element).strip()
            
            # 生成elem_id
            if element_type in ['Title', 'Header']:
                elem_id = f"title_t{order}"
            elif element_type == 'Image':
                elem_id = f"fig_{order}"
            elif element_type == 'Table':
                elem_id = f"tbl_{order}"
            else:
                elem_id = f"para_p{order}"
            
            # 基础block结构
            block = {
                'order': order,
                'elem_id': elem_id,
                'type': self._get_block_type(element_type),
                'page': page,
                'bbox': bbox,
                'text': element_text
            }
            
            # 处理特殊类型
            if element_type == 'Image':
                block = self._process_image_block(block, element, file_path, document_id)
            elif element_type == 'Table':
                block = self._process_table_block(block, element)
            
            return block
            
        except Exception as e:
            self.logger.error(f"创建block失败: {str(e)}")
            return None
    
    def _get_block_type(self, element_type: str) -> str:
        """
        将Unstructured元素类型转换为block类型
        
        Args:
            element_type: Unstructured元素类型
            
        Returns:
            str: block类型
        """
        type_mapping = {
            'Title': 'title',
            'Header': 'title', 
            'NarrativeText': 'paragraph',
            'Text': 'paragraph',
            'ListItem': 'paragraph',
            'Image': 'figure',
            'Table': 'table',
            'Formula': 'formula'
        }
        return type_mapping.get(element_type, 'paragraph')
    
    def _process_image_block(self, block: Dict, element, file_path: str, document_id: int) -> Dict:
        """
        处理图片类型的block
        
        Args:
            block: 基础block
            element: Unstructured元素
            file_path: 文件路径
            document_id: 文档ID
            
        Returns:
            Dict: 处理后的图片block
        """
        try:
            # 添加图片特有字段
            block['caption'] = str(element).strip() if str(element).strip() else "图片"
            
            # 获取图片路径（转换为相对路径）
            image_path = ""
            if hasattr(element, 'metadata') and hasattr(element.metadata, 'image_path'):
                original_path = element.metadata.image_path
                # 重命名图片文件并获取相对路径
                relative_path = self._rename_image_file(original_path, file_path, document_id, block['page'], block['order'])
                image_path = relative_path
            
            block['image_path'] = image_path
            
            return block
            
        except Exception as e:
            self.logger.error(f"处理图片block失败: {str(e)}")
            return block
    
    def _process_table_block(self, block: Dict, element) -> Dict:
        """
        处理表格类型的block
        
        Args:
            block: 基础block
            element: Unstructured元素
            
        Returns:
            Dict: 处理后的表格block
        """
        try:
            # 添加表格特有字段
            if hasattr(element, 'metadata') and hasattr(element.metadata, 'text_as_html'):
                raw_html = element.metadata.text_as_html
                # 确保table标签有正确的CSS类名
                if raw_html and '<table' in raw_html:
                    # 使用正则表达式更准确地添加CSS类名
                    import re
                    if 'class=' in raw_html:
                        # 如果已经有class属性，在现有class中添加multimodal-table
                        block['html'] = re.sub(
                            r'<table([^>]*?)class=["\']([^"\']*)["\']([^>]*?)>',
                            r'<table\1class="multimodal-table \2"\3>',
                            raw_html,
                            count=1
                        )
                    else:
                        # 如果没有class属性，添加class="multimodal-table"
                        block['html'] = re.sub(
                            r'<table([^>]*?)>',
                            r'<table\1 class="multimodal-table">',
                            raw_html,
                            count=1
                        )
                else:
                    block['html'] = raw_html
            else:
                block['html'] = f'<table class="multimodal-table"><tr><td>{str(element)}</td></tr></table>'
            
            # 简单的行解析
            text_lines = str(element).strip().split('\n')
            rows = []
            for i, line in enumerate(text_lines):
                if line.strip():
                    rows.append({
                        'row_id': f"{block['elem_id']}_r{i+1}",
                        'row_text': line.strip()
                    })
            
            block['rows'] = rows
            
            return block
            
        except Exception as e:
            self.logger.error(f"处理表格block失败: {str(e)}")
            return block
    
    def _rename_image_file(self, image_path: str, file_path: str, document_id: int, page: int, order: int) -> str:
        """
        重命名单个图片文件并返回相对路径
        
        Args:
            image_path: 原始图片路径
            file_path: 原始PDF文件路径
            document_id: 文档ID
            page: 页码
            order: 图片序号
            
        Returns:
            str: 新的图片相对路径（相对于项目根目录）
        """
        try:
            if not image_path or not os.path.exists(image_path):
                # 如果原始路径无效，返回空字符串
                return ""
            
            # 获取文档名称
            doc_name = os.path.splitext(os.path.basename(file_path))[0]
            # 清理文档名称，移除特殊字符
            doc_name = "".join(c for c in doc_name if c.isalnum() or c in ('-', '_')).rstrip()[:20]
            
            # 生成时间戳
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # 构建新的文件名
            new_filename = f"{doc_name}_page{page:03d}_img{order:02d}_{timestamp}.jpg"
            
            # 构建新的完整路径
            old_dir = os.path.dirname(image_path)
            new_image_path = os.path.join(old_dir, new_filename)
            
            # 重命名文件
            try:
                os.rename(image_path, new_image_path)
                self.logger.info(f"图片重命名: {os.path.basename(image_path)} -> {new_filename}")
                
                # 返回相对路径（相对于项目根目录）
                relative_path = self._get_relative_path(new_image_path)
                return relative_path
                
            except OSError as e:
                self.logger.warning(f"图片重命名失败: {image_path} -> {new_image_path}, 错误: {e}")
                # 如果重命名失败，尝试返回原始文件的相对路径
                return self._get_relative_path(image_path)
            
        except Exception as e:
            self.logger.error(f"重命名图片文件失败: {str(e)}")
            return ""
    
    def _get_relative_path(self, absolute_path: str) -> str:
        """
        将绝对路径转换为相对于项目根目录的相对路径
        
        Args:
            absolute_path: 绝对路径
            
        Returns:
            str: 相对路径
        """
        try:
            # 获取项目根目录
            # 当前文件位于 app/service/pdf/ 下，项目根目录在上三级
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            
            # 计算相对路径
            relative_path = os.path.relpath(absolute_path, project_root)
            
            # 如果相对路径以 ../ 开头，说明文件在项目目录外，直接返回文件名
            if relative_path.startswith('..'):
                filename = os.path.basename(absolute_path)
                return f"figures/{filename}"
            
            return relative_path
            
        except Exception as e:
            self.logger.error(f"转换相对路径失败: {str(e)}")
            # 备用方案：直接返回文件名，加上 figures/ 前缀
            filename = os.path.basename(absolute_path)
            return f"figures/{filename}"
