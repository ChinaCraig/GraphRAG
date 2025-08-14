"""
文件管理服务
负责文件的上传、处理、存储和管理功能
"""

import os
import hashlib
import logging
import yaml
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
import re
import urllib.parse
import json
import threading

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

    def _safe_filename(self, filename: str) -> str:
        """
        生成安全的文件名，支持中文字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 安全的文件名
        """
        if not filename:
            return "unknown"
        
        # 移除路径分隔符和其他危险字符，但保留中文字符
        dangerous_chars = r'[<>:"/\\|?*\x00-\x1f]'
        safe_name = re.sub(dangerous_chars, '_', filename)
        
        # 移除开头和结尾的空格、点号
        safe_name = safe_name.strip(' .')
        
        # 如果文件名为空或只有扩展名，使用默认名称
        if not safe_name or safe_name.startswith('.'):
            safe_name = f"file_{safe_name}" if safe_name.startswith('.') else "unknown_file"
        
        # 限制文件名长度（保留扩展名）
        if len(safe_name) > 200:
            name_part, ext_part = os.path.splitext(safe_name)
            max_name_len = 200 - len(ext_part)
            safe_name = name_part[:max_name_len] + ext_part
        
        return safe_name
    
    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.file_config = config['file']
                
                # 🔧 修复：将相对路径转换为绝对路径
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                
                # 转换上传目录路径
                upload_folder = self.file_config['upload_folder']
                if not os.path.isabs(upload_folder):
                    self.file_config['upload_folder'] = os.path.abspath(os.path.join(project_root, upload_folder))
                
                # 转换临时目录路径
                temp_folder = self.file_config['temp_folder']
                if not os.path.isabs(temp_folder):
                    self.file_config['temp_folder'] = os.path.abspath(os.path.join(project_root, temp_folder))
                
                self.logger.info(f"文件服务配置加载成功")
                self.logger.info(f"上传目录: {self.file_config['upload_folder']}")
                self.logger.info(f"临时目录: {self.file_config['temp_folder']}")
                
        except Exception as e:
            self.logger.error(f"加载文件服务配置失败: {str(e)}")
            raise
    
    def _create_directories(self) -> None:
        """创建必要的目录"""
        directories = [
            self.file_config['upload_folder'],
            self.file_config['temp_folder']
        ]
        
        # 添加文件类型子目录
        upload_folder = self.file_config['upload_folder']
        file_type_dirs = ['pdf', 'doc', 'docx', 'xlsx', 'xls', 'pptx', 'ppt', 'txt', 'md', 'images']
        for file_type in file_type_dirs:
            directories.append(os.path.join(upload_folder, file_type))
        
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
            # 添加详细的调试信息
            self.logger.info(f"=== 文件上传开始 ===")
            self.logger.info(f"接收到的文件对象: {type(file)}")
            self.logger.info(f"file.filename: '{file.filename}' (类型: {type(file.filename)})")
            self.logger.info(f"file.filename原始字节: {repr(file.filename.encode('utf-8')) if file.filename else 'None'}")
            
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
                    'message': f'不支持的文件类型: {file.filename}',
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
            
            # 保存原始文件名（用于显示）
            original_filename = file.filename
            
            # 直接从原始文件名获取扩展名
            if '.' in original_filename:
                file_ext = original_filename.rsplit('.', 1)[1].lower()
            else:
                file_ext = ''
            
            # 记录调试信息
            self.logger.info(f"上传文件调试信息 - 原始文件名: {original_filename}, 扩展名: {file_ext}")
            
            # 生成唯一的物理文件名
            timestamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
            # 对于磁盘存储，使用更安全的文件名（英文+数字）
            import hashlib
            name_hash = hashlib.md5(original_filename.encode('utf-8')).hexdigest()[:8]
            unique_filename = f"{timestamp}_{name_hash}.{file_ext}" if file_ext else f"{timestamp}_{name_hash}"
            
            # 根据文件类型选择子目录
            if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                sub_dir = 'images'
            else:
                sub_dir = file_ext
            
            # 保存文件到相应的子目录
            file_dir = os.path.join(self.file_config['upload_folder'], sub_dir)
            file_path = os.path.join(file_dir, unique_filename)
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
            
            # 保存文件信息到数据库（filename字段保存原始文件名用于显示）
            file_data = {
                'filename': original_filename,  # 保存原始文件名（包含中文）
                'file_path': file_path,
                'file_type': file_ext,
                'file_size': file_size,
                'upload_time': datetime.now(timezone(timedelta(hours=8))),
                'process_status': 'pending',
                'content_hash': content_hash,
                'metadata': json.dumps(metadata or {}, ensure_ascii=False)
            }
            
            # 调试：数据库存储前的数据
            self.logger.info(f"准备存储到数据库的数据: filename='{file_data['filename']}', file_path='{file_data['file_path']}'")
            
            success = self.mysql_manager.insert_data('documents', file_data)
            
            if success:
                # 获取插入的文件ID
                file_info = self._get_file_by_hash(content_hash)
                file_id = file_info['id'] if file_info else None
                
                self.logger.info(f"文件上传成功: {original_filename}, ID: {file_id}")
                
                # 异步启动处理流程
                if file_ext == 'pdf':  # 只对PDF文件进行后续处理
                    threading.Thread(target=self._async_process_file, args=(file_id, file_path)).start()
                
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
                     process_status: Optional[str] = None,
                     filename: Optional[str] = None) -> Dict[str, Any]:
        """
        获取文件列表
        
        Args:
            page: 页码
            page_size: 每页数量
            file_type: 文件类型过滤
            process_status: 处理状态过滤
            filename: 文件名模糊搜索（支持文件名、元数据等字段）
            
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
            
            # 添加文件名模糊搜索（支持多字段搜索）
            if filename:
                # 支持文件名、元数据等字段的模糊搜索
                search_conditions = [
                    "filename LIKE :filename_search",
                    "metadata LIKE :filename_search"
                ]
                where_conditions.append(f"({' OR '.join(search_conditions)})")
                params['filename_search'] = f"%{filename}%"
            
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
            SELECT id, filename, file_type, file_size, upload_time, process_status, process_time
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
    
    def update_file_status(self, file_id: int, status: str, process_time: Optional[datetime] = None, send_websocket: bool = True) -> bool:
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
                update_data['process_time'] = datetime.now(timezone(timedelta(hours=8)))
            
            success = self.mysql_manager.update_data(
                'documents',
                update_data,
                'id = :file_id',
                {'file_id': file_id}
            )
            
            if success:
                self.logger.info(f"文件状态更新成功，ID: {file_id}, 状态: {status}")
                
                # 发送WebSocket进度更新
                if send_websocket:
                    self._send_progress_update(file_id, status, process_time)
            
            return success
            
        except Exception as e:
            self.logger.error(f"更新文件状态失败: {str(e)}")
            return False
    
    def _send_progress_update(self, file_id: int, status: str, process_time: Optional[datetime] = None):
        """
        发送WebSocket进度更新
        
        Args:
            file_id: 文件ID
            status: 处理状态
            process_time: 处理时间
        """
        try:
            from app.utils.websocket import send_file_progress
            
            # 计算进度数据
            progress_data = self._calculate_progress(status)
            
            # 添加时间戳
            if process_time:
                progress_data['timestamp'] = process_time.isoformat()
            else:
                progress_data['timestamp'] = datetime.now(timezone(timedelta(hours=8))).isoformat()
            
            # 发送WebSocket消息
            send_file_progress(file_id, progress_data)
            
        except Exception as e:
            self.logger.error(f"发送WebSocket进度更新失败: {str(e)}")
    
    def _calculate_progress(self, status: str) -> Dict[str, Any]:
        """
        根据状态计算进度
        
        Args:
            status: 处理状态
            
        Returns:
            Dict[str, Any]: 进度信息
        """
        progress_map = {
            'pending': {'progress': 10, 'stage': 'uploaded', 'stage_name': '文件已上传'},
            'extracting': {'progress': 25, 'stage': 'extracting', 'stage_name': '内容提取中'},
            'extracted': {'progress': 40, 'stage': 'extracted', 'stage_name': '内容提取完成'},
            'vectorizing': {'progress': 50, 'stage': 'vectorizing', 'stage_name': '向量化处理中'},
            'vectorized': {'progress': 60, 'stage': 'vectorized', 'stage_name': '向量化完成'},
            'bm25_processing': {'progress': 65, 'stage': 'bm25_processing', 'stage_name': 'BM25倒排处理中'},
            'bm25_completed': {'progress': 70, 'stage': 'bm25_completed', 'stage_name': 'BM25倒排完成'},
            'graph_processing': {'progress': 80, 'stage': 'graph_processing', 'stage_name': '知识图谱构建中'},
            'graph_completed': {'progress': 85, 'stage': 'graph_completed', 'stage_name': '知识图谱构建完成'},
            'mysql_processing': {'progress': 95, 'stage': 'mysql_processing', 'stage_name': 'MySQL保存中'},
            'completed': {'progress': 100, 'stage': 'completed', 'stage_name': '处理完成'},
            'extract_failed': {'progress': 40, 'stage': 'extract_failed', 'stage_name': '内容提取失败'},
            'vectorize_failed': {'progress': 60, 'stage': 'vectorize_failed', 'stage_name': '向量化失败'},
            'bm25_failed': {'progress': 70, 'stage': 'bm25_failed', 'stage_name': 'BM25倒排失败'},
            'graph_failed': {'progress': 85, 'stage': 'graph_failed', 'stage_name': '知识图谱构建失败'},
            'mysql_failed': {'progress': 95, 'stage': 'mysql_failed', 'stage_name': 'MySQL保存失败'},
            'process_failed': {'progress': 0, 'stage': 'process_failed', 'stage_name': '处理失败'}
        }
        
        return progress_map.get(status, {'progress': 0, 'stage': 'unknown', 'stage_name': '未知状态'})
    
    def _delete_processed_files(self, file_id: int, original_filename: str) -> Dict[str, bool]:
        """
        删除处理过程中生成的文件
        
        Args:
            file_id: 文件ID
            original_filename: 原始文件名
            
        Returns:
            Dict[str, bool]: 各类文件删除结果
        """
        results = {
            'json_files': False,
            'bm25_files': False,
            'figure_files': False
        }
        
        try:
            upload_folder = self.file_config['upload_folder']
            
            # 1. 删除JSON文件
            json_dir = os.path.join(upload_folder, 'json')
            if os.path.exists(json_dir):
                # 可能的JSON文件名模式
                base_name = os.path.splitext(original_filename)[0]
                json_patterns = [
                    f"{base_name}_doc_{file_id}.json",
                    f"*_doc_{file_id}.json"
                ]
                
                json_deleted = 0
                for pattern in json_patterns:
                    if '*' in pattern:
                        import glob
                        matching_files = glob.glob(os.path.join(json_dir, pattern))
                        for file_path in matching_files:
                            try:
                                os.remove(file_path)
                                json_deleted += 1
                                self.logger.info(f"删除JSON文件: {file_path}")
                            except Exception as e:
                                self.logger.warning(f"删除JSON文件失败: {file_path}, 错误: {e}")
                    else:
                        file_path = os.path.join(json_dir, pattern)
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                json_deleted += 1
                                self.logger.info(f"删除JSON文件: {file_path}")
                            except Exception as e:
                                self.logger.warning(f"删除JSON文件失败: {file_path}, 错误: {e}")
                
                results['json_files'] = json_deleted > 0
            
            # 2. 删除BM25索引文件
            bm25_dir = os.path.join(upload_folder, 'bm25')
            if os.path.exists(bm25_dir):
                import glob
                # BM25文件名模式: bm25_*_{file_id}.json
                bm25_patterns = [
                    f"bm25_*_{file_id}.json",
                    f"bm25_combined_{file_id}.json",
                    f"bm25_sections_{file_id}.json", 
                    f"bm25_fragments_{file_id}.json"
                ]
                
                bm25_deleted = 0
                for pattern in bm25_patterns:
                    matching_files = glob.glob(os.path.join(bm25_dir, pattern))
                    for file_path in matching_files:
                        try:
                            os.remove(file_path)
                            bm25_deleted += 1
                            self.logger.info(f"删除BM25文件: {file_path}")
                        except Exception as e:
                            self.logger.warning(f"删除BM25文件失败: {file_path}, 错误: {e}")
                
                results['bm25_files'] = bm25_deleted > 0
            
            # 3. 删除提取的图片文件
            # 修复：figures目录在项目根目录，不在upload目录下
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            figures_dir = os.path.join(project_root, 'figures')
            
            figure_deleted = 0
            
            # 方法1：通过MySQL figures表精确查找图片路径
            try:
                # 查询该文档相关的所有图片路径
                query = """
                SELECT DISTINCT f.image_path 
                FROM figures f 
                JOIN sections s ON f.section_id = s.section_id 
                WHERE s.document_id = :doc_id AND f.image_path IS NOT NULL AND f.image_path != ''
                """
                
                figure_records = self.mysql_manager.fetch_all(query, {'doc_id': file_id})
                
                for record in figure_records:
                    image_path = record.get('image_path', '')
                    if image_path:
                        # 构建完整路径
                        if image_path.startswith('figures/'):
                            full_path = os.path.join(project_root, image_path)
                        else:
                            # 如果路径不以figures/开头，假设它是相对于figures目录的
                            full_path = os.path.join(figures_dir, os.path.basename(image_path))
                        
                        if os.path.exists(full_path):
                            try:
                                os.remove(full_path)
                                figure_deleted += 1
                                self.logger.info(f"通过MySQL记录删除图片文件: {full_path}")
                            except Exception as e:
                                self.logger.warning(f"删除图片文件失败: {full_path}, 错误: {e}")
                
            except Exception as e:
                self.logger.warning(f"通过MySQL查找图片文件失败: {e}")
            
            # 方法2：模式匹配删除（作为备用方案）
            if os.path.exists(figures_dir):
                import glob
                # 基于文件名模式的删除（作为备用方案）
                figure_patterns = [
                    f"*{file_id}*",           # 直接包含ID
                    f"*_{file_id}_*",         # ID前后有下划线
                    f"figure-{file_id}-*",    # figure-ID-序号 格式
                    f"*doc_{file_id}*"        # 包含doc_ID的格式
                ]
                
                pattern_deleted = 0
                for pattern in figure_patterns:
                    matching_files = glob.glob(os.path.join(figures_dir, pattern))
                    for file_path in matching_files:
                        try:
                            os.remove(file_path)
                            pattern_deleted += 1
                            self.logger.info(f"通过模式匹配删除图片文件: {file_path}")
                        except Exception as e:
                            self.logger.warning(f"删除图片文件失败: {file_path}, 错误: {e}")
                
                figure_deleted += pattern_deleted
                
            results['figure_files'] = figure_deleted > 0
            self.logger.info(f"figures目录路径: {figures_dir}, 删除图片总数: {figure_deleted}")
            
            self.logger.info(f"文件清理完成，文档ID: {file_id}, 结果: {results}")
            
        except Exception as e:
            self.logger.error(f"清理处理文件时发生错误: {str(e)}")
        
        return results
    
    def delete_file(self, file_id: int) -> bool:
        """
        完整删除文件及其所有相关数据
        
        Args:
            file_id: 文件ID
            
        Returns:
            bool: 删除成功返回True
        """
        try:
            # 获取文件信息
            file_info = self.get_file_info(file_id)
            if not file_info:
                self.logger.warning(f"文件不存在，ID: {file_id}")
                return False
            
            self.logger.info(f"开始删除文件：{file_info['filename']} (ID: {file_id})")
            
            # 记录删除过程中的错误，但不中断删除过程
            deletion_errors = []
            success_count = 0
            total_operations = 7
            
            # 1. 删除Milvus向量数据
            try:
                from utils.MilvusManager import MilvusManager
                milvus_manager = MilvusManager()
                if milvus_manager.delete_by_document_id(file_id):
                    success_count += 1
                    self.logger.info(f"✓ Milvus向量数据删除成功")
                else:
                    deletion_errors.append("Milvus向量数据删除失败")
            except Exception as e:
                deletion_errors.append(f"Milvus向量数据删除异常: {str(e)}")
                self.logger.warning(f"Milvus向量数据删除异常: {str(e)}")
            
            # 1.5. 删除OpenSearch索引数据
            try:
                from app.service.pdf.PdfOpenSearchService import PdfOpenSearchService
                opensearch_service = PdfOpenSearchService()
                if opensearch_service.delete_document_from_opensearch(file_id):
                    success_count += 1
                    self.logger.info(f"✓ OpenSearch索引数据删除成功")
                else:
                    deletion_errors.append("OpenSearch索引数据删除失败")
            except Exception as e:
                deletion_errors.append(f"OpenSearch索引数据删除异常: {str(e)}")
                self.logger.warning(f"OpenSearch索引数据删除异常: {str(e)}")
            
            # 2. 删除Neo4j图数据
            try:
                from utils.Neo4jManager import Neo4jManager
                neo4j_manager = Neo4jManager()
                if neo4j_manager.delete_document_data(file_id):
                    success_count += 1
                    self.logger.info(f"✓ Neo4j图数据删除成功")
                else:
                    deletion_errors.append("Neo4j图数据删除失败")
            except Exception as e:
                deletion_errors.append(f"Neo4j图数据删除异常: {str(e)}")
                self.logger.warning(f"Neo4j图数据删除异常: {str(e)}")
            
            # 3. 删除处理过程中生成的文件（JSON、BM25、图片等）
            try:
                file_deletion_results = self._delete_processed_files(file_id, file_info['filename'])
                if any(file_deletion_results.values()):
                    success_count += 1
                    self.logger.info(f"✓ 处理文件删除成功: {file_deletion_results}")
                else:
                    self.logger.info("没有找到需要删除的处理文件")
                    success_count += 1  # 没有文件也算成功
            except Exception as e:
                deletion_errors.append(f"处理文件删除异常: {str(e)}")
                self.logger.warning(f"处理文件删除异常: {str(e)}")
            
            # 4. 删除原始物理文件
            try:
                if os.path.exists(file_info['file_path']):
                    os.remove(file_info['file_path'])
                    success_count += 1
                    self.logger.info(f"✓ 原始文件删除成功: {file_info['file_path']}")
                else:
                    self.logger.info("原始文件不存在，跳过删除")
                    success_count += 1  # 文件不存在也算成功
            except Exception as e:
                deletion_errors.append(f"原始文件删除失败: {str(e)}")
                self.logger.warning(f"原始文件删除失败: {str(e)}")
            
            # 5. 删除MySQL数据库记录（这会触发级联删除）
            try:
                mysql_success = self.mysql_manager.delete_data(
                    'documents',
                    'id = :file_id',
                    {'file_id': file_id}
                )
                if mysql_success:
                    success_count += 1
                    self.logger.info(f"✓ MySQL数据删除成功（包括级联删除sections、figures、tables、table_rows）")
                else:
                    deletion_errors.append("MySQL数据删除失败")
            except Exception as e:
                deletion_errors.append(f"MySQL数据删除异常: {str(e)}")
                self.logger.warning(f"MySQL数据删除异常: {str(e)}")
            
            # 6. 记录操作日志（这已经通过数据库触发器自动记录了）
            success_count += 1
            
            # 评估删除结果
            if success_count >= 4:  # 至少完成核心删除操作
                self.logger.info(f"文件删除成功，ID: {file_id}, 成功操作: {success_count}/{total_operations}")
                if deletion_errors:
                    self.logger.warning(f"删除过程中的警告: {'; '.join(deletion_errors)}")
                return True
            else:
                self.logger.error(f"文件删除失败，ID: {file_id}, 成功操作: {success_count}/{total_operations}")
                self.logger.error(f"删除错误: {'; '.join(deletion_errors)}")
                return False
            
        except Exception as e:
            self.logger.error(f"删除文件过程中发生严重错误: {str(e)}")
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
            
            current_time = datetime.now(timezone(timedelta(hours=8)))
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
    
    def _async_process_file(self, file_id: int, file_path: str) -> None:
        """
        异步处理文件（提取内容、向量化、知识图谱）
        
        Args:
            file_id: 文件ID
            file_path: 文件路径
        """
        try:
            # 导入处理服务
            from app.service.pdf.PdfExtractService import PdfExtractService
            from app.service.pdf.PdfFormatElementsToJson import PdfFormatElementsToJson
            from app.service.pdf.PdfVectorService import PdfVectorService
            from app.service.pdf.PdfOpenSearchService import PdfOpenSearchService
            from app.service.pdf.PdfGraphService import PdfGraphService
            from app.service.pdf.PdfMysqlService import PdfMysqlService
            
            pdf_extract_service = PdfExtractService()
            pdf_format_service = PdfFormatElementsToJson()
            pdf_vector_service = PdfVectorService()
            pdf_opensearch_service = PdfOpenSearchService()
            pdf_graph_service = PdfGraphService()
            pdf_mysql_service = PdfMysqlService()
            
            self.logger.info(f"开始异步处理文件，ID: {file_id}")
            
            # 步骤1：内容提取 (10% -> 25%)
            self.update_file_status(file_id, 'extracting')
            elements = pdf_extract_service.extract_pdf_content(file_path, file_id)
            
            if elements is None:
                self.update_file_status(file_id, 'extract_failed')
                self.logger.error(f"文件内容提取失败，ID: {file_id}")
                return

            # 步骤1.1：格式化elements (25% -> 35%)
            format_result = pdf_format_service.format_elements_to_json(elements, file_id, file_path)
            
            if not format_result['success']:
                self.update_file_status(file_id, 'extract_failed')
                self.logger.error(f"元素格式化失败，ID: {file_id}, 错误: {format_result['message']}")
                return
            
            json_data = format_result['json_data']
            self.logger.info(f"元素格式化完成，ID: {file_id}")
            
            # 步骤1.2：保存JSON文件 (35% -> 40%)
            json_file_path = self._save_json_data(json_data, file_path, file_id)
            
            if not json_file_path:
                self.update_file_status(file_id, 'extract_failed')
                self.logger.error(f"保存JSON文件失败，ID: {file_id}")
                return
                
            self.update_file_status(file_id, 'extracted')
            self.logger.info(f"JSON文件保存完成，ID: {file_id}, 路径: {json_file_path}")
            
            # 步骤2：向量化 (40% -> 60%)
            self.update_file_status(file_id, 'vectorizing')
            vector_result = pdf_vector_service.process_pdf_json_to_vectors(json_data, file_id)
            
            if not vector_result['success']:
                self.update_file_status(file_id, 'vectorize_failed')
                self.logger.error(f"文件向量化失败，ID: {file_id}, 错误: {vector_result['message']}")
                return
                
            self.update_file_status(file_id, 'vectorized')
            self.logger.info(f"文件向量化完成，ID: {file_id}")
            
            # 步骤3：OpenSearch索引 (60% -> 70%)
            self.update_file_status(file_id, 'bm25_processing')
            opensearch_result = pdf_opensearch_service.process_pdf_json_to_opensearch(json_data, file_id)
            
            if not opensearch_result['success']:
                self.update_file_status(file_id, 'bm25_failed')
                self.logger.error(f"OpenSearch索引处理失败，ID: {file_id}, 错误: {opensearch_result['message']}")
                return
                
            self.update_file_status(file_id, 'bm25_completed')
            self.logger.info(f"OpenSearch索引处理完成，ID: {file_id}")
            
            # 步骤4：知识图谱构建 (70% -> 85%)
            self.update_file_status(file_id, 'graph_processing')
            graph_result = pdf_graph_service.process_pdf_json_to_graph(json_data, file_id)
            
            if not graph_result['success']:
                self.update_file_status(file_id, 'graph_failed')
                self.logger.error(f"知识图谱构建失败，ID: {file_id}, 错误: {graph_result['message']}")
                return
                
            self.update_file_status(file_id, 'graph_completed')
            self.logger.info(f"知识图谱构建完成，ID: {file_id}")
            
            # 步骤5：MySQL保存 (85% -> 100%)
            self.update_file_status(file_id, 'mysql_processing')
            mysql_result = pdf_mysql_service.process_pdf_json_to_mysql(json_data, file_id)
            
            if not mysql_result['success']:
                self.update_file_status(file_id, 'mysql_failed')
                self.logger.error(f"MySQL保存失败，ID: {file_id}, 错误: {mysql_result['message']}")
                return
                
            # 所有步骤完成
            self.update_file_status(file_id, 'completed')
            self.logger.info(f"文件处理全部完成，ID: {file_id}")
            
        except Exception as e:
            self.logger.error(f"异步文件处理失败，ID: {file_id}, 错误: {str(e)}")
            self.update_file_status(file_id, 'process_failed')
    
    def _get_json_file_path(self, pdf_file_path: str, file_id: int) -> Optional[str]:
        """
        获取提取后的JSON文件路径
        
        Args:
            pdf_file_path: PDF文件路径
            file_id: 文件ID
            
        Returns:
            Optional[str]: JSON文件路径
        """
        try:
            # 根据PDF文件路径推测JSON文件路径
            # 通常保存在upload/json目录下
            filename = os.path.basename(pdf_file_path)
            name_without_ext = os.path.splitext(filename)[0]
            
            # 🔧 修复：使用正确的文件ID生成文件名
            possible_names = [
                f"{name_without_ext}_doc_{file_id}.json",  # 使用实际的file_id
                f"{name_without_ext}_content_units.json",
                f"{name_without_ext}_doc_1.json"  # 保留兼容性
            ]
            
            json_dir = os.path.join(self.file_config['upload_folder'], 'json')
            
            for json_name in possible_names:
                json_path = os.path.join(json_dir, json_name)
                if os.path.exists(json_path):
                    self.logger.info(f"找到JSON文件: {json_path}")
                    return json_path
            
            # 🔧 增强：如果找不到，记录详细信息
            self.logger.warning(f"在目录 {json_dir} 中找不到以下任何文件: {possible_names}")
            return None
            
        except Exception as e:
            self.logger.error(f"获取JSON文件路径失败: {str(e)}")
            return None

    
    def _save_json_data(self, json_data: Dict[str, Any], file_path: str, document_id: int) -> Optional[str]:
        """
        保存JSON数据到文件
        
        Args:
            json_data: JSON数据
            file_path: 原始PDF文件路径
            document_id: 文档ID
            
        Returns:
            Optional[str]: 保存的JSON文件路径，失败返回None
        """
        try:
            # 获取JSON输出目录
            json_dir = os.path.join(self.file_config['upload_folder'], 'json')
            
            # 确保目录存在
            if not os.path.exists(json_dir):
                os.makedirs(json_dir, exist_ok=True)
                self.logger.info(f"创建JSON输出目录: {json_dir}")
            
            # 生成输出文件名
            pdf_filename = os.path.basename(file_path)
            pdf_name_without_ext = os.path.splitext(pdf_filename)[0]
            json_filename = f"{pdf_name_without_ext}_doc_{document_id}.json"
            json_file_path = os.path.join(json_dir, json_filename)
            
            # 保存JSON文件
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
            
            self.logger.info(f"JSON数据已保存到: {json_file_path}")
            return json_file_path
            
        except Exception as e:
            self.logger.error(f"保存JSON数据到文件失败: {str(e)}")
            return None