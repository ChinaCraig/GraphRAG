"""
PDF知识图谱服务
负责将PDF文档中的标题和内容构建为知识图谱，支持GraphRAG查询
基于标题-内容层级关系构建图谱，确保查询结果的完整性
"""

import logging
import yaml
import json
import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime


from utils.MySQLManager import MySQLManager
from utils.Neo4jManager import Neo4jManager


class PdfGraphService:
    """PDF知识图谱服务类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化PDF知识图谱服务
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_configs()
        
        # 初始化数据库管理器
        self.mysql_manager = MySQLManager()
        self.neo4j_manager = Neo4jManager()
    
    def _load_configs(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
            
            with open('config/model.yaml', 'r', encoding='utf-8') as file:
                self.model_config = yaml.safe_load(file)
            
            with open('config/prompt.yaml', 'r', encoding='utf-8') as file:
                self.prompt_config = yaml.safe_load(file)
            
            self.logger.info("PDF知识图谱服务配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载PDF知识图谱服务配置失败: {str(e)}")
            raise
    
    def process_pdf_json_to_graph(self, json_file_path: str, document_id: int) -> Dict[str, Any]:
        """
        将PDF提取的JSON文件处理为知识图谱
        
        Args:
            json_file_path: JSON文件路径（支持doc_1.json和content_units.json）
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 加载JSON数据
            with open(json_file_path, 'r', encoding='utf-8') as file:
                json_data = json.load(file)
            
            # 判断JSON文件类型并选择相应的解析方法
            if self._is_content_units_format(json_data):
                # 使用content_units.json构建图谱（推荐方式）
                graph_structure = self._parse_content_units_to_graph_structure(json_data, document_id)
                self.logger.info(f"使用content_units.json格式构建图谱，文档ID: {document_id}")
            else:
                # 使用原始doc_1.json构建图谱（兼容性）
                graph_structure = self._parse_pdf_json_to_graph_structure(json_data, document_id)
                self.logger.info(f"使用doc_1.json格式构建图谱，文档ID: {document_id}")
            
            if not graph_structure:
                return {
                    'success': False,
                    'message': '未找到可构建图谱的内容',
                    'nodes_count': 0,
                    'relationships_count': 0
                }
            
            # 创建图谱节点和关系
            nodes_created = self._create_graph_nodes(graph_structure, document_id)
            relationships_created = self._create_graph_relationships(graph_structure, document_id)
            
            # 更新文档处理状态
            self.mysql_manager.update_data(
                'documents',
                {'process_status': 'graph_processed'},
                'id = :doc_id',
                {'doc_id': document_id}
            )
            
            self.logger.info(f"PDF知识图谱构建完成，文档ID: {document_id}, 节点: {nodes_created}, 关系: {relationships_created}")
            
            return {
                'success': True,
                'message': 'PDF知识图谱构建成功',
                'nodes_count': nodes_created,
                'relationships_count': relationships_created,
                'document_id': document_id
            }
            
        except Exception as e:
            self.logger.error(f"PDF知识图谱构建失败: {str(e)}")
            return {
                'success': False,
                'message': f'PDF知识图谱构建失败: {str(e)}',
                'nodes_count': 0,
                'relationships_count': 0
            }
    
    def _is_content_units_format(self, json_data) -> bool:
        """
        判断JSON数据是否为content_units格式
        
        Args:
            json_data: JSON数据
            
        Returns:
            bool: 是否为content_units格式
        """
        try:
            # content_units.json是一个列表，每个元素包含content, content_type等字段
            if isinstance(json_data, list) and len(json_data) > 0:
                first_item = json_data[0]
                required_fields = ['content', 'content_type', 'title', 'element_id']
                return all(field in first_item for field in required_fields)
            return False
        except Exception:
            return False
    
    def _parse_content_units_to_graph_structure(self, content_units_data: List[Dict[str, Any]], document_id: int) -> Dict[str, Any]:
        """
        基于content_units.json构建知识图谱结构
        按照新的设计：Section -> Paragraph/Figure/Table -> 详细关系
        
        Args:
            content_units_data: content_units.json数据
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 图谱结构数据
        """
        try:
            # 存储图谱结构
            graph_structure = {
                'document_node': None,
                'section_nodes': [],  # Section节点（每个content unit对应一个section）
                'paragraph_nodes': [],  # Paragraph节点（正文内容）
                'figure_nodes': [],  # Figure节点（图片）
                'table_nodes': [],  # Table节点（表格）
                'table_row_nodes': [],  # 表格行节点
                'table_cell_nodes': [],  # 表格单元格节点
                'section_relationships': [],  # Section之间的关系
                'content_relationships': [],  # HAS_CONTENT关系
                'sequence_relationships': [],  # NEXT顺序关系
                'illustration_relationships': [],  # ILLUSTRATES关系
                'table_relationships': [],  # 表格内部关系
                'semantic_entities': [],  # 语义实体
                'entity_relationships': []  # 实体关系
            }
            
            # 创建文档根节点
            doc_node_id = f"doc_{document_id}"
            graph_structure['document_node'] = {
                'id': doc_node_id,
                'type': 'Document',
                'properties': {
                    'id': doc_node_id,  # 添加id属性用于关系匹配
                    'document_id': document_id,
                    'filename': f'document_{document_id}',
                    'total_sections': len(content_units_data),
                    'created_time': datetime.now().isoformat()
                }
            }
            
            all_content_nodes = []  # 用于建立顺序链
            
            # 步骤1: 处理每个content unit作为一个Section
            for unit_index, unit in enumerate(content_units_data):
                section_node = self._create_section_node(unit, document_id, unit_index)
                if section_node:
                    graph_structure['section_nodes'].append(section_node)
                    
                    # 步骤2: 为每个Section创建子节点
                    content_nodes = []
                    order_index = 0
                    
                    # 创建Paragraph节点（从content中提取正文）
                    paragraph_node = self._create_paragraph_node(unit, document_id, unit_index)
                    if paragraph_node:
                        graph_structure['paragraph_nodes'].append(paragraph_node)
                        content_nodes.append(paragraph_node)
                        all_content_nodes.append(paragraph_node)
                        
                        # 步骤3: 建立HAS_CONTENT关系，保持阅读顺序
                        graph_structure['content_relationships'].append({
                            'source_id': section_node['id'],
                            'target_id': paragraph_node['id'],
                            'relationship_type': 'HAS_CONTENT',
                            'properties': {
                                'order': order_index,
                                'content_type': 'paragraph',
                                'document_id': document_id,
                                'created_time': datetime.now().isoformat()
                            }
                        })
                        order_index += 1
                    
                    # 创建Table节点
                    if 'table' in unit and unit['table']:
                        for table_index, table_data in enumerate(unit['table']):
                            table_node = self._create_table_node(table_data, unit, document_id, unit_index, table_index)
                            if table_node:
                                graph_structure['table_nodes'].append(table_node)
                                content_nodes.append(table_node)
                                all_content_nodes.append(table_node)
                                
                                # 建立HAS_CONTENT关系
                                graph_structure['content_relationships'].append({
                                    'source_id': section_node['id'],
                                    'target_id': table_node['id'],
                                    'relationship_type': 'HAS_CONTENT',
                                    'properties': {
                                        'order': order_index,
                                        'content_type': 'table',
                                        'document_id': document_id,
                                        'created_time': datetime.now().isoformat()
                                    }
                                })
                                order_index += 1
                                
                                # 步骤4: 创建表格行列关系
                                self._create_table_structure(table_node, table_data, graph_structure, document_id)
                    
                    # 创建Figure节点
                    if 'img' in unit and unit['img']:
                        for img_index, img_data in enumerate(unit['img']):
                            figure_node = self._create_figure_node(img_data, unit, document_id, unit_index, img_index)
                            if figure_node:
                                graph_structure['figure_nodes'].append(figure_node)
                                content_nodes.append(figure_node)
                                all_content_nodes.append(figure_node)
                                
                                # 建立HAS_CONTENT关系
                                graph_structure['content_relationships'].append({
                                    'source_id': section_node['id'],
                                    'target_id': figure_node['id'],
                                    'relationship_type': 'HAS_CONTENT',
                                    'properties': {
                                        'order': order_index,
                                        'content_type': 'figure',
                                        'document_id': document_id,
                                        'created_time': datetime.now().isoformat()
                                    }
                                })
                                order_index += 1
                                
                                # 步骤5: 建立ILLUSTRATES关系（图片说明内容）
                                if paragraph_node:
                                    graph_structure['illustration_relationships'].append({
                                        'source_id': figure_node['id'],
                                        'target_id': paragraph_node['id'],
                                        'relationship_type': 'ILLUSTRATES',
                                        'properties': {
                                            'illustration_type': img_data.get('image_type', 'general'),
                                            'ocr_text': img_data.get('ocr_text', ''),
                                            'document_id': document_id,
                                            'created_time': datetime.now().isoformat()
                                        }
                                    })
                    
                    # 提取语义实体
                    section_entities = self._extract_semantic_entities_from_section(section_node, unit, document_id)
                    graph_structure['semantic_entities'].extend(section_entities)
            
            # 步骤6: 建立Section之间的顺序关系（NEXT链）
            self._build_section_sequence_chain(graph_structure['section_nodes'], graph_structure['section_relationships'], document_id)
            
            # 步骤7: 建立所有内容节点的顺序链（保证原文复原）
            self._build_content_sequence_chain(all_content_nodes, graph_structure['sequence_relationships'], document_id)
            
            # 建立语义实体之间的关系
            entity_relationships = self._build_entity_relationships_from_sections(graph_structure['semantic_entities'], document_id)
            graph_structure['entity_relationships'].extend(entity_relationships)
            
            self.logger.info(f"Content Units图谱结构解析完成，文档ID: {document_id}, Section数: {len(graph_structure['section_nodes'])}")
            return graph_structure
            
        except Exception as e:
            self.logger.error(f"解析Content Units图谱结构失败: {str(e)}")
            return {}
    
    def _create_section_node(self, unit: Dict[str, Any], document_id: int, unit_index: int) -> Optional[Dict[str, Any]]:
        """创建Section节点，使用Title的element_id作为section_id"""
        try:
            element_id = unit.get('element_id', f"section_{unit_index}")
            title = unit.get('title', '').strip()
            content_type = unit.get('content_type', 'title_with_content')
            
            node_id = f"section_{document_id}_{element_id}"
            section_node = {
                'id': node_id,
                'type': 'Section',
                'properties': {
                    'id': node_id,  # 添加id属性用于关系匹配
                    'section_id': element_id,
                    'title': title,
                    'content_type': content_type,
                    'page_number': unit.get('page_number', 1),
                    'element_ids': json.dumps(unit.get('element_ids', []), ensure_ascii=False),
                    'hierarchy_level': unit.get('hierarchy_info', {}).get('title_level', 1),
                    'hierarchy_depth': unit.get('hierarchy_info', {}).get('hierarchy_depth', 1),
                    'coordinates': json.dumps(unit.get('coordinates', {}), ensure_ascii=False),
                    'has_table': len(unit.get('table', [])) > 0,
                    'has_image': len(unit.get('img', [])) > 0,
                    'has_chars': len(unit.get('chars', [])) > 0,
                    'document_id': document_id,
                    'order_in_document': unit_index,
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return section_node
            
        except Exception as e:
            self.logger.error(f"创建Section节点失败: {str(e)}")
            return None
    
    def _create_paragraph_node(self, unit: Dict[str, Any], document_id: int, unit_index: int) -> Optional[Dict[str, Any]]:
        """创建Paragraph节点，从content中提取正文内容"""
        try:
            element_id = unit.get('element_id', f"section_{unit_index}")
            content = unit.get('content', '').strip()
            
            # 提取正文内容（去掉标题部分）
            content_lines = content.split('\n')
            paragraph_text = ''
            
            for line in content_lines:
                if not line.startswith('标题:') and not line.startswith('图片内容:') and not line.startswith('表格数据:'):
                    paragraph_text += line.strip() + ' '
            
            paragraph_text = paragraph_text.strip()
            
            if not paragraph_text:
                return None
            
            node_id = f"paragraph_{document_id}_{element_id}"
            paragraph_node = {
                'id': node_id,
                'type': 'Paragraph',
                'properties': {
                    'id': node_id,  # 添加id属性用于关系匹配
                    'text': paragraph_text,
                    'original_content': content,
                    'section_id': element_id,
                    'page_number': unit.get('page_number', 1),
                    'word_count': len(paragraph_text.split()),
                    'char_count': len(paragraph_text),
                    'document_id': document_id,
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return paragraph_node
            
        except Exception as e:
            self.logger.error(f"创建Paragraph节点失败: {str(e)}")
            return None
    
    def _create_table_node(self, table_data: Dict[str, Any], unit: Dict[str, Any], document_id: int, unit_index: int, table_index: int) -> Optional[Dict[str, Any]]:
        """创建Table节点"""
        try:
            table_element_id = table_data.get('element_id', f"table_{unit_index}_{table_index}")
            section_id = unit.get('element_id', f"section_{unit_index}")
            raw_text = table_data.get('raw_text', '').strip()
            
            if not raw_text:
                return None
            
            node_id = f"table_{document_id}_{table_element_id}"
            table_node = {
                'id': node_id,
                'type': 'Table',
                'properties': {
                    'id': node_id,  # 添加id属性用于关系匹配
                    'table_id': table_element_id,
                    'section_id': section_id,
                    'raw_text': raw_text,
                    'table_type': table_data.get('table_type', 'general'),
                    'structured_html': table_data.get('structured_html', ''),
                    'parsed_data': json.dumps(table_data.get('parsed_data', {}), ensure_ascii=False),
                    'page_number': table_data.get('page_number', unit.get('page_number', 1)),
                    'coordinates': json.dumps(table_data.get('coordinates', {}), ensure_ascii=False),
                    'row_count': len(table_data.get('parsed_data', {}).get('rows', [])),
                    'header_count': len(table_data.get('parsed_data', {}).get('headers', [])),
                    'document_id': document_id,
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return table_node
            
        except Exception as e:
            self.logger.error(f"创建Table节点失败: {str(e)}")
            return None
    
    def _create_figure_node(self, img_data: Dict[str, Any], unit: Dict[str, Any], document_id: int, unit_index: int, img_index: int) -> Optional[Dict[str, Any]]:
        """创建Figure节点"""
        try:
            img_element_id = img_data.get('element_id', f"img_{unit_index}_{img_index}")
            section_id = unit.get('element_id', f"section_{unit_index}")
            ocr_text = img_data.get('ocr_text', '').strip()
            
            node_id = f"figure_{document_id}_{img_element_id}"
            figure_node = {
                'id': node_id,
                'type': 'Figure',
                'properties': {
                    'id': node_id,  # 添加id属性用于关系匹配
                    'figure_id': img_element_id,
                    'section_id': section_id,
                    'ocr_text': ocr_text,
                    'image_type': img_data.get('image_type', 'general'),
                    'description': img_data.get('description', ''),
                    'image_path': img_data.get('image_path', ''),
                    'page_number': img_data.get('page_number', unit.get('page_number', 1)),
                    'coordinates': json.dumps(img_data.get('coordinates', {}), ensure_ascii=False),
                    'has_ocr_text': bool(ocr_text),
                    'document_id': document_id,
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return figure_node
            
        except Exception as e:
            self.logger.error(f"创建Figure节点失败: {str(e)}")
            return None
    
    def _create_content_unit_node(self, unit: Dict[str, Any], document_id: int, unit_index: int) -> Optional[Dict[str, Any]]:
        """创建内容单元节点（包含完整的标题+内容）"""
        try:
            element_id = unit.get('element_id', f"unit_{unit_index}")
            title = unit.get('title', '').strip()
            content = unit.get('content', '').strip()
            
            if not content:
                return None
            
            content_unit_node = {
                'id': f"content_unit_{document_id}_{element_id}",
                'type': 'ContentUnit',
                'properties': {
                    'title': title,
                    'content': content,
                    'complete_text': content,  # 完整文本（标题+内容）
                    'content_type': unit.get('content_type', 'title_with_content'),
                    'original_element_id': element_id,
                    'document_id': document_id,
                    'page_number': unit.get('page_number', 1),
                    'element_ids': json.dumps(unit.get('element_ids', []), ensure_ascii=False),
                    'coordinates': json.dumps(unit.get('coordinates', {}), ensure_ascii=False),
                    'has_table': len(unit.get('table', [])) > 0,
                    'has_image': len(unit.get('img', [])) > 0,
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return content_unit_node
            
        except Exception as e:
            self.logger.error(f"创建内容单元节点失败: {str(e)}")
            return None
    
    def _create_pure_title_node(self, unit: Dict[str, Any], document_id: int, unit_index: int) -> Optional[Dict[str, Any]]:
        """创建纯标题节点"""
        try:
            element_id = unit.get('element_id', f"unit_{unit_index}")
            title = unit.get('title', '').strip()
            
            if not title:
                return None
            
            title_node = {
                'id': f"title_{document_id}_{element_id}",
                'type': 'Title',
                'properties': {
                    'text': title,
                    'original_element_id': element_id,
                    'document_id': document_id,
                    'page_number': unit.get('page_number', 1),
                    'title_level': unit.get('hierarchy_info', {}).get('title_level', 1),
                    'hierarchy_depth': unit.get('hierarchy_info', {}).get('hierarchy_depth', 1),
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return title_node
            
        except Exception as e:
            self.logger.error(f"创建纯标题节点失败: {str(e)}")
            return None
    
    def _create_table_element_node(self, table: Dict[str, Any], unit: Dict[str, Any], document_id: int, unit_index: int, table_index: int) -> Optional[Dict[str, Any]]:
        """创建表格元素节点"""
        try:
            table_id = table.get('element_id', f"unit_{unit_index}_table_{table_index}")
            raw_text = table.get('raw_text', '').strip()
            
            if not raw_text:
                return None
            
            table_node = {
                'id': f"table_{document_id}_{table_id}",
                'type': 'Table',
                'properties': {
                    'raw_text': raw_text,
                    'table_type': table.get('table_type', 'general'),
                    'structured_html': table.get('structured_html', ''),
                    'parsed_data': json.dumps(table.get('parsed_data', {}), ensure_ascii=False),
                    'original_element_id': table_id,
                    'document_id': document_id,
                    'page_number': table.get('page_number', unit.get('page_number', 1)),
                    'parent_unit_id': f"content_unit_{document_id}_{unit.get('element_id', f'unit_{unit_index}')}",
                    'coordinates': json.dumps(table.get('coordinates', {}), ensure_ascii=False),
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return table_node
            
        except Exception as e:
            self.logger.error(f"创建表格元素节点失败: {str(e)}")
            return None
    
    def _create_image_element_node(self, img: Dict[str, Any], unit: Dict[str, Any], document_id: int, unit_index: int, img_index: int) -> Optional[Dict[str, Any]]:
        """创建图片元素节点"""
        try:
            img_id = img.get('element_id', f"unit_{unit_index}_img_{img_index}")
            ocr_text = img.get('ocr_text', '').strip()
            
            img_node = {
                'id': f"image_{document_id}_{img_id}",
                'type': 'Image',
                'properties': {
                    'ocr_text': ocr_text,
                    'image_type': img.get('image_type', 'general'),
                    'description': img.get('description', ''),
                    'image_path': img.get('image_path', ''),
                    'original_element_id': img_id,
                    'document_id': document_id,
                    'page_number': img.get('page_number', unit.get('page_number', 1)),
                    'parent_unit_id': f"content_unit_{document_id}_{unit.get('element_id', f'unit_{unit_index}')}",
                    'coordinates': json.dumps(img.get('coordinates', {}), ensure_ascii=False),
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return img_node
            
        except Exception as e:
            self.logger.error(f"创建图片元素节点失败: {str(e)}")
            return None
    
    def _extract_semantic_entities_from_unit(self, content_unit_node: Dict[str, Any], unit: Dict[str, Any], document_id: int) -> List[Dict[str, Any]]:
        """从内容单元中提取语义实体"""
        try:
            content = content_unit_node['properties']['content']
            title = content_unit_node['properties']['title']
            content_unit_id = content_unit_node['id']
            
            entities = []
            
            # 从标题中提取关键概念
            if title:
                title_concepts = self._extract_concepts(title)
                for concept in title_concepts:
                    entities.append({
                        'id': f"entity_{document_id}_{len(entities)}",
                        'type': 'TitleConcept',
                        'properties': {
                            'name': concept,
                            'entity_type': 'title_concept',
                            'source_unit_id': content_unit_id,
                            'document_id': document_id,
                            'context': title,
                            'created_time': datetime.now().isoformat()
                        }
                    })
            
            # 从内容中提取关键概念
            content_concepts = self._extract_concepts(content)
            for concept in content_concepts:
                entities.append({
                    'id': f"entity_{document_id}_{len(entities)}",
                    'type': 'ContentConcept',
                    'properties': {
                        'name': concept,
                        'entity_type': 'content_concept',
                        'source_unit_id': content_unit_id,
                        'document_id': document_id,
                        'context': content[:200],
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            # 提取产品和技术名称
            products = self._extract_products_and_technologies(content)
            for product in products:
                entities.append({
                    'id': f"entity_{document_id}_{len(entities)}",
                    'type': 'Product',
                    'properties': {
                        'name': product,
                        'entity_type': 'product',
                        'source_unit_id': content_unit_id,
                        'document_id': document_id,
                        'context': content[:200],
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            # 提取技术规格
            specifications = self._extract_specifications(content)
            for spec in specifications:
                entities.append({
                    'id': f"entity_{document_id}_{len(entities)}",
                    'type': 'Specification',
                    'properties': {
                        'name': spec['name'],
                        'value': spec['value'],
                        'entity_type': 'specification',
                        'source_unit_id': content_unit_id,
                        'document_id': document_id,
                        'context': content[:200],
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            return entities
            
        except Exception as e:
            self.logger.error(f"从内容单元提取语义实体失败: {str(e)}")
            return []
    
    def _build_content_unit_hierarchy(self, content_unit_nodes: List[Dict[str, Any]], unit_relationships: List[Dict[str, Any]], document_id: int) -> None:
        """构建内容单元之间的层级关系"""
        try:
            # 按页码和标题级别排序
            sorted_units = sorted(content_unit_nodes, key=lambda x: (
                x['properties']['page_number'], 
                x['properties'].get('title_level', 1)
            ))
            
            # 建立相邻单元的关系
            for i in range(len(sorted_units) - 1):
                current_unit = sorted_units[i]
                next_unit = sorted_units[i + 1]
                
                unit_relationships.append({
                    'source_id': current_unit['id'],
                    'target_id': next_unit['id'],
                    'relationship_type': 'FOLLOWED_BY',
                    'properties': {
                        'document_id': document_id,
                        'sequence_order': i,
                        'created_time': datetime.now().isoformat()
                    }
                })
                
        except Exception as e:
            self.logger.error(f"构建内容单元层级关系失败: {str(e)}")
    
    def _build_entity_relationships_from_units(self, entities: List[Dict[str, Any]], document_id: int) -> List[Dict[str, Any]]:
        """构建基于内容单元的实体关系"""
        try:
            relationships = []
            
            # 按源单元分组实体
            unit_entities = {}
            for entity in entities:
                source_unit_id = entity['properties']['source_unit_id']
                if source_unit_id not in unit_entities:
                    unit_entities[source_unit_id] = []
                unit_entities[source_unit_id].append(entity)
            
            # 在同一单元内建立实体关系
            for unit_id, unit_entity_list in unit_entities.items():
                for i, entity1 in enumerate(unit_entity_list):
                    for j, entity2 in enumerate(unit_entity_list):
                        if i >= j:
                            continue
                        
                        rel_type = self._determine_entity_relationship_type(entity1, entity2)
                        if rel_type:
                            relationships.append({
                                'source_id': entity1['id'],
                                'target_id': entity2['id'],
                                'relationship_type': rel_type,
                                'properties': {
                                    'confidence': 0.8,
                                    'document_id': document_id,
                                    'relationship_basis': 'same_unit_co_occurrence',
                                    'source_unit_id': unit_id,
                                    'created_time': datetime.now().isoformat()
                                }
                            })
            
            return relationships
            
        except Exception as e:
            self.logger.error(f"构建单元实体关系失败: {str(e)}")
            return []
    
    def _create_table_structure(self, table_node: Dict[str, Any], table_data: Dict[str, Any], graph_structure: Dict[str, Any], document_id: int) -> None:
        """创建表格行列结构，建立SAME_ROW_AS关系"""
        try:
            parsed_data = table_data.get('parsed_data', {})
            headers = parsed_data.get('headers', [])
            rows = parsed_data.get('rows', [])
            
            table_id = table_node['id']
            
            # 创建表头行节点
            if headers:
                row_node_id = f"{table_id}_header_row"
                header_row_node = {
                    'id': row_node_id,
                    'type': 'TableRow',
                    'properties': {
                        'id': row_node_id,  # 添加id属性用于关系匹配
                        'table_id': table_id,
                        'row_type': 'header',
                        'row_index': 0,
                        'cell_count': len(headers),
                        'content': ' | '.join(headers),
                        'document_id': document_id,
                        'created_time': datetime.now().isoformat()
                    }
                }
                graph_structure['table_row_nodes'].append(header_row_node)
                
                # 建立表格与行的关系
                graph_structure['table_relationships'].append({
                    'source_id': table_id,
                    'target_id': header_row_node['id'],
                    'relationship_type': 'HAS_ROW',
                    'properties': {
                        'row_index': 0,
                        'row_type': 'header',
                        'document_id': document_id,
                        'created_time': datetime.now().isoformat()
                    }
                })
                
                # 为表头创建单元格节点
                for col_index, header in enumerate(headers):
                    cell_node_id = f"{table_id}_header_cell_{col_index}"
                    cell_node = {
                        'id': cell_node_id,
                        'type': 'TableCell',
                        'properties': {
                            'id': cell_node_id,  # 添加id属性用于关系匹配
                            'table_id': table_id,
                            'row_id': header_row_node['id'],
                            'cell_type': 'header',
                            'row_index': 0,
                            'col_index': col_index,
                            'content': header,
                            'document_id': document_id,
                            'created_time': datetime.now().isoformat()
                        }
                    }
                    graph_structure['table_cell_nodes'].append(cell_node)
                    
                    # 建立行与单元格的关系
                    graph_structure['table_relationships'].append({
                        'source_id': header_row_node['id'],
                        'target_id': cell_node['id'],
                        'relationship_type': 'HAS_CELL',
                        'properties': {
                            'col_index': col_index,
                            'document_id': document_id,
                            'created_time': datetime.now().isoformat()
                        }
                    })
            
            # 创建数据行节点
            for row_index, row_data in enumerate(rows):
                if not isinstance(row_data, list):
                    continue
                    
                data_row_node_id = f"{table_id}_data_row_{row_index}"
                data_row_node = {
                    'id': data_row_node_id,
                    'type': 'TableRow',
                    'properties': {
                        'id': data_row_node_id,  # 添加id属性用于关系匹配
                        'table_id': table_id,
                        'row_type': 'data',
                        'row_index': row_index + 1,  # +1 because header is index 0
                        'cell_count': len(row_data),
                        'content': ' | '.join(str(cell) for cell in row_data),
                        'document_id': document_id,
                        'created_time': datetime.now().isoformat()
                    }
                }
                graph_structure['table_row_nodes'].append(data_row_node)
                
                # 建立表格与行的关系
                graph_structure['table_relationships'].append({
                    'source_id': table_id,
                    'target_id': data_row_node['id'],
                    'relationship_type': 'HAS_ROW',
                    'properties': {
                        'row_index': row_index + 1,
                        'row_type': 'data',
                        'document_id': document_id,
                        'created_time': datetime.now().isoformat()
                    }
                })
                
                # 为数据行创建单元格节点
                for col_index, cell_content in enumerate(row_data):
                    data_cell_node_id = f"{table_id}_data_cell_{row_index}_{col_index}"
                    cell_node = {
                        'id': data_cell_node_id,
                        'type': 'TableCell',
                        'properties': {
                            'id': data_cell_node_id,  # 添加id属性用于关系匹配
                            'table_id': table_id,
                            'row_id': data_row_node['id'],
                            'cell_type': 'data',
                            'row_index': row_index + 1,
                            'col_index': col_index,
                            'content': str(cell_content),
                            'document_id': document_id,
                            'created_time': datetime.now().isoformat()
                        }
                    }
                    graph_structure['table_cell_nodes'].append(cell_node)
                    
                    # 建立行与单元格的关系
                    graph_structure['table_relationships'].append({
                        'source_id': data_row_node['id'],
                        'target_id': cell_node['id'],
                        'relationship_type': 'HAS_CELL',
                        'properties': {
                            'col_index': col_index,
                            'document_id': document_id,
                            'created_time': datetime.now().isoformat()
                        }
                    })
                    
                    # 建立同行单元格之间的SAME_ROW_AS关系
                    if col_index > 0:
                        prev_cell_id = f"{table_id}_data_cell_{row_index}_{col_index-1}"
                        graph_structure['table_relationships'].append({
                            'source_id': prev_cell_id,
                            'target_id': data_cell_node_id,
                            'relationship_type': 'SAME_ROW_AS',
                            'properties': {
                                'row_index': row_index + 1,
                                'document_id': document_id,
                                'created_time': datetime.now().isoformat()
                            }
                        })
                        
        except Exception as e:
            self.logger.error(f"创建表格结构失败: {str(e)}")
    
    def _build_section_sequence_chain(self, section_nodes: List[Dict[str, Any]], section_relationships: List[Dict[str, Any]], document_id: int) -> None:
        """建立Section之间的顺序关系（NEXT链）"""
        try:
            # 按页码和文档内顺序排序
            sorted_sections = sorted(section_nodes, key=lambda x: (
                x['properties']['page_number'], 
                x['properties']['order_in_document']
            ))
            
            # 建立相邻Section的NEXT关系
            for i in range(len(sorted_sections) - 1):
                current_section = sorted_sections[i]
                next_section = sorted_sections[i + 1]
                
                section_relationships.append({
                    'source_id': current_section['id'],
                    'target_id': next_section['id'],
                    'relationship_type': 'NEXT',
                    'properties': {
                        'sequence_order': i,
                        'document_id': document_id,
                        'created_time': datetime.now().isoformat()
                    }
                })
                
        except Exception as e:
            self.logger.error(f"构建Section顺序链失败: {str(e)}")
    
    def _build_content_sequence_chain(self, all_content_nodes: List[Dict[str, Any]], sequence_relationships: List[Dict[str, Any]], document_id: int) -> None:
        """建立所有内容节点的顺序链（保证原文复原）"""
        try:
            # 按页码和节点类型排序，确保阅读顺序
            sorted_content = sorted(all_content_nodes, key=lambda x: (
                x['properties']['page_number'],
                x['properties'].get('section_id', ''),  # 同section内的内容保持一起
                x['type']  # Paragraph, Table, Figure的类型顺序
            ))
            
            # 建立相邻内容节点的NEXT关系
            for i in range(len(sorted_content) - 1):
                current_content = sorted_content[i]
                next_content = sorted_content[i + 1]
                
                sequence_relationships.append({
                    'source_id': current_content['id'],
                    'target_id': next_content['id'],
                    'relationship_type': 'NEXT',
                    'properties': {
                        'sequence_order': i,
                        'content_type_from': current_content['type'],
                        'content_type_to': next_content['type'],
                        'document_id': document_id,
                        'created_time': datetime.now().isoformat()
                    }
                })
                
        except Exception as e:
            self.logger.error(f"构建内容顺序链失败: {str(e)}")
    
    def _extract_semantic_entities_from_section(self, section_node: Dict[str, Any], unit: Dict[str, Any], document_id: int) -> List[Dict[str, Any]]:
        """从Section中提取语义实体"""
        try:
            title = section_node['properties']['title']
            content = unit.get('content', '')
            section_id = section_node['id']
            
            entities = []
            
            # 从标题中提取关键概念
            if title:
                title_concepts = self._extract_concepts(title)
                for concept in title_concepts:
                    entity_id = f"entity_{document_id}_{len(entities)}"
                    entities.append({
                        'id': entity_id,
                        'type': 'TitleConcept',
                        'properties': {
                            'id': entity_id,  # 添加id属性用于关系匹配
                            'name': concept,
                            'entity_type': 'title_concept',
                            'source_section_id': section_id,
                            'document_id': document_id,
                            'context': title,
                            'created_time': datetime.now().isoformat()
                        }
                    })
            
            # 从内容中提取关键概念
            content_concepts = self._extract_concepts(content)
            for concept in content_concepts:
                entity_id = f"entity_{document_id}_{len(entities)}"
                entities.append({
                    'id': entity_id,
                    'type': 'ContentConcept',
                    'properties': {
                        'id': entity_id,  # 添加id属性用于关系匹配
                        'name': concept,
                        'entity_type': 'content_concept',
                        'source_section_id': section_id,
                        'document_id': document_id,
                        'context': content[:200],
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            # 提取产品和技术名称
            products = self._extract_products_and_technologies(content)
            for product in products:
                entity_id = f"entity_{document_id}_{len(entities)}"
                entities.append({
                    'id': entity_id,
                    'type': 'Product',
                    'properties': {
                        'id': entity_id,  # 添加id属性用于关系匹配
                        'name': product,
                        'entity_type': 'product',
                        'source_section_id': section_id,
                        'document_id': document_id,
                        'context': content[:200],
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            # 提取技术规格
            specifications = self._extract_specifications(content)
            for spec in specifications:
                entity_id = f"entity_{document_id}_{len(entities)}"
                entities.append({
                    'id': entity_id,
                    'type': 'Specification',
                    'properties': {
                        'id': entity_id,  # 添加id属性用于关系匹配
                        'name': spec['name'],
                        'value': spec['value'],
                        'entity_type': 'specification',
                        'source_section_id': section_id,
                        'document_id': document_id,
                        'context': content[:200],
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            return entities
            
        except Exception as e:
            self.logger.error(f"从Section提取语义实体失败: {str(e)}")
            return []
    
    def _build_entity_relationships_from_sections(self, entities: List[Dict[str, Any]], document_id: int) -> List[Dict[str, Any]]:
        """构建基于Section的实体关系"""
        try:
            relationships = []
            
            # 按源Section分组实体
            section_entities = {}
            for entity in entities:
                source_section_id = entity['properties']['source_section_id']
                if source_section_id not in section_entities:
                    section_entities[source_section_id] = []
                section_entities[source_section_id].append(entity)
            
            # 在同一Section内建立实体关系
            for section_id, section_entity_list in section_entities.items():
                for i, entity1 in enumerate(section_entity_list):
                    for j, entity2 in enumerate(section_entity_list):
                        if i >= j:
                            continue
                        
                        rel_type = self._determine_entity_relationship_type(entity1, entity2)
                        if rel_type:
                            relationships.append({
                                'source_id': entity1['id'],
                                'target_id': entity2['id'],
                                'relationship_type': rel_type,
                                'properties': {
                                    'confidence': 0.8,
                                    'document_id': document_id,
                                    'relationship_basis': 'same_section_co_occurrence',
                                    'source_section_id': section_id,
                                    'created_time': datetime.now().isoformat()
                                }
                            })
            
            return relationships
            
        except Exception as e:
            self.logger.error(f"构建Section实体关系失败: {str(e)}")
            return []
    
    def _parse_pdf_json_to_graph_structure(self, pdf_data: Dict[str, Any], document_id: int) -> Dict[str, Any]:
        """
        解析PDF JSON数据，构建图谱结构
        重点关注标题-内容的层级关系，确保GraphRAG查询的完整性
        
        Args:
            pdf_data: PDF提取的JSON数据
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 图谱结构数据
        """
        try:
            elements = pdf_data.get('elements', [])
            
            # 存储图谱结构
            graph_structure = {
                'document_node': None,
                'title_nodes': [],
                'content_nodes': [],
                'title_content_relationships': [],
                'content_hierarchy_relationships': [],
                'semantic_entities': [],
                'entity_relationships': []
            }
            
            # 创建文档根节点
            doc_info = pdf_data.get('document_info', {})
            graph_structure['document_node'] = {
                'id': f"doc_{document_id}",
                'type': 'Document',
                'properties': {
                    'document_id': document_id,
                    'filename': doc_info.get('filename', ''),
                    'source_file': doc_info.get('source_file', ''),
                    'total_elements': doc_info.get('total_elements', 0),
                    'extraction_time': doc_info.get('extraction_time', ''),
                    'created_time': datetime.now().isoformat()
                }
            }
            
            # 解析标题和内容的层级结构
            current_title_stack = []  # 标题栈，支持多级标题
            
            for element in elements:
                element_type = element.get('type', '').lower()
                element_category = element.get('category', '').lower()
                text = element.get('text', '').strip()
                element_id = element.get('id', '')
                
                if not text:
                    continue
                
                # 处理标题节点
                if element_type == 'title' or element_category == 'title':
                    title_node = self._create_title_node(element, document_id)
                    if title_node:
                        graph_structure['title_nodes'].append(title_node)
                        
                        # 管理标题层级栈
                        title_level = element.get('metadata', {}).get('title_level', 1)
                        self._update_title_stack(current_title_stack, title_node, title_level)
                        
                        # 创建标题层级关系
                        if len(current_title_stack) > 1:
                            parent_title = current_title_stack[-2]
                            child_title = current_title_stack[-1]
                            graph_structure['content_hierarchy_relationships'].append({
                                'parent_id': parent_title['id'],
                                'child_id': child_title['id'],
                                'relationship_type': 'HAS_SUBTITLE',
                                'properties': {
                                    'hierarchy_level': title_level,
                                    'document_id': document_id
                                }
                            })
                
                # 处理内容节点
                elif element_type in ['narrativetext', 'text', 'table', 'image', 'figure'] or \
                     element_category in ['narrativetext', 'text', 'table', 'image', 'figure']:
                    
                    content_node = self._create_content_node(element, document_id)
                    if content_node:
                        graph_structure['content_nodes'].append(content_node)
                        
                        # 建立内容与标题的关系
                        parent_title = self._find_parent_title(element, current_title_stack)
                        if parent_title:
                            graph_structure['title_content_relationships'].append({
                                'title_id': parent_title['id'],
                                'content_id': content_node['id'],
                                'relationship_type': 'HAS_CONTENT',
                                'properties': {
                                    'content_type': content_node['properties']['content_type'],
                                    'page_number': content_node['properties']['page_number'],
                                    'document_id': document_id
                                }
                            })
                        else:
                            # 独立内容直接连接到文档节点
                            graph_structure['title_content_relationships'].append({
                                'title_id': graph_structure['document_node']['id'],
                                'content_id': content_node['id'],
                                'relationship_type': 'HAS_CONTENT',
                                'properties': {
                                    'content_type': content_node['properties']['content_type'],
                                    'page_number': content_node['properties']['page_number'],
                                    'document_id': document_id,
                                    'is_standalone': True
                                }
                            })
                        
                        # 提取语义实体
                        semantic_entities = self._extract_semantic_entities_from_content(content_node, document_id)
                        graph_structure['semantic_entities'].extend(semantic_entities)
            
            # 建立语义实体之间的关系
            entity_relationships = self._build_entity_relationships(graph_structure['semantic_entities'], document_id)
            graph_structure['entity_relationships'].extend(entity_relationships)
            
            # 建立标题与语义实体的关系
            title_entity_relationships = self._build_title_entity_relationships(
                graph_structure['title_nodes'], 
                graph_structure['semantic_entities'], 
                document_id
            )
            graph_structure['entity_relationships'].extend(title_entity_relationships)
            
            self.logger.info(f"PDF图谱结构解析完成，文档ID: {document_id}")
            return graph_structure
            
        except Exception as e:
            self.logger.error(f"解析PDF图谱结构失败: {str(e)}")
            return {}
    
    def _create_title_node(self, element: Dict[str, Any], document_id: int) -> Optional[Dict[str, Any]]:
        """创建标题节点"""
        try:
            element_id = element.get('id', '')
            text = element.get('text', '').strip()
            metadata = element.get('metadata', {})
            
            if not text:
                return None
            
            title_node = {
                'id': f"title_{element_id}",
                'type': 'Title',
                'properties': {
                    'text': text,
                    'original_element_id': element_id,
                    'document_id': document_id,
                    'page_number': metadata.get('page_number', 1),
                    'title_level': metadata.get('title_level', 1),
                    'hierarchy_depth': metadata.get('hierarchy_depth', 1),
                    'detection_class_prob': metadata.get('detection_class_prob', 0.0),
                    'coordinates': json.dumps(metadata.get('coordinates', {}), ensure_ascii=False),
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return title_node
            
        except Exception as e:
            self.logger.error(f"创建标题节点失败: {str(e)}")
            return None
    
    def _create_content_node(self, element: Dict[str, Any], document_id: int) -> Optional[Dict[str, Any]]:
        """创建内容节点"""
        try:
            element_id = element.get('id', '')
            text = element.get('text', '').strip()
            element_type = element.get('type', '').lower()
            element_category = element.get('category', '').lower()
            metadata = element.get('metadata', {})
            
            if not text:
                return None
            
            # 确定内容类型
            content_type = element_type if element_type in ['table', 'image', 'figure'] else 'text'
            
            content_node = {
                'id': f"content_{element_id}",
                'type': 'Content',
                'properties': {
                    'text': text,
                    'content_type': content_type,
                    'original_element_id': element_id,
                    'document_id': document_id,
                    'page_number': metadata.get('page_number', 1),
                    'detection_class_prob': metadata.get('detection_class_prob', 0.0),
                    'coordinates': json.dumps(metadata.get('coordinates', {}), ensure_ascii=False),
                    'belongs_to_titles': json.dumps(metadata.get('belongs_to_titles', []), ensure_ascii=False),
                    'created_time': datetime.now().isoformat()
                }
            }
            
            return content_node
            
        except Exception as e:
            self.logger.error(f"创建内容节点失败: {str(e)}")
            return None
    
    def _update_title_stack(self, title_stack: List[Dict[str, Any]], new_title: Dict[str, Any], title_level: int) -> None:
        """更新标题层级栈"""
        try:
            # 移除比当前标题级别更深的标题
            while title_stack and title_stack[-1]['properties']['title_level'] >= title_level:
                title_stack.pop()
            
            # 添加新标题
            title_stack.append(new_title)
            
        except Exception as e:
            self.logger.error(f"更新标题栈失败: {str(e)}")
    
    def _find_parent_title(self, element: Dict[str, Any], title_stack: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """找到内容元素的父标题"""
        try:
            # 首先检查belongs_to_titles字段
            belongs_to_titles = element.get('metadata', {}).get('belongs_to_titles', [])
            if belongs_to_titles:
                target_title_id = belongs_to_titles[0].get('id')
                for title in title_stack:
                    if title['properties']['original_element_id'] == target_title_id:
                        return title
            
            # 如果没有明确关联，返回栈顶标题（最近的标题）
            return title_stack[-1] if title_stack else None
            
        except Exception as e:
            self.logger.error(f"查找父标题失败: {str(e)}")
            return None
    
    def _extract_semantic_entities_from_content(self, content_node: Dict[str, Any], document_id: int) -> List[Dict[str, Any]]:
        """从内容中提取语义实体"""
        try:
            text = content_node['properties']['text']
            content_id = content_node['id']
            
            entities = []
            
            # 提取关键概念和术语
            concepts = self._extract_concepts(text)
            for concept in concepts:
                entities.append({
                    'id': f"entity_{document_id}_{len(entities)}",
                    'type': 'Concept',
                    'properties': {
                        'name': concept,
                        'entity_type': 'concept',
                        'source_content_id': content_id,
                        'document_id': document_id,
                        'context': text[:200],  # 保存上下文
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            # 提取产品和技术名称
            products = self._extract_products_and_technologies(text)
            for product in products:
                entities.append({
                    'id': f"entity_{document_id}_{len(entities)}",
                    'type': 'Product',
                    'properties': {
                        'name': product,
                        'entity_type': 'product',
                        'source_content_id': content_id,
                        'document_id': document_id,
                        'context': text[:200],
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            # 提取数值和规格
            specifications = self._extract_specifications(text)
            for spec in specifications:
                entities.append({
                    'id': f"entity_{document_id}_{len(entities)}",
                    'type': 'Specification',
                    'properties': {
                        'name': spec['name'],
                        'value': spec['value'],
                        'entity_type': 'specification',
                        'source_content_id': content_id,
                        'document_id': document_id,
                        'context': text[:200],
                        'created_time': datetime.now().isoformat()
                    }
                })
            
            return entities
            
        except Exception as e:
            self.logger.error(f"提取语义实体失败: {str(e)}")
            return []
    
    def _extract_concepts(self, text: str) -> List[str]:
        """提取关键概念"""
        try:
            concepts = []
            
            # 生物技术相关概念模式
            bio_patterns = [
                r'[A-Z]{2,5}[-\s]*\d*\s*(?:细胞|蛋白|试剂|检测|分析)',
                r'(?:宿主|残留|检测|试剂盒|表达系统|过程开发)',
                r'[A-Z]{3,}(?:[-\s]*\w+)*(?=\s|$)',  # 英文缩写
                r'[\u4e00-\u9fff]{2,6}(?:检测|试剂|方法|技术|系统)',
            ]
            
            for pattern in bio_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                concepts.extend([match.strip() for match in matches if len(match.strip()) > 1])
            
            # 去重并过滤
            unique_concepts = list(set(concepts))
            return [concept for concept in unique_concepts if len(concept) > 2 and len(concept) < 50]
            
        except Exception as e:
            self.logger.error(f"提取概念失败: {str(e)}")
            return []
    
    def _extract_products_and_technologies(self, text: str) -> List[str]:
        """提取产品和技术名称"""
        try:
            products = []
            
            # 产品模式
            product_patterns = [
                r'CHO[-\s]*K\d+\s*(?:细胞|表达系统)',
                r'[\u4e00-\u9fff]{2,8}(?:试剂盒|检测盒)',
                r'[A-Z]+[-\s]*\d*\s*(?:试剂|检测)',
                r'(?:多宁|DIONING)[\u4e00-\u9fff\w\s]*'
            ]
            
            for pattern in product_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                products.extend([match.strip() for match in matches])
            
            return list(set([product for product in products if len(product) > 2]))
            
        except Exception as e:
            self.logger.error(f"提取产品失败: {str(e)}")
            return []
    
    def _extract_specifications(self, text: str) -> List[Dict[str, str]]:
        """提取技术规格和数值"""
        try:
            specifications = []
            
            # 数值模式
            spec_patterns = [
                r'(\d+(?:\.\d+)?)\s*%\s*以上',
                r'(\d+(?:\.\d+)?)\s*(?:mg|μg|ng|ml|μl)',
                r'(\d+(?:\.\d+)?)\s*(?:度|温度|℃)',
                r'(\d+(?:\.\d+)?)\s*(?:小时|分钟|秒)',
                r'pH\s*(\d+(?:\.\d+)?)',
                r'(\d+(?:\.\d+)?)\s*(?:倍|次|fold)'
            ]
            
            for pattern in spec_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    full_match = match.group(0)
                    value = match.group(1)
                    specifications.append({
                        'name': full_match,
                        'value': value
                    })
            
            return specifications
            
        except Exception as e:
            self.logger.error(f"提取规格失败: {str(e)}")
            return []
    
    def _build_entity_relationships(self, entities: List[Dict[str, Any]], document_id: int) -> List[Dict[str, Any]]:
        """构建实体间关系"""
        try:
            relationships = []
            
            # 基于实体类型和共现构建关系
            for i, entity1 in enumerate(entities):
                for j, entity2 in enumerate(entities):
                    if i >= j:
                        continue
                    
                    # 检查是否来自同一内容源
                    if entity1['properties']['source_content_id'] == entity2['properties']['source_content_id']:
                        rel_type = self._determine_entity_relationship_type(entity1, entity2)
                        if rel_type:
                            relationships.append({
                                'source_id': entity1['id'],
                                'target_id': entity2['id'],
                                'relationship_type': rel_type,
                                'properties': {
                                    'confidence': 0.8,  # 共现关系置信度
                                    'document_id': document_id,
                                    'relationship_basis': 'co_occurrence',
                                    'created_time': datetime.now().isoformat()
                                }
                            })
            
            return relationships
            
        except Exception as e:
            self.logger.error(f"构建实体关系失败: {str(e)}")
            return []
    
    def _determine_entity_relationship_type(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> Optional[str]:
        """确定实体间关系类型"""
        try:
            type1 = entity1['properties']['entity_type']
            type2 = entity2['properties']['entity_type']
            
            # 定义关系类型映射
            relationship_map = {
                ('product', 'concept'): 'USES_CONCEPT',
                ('product', 'specification'): 'HAS_SPECIFICATION',
                ('concept', 'specification'): 'MEASURED_BY',
                ('concept', 'concept'): 'RELATED_TO',
                ('product', 'product'): 'RELATED_TO'
            }
            
            # 确保关系的一致性（按字母顺序）
            key = tuple(sorted([type1, type2]))
            return relationship_map.get(key, 'RELATED_TO')
            
        except Exception as e:
            self.logger.error(f"确定实体关系类型失败: {str(e)}")
            return None
    
    def _build_title_entity_relationships(self, title_nodes: List[Dict[str, Any]], entities: List[Dict[str, Any]], document_id: int) -> List[Dict[str, Any]]:
        """构建标题与实体的关系"""
        try:
            relationships = []
            
            for entity in entities:
                source_content_id = entity['properties']['source_content_id']
                
                # 找到包含此内容的标题
                for title in title_nodes:
                    title_id = title['id']
                    # 这里可以通过内容归属关系来判断
                    # 简化处理：假设同一文档下的实体都与标题相关
                    relationships.append({
                        'source_id': title_id,
                        'target_id': entity['id'],
                        'relationship_type': 'MENTIONS',
                        'properties': {
                            'confidence': 0.7,
                            'document_id': document_id,
                            'created_time': datetime.now().isoformat()
                        }
                    })
                    break  # 只关联最相关的一个标题
            
            return relationships
            
        except Exception as e:
            self.logger.error(f"构建标题实体关系失败: {str(e)}")
            return []
    
    def _create_graph_nodes(self, graph_structure: Dict[str, Any], document_id: int) -> int:
        """在Neo4j中创建图谱节点"""
        try:
            nodes_created = 0
            
            # 创建文档节点
            if graph_structure['document_node']:
                node = graph_structure['document_node']
                success = self.neo4j_manager.create_node(node['type'], node['properties'])
                if success:
                    nodes_created += 1
            
            # 创建新结构的节点
            # 创建Section节点
            if 'section_nodes' in graph_structure:
                for section_node in graph_structure['section_nodes']:
                    success = self.neo4j_manager.create_node(section_node['type'], section_node['properties'])
                    if success:
                        nodes_created += 1
            
            # 创建Paragraph节点
            if 'paragraph_nodes' in graph_structure:
                for paragraph_node in graph_structure['paragraph_nodes']:
                    success = self.neo4j_manager.create_node(paragraph_node['type'], paragraph_node['properties'])
                    if success:
                        nodes_created += 1
            
            # 创建Figure节点
            if 'figure_nodes' in graph_structure:
                for figure_node in graph_structure['figure_nodes']:
                    success = self.neo4j_manager.create_node(figure_node['type'], figure_node['properties'])
                    if success:
                        nodes_created += 1
            
            # 创建Table节点
            if 'table_nodes' in graph_structure:
                for table_node in graph_structure['table_nodes']:
                    success = self.neo4j_manager.create_node(table_node['type'], table_node['properties'])
                    if success:
                        nodes_created += 1
            
            # 创建TableRow节点
            if 'table_row_nodes' in graph_structure:
                for row_node in graph_structure['table_row_nodes']:
                    success = self.neo4j_manager.create_node(row_node['type'], row_node['properties'])
                    if success:
                        nodes_created += 1
            
            # 创建TableCell节点
            if 'table_cell_nodes' in graph_structure:
                for cell_node in graph_structure['table_cell_nodes']:
                    success = self.neo4j_manager.create_node(cell_node['type'], cell_node['properties'])
                    if success:
                        nodes_created += 1
            
            # 兼容性支持：创建旧格式的节点
            # 创建内容单元节点（content_units格式）
            if 'content_unit_nodes' in graph_structure:
                for content_unit_node in graph_structure['content_unit_nodes']:
                    success = self.neo4j_manager.create_node(content_unit_node['type'], content_unit_node['properties'])
                    if success:
                        nodes_created += 1
            
            # 创建内容元素节点（表格、图片等）
            if 'content_element_nodes' in graph_structure:
                for element_node in graph_structure['content_element_nodes']:
                    success = self.neo4j_manager.create_node(element_node['type'], element_node['properties'])
                if success:
                    nodes_created += 1
            
            # 创建标题节点
            if 'title_nodes' in graph_structure:
            for title_node in graph_structure['title_nodes']:
                success = self.neo4j_manager.create_node(title_node['type'], title_node['properties'])
                if success:
                    nodes_created += 1
            
            # 创建内容节点（兼容原有格式）
            if 'content_nodes' in graph_structure:
            for content_node in graph_structure['content_nodes']:
                success = self.neo4j_manager.create_node(content_node['type'], content_node['properties'])
                if success:
                    nodes_created += 1
            
            # 创建语义实体节点
            if 'semantic_entities' in graph_structure:
            for entity in graph_structure['semantic_entities']:
                success = self.neo4j_manager.create_node(entity['type'], entity['properties'])
                if success:
                    nodes_created += 1
            
            return nodes_created
            
        except Exception as e:
            self.logger.error(f"创建图谱节点失败: {str(e)}")
            return 0
    
    def _create_graph_relationships(self, graph_structure: Dict[str, Any], document_id: int) -> int:
        """在Neo4j中创建图谱关系"""
        try:
            relationships_created = 0
            
            # 创建新结构的关系
            # 创建Section之间的关系
            if 'section_relationships' in graph_structure:
                for rel in graph_structure['section_relationships']:
                    success = self._create_relationship_by_property(
                        rel['source_id'], 
                        rel['target_id'], 
                        rel['relationship_type'], 
                        rel['properties']
                    )
                    if success:
                        relationships_created += 1
            
            # 创建HAS_CONTENT关系（Section -> Paragraph/Figure/Table）
            if 'content_relationships' in graph_structure:
                for rel in graph_structure['content_relationships']:
                    success = self._create_relationship_by_property(
                        rel['source_id'], 
                        rel['target_id'], 
                        rel['relationship_type'], 
                        rel['properties']
                    )
                    if success:
                        relationships_created += 1
            
            # 创建NEXT顺序关系
            if 'sequence_relationships' in graph_structure:
                for rel in graph_structure['sequence_relationships']:
                    success = self._create_relationship_by_property(
                        rel['source_id'], 
                        rel['target_id'], 
                        rel['relationship_type'], 
                        rel['properties']
                    )
                    if success:
                        relationships_created += 1
            
            # 创建ILLUSTRATES关系（Figure -> Paragraph）
            if 'illustration_relationships' in graph_structure:
                for rel in graph_structure['illustration_relationships']:
                    success = self._create_relationship_by_property(
                        rel['source_id'], 
                        rel['target_id'], 
                        rel['relationship_type'], 
                        rel['properties']
                    )
                    if success:
                        relationships_created += 1
            
            # 创建表格内部关系（HAS_ROW, HAS_CELL, SAME_ROW_AS）
            if 'table_relationships' in graph_structure:
                for rel in graph_structure['table_relationships']:
                    success = self._create_relationship_by_property(
                        rel['source_id'], 
                        rel['target_id'], 
                        rel['relationship_type'], 
                        rel['properties']
                    )
                    if success:
                        relationships_created += 1
            
            # 兼容性支持：创建旧格式的关系
            # 创建内容单元关系（content_units格式）
            if 'unit_relationships' in graph_structure:
                for rel in graph_structure['unit_relationships']:
                    success = self._create_relationship_by_property(
                        rel['source_id'], 
                        rel['target_id'], 
                        rel['relationship_type'], 
                        rel['properties']
                    )
                    if success:
                        relationships_created += 1
            
            # 创建元素关系（表格、图片等）
            if 'element_relationships' in graph_structure:
                for rel in graph_structure['element_relationships']:
                    success = self._create_relationship_by_property(
                        rel['source_id'], 
                        rel['target_id'], 
                        rel['relationship_type'], 
                        rel['properties']
                    )
                    if success:
                        relationships_created += 1
            
            # 创建标题-内容关系（兼容原有格式）
            if 'title_content_relationships' in graph_structure:
            for rel in graph_structure['title_content_relationships']:
                success = self._create_relationship_by_property(
                    rel['title_id'], 
                    rel['content_id'], 
                    rel['relationship_type'], 
                    rel['properties']
                )
                if success:
                    relationships_created += 1
            
            # 创建内容层级关系（兼容原有格式）
            if 'content_hierarchy_relationships' in graph_structure:
            for rel in graph_structure['content_hierarchy_relationships']:
                success = self._create_relationship_by_property(
                    rel['parent_id'], 
                    rel['child_id'], 
                    rel['relationship_type'], 
                    rel['properties']
                )
                if success:
                    relationships_created += 1
            
            # 创建实体关系
            if 'entity_relationships' in graph_structure:
            for rel in graph_structure['entity_relationships']:
                success = self._create_relationship_by_property(
                    rel['source_id'], 
                    rel['target_id'], 
                    rel['relationship_type'], 
                    rel['properties']
                )
                if success:
                    relationships_created += 1
            
            return relationships_created
            
        except Exception as e:
            self.logger.error(f"创建图谱关系失败: {str(e)}")
            return 0
    
    def _create_relationship_by_property(self, source_id: str, target_id: str, rel_type: str, properties: Dict[str, Any]) -> bool:
        """通过属性匹配创建关系"""
        try:
            # 构建Cypher查询，通过节点的id属性匹配
            query = """
            MATCH (source), (target)
            WHERE source.id = $source_id AND target.id = $target_id
            CREATE (source)-[r:%s]->(target)
            SET r = $properties
            RETURN r
            """ % rel_type
            
            parameters = {
                'source_id': source_id,
                'target_id': target_id,
                'properties': properties
            }
            
            result = self.neo4j_manager.execute_query(query, parameters)
            return len(result) > 0
            
        except Exception as e:
            self.logger.error(f"创建关系失败: {str(e)}")
            return False
    

    

    

    

    

    

    

    

    
    def process_content_units_to_graph(self, content_units_file_path: str, document_id: int) -> Dict[str, Any]:
        """
        便捷方法：直接处理content_units.json文件构建知识图谱
        推荐使用此方法，因为content_units.json数据结构更适合GraphRAG查询
        
        Args:
            content_units_file_path: content_units.json文件路径
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            self.logger.info(f"开始处理content_units.json文件构建知识图谱，文档ID: {document_id}")
            return self.process_pdf_json_to_graph(content_units_file_path, document_id)
            
        except Exception as e:
            self.logger.error(f"处理content_units.json文件失败: {str(e)}")
            return {
                'success': False,
                'message': f'处理content_units.json文件失败: {str(e)}',
                'nodes_count': 0,
                'relationships_count': 0
            }
    
