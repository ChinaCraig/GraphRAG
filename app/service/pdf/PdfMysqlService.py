"""
PDF MySQL保存服务
负责将JSON数据保存到MySQL的sections、figures、tables、table_rows表
"""

import logging
import yaml
import json
import re
from typing import Optional, Dict, Any, List
from datetime import datetime

from utils.MySQLManager import MySQLManager


class PdfMysqlService:
    """PDF MySQL保存服务类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化PDF MySQL服务
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_configs()
        
        # 初始化数据库管理器
        self.mysql_manager = MySQLManager()
    
    def _load_configs(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            
            self.config = config
            self.logger.info("PDF MySQL服务配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载PDF MySQL服务配置失败: {str(e)}")
            raise
    
    def process_pdf_json_to_mysql(self, json_data: Dict[str, Any], document_id: int) -> Dict[str, Any]:
        """
        将PDF提取的JSON数据保存到MySQL
        
        Args:
            json_data: JSON数据（包含sections）
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            self.logger.info(f"开始MySQL保存，文档ID: {document_id}")
            
            # 获取sections数据
            sections = json_data.get('sections', [])
            if not sections:
                return {
                    'success': False,
                    'message': '未找到可保存的sections',
                    'saved_count': 0
                }
            
            saved_count = 0
            
            # 1. 保存sections
            sections_result = self._save_sections(sections, document_id)
            saved_count += sections_result
            
            # 2. 保存figures
            figures_result = self._save_figures(sections, document_id)
            saved_count += figures_result
            
            # 3. 保存tables
            tables_result = self._save_tables(sections, document_id)
            saved_count += tables_result
            
            # 4. 保存table_rows
            table_rows_result = self._save_table_rows(sections, document_id)
            saved_count += table_rows_result
            
            self.logger.info(f"MySQL保存完成，文档ID: {document_id}, 总保存条数: {saved_count}")
            
            return {
                'success': True,
                'message': 'MySQL保存成功',
                'saved_count': saved_count,
                'document_id': document_id,
                'sections_count': sections_result,
                'figures_count': figures_result,
                'tables_count': tables_result,
                'table_rows_count': table_rows_result
            }
            
        except Exception as e:
            self.logger.error(f"MySQL保存失败: {str(e)}")
            return {
                'success': False,
                'message': f'MySQL保存失败: {str(e)}',
                'saved_count': 0
            }
    
    def _save_sections(self, sections: List[Dict[str, Any]], document_id: int) -> int:
        """
        保存sections数据（一节一行）
        映射规则：section_id / doc_id / version / title / page_start / page_end
        
        Args:
            sections: sections列表
            document_id: 文档ID
            
        Returns:
            int: 保存的条数
        """
        try:
            saved_count = 0
            
            for section in sections:
                section_id = section.get('section_id', '')
                title = section.get('title', '')
                page_start = section.get('page_start', 1)
                page_end = section.get('page_end', page_start)
                
                # 构建sections表数据
                section_data = {
                    'section_id': section_id,  # 主键，与Neo4j、向量库、ES一致
                    'doc_id': document_id,  # 等同于document_id
                    'version': 1,  # 默认版本为1
                    'title': title,
                    'page_start': page_start,
                    'page_end': page_end,
                    'created_time': datetime.now()
                }
                
                # 保存到sections表
                success = self.mysql_manager.insert_data('sections', section_data)
                if success:
                    saved_count += 1
                    self.logger.debug(f"保存section成功: {section_id}")
                else:
                    self.logger.error(f"保存section失败: {section_id}")
            
            self.logger.info(f"sections表保存完成，保存条数: {saved_count}")
            return saved_count
            
        except Exception as e:
            self.logger.error(f"保存sections失败: {str(e)}")
            return 0
    
    def _save_figures(self, sections: List[Dict[str, Any]], document_id: int) -> int:
        """
        保存figures数据（一图一行）
        遍历 blocks.type='figure'
        映射规则：elem_id / section_id / image_path / caption / page / bbox_norm / bind_to_elem_id
        
        Args:
            sections: sections列表
            document_id: 文档ID
            
        Returns:
            int: 保存的条数
        """
        try:
            saved_count = 0
            
            for section in sections:
                section_id = section.get('section_id', '')
                blocks = section.get('blocks', [])
                
                # 遍历blocks，寻找type='figure'的block
                for block in blocks:
                    block_type = block.get('type', '').lower()
                    if block_type == 'figure':
                        elem_id = block.get('elem_id', '')
                        image_path = block.get('image_path', '')
                        caption = block.get('caption', '')
                        page = block.get('page', 1)
                        bbox = block.get('bbox', {})
                        
                        # 规范化bbox（简化实现，假设页面尺寸为标准A4）
                        bbox_norm = self._normalize_bbox(bbox, 595, 842)  # A4尺寸
                        
                        # bind_to_elem_id（若清单里有图文绑定，暂时留空）
                        bind_to_elem_id = ''
                        
                        # 确保elem_id唯一性：组合section_id和原始elem_id
                        unique_elem_id = f"{section_id}_{elem_id}" if elem_id else f"{section_id}_figure_{saved_count}"
                        
                        # 构建figures表数据
                        figure_data = {
                            'elem_id': unique_elem_id,  # 使用唯一的elem_id作为主键
                            'section_id': section_id,
                            'image_path': image_path,
                            'caption': caption,
                            'page': page,
                            'bbox_norm': json.dumps(bbox_norm),
                            'bind_to_elem_id': bind_to_elem_id,
                            'created_time': datetime.now()
                        }
                        
                        # 保存到figures表
                        success = self.mysql_manager.insert_data('figures', figure_data)
                        if success:
                            saved_count += 1
                            self.logger.debug(f"保存figure成功: {elem_id}")
                        else:
                            self.logger.error(f"保存figure失败: {elem_id}")
            
            self.logger.info(f"figures表保存完成，保存条数: {saved_count}")
            return saved_count
            
        except Exception as e:
            self.logger.error(f"保存figures失败: {str(e)}")
            return 0
    
    def _normalize_bbox(self, bbox: Any, page_w: int, page_h: int) -> Dict[str, float]:
        """
        规范化bbox坐标（转换为相对坐标）
        
        Args:
            bbox: 边界框坐标，可能是字典格式 {'x1':..., 'y1':...} 或列表格式 [[x1,y1],[x2,y2]]
            page_w: 页面宽度
            page_h: 页面高度
            
        Returns:
            Dict[str, float]: 规范化后的坐标
        """
        try:
            if not bbox or page_w <= 0 or page_h <= 0:
                return {'x1': 0.0, 'y1': 0.0, 'x2': 0.0, 'y2': 0.0}
            
            # 处理不同的bbox格式
            if isinstance(bbox, dict):
                # 字典格式：{'x1': ..., 'y1': ..., 'x2': ..., 'y2': ...}
                x1 = float(bbox.get('x1', 0)) / page_w
                y1 = float(bbox.get('y1', 0)) / page_h
                x2 = float(bbox.get('x2', 0)) / page_w
                y2 = float(bbox.get('y2', 0)) / page_h
            elif isinstance(bbox, list) and len(bbox) >= 2:
                # 列表格式：[[x1, y1], [x2, y2]]
                if isinstance(bbox[0], list) and len(bbox[0]) >= 2 and isinstance(bbox[1], list) and len(bbox[1]) >= 2:
                    x1 = float(bbox[0][0]) / page_w
                    y1 = float(bbox[0][1]) / page_h
                    x2 = float(bbox[1][0]) / page_w
                    y2 = float(bbox[1][1]) / page_h
                else:
                    # 其他列表格式，返回默认值
                    return {'x1': 0.0, 'y1': 0.0, 'x2': 0.0, 'y2': 0.0}
            else:
                # 其他格式，返回默认值
                return {'x1': 0.0, 'y1': 0.0, 'x2': 0.0, 'y2': 0.0}
            
            return {
                'x1': round(x1, 4),
                'y1': round(y1, 4),
                'x2': round(x2, 4),
                'y2': round(y2, 4)
            }
            
        except Exception as e:
            self.logger.warning(f"bbox规范化失败: {str(e)}")
            return {'x1': 0.0, 'y1': 0.0, 'x2': 0.0, 'y2': 0.0}
    
    def _save_tables(self, sections: List[Dict[str, Any]], document_id: int) -> int:
        """
        保存tables数据（一表一行）
        遍历 blocks.type='table'
        映射规则：elem_id / section_id / table_html / n_rows / n_cols
        
        Args:
            sections: sections列表
            document_id: 文档ID
            
        Returns:
            int: 保存的条数
        """
        try:
            saved_count = 0
            
            for section in sections:
                section_id = section.get('section_id', '')
                blocks = section.get('blocks', [])
                
                # 遍历blocks，寻找type='table'的block
                for block in blocks:
                    block_type = block.get('type', '').lower()
                    if block_type == 'table':
                        elem_id = block.get('elem_id', '')
                        table_html = block.get('html', '')
                        rows = block.get('rows', [])
                        
                        # n_rows = len(block.rows)
                        n_rows = len(rows)
                        
                        # n_cols = 推断/解析列数
                        n_cols = self._infer_table_columns(rows, table_html)
                        
                        # 确保elem_id唯一性：组合section_id和原始elem_id
                        unique_elem_id = f"{section_id}_{elem_id}" if elem_id else f"{section_id}_table_{saved_count}"
                        
                        # 构建tables表数据
                        table_data = {
                            'elem_id': unique_elem_id,  # 使用唯一的elem_id作为主键
                            'section_id': section_id,
                            'table_html': table_html,
                            'n_rows': n_rows,
                            'n_cols': n_cols,
                            'created_time': datetime.now()
                        }
                        
                        # 保存到tables表
                        success = self.mysql_manager.insert_data('tables', table_data)
                        if success:
                            saved_count += 1
                            self.logger.debug(f"保存table成功: {elem_id}")
                        else:
                            self.logger.error(f"保存table失败: {elem_id}")
            
            self.logger.info(f"tables表保存完成，保存条数: {saved_count}")
            return saved_count
            
        except Exception as e:
            self.logger.error(f"保存tables失败: {str(e)}")
            return 0
    
    def _infer_table_columns(self, rows: List[Dict[str, Any]], table_html: str) -> int:
        """
        推断/解析表格列数
        
        Args:
            rows: 表格行数据
            table_html: 表格HTML
            
        Returns:
            int: 列数
        """
        try:
            # 方法1：从rows数据推断列数
            if rows:
                # 假设第一行包含所有列
                first_row = rows[0]
                if isinstance(first_row, dict):
                    # 如果row是字典格式，键的数量就是列数
                    return len(first_row.keys())
                elif 'row_cells' in first_row:
                    # 如果有row_cells字段
                    return len(first_row.get('row_cells', []))
            
            # 方法2：从HTML解析列数
            if table_html:
                # 简单正则匹配<td>或<th>标签数量
                import re
                # 找到第一行的td或th标签数量
                first_row_match = re.search(r'<tr[^>]*>(.*?)</tr>', table_html, re.IGNORECASE | re.DOTALL)
                if first_row_match:
                    first_row_content = first_row_match.group(1)
                    td_count = len(re.findall(r'<t[hd][^>]*>', first_row_content, re.IGNORECASE))
                    if td_count > 0:
                        return td_count
            
            # 默认返回1列
            return 1
            
        except Exception as e:
            self.logger.warning(f"推断表格列数失败: {str(e)}")
            return 1
    
    def _save_table_rows(self, sections: List[Dict[str, Any]], document_id: int) -> int:
        """
        保存table_rows数据（一行一行）
        对 block.rows：table_elem_id / row_index / row_text / row_json
        
        Args:
            sections: sections列表
            document_id: 文档ID
            
        Returns:
            int: 保存的条数
        """
        try:
            saved_count = 0
            
            for section in sections:
                section_id = section.get('section_id', '')
                blocks = section.get('blocks', [])
                
                # 遍历blocks，寻找type='table'的block
                for block in blocks:
                    block_type = block.get('type', '').lower()
                    if block_type == 'table':
                        original_elem_id = block.get('elem_id', '')
                        rows = block.get('rows', [])
                        
                        # 生成与tables表一致的唯一elem_id
                        table_elem_id = f"{section_id}_{original_elem_id}" if original_elem_id else f"{section_id}_table_unknown"
                        
                        # 对每一行创建记录
                        for row_index, row in enumerate(rows):
                            # row_text = 规范化行文本
                            row_text = self._format_row_text(row)
                            
                            # row_json = 行的原始键值对
                            row_json = json.dumps(row, ensure_ascii=False) if row else '{}'
                            
                            # 构建table_rows表数据
                            table_row_data = {
                                'table_elem_id': table_elem_id,  # 使用与tables表一致的唯一ID
                                'row_index': row_index,
                                'row_text': row_text,
                                'row_json': row_json,
                                'created_time': datetime.now()
                            }
                            
                            # 保存到table_rows表
                            success = self.mysql_manager.insert_data('table_rows', table_row_data)
                            if success:
                                saved_count += 1
                                self.logger.debug(f"保存table_row成功: {table_elem_id}[{row_index}]")
                            else:
                                self.logger.error(f"保存table_row失败: {table_elem_id}[{row_index}]")
            
            self.logger.info(f"table_rows表保存完成，保存条数: {saved_count}")
            return saved_count
            
        except Exception as e:
            self.logger.error(f"保存table_rows失败: {str(e)}")
            return 0
    
    def _format_row_text(self, row: Dict[str, Any]) -> str:
        """
        格式化行文本（例如：项目: 线性范围 | 数值: 1–100 ng/mL | R²: 0.998）
        
        Args:
            row: 行数据
            
        Returns:
            str: 格式化后的行文本
        """
        try:
            if not row:
                return ''
            
            # 如果row有row_text字段，直接使用
            if 'row_text' in row and row['row_text']:
                return str(row['row_text'])
            
            # 否则根据键值对构建格式化文本
            formatted_parts = []
            for key, value in row.items():
                if key in ['row_text', 'row_cells'] or not value:
                    continue
                formatted_parts.append(f"{key}: {value}")
            
            return ' | '.join(formatted_parts) if formatted_parts else str(row)
            
        except Exception as e:
            self.logger.warning(f"格式化行文本失败: {str(e)}")
            return str(row)
