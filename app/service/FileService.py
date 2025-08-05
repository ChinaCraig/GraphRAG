# -*- coding: utf-8 -*-
"""
文件管理服务
处理各种文件类型的上传、解析和内容提取
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# 导入PDF提取服务
from app.service.pdf.PdfExtractService import extract_pdf_content

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileService:
    """文件管理服务类"""
    
    def __init__(self):
        """初始化文件服务"""
        self.upload_base_path = Path("upload")
        self.supported_extensions = {
            '.pdf': 'pdf',
            '.docx': 'word',
            '.doc': 'word',
            '.xlsx': 'excel',
            '.xls': 'excel',
            '.pptx': 'ppt',
            '.ppt': 'ppt',
            '.md': 'md',
            '.txt': 'txt',
            '.jpg': 'img',
            '.jpeg': 'img',
            '.png': 'img',
            '.gif': 'img'
        }
    
    def upload_file(self, file_path: str, file_type: Optional[str] = None) -> Dict[str, Any]:
        """
        上传文件并进行初步处理
        
        Args:
            file_path (str): 文件路径
            file_type (str, optional): 文件类型，如果不提供则自动检测
            
        Returns:
            Dict[str, Any]: 上传结果
        """
        try:
            # 验证文件
            if not os.path.exists(file_path):
                raise ValueError(f"文件不存在: {file_path}")
            
            # 获取文件信息
            file_info = self._get_file_info(file_path)
            
            # 自动检测文件类型
            if not file_type:
                file_type = self._detect_file_type(file_path)
            
            # 移动文件到对应目录
            target_path = self._move_file_to_category(file_path, file_type)
            
            # 更新文件信息
            file_info['target_path'] = str(target_path)
            file_info['file_type'] = file_type
            
            logger.info(f"文件上传成功: {target_path}")
            
            return {
                'success': True,
                'message': '文件上传成功',
                'file_info': file_info
            }
            
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            return {
                'success': False,
                'message': f'文件上传失败: {str(e)}',
                'file_info': None
            }
    
    def extract_file_content(self, file_path: str) -> Dict[str, Any]:
        """
        提取文件内容
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            Dict[str, Any]: 提取结果
        """
        try:
            # 检测文件类型
            file_type = self._detect_file_type(file_path)
            
            # 根据文件类型调用相应的提取服务
            if file_type == 'pdf':
                return self._extract_pdf_content(file_path)
            elif file_type == 'word':
                return self._extract_word_content(file_path)
            elif file_type == 'excel':
                return self._extract_excel_content(file_path)
            elif file_type == 'ppt':
                return self._extract_ppt_content(file_path)
            elif file_type == 'md':
                return self._extract_md_content(file_path)
            elif file_type == 'txt':
                return self._extract_txt_content(file_path)
            elif file_type == 'img':
                return self._extract_img_content(file_path)
            else:
                raise ValueError(f"不支持的文件类型: {file_type}")
                
        except Exception as e:
            logger.error(f"文件内容提取失败: {str(e)}")
            return {
                'success': False,
                'message': f'文件内容提取失败: {str(e)}',
                'content': None
            }
    
    def process_file_for_rag(self, file_path: str) -> Dict[str, Any]:
        """
        为RAG系统处理文件（完整流程）
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            Dict[str, Any]: 处理结果，包含向量化和图数据库所需的数据
        """
        try:
            # 1. 上传文件
            upload_result = self.upload_file(file_path)
            if not upload_result['success']:
                return upload_result
            
            # 2. 提取内容
            target_path = upload_result['file_info']['target_path']
            extract_result = self.extract_file_content(target_path)
            if not extract_result['success']:
                return extract_result
            
            # 3. 准备RAG数据
            rag_data = self._prepare_rag_data(extract_result['content'])
            
            return {
                'success': True,
                'message': '文件处理完成',
                'file_info': upload_result['file_info'],
                'extracted_content': extract_result['content'],
                'rag_data': rag_data
            }
            
        except Exception as e:
            logger.error(f"文件RAG处理失败: {str(e)}")
            return {
                'success': False,
                'message': f'文件RAG处理失败: {str(e)}',
                'rag_data': None
            }
    
    def _get_file_info(self, file_path: str) -> Dict[str, Any]:
        """获取文件基本信息"""
        file_path = Path(file_path)
        return {
            'file_name': file_path.name,
            'file_size': file_path.stat().st_size,
            'file_extension': file_path.suffix,
            'original_path': str(file_path)
        }
    
    def _detect_file_type(self, file_path: str) -> str:
        """检测文件类型"""
        file_extension = Path(file_path).suffix.lower()
        return self.supported_extensions.get(file_extension, 'unknown')
    
    def _move_file_to_category(self, file_path: str, file_type: str) -> Path:
        """将文件移动到对应类型目录"""
        source_path = Path(file_path)
        target_dir = self.upload_base_path / file_type
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = target_dir / source_path.name
        
        # 如果目标文件已存在，添加序号
        counter = 1
        while target_path.exists():
            name_parts = source_path.stem, counter, source_path.suffix
            target_path = target_dir / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
            counter += 1
        
        # 复制文件（保留原文件）
        import shutil
        shutil.copy2(source_path, target_path)
        
        return target_path
    
    def _extract_pdf_content(self, file_path: str) -> Dict[str, Any]:
        """提取PDF内容"""
        try:
            content = extract_pdf_content(file_path)
            return {
                'success': True,
                'message': 'PDF内容提取成功',
                'content': content
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'PDF内容提取失败: {str(e)}',
                'content': None
            }
    
    def _extract_word_content(self, file_path: str) -> Dict[str, Any]:
        """提取Word内容（待实现）"""
        # TODO: 实现Word内容提取
        return {
            'success': False,
            'message': 'Word内容提取尚未实现',
            'content': None
        }
    
    def _extract_excel_content(self, file_path: str) -> Dict[str, Any]:
        """提取Excel内容（待实现）"""
        # TODO: 实现Excel内容提取
        return {
            'success': False,
            'message': 'Excel内容提取尚未实现',
            'content': None
        }
    
    def _extract_ppt_content(self, file_path: str) -> Dict[str, Any]:
        """提取PPT内容（待实现）"""
        # TODO: 实现PPT内容提取
        return {
            'success': False,
            'message': 'PPT内容提取尚未实现',
            'content': None
        }
    
    def _extract_md_content(self, file_path: str) -> Dict[str, Any]:
        """提取Markdown内容（待实现）"""
        # TODO: 实现Markdown内容提取
        return {
            'success': False,
            'message': 'Markdown内容提取尚未实现',
            'content': None
        }
    
    def _extract_txt_content(self, file_path: str) -> Dict[str, Any]:
        """提取文本文件内容（待实现）"""
        # TODO: 实现文本文件内容提取
        return {
            'success': False,
            'message': '文本文件内容提取尚未实现',
            'content': None
        }
    
    def _extract_img_content(self, file_path: str) -> Dict[str, Any]:
        """提取图片内容（待实现）"""
        # TODO: 实现图片内容提取（OCR等）
        return {
            'success': False,
            'message': '图片内容提取尚未实现',
            'content': None
        }
    
    def _prepare_rag_data(self, extracted_content: Dict[str, Any]) -> Dict[str, Any]:
        """准备RAG系统所需的数据格式"""
        if not extracted_content:
            return None
        
        # 提取sections用于向量化
        sections_for_vector = []
        if 'sections' in extracted_content:
            for section_id, section_info in extracted_content['sections'].items():
                # 收集section中的所有文本内容
                section_texts = []
                for element_id in section_info['elements']:
                    if element_id in extracted_content['elements']:
                        element = extracted_content['elements'][element_id]
                        section_texts.append(element['content'])
                
                sections_for_vector.append({
                    'section_id': section_id,
                    'title': section_info['title'],
                    'content': ' '.join(section_texts),
                    'page_number': section_info['page_number'],
                    'word_count': section_info['word_count']
                })
        
        # 提取elements用于图数据库
        elements_for_graph = []
        if 'elements' in extracted_content:
            for element_id, element in extracted_content['elements'].items():
                elements_for_graph.append({
                    'element_id': element_id,
                    'element_type': element['element_type'],
                    'content': element['content'],
                    'section_id': element['section_id'],
                    'page_number': element['metadata']['page_number'],
                    'language': element['metadata']['language']
                })
        
        return {
            'sections_for_vector': sections_for_vector,
            'elements_for_graph': elements_for_graph,
            'file_summary': extracted_content.get('summary', {}),
            'extraction_metadata': extracted_content.get('extraction_metadata', {})
        }


# 便捷函数
def process_pdf_for_rag(pdf_path: str) -> Dict[str, Any]:
    """
    处理PDF文件用于RAG系统的便捷函数
    
    Args:
        pdf_path (str): PDF文件路径
        
    Returns:
        Dict[str, Any]: 处理结果
    """
    service = FileService()
    return service.process_file_for_rag(pdf_path)


# 测试用例
if __name__ == "__main__":
    # 示例使用
    test_pdf_path = "/path/to/test.pdf"
    if os.path.exists(test_pdf_path):
        try:
            result = process_pdf_for_rag(test_pdf_path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"测试失败: {str(e)}")
    else:
        print("请提供有效的PDF文件路径进行测试")