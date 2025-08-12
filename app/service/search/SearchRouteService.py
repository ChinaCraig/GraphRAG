"""
搜索路由服务
实现Query理解与路由功能，包括：
1. 查询分类器（轻量）
2. 实体识别
3. 改写与扩展
4. 路由规则
"""

import re
import json
import logging
import yaml
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# 配置日志
logger = logging.getLogger(__name__)


class SearchRouteService:
    """搜索路由服务类"""
    
    def __init__(self):
        """初始化搜索路由服务"""
        self._load_config()
        self._init_query_patterns()
        self._init_entity_patterns()
        self._init_synonym_dict()
        
    def _load_config(self):
        """加载配置文件"""
        try:
            with open('config/model.yaml', 'r', encoding='utf-8') as f:
                self.model_config = yaml.safe_load(f)
            with open('config/prompt.yaml', 'r', encoding='utf-8') as f:
                self.prompt_config = yaml.safe_load(f)
            logger.info("配置文件加载成功")
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            self.model_config = {}
            self.prompt_config = {}
    
    def _init_query_patterns(self):
        """初始化查询模式识别器"""
        self.query_patterns = {
            # 定义类查询
            "definition": [
                r"什么是|是什么|定义|含义|概念",
                r"^(.+)的定义$",
                r"解释(.+)",
                r"(.+)指的是"
            ],
            
            # 事实类查询
            "factual": [
                r"谁|什么时候|哪里|多少|如何",
                r"(.+)的作用|功能|用途",
                r"(.+)包含|包括",
                r"(.+)属于"
            ],
            
            # 比较类查询
            "comparison": [
                r"比较|对比|区别|差异|相同|不同",
                r"(.+)和(.+)的区别",
                r"(.+)与(.+)比较",
                r"哪个更|哪种更"
            ],
            
            # 流程类查询
            "process": [
                r"步骤|流程|过程|程序|方法|如何操作",
                r"怎么(.+)|如何(.+)",
                r"(.+)的流程|步骤",
                r"操作(.+)"
            ],
            
            # 规范类查询
            "standard": [
                r"标准|规范|要求|规定|准则",
                r"(.+)标准|规范",
                r"符合(.+)",
                r"满足(.+)"
            ],
            
            # 数值类查询
            "numerical": [
                r"多少|数量|范围|参数|指标|数值",
                r"(.+)的范围|参数|指标",
                r"正常值|标准值|参考值",
                r"\d+|\%|mg|ml|g|kg"
            ],
            
            # 位置类查询
            "location": [
                r"位置|地点|在哪|位于|存放",
                r"(.+)在哪里|位置",
                r"存储(.+)|保存(.+)",
                r"放在(.+)"
            ],
            
            # FAQ类查询
            "faq": [
                r"常见问题|FAQ|疑问|问题",
                r"为什么|怎么办|如何解决",
                r"出现(.+)怎么办",
                r"(.+)失败|错误"
            ],
            
            # 表格字段查询
            "table": [
                r"表格|字段|列|行|数据表",
                r"表中|表格中|数据中",
                r"字段(.+)|列(.+)",
                r"查询(.+)表"
            ],
            
            # 图像相关查询
            "image": [
                r"图片|图像|照片|截图|图表|图形",
                r"显示(.+)|展示(.+)",
                r"看到(.+)|观察(.+)",
                r"可视化(.+)"
            ]
        }
    
    def _init_entity_patterns(self):
        """初始化实体识别模式"""
        self.entity_patterns = {
            # 产品型号
            "product_model": [
                r"[A-Z]{2,5}\d{2,6}",  # 如：ABC123, XY12345
                r"[A-Z]+\-\d+",        # 如：Kit-001
                r"v\d+\.\d+",          # 如：v1.0, v2.3
                r"型号\s*[:\s]*([A-Z0-9\-]+)"
            ],
            
            # 批号
            "batch_number": [
                r"批号\s*[:\s]*([A-Z0-9\-]+)",
                r"LOT\s*[:\s]*([A-Z0-9\-]+)",
                r"Batch\s*[:\s]*([A-Z0-9\-]+)",
                r"\d{6,8}"  # 6-8位数字批号
            ],
            
            # 生物制品实体
            "bio_entity": [
                r"HCP|宿主细胞蛋白",
                r"CHO|中国仓鼠卵巢",
                r"细胞株|cell\s*line",
                r"培养基|medium",
                r"血清|serum",
                r"抗体|antibody",
                r"蛋白质|protein"
            ],
            
            # 检测指标
            "indicator": [
                r"pH值|酸碱度",
                r"温度|°C|摄氏度",
                r"浓度|mg/ml|μg/ml",
                r"纯度|%|百分比",
                r"活性|activity",
                r"稳定性|stability"
            ],
            
            # 时间表达
            "time_expression": [
                r"\d{4}年\d{1,2}月\d{1,2}日",
                r"\d{4}-\d{1,2}-\d{1,2}",
                r"\d{1,2}小时|\d+h",
                r"\d{1,2}分钟|\d+min",
                r"昨天|今天|明天",
                r"上周|本周|下周"
            ],
            
            # 部门机构
            "department": [
                r"质量部|QC|QA",
                r"研发部|R&D",
                r"生产部|制造部",
                r"技术部|工程部",
                r"实验室|lab"
            ]
        }
    
    def _init_synonym_dict(self):
        """初始化同义词词典"""
        self.synonym_dict = {
            "HCP": ["宿主细胞蛋白", "Host Cell Protein", "host cell protein"],
            "CHO": ["中国仓鼠卵巢", "Chinese Hamster Ovary", "中国仓鼠卵巢细胞"],
            "质量控制": ["QC", "Quality Control", "品质控制"],
            "质量保证": ["QA", "Quality Assurance", "品质保证"],
            "研发": ["R&D", "Research and Development", "研究开发"],
            "培养基": ["medium", "培养液", "culture medium"],
            "细胞株": ["cell line", "细胞系", "cell strain"],
            "抗体": ["antibody", "Ab", "免疫球蛋白"],
            "蛋白质": ["protein", "蛋白", "polypeptide"],
            "浓度": ["concentration", "含量", "content"],
            "纯度": ["purity", "纯净度", "pure degree"],
            "活性": ["activity", "生物活性", "biological activity"],
            "稳定性": ["stability", "稳定度", "stable"],
            "标准": ["standard", "规范", "specification", "准则"],
            "流程": ["process", "程序", "procedure", "步骤"],
            "检测": ["test", "测试", "detection", "assay"],
            "分析": ["analysis", "analyze", "analytical"],
            "验证": ["validation", "verify", "confirmation"]
        }
    
    def process_query(self, query: str, filters: Dict = None) -> Dict:
        """
        处理查询，返回理解结果
        
        Args:
            query: 用户查询文本
            filters: 过滤条件
            
        Returns:
            Dict: 查询理解结果
        """
        try:
            logger.info(f"开始处理查询: {query}")
            
            # 1. 查询分类
            query_type = self._classify_query(query)
            
            # 2. 实体识别
            entities = self._extract_entities(query)
            
            # 3. 改写与扩展
            rewrite_result = self._rewrite_and_expand(query, query_type, entities)
            
            # 4. 路由规则
            routing_strategy = self._determine_routing(query_type, entities, rewrite_result)
            
            result = {
                "original_query": query,
                "query_type": query_type,
                "entities": entities,
                "rewrite_result": rewrite_result,
                "routing_strategy": routing_strategy,
                "filters": filters or {},
                "timestamp": datetime.now().isoformat(),
                "intent": self._extract_intent(query, query_type, entities)
            }
            
            logger.info(f"查询处理完成: {query_type}")
            return result
            
        except Exception as e:
            logger.error(f"查询处理失败: {str(e)}")
            # 返回默认结果，确保流程继续
            return {
                "original_query": query,
                "query_type": "factual",
                "entities": {"general": [query]},
                "rewrite_result": {
                    "bm25_keywords": [query],
                    "vector_query": query,
                    "graph_intent": None
                },
                "routing_strategy": {
                    "use_bm25": True,
                    "use_vector": True,
                    "use_graph": False,
                    "primary_method": "hybrid"
                },
                "filters": filters or {},
                "intent": "信息查询",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def _classify_query(self, query: str) -> str:
        """
        查询分类器，判断查询类型
        
        Args:
            query: 查询文本
            
        Returns:
            str: 查询类型
        """
        query_lower = query.lower()
        
        # 按优先级检查各种模式
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    logger.debug(f"查询类型匹配: {query_type} - 模式: {pattern}")
                    return query_type
        
        # 默认为事实类查询
        return "factual"
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        实体识别，从查询中识别各类实体
        
        Args:
            query: 查询文本
            
        Returns:
            Dict: 识别出的实体
        """
        entities = {}
        
        for entity_type, patterns in self.entity_patterns.items():
            entities[entity_type] = []
            
            for pattern in patterns:
                matches = re.findall(pattern, query, re.IGNORECASE)
                if matches:
                    # 处理匹配结果
                    for match in matches:
                        if isinstance(match, tuple):
                            entities[entity_type].extend([m for m in match if m])
                        else:
                            entities[entity_type].append(match)
        
        # 去重并过滤空值
        for entity_type in entities:
            entities[entity_type] = list(set([e for e in entities[entity_type] if e]))
        
        # 如果没有识别到专门的实体，将整个查询作为通用实体
        if not any(entities.values()):
            entities["general"] = [query]
        
        return entities
    
    def _rewrite_and_expand(self, query: str, query_type: str, entities: Dict) -> Dict:
        """
        改写与扩展查询
        
        Args:
            query: 原始查询
            query_type: 查询类型
            entities: 识别出的实体
            
        Returns:
            Dict: 改写扩展结果
        """
        # 生成BM25友好的关键字
        bm25_keywords = self._generate_bm25_keywords(query, entities)
        
        # 生成向量检索的语义化query
        vector_query = self._generate_vector_query(query, query_type)
        
        # 生成图谱查询意图
        graph_intent = self._generate_graph_intent(query, query_type, entities)
        
        return {
            "bm25_keywords": bm25_keywords,
            "vector_query": vector_query,
            "graph_intent": graph_intent,
            "expanded_synonyms": self._expand_synonyms(bm25_keywords),
            "english_aliases": self._get_english_aliases(bm25_keywords)
        }
    
    def _generate_bm25_keywords(self, query: str, entities: Dict) -> List[str]:
        """生成BM25友好的关键字"""
        keywords = []
        
        # 提取实体作为关键词
        for entity_type, entity_list in entities.items():
            keywords.extend(entity_list)
        
        # 基于规则提取关键词
        # 移除停用词
        stopwords = {"的", "是", "在", "有", "和", "与", "或", "但", "而", "了", "着", "过",
                    "能", "会", "要", "请", "帮", "我", "查询", "查找", "搜索", "一下", "相关", "内容"}
        
        words = re.findall(r'\w+', query)
        keywords.extend([w for w in words if w not in stopwords and len(w) > 1])
        
        # 去重并保持顺序
        seen = set()
        result = []
        for keyword in keywords:
            if keyword not in seen:
                seen.add(keyword)
                result.append(keyword)
        
        return result[:10]  # 限制关键词数量
    
    def _generate_vector_query(self, query: str, query_type: str) -> str:
        """生成向量检索的语义化查询"""
        # 根据查询类型优化语义表达
        if query_type == "definition":
            return f"{query} 定义 概念 含义"
        elif query_type == "process":
            return f"{query} 流程 步骤 方法 操作"
        elif query_type == "comparison":
            return f"{query} 区别 比较 差异 对比"
        elif query_type == "numerical":
            return f"{query} 数值 参数 范围 指标"
        else:
            return query
    
    def _generate_graph_intent(self, query: str, query_type: str, entities: Dict) -> Optional[Dict]:
        """生成图谱查询意图"""
        if not entities or query_type not in ["factual", "definition", "comparison"]:
            return None
        
        # 识别关系查询意图
        relation_patterns = {
            "组成": ["组成", "包含", "包括", "含有", "构成"],
            "适用": ["适用", "应用", "使用", "用于", "针对"],
            "依赖": ["依赖", "需要", "要求", "基于", "依赖于"],
            "引用": ["引用", "参考", "依据", "根据", "标准"],
            "流程": ["流程", "步骤", "过程", "程序", "方法"],
            "属性": ["属性", "特征", "性质", "参数", "指标"]
        }
        
        for relation, keywords in relation_patterns.items():
            if any(keyword in query for keyword in keywords):
                return {
                    "relation_type": relation,
                    "entities": entities,
                    "cypher_template": self._get_cypher_template(relation),
                    "confidence": 0.8
                }
        
        return None
    
    def _get_cypher_template(self, relation_type: str) -> str:
        """获取Cypher查询模板"""
        templates = {
            "组成": "(a)-[:HAS_PART|CONTAINS]->(b)",
            "适用": "(a)-[:APPLICABLE_TO|SUITABLE_FOR]->(b)", 
            "依赖": "(a)-[:DEPENDS_ON|REQUIRES]->(b)",
            "引用": "(a)-[:CITED_BY|REFER_TO]->(b)",
            "流程": "(a)-[:NEXT|FOLLOWS]->(b)",
            "属性": "(a)-[:HAS_PROPERTY|HAS_ATTRIBUTE]->(b)"
        }
        return templates.get(relation_type, "(a)-[:RELATED_TO]->(b)")
    
    def _expand_synonyms(self, keywords: List[str]) -> List[str]:
        """扩展同义词"""
        expanded = set(keywords)
        
        for keyword in keywords:
            if keyword in self.synonym_dict:
                expanded.update(self.synonym_dict[keyword])
        
        return list(expanded)
    
    def _get_english_aliases(self, keywords: List[str]) -> List[str]:
        """获取英文别名"""
        aliases = []
        
        for keyword in keywords:
            if keyword in self.synonym_dict:
                # 提取英文别名
                for synonym in self.synonym_dict[keyword]:
                    if re.match(r'^[A-Za-z\s&]+$', synonym):
                        aliases.append(synonym)
        
        return aliases
    
    def _determine_routing(self, query_type: str, entities: Dict, rewrite_result: Dict) -> Dict:
        """
        确定路由策略
        
        Args:
            query_type: 查询类型
            entities: 实体
            rewrite_result: 改写结果
            
        Returns:
            Dict: 路由策略
        """
        strategy = {
            "use_bm25": True,
            "use_vector": True, 
            "use_graph": False,
            "primary_method": "hybrid",
            "bm25_weight": 0.3,
            "vector_weight": 0.4,
            "graph_weight": 0.3,
            "filters": {}
        }
        
        # 根据查询类型调整策略
        if query_type in ["definition", "standard"]:
            # 定义和规范类优先BM25+Vector
            strategy["bm25_weight"] = 0.5
            strategy["vector_weight"] = 0.5
            strategy["graph_weight"] = 0.0
            
        elif query_type == "comparison":
            # 比较类优先图谱
            if rewrite_result.get("graph_intent"):
                strategy["use_graph"] = True
                strategy["primary_method"] = "graph_enhanced"
                strategy["graph_weight"] = 0.4
                
        elif query_type == "table":
            # 表格类优先BM25，增加类型过滤
            strategy["primary_method"] = "bm25"
            strategy["bm25_weight"] = 0.6
            strategy["vector_weight"] = 0.4
            strategy["filters"]["type"] = "table"
            
        elif query_type == "numerical":
            # 数值类增加表格权重
            strategy["filters"]["boost_table"] = 2.0
            
        elif query_type == "image":
            # 图像相关
            strategy["filters"]["has_image"] = True
            
        # 检查是否有强结构意图
        if rewrite_result.get("graph_intent"):
            strategy["use_graph"] = True
            if any(keyword in rewrite_result["graph_intent"].get("relation_type", "") 
                   for keyword in ["组成", "适用", "依赖"]):
                strategy["primary_method"] = "graph_first"
                strategy["graph_weight"] = 0.5
        
        return strategy
    
    def _extract_intent(self, query: str, query_type: str, entities: Dict) -> str:
        """提取用户意图描述"""
        intent_templates = {
            "definition": "查询定义和概念",
            "factual": "查询事实信息",
            "comparison": "对比分析",
            "process": "了解流程步骤",
            "standard": "查询标准规范",
            "numerical": "查询数值参数",
            "location": "查询位置信息",
            "faq": "常见问题咨询",
            "table": "表格数据查询",
            "image": "图像相关查询"
        }
        
        base_intent = intent_templates.get(query_type, "信息查询")
        
        # 如果有特定实体，添加实体信息
        main_entities = []
        for entity_type, entity_list in entities.items():
            if entity_list and entity_type != "general":
                main_entities.extend(entity_list[:2])  # 最多取2个主要实体
        
        if main_entities:
            return f"{base_intent} - 关于{', '.join(main_entities)}"
        else:
            return base_intent
    
    def get_search_suggestions(self, partial_query: str, limit: int = 10) -> List[Dict]:
        """
        获取搜索建议
        
        Args:
            partial_query: 部分查询文本
            limit: 返回建议数量
            
        Returns:
            List[Dict]: 建议列表
        """
        suggestions = []
        
        # 基于同义词字典生成建议
        for key, synonyms in self.synonym_dict.items():
            if partial_query.lower() in key.lower():
                suggestions.append({
                    "text": key,
                    "type": "entity",
                    "score": 0.9
                })
            
            for synonym in synonyms:
                if partial_query.lower() in synonym.lower():
                    suggestions.append({
                        "text": synonym,
                        "type": "entity", 
                        "score": 0.8
                    })
        
        # 基于查询模式生成建议
        common_queries = [
            "HCP的检测方法",
            "CHO细胞培养流程",
            "蛋白质纯度标准",
            "质量控制流程",
            "细胞株的保存方法",
            "培养基的配制"
        ]
        
        for query in common_queries:
            if partial_query.lower() in query.lower():
                suggestions.append({
                    "text": query,
                    "type": "question",
                    "score": 0.7
                })
        
        # 去重并排序
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion["text"] not in seen:
                seen.add(suggestion["text"])
                unique_suggestions.append(suggestion)
        
        # 按分数排序并限制数量
        unique_suggestions.sort(key=lambda x: x["score"], reverse=True)
        return unique_suggestions[:limit]
    
    def get_search_history(self, user_id: str, limit: int = 20, offset: int = 0) -> Dict:
        """
        获取搜索历史（模拟实现）
        
        Args:
            user_id: 用户ID
            limit: 返回数量
            offset: 偏移量
            
        Returns:
            Dict: 历史数据
        """
        # 这里应该连接数据库获取真实历史
        # 目前返回模拟数据
        mock_history = [
            {
                "query": "HCP检测方法",
                "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                "result_count": 15,
                "query_type": "process"
            },
            {
                "query": "CHO细胞培养条件",
                "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
                "result_count": 8,
                "query_type": "factual"
            }
        ]
        
        return {
            "total": len(mock_history),
            "items": mock_history[offset:offset + limit]
        }
    
    def get_search_stats(self) -> Dict:
        """
        获取搜索统计信息（模拟实现）
        
        Returns:
            Dict: 统计信息
        """
        # 这里应该连接数据库获取真实统计
        # 目前返回模拟数据
        return {
            "total_searches": 1250,
            "today_searches": 45,
            "avg_response_time": 2.3,
            "popular_queries": [
                "HCP检测",
                "细胞培养",
                "质量控制",
                "蛋白纯化",
                "标准流程"
            ],
            "query_type_distribution": {
                "factual": 35,
                "definition": 25,
                "process": 20,
                "comparison": 10,
                "other": 10
            }
        }
