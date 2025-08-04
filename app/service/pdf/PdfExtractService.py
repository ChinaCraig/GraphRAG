#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF内容提取服务
使用Unstructured架构提取PDF文件内容
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import Text, Title, NarrativeText, Table, Image, PageBreak
import os

logger = logging.getLogger(__name__)

class PdfExtractService:
    """
    PDF内容提取服务
    使用Unstructured架构提取PDF文件内容
    """
    
    def __init__(self):
        """
        初始化PDF提取服务
        """
        self.supported_extensions = ['.pdf']
    
    def extract_content(self, file_path: str) -> List[Dict[str, Any]]:
        """
        提取PDF文件内容
        这是唯一的入口函数
        
        Args:
            file_path: PDF文件的绝对路径
            
        Returns:
            List[Dict[str, Any]]: 提取的内容，格式如下：
            [
                {
                    "type": "text",
                    "content": "本试验旨在探究药物A与药物B在不同剂量下的反应。",
                    "embedding_model": "mpnet",
                    "position": { "page": 1, "x": 50, "y": 100 }
                }
            ]
        """
        try:
            # 验证文件路径
            if not self._validate_file_path(file_path):
                raise ValueError(f"无效的文件路径: {file_path}")
            
            # 验证文件类型
            if not self._validate_file_type(file_path):
                raise ValueError(f"不支持的文件类型: {file_path}")
            
            logger.info(f"开始提取PDF内容: {file_path}")
            
            # 使用Unstructured提取PDF内容
            elements = partition_pdf(
                file_path,
                include_metadata=True,
                include_page_breaks=True
            )
            
            # 处理提取的元素
            extracted_content = self._process_elements(elements)
            
            logger.info(f"PDF内容提取完成，共提取 {len(extracted_content)} 个内容块")
            
            return extracted_content
            
        except Exception as e:
            logger.error(f"PDF内容提取失败: {str(e)}")
            raise
    
    def _validate_file_path(self, file_path: str) -> bool:
        """
        验证文件路径
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 路径是否有效
        """
        try:
            path = Path(file_path)
            return path.exists() and path.is_file()
        except Exception:
            return False
    
    def _validate_file_type(self, file_path: str) -> bool:
        """
        验证文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 文件类型是否支持
        """
        try:
            extension = Path(file_path).suffix.lower()
            return extension in self.supported_extensions
        except Exception:
            return False
    
    def _process_elements(self, elements: List[Any]) -> List[Dict[str, Any]]:
        """
        处理提取的元素
        
        Args:
            elements: Unstructured提取的元素列表
            
        Returns:
            List[Dict[str, Any]]: 处理后的内容列表
        """
        processed_content = []
        
        for element in elements:
            try:
                # 获取元素类型
                element_type = self._get_element_type(element)
                
                # 获取元素内容
                content = self._get_element_content(element)
                
                # 获取位置信息
                position = self._get_element_position(element)
                
                # 跳过空内容
                if not content or not content.strip():
                    continue
                
                # 构建内容块
                content_block = {
                    "type": element_type,
                    "content": content.strip(),
                    "embedding_model": "mpnet",
                    "position": position
                }
                
                processed_content.append(content_block)
                
            except Exception as e:
                logger.warning(f"处理元素失败: {str(e)}")
                continue
        
        return processed_content
    
    def _get_element_type(self, element: Any) -> str:
        """
        获取元素类型
        
        Args:
            element: Unstructured元素
            
        Returns:
            str: 元素类型
        """
        if isinstance(element, Text):
            return "text"
        elif isinstance(element, Title):
            return "title"
        elif isinstance(element, NarrativeText):
            return "narrative"
        elif isinstance(element, Table):
            return "table"
        elif isinstance(element, Image):
            return "image"
        elif isinstance(element, PageBreak):
            return "page_break"
        else:
            return "text"
    
    def _get_element_content(self, element: Any) -> str:
        """
        获取元素内容
        
        Args:
            element: Unstructured元素
            
        Returns:
            str: 元素内容
        """
        try:
            # 获取文本内容
            if hasattr(element, 'text'):
                return element.text
            elif hasattr(element, 'content'):
                return element.content
            else:
                return str(element)
        except Exception:
            return str(element)
    
    def _get_element_position(self, element: Any) -> Dict[str, Any]:
        """
        获取元素位置信息
        
        Args:
            element: Unstructured元素
            
        Returns:
            Dict[str, Any]: 位置信息
        """
        position = {
            "page": 1,
            "x": 0,
            "y": 0
        }
        
        try:
            # 获取页码
            if hasattr(element, 'metadata') and element.metadata:
                if 'page_number' in element.metadata:
                    position["page"] = element.metadata['page_number']
            
            # 获取坐标信息
            if hasattr(element, 'coordinates'):
                coords = element.coordinates
                if coords:
                    position["x"] = coords.x1 if hasattr(coords, 'x1') else 0
                    position["y"] = coords.y1 if hasattr(coords, 'y1') else 0
            
        except Exception as e:
            logger.debug(f"获取位置信息失败: {str(e)}")
        
        return position
    
    def save_json_content(self, content: List[Dict[str, Any]], file_path: str) -> str:
        """
        保存提取的内容为JSON文件
        
        Args:
            content: 提取的内容
            file_path: 原始PDF文件路径
            
        Returns:
            str: 保存的JSON文件路径
        """
        try:
            # 创建JSON保存目录
            json_dir = Path("upload/json")
            json_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成JSON文件名（使用PDF文件名）
            pdf_name = Path(file_path).stem
            json_path = json_dir / f"{pdf_name}.json"
            
            # 保存JSON文件
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON内容已保存到: {json_path}")
            return str(json_path)
            
        except Exception as e:
            logger.error(f"保存JSON内容失败: {str(e)}")
            raise

# 全局PDF提取服务实例
pdf_extract_service = PdfExtractService()

def extract_pdf_content(file_path: str) -> List[Dict[str, Any]]:
    """
    PDF内容提取的全局入口函数
    
    Args:
        file_path: PDF文件的绝对路径
        
    Returns:
        List[Dict[str, Any]]: 提取的内容
    """
    return pdf_extract_service.extract_content(file_path) 