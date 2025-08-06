"""
文件管理服务
负责文件的上传、处理、存储和管理功能
"""

import os
import hashlib
import logging
import yaml
from typing import Optional, Dict, Any, List
from datetime import datetime
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
import json

from utils.MySQLManager import MySQLManager


class FileService:
    """文件管理服务类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化文件服务
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载配置
        self._load_config()
        
        # 初始化数据库管理器
        self.mysql_manager = MySQLManager()
        
        # 创建必要的目录
        self._create_directories()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.file_config = config['file']
                self.logger.info("文件服务配置加载成功")
        except Exception as e:
            self.logger.error(f"加载文件服务配置失败: {str(e)}")
            raise
    
    def _create_directories(self) -> None:
        """创建必要的目录"""
        directories = [
            self.file_config['upload_folder'],
            self.file_config['processed_folder'],
            self.file_config['temp_folder']
        ]
        
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                self.logger.info(f"创建目录: {directory}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """
        计算文件哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件的SHA256哈希值
        """
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.error(f"计算文件哈希失败: {str(e)}")
            return ""
    
    def _is_allowed_file(self, filename: str) -> bool:
        """
        检查文件类型是否允许
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 是否允许上传
        """
        if '.' not in filename:
            return False
        
        file_ext = filename.rsplit('.', 1)[1].lower()
        return file_ext in self.file_config['allowed_extensions']
    
    def upload_file(self, file: FileStorage, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        上传文件
        
        Args:
            file: 上传的文件对象
            metadata: 文件元数据
            
        Returns:
            Dict[str, Any]: 上传结果
        """
        try:
            # 检查文件是否存在
            if not file or file.filename == '':
                return {
                    'success': False,
                    'message': '未选择文件',
                    'file_id': None
                }
            
            # 检查文件类型
            if not self._is_allowed_file(file.filename):
                return {
                    'success': False,
                    'message': f'不支持的文件类型',
                    'file_id': None
                }
            
            # 检查文件大小
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > self.file_config['max_file_size']:
                return {
                    'success': False,
                    'message': f'文件大小超过限制 ({self.file_config["max_file_size"]} bytes)',
                    'file_id': None
                }
            
            # 生成安全的文件名
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()
            
            # 生成唯一文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{filename}"
            
            # 保存文件
            file_path = os.path.join(self.file_config['upload_folder'], unique_filename)
            file.save(file_path)
            
            # 计算文件哈希
            content_hash = self._get_file_hash(file_path)
            
            # 检查是否已存在相同内容的文件
            existing_file = self._check_duplicate_file(content_hash)
            if existing_file:
                # 删除刚保存的重复文件
                os.remove(file_path)
                return {
                    'success': True,
                    'message': '文件已存在',
                    'file_id': existing_file['id'],
                    'duplicate': True
                }
            
            # 保存文件信息到数据库
            file_data = {
                'filename': filename,
                'file_path': file_path,
                'file_type': file_ext,
                'file_size': file_size,
                'upload_time': datetime.now(),
                'process_status': 'pending',
                'content_hash': content_hash,
                'metadata': json.dumps(metadata or {}, ensure_ascii=False)
            }
            
            success = self.mysql_manager.insert_data('documents', file_data)
            
            if success:
                # 获取插入的文件ID
                file_info = self._get_file_by_hash(content_hash)
                file_id = file_info['id'] if file_info else None
                
                self.logger.info(f"文件上传成功: {filename}, ID: {file_id}")
                return {
                    'success': True,
                    'message': '文件上传成功',
                    'file_id': file_id,
                    'duplicate': False
                }
            else:
                # 删除已保存的文件
                os.remove(file_path)
                return {
                    'success': False,
                    'message': '保存文件信息失败',
                    'file_id': None
                }
                
        except Exception as e:
            self.logger.error(f"文件上传失败: {str(e)}")
            return {
                'success': False,
                'message': f'文件上传失败: {str(e)}',
                'file_id': None
            }
    
    def _check_duplicate_file(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """
        检查重复文件
        
        Args:
            content_hash: 文件内容哈希
            
        Returns:
            Optional[Dict[str, Any]]: 重复文件信息，不存在返回None
        """
        try:
            query = "SELECT * FROM documents WHERE content_hash = :hash LIMIT 1"
            result = self.mysql_manager.execute_query(query, {'hash': content_hash})
            return result[0] if result else None
        except Exception as e:
            self.logger.error(f"检查重复文件失败: {str(e)}")
            return None
    
    def _get_file_by_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """
        根据哈希获取文件信息
        
        Args:
            content_hash: 文件内容哈希
            
        Returns:
            Optional[Dict[str, Any]]: 文件信息
        """
        try:
            query = "SELECT * FROM documents WHERE content_hash = :hash LIMIT 1"
            result = self.mysql_manager.execute_query(query, {'hash': content_hash})
            return result[0] if result else None
        except Exception as e:
            self.logger.error(f"获取文件信息失败: {str(e)}")
            return None
    
    def get_file_info(self, file_id: int) -> Optional[Dict[str, Any]]:
        """
        获取文件信息
        
        Args:
            file_id: 文件ID
            
        Returns:
            Optional[Dict[str, Any]]: 文件信息
        """
        try:
            query = "SELECT * FROM documents WHERE id = :file_id"
            result = self.mysql_manager.execute_query(query, {'file_id': file_id})
            
            if result:
                file_info = result[0]
                # 解析元数据
                if file_info.get('metadata'):
                    file_info['metadata'] = json.loads(file_info['metadata'])
                return file_info
            return None
            
        except Exception as e:
            self.logger.error(f"获取文件信息失败: {str(e)}")
            return None
    
    def get_file_list(self, page: int = 1, page_size: int = 20, 
                     file_type: Optional[str] = None, 
                     process_status: Optional[str] = None) -> Dict[str, Any]:
        """
        获取文件列表
        
        Args:
            page: 页码
            page_size: 每页数量
            file_type: 文件类型过滤
            process_status: 处理状态过滤
            
        Returns:
            Dict[str, Any]: 文件列表和分页信息
        """
        try:
            # 构建查询条件
            where_conditions = []
            params = {}
            
            if file_type:
                where_conditions.append("file_type = :file_type")
                params['file_type'] = file_type
            
            if process_status:
                where_conditions.append("process_status = :process_status")
                params['process_status'] = process_status
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # 计算总数
            count_query = f"SELECT COUNT(*) as total FROM documents WHERE {where_clause}"
            count_result = self.mysql_manager.execute_query(count_query, params)
            total = count_result[0]['total'] if count_result else 0
            
            # 计算偏移量
            offset = (page - 1) * page_size
            params['limit'] = page_size
            params['offset'] = offset
            
            # 查询文件列表
            list_query = f"""
            SELECT id, filename, file_type, file_size, upload_time, process_status
            FROM documents 
            WHERE {where_clause}
            ORDER BY upload_time DESC
            LIMIT :limit OFFSET :offset
            """
            
            files = self.mysql_manager.execute_query(list_query, params)
            
            return {
                'files': files,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            self.logger.error(f"获取文件列表失败: {str(e)}")
            return {
                'files': [],
                'total': 0,
                'page': page,
                'page_size': page_size,
                'total_pages': 0
            }
    
    def update_file_status(self, file_id: int, status: str, process_time: Optional[datetime] = None) -> bool:
        """
        更新文件处理状态
        
        Args:
            file_id: 文件ID
            status: 新状态
            process_time: 处理时间
            
        Returns:
            bool: 更新成功返回True
        """
        try:
            update_data = {'process_status': status}
            if process_time:
                update_data['process_time'] = process_time
            else:
                update_data['process_time'] = datetime.now()
            
            success = self.mysql_manager.update_data(
                'documents',
                update_data,
                'id = :file_id',
                {'file_id': file_id}
            )
            
            if success:
                self.logger.info(f"文件状态更新成功，ID: {file_id}, 状态: {status}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"更新文件状态失败: {str(e)}")
            return False
    
    def delete_file(self, file_id: int) -> bool:
        """
        删除文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            # 获取文件信息
            file_info = self.get_file_info(file_id)
            if not file_info:
                return False
            
            # 删除物理文件
            if os.path.exists(file_info['file_path']):
                os.remove(file_info['file_path'])
                self.logger.info(f"删除物理文件: {file_info['file_path']}")
            
            # 删除数据库记录
            success = self.mysql_manager.delete_data(
                'documents',
                'id = :file_id',
                {'file_id': file_id}
            )
            
            if success:
                self.logger.info(f"文件删除成功，ID: {file_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"删除文件失败: {str(e)}")
            return False
    
    def get_file_stats(self) -> Dict[str, Any]:
        """
        获取文件统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            queries = {
                'total_files': "SELECT COUNT(*) as count FROM documents",
                'total_size': "SELECT SUM(file_size) as size FROM documents",
                'by_type': """
                    SELECT file_type, COUNT(*) as count, SUM(file_size) as size
                    FROM documents 
                    GROUP BY file_type
                """,
                'by_status': """
                    SELECT process_status, COUNT(*) as count
                    FROM documents 
                    GROUP BY process_status
                """
            }
            
            stats = {}
            for key, query in queries.items():
                result = self.mysql_manager.execute_query(query)
                if key in ['total_files', 'total_size']:
                    stats[key] = result[0][list(result[0].keys())[0]] if result else 0
                else:
                    stats[key] = result
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取文件统计信息失败: {str(e)}")
            return {}
    
    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        清理临时文件
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            int: 清理的文件数量
        """
        try:
            temp_folder = self.file_config['temp_folder']
            if not os.path.exists(temp_folder):
                return 0
            
            current_time = datetime.now()
            max_age_seconds = max_age_hours * 3600
            cleaned_count = 0
            
            for filename in os.listdir(temp_folder):
                file_path = os.path.join(temp_folder, filename)
                if os.path.isfile(file_path):
                    file_age = current_time.timestamp() - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        cleaned_count += 1
                        self.logger.info(f"清理临时文件: {filename}")
            
            self.logger.info(f"临时文件清理完成，共清理{cleaned_count}个文件")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"清理临时文件失败: {str(e)}")
            return 0