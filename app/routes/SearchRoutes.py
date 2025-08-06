"""
智能检索路由
处理搜索、问答等智能检索相关的HTTP请求
"""

import logging
from flask import Blueprint, request, jsonify
import json

from app.service.SearchService import SearchService


# 创建蓝图
search_bp = Blueprint('search', __name__, url_prefix='/api/search')

# 初始化服务
search_service = SearchService()

logger = logging.getLogger(__name__)


@search_bp.route('/vector', methods=['POST'])
def vector_search():
    """
    向量相似性搜索接口
    
    Returns:
        JSON响应，包含搜索结果
    """
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'message': '缺少查询参数',
                'code': 400
            }), 400
        
        query = data['query'].strip()
        if not query:
            return jsonify({
                'success': False,
                'message': '查询内容不能为空',
                'code': 400
            }), 400
        
        # 获取搜索参数
        top_k = data.get('top_k', 10)
        filters = data.get('filters', {})
        
        # 参数验证
        if top_k < 1 or top_k > 100:
            top_k = 10
        
        # 执行向量搜索
        results = search_service.vector_search(
            query=query,
            top_k=top_k,
            filters=filters
        )
        
        return jsonify({
            'success': True,
            'message': '向量搜索完成',
            'data': {
                'query': query,
                'results': results,
                'total': len(results)
            },
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"向量搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'向量搜索失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/graph', methods=['POST'])
def graph_search():
    """
    知识图谱搜索接口
    
    Returns:
        JSON响应，包含搜索结果
    """
    try:
        data = request.get_json()
        if not data or 'entity' not in data:
            return jsonify({
                'success': False,
                'message': '缺少实体参数',
                'code': 400
            }), 400
        
        entity_name = data['entity'].strip()
        if not entity_name:
            return jsonify({
                'success': False,
                'message': '实体名称不能为空',
                'code': 400
            }), 400
        
        relationship_types = data.get('relationship_types', None)
        
        # 执行图搜索
        results = search_service.graph_search(
            entity_name=entity_name,
            relationship_types=relationship_types
        )
        
        return jsonify({
            'success': True,
            'message': '知识图谱搜索完成',
            'data': {
                'entity': entity_name,
                'results': results
            },
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"知识图谱搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'知识图谱搜索失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/hybrid', methods=['POST'])
def hybrid_search():
    """
    混合搜索接口（向量+图谱）
    
    Returns:
        JSON响应，包含搜索结果
    """
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'message': '缺少查询参数',
                'code': 400
            }), 400
        
        query = data['query'].strip()
        if not query:
            return jsonify({
                'success': False,
                'message': '查询内容不能为空',
                'code': 400
            }), 400
        
        # 获取搜索参数
        top_k = data.get('top_k', 10)
        enable_graph = data.get('enable_graph', True)
        filters = data.get('filters', {})
        
        # 参数验证
        if top_k < 1 or top_k > 100:
            top_k = 10
        
        # 执行混合搜索
        results = search_service.hybrid_search(
            query=query,
            top_k=top_k,
            enable_graph=enable_graph,
            filters=filters
        )
        
        return jsonify({
            'success': True,
            'message': '混合搜索完成',
            'data': results,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"混合搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'混合搜索失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/semantic', methods=['POST'])
def semantic_search():
    """
    语义搜索接口
    
    Returns:
        JSON响应，包含搜索结果
    """
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'message': '缺少查询参数',
                'code': 400
            }), 400
        
        query = data['query'].strip()
        if not query:
            return jsonify({
                'success': False,
                'message': '查询内容不能为空',
                'code': 400
            }), 400
        
        # 获取搜索参数
        search_type = data.get('search_type', 'all')  # vector, graph, all
        top_k = data.get('top_k', 10)
        filters = data.get('filters', {})
        
        # 参数验证
        if search_type not in ['vector', 'graph', 'all']:
            search_type = 'all'
        
        if top_k < 1 or top_k > 100:
            top_k = 10
        
        # 执行语义搜索
        results = search_service.semantic_search(
            query=query,
            search_type=search_type,
            top_k=top_k,
            filters=filters
        )
        
        return jsonify({
            'success': True,
            'message': '语义搜索完成',
            'data': results,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"语义搜索失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'语义搜索失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/qa', methods=['POST'])
def question_answering():
    """
    智能问答接口
    
    Returns:
        JSON响应，包含问答结果
    """
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({
                'success': False,
                'message': '缺少问题参数',
                'code': 400
            }), 400
        
        question = data['question'].strip()
        if not question:
            return jsonify({
                'success': False,
                'message': '问题内容不能为空',
                'code': 400
            }), 400
        
        # 获取上下文限制参数
        context_limit = data.get('context_limit', 5)
        
        # 参数验证
        if context_limit < 1 or context_limit > 20:
            context_limit = 5
        
        # 执行问答
        results = search_service.question_answering(
            question=question,
            context_limit=context_limit
        )
        
        return jsonify({
            'success': True,
            'message': '问答完成',
            'data': results,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"智能问答失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'智能问答失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/suggestions', methods=['GET'])
def get_search_suggestions():
    """
    获取搜索建议接口
    
    Returns:
        JSON响应，包含搜索建议
    """
    try:
        # 获取查询参数
        partial_query = request.args.get('q', '').strip()
        limit = request.args.get('limit', 5, type=int)
        
        if not partial_query:
            return jsonify({
                'success': False,
                'message': '缺少查询参数',
                'code': 400
            }), 400
        
        # 参数验证
        if limit < 1 or limit > 20:
            limit = 5
        
        # 获取搜索建议
        suggestions = search_service.get_search_suggestions(
            partial_query=partial_query,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'message': '获取搜索建议成功',
            'data': {
                'query': partial_query,
                'suggestions': suggestions,
                'total': len(suggestions)
            },
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"获取搜索建议失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取搜索建议失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/history', methods=['GET'])
def get_search_history():
    """
    获取搜索历史接口
    
    Returns:
        JSON响应，包含搜索历史
    """
    try:
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        search_type = request.args.get('search_type', None)
        
        # 参数验证
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        
        # 这里应该从数据库获取搜索历史
        # 暂时返回空结果
        history_data = {
            'history': [],
            'total': 0,
            'page': page,
            'page_size': page_size,
            'total_pages': 0
        }
        
        return jsonify({
            'success': True,
            'message': '获取搜索历史成功',
            'data': history_data,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"获取搜索历史失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取搜索历史失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/export', methods=['POST'])
def export_search_results():
    """
    导出搜索结果接口
    
    Returns:
        JSON响应，包含导出结果
    """
    try:
        data = request.get_json()
        if not data or 'search_results' not in data:
            return jsonify({
                'success': False,
                'message': '缺少搜索结果数据',
                'code': 400
            }), 400
        
        search_results = data['search_results']
        export_format = data.get('format', 'json')  # json, csv, excel
        
        # 参数验证
        if export_format not in ['json', 'csv', 'excel']:
            export_format = 'json'
        
        # 这里应该实现实际的导出逻辑
        # 暂时返回成功响应
        export_data = {
            'export_id': 'export_' + str(hash(str(search_results))),
            'format': export_format,
            'file_size': len(str(search_results)),
            'download_url': f'/api/search/download/{export_format}'
        }
        
        return jsonify({
            'success': True,
            'message': '搜索结果导出成功',
            'data': export_data,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"导出搜索结果失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'导出搜索结果失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/stats', methods=['GET'])
def get_search_stats():
    """
    获取搜索统计信息接口
    
    Returns:
        JSON响应，包含统计信息
    """
    try:
        # 获取查询参数
        time_range = request.args.get('time_range', '7d')  # 1d, 7d, 30d, all
        
        # 这里应该从数据库获取实际的统计数据
        # 暂时返回模拟数据
        stats_data = {
            'total_searches': 0,
            'vector_searches': 0,
            'graph_searches': 0,
            'qa_requests': 0,
            'avg_response_time': 0.0,
            'popular_queries': [],
            'search_trends': []
        }
        
        return jsonify({
            'success': True,
            'message': '获取搜索统计信息成功',
            'data': stats_data,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"获取搜索统计信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取搜索统计信息失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/feedback', methods=['POST'])
def submit_search_feedback():
    """
    提交搜索反馈接口
    
    Returns:
        JSON响应，包含提交结果
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '缺少反馈数据',
                'code': 400
            }), 400
        
        # 获取反馈参数
        search_id = data.get('search_id')
        rating = data.get('rating')  # 1-5分
        feedback_text = data.get('feedback', '')
        helpful_results = data.get('helpful_results', [])
        
        # 参数验证
        if rating is not None and (rating < 1 or rating > 5):
            return jsonify({
                'success': False,
                'message': '评分必须在1-5之间',
                'code': 400
            }), 400
        
        # 这里应该将反馈数据保存到数据库
        # 暂时返回成功响应
        
        return jsonify({
            'success': True,
            'message': '反馈提交成功',
            'data': {
                'feedback_id': f'feedback_{hash(str(data))}',
                'timestamp': '2024-01-01T00:00:00Z'
            },
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"提交搜索反馈失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'提交搜索反馈失败: {str(e)}',
            'code': 500
        }), 500


@search_bp.route('/similar/<int:document_id>', methods=['GET'])
def find_similar_documents(document_id):
    """
    查找相似文档接口
    
    Args:
        document_id: 文档ID
        
    Returns:
        JSON响应，包含相似文档列表
    """
    try:
        # 获取查询参数
        top_k = request.args.get('top_k', 10, type=int)
        similarity_threshold = request.args.get('threshold', 0.7, type=float)
        
        # 参数验证
        if top_k < 1 or top_k > 50:
            top_k = 10
        
        if similarity_threshold < 0 or similarity_threshold > 1:
            similarity_threshold = 0.7
        
        # 这里应该实现相似文档查找逻辑
        # 暂时返回空结果
        similar_docs = []
        
        return jsonify({
            'success': True,
            'message': '相似文档查找完成',
            'data': {
                'document_id': document_id,
                'similar_documents': similar_docs,
                'total': len(similar_docs),
                'threshold': similarity_threshold
            },
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"查找相似文档失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'查找相似文档失败: {str(e)}',
            'code': 500
        }), 500


# 错误处理
@search_bp.errorhandler(400)
def bad_request(e):
    """处理请求错误"""
    return jsonify({
        'success': False,
        'message': '请求参数错误',
        'code': 400
    }), 400


@search_bp.errorhandler(404)
def not_found(e):
    """处理资源不存在错误"""
    return jsonify({
        'success': False,
        'message': '请求的资源不存在',
        'code': 404
    }), 404


@search_bp.errorhandler(500)
def internal_error(e):
    """处理内部服务器错误"""
    return jsonify({
        'success': False,
        'message': '内部服务器错误',
        'code': 500
    }), 500