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
    
    def process_pdf_json_to_graph(self, json_data: Dict[str, Any], document_id: int) -> Dict[str, Any]:
        """
        将PDF提取的JSON数据处理为知识图谱
        
        Args:
            json_data: JSON数据（包含sections）
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            self.logger.info(f"开始知识图谱构建，文档ID: {document_id}")
            
            # 1. 解析sections和blocks
            sections = json_data.get('sections', [])
            if not sections:
                return {
                    'success': False,
                    'message': '未找到可处理的sections',
                    'entities_count': 0,
                    'relations_count': 0
                }
            
            # 2. 对每个block进行实体识别和指标提取
            all_mentions = []
            for section in sections:
                section_mentions = self._process_section_blocks(section, document_id)
                all_mentions.extend(section_mentions)
            
            if not all_mentions:
                return {
                    'success': False,
                    'message': '未识别到任何实体或指标',
                    'entities_count': 0,
                    'relations_count': 0
                }
            
            # 3. 规范化实体（别名/缩写表）
            normalized_mentions = self._normalize_mentions(all_mentions)
            
            # 4. 构建图谱节点和关系
            graph_result = self._build_knowledge_graph(normalized_mentions, sections, document_id)
            
            if graph_result['success']:
                self.logger.info(f"知识图谱构建完成，文档ID: {document_id}, "
                               f"实体数: {graph_result.get('entities_count', 0)}, "
                               f"关系数: {graph_result.get('relations_count', 0)}")
                
                return {
                    'success': True,
                    'message': '知识图谱构建成功',
                    'entities_count': graph_result.get('entities_count', 0),
                    'relations_count': graph_result.get('relations_count', 0),
                    'document_id': document_id
                }
            else:
                return graph_result
            
        except Exception as e:
            self.logger.error(f"知识图谱构建失败: {str(e)}")
            return {
                'success': False,
                'message': f'知识图谱构建失败: {str(e)}',
                'entities_count': 0,
                'relations_count': 0
            }
    
    def _process_section_blocks(self, section: Dict[str, Any], document_id: int) -> List[Dict[str, Any]]:
        """
        处理section中的blocks，进行实体识别和指标提取
        
        Args:
            section: section数据
            document_id: 文档ID
            
        Returns:
            List[Dict[str, Any]]: mentions列表
        """
        try:
            section_id = section.get('section_id', '')
            blocks = section.get('blocks', [])
            mentions = []
            
            for block in blocks:
                elem_id = block.get('elem_id', '')
                block_type = block.get('type', '').lower()
                page = block.get('page', 1)
                bbox = block.get('bbox', {})
                
                # 根据block类型提取文本内容
                block_text = self._extract_block_text_for_ner(block, block_type)
                
                if not block_text.strip():
                    continue
                
                # 实体识别
                entities = self._extract_entities(block_text, elem_id, section_id, page, bbox)
                mentions.extend(entities)
                
                # 指标/数值识别
                metrics = self._extract_metrics(block_text, elem_id, section_id, page, bbox)
                mentions.extend(metrics)
            
            return mentions
            
        except Exception as e:
            self.logger.error(f"处理section blocks失败: {str(e)}")
            return []
    
    def _extract_block_text_for_ner(self, block: Dict[str, Any], block_type: str) -> str:
        """
        根据block类型提取用于NER的文本内容
        
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
    
    def _extract_entities(self, text: str, elem_id: str, section_id: str, page: int, bbox: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从文本中提取实体（使用规则+词典方法）
        
        Args:
            text: 文本内容
            elem_id: 元素ID
            section_id: section ID
            page: 页码
            bbox: 边界框
            
        Returns:
            List[Dict[str, Any]]: 实体mentions列表
        """
        try:
            mentions = []
            
            # 定义实体词典（规则+词典方法）
            # 注意：中文模式不使用\b边界，英文模式保留\b边界
            entity_patterns = {
                'CellLine': [
                    r'CHO-K1', r'CHO\s*K1', r'CHO细胞', r'CHO',
                    r'\bHEK293\b', r'\bHEK\s*293\b', r'\bVero\b', r'\bMDCK\b'
                ],
                'Protein': [
                    r'\bHCP\b', r'宿主蛋白', r'宿主细胞蛋白', r'\bHost\s*Cell\s*Protein\b',
                    r'蛋白质', r'蛋白', r'\bprotein\b'
                ],
                'Analyte': [
                    r'\bHCP\b', r'分析物', r'待测物', r'\banalyte\b'
                ],
                'Reagent': [
                    r'抗体', r'\bantibody\b', r'\bAb\b', r'\bmAb\b', r'单抗', r'单克隆抗体',
                    r'试剂', r'\breagent\b', r'缓冲液', r'\bbuffer\b'
                ],
                'Product': [
                    r'试剂盒', r'\bkit\b', r'\bassay\b', r'检测试剂盒', r'检测kit',
                    r'\bELISA\b', r'\bWestern\b', r'\b2D\s*Gel\b'
                ]
            }
            
            # 对每种实体类型进行模式匹配
            for entity_type, patterns in entity_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        span_text = match.group()
                        start_pos = match.start()
                        end_pos = match.end()
                        
                        mention = {
                            'elem_id': elem_id,
                            'section_id': section_id,
                            'span_text': span_text,
                            'page': page,
                            'bbox': bbox,
                            'entity_type': entity_type,
                            'start_pos': start_pos,
                            'end_pos': end_pos,
                            'mention_type': 'entity',
                            'confidence': 0.8  # 规则匹配的置信度
                        }
                        mentions.append(mention)
            
            return mentions
            
        except Exception as e:
            self.logger.error(f"实体提取失败: {str(e)}")
            return []
    
    def _extract_metrics(self, text: str, elem_id: str, section_id: str, page: int, bbox: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从文本中提取指标/数值（使用正则表达式）
        
        Args:
            text: 文本内容
            elem_id: 元素ID
            section_id: section ID
            page: 页码
            bbox: 边界框
            
        Returns:
            List[Dict[str, Any]]: 指标mentions列表
        """
        try:
            mentions = []
            
            # 定义指标/数值的正则模式
            metric_patterns = {
                'Coverage': [
                    r'覆盖率\s*[≥≤><!＞\d\.\-\s%]*\d+(?:\.\d+)?%',
                    r'coverage\s*[≥≤><!＞\d\.\-\s%]*\d+(?:\.\d+)?%',
                    r'\d+(?:\.\d+)?%\s*覆盖率',
                    r'\d+(?:\.\d+)?%\s*coverage'
                ],
                'LinearRange': [
                    r'线性范围\s*[:：]\s*\d+(?:\.\d+)?\s*[–\-~]\s*\d+(?:\.\d+)?\s*(?:ng/mL|μg/mL|mg/mL|ppm)',
                    r'linear\s*range\s*[:：]\s*\d+(?:\.\d+)?\s*[–\-~]\s*\d+(?:\.\d+)?\s*(?:ng/mL|μg/mL|mg/mL|ppm)',
                    r'\d+(?:\.\d+)?\s*[–\-~]\s*\d+(?:\.\d+)?\s*(?:ng/mL|μg/mL|mg/mL|ppm)',
                    r'\d+(?:\.\d+)?\s*to\s*\d+(?:\.\d+)?\s*(?:ng/mL|μg/mL|mg/mL|ppm)'
                ],
                'RSquared': [
                    r'R[²2]\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?',
                    r'r[²2]\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?',
                    r'R\s*squared\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?',
                    r'相关系数\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?'
                ],
                'Sensitivity': [
                    r'灵敏度\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?\s*(?:ng/mL|μg/mL|mg/mL|ppm)?',
                    r'sensitivity\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?\s*(?:ng/mL|μg/mL|mg/mL|ppm)?',
                    r'检测限\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?\s*(?:ng/mL|μg/mL|mg/mL|ppm)?'
                ],
                'Precision': [
                    r'精密度\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?%',
                    r'precision\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?%',
                    r'CV\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?%',
                    r'变异系数\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?%'
                ],
                'Recovery': [
                    r'回收率\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?%',
                    r'recovery\s*[≥≤><!＞=]\s*\d+(?:\.\d+)?%',
                    r'\d+(?:\.\d+)?%\s*回收率',
                    r'\d+(?:\.\d+)?%\s*recovery'
                ],
                'Concentration': [
                    r'\d+(?:\.\d+)?\s*(?:ng/mL|μg/mL|mg/mL|ppm|nM|μM|mM)',
                    r'\d+(?:\.\d+)?\s*(?:纳克|微克|毫克)/毫升'
                ]
            }
            
            # 对每种指标类型进行模式匹配
            for metric_type, patterns in metric_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        span_text = match.group()
                        start_pos = match.start()
                        end_pos = match.end()
                        
                        # 解析数值和单位
                        parsed_value = self._parse_metric_value(span_text, metric_type)
                        
                        mention = {
                            'elem_id': elem_id,
                            'section_id': section_id,
                            'span_text': span_text,
                            'page': page,
                            'bbox': bbox,
                            'entity_type': 'Metric',
                            'metric_type': metric_type,
                            'parsed_value': parsed_value,
                            'start_pos': start_pos,
                            'end_pos': end_pos,
                            'mention_type': 'metric',
                            'confidence': 0.9  # 正则匹配的置信度较高
                        }
                        mentions.append(mention)
            
            return mentions
            
        except Exception as e:
            self.logger.error(f"指标提取失败: {str(e)}")
            return []
    
    def _parse_metric_value(self, span_text: str, metric_type: str) -> Dict[str, Any]:
        """
        解析指标数值和单位
        
        Args:
            span_text: 匹配的文本
            metric_type: 指标类型
            
        Returns:
            Dict[str, Any]: 解析结果
        """
        try:
            result = {'raw_text': span_text}
            
            # 提取数值
            number_pattern = r'\d+(?:\.\d+)?'
            numbers = re.findall(number_pattern, span_text)
            
            # 提取单位
            unit_pattern = r'(?:ng/mL|μg/mL|mg/mL|ppm|nM|μM|mM|%)'
            units = re.findall(unit_pattern, span_text, re.IGNORECASE)
            
            # 提取操作符
            operator_pattern = r'[≥≤><!＞=]+'
            operators = re.findall(operator_pattern, span_text)
            
            if numbers:
                result['numbers'] = [float(num) for num in numbers]
            if units:
                result['units'] = units
            if operators:
                result['operators'] = operators
            
            # 根据指标类型进行特殊处理
            if metric_type == 'LinearRange' and len(numbers) >= 2:
                result['range_min'] = float(numbers[0])
                result['range_max'] = float(numbers[1])
            elif metric_type in ['Coverage', 'Precision', 'Recovery'] and numbers:
                result['percentage'] = float(numbers[0])
            elif metric_type == 'RSquared' and numbers:
                result['r_squared'] = float(numbers[0])
            elif metric_type in ['Sensitivity', 'Concentration'] and numbers:
                result['value'] = float(numbers[0])
                if units:
                    result['unit'] = units[0]
            
            return result
            
        except Exception as e:
            self.logger.warning(f"解析指标数值失败: {str(e)}")
            return {'raw_text': span_text}
    
    def _normalize_mentions(self, mentions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        规范化实体mentions（别名/缩写表）
        
        Args:
            mentions: 原始mentions列表
            
        Returns:
            List[Dict[str, Any]]: 规范化后的mentions列表
        """
        try:
            # 定义规范化词典（别名/缩写表）
            normalization_dict = {
                'CellLine': {
                    'CHO': 'CHO-K1',
                    'CHO K1': 'CHO-K1',
                    'CHO细胞': 'CHO-K1',
                    'HEK 293': 'HEK293',
                    'HEK-293': 'HEK293'
                },
                'Protein': {
                    'HCP': '宿主细胞蛋白',
                    '宿主蛋白': '宿主细胞蛋白',
                    'Host Cell Protein': '宿主细胞蛋白',
                    '蛋白': '蛋白质'
                },
                'Analyte': {
                    'HCP': '宿主细胞蛋白',
                    '待测物': '分析物'
                },
                'Reagent': {
                    'mAb': '单克隆抗体',
                    'Ab': '抗体',
                    'antibody': '抗体'
                },
                'Product': {
                    'kit': '试剂盒',
                    'assay': '检测试剂盒',
                    '检测kit': '检测试剂盒'
                }
            }
            
            normalized_mentions = []
            entity_uid_counter = {}
            
            for mention in mentions:
                entity_type = mention.get('entity_type', '')
                span_text = mention.get('span_text', '')
                
                # 规范化实体名称
                normalized_name = span_text
                if entity_type in normalization_dict:
                    normalized_name = normalization_dict[entity_type].get(span_text, span_text)
                
                # 生成唯一UID
                uid_key = f"{entity_type}_{normalized_name}"
                if uid_key not in entity_uid_counter:
                    entity_uid_counter[uid_key] = 1
                else:
                    entity_uid_counter[uid_key] += 1
                
                entity_uid = f"{entity_type}_{normalized_name}_{entity_uid_counter[uid_key]}"
                
                # 更新mention信息
                normalized_mention = mention.copy()
                normalized_mention['normalized_name'] = normalized_name
                normalized_mention['entity_uid'] = entity_uid
                normalized_mention['original_span'] = span_text
                
                normalized_mentions.append(normalized_mention)
            
            self.logger.info(f"实体规范化完成，处理mentions: {len(normalized_mentions)}")
            return normalized_mentions
            
        except Exception as e:
            self.logger.error(f"实体规范化失败: {str(e)}")
            return mentions
    
    def _build_knowledge_graph(self, mentions: List[Dict[str, Any]], sections: List[Dict[str, Any]], document_id: int) -> Dict[str, Any]:
        """
        构建知识图谱节点和关系
        
        Args:
            mentions: 规范化后的mentions列表
            sections: sections数据
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 构建结果
        """
        try:
            entities_created = 0
            relations_created = 0
            
            # 1. 创建Section节点
            for section in sections:
                section_result = self._create_section_node(section, document_id)
                if section_result:
                    entities_created += 1
            
            # 2. 创建Block节点
            for section in sections:
                blocks = section.get('blocks', [])
                for block in blocks:
                    block_result = self._create_block_node(block, section.get('section_id', ''), document_id)
                    if block_result:
                        entities_created += 1
            
            # 3. 创建Entity节点和Claim节点
            unique_entities = {}
            claims = []
            
            for mention in mentions:
                entity_uid = mention.get('entity_uid', '')
                if entity_uid not in unique_entities:
                    entity_result = self._create_entity_node(mention, document_id)
                    if entity_result:
                        unique_entities[entity_uid] = mention
                        entities_created += 1
                
                # 如果是指标类型，创建Claim节点
                if mention.get('mention_type') == 'metric':
                    claim_result = self._create_claim_node(mention, document_id)
                    if claim_result:
                        claims.append(mention)
                        entities_created += 1
            
            # 4. 创建关系
            # 4.1 创建MENTIONS关系
            for mention in mentions:
                mention_relation = self._create_mentions_relation(mention, document_id)
                if mention_relation:
                    relations_created += 1
            
            # 4.2 创建HAS_ENTITY关系
            for section in sections:
                section_id = section.get('section_id', '')
                section_mentions = [m for m in mentions if m.get('section_id') == section_id]
                
                for mention in section_mentions:
                    has_entity_relation = self._create_has_entity_relation(section_id, mention, document_id)
                    if has_entity_relation:
                        relations_created += 1
            
            # 4.3 创建语义关系
            semantic_relations = self._create_semantic_relations(mentions, document_id)
            relations_created += semantic_relations
            
            self.logger.info(f"知识图谱构建完成，实体: {entities_created}, 关系: {relations_created}")
            
            return {
                'success': True,
                'entities_count': entities_created,
                'relations_count': relations_created,
                'unique_entities': len(unique_entities),
                'claims_count': len(claims)
            }
            
        except Exception as e:
            self.logger.error(f"知识图谱构建失败: {str(e)}")
            return {
                'success': False,
                'message': f'知识图谱构建失败: {str(e)}',
                'entities_count': 0,
                'relations_count': 0
            }


    def _create_section_node(self, section, document_id):
        """创建Section节点 - 仅使用Neo4j存储"""
        try:
            section_id = section.get('section_id', '')
            title = section.get('title', '')
            
            # 仅使用Neo4j存储节点数据
            try:
                neo4j_properties = {
                    'section_id': section_id,
                    'title': title,
                    'document_id': document_id,
                    'node_type': 'Section',
                    'created_at': datetime.now().isoformat()
                }
                neo4j_node_id = self.neo4j_manager.create_node('Section', neo4j_properties)
                neo4j_success = neo4j_node_id is not None
                self.logger.debug(f"Neo4j Section节点创建: {neo4j_success}, ID: {neo4j_node_id}")
                return neo4j_success
            except Exception as e:
                self.logger.warning(f"Neo4j Section节点创建失败: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"创建Section节点失败: {e}")
            return False

    def _create_block_node(self, block, section_id, document_id):
        """创建Block节点 - 仅使用Neo4j存储"""
        try:
            elem_id = block.get('elem_id', '')
            block_type = block.get('type', '')
            
            # 仅使用Neo4j存储节点数据
            try:
                neo4j_properties = {
                    'elem_id': elem_id,
                    'section_id': section_id,
                    'block_type': block_type,
                    'document_id': document_id,
                    'node_type': 'Block',
                    'created_at': datetime.now().isoformat()
                }
                neo4j_node_id = self.neo4j_manager.create_node('Block', neo4j_properties)
                neo4j_success = neo4j_node_id is not None
                self.logger.debug(f"Neo4j Block节点创建: {neo4j_success}, ID: {neo4j_node_id}")
                return neo4j_success
            except Exception as e:
                self.logger.warning(f"Neo4j Block节点创建失败: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"创建Block节点失败: {e}")
            return False

    def _create_entity_node(self, mention, document_id):
        """创建Entity节点 - 仅使用Neo4j存储"""
        try:
            entity_uid = mention.get('entity_uid', '')
            name = mention.get('normalized_name', '')
            entity_type = mention.get('entity_type', '')
            span_text = mention.get('span_text', '')
            
            # 仅使用Neo4j存储节点数据
            try:
                # 使用entity_type作为Neo4j标签，如果为空则使用Entity
                neo4j_label = entity_type if entity_type else 'Entity'
                neo4j_properties = {
                    'entity_uid': entity_uid,
                    'name': name,
                    'entity_type': entity_type,
                    'span_text': span_text,
                    'document_id': document_id,
                    'node_type': 'Entity',
                    'created_at': datetime.now().isoformat()
                }
                neo4j_node_id = self.neo4j_manager.create_node(neo4j_label, neo4j_properties)
                neo4j_success = neo4j_node_id is not None
                self.logger.debug(f"Neo4j Entity节点创建: {neo4j_success}, 标签: {neo4j_label}, ID: {neo4j_node_id}")
                return neo4j_success
            except Exception as e:
                self.logger.warning(f"Neo4j Entity节点创建失败: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"创建Entity节点失败: {e}")
            return False

    def _create_claim_node(self, mention, document_id):
        """创建Claim节点 - 仅使用Neo4j存储"""
        try:
            if mention.get('mention_type') != 'metric':
                return False
                
            claim_id = f"claim_{document_id}_{hash(mention.get('span_text', '')) % 10000}"
            metric_type = mention.get('metric_type', '')
            span_text = mention.get('span_text', '')
            
            # 仅使用Neo4j存储节点数据
            try:
                neo4j_properties = {
                    'claim_id': claim_id,
                    'metric_type': metric_type,
                    'span_text': span_text,
                    'document_id': document_id,
                    'node_type': 'Claim',
                    'created_at': datetime.now().isoformat()
                }
                neo4j_node_id = self.neo4j_manager.create_node('Claim', neo4j_properties)
                neo4j_success = neo4j_node_id is not None
                self.logger.debug(f"Neo4j Claim节点创建: {neo4j_success}, ID: {neo4j_node_id}")
                return neo4j_success
            except Exception as e:
                self.logger.warning(f"Neo4j Claim节点创建失败: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"创建Claim节点失败: {e}")
            return False

    def _create_mentions_relation(self, mention, document_id):
        """创建MENTIONS关系 - 仅使用Neo4j存储"""
        try:
            source_id = mention.get('elem_id', '')
            target_id = mention.get('entity_uid', '')
            
            # 仅使用Neo4j存储关系数据
            try:
                # 查找源节点（Block）
                source_nodes = self.neo4j_manager.find_nodes('Block', {'elem_id': source_id, 'document_id': document_id})
                # 查找目标节点（Entity）
                entity_type = mention.get('entity_type', '')
                target_label = entity_type if entity_type else 'Entity'
                target_nodes = self.neo4j_manager.find_nodes(target_label, {'entity_uid': target_id, 'document_id': document_id})
                
                if source_nodes and target_nodes:
                    source_node_id = source_nodes[0]['node_id']
                    target_node_id = target_nodes[0]['node_id']
                    
                    relation_properties = {
                        'document_id': document_id,
                        'source_id': source_id,
                        'target_id': target_id,
                        'relation_type': 'MENTIONS',
                        'created_at': datetime.now().isoformat()
                    }
                    
                    neo4j_success = self.neo4j_manager.create_relationship(
                        source_node_id, target_node_id, 'MENTIONS', relation_properties
                    )
                    self.logger.debug(f"Neo4j MENTIONS关系创建: {neo4j_success}")
                    return neo4j_success
                else:
                    self.logger.warning(f"Neo4j MENTIONS关系创建失败: 找不到源节点或目标节点")
                    return False
            except Exception as e:
                self.logger.warning(f"Neo4j MENTIONS关系创建失败: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"创建MENTIONS关系失败: {e}")
            return False

    def _create_has_entity_relation(self, section_id, mention, document_id):
        """创建HAS_ENTITY关系 - 仅使用Neo4j存储"""
        try:
            target_id = mention.get('entity_uid', '')
            
            # 仅使用Neo4j存储关系数据
            try:
                # 查找源节点（Section）
                source_nodes = self.neo4j_manager.find_nodes('Section', {'section_id': section_id, 'document_id': document_id})
                # 查找目标节点（Entity）
                entity_type = mention.get('entity_type', '')
                target_label = entity_type if entity_type else 'Entity'
                target_nodes = self.neo4j_manager.find_nodes(target_label, {'entity_uid': target_id, 'document_id': document_id})
                
                if source_nodes and target_nodes:
                    source_node_id = source_nodes[0]['node_id']
                    target_node_id = target_nodes[0]['node_id']
                    
                    relation_properties = {
                        'document_id': document_id,
                        'source_id': section_id,
                        'target_id': target_id,
                        'relation_type': 'HAS_ENTITY',
                        'created_at': datetime.now().isoformat()
                    }
                    
                    neo4j_success = self.neo4j_manager.create_relationship(
                        source_node_id, target_node_id, 'HAS_ENTITY', relation_properties
                    )
                    self.logger.debug(f"Neo4j HAS_ENTITY关系创建: {neo4j_success}")
                    return neo4j_success
                else:
                    self.logger.warning(f"Neo4j HAS_ENTITY关系创建失败: 找不到源节点或目标节点")
                    return False
            except Exception as e:
                self.logger.warning(f"Neo4j HAS_ENTITY关系创建失败: {e}")
                return False
            
        except Exception as e:
            self.logger.error(f"创建HAS_ENTITY关系失败: {e}")
            return False

    def _create_semantic_relations(self, mentions, document_id):
        """创建语义关系 - 仅使用Neo4j存储"""
        try:
            relations_count = 0
            # 简化实现：在同一section内的Product和Analyte之间创建MEASURES关系
            sections_mentions = {}
            for mention in mentions:
                section_id = mention.get('section_id', '')
                if section_id not in sections_mentions:
                    sections_mentions[section_id] = []
                sections_mentions[section_id].append(mention)

            for section_mentions in sections_mentions.values():
                products = [m for m in section_mentions if m.get('entity_type') == 'Product']
                analytes = [m for m in section_mentions if m.get('entity_type') == 'Analyte']

                for product in products:
                    for analyte in analytes:
                        source_id = product.get('entity_uid', '')
                        target_id = analyte.get('entity_uid', '')
                        
                        # 仅使用Neo4j存储关系数据
                        try:
                            # 查找源节点（Product）
                            source_nodes = self.neo4j_manager.find_nodes('Product', {'entity_uid': source_id, 'document_id': document_id})
                            # 查找目标节点（Analyte）
                            target_nodes = self.neo4j_manager.find_nodes('Analyte', {'entity_uid': target_id, 'document_id': document_id})
                            
                            if source_nodes and target_nodes:
                                source_node_id = source_nodes[0]['node_id']
                                target_node_id = target_nodes[0]['node_id']
                                
                                relation_properties = {
                                    'document_id': document_id,
                                    'source_id': source_id,
                                    'target_id': target_id,
                                    'relation_type': 'MEASURES',
                                    'created_at': datetime.now().isoformat()
                                }
                                
                                neo4j_success = self.neo4j_manager.create_relationship(
                                    source_node_id, target_node_id, 'MEASURES', relation_properties
                                )
                                if neo4j_success:
                                    relations_count += 1
                                    self.logger.debug(f"Neo4j MEASURES关系创建: {neo4j_success}")
                                else:
                                    self.logger.warning(f"Neo4j MEASURES关系创建失败")
                            else:
                                self.logger.warning(f"Neo4j MEASURES关系创建失败: 找不到源节点或目标节点")
                        except Exception as e:
                            self.logger.warning(f"Neo4j MEASURES关系创建失败: {e}")

            return relations_count
            
        except Exception as e:
            self.logger.error(f"创建语义关系失败: {e}")
            return 0