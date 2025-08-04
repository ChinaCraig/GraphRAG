#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件管理服务
"""

import os
import logging
import yaml
from pathlib import Path
from typing import Dict, Any
from werkzeug.utils import secure_filename
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils.MySQLManager import get_mysql_manager

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self.mysql_manager = None
        self._load_config()
        self._init_managers()
        self._init_upload_dirs()
    
    def _load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            self.upload_config = config.get('upload', {})
            logger.info("文件管理配置加载成功")
        except Exception as e:
            logger.error(f"加载文件管理配置失败: {str(e)}")
            raise
    
    def _init_managers(self):
        try:
            self.mysql_manager = get_mysql_manager()
            logger.info("数据库管理器初始化成功")
        except Exception as e:
            logger.error(f"初始化数据库管理器失败: {str(e)}")
            raise
    
    def _init_upload_dirs(self):
        try:
            upload_dirs = [
                self.upload_config.get('base_path', './upload'),
                self.upload_config.get('json_path', './upload/json'),
                self.upload_config.get('pdf_path', './upload/pdf'),
                self.upload_config.get('word_path', './upload/word'),
                self.upload_config.get('excel_path', './upload/excel'),
                self.upload_config.get('ppt_path', './upload/ppt'),
                self.upload_config.get('img_path', './upload/img'),
                self.upload_config.get('md_path', './upload/md'),
                self.upload_config.get('txt_path', './upload/txt')
            ]
            
            for dir_path in upload_dirs:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
            
            logger.info("上传目录初始化成功")
        except Exception as e:
            logger.error(f"初始化上传目录失败: {str(e)}")
            raise
    
    def upload_file(self, file, file_type: str = '') -> Dict[str, Any]:
        try:
            filename = secure_filename(file.filename)
            if not filename:
                return {'success': False, 'message': '无效的文件名', 'data': None}
            
            if not file_type:
                file_type = self._get_file_type(filename)
            
            save_path = self._get_save_path(filename, file_type)
            file.save(save_path)
            file_size = os.path.getsize(save_path)
            file_id = self._save_file_info(filename, str(save_path), file_type, file_size)
            
            return {
                'success': True,
                'message': '文件上传成功',
                'data': {
                    'file_id': file_id,
                    'filename': filename,
                    'file_path': str(save_path),
                    'file_type': file_type,
                    'file_size': file_size
                }
            }
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            return {'success': False, 'message': f'文件上传失败: {str(e)}', 'data': None}
    
    def _get_file_type(self, filename: str) -> str:
        extension = Path(filename).suffix.lower()
        type_mapping = {
            '.pdf': 'pdf', '.doc': 'word', '.docx': 'word',
            '.xls': 'excel', '.xlsx': 'excel', '.ppt': 'ppt', '.pptx': 'ppt',
            '.jpg': 'img', '.jpeg': 'img', '.png': 'img', '.gif': 'img',
            '.md': 'md', '.txt': 'txt'
        }
        return type_mapping.get(extension, 'unknown')
    
    def _get_save_path(self, filename: str, file_type: str) -> str:
        type_path_mapping = {
            'pdf': self.upload_config.get('pdf_path', './upload/pdf'),
            'word': self.upload_config.get('word_path', './upload/word'),
            'excel': self.upload_config.get('excel_path', './upload/excel'),
            'ppt': self.upload_config.get('ppt_path', './upload/ppt'),
            'img': self.upload_config.get('img_path', './upload/img'),
            'md': self.upload_config.get('md_path', './upload/md'),
            'txt': self.upload_config.get('txt_path', './upload/txt')
        }
        save_dir = type_path_mapping.get(file_type, self.upload_config.get('base_path', './upload'))
        return os.path.join(save_dir, filename)
    
    def _save_file_info(self, filename: str, file_path: str, file_type: str, file_size: int) -> int:
        sql = """
        INSERT INTO file_info (file_name, file_path, file_type, file_size, process_status)
        VALUES (%(filename)s, %(file_path)s, %(file_type)s, %(file_size)s, 'pending')
        """
        params = {'filename': filename, 'file_path': file_path, 'file_type': file_type, 'file_size': file_size}
        return self.mysql_manager.execute_insert(sql, params)
    
    def list_files(self, page: int = 1, size: int = 10, file_type: str = '', status: str = '') -> Dict[str, Any]:
        try:
            where_conditions = []
            params = {}
            
            if file_type:
                where_conditions.append("file_type = %(file_type)s")
                params['file_type'] = file_type
            
            if status:
                where_conditions.append("process_status = %(status)s")
                params['status'] = status
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            offset = (page - 1) * size
            
            count_sql = f"SELECT COUNT(*) as total FROM file_info WHERE {where_clause}"
            count_result = self.mysql_manager.execute_query(count_sql, params)
            total = count_result[0]['total'] if count_result else 0
            
            list_sql = f"""
            SELECT id, file_name, file_path, file_type, file_size, upload_time, process_status, json_path
            FROM file_info 
            WHERE {where_clause}
            ORDER BY upload_time DESC
            LIMIT %(size)s OFFSET %(offset)s
            """
            
            params.update({'size': size, 'offset': offset})
            files = self.mysql_manager.execute_query(list_sql, params)
            
            return {
                'success': True,
                'message': '获取文件列表成功',
                'data': {
                    'files': files,
                    'total': total,
                    'page': page,
                    'size': size,
                    'total_pages': (total + size - 1) // size
                }
            }
        except Exception as e:
            logger.error(f"获取文件列表失败: {str(e)}")
            return {'success': False, 'message': f'获取文件列表失败: {str(e)}', 'data': None}
    
    def get_file_info(self, file_id: int) -> Dict[str, Any]:
        try:
            sql = """
            SELECT id, file_name, file_path, file_type, file_size, upload_time, process_status, json_path
            FROM file_info 
            WHERE id = %(file_id)s
            """
            result = self.mysql_manager.execute_query(sql, {'file_id': file_id})
            
            if not result:
                return {'success': False, 'message': '文件不存在', 'data': None}
            
            return {'success': True, 'message': '获取文件信息成功', 'data': result[0]}
        except Exception as e:
            logger.error(f"获取文件信息失败: {str(e)}")
            return {'success': False, 'message': f'获取文件信息失败: {str(e)}', 'data': None}
    
    def delete_file(self, file_id: int) -> Dict[str, Any]:
        try:
            file_info = self.get_file_info(file_id)
            if not file_info['success']:
                return file_info
            
            file_data = file_info['data']
            file_path = file_data['file_path']
            
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"删除物理文件: {file_path}")
            
            if file_data.get('json_path') and os.path.exists(file_data['json_path']):
                os.remove(file_data['json_path'])
                logger.info(f"删除JSON文件: {file_data['json_path']}")
            
            sql = "DELETE FROM file_info WHERE id = %(file_id)s"
            self.mysql_manager.execute_update(sql, {'file_id': file_id})
            
            return {'success': True, 'message': '文件删除成功', 'data': None}
        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
            return {'success': False, 'message': f'删除文件失败: {str(e)}', 'data': None}
    
    def process_file(self, file_id: int) -> Dict[str, Any]:
        try:
            file_info = self.get_file_info(file_id)
            if not file_info['success']:
                return file_info
            
            file_data = file_info['data']
            file_path = file_data['file_path']
            file_type = file_data['file_type']
            
            self._update_process_status(file_id, 'processing')
            
            if file_type == 'pdf':
                result = self._process_pdf_file(file_id, file_path)
            else:
                result = {'success': False, 'message': f'不支持的文件类型: {file_type}', 'data': None}
            
            status = 'completed' if result['success'] else 'failed'
            self._update_process_status(file_id, status)
            
            return result
        except Exception as e:
            logger.error(f"处理文件失败: {str(e)}")
            self._update_process_status(file_id, 'failed')
            return {'success': False, 'message': f'处理文件失败: {str(e)}', 'data': None}
    
    def _process_pdf_file(self, file_id: int, file_path: str) -> Dict[str, Any]:
        try:
            return {
                'success': True,
                'message': 'PDF文件处理成功',
                'data': {'file_id': file_id, 'content_count': 0}
            }
        except Exception as e:
            logger.error(f"PDF文件处理失败: {str(e)}")
            return {'success': False, 'message': f'PDF文件处理失败: {str(e)}', 'data': None}
    
    def _update_process_status(self, file_id: int, status: str):
        sql = "UPDATE file_info SET process_status = %(status)s WHERE id = %(file_id)s"
        self.mysql_manager.execute_update(sql, {'file_id': file_id, 'status': status})
    
    def get_file_status(self, file_id: int) -> Dict[str, Any]:
        try:
            sql = """
            SELECT id, file_name, process_status, json_path, upload_time, updated_at
            FROM file_info 
            WHERE id = %(file_id)s
            """
            result = self.mysql_manager.execute_query(sql, {'file_id': file_id})
            
            if not result:
                return {'success': False, 'message': '文件不存在', 'data': None}
            
            return {'success': True, 'message': '获取文件状态成功', 'data': result[0]}
        except Exception as e:
            logger.error(f"获取文件状态失败: {str(e)}")
            return {'success': False, 'message': f'获取文件状态失败: {str(e)}', 'data': None} 