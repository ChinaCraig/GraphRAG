"""
搜索答案生成服务
实现上下文拼装与回答生成功能，包括：
1. 证据拼装（Context Builder）
2. 保留原格式输出
3. 生成答案（支持流式生成）
"""

import json
import logging
import re
import yaml
from typing import Dict, List, Optional, Generator, Any
from datetime import datetime
import requests
from time import sleep

# 配置日志
logger = logging.getLogger(__name__)


class SearchAnswerService:
    """搜索答案生成服务类"""
    
    def __init__(self):
        """初始化搜索答案生成服务"""
        self._load_config()
        self._init_llm_client()
        self._init_templates()
        
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
    
    def _init_llm_client(self):
        """初始化LLM客户端"""
        try:
            deepseek_config = self.model_config.get('deepseek', {})
            self.api_url = deepseek_config.get('api_url', 'https://api.deepseek.com')
            self.api_key = deepseek_config.get('api_key', '')
            self.model_name = deepseek_config.get('model_name', 'deepseek-chat')
            self.max_tokens = deepseek_config.get('max_tokens', 4096)
            self.temperature = deepseek_config.get('temperature', 0.7)
            
            if not self.api_key:
                logger.warning("DeepSeek API密钥未配置，将使用模拟回答")
                self.llm_client = None
            else:
                self.llm_client = self._create_llm_client()
                logger.info("LLM客户端初始化成功")
                
        except Exception as e:
            logger.error(f"LLM客户端初始化失败: {str(e)}")
            self.llm_client = None
    
    def _create_llm_client(self):
        """创建LLM客户端"""
        # 这里可以根据需要使用不同的LLM库
        # 目前使用简单的HTTP请求
        return {
            'api_url': self.api_url,
            'api_key': self.api_key,
            'headers': {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
        }
    
    def _init_templates(self):
        """初始化答案模板"""
        self.answer_templates = {
            "definition": """基于以下证据，我为您解释"{query}"的定义：

{conclusion}

**详细说明：**
{evidence_points}

**参考来源：**
{references}

{original_links}""",
            
            "factual": """根据检索到的信息，关于"{query}"的回答如下：

{conclusion}

**具体信息：**
{evidence_points}

**参考来源：**
{references}

{original_links}""",
            
            "comparison": """关于"{query}"的对比分析如下：

{conclusion}

**对比要点：**
{evidence_points}

**参考来源：**
{references}

{original_links}""",
            
            "process": """关于"{query}"的流程步骤如下：

{conclusion}

**详细步骤：**
{evidence_points}

**参考来源：**
{references}

{original_links}""",
            
            "numerical": """关于"{query}"的数值参数信息：

{conclusion}

**具体数值：**
{evidence_points}

**参考来源：**
{references}

{original_links}""",
            
            "default": """根据您的查询"{query}"，检索到以下相关信息：

{conclusion}

**相关要点：**
{evidence_points}

**参考来源：**
{references}

{original_links}"""
        }
    
    def generate_answer_stream(self, query: str, retrieval_result: Dict, 
                             understanding_result: Dict) -> Generator[Dict, None, None]:
        """
        流式生成答案
        严格按照要求输出增量内容和多模态事件
        
        Args:
            query: 用户查询
            retrieval_result: 检索结果
            understanding_result: 查询理解结果
            
        Yields:
            Dict: 流式答案片段或多模态事件
        """
        try:
            logger.info(f"开始流式生成答案: {query}")
            
            # 构建上下文
            context = self._build_context(retrieval_result, understanding_result)
            
            # 流式生成文本答案
            if self.llm_client:
                # 使用LLM流式生成
                for chunk in self._stream_llm_generation(query, context, understanding_result):
                    yield chunk
            else:
                # 使用模板流式生成
                for chunk in self._stream_template_generation(query, context, understanding_result):
                    yield chunk
            
            # 处理多模态内容
            for multimodal_chunk in self._stream_multimodal_content(context):
                yield multimodal_chunk
            
            # 生成最终完整答案（包含引用等）
            final_answer = self._format_final_answer(query, context, understanding_result)
            
            yield {
                "type": "final_answer",
                "content": final_answer,
                "context": context,
                "metadata": {
                    "total_sources": len(context.get("sources", [])),
                    "evidence_count": len(context.get("evidence_list", [])),
                    "generation_method": "llm" if self.llm_client else "template"
                }
            }
            
        except Exception as e:
            logger.error(f"流式生成答案失败: {str(e)}")
            yield {
                "type": "error",
                "content": f"答案生成失败: {str(e)}"
            }
    
    def generate_answer_complete(self, query: str, retrieval_result: Dict, 
                               understanding_result: Dict) -> Dict:
        """
        完整生成答案（非流式）
        
        Args:
            query: 用户查询
            retrieval_result: 检索结果
            understanding_result: 查询理解结果
            
        Returns:
            Dict: 完整答案
        """
        try:
            logger.info(f"开始完整生成答案: {query}")
            
            # 证据拼装
            context = self._build_context(retrieval_result, understanding_result)
            
            # 生成答案
            if self.llm_client:
                answer_content = self._generate_llm_answer(query, context, understanding_result)
            else:
                answer_content = self._generate_template_answer(query, context, understanding_result)
            
            # 格式化最终答案
            final_answer = self._format_final_answer(query, context, understanding_result, answer_content)
            
            return {
                "answer": final_answer,
                "context": context,
                "metadata": {
                    "total_sources": len(context.get("sources", [])),
                    "evidence_count": len(context.get("evidence_list", [])),
                    "generation_method": "llm" if self.llm_client else "template",
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"完整生成答案失败: {str(e)}")
            return {
                "answer": f"抱歉，生成答案时发生错误：{str(e)}",
                "context": {},
                "metadata": {"error": str(e)}
            }
    
    def _build_context(self, retrieval_result: Dict, understanding_result: Dict) -> Dict:
        """
        构建上下文
        
        Args:
            retrieval_result: 检索结果
            understanding_result: 查询理解结果
            
        Returns:
            Dict: 上下文信息
        """
        try:
            candidates = retrieval_result.get("candidates", [])
            
            # 按文档合并相邻块
            merged_chunks = self._merge_adjacent_chunks(candidates)
            
            # 表格强化
            enhanced_chunks = self._enhance_table_context(merged_chunks)
            
            # 图片/图表处理
            image_enhanced_chunks = self._enhance_image_context(enhanced_chunks)
            
            # 构建证据列表
            evidence_list = self._build_evidence_list(image_enhanced_chunks)
            
            # 提取关键信息
            key_facts = self._extract_key_facts(evidence_list, understanding_result)
            
            # 构建引用映射
            references = self._build_references(evidence_list)
            
            # 构建原文链接
            original_links = self._build_original_links(evidence_list)
            
            return {
                "evidence_list": evidence_list,
                "key_facts": key_facts,
                "references": references,
                "original_links": original_links,
                "sources": retrieval_result.get("sources", []),
                "total_chunks": len(candidates),
                "merged_chunks": len(merged_chunks)
            }
            
        except Exception as e:
            logger.error(f"构建上下文失败: {str(e)}")
            return {
                "evidence_list": [],
                "key_facts": [],
                "references": [],
                "original_links": [],
                "sources": [],
                "error": str(e)
            }
    
    def _merge_adjacent_chunks(self, candidates: List[Dict]) -> List[Dict]:
        """合并相邻块"""
        if not candidates:
            return []
        
        # 按文档和页面分组
        doc_groups = {}
        for candidate in candidates:
            doc_id = candidate.get("doc_id", "")
            page_no = candidate.get("page_no", 1)
            key = f"{doc_id}_{page_no}"
            
            if key not in doc_groups:
                doc_groups[key] = []
            doc_groups[key].append(candidate)
        
        merged_chunks = []
        
        for key, chunks in doc_groups.items():
            if len(chunks) == 1:
                merged_chunks.extend(chunks)
                continue
            
            # 按bbox位置排序（如果有的话）
            chunks.sort(key=lambda x: x.get("bbox", [0])[0] if x.get("bbox") else 0)
            
            # 检查是否可以合并
            current_chunk = chunks[0]
            
            for next_chunk in chunks[1:]:
                # 检查是否相邻（简化判断）
                if self._are_chunks_adjacent(current_chunk, next_chunk):
                    # 合并内容
                    current_chunk["content"] += " " + next_chunk.get("content", "")
                    current_chunk["bbox"] = self._merge_bbox(
                        current_chunk.get("bbox", []),
                        next_chunk.get("bbox", [])
                    )
                    # 取最高分数
                    current_chunk["final_score"] = max(
                        current_chunk.get("final_score", 0),
                        next_chunk.get("final_score", 0)
                    )
                else:
                    # 不相邻，添加当前块并开始新的块
                    merged_chunks.append(current_chunk)
                    current_chunk = next_chunk
            
            # 添加最后一个块
            merged_chunks.append(current_chunk)
        
        return merged_chunks
    
    def _are_chunks_adjacent(self, chunk1: Dict, chunk2: Dict) -> bool:
        """判断两个块是否相邻"""
        bbox1 = chunk1.get("bbox", [])
        bbox2 = chunk2.get("bbox", [])
        
        if not bbox1 or not bbox2 or len(bbox1) < 4 or len(bbox2) < 4:
            return False
        
        # 简单判断：垂直距离小于阈值
        vertical_distance = abs(bbox1[1] - bbox2[3])  # chunk1的top与chunk2的bottom
        return vertical_distance < 50  # 50像素阈值
    
    def _merge_bbox(self, bbox1: List, bbox2: List) -> List:
        """合并两个bbox"""
        if not bbox1:
            return bbox2
        if not bbox2:
            return bbox1
        
        if len(bbox1) >= 4 and len(bbox2) >= 4:
            return [
                min(bbox1[0], bbox2[0]),  # left
                min(bbox1[1], bbox2[1]),  # top
                max(bbox1[2], bbox2[2]),  # right
                max(bbox1[3], bbox2[3])   # bottom
            ]
        
        return bbox1
    
    def _enhance_table_context(self, chunks: List[Dict]) -> List[Dict]:
        """表格强化"""
        enhanced_chunks = []
        
        for chunk in chunks:
            content_type = chunk.get("metadata", {}).get("content_type", "text")
            
            if content_type == "table":
                # 对表格内容进行强化
                enhanced_chunk = chunk.copy()
                content = chunk.get("content", "")
                
                # 添加表格说明
                enhanced_chunk["content"] = f"[表格数据] {content}"
                
                # 如果是表格，尝试解析结构
                table_data = self._parse_table_structure(content)
                if table_data:
                    enhanced_chunk["table_structure"] = table_data
                
                enhanced_chunks.append(enhanced_chunk)
            else:
                enhanced_chunks.append(chunk)
        
        return enhanced_chunks
    
    def _parse_table_structure(self, content: str) -> Optional[Dict]:
        """解析表格结构（简化版）"""
        try:
            # 简单的表格解析
            lines = content.split('\n')
            table_data = {
                "rows": len(lines),
                "estimated_columns": 0,
                "headers": [],
                "preview": content[:200] + "..." if len(content) > 200 else content
            }
            
            # 估计列数（基于分隔符）
            if lines:
                separators = ['\t', '|', ',']
                for sep in separators:
                    col_count = lines[0].count(sep) + 1
                    if col_count > table_data["estimated_columns"]:
                        table_data["estimated_columns"] = col_count
            
            return table_data
            
        except Exception as e:
            logger.error(f"解析表格结构失败: {str(e)}")
            return None
    
    def _enhance_image_context(self, chunks: List[Dict]) -> List[Dict]:
        """图片/图表强化"""
        enhanced_chunks = []
        
        for chunk in chunks:
            if "图" in chunk.get("content", "") or "图表" in chunk.get("content", ""):
                enhanced_chunk = chunk.copy()
                
                # 添加图片说明
                enhanced_chunk["has_image"] = True
                enhanced_chunk["image_info"] = {
                    "page_no": chunk.get("page_no", 1),
                    "bbox": chunk.get("bbox", []),
                    "doc_id": chunk.get("doc_id", ""),
                    "caption": self._extract_image_caption(chunk.get("content", ""))
                }
                
                enhanced_chunks.append(enhanced_chunk)
            else:
                enhanced_chunks.append(chunk)
        
        return enhanced_chunks
    
    def _extract_image_caption(self, content: str) -> str:
        """提取图片说明"""
        # 简单的图片说明提取
        if "图" in content:
            lines = content.split('\n')
            for line in lines:
                if "图" in line and len(line) < 100:
                    return line.strip()
        
        return ""
    
    def _build_evidence_list(self, chunks: List[Dict]) -> List[Dict]:
        """构建证据列表"""
        evidence_list = []
        
        for i, chunk in enumerate(chunks[:10]):  # 最多取10个证据
            evidence = {
                "id": i + 1,
                "content": chunk.get("content", ""),
                "title": chunk.get("title", ""),
                "source": chunk.get("source", ""),
                "doc_id": chunk.get("doc_id", ""),
                "page_no": chunk.get("page_no", 1),
                "bbox": chunk.get("bbox", []),
                "score": chunk.get("final_score", 0),
                "file_type": chunk.get("file_type", ""),
                "has_table": chunk.get("metadata", {}).get("content_type") == "table",
                "has_image": chunk.get("has_image", False),
                "confidence": self._calculate_evidence_confidence(chunk)
            }
            
            evidence_list.append(evidence)
        
        return evidence_list
    
    def _calculate_evidence_confidence(self, chunk: Dict) -> float:
        """计算证据置信度"""
        confidence = chunk.get("final_score", 0)
        
        # 根据来源调整置信度
        source = chunk.get("source", "")
        if source == "graph":
            confidence += 0.1  # 图谱结果更可信
        elif source == "bm25" and chunk.get("highlight"):
            confidence += 0.05  # 有高亮的BM25结果更可信
        
        # 根据内容质量调整
        content = chunk.get("content", "")
        if len(content) > 100:
            confidence += 0.05  # 内容丰富
        
        return min(confidence, 1.0)
    
    def _extract_key_facts(self, evidence_list: List[Dict], understanding_result: Dict) -> List[str]:
        """提取关键事实"""
        key_facts = []
        query_type = understanding_result.get("query_type", "factual")
        
        for evidence in evidence_list[:5]:  # 从前5个证据提取
            content = evidence.get("content", "")
            
            # 基于查询类型提取不同类型的事实
            if query_type == "numerical":
                facts = self._extract_numerical_facts(content)
            elif query_type == "definition":
                facts = self._extract_definition_facts(content)
            elif query_type == "process":
                facts = self._extract_process_facts(content)
            else:
                facts = self._extract_general_facts(content)
            
            key_facts.extend(facts)
        
        # 去重并限制数量
        unique_facts = list(set(key_facts))
        return unique_facts[:8]
    
    def _extract_numerical_facts(self, content: str) -> List[str]:
        """提取数值事实"""
        facts = []
        
        # 查找数值模式
        patterns = [
            r'\d+\.?\d*\s*[%％]',  # 百分比
            r'\d+\.?\d*\s*[mg|ml|g|kg|℃|°C]',  # 单位数值
            r'pH\s*[值]?\s*[:：]?\s*\d+\.?\d*',  # pH值
            r'范围\s*[:：]?\s*\d+\.?\d*\s*[-~]\s*\d+\.?\d*',  # 范围
            r'\d+\.?\d*\s*[-~至到]\s*\d+\.?\d*',  # 范围
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                facts.append(match.strip())
        
        return facts[:3]
    
    def _extract_definition_facts(self, content: str) -> List[str]:
        """提取定义事实"""
        facts = []
        
        # 查找定义模式
        sentences = content.split('。')
        for sentence in sentences:
            if any(keyword in sentence for keyword in ['是', '指', '定义为', '称为', '叫做']):
                if len(sentence.strip()) < 200:  # 避免过长的句子
                    facts.append(sentence.strip() + '。')
        
        return facts[:3]
    
    def _extract_process_facts(self, content: str) -> List[str]:
        """提取流程事实"""
        facts = []
        
        # 查找步骤模式
        patterns = [
            r'第[一二三四五六七八九十\d]+步[：:]?[^。]*。',
            r'\d+[、\.][\s]*[^。]*。',
            r'步骤\d+[：:]?[^。]*。',
            r'[首先|然后|接下来|最后][^。]*。'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match.strip()) < 150:
                    facts.append(match.strip())
        
        return facts[:4]
    
    def _extract_general_facts(self, content: str) -> List[str]:
        """提取一般事实"""
        facts = []
        
        # 简单的句子分割
        sentences = content.split('。')
        for sentence in sentences:
            sentence = sentence.strip()
            if 20 < len(sentence) < 100:  # 长度合适的句子
                facts.append(sentence + '。')
        
        return facts[:2]
    
    def _build_references(self, evidence_list: List[Dict]) -> List[str]:
        """构建引用列表"""
        references = []
        
        for evidence in evidence_list:
            ref = f"[{evidence['id']}] {evidence.get('title', '未知标题')}"
            
            if evidence.get('page_no'):
                ref += f" (第{evidence['page_no']}页)"
            
            if evidence.get('file_type'):
                ref += f" [{evidence['file_type'].upper()}]"
            
            references.append(ref)
        
        return references
    
    def _build_original_links(self, evidence_list: List[Dict]) -> List[Dict]:
        """构建原文链接"""
        links = []
        
        for evidence in evidence_list:
            link = {
                "id": evidence["id"],
                "text": "查看原文",
                "doc_id": evidence.get("doc_id", ""),
                "page_no": evidence.get("page_no", 1),
                "bbox": evidence.get("bbox", []),
                "file_type": evidence.get("file_type", "")
            }
            
            # 生成查看链接（根据文件类型）
            if evidence.get("file_type") == "pdf" and evidence.get("bbox"):
                link["url"] = f"/api/file/view/{evidence['doc_id']}?page={evidence['page_no']}&bbox={','.join(map(str, evidence['bbox']))}"
            else:
                link["url"] = f"/api/file/view/{evidence['doc_id']}?page={evidence['page_no']}"
            
            links.append(link)
        
        return links
    
    def _stream_llm_generation(self, query: str, context: Dict, 
                             understanding_result: Dict) -> Generator[Dict, None, None]:
        """流式LLM生成"""
        try:
            prompt = self._build_llm_prompt(query, context, understanding_result)
            
            # 构建请求
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": "你是一个专业的知识问答助手，根据提供的证据准确回答用户问题。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": True
            }
            
            # 发送流式请求
            response = requests.post(
                f"{self.api_url}/v1/chat/completions",
                headers=self.llm_client["headers"],
                json=payload,
                stream=True
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                data = json.loads(data_str)
                                if 'choices' in data and data['choices']:
                                    delta = data['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        yield {
                                            "type": "answer_chunk",
                                            "content": delta['content']
                                        }
                            except json.JSONDecodeError:
                                continue
            else:
                # 请求失败，降级到模板生成
                for chunk in self._stream_template_generation(query, context, understanding_result):
                    yield chunk
                    
        except Exception as e:
            logger.error(f"LLM流式生成失败: {str(e)}")
            # 降级到模板生成
            for chunk in self._stream_template_generation(query, context, understanding_result):
                yield chunk
    
    def _stream_template_generation(self, query: str, context: Dict, 
                                  understanding_result: Dict) -> Generator[Dict, None, None]:
        """流式模板生成 - 按字符增量输出"""
        try:
            # 生成完整答案
            answer = self._generate_template_answer(query, context, understanding_result)
            
            # 按字符流式输出，每次发送1-3个字符
            chars_per_chunk = 2
            for i in range(0, len(answer), chars_per_chunk):
                chunk = answer[i:i + chars_per_chunk]
                yield {
                    "type": "answer_chunk",
                    "content": chunk
                }
                sleep(0.05)  # 模拟真实的生成速度
                    
        except Exception as e:
            logger.error(f"模板流式生成失败: {str(e)}")
            yield {
                "type": "answer_chunk",
                "content": f"抱歉，生成答案时发生错误：{str(e)}"
            }
    
    def _stream_multimodal_content(self, context: Dict) -> Generator[Dict, None, None]:
        """
        流式处理多模态内容
        严格按照要求分别推送图片、表格、图表事件
        
        Args:
            context: 上下文信息
            
        Yields:
            Dict: 多模态内容事件
        """
        try:
            evidence_list = context.get("evidence_list", [])
            
            for evidence in evidence_list:
                # 处理图片内容
                if evidence.get("has_image") and evidence.get("image_info"):
                    yield {
                        "type": "multimodal_content",
                        "content_type": "image",
                        "data": {
                            "element_id": evidence.get("id"),
                            "doc_id": evidence.get("doc_id"),
                            "page_no": evidence.get("page_no"),
                            "bbox": evidence.get("bbox", []),
                            "caption": evidence.get("image_info", {}).get("caption", ""),
                            "url": f"/api/file/view/{evidence.get('doc_id')}?page={evidence.get('page_no')}&highlight=image",
                            "description": evidence.get("content", "")[:100] + "..."
                        }
                    }
                    sleep(0.1)  # 模拟处理时间
                
                # 处理表格内容  
                if evidence.get("has_table") and evidence.get("table_structure"):
                    table_data = evidence.get("table_structure", {})
                    yield {
                        "type": "multimodal_content",
                        "content_type": "table",
                        "data": {
                            "element_id": evidence.get("id"),
                            "doc_id": evidence.get("doc_id"),
                            "page_no": evidence.get("page_no"),
                            "bbox": evidence.get("bbox", []),
                            "title": evidence.get("title", f"表格 {evidence.get('id')}"),
                            "summary": table_data.get("preview", ""),
                            "rows": table_data.get("rows", 0),
                            "columns": table_data.get("estimated_columns", 0),
                            "url": f"/api/file/view/{evidence.get('doc_id')}?page={evidence.get('page_no')}&highlight=table"
                        }
                    }
                    sleep(0.1)  # 模拟处理时间
                
                # 处理图表内容
                content = evidence.get("content", "")
                if any(keyword in content for keyword in ["图表", "图形", "Chart", "chart", "图"]):
                    yield {
                        "type": "multimodal_content", 
                        "content_type": "chart",
                        "data": {
                            "element_id": evidence.get("id"),
                            "doc_id": evidence.get("doc_id"),
                            "page_no": evidence.get("page_no"),
                            "bbox": evidence.get("bbox", []),
                            "description": content[:150] + "..." if len(content) > 150 else content,
                            "url": f"/api/file/view/{evidence.get('doc_id')}?page={evidence.get('page_no')}&highlight=chart"
                        }
                    }
                    sleep(0.1)  # 模拟处理时间
                    
        except Exception as e:
            logger.error(f"流式处理多模态内容失败: {str(e)}")
            yield {
                "type": "error",
                "content": f"多模态内容处理失败: {str(e)}"
            }
    
    def _build_llm_prompt(self, query: str, context: Dict, understanding_result: Dict) -> str:
        """构建LLM提示词"""
        evidence_list = context.get("evidence_list", [])
        key_facts = context.get("key_facts", [])
        
        # 构建证据文本
        evidence_text = "\n\n".join([
            f"证据{i+1}：{evidence['content']}"
            for i, evidence in enumerate(evidence_list[:5])
        ])
        
        # 构建关键事实
        facts_text = "\n".join([f"- {fact}" for fact in key_facts])
        
        prompt = f"""基于以下检索到的证据，请准确回答用户问题。

用户问题：{query}

相关证据：
{evidence_text}

关键事实：
{facts_text}

要求：
1. 根据证据内容回答，不要编造信息
2. 如果证据不足，请明确说明
3. 保持回答的结构化和条理性
4. 适当引用证据编号
5. 回答要专业、准确、有条理

请回答："""
        
        return prompt
    
    def _generate_llm_answer(self, query: str, context: Dict, understanding_result: Dict) -> str:
        """生成LLM答案（非流式）"""
        try:
            prompt = self._build_llm_prompt(query, context, understanding_result)
            
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": "你是一个专业的知识问答助手，根据提供的证据准确回答用户问题。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
            
            response = requests.post(
                f"{self.api_url}/v1/chat/completions",
                headers=self.llm_client["headers"],
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and result['choices']:
                    return result['choices'][0]['message']['content']
            
            # 如果LLM调用失败，降级到模板生成
            return self._generate_template_answer(query, context, understanding_result)
            
        except Exception as e:
            logger.error(f"LLM答案生成失败: {str(e)}")
            return self._generate_template_answer(query, context, understanding_result)
    
    def _generate_template_answer(self, query: str, context: Dict, understanding_result: Dict) -> str:
        """使用模板生成答案"""
        try:
            query_type = understanding_result.get("query_type", "factual")
            evidence_list = context.get("evidence_list", [])
            key_facts = context.get("key_facts", [])
            
            # 生成结论
            conclusion = self._generate_conclusion(query, evidence_list, key_facts, query_type)
            
            # 生成证据要点
            evidence_points = self._generate_evidence_points(evidence_list, key_facts)
            
            # 生成引用
            references = context.get("references", [])
            
            # 生成原文链接
            original_links = self._format_original_links(context.get("original_links", []))
            
            # 选择模板
            template = self.answer_templates.get(query_type, self.answer_templates["default"])
            
            # 填充模板
            answer = template.format(
                query=query,
                conclusion=conclusion,
                evidence_points=evidence_points,
                references="\n".join(references),
                original_links=original_links
            )
            
            return answer
            
        except Exception as e:
            logger.error(f"模板答案生成失败: {str(e)}")
            return f"抱歉，基于检索到的信息无法生成完整答案。错误：{str(e)}"
    
    def _generate_conclusion(self, query: str, evidence_list: List[Dict], 
                           key_facts: List[str], query_type: str) -> str:
        """生成结论"""
        if not evidence_list:
            return f"抱歉，没有找到关于「{query}」的相关信息。"
        
        # 基于第一个最高分证据生成结论
        top_evidence = evidence_list[0]
        content = top_evidence.get("content", "")
        
        if query_type == "definition":
            return f"根据检索到的资料，{self._extract_definition_from_content(content, query)}"
        elif query_type == "numerical":
            return f"关于{query}的数值信息如下：{self._extract_numbers_from_content(content)}"
        elif query_type == "process":
            return f"{query}的流程包括以下步骤："
        else:
            # 提取前100字符作为简要结论
            conclusion = content[:100].strip()
            if len(content) > 100:
                conclusion += "..."
            return conclusion
    
    def _extract_definition_from_content(self, content: str, query: str) -> str:
        """从内容中提取定义"""
        sentences = content.split('。')
        for sentence in sentences:
            if query in sentence and any(keyword in sentence for keyword in ['是', '指', '定义为']):
                return sentence.strip() + '。'
        
        return f"{query}的相关定义信息如下：" + content[:150] + ("..." if len(content) > 150 else "")
    
    def _extract_numbers_from_content(self, content: str) -> str:
        """从内容中提取数字信息"""
        # 查找数字模式
        number_patterns = [
            r'\d+\.?\d*\s*[%％mg/mlgkg℃°C]',
            r'pH\s*[值]?\s*[:：]?\s*\d+\.?\d*',
            r'范围\s*[:：]?\s*\d+\.?\d*\s*[-~]\s*\d+\.?\d*'
        ]
        
        numbers = []
        for pattern in number_patterns:
            matches = re.findall(pattern, content)
            numbers.extend(matches)
        
        if numbers:
            return "、".join(numbers[:5])
        else:
            return content[:100] + ("..." if len(content) > 100 else "")
    
    def _generate_evidence_points(self, evidence_list: List[Dict], key_facts: List[str]) -> str:
        """生成证据要点"""
        points = []
        
        # 使用关键事实
        for i, fact in enumerate(key_facts[:6]):
            points.append(f"{i+1}. {fact}")
        
        # 如果关键事实不够，从证据中补充
        if len(points) < 3:
            for i, evidence in enumerate(evidence_list[:3]):
                if i >= len(key_facts):
                    content = evidence.get("content", "")
                    point = content[:80].strip()
                    if len(content) > 80:
                        point += "..."
                    points.append(f"{len(points)+1}. {point}")
        
        return "\n".join(points)
    
    def _format_original_links(self, links: List[Dict]) -> str:
        """格式化原文链接"""
        if not links:
            return ""
        
        formatted_links = []
        for link in links[:5]:  # 最多显示5个链接
            formatted_links.append(
                f"📄 [{link['text']}]({link['url']}) (第{link['page_no']}页)"
            )
        
        return "\n**查看原文：**\n" + "\n".join(formatted_links)
    
    def _format_final_answer(self, query: str, context: Dict, 
                           understanding_result: Dict, answer_content: str = None) -> Dict:
        """格式化最终答案"""
        evidence_list = context.get("evidence_list", [])
        
        if answer_content is None:
            answer_content = self._generate_template_answer(query, context, understanding_result)
        
        return {
            "query": query,
            "answer": answer_content,
            "evidence_count": len(evidence_list),
            "confidence": self._calculate_answer_confidence(evidence_list),
            "query_type": understanding_result.get("query_type", "factual"),
            "sources": context.get("sources", []),
            "has_tables": any(e.get("has_table", False) for e in evidence_list),
            "has_images": any(e.get("has_image", False) for e in evidence_list),
            "original_links": context.get("original_links", []),
            "generation_time": datetime.now().isoformat()
        }
    
    def _calculate_answer_confidence(self, evidence_list: List[Dict]) -> float:
        """计算答案置信度"""
        if not evidence_list:
            return 0.0
        
        # 基于证据数量和质量计算置信度
        confidence = 0.0
        
        # 证据数量贡献
        evidence_count = len(evidence_list)
        confidence += min(evidence_count * 0.1, 0.4)
        
        # 证据质量贡献（平均置信度）
        avg_evidence_confidence = sum(e.get("confidence", 0) for e in evidence_list) / len(evidence_list)
        confidence += avg_evidence_confidence * 0.6
        
        return min(confidence, 1.0)
