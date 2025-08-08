# -*- coding: utf-8 -*-
"""
WebSocket服务模块
用于实时推送文件处理进度更新
"""

from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import logging

# 创建logger
logger = logging.getLogger(__name__)

# 全局SocketIO实例
socketio = None

def init_socketio(app: Flask) -> SocketIO:
    """
    初始化SocketIO
    
    Args:
        app: Flask应用实例
        
    Returns:
        SocketIO: SocketIO实例
    """
    global socketio
    
    # 配置CORS以支持跨域
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        logger=True,
        engineio_logger=True
    )
    
    # 注册事件处理器
    register_handlers()
    
    logger.info("WebSocket服务初始化完成")
    return socketio

def register_handlers():
    """注册WebSocket事件处理器"""
    
    @socketio.on('connect')
    def on_connect(auth=None):
        """客户端连接事件"""
        logger.info(f"客户端连接: {request.sid}")
        emit('status', {'message': 'WebSocket连接成功'})
    
    @socketio.on('disconnect')
    def on_disconnect():
        """客户端断开连接事件"""
        logger.info(f"客户端断开连接: {request.sid}")
    
    @socketio.on('join_file_room')
    def on_join_file_room(data):
        """
        加入文件房间，监听特定文件的处理进度
        
        Args:
            data: {'file_id': int} - 文件ID
        """
        logger.info(f"收到加入房间请求: {data} 来自客户端 {request.sid}")
        file_id = data.get('file_id')
        if file_id:
            room = f"file_{file_id}"
            join_room(room)
            logger.info(f"✅ 客户端 {request.sid} 成功加入文件房间: {room}")
            emit('joined_room', {'file_id': file_id, 'room': room, 'message': f'成功加入房间 {room}'})
        else:
            logger.error(f"❌ 客户端 {request.sid} 加入房间失败: 缺少文件ID参数")
            emit('error', {'message': '缺少文件ID参数'})
    
    @socketio.on('leave_file_room')
    def on_leave_file_room(data):
        """
        离开文件房间
        
        Args:
            data: {'file_id': int} - 文件ID
        """
        file_id = data.get('file_id')
        if file_id:
            room = f"file_{file_id}"
            leave_room(room)
            logger.info(f"客户端 {request.sid} 离开文件房间: {room}")
            emit('left_room', {'file_id': file_id, 'room': room})

def send_file_progress(file_id: int, progress_data: dict):
    """
    向特定文件房间发送进度更新
    
    Args:
        file_id: 文件ID
        progress_data: 进度数据，格式如下:
        {
            'file_id': int,
            'status': str,
            'progress': int,  # 0-100
            'stage': str,
            'stage_name': str,
            'message': str,   # 可选的详细信息
            'timestamp': str  # ISO格式时间戳
        }
    """
    if not socketio:
        logger.warning("WebSocket服务未初始化，无法发送进度更新")
        return
    
    try:
        room = f"file_{file_id}"
        
        # 确保进度数据包含必要字段
        progress_update = {
            'file_id': file_id,
            'status': progress_data.get('status', 'unknown'),
            'progress': progress_data.get('progress', 0),
            'stage': progress_data.get('stage', 'unknown'),
            'stage_name': progress_data.get('stage_name', '未知状态'),
            'message': progress_data.get('message', ''),
            'timestamp': progress_data.get('timestamp')
        }
        
        # 发送到特定文件房间
        socketio.emit('file_progress', progress_update, room=room)
        
        logger.info(f"📊 发送文件进度更新到房间 {room}: {progress_update['stage_name']} ({progress_update['progress']}%)")
        logger.debug(f"完整进度数据: {progress_update}")
        
    except Exception as e:
        logger.error(f"发送文件进度更新失败: {str(e)}")

def send_file_completed(file_id: int, result_data: dict):
    """
    发送文件处理完成通知
    
    Args:
        file_id: 文件ID
        result_data: 结果数据
        {
            'file_id': int,
            'status': str,    # 'completed', 'failed' 等
            'success': bool,
            'message': str,
            'timestamp': str
        }
    """
    if not socketio:
        logger.warning("WebSocket服务未初始化，无法发送完成通知")
        return
    
    try:
        room = f"file_{file_id}"
        
        completion_data = {
            'file_id': file_id,
            'status': result_data.get('status', 'unknown'),
            'success': result_data.get('success', False),
            'message': result_data.get('message', ''),
            'timestamp': result_data.get('timestamp')
        }
        
        # 发送完成通知
        socketio.emit('file_completed', completion_data, room=room)
        
        logger.info(f"发送文件完成通知到房间 {room}: {completion_data['message']}")
        
    except Exception as e:
        logger.error(f"发送文件完成通知失败: {str(e)}")

def broadcast_file_list_update():
    """
    广播文件列表更新通知
    """
    if not socketio:
        return
    
    try:
        socketio.emit('file_list_update', {'message': '文件列表已更新'})
        logger.info("广播文件列表更新通知")
    except Exception as e:
        logger.error(f"广播文件列表更新失败: {str(e)}")

def get_socketio():
    """获取SocketIO实例"""
    return socketio
