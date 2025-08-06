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
import requests

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
            json_file_path: JSON文件路径
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 加载JSON数据
            with open(json_file_path, 'r', encoding='utf-8') as file:
                pdf_data = json.load(file)
            
            # 解析PDF数据，构建图谱结构
            graph_structure = self._parse_pdf_json_to_graph_structure(pdf_data, document_id)
            
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
            
            # 存储图谱信息到MySQL
            self._store_graph_info_to_mysql(graph_structure, document_id)
            
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
            
            # 创建标题节点
            for title_node in graph_structure['title_nodes']:
                success = self.neo4j_manager.create_node(title_node['type'], title_node['properties'])
                if success:
                    nodes_created += 1
            
            # 创建内容节点
            for content_node in graph_structure['content_nodes']:
                success = self.neo4j_manager.create_node(content_node['type'], content_node['properties'])
                if success:
                    nodes_created += 1
            
            # 创建语义实体节点
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
            
            # 创建标题-内容关系
            for rel in graph_structure['title_content_relationships']:
                success = self._create_relationship_by_property(
                    rel['title_id'], 
                    rel['content_id'], 
                    rel['relationship_type'], 
                    rel['properties']
                )
                if success:
                    relationships_created += 1
            
            # 创建内容层级关系
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
    
    def _store_graph_info_to_mysql(self, graph_structure: Dict[str, Any], document_id: int) -> None:
        """存储图谱信息到MySQL"""
        try:
            # 存储实体信息
            for entity in graph_structure['semantic_entities']:
                entity_data = {
                    'name': entity['properties']['name'],
                    'entity_type': entity['properties']['entity_type'],
                    'description': entity['properties'].get('context', ''),
                    'properties': json.dumps({
                        'neo4j_node_id': entity['id'],
                        'source_content_id': entity['properties']['source_content_id'],
                        'document_id': document_id
                    }, ensure_ascii=False),
                    'create_time': datetime.now()
                }
                
                self.mysql_manager.insert_data('entities', entity_data)
            
            # 存储关系信息
            for rel in graph_structure['entity_relationships']:
                # 获取实体的MySQL ID
                source_entity = next((e for e in graph_structure['semantic_entities'] if e['id'] == rel['source_id']), None)
                target_entity = next((e for e in graph_structure['semantic_entities'] if e['id'] == rel['target_id']), None)
                
                if source_entity and target_entity:
                    # 查找对应的MySQL实体ID
                    source_query = "SELECT id FROM entities WHERE name = :name AND JSON_EXTRACT(properties, '$.document_id') = :doc_id LIMIT 1"
                    target_query = "SELECT id FROM entities WHERE name = :name AND JSON_EXTRACT(properties, '$.document_id') = :doc_id LIMIT 1"
                    
                    source_result = self.mysql_manager.execute_query(
                        source_query, 
                        {'name': source_entity['properties']['name'], 'doc_id': document_id}
                    )
                    target_result = self.mysql_manager.execute_query(
                        target_query, 
                        {'name': target_entity['properties']['name'], 'doc_id': document_id}
                    )
                    
                    if source_result and target_result:
                        relation_data = {
                            'head_entity_id': source_result[0]['id'],
                            'tail_entity_id': target_result[0]['id'],
                            'relation_type': rel['relationship_type'],
                            'confidence': rel['properties']['confidence'],
                            'source_document_id': document_id,
                            'create_time': datetime.now()
                        }
                        
                        self.mysql_manager.insert_data('relations', relation_data)
            
            self.logger.info(f"图谱信息存储到MySQL成功，文档ID: {document_id}")
            
        except Exception as e:
            self.logger.error(f"存储图谱信息到MySQL失败: {str(e)}")
    
    def query_related_content(self, query_text: str, document_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        基于图谱查询相关内容，确保返回完整的标题+内容
        
        Args:
            query_text: 查询文本
            document_id: 可选的文档ID过滤
            
        Returns:
            List[Dict[str, Any]]: 相关内容列表，每个项目包含完整的标题+内容
        """
        try:
            # 构建图谱查询
            cypher_query = """
            MATCH (d:Document)
            """
            
            parameters = {}
            
            if document_id:
                cypher_query += " WHERE d.document_id = $document_id"
                parameters['document_id'] = document_id
            
            cypher_query += """
            MATCH (d)-[:HAS_CONTENT*1..3]-(t:Title)-[:HAS_CONTENT]-(c:Content)
            WHERE t.text CONTAINS $query_text OR c.text CONTAINS $query_text
            RETURN DISTINCT t.text as title, collect(c.text) as contents, 
                   t.page_number as page_number, t.title_level as title_level
            ORDER BY t.page_number, t.title_level
            """
            
            parameters['query_text'] = query_text
            
            results = self.neo4j_manager.execute_query(cypher_query, parameters)
            
            # 格式化结果，确保每个结果都包含完整的标题+内容
            formatted_results = []
            for result in results:
                complete_content = {
                    'title': result.get('title', ''),
                    'contents': result.get('contents', []),
                    'page_number': result.get('page_number', 1),
                    'title_level': result.get('title_level', 1),
                    'complete_text': f"标题: {result.get('title', '')}\n内容: {chr(10).join(result.get('contents', []))}"
                }
                formatted_results.append(complete_content)
            
            self.logger.info(f"图谱查询完成，查询: {query_text}, 结果数量: {len(formatted_results)}")
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"图谱查询失败: {str(e)}")
            return []
    
    def get_document_graph_stats(self, document_id: int) -> Dict[str, Any]:
        """
        获取文档的图谱统计信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 图谱统计信息
        """
        try:
            # 查询Neo4j中的节点和关系统计
            stats_query = """
            MATCH (n)
            WHERE n.document_id = $document_id
            WITH labels(n) as node_types, count(n) as node_count
            RETURN node_types[0] as node_type, node_count
            """
            
            node_stats = self.neo4j_manager.execute_query(stats_query, {'document_id': document_id})
            
            # 查询关系统计
            rel_stats_query = """
            MATCH (n)-[r]-(m)
            WHERE n.document_id = $document_id AND m.document_id = $document_id
            RETURN type(r) as relationship_type, count(r) as relationship_count
            """
            
            rel_stats = self.neo4j_manager.execute_query(rel_stats_query, {'document_id': document_id})
            
            # 查询MySQL中的实体和关系统计
            entity_count_query = "SELECT COUNT(*) as count FROM entities WHERE JSON_EXTRACT(properties, '$.document_id') = :doc_id"
            entity_result = self.mysql_manager.execute_query(entity_count_query, {'doc_id': document_id})
            
            relation_count_query = "SELECT COUNT(*) as count FROM relations WHERE source_document_id = :doc_id"
            relation_result = self.mysql_manager.execute_query(relation_count_query, {'doc_id': document_id})
            
            stats = {
                'document_id': document_id,
                'neo4j_nodes': {item['node_type']: item['node_count'] for item in node_stats},
                'neo4j_relationships': {item['relationship_type']: item['relationship_count'] for item in rel_stats},
                'mysql_entities': entity_result[0]['count'] if entity_result else 0,
                'mysql_relations': relation_result[0]['count'] if relation_result else 0
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取文档图谱统计信息失败: {str(e)}")
            return {}
    
    def delete_document_graph(self, document_id: int) -> bool:
        """
        删除文档的图谱数据
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            # 删除Neo4j中的所有相关节点和关系
            delete_query = """
            MATCH (n)
            WHERE n.document_id = $document_id
            DETACH DELETE n
            """
            
            self.neo4j_manager.execute_query(delete_query, {'document_id': document_id})
            
            # 删除MySQL中的关系
            self.mysql_manager.delete_data(
                'relations',
                'source_document_id = :doc_id',
                {'doc_id': document_id}
            )
            
            # 删除MySQL中的实体
            self.mysql_manager.execute_query(
                "DELETE FROM entities WHERE JSON_EXTRACT(properties, '$.document_id') = :doc_id",
                {'doc_id': document_id}
            )
            
            self.logger.info(f"文档图谱数据删除成功，文档ID: {document_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除文档图谱数据失败: {str(e)}")
            return False