"""
PDF内容提取服务 - 基于Unstructured库实现
负责从PDF文件中提取文本、图片、表格等内容
"""

import logging
import os
import yaml
from typing import Dict, Any, List
from datetime import datetime
import json

from unstructured.partition.pdf import partition_pdf


class PdfExtractService:
    """PDF内容提取服务类 - 基于Unstructured库"""
    
    def __init__(self, unstructured_config_path: str = 'config/Unstructured.yaml'):
        """
        初始化PDF提取服务
        
        Args:
            unstructured_config_path: Unstructured配置文件路径
        """
        self.unstructured_config_path = unstructured_config_path
        self.logger = logging.getLogger(__name__)
        
        # 加载Unstructured配置
        self._load_unstructured_config()
        
        # 创建必要的目录
        self._create_directories()
    

    
    def _load_unstructured_config(self) -> None:
        """加载Unstructured配置文件"""
        try:
            with open(self.unstructured_config_path, 'r', encoding='utf-8') as file:
                self.unstructured_config = yaml.safe_load(file)
                self.logger.info("Unstructured配置加载成功")
        except Exception as e:
            self.logger.error(f"加载Unstructured配置失败: {str(e)}")
            # 使用默认配置
            self.unstructured_config = {
                'basic': {'output_format': 'application/json', 'encoding': 'utf-8'},
                'pdf': {'strategy': 'auto'},
                'performance': {'multiprocessing': False}
            }
    
    def _create_directories(self) -> None:
        """创建必要的目录"""
        try:
            # 创建缓存目录
            cache_dir = self.unstructured_config.get('performance', {}).get('cache_dir', './temp/unstructured_cache')
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
                self.logger.info(f"创建Unstructured缓存目录: {cache_dir}")
            
            # 创建JSON输出目录
            pdf_config = self.unstructured_config.get('pdf', {})
            json_output_dir = pdf_config.get('pdf_json_output_dir_path')
            if json_output_dir and json_output_dir != 'null':
                if not os.path.exists(json_output_dir):
                    os.makedirs(json_output_dir, exist_ok=True)
                    self.logger.info(f"创建JSON输出目录: {json_output_dir}")
            
            # 创建调试输出目录
            debug_config = self.unstructured_config.get('debug', {})
            if debug_config.get('save_intermediate_results', False):
                debug_dir = debug_config.get('debug_output_dir', './logs/unstructured_debug')
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir, exist_ok=True)
                    self.logger.info(f"创建调试输出目录: {debug_dir}")
                    
        except Exception as e:
            self.logger.error(f"创建目录失败: {str(e)}")
    
    def extract_pdf_content(self, file_path: str, document_id: int):
        """
        提取PDF文件内容 - 使用Unstructured库
        
        Args:
            file_path: PDF文件路径
            document_id: 文档ID
            
        Returns:
            List: Unstructured元素列表，提取失败返回None
        """
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"文件不存在: {file_path}")
                return None
            
            self.logger.info(f"开始使用Unstructured库提取PDF内容: {file_path}")
            
            # 使用Unstructured库解析PDF
            elements = self._partition_pdf_with_unstructured(file_path)
            
            if not elements:
                self.logger.error("PDF内容提取失败，未获取到任何元素")
                return None
            
            self.logger.info(f"PDF内容提取完成，文档ID: {document_id}, 元素数量: {len(elements)}")
            
            return elements
            
        except Exception as e:
            self.logger.error(f"PDF内容提取失败: {str(e)}")
            return None
    
    def _partition_pdf_with_unstructured(self, file_path: str) -> List:
        """
        使用Unstructured库解析PDF文件
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            List: Unstructured元素列表
        """
        try:
            # 获取PDF配置
            pdf_config = self.unstructured_config.get('pdf', {})
            basic_config = self.unstructured_config.get('basic', {})
            filtering_config = self.unstructured_config.get('filtering', {})
            output_config = self.unstructured_config.get('output', {})
            
            # 构建partition_pdf参数
            partition_kwargs = {
                'filename': file_path,
                'strategy': pdf_config.get('strategy', 'auto'),
                'include_page_breaks': filtering_config.get('include_page_breaks', False),
                'infer_table_structure': pdf_config.get('pdf_infer_table_structure', True),
                # 移除coordinates参数避免冲突
                # 'coordinates': basic_config.get('coordinates', True),
                'metadata_include': output_config.get('metadata_include', []),
                'metadata_exclude': output_config.get('metadata_exclude', [])
            }
            
            # 可选参数
            if pdf_config.get('ocr_languages'):
                partition_kwargs['languages'] = pdf_config['ocr_languages']
            
            if pdf_config.get('hi_res_model_name'):
                partition_kwargs['hi_res_model_name'] = pdf_config['hi_res_model_name']
            
            if pdf_config.get('starting_page_number') is not None:
                partition_kwargs['starting_page_number'] = pdf_config['starting_page_number']
            
            if pdf_config.get('ending_page_number') is not None:
                partition_kwargs['ending_page_number'] = pdf_config['ending_page_number']
            
            # 图片提取配置
            if pdf_config.get('pdf_extract_images', False):
                partition_kwargs['extract_images_in_pdf'] = True
                if pdf_config.get('pdf_image_output_dir_path'):
                    partition_kwargs['extract_image_block_output_dir'] = pdf_config['pdf_image_output_dir_path']
            
            # 执行PDF解析
            elements = partition_pdf(**partition_kwargs)
            
            self.logger.info(f"Unstructured解析完成，获取到{len(elements)}个元素")
            return elements
            
        except Exception as e:
            self.logger.error(f"Unstructured PDF解析失败: {str(e)}")
            return []
