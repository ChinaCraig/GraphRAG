"""
智能检索路由模块
处理搜索相关的HTTP请求，支持流式响应
只负责接口的入参和返参处理，不处理任何业务内容
"""

import json
import traceback
from flask import Blueprint, request, Response, current_app
from flask_socketio import emit
from app.service.search.SearchRouteService import SearchRouteService
from app.service.search.SearchFormatService import SearchFormatService
from app.service.search.SearchAnswerService import SearchAnswerService

# 创建蓝图
search_bp = Blueprint('search', __name__, url_prefix='/api/search')

# 初始化服务实例
route_service = SearchRouteService()
format_service = SearchFormatService()
answer_service = SearchAnswerService()


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
        # 第一阶段：理解过程（Query理解与路由）
        yield _format_sse_event("stage_update", {
            "stage": "understanding",
            "message": "🔍 正在理解您的查询...",
            "progress": 10
        })
        
        # 调用理解服务
        understanding_result = route_service.process_query(query, filters)
        
        yield _format_sse_event("stage_update", {
            "stage": "understanding", 
            "message": "✅ 查询理解完成",
            "progress": 30,
            "data": {
                "query_type": understanding_result.get("query_type"),
                "entities": understanding_result.get("entities"),
                "intent": understanding_result.get("intent")
            }
        })
        
        # 第二阶段：召回融合过程
        yield _format_sse_event("stage_update", {
            "stage": "retrieval",
            "message": "📚 正在搜索相关内容...",
            "progress": 50
        })
        
        # 调用召回服务
        retrieval_result = format_service.retrieve_and_rerank(understanding_result, filters)
        
        yield _format_sse_event("stage_update", {
            "stage": "retrieval",
            "message": f"✅ 内容召回完成，找到 {len(retrieval_result.get('candidates', []))} 个相关片段",
            "progress": 70,
            "data": {
                "total_found": retrieval_result.get("total_found", 0),
                "final_count": len(retrieval_result.get("candidates", []))
            }
        })
        
        # 第三阶段：答案生成过程
        yield _format_sse_event("stage_update", {
            "stage": "generation", 
            "message": "✍️ 正在生成答案...",
            "progress": 80
        })
        
        # 流式生成答案 - 边生成边推送
        for chunk in answer_service.generate_answer_stream(query, retrieval_result, understanding_result):
            if chunk.get("type") == "answer_chunk":
                # 推送文本增量
                yield _format_sse_event("text_delta", {
                    "content": chunk.get("content", ""),
                    "append": True
                })
            elif chunk.get("type") == "multimodal_content":
                # 推送多模态内容事件
                content_type = chunk.get("content_type")
                if content_type == "image":
                    yield _format_sse_event("render_image", chunk.get("data", {}))
                elif content_type == "table":
                    yield _format_sse_event("render_table", chunk.get("data", {}))
                elif content_type == "chart":
                    yield _format_sse_event("render_chart", chunk.get("data", {}))
            elif chunk.get("type") == "final_answer":
                # 推送最终完整答案（包含引用链接等）
                yield _format_sse_event("final_answer", {
                    "answer": chunk.get("content", {}),
                    "context": chunk.get("context", {}),
                    "metadata": chunk.get("metadata", {})
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
        # 理解阶段
        understanding_result = route_service.process_query(query, filters)
        
        # 召回阶段
        retrieval_result = format_service.retrieve_and_rerank(understanding_result, filters)
        
        # 答案生成阶段
        final_answer = answer_service.generate_answer_complete(query, retrieval_result, understanding_result)
        
        return {
            "success": True,
            "data": {
                "query": query,
                "understanding": understanding_result,
                "retrieval": {
                    "total_found": retrieval_result.get("total_found", 0),
                    "final_count": len(retrieval_result.get("candidates", [])),
                    "sources": retrieval_result.get("sources", [])
                },
                "answer": final_answer
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
    """
    获取搜索建议
    
    Query Parameters:
        q: 部分查询文本
        limit: 返回建议数量，默认10
    
    Response:
        {
            "success": true,
            "data": [
                {
                    "text": "建议文本",
                    "type": "entity|concept|question",
                    "score": 0.95
                }
            ]
        }
    """
    try:
        query = request.args.get('q', '').strip()
        limit = int(request.args.get('limit', 10))
        
        if not query:
            return {
                "success": True,
                "data": []
            }
        
        # 调用路由服务获取建议
        suggestions = route_service.get_search_suggestions(query, limit)
        
        return {
            "success": True,
            "data": suggestions
        }
        
    except Exception as e:
        current_app.logger.error(f"获取搜索建议错误: {str(e)}")
        return {
            "success": False,
            "message": f"获取建议失败: {str(e)}"
        }, 500


@search_bp.route('/history', methods=['GET'])
def get_search_history():
    """
    获取搜索历史
    
    Query Parameters:
        user_id: 用户ID
        limit: 返回历史数量，默认20
        offset: 偏移量，默认0
    
    Response:
        {
            "success": true,
            "data": {
                "total": 100,
                "items": [
                    {
                        "query": "查询文本",
                        "timestamp": "2024-01-01T00:00:00Z",
                        "result_count": 10
                    }
                ]
            }
        }
    """
    try:
        user_id = request.args.get('user_id', 'anonymous')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        # 调用路由服务获取历史
        history = route_service.get_search_history(user_id, limit, offset)
        
        return {
            "success": True,
            "data": history
        }
        
    except Exception as e:
        current_app.logger.error(f"获取搜索历史错误: {str(e)}")
        return {
            "success": False,
            "message": f"获取历史失败: {str(e)}"
        }, 500


@search_bp.route('/stats', methods=['GET'])
def get_search_stats():
    """
    获取搜索统计信息
    
    Response:
        {
            "success": true,
            "data": {
                "total_searches": 1000,
                "today_searches": 50,
                "avg_response_time": 2.5,
                "popular_queries": ["query1", "query2"]
            }
        }
    """
    try:
        # 调用路由服务获取统计
        stats = route_service.get_search_stats()
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        current_app.logger.error(f"获取搜索统计错误: {str(e)}")
        return {
            "success": False,
            "message": f"获取统计失败: {str(e)}"
        }, 500


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
