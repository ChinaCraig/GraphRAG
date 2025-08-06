"""
PDF图数据库服务
负责从PDF文档中提取实体和关系，并存储到Neo4j图数据库
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
    """PDF图数据库服务类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化PDF图数据库服务
        
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
            
            self.logger.info("PDF图数据库服务配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载PDF图数据库服务配置失败: {str(e)}")
            raise
    
    def process_pdf_to_graph(self, document_id: int) -> Dict[str, Any]:
        """
        将PDF文档处理为知识图谱
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 获取文档信息
            doc_info = self._get_document_info(document_id)
            if not doc_info:
                return {
                    'success': False,
                    'message': '文档不存在',
                    'entities_count': 0,
                    'relations_count': 0
                }
            
            # 获取文档分块
            chunks = self._get_document_chunks(document_id)
            if not chunks:
                return {
                    'success': False,
                    'message': '文档分块不存在，请先进行内容提取',
                    'entities_count': 0,
                    'relations_count': 0
                }
            
            # 提取实体和关系
            entities_data = []
            relations_data = []
            
            for chunk in chunks:
                # 从每个分块中提取实体
                chunk_entities = self._extract_entities_from_chunk(chunk)
                entities_data.extend(chunk_entities)
                
                # 从每个分块中提取关系
                chunk_relations = self._extract_relations_from_chunk(chunk, chunk_entities)
                relations_data.extend(chunk_relations)
                
                self.logger.info(f"分块 {chunk['chunk_index']} 处理完成，实体: {len(chunk_entities)}, 关系: {len(chunk_relations)}")
            
            # 去重实体
            unique_entities = self._deduplicate_entities(entities_data)
            
            # 存储实体到图数据库和MySQL
            stored_entities = self._store_entities(unique_entities, document_id)
            
            # 存储关系到图数据库和MySQL
            stored_relations = self._store_relations(relations_data, stored_entities, document_id)
            
            # 更新文档处理状态
            self.mysql_manager.update_data(
                'documents',
                {'process_status': 'graph_processed'},
                'id = :doc_id',
                {'doc_id': document_id}
            )
            
            self.logger.info(f"PDF图处理完成，文档ID: {document_id}, 实体: {len(stored_entities)}, 关系: {len(stored_relations)}")
            
            return {
                'success': True,
                'message': 'PDF图处理成功',
                'entities_count': len(stored_entities),
                'relations_count': len(stored_relations),
                'document_id': document_id
            }
            
        except Exception as e:
            self.logger.error(f"PDF图处理失败: {str(e)}")
            return {
                'success': False,
                'message': f'PDF图处理失败: {str(e)}',
                'entities_count': 0,
                'relations_count': 0
            }
    
    def _get_document_info(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        获取文档信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Optional[Dict[str, Any]]: 文档信息
        """
        try:
            query = "SELECT * FROM documents WHERE id = :doc_id"
            result = self.mysql_manager.execute_query(query, {'doc_id': document_id})
            return result[0] if result else None
            
        except Exception as e:
            self.logger.error(f"获取文档信息失败: {str(e)}")
            return None
    
    def _get_document_chunks(self, document_id: int) -> List[Dict[str, Any]]:
        """
        获取文档分块
        
        Args:
            document_id: 文档ID
            
        Returns:
            List[Dict[str, Any]]: 文档分块列表
        """
        try:
            query = """
            SELECT id, document_id, chunk_index, content
            FROM document_chunks 
            WHERE document_id = :doc_id 
            ORDER BY chunk_index
            """
            
            result = self.mysql_manager.execute_query(query, {'doc_id': document_id})
            return result
            
        except Exception as e:
            self.logger.error(f"获取文档分块失败: {str(e)}")
            return []
    
    def _call_deepseek_api(self, prompt: str, max_tokens: Optional[int] = None) -> Optional[str]:
        """
        调用DeepSeek API
        
        Args:
            prompt: 提示词
            max_tokens: 最大生成token数
            
        Returns:
            Optional[str]: API响应内容
        """
        try:
            deepseek_config = self.model_config['deepseek']
            
            headers = {
                'Authorization': f"Bearer {deepseek_config['api_key']}",
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': deepseek_config['model_name'],
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': max_tokens or deepseek_config['max_tokens'],
                'temperature': deepseek_config['temperature'],
                'top_p': deepseek_config['top_p']
            }
            
            response = requests.post(
                f"{deepseek_config['api_url']}/chat/completions",
                headers=headers,
                json=data,
                timeout=deepseek_config['timeout']
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                self.logger.error(f"DeepSeek API调用失败: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"调用DeepSeek API失败: {str(e)}")
            return None
    
    def _extract_entities_from_chunk(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从文档分块中提取实体
        
        Args:
            chunk: 文档分块
            
        Returns:
            List[Dict[str, Any]]: 提取的实体列表
        """
        try:
            content = chunk['content']
            
            # 使用DeepSeek API进行实体识别
            prompt = self.prompt_config['entity_recognition']['ner_extraction'].format(
                text_content=content
            )
            
            response = self._call_deepseek_api(prompt)
            
            if response:
                try:
                    # 解析JSON响应
                    entities_data = json.loads(response)
                    
                    entities = []
                    for entity_type, entity_list in entities_data.items():
                        if isinstance(entity_list, list):
                            for entity_name in entity_list:
                                if entity_name and entity_name.strip():
                                    entity = {
                                        'name': entity_name.strip(),
                                        'type': entity_type,
                                        'source_chunk_id': chunk['id'],
                                        'source_document_id': chunk['document_id'],
                                        'context': content[:200]  # 保存上下文
                                    }
                                    entities.append(entity)
                    
                    return entities
                    
                except json.JSONDecodeError:
                    self.logger.warning(f"无法解析实体识别结果: {response}")
                    # 使用简单的规则提取作为后备
                    return self._extract_entities_with_rules(content, chunk)
            
            # 如果API调用失败，使用规则提取
            return self._extract_entities_with_rules(content, chunk)
            
        except Exception as e:
            self.logger.error(f"从分块提取实体失败: {str(e)}")
            return []
    
    def _extract_entities_with_rules(self, content: str, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        使用规则方法提取实体（作为AI提取的后备）
        
        Args:
            content: 文本内容
            chunk: 文档分块
            
        Returns:
            List[Dict[str, Any]]: 提取的实体列表
        """
        try:
            entities = []
            
            # 简单的规则提取
            # 人名模式 (中文姓名)
            person_pattern = r'[\u4e00-\u9fff]{2,4}(?=先生|女士|教授|博士|经理|总监|主任|老师|同学)'
            persons = re.findall(person_pattern, content)
            
            for person in set(persons):
                entities.append({
                    'name': person,
                    'type': 'persons',
                    'source_chunk_id': chunk['id'],
                    'source_document_id': chunk['document_id'],
                    'context': content[:200]
                })
            
            # 组织机构模式
            org_pattern = r'[\u4e00-\u9fff]{2,10}(?=公司|集团|企业|机构|组织|部门|学院|大学|银行)'
            orgs = re.findall(org_pattern, content)
            
            for org in set(orgs):
                entities.append({
                    'name': org,
                    'type': 'organizations',
                    'source_chunk_id': chunk['id'],
                    'source_document_id': chunk['document_id'],
                    'context': content[:200]
                })
            
            # 地名模式
            location_pattern = r'[\u4e00-\u9fff]{2,8}(?=市|省|县|区|镇|村|街|路|街道)'
            locations = re.findall(location_pattern, content)
            
            for location in set(locations):
                entities.append({
                    'name': location,
                    'type': 'locations',
                    'source_chunk_id': chunk['id'],
                    'source_document_id': chunk['document_id'],
                    'context': content[:200]
                })
            
            return entities
            
        except Exception as e:
            self.logger.error(f"规则提取实体失败: {str(e)}")
            return []
    
    def _extract_relations_from_chunk(self, chunk: Dict[str, Any], entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从文档分块中提取关系
        
        Args:
            chunk: 文档分块
            entities: 已提取的实体列表
            
        Returns:
            List[Dict[str, Any]]: 提取的关系列表
        """
        try:
            if len(entities) < 2:
                return []
            
            content = chunk['content']
            entity_names = [entity['name'] for entity in entities]
            
            # 使用DeepSeek API进行关系提取
            prompt = self.prompt_config['relation_extraction']['entity_relations'].format(
                text_content=content,
                entities=json.dumps(entity_names, ensure_ascii=False)
            )
            
            response = self._call_deepseek_api(prompt)
            
            if response:
                try:
                    # 解析JSON响应
                    relations_data = json.loads(response)
                    
                    relations = []
                    for relation in relations_data.get('relations', []):
                        head = relation.get('head', '').strip()
                        tail = relation.get('tail', '').strip()
                        relation_type = relation.get('relation', '').strip()
                        confidence = relation.get('confidence', 0.5)
                        
                        if head and tail and relation_type and head != tail:
                            # 查找对应的实体
                            head_entity = next((e for e in entities if e['name'] == head), None)
                            tail_entity = next((e for e in entities if e['name'] == tail), None)
                            
                            if head_entity and tail_entity:
                                relation_data = {
                                    'head_entity': head_entity,
                                    'tail_entity': tail_entity,
                                    'relation_type': relation_type,
                                    'confidence': confidence,
                                    'source_chunk_id': chunk['id'],
                                    'source_document_id': chunk['document_id'],
                                    'context': content[:300]
                                }
                                relations.append(relation_data)
                    
                    return relations
                    
                except json.JSONDecodeError:
                    self.logger.warning(f"无法解析关系提取结果: {response}")
                    return self._extract_relations_with_rules(content, entities, chunk)
            
            # 如果API调用失败，使用规则提取
            return self._extract_relations_with_rules(content, entities, chunk)
            
        except Exception as e:
            self.logger.error(f"从分块提取关系失败: {str(e)}")
            return []
    
    def _extract_relations_with_rules(self, content: str, entities: List[Dict[str, Any]], chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        使用规则方法提取关系（作为AI提取的后备）
        
        Args:
            content: 文本内容
            entities: 实体列表
            chunk: 文档分块
            
        Returns:
            List[Dict[str, Any]]: 提取的关系列表
        """
        try:
            relations = []
            
            # 简单的共现关系提取
            entity_names = [entity['name'] for entity in entities]
            
            for i, entity1 in enumerate(entities):
                for j, entity2 in enumerate(entities):
                    if i >= j:  # 避免重复和自关联
                        continue
                    
                    name1 = entity1['name']
                    name2 = entity2['name']
                    
                    # 检查两个实体是否在同一个句子中出现
                    sentences = re.split(r'[。！？]', content)
                    
                    for sentence in sentences:
                        if name1 in sentence and name2 in sentence:
                            # 确定关系类型
                            relation_type = self._determine_relation_type(entity1, entity2, sentence)
                            
                            if relation_type:
                                relation_data = {
                                    'head_entity': entity1,
                                    'tail_entity': entity2,
                                    'relation_type': relation_type,
                                    'confidence': 0.7,  # 规则提取的置信度较低
                                    'source_chunk_id': chunk['id'],
                                    'source_document_id': chunk['document_id'],
                                    'context': sentence[:200]
                                }
                                relations.append(relation_data)
                            break
            
            return relations
            
        except Exception as e:
            self.logger.error(f"规则提取关系失败: {str(e)}")
            return []
    
    def _determine_relation_type(self, entity1: Dict[str, Any], entity2: Dict[str, Any], sentence: str) -> Optional[str]:
        """
        确定两个实体之间的关系类型
        
        Args:
            entity1: 实体1
            entity2: 实体2
            sentence: 包含两个实体的句子
            
        Returns:
            Optional[str]: 关系类型
        """
        try:
            type1 = entity1['type']
            type2 = entity2['type']
            
            # 根据实体类型和句子内容确定关系
            if type1 == 'persons' and type2 == 'organizations':
                if any(keyword in sentence for keyword in ['工作', '任职', '就职', '在']):
                    return '工作于'
                elif any(keyword in sentence for keyword in ['创建', '创立', '成立']):
                    return '创建'
            
            elif type1 == 'persons' and type2 == 'persons':
                if any(keyword in sentence for keyword in ['合作', '合伙', '共同']):
                    return '合作'
                elif any(keyword in sentence for keyword in ['认识', '朋友', '同事']):
                    return '认识'
            
            elif type1 == 'organizations' and type2 == 'locations':
                if any(keyword in sentence for keyword in ['位于', '在', '设在']):
                    return '位于'
            
            # 默认关系
            return '相关'
            
        except Exception as e:
            self.logger.error(f"确定关系类型失败: {str(e)}")
            return None
    
    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重实体
        
        Args:
            entities: 实体列表
            
        Returns:
            List[Dict[str, Any]]: 去重后的实体列表
        """
        try:
            unique_entities = {}
            
            for entity in entities:
                key = f"{entity['name']}_{entity['type']}"
                
                if key not in unique_entities:
                    unique_entities[key] = entity
                else:
                    # 合并上下文信息
                    existing = unique_entities[key]
                    if len(entity['context']) > len(existing['context']):
                        unique_entities[key] = entity
            
            return list(unique_entities.values())
            
        except Exception as e:
            self.logger.error(f"实体去重失败: {str(e)}")
            return entities
    
    def _store_entities(self, entities: List[Dict[str, Any]], document_id: int) -> Dict[str, str]:
        """
        存储实体到图数据库和MySQL
        
        Args:
            entities: 实体列表
            document_id: 文档ID
            
        Returns:
            Dict[str, str]: 实体名称到节点ID的映射
        """
        try:
            entity_mapping = {}
            
            for entity in entities:
                # 存储到Neo4j
                node_properties = {
                    'name': entity['name'],
                    'entity_type': entity['type'],
                    'source_document_id': document_id,
                    'context': entity['context'],
                    'created_time': datetime.now().isoformat()
                }
                
                node_id = self.neo4j_manager.create_node('Entity', node_properties)
                
                if node_id:
                    entity_mapping[entity['name']] = node_id
                    
                    # 存储到MySQL
                    mysql_data = {
                        'name': entity['name'],
                        'entity_type': entity['type'],
                        'description': entity['context'],
                        'properties': json.dumps({
                            'source_document_id': document_id,
                            'neo4j_node_id': node_id
                        }, ensure_ascii=False),
                        'create_time': datetime.now()
                    }
                    
                    self.mysql_manager.insert_data('entities', mysql_data)
            
            return entity_mapping
            
        except Exception as e:
            self.logger.error(f"存储实体失败: {str(e)}")
            return {}
    
    def _store_relations(self, relations: List[Dict[str, Any]], entity_mapping: Dict[str, str], document_id: int) -> List[Dict[str, Any]]:
        """
        存储关系到图数据库和MySQL
        
        Args:
            relations: 关系列表
            entity_mapping: 实体名称到节点ID的映射
            document_id: 文档ID
            
        Returns:
            List[Dict[str, Any]]: 存储的关系列表
        """
        try:
            stored_relations = []
            
            for relation in relations:
                head_name = relation['head_entity']['name']
                tail_name = relation['tail_entity']['name']
                
                head_node_id = entity_mapping.get(head_name)
                tail_node_id = entity_mapping.get(tail_name)
                
                if head_node_id and tail_node_id:
                    # 存储到Neo4j
                    rel_properties = {
                        'confidence': relation['confidence'],
                        'source_document_id': document_id,
                        'context': relation['context'],
                        'created_time': datetime.now().isoformat()
                    }
                    
                    success = self.neo4j_manager.create_relationship(
                        head_node_id,
                        tail_node_id,
                        relation['relation_type'],
                        rel_properties
                    )
                    
                    if success:
                        # 获取实体的MySQL ID
                        head_entity_query = "SELECT id FROM entities WHERE name = :name LIMIT 1"
                        tail_entity_query = "SELECT id FROM entities WHERE name = :name LIMIT 1"
                        
                        head_result = self.mysql_manager.execute_query(
                            head_entity_query, 
                            {'name': head_name}
                        )
                        tail_result = self.mysql_manager.execute_query(
                            tail_entity_query, 
                            {'name': tail_name}
                        )
                        
                        if head_result and tail_result:
                            # 存储到MySQL
                            mysql_data = {
                                'head_entity_id': head_result[0]['id'],
                                'tail_entity_id': tail_result[0]['id'],
                                'relation_type': relation['relation_type'],
                                'confidence': relation['confidence'],
                                'source_document_id': document_id,
                                'create_time': datetime.now()
                            }
                            
                            self.mysql_manager.insert_data('relations', mysql_data)
                            stored_relations.append(relation)
            
            return stored_relations
            
        except Exception as e:
            self.logger.error(f"存储关系失败: {str(e)}")
            return []
    
    def get_document_graph_stats(self, document_id: int) -> Dict[str, Any]:
        """
        获取文档的图统计信息
        
        Args:
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 图统计信息
        """
        try:
            # 获取实体数量
            entity_query = "SELECT COUNT(*) as count FROM entities WHERE JSON_EXTRACT(properties, '$.source_document_id') = :doc_id"
            entity_result = self.mysql_manager.execute_query(entity_query, {'doc_id': document_id})
            entity_count = entity_result[0]['count'] if entity_result else 0
            
            # 获取关系数量
            relation_query = "SELECT COUNT(*) as count FROM relations WHERE source_document_id = :doc_id"
            relation_result = self.mysql_manager.execute_query(relation_query, {'doc_id': document_id})
            relation_count = relation_result[0]['count'] if relation_result else 0
            
            # 获取实体类型分布
            type_query = """
            SELECT entity_type, COUNT(*) as count 
            FROM entities 
            WHERE JSON_EXTRACT(properties, '$.source_document_id') = :doc_id
            GROUP BY entity_type
            """
            type_result = self.mysql_manager.execute_query(type_query, {'doc_id': document_id})
            
            # 获取关系类型分布
            rel_type_query = """
            SELECT relation_type, COUNT(*) as count 
            FROM relations 
            WHERE source_document_id = :doc_id
            GROUP BY relation_type
            """
            rel_type_result = self.mysql_manager.execute_query(rel_type_query, {'doc_id': document_id})
            
            stats = {
                'document_id': document_id,
                'entity_count': entity_count,
                'relation_count': relation_count,
                'entity_types': type_result,
                'relation_types': rel_type_result
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取文档图统计信息失败: {str(e)}")
            return {}
    
    def delete_document_graph(self, document_id: int) -> bool:
        """
        删除文档的图数据
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            # 删除Neo4j中的节点和关系
            query = f"""
            MATCH (n:Entity)
            WHERE n.source_document_id = {document_id}
            DETACH DELETE n
            """
            
            self.neo4j_manager.execute_query(query)
            
            # 删除MySQL中的关系
            self.mysql_manager.delete_data(
                'relations',
                'source_document_id = :doc_id',
                {'doc_id': document_id}
            )
            
            # 删除MySQL中的实体
            self.mysql_manager.execute_query(
                "DELETE FROM entities WHERE JSON_EXTRACT(properties, '$.source_document_id') = :doc_id",
                {'doc_id': document_id}
            )
            
            self.logger.info(f"文档图数据删除成功，文档ID: {document_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除文档图数据失败: {str(e)}")
            return False