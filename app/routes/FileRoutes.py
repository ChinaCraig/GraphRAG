#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件管理路由
处理文件管理相关的路由信息，只做入参和返参的处理
"""

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import logging
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.service.FileService import FileService

logger = logging.getLogger(__name__)

# 创建蓝图
file_routes = Blueprint('file', __name__, url_prefix='/api/file')

# 文件服务实例
file_service = FileService()

@file_routes.route('/upload', methods=['POST'])
def upload_file():
    """
    文件上传接口
    
    入参:
        - file: 上传的文件
        - file_type: 文件类型（可选）
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 文件信息
    """
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '没有上传文件',
                'data': None
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '没有选择文件',
                'data': None
            }), 400
        
        # 获取文件类型（可选）
        file_type = request.form.get('file_type', '')
        
        # 调用服务层处理
        result = file_service.upload_file(file, file_type)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'文件上传失败: {str(e)}',
            'data': None
        }), 500

@file_routes.route('/list', methods=['GET'])
def list_files():
    """
    获取文件列表接口
    
    入参:
        - page: 页码（可选，默认1）
        - size: 每页大小（可选，默认10）
        - file_type: 文件类型过滤（可选）
        - status: 处理状态过滤（可选）
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 文件列表
    """
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        file_type = request.args.get('file_type', '')
        status = request.args.get('status', '')
        
        # 调用服务层处理
        result = file_service.list_files(page, size, file_type, status)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取文件列表失败: {str(e)}',
            'data': None
        }), 500

@file_routes.route('/<int:file_id>', methods=['GET'])
def get_file_info(file_id):
    """
    获取文件信息接口
    
    入参:
        - file_id: 文件ID
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 文件信息
    """
    try:
        # 调用服务层处理
        result = file_service.get_file_info(file_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取文件信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取文件信息失败: {str(e)}',
            'data': None
        }), 500

@file_routes.route('/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    """
    删除文件接口
    
    入参:
        - file_id: 文件ID
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: None
    """
    try:
        # 调用服务层处理
        result = file_service.delete_file(file_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"删除文件失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除文件失败: {str(e)}',
            'data': None
        }), 500

@file_routes.route('/<int:file_id>/process', methods=['POST'])
def process_file(file_id):
    """
    处理文件接口
    
    入参:
        - file_id: 文件ID
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 处理结果
    """
    try:
        # 调用服务层处理
        result = file_service.process_file(file_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"处理文件失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'处理文件失败: {str(e)}',
            'data': None
        }), 500

@file_routes.route('/<int:file_id>/status', methods=['GET'])
def get_file_status(file_id):
    """
    获取文件处理状态接口
    
    入参:
        - file_id: 文件ID
    
    返参:
        - success: 是否成功
        - message: 消息
        - data: 处理状态
    """
    try:
        # 调用服务层处理
        result = file_service.get_file_status(file_id)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"获取文件状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取文件状态失败: {str(e)}',
            'data': None
        }), 500 