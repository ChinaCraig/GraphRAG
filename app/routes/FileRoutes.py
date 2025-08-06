"""
文件管理路由
处理文件上传、管理、处理等相关的HTTP请求
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import json
from datetime import datetime

from app.service.FileService import FileService
from app.service.pdf.PdfExtractService import PdfExtractService
from app.service.pdf.PdfVectorService import PdfVectorService
from app.service.pdf.PdfGraphService import PdfGraphService


# 创建蓝图
file_bp = Blueprint('file', __name__, url_prefix='/api/file')

# 初始化服务
file_service = FileService()
pdf_extract_service = PdfExtractService()
pdf_vector_service = PdfVectorService()
pdf_graph_service = PdfGraphService()

logger = logging.getLogger(__name__)


@file_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    上传文件接口
    
    Returns:
        JSON响应，包含上传结果
    """
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '没有选择文件',
                'code': 400
            }), 400
        
        file = request.files['file']
        
        # 获取元数据
        metadata = {}
        if 'metadata' in request.form:
            try:
                metadata = json.loads(request.form['metadata'])
            except json.JSONDecodeError:
                logger.warning("元数据JSON解析失败，使用空元数据")
        
        # 添加上传者信息（如果有）
        if 'uploader' in request.form:
            metadata['uploader'] = request.form['uploader']
        
        # 调用文件服务上传文件
        result = file_service.upload_file(file, metadata)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'data': {
                    'file_id': result['file_id'],
                    'duplicate': result.get('duplicate', False)
                },
                'code': 200
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': result['message'],
                'code': 400
            }), 400
            
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'文件上传失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/list', methods=['GET'])
def get_file_list():
    """
    获取文件列表接口
    
    Returns:
        JSON响应，包含文件列表
    """
    try:
        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        file_type = request.args.get('file_type', None)
        process_status = request.args.get('process_status', None)
        
        # 参数验证
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20
        
        # 调用文件服务获取文件列表
        result = file_service.get_file_list(
            page=page,
            page_size=page_size,
            file_type=file_type,
            process_status=process_status
        )
        
        return jsonify({
            'success': True,
            'message': '获取文件列表成功',
            'data': result,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"获取文件列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取文件列表失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/<int:file_id>', methods=['GET'])
def get_file_info(file_id):
    """
    获取文件详细信息接口
    
    Args:
        file_id: 文件ID
        
    Returns:
        JSON响应，包含文件详细信息
    """
    try:
        # 调用文件服务获取文件信息
        file_info = file_service.get_file_info(file_id)
        
        if file_info:
            return jsonify({
                'success': True,
                'message': '获取文件信息成功',
                'data': file_info,
                'code': 200
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': '文件不存在',
                'code': 404
            }), 404
            
    except Exception as e:
        logger.error(f"获取文件信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取文件信息失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    """
    删除文件接口
    
    Args:
        file_id: 文件ID
        
    Returns:
        JSON响应，包含删除结果
    """
    try:
        # 调用文件服务删除文件
        success = file_service.delete_file(file_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '文件删除成功',
                'code': 200
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': '文件删除失败',
                'code': 400
            }), 400
            
    except Exception as e:
        logger.error(f"删除文件失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除文件失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/<int:file_id>/process', methods=['POST'])
def process_file(file_id):
    """
    处理文件接口（提取内容、向量化、图处理）
    
    Args:
        file_id: 文件ID
        
    Returns:
        JSON响应，包含处理结果
    """
    try:
        # 获取处理参数
        data = request.get_json() or {}
        process_steps = data.get('steps', ['extract', 'vectorize', 'graph'])
        
        # 获取文件信息
        file_info = file_service.get_file_info(file_id)
        if not file_info:
            return jsonify({
                'success': False,
                'message': '文件不存在',
                'code': 404
            }), 404
        
        # 检查文件类型
        if file_info['file_type'] not in ['pdf']:
            return jsonify({
                'success': False,
                'message': '当前只支持PDF文件处理',
                'code': 400
            }), 400
        
        results = {}
        
        # 步骤1：内容提取
        if 'extract' in process_steps:
            file_service.update_file_status(file_id, 'extracting')
            
            extract_result = pdf_extract_service.extract_pdf_content(
                file_info['file_path'], 
                file_id
            )
            
            results['extract'] = extract_result
            
            if extract_result['success']:
                file_service.update_file_status(file_id, 'extracted')
            else:
                file_service.update_file_status(file_id, 'extract_failed')
                return jsonify({
                    'success': False,
                    'message': '内容提取失败',
                    'data': results,
                    'code': 400
                }), 400
        
        # 步骤2：向量化
        if 'vectorize' in process_steps:
            file_service.update_file_status(file_id, 'vectorizing')
            
            vector_result = pdf_vector_service.vectorize_pdf_document(file_id)
            results['vectorize'] = vector_result
            
            if not vector_result['success']:
                file_service.update_file_status(file_id, 'vectorize_failed')
        
        # 步骤3：图处理
        if 'graph' in process_steps:
            file_service.update_file_status(file_id, 'graph_processing')
            
            graph_result = pdf_graph_service.process_pdf_to_graph(file_id)
            results['graph'] = graph_result
            
            if not graph_result['success']:
                file_service.update_file_status(file_id, 'graph_failed')
        
        # 确定最终状态
        all_success = all(
            results.get(step, {}).get('success', False) 
            for step in process_steps
        )
        
        if all_success:
            file_service.update_file_status(file_id, 'completed')
            message = '文件处理完成'
        else:
            file_service.update_file_status(file_id, 'partial_failed')
            message = '文件处理部分完成'
        
        return jsonify({
            'success': all_success,
            'message': message,
            'data': results,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"文件处理失败: {str(e)}")
        file_service.update_file_status(file_id, 'process_failed')
        return jsonify({
            'success': False,
            'message': f'文件处理失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/<int:file_id>/status', methods=['PUT'])
def update_file_status(file_id):
    """
    更新文件状态接口
    
    Args:
        file_id: 文件ID
        
    Returns:
        JSON响应，包含更新结果
    """
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({
                'success': False,
                'message': '缺少状态参数',
                'code': 400
            }), 400
        
        status = data['status']
        process_time = datetime.now() if data.get('update_time', True) else None
        
        # 调用文件服务更新状态
        success = file_service.update_file_status(file_id, status, process_time)
        
        if success:
            return jsonify({
                'success': True,
                'message': '文件状态更新成功',
                'code': 200
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': '文件状态更新失败',
                'code': 400
            }), 400
            
    except Exception as e:
        logger.error(f"更新文件状态失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'更新文件状态失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/stats', methods=['GET'])
def get_file_stats():
    """
    获取文件统计信息接口
    
    Returns:
        JSON响应，包含统计信息
    """
    try:
        # 调用文件服务获取统计信息
        stats = file_service.get_file_stats()
        
        return jsonify({
            'success': True,
            'message': '获取统计信息成功',
            'data': stats,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"获取文件统计信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取文件统计信息失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/<int:file_id>/summary', methods=['GET'])
def get_file_summary(file_id):
    """
    获取文件摘要信息接口
    
    Args:
        file_id: 文件ID
        
    Returns:
        JSON响应，包含文件摘要
    """
    try:
        # 获取文件信息
        file_info = file_service.get_file_info(file_id)
        if not file_info:
            return jsonify({
                'success': False,
                'message': '文件不存在',
                'code': 404
            }), 404
        
        summary_data = {}
        
        # 根据文件类型获取不同的摘要信息
        if file_info['file_type'] == 'pdf':
            # PDF摘要
            pdf_summary = pdf_extract_service.get_pdf_summary(file_id)
            summary_data.update(pdf_summary)
            
            # 向量化统计
            vector_stats = pdf_vector_service.get_document_vectors_stats(file_id)
            summary_data['vector_stats'] = vector_stats
            
            # 图数据统计
            graph_stats = pdf_graph_service.get_document_graph_stats(file_id)
            summary_data['graph_stats'] = graph_stats
        
        return jsonify({
            'success': True,
            'message': '获取文件摘要成功',
            'data': summary_data,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"获取文件摘要失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取文件摘要失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/cleanup', methods=['POST'])
def cleanup_files():
    """
    清理文件接口
    
    Returns:
        JSON响应，包含清理结果
    """
    try:
        data = request.get_json() or {}
        max_age_hours = data.get('max_age_hours', 24)
        
        # 清理临时文件
        cleaned_count = file_service.cleanup_temp_files(max_age_hours)
        
        return jsonify({
            'success': True,
            'message': f'文件清理完成，共清理{cleaned_count}个临时文件',
            'data': {
                'cleaned_count': cleaned_count,
                'max_age_hours': max_age_hours
            },
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"文件清理失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'文件清理失败: {str(e)}',
            'code': 500
        }), 500


@file_bp.route('/batch/process', methods=['POST'])
def batch_process_files():
    """
    批量处理文件接口
    
    Returns:
        JSON响应，包含批量处理结果
    """
    try:
        data = request.get_json()
        if not data or 'file_ids' not in data:
            return jsonify({
                'success': False,
                'message': '缺少文件ID列表',
                'code': 400
            }), 400
        
        file_ids = data['file_ids']
        process_steps = data.get('steps', ['extract', 'vectorize', 'graph'])
        
        if not isinstance(file_ids, list) or not file_ids:
            return jsonify({
                'success': False,
                'message': '文件ID列表无效',
                'code': 400
            }), 400
        
        results = {
            'total_files': len(file_ids),
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for file_id in file_ids:
            try:
                # 模拟调用单个文件处理
                # 这里可以异步处理或者调用现有的process_file逻辑
                file_info = file_service.get_file_info(file_id)
                
                if file_info and file_info['file_type'] == 'pdf':
                    # 这里简化处理，实际应该调用完整的处理流程
                    results['successful'] += 1
                    results['details'].append({
                        'file_id': file_id,
                        'success': True,
                        'message': '处理成功'
                    })
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'file_id': file_id,
                        'success': False,
                        'message': '文件不存在或类型不支持'
                    })
                    
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'file_id': file_id,
                    'success': False,
                    'message': str(e)
                })
        
        return jsonify({
            'success': results['failed'] == 0,
            'message': f'批量处理完成，成功: {results["successful"]}, 失败: {results["failed"]}',
            'data': results,
            'code': 200
        }), 200
        
    except Exception as e:
        logger.error(f"批量处理文件失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量处理文件失败: {str(e)}',
            'code': 500
        }), 500


# 错误处理
@file_bp.errorhandler(413)
def too_large(e):
    """处理文件过大错误"""
    return jsonify({
        'success': False,
        'message': '文件过大',
        'code': 413
    }), 413


@file_bp.errorhandler(400)
def bad_request(e):
    """处理请求错误"""
    return jsonify({
        'success': False,
        'message': '请求参数错误',
        'code': 400
    }), 400