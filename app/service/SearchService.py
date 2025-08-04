#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能检索服务
"""

import logging
import yaml
from typing import Dict, Any, List
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils.MySQLManager import get_mysql_manager
from utils.MilvusManager import get_milvus_manager

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self, config_path: str = "config/model.yaml"):
        self.config_path = config_path
        self.mysql_manager = None
        self.milvus_manager = None
        self._load_config()
        self._init_managers()
    
    def _load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.deepseek_config = config.get('deepseek', {})
            logger.info("智能检索配置加载成功")
        except Exception as e:
            logger.error(f"加载智能检索配置失败: {str(e)}")
            raise
    
    def _init_managers(self):
        try:
            self.mysql_manager = get_mysql_manager()
            self.milvus_manager = get_milvus_manager()
            logger.info("数据库管理器初始化成功")
        except Exception as e:
            logger.error(f"初始化数据库管理器失败: {str(e)}")
            raise
    
    def search_query(self, query: str, top_k: int = 10, search_type: str = 'vector', file_type: str = '') -> Dict[str, Any]:
        try:
            logger.info(f"开始智能检索: {query}")
            
            if search_type == 'vector':
                results = self._vector_search(query, top_k, file_type)
            elif search_type == 'keyword':
                results = self._keyword_search(query, top_k, file_type)
            elif search_type == 'hybrid':
                results = self._hybrid_search(query, top_k, file_type)
            else:
                results = self._vector_search(query, top_k, file_type)
            
            self._save_search_history(query, search_type, len(results))
            
            return {
                'success': True,
                'message': '智能检索成功',
                'data': {
                    'query': query,
                    'search_type': search_type,
                    'results': results,
                    'total': len(results)
                }
            }
        except Exception as e:
            logger.error(f"智能检索失败: {str(e)}")
            return {'success': False, 'message': f'智能检索失败: {str(e)}', 'data': None}
    
    def semantic_search(self, query: str, top_k: int = 10, threshold: float = 0.5) -> Dict[str, Any]:
        try:
            logger.info(f"开始语义搜索: {query}")
            results = self._vector_search(query, top_k)
            filtered_results = [r for r in results if r.get('distance', 0) >= threshold]
            
            return {
                'success': True,
                'message': '语义搜索成功',
                'data': {
                    'query': query,
                    'results': filtered_results,
                    'total': len(filtered_results),
                    'threshold': threshold
                }
            }
        except Exception as e:
            logger.error(f"语义搜索失败: {str(e)}")
            return {'success': False, 'message': f'语义搜索失败: {str(e)}', 'data': None}
    
    def keyword_search(self, keywords: List[str], top_k: int = 10, match_type: str = 'any') -> Dict[str, Any]:
        try:
            logger.info(f"开始关键词搜索: {keywords}")
            
            if match_type == 'all':
                where_conditions = []
                for i, keyword in enumerate(keywords):
                    where_conditions.append(f"content LIKE %(keyword{i})s")
                where_clause = " AND ".join(where_conditions)
                params = {f'keyword{i}': f'%{keyword}%' for i, keyword in enumerate(keywords)}
            else:
                where_conditions = []
                for i, keyword in enumerate(keywords):
                    where_conditions.append(f"content LIKE %(keyword{i})s")
                where_clause = " OR ".join(where_conditions)
                params = {f'keyword{i}': f'%{keyword}%' for i, keyword in enumerate(keywords)}
            
            sql = f"""
            SELECT vd.*, fi.file_name, fi.file_type
            FROM vector_data vd
            JOIN file_info fi ON vd.file_id = fi.id
            WHERE {where_clause}
            ORDER BY vd.created_at DESC
            LIMIT %(top_k)s
            """
            params['top_k'] = top_k
            
            results = self.mysql_manager.execute_query(sql, params)
            
            return {
                'success': True,
                'message': '关键词搜索成功',
                'data': {
                    'keywords': keywords,
                    'match_type': match_type,
                    'results': results,
                    'total': len(results)
                }
            }
        except Exception as e:
            logger.error(f"关键词搜索失败: {str(e)}")
            return {'success': False, 'message': f'关键词搜索失败: {str(e)}', 'data': None}
    
    def hybrid_search(self, query: str, top_k: int = 10, vector_weight: float = 0.7, keyword_weight: float = 0.3) -> Dict[str, Any]:
        try:
            logger.info(f"开始混合搜索: {query}")
            
            vector_results = self._vector_search(query, top_k)
            keyword_results = self._keyword_search([query], top_k)
            combined_results = self._combine_search_results(vector_results, keyword_results, vector_weight, keyword_weight)
            
            return {
                'success': True,
                'message': '混合搜索成功',
                'data': {
                    'query': query,
                    'results': combined_results[:top_k],
                    'total': len(combined_results),
                    'vector_weight': vector_weight,
                    'keyword_weight': keyword_weight
                }
            }
        except Exception as e:
            logger.error(f"混合搜索失败: {str(e)}")
            return {'success': False, 'message': f'混合搜索失败: {str(e)}', 'data': None}
    
    def generate_answer(self, query: str, context: str = '', max_length: int = 500) -> Dict[str, Any]:
        try:
            logger.info(f"开始生成答案: {query}")
            
            if not context:
                search_results = self._vector_search(query, 5)
                context = self._build_context_from_results(search_results)
            
            prompt = self._build_answer_prompt(query, context, max_length)
            answer = self._call_llm(prompt)
            
            return {
                'success': True,
                'message': '答案生成成功',
                'data': {
                    'query': query,
                    'answer': answer,
                    'context': context,
                    'max_length': max_length
                }
            }
        except Exception as e:
            logger.error(f"生成答案失败: {str(e)}")
            return {'success': False, 'message': f'生成答案失败: {str(e)}', 'data': None}
    
    def get_search_history(self, page: int = 1, size: int = 10, query_type: str = '') -> Dict[str, Any]:
        try:
            where_conditions = []
            params = {}
            
            if query_type:
                where_conditions.append("query_type = %(query_type)s")
                params['query_type'] = query_type
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            offset = (page - 1) * size
            
            count_sql = f"SELECT COUNT(*) as total FROM search_history WHERE {where_clause}"
            count_result = self.mysql_manager.execute_query(count_sql, params)
            total = count_result[0]['total'] if count_result else 0
            
            list_sql = f"""
            SELECT id, query_text, query_type, result_count, search_time, user_ip
            FROM search_history 
            WHERE {where_clause}
            ORDER BY search_time DESC
            LIMIT %(size)s OFFSET %(offset)s
            """
            
            params.update({'size': size, 'offset': offset})
            history = self.mysql_manager.execute_query(list_sql, params)
            
            return {
                'success': True,
                'message': '获取搜索历史成功',
                'data': {
                    'history': history,
                    'total': total,
                    'page': page,
                    'size': size,
                    'total_pages': (total + size - 1) // size
                }
            }
        except Exception as e:
            logger.error(f"获取搜索历史失败: {str(e)}")
            return {'success': False, 'message': f'获取搜索历史失败: {str(e)}', 'data': None}
    
    def _vector_search(self, query: str, top_k: int, file_type: str = '') -> List[Dict[str, Any]]:
        try:
            return []
        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            return []
    
    def _keyword_search(self, query: str, top_k: int, file_type: str = '') -> List[Dict[str, Any]]:
        try:
            where_conditions = ["content LIKE %(query)s"]
            params = {'query': f'%{query}%', 'top_k': top_k}
            
            if file_type:
                where_conditions.append("fi.file_type = %(file_type)s")
                params['file_type'] = file_type
            
            where_clause = " AND ".join(where_conditions)
            
            sql = f"""
            SELECT vd.*, fi.file_name, fi.file_type
            FROM vector_data vd
            JOIN file_info fi ON vd.file_id = fi.id
            WHERE {where_clause}
            ORDER BY vd.created_at DESC
            LIMIT %(top_k)s
            """
            
            return self.mysql_manager.execute_query(sql, params)
        except Exception as e:
            logger.error(f"关键词搜索失败: {str(e)}")
            return []
    
    def _hybrid_search(self, query: str, top_k: int, file_type: str = '') -> List[Dict[str, Any]]:
        try:
            vector_results = self._vector_search(query, top_k, file_type)
            keyword_results = self._keyword_search(query, top_k, file_type)
            combined_results = vector_results + keyword_results
            return combined_results[:top_k]
        except Exception as e:
            logger.error(f"混合搜索失败: {str(e)}")
            return []
    
    def _combine_search_results(self, vector_results: List[Dict], keyword_results: List[Dict], 
                               vector_weight: float, keyword_weight: float) -> List[Dict]:
        combined = []
        
        for result in vector_results:
            result['score'] = result.get('distance', 0) * vector_weight
            combined.append(result)
        
        for result in keyword_results:
            result['score'] = 1.0 * keyword_weight
            combined.append(result)
        
        combined.sort(key=lambda x: x.get('score', 0), reverse=True)
        return combined
    
    def _build_context_from_results(self, results: List[Dict[str, Any]]) -> str:
        context_parts = []
        for result in results:
            content = result.get('content', '')
            if content:
                context_parts.append(content)
        return "\n\n".join(context_parts)
    
    def _build_answer_prompt(self, query: str, context: str, max_length: int) -> str:
        prompt = f"""
        基于以下上下文信息，回答用户的问题。
        
        上下文信息：
        {context}
        
        用户问题：
        {query}
        
        请生成一个准确、完整的答案，长度不超过{max_length}个字符。
        """
        return prompt.strip()
    
    def _call_llm(self, prompt: str) -> str:
        try:
            return "这是一个模拟的答案，实际应用中需要调用DeepSeek API。"
        except Exception as e:
            logger.error(f"调用大语言模型失败: {str(e)}")
            return "抱歉，无法生成答案。"
    
    def _save_search_history(self, query: str, query_type: str, result_count: int):
        try:
            sql = """
            INSERT INTO search_history (query_text, query_type, result_count, user_ip)
            VALUES (%(query)s, %(query_type)s, %(result_count)s, %(user_ip)s)
            """
            
            params = {
                'query': query,
                'query_type': query_type,
                'result_count': result_count,
                'user_ip': '127.0.0.1'
            }
            
            self.mysql_manager.execute_insert(sql, params)
        except Exception as e:
            logger.error(f"保存搜索历史失败: {str(e)}") 