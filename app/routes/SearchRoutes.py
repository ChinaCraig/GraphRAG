"""
智能检索路由模块
处理搜索相关的HTTP请求，支持流式响应
只负责接口的入参和返参处理，不处理任何业务内容
"""

import json
import traceback
from flask import Blueprint, request, Response, current_app
from flask_socketio import emit
from app.service.search.SearchService import SearchService

# 创建蓝图
search_bp = Blueprint('search', __name__, url_prefix='/api/search')

# 初始化服务实例
search_service = SearchService()


@search_bp.route('/intelligent', methods=['POST', 'GET'])
def intelligent_search():
    """
    智能检索接口
    
    Request Body:
        {
            "query": "用户查询文本",
            "user_id": "用户ID（可选）",
            "session_id": "会话ID（可选）",
            "stream": true/false,  # 是否流式响应
            "filters": {           # 过滤条件（可选）
                "time_range": ["start_time", "end_time"],
                "doc_types": ["pdf", "docx"],
                "departments": ["部门1", "部门2"]
            }
        }
    
    Response:
        流式响应或一次性响应，包含理解、召回、答案生成的过程
    """
    try:
        # 根据请求方法获取参数
        if request.method == 'POST':
            # POST请求从JSON获取参数
            request_data = request.get_json()
            if not request_data:
                return {
                    "success": False,
                    "message": "请求体不能为空"
                }, 400
            
            query = request_data.get('query', '').strip()
            user_id = request_data.get('user_id', 'anonymous')
            session_id = request_data.get('session_id', 'default')
            stream = request_data.get('stream', True)
            filters = request_data.get('filters', {})
        else:
            # GET请求从URL参数获取
            query = request.args.get('query', '').strip()
            user_id = request.args.get('user_id', 'anonymous')
            session_id = request.args.get('session_id', 'default')
            stream = request.args.get('stream', 'true').lower() == 'true'
            filters = {}
        
        if not query:
            return {
                "success": False,
                "message": "查询内容不能为空"
            }, 400
        
        # 验证参数长度
        if len(query) > 1000:
            return {
                "success": False,
                "message": "查询内容过长，请控制在1000字符以内"
            }, 400
        
        current_app.logger.info(f"开始智能检索 - query: {query[:100]}..., user_id: {user_id}, stream: {stream}")
        
        # 如果是流式响应
        if stream:
            return Response(
                _stream_search_process(query, user_id, session_id, filters),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Cache-Control'
                }
            )
        else:
            # 非流式响应，一次性返回完整结果
            return _complete_search_process(query, user_id, session_id, filters)
    
    except Exception as e:
        current_app.logger.error(f"智能检索接口错误: {str(e)}\n{traceback.format_exc()}")
        return {
            "success": False,
            "message": f"服务器内部错误: {str(e)}"
        }, 500


def _stream_search_process(query, user_id, session_id, filters):
    """
    流式搜索过程，生成器函数
    严格按照SSE格式输出增量内容
    
    Args:
        query: 查询文本
        user_id: 用户ID
        session_id: 会话ID
        filters: 过滤条件
        
    Yields:
        str: SSE格式的响应数据
    """
    try:
        # 调用统一的智能检索服务，直接流式处理
        for chunk in search_service.intelligent_search(query, filters):
            chunk_type = chunk.get("type", "")
            
            if chunk_type == "stage_update":
                # 阶段更新
                yield _format_sse_event("stage_update", {
                    "stage": chunk.get("stage", ""),
                    "message": chunk.get("message", ""),
                    "progress": chunk.get("progress", 0),
                    "data": chunk.get("data", {})
                })
            elif chunk_type == "answer_chunk":
                # 推送文本增量
                yield _format_sse_event("text_delta", {
                    "content": chunk.get("content", ""),
                    "append": True
                })
            elif chunk_type == "multimodal_content":
                # 推送多模态内容事件
                content_type = chunk.get("content_type")
                if content_type == "image":
                    yield _format_sse_event("render_image", chunk.get("data", {}))
                elif content_type == "table":
                    yield _format_sse_event("render_table", chunk.get("data", {}))
                elif content_type == "chart":
                    yield _format_sse_event("render_chart", chunk.get("data", {}))
            elif chunk_type == "final_answer":
                # 推送最终完整答案
                yield _format_sse_event("final_answer", {
                    "answer": chunk.get("content", {}),
                    "metadata": chunk.get("metadata", {})
                })
            elif chunk_type == "error":
                # 错误处理
                yield _format_sse_event("error", {
                    "message": chunk.get("message", "处理失败")
                })
        
        # 完成
        yield _format_sse_event("completed", {
            "message": "🎉 检索完成",
            "progress": 100
        })
        
    except Exception as e:
        current_app.logger.error(f"流式搜索过程错误: {str(e)}\n{traceback.format_exc()}")
        yield _format_sse_event("error", {
            "message": f"❌ 处理过程中发生错误: {str(e)}"
        })


def _complete_search_process(query, user_id, session_id, filters):
    """
    完整搜索过程，一次性返回结果
    
    Args:
        query: 查询文本
        user_id: 用户ID
        session_id: 会话ID
        filters: 过滤条件
        
    Returns:
        tuple: (response_dict, status_code)
    """
    try:
        # 收集所有流式结果
        all_chunks = []
        final_answer = None
        
        for chunk in search_service.intelligent_search(query, filters):
            all_chunks.append(chunk)
            if chunk.get("type") == "final_answer":
                final_answer = chunk.get("content", {})
        
        # 构建响应
        return {
            "success": True,
            "data": {
                "query": query,
                "answer": final_answer or {},
                "chunks": all_chunks
            },
            "user_id": user_id,
            "session_id": session_id
        }, 200
        
    except Exception as e:
        current_app.logger.error(f"完整搜索过程错误: {str(e)}\n{traceback.format_exc()}")
        return {
            "success": False,
            "message": f"搜索失败: {str(e)}"
        }, 500


def _format_sse_event(event_type, data):
    """
    格式化SSE事件数据
    
    Args:
        event_type: 事件类型
        data: 事件数据
        
    Returns:
        str: SSE格式的事件字符串
    """
    response = {
        "timestamp": _get_current_timestamp(),
        **data
    }
    
    # SSE格式: event: 事件类型\ndata: JSON数据\n\n
    event_data = json.dumps(response, ensure_ascii=False)
    return f"event: {event_type}\ndata: {event_data}\n\n"


def _get_current_timestamp():
    """
    获取当前时间戳
    
    Returns:
        str: ISO格式时间戳
    """
    from datetime import datetime
    return datetime.now().isoformat()


@search_bp.route('/suggestions', methods=['GET'])
def get_search_suggestions():
    """获取搜索建议（简化版）"""
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        
        # 简单的建议列表
        suggestions = [
            {"text": "HCP检测方法", "type": "query", "score": 0.9},
            {"text": "CHO细胞培养", "type": "query", "score": 0.8},
            {"text": "蛋白质纯度检测", "type": "query", "score": 0.7}
        ]
        
        # 过滤匹配的建议
        if query:
            filtered = [s for s in suggestions if query.lower() in s["text"].lower()]
            return {"success": True, "data": filtered[:limit]}
        
        return {"success": True, "data": suggestions[:limit]}
        
    except Exception as e:
        current_app.logger.error(f"获取搜索建议错误: {str(e)}")
        return {"success": False, "message": f"获取建议失败: {str(e)}"}, 500


@search_bp.route('/history', methods=['GET'])
def get_search_history():
    """获取搜索历史（简化版）"""
    try:
        return {
            "success": True,
            "data": {
                "total": 0,
                "items": []
            }
        }
    except Exception as e:
        current_app.logger.error(f"获取搜索历史错误: {str(e)}")
        return {"success": False, "message": f"获取历史失败: {str(e)}"}, 500


@search_bp.route('/stats', methods=['GET'])
def get_search_stats():
    """获取搜索统计信息（简化版）"""
    try:
        return {
            "success": True,
            "data": {
                "total_searches": 0,
                "today_searches": 0,
                "avg_response_time": 0.0,
                "popular_queries": []
            }
        }
    except Exception as e:
        current_app.logger.error(f"获取搜索统计错误: {str(e)}")
        return {"success": False, "message": f"获取统计失败: {str(e)}"}, 500


# WebSocket事件处理（可选，用于实时搜索）
def register_socketio_events(socketio):
    """
    注册WebSocket事件处理器
    
    Args:
        socketio: SocketIO实例
    """
    
    @socketio.on('search_query')
    def handle_search_query(data):
        """
        处理实时搜索查询
        """
        try:
            query = data.get('query', '').strip()
            if not query:
                emit('search_error', {'message': '查询内容不能为空'})
                return
            
            # 发送搜索开始事件
            emit('search_started', {'query': query})
            
            # 这里可以调用搜索服务并通过WebSocket发送实时更新
            # 暂时发送一个模拟响应
            emit('search_result', {
                'query': query,
                'message': 'WebSocket搜索功能开发中...'
            })
            
        except Exception as e:
            current_app.logger.error(f"WebSocket搜索错误: {str(e)}")
            emit('search_error', {'message': f'搜索失败: {str(e)}'})


# 导出蓝图和WebSocket事件注册函数
__all__ = ['search_bp', 'register_socketio_events']
