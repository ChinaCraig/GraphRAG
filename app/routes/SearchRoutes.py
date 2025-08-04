#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能检索路由
处理智能检索相关的路由信息，只做入参和返参的处理
"""

from flask import Blueprint, request, jsonify
import logging
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.service.SearchService import SearchService

logger = logging.getLogger(__name__)

# 创建蓝图
search_routes = Blueprint('search', __name__, url_prefix='/api/search')

# 搜索服务实例
search_service = SearchService()

@search_routes.route('/query', methods=['POST'])
def search_query():
    """
    智能检索接口
    
    入参:
        - query: 查询文本
        - top_k: 返回结果数量（可选，默认10）
        - search_type: 搜索类型（可选，默认vector）
        - file_type: 文件类型过滤（可选）
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 搜索结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'message': '缺少查询参数',
                'data': None
            }), 400
        
        query = data['query']
        top_k = data.get('top_k', 10)
        search_type = data.get('search_type', 'vector')
        file_type = data.get('file_type', '')
        
        # 调用服务层处理
        result = search_service.search_query(query, top_k, search_type, file_type)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"智能检索失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'智能检索失败: {str(e)}',
            'data': None
        }), 500

@search_routes.route('/semantic', methods=['POST'])
def semantic_search():
    """
    语义搜索接口
    
    入参:
        - query: 查询文本
        - top_k: 返回结果数量（可选，默认10）
        - threshold: 相似度阈值（可选，默认0.5）
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 搜索结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'message': '缺少查询参数',
                'data': None
            }), 400
        
        query = data['query']
        top_k = data.get('top_k', 10)
        threshold = data.get('threshold', 0.5)
        
        # 调用服务层处理
        result = search_service.semantic_search(query, top_k, threshold)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"语义搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'语义搜索失败: {str(e)}',
            'data': None
        }), 500

@search_routes.route('/keyword', methods=['POST'])
def keyword_search():
    """
    关键词搜索接口
    
    入参:
        - keywords: 关键词列表
        - top_k: 返回结果数量（可选，默认10）
        - match_type: 匹配类型（可选，默认any）
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 搜索结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'keywords' not in data:
            return jsonify({
                'success': False,
                'message': '缺少关键词参数',
                'data': None
            }), 400
        
        keywords = data['keywords']
        top_k = data.get('top_k', 10)
        match_type = data.get('match_type', 'any')
        
        # 调用服务层处理
        result = search_service.keyword_search(keywords, top_k, match_type)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"关键词搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'关键词搜索失败: {str(e)}',
            'data': None
        }), 500

@search_routes.route('/hybrid', methods=['POST'])
def hybrid_search():
    """
    混合搜索接口
    
    入参:
        - query: 查询文本
        - top_k: 返回结果数量（可选，默认10）
        - vector_weight: 向量搜索权重（可选，默认0.7）
        - keyword_weight: 关键词搜索权重（可选，默认0.3）
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 搜索结果
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'message': '缺少查询参数',
                'data': None
            }), 400
        
        query = data['query']
        top_k = data.get('top_k', 10)
        vector_weight = data.get('vector_weight', 0.7)
        keyword_weight = data.get('keyword_weight', 0.3)
        
        # 调用服务层处理
        result = search_service.hybrid_search(query, top_k, vector_weight, keyword_weight)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"混合搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'混合搜索失败: {str(e)}',
            'data': None
        }), 500

@search_routes.route('/answer', methods=['POST'])
def generate_answer():
    """
    生成答案接口
    
    入参:
        - query: 查询文本
        - context: 上下文信息（可选）
        - max_length: 答案最大长度（可选，默认500）
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 生成的答案
    """
    try:
        # 获取请求数据
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'message': '缺少查询参数',
                'data': None
            }), 400
        
        query = data['query']
        context = data.get('context', '')
        max_length = data.get('max_length', 500)
        
        # 调用服务层处理
        result = search_service.generate_answer(query, context, max_length)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"生成答案失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'生成答案失败: {str(e)}',
            'data': None
        }), 500

@search_routes.route('/history', methods=['GET'])
def get_search_history():
    """
    获取搜索历史接口
    
    入参:
        - page: 页码（可选，默认1）
        - size: 每页大小（可选，默认10）
        - query_type: 查询类型过滤（可选）
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 搜索历史
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        query_type = request.args.get('query_type', '')
        
        # 调用服务层处理
        result = search_service.get_search_history(page, size, query_type)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取搜索历史失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取搜索历史失败: {str(e)}',
            'data': None
        }), 500 