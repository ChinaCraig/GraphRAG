"""
PDF文档结构化内容提取服务

基于unstructured库的PDF文档结构化内容提取系统，支持提取文本、标题、表格、图片等多种内容类型，
并记录其坐标和元数据信息。生成的JSON格式适用于向量化和实体关系提取。

功能特点：
1. 支持中英文PDF文档处理
2. 提取文本、标题、表格、图片等多种内容类型
3. 记录元素坐标和页面信息
4. 生成结构化JSON，适合向量化和知识图谱构建
5. 保持文档层次结构和上下文关系

使用方法：
    extractor = PdfExtractService()
    result = extractor.extract_pdf_content("/path/to/pdf/file.pdf")
"""

import os
import json
import hashlib
import yaml
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path

# unstructured库导入
from unstructured.partition.pdf import partition_pdf
from unstructured.staging.base import dict_to_elements, elements_to_json
from unstructured.chunking.title import chunk_by_title

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PdfExtractService:
    """PDF文档结构化内容提取服务类"""
    
    def __init__(self):
        """初始化PDF提取服务"""
        self.supported_languages = ['zh', 'en']  # 支持中英文
        self.element_types = {
            'Title': '标题',
            'NarrativeText': '正文',
            'ListItem': '列表项',
            'Table': '表格', 
            'Image': '图片',
            'Header': '页眉',
            'Footer': '页脚',
            'UncategorizedText': '未分类文本'
        }
        # 加载配置
        self.config = self._load_config()
    
    def extract_pdf_content(self, pdf_file_path: str) -> Dict[str, Any]:
        """
        PDF文档内容提取主入口函数
        
        Args:
            pdf_file_path (str): PDF文件的绝对路径
            
        Returns:
            Dict[str, Any]: 结构化的JSON数据，包含文档元数据和提取的内容
            
        Raises:
            FileNotFoundError: 当PDF文件不存在时
            Exception: 当PDF处理失败时
        """
        try:
            # 验证文件存在性
            if not os.path.exists(pdf_file_path):
                raise FileNotFoundError(f"PDF文件不存在: {pdf_file_path}")
                
            logger.info(f"开始处理PDF文件: {pdf_file_path}")
            
            # 使用unstructured库进行PDF分割处理
            elements = partition_pdf(
                filename=pdf_file_path,
                strategy="fast",  # 使用快速策略，避免下载大型模型
                infer_table_structure=True,  # 推断表格结构
                extract_images_in_pdf=False,  # 暂时关闭图片提取以避免网络问题
                include_page_breaks=True,  # 包含分页信息
                languages=self.supported_languages,  # 支持的语言
            )
            
            # 生成文档基础信息
            doc_metadata = self._generate_document_metadata(pdf_file_path)
            
            # 处理和结构化元素
            structured_elements = self._process_elements(elements)
            
            # 生成精简的AI核心JSON结构
            result = {
                "document_info": {
                    "file_hash": doc_metadata["file_hash"],
                    "file_name": doc_metadata["file_name"],
                    "total_pages": self._get_total_pages(structured_elements)
                },
                "elements": self._generate_ai_core_elements(structured_elements)
            }
            
            logger.info(f"PDF处理完成，提取了 {len(result['elements'])} 个有效AI核心元素")
            
            # 保存JSON文件到配置的目录
            saved_path = self._save_json_result(result, pdf_file_path)
            if saved_path:
                logger.info(f"JSON文件已保存到: {saved_path}")
                result["saved_json_path"] = saved_path
            
            return result
            
        except Exception as e:
            logger.error(f"PDF处理失败: {str(e)}")
            raise Exception(f"PDF文档提取失败: {str(e)}")
    
    def _generate_document_metadata(self, pdf_file_path: str) -> Dict[str, Any]:
        """
        生成文档元数据信息
        
        Args:
            pdf_file_path (str): PDF文件路径
            
        Returns:
            Dict[str, Any]: 文档元数据
        """
        file_path = Path(pdf_file_path)
        file_stats = file_path.stat()
        
        # 生成文件哈希值
        with open(pdf_file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        
        return {
            "file_name": file_path.name,
            "file_path": str(file_path.absolute()),
            "file_size": file_stats.st_size,
            "file_hash": file_hash,
            "created_time": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
            "modified_time": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            "file_extension": file_path.suffix.lower()
        }
    
    def _generate_ai_core_elements(self, structured_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        生成AI核心功能所需的精简元素列表
        
        Args:
            structured_elements (List[Dict[str, Any]]): 完整的结构化元素列表
            
        Returns:
            List[Dict[str, Any]]: AI核心字段的精简元素列表
        """
        ai_core_elements = []
        
        for element in structured_elements:
            # 只保留AI核心功能必需的字段
            core_element = {
                "element_id": element.get("element_id"),
                "vectorization_text": element.get("vectorization_text"),
                "text_content": element.get("text_content"),
                "page_number": element.get("page_number"),
                "coordinates": element.get("coordinates"),
                "context_info": element.get("context_info")
            }
            
            # 过滤掉None值和空字符串的元素
            if core_element["text_content"] or core_element["vectorization_text"]:
                ai_core_elements.append(core_element)
        
        return ai_core_elements
    
    def _get_total_pages(self, structured_elements: List[Dict[str, Any]]) -> int:
        """
        获取文档总页数
        
        Args:
            structured_elements (List[Dict[str, Any]]): 结构化元素列表
            
        Returns:
            int: 文档总页数
        """
        pages = set()
        for element in structured_elements:
            if element.get("page_number"):
                pages.add(element["page_number"])
        return len(pages) if pages else 0

    def _process_elements(self, elements: List) -> List[Dict[str, Any]]:
        """
        处理和结构化提取的元素
        
        Args:
            elements (List): unstructured库提取的原始元素列表
            
        Returns:
            List[Dict[str, Any]]: 结构化的元素列表
        """
        structured_elements = []
        
        for idx, element in enumerate(elements):
            try:
                # 获取元素基本信息
                element_data = {
                    "element_id": f"elem_{idx:06d}",
                    "element_type": str(type(element).__name__),
                    "element_type_cn": self.element_types.get(str(type(element).__name__), "未知类型"),
                    "text_content": str(element),
                    "text_length": len(str(element)),
                }
                
                # 添加坐标信息（如果存在）
                if hasattr(element, 'metadata') and element.metadata:
                    metadata = element.metadata
                    
                    # 页面信息
                    if hasattr(metadata, 'page_number'):
                        element_data["page_number"] = metadata.page_number
                    
                    # 坐标信息
                    if hasattr(metadata, 'coordinates') and metadata.coordinates:
                        coords = metadata.coordinates
                        element_data["coordinates"] = {
                            "points": list(coords.points) if hasattr(coords, 'points') and coords.points else None,
                            "system": str(coords.system) if hasattr(coords, 'system') and coords.system else None,
                            "layout_width": float(coords.layout_width) if hasattr(coords, 'layout_width') and coords.layout_width else None,
                            "layout_height": float(coords.layout_height) if hasattr(coords, 'layout_height') and coords.layout_height else None
                        }
                    
                    # 其他元数据
                    if hasattr(metadata, 'filename'):
                        element_data["source_filename"] = str(metadata.filename)
                    if hasattr(metadata, 'filetype'):
                        element_data["source_filetype"] = str(metadata.filetype)
                    if hasattr(metadata, 'languages'):
                        element_data["detected_languages"] = list(metadata.languages) if metadata.languages else []
                
                # 特殊处理表格元素
                if 'Table' in str(type(element).__name__):
                    element_data.update(self._process_table_element(element))
                
                # 特殊处理图片元素
                if 'Image' in str(type(element).__name__):
                    element_data.update(self._process_image_element(element))
                
                # 添加用于向量化的组合文本
                element_data["vectorization_text"] = self._generate_vectorization_text(element_data)
                
                # 添加用于实体关系提取的上下文
                element_data["context_info"] = self._generate_context_info(element_data, idx, len(elements))
                
                structured_elements.append(element_data)
                
            except Exception as e:
                logger.warning(f"处理元素 {idx} 时发生错误: {str(e)}")
                # 即使单个元素处理失败，也继续处理其他元素
                continue
        
        return structured_elements
    
    def _process_table_element(self, element) -> Dict[str, Any]:
        """
        特殊处理表格元素
        
        Args:
            element: 表格元素
            
        Returns:
            Dict[str, Any]: 表格特殊处理信息
        """
        table_info = {
            "is_table": True,
            "table_text": str(element),
        }
        
        # 尝试获取表格的HTML表示
        if hasattr(element, 'metadata') and hasattr(element.metadata, 'text_as_html'):
            table_info["table_html"] = str(element.metadata.text_as_html) if element.metadata.text_as_html else None
        
        return table_info
    
    def _process_image_element(self, element) -> Dict[str, Any]:
        """
        特殊处理图片元素
        
        Args:
            element: 图片元素
            
        Returns:
            Dict[str, Any]: 图片特殊处理信息
        """
        image_info = {
            "is_image": True,
            "image_description": str(element) if str(element) else "图片内容",
        }
        
        # 如果有图片路径信息
        if hasattr(element, 'metadata') and hasattr(element.metadata, 'image_path'):
            image_info["image_path"] = str(element.metadata.image_path) if element.metadata.image_path else None
        
        return image_info
    
    def _generate_vectorization_text(self, element_data: Dict[str, Any]) -> str:
        """
        生成用于向量化的组合文本
        
        Args:
            element_data (Dict[str, Any]): 元素数据
            
        Returns:
            str: 用于向量化的文本
        """
        vectorization_parts = []
        
        # 添加元素类型信息
        if element_data.get("element_type_cn"):
            vectorization_parts.append(f"[{element_data['element_type_cn']}]")
        
        # 添加主要文本内容
        if element_data.get("text_content"):
            vectorization_parts.append(element_data["text_content"])
        
        # 如果是表格，添加结构信息
        if element_data.get("is_table"):
            vectorization_parts.append("[表格数据]")
        
        # 如果是图片，添加描述信息
        if element_data.get("is_image"):
            vectorization_parts.append("[图片内容]")
            if element_data.get("image_description"):
                vectorization_parts.append(element_data["image_description"])
        
        return " ".join(vectorization_parts)
    
    def _generate_context_info(self, element_data: Dict[str, Any], current_idx: int, total_elements: int) -> Dict[str, Any]:
        """
        生成用于实体关系提取的上下文信息
        
        Args:
            element_data (Dict[str, Any]): 当前元素数据
            current_idx (int): 当前元素索引
            total_elements (int): 总元素数量
            
        Returns:
            Dict[str, Any]: 上下文信息
        """
        context_info = {
            "position_in_document": {
                "index": current_idx,
                "relative_position": current_idx / total_elements if total_elements > 0 else 0,
                "is_beginning": current_idx < total_elements * 0.1,
                "is_middle": 0.1 <= current_idx / total_elements <= 0.9,
                "is_end": current_idx > total_elements * 0.9
            }
        }
        
        # 添加页面上下文
        if element_data.get("page_number"):
            context_info["page_context"] = {
                "page_number": element_data["page_number"],
                "page_position": f"第{element_data['page_number']}页"
            }
        
        # 添加元素类型上下文
        context_info["type_context"] = {
            "element_type": element_data.get("element_type"),
            "is_title": "Title" in element_data.get("element_type", ""),
            "is_content": "NarrativeText" in element_data.get("element_type", ""),
            "is_structured": element_data.get("is_table", False) or element_data.get("is_image", False)
        }
        
        return context_info
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载项目配置文件
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        try:
            # 获取项目根目录（从当前文件位置推导）
            current_dir = Path(__file__).parent.parent.parent.parent
            config_path = current_dir / "config" / "config.yaml"
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                logger.info(f"成功加载配置文件: {config_path}")
                return config
            else:
                logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
                return {"upload": {"json_path": "./upload/json"}}
                
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}，使用默认配置")
            return {"upload": {"json_path": "./upload/json"}}
    
    def _save_json_result(self, result: Dict[str, Any], pdf_file_path: str) -> Optional[str]:
        """
        保存提取结果到JSON文件
        
        Args:
            result (Dict[str, Any]): 提取结果
            pdf_file_path (str): 原始PDF文件路径
            
        Returns:
            Optional[str]: 保存的JSON文件路径，如果保存失败则返回None
        """
        try:
            # 获取配置的JSON保存路径
            json_path = self.config.get("upload", {}).get("json_path", "./upload/json")
            
            # 确保目录存在
            json_dir = Path(json_path)
            json_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成JSON文件名（基于原PDF文件名）
            pdf_name = Path(pdf_file_path).stem  # 不包含扩展名的文件名
            json_filename = f"{pdf_name}_extracted.json"
            json_file_path = json_dir / json_filename
            
            # 保存JSON文件
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON文件保存成功: {json_file_path}")
            return str(json_file_path.absolute())
            
        except Exception as e:
            logger.error(f"保存JSON文件失败: {str(e)}")
            return None


# 全局函数接口，方便外部调用
def extract_pdf_content(pdf_file_path: str) -> Dict[str, Any]:
    """
    PDF内容提取的全局函数接口
    
    Args:
        pdf_file_path (str): PDF文件的绝对路径
        
    Returns:
        Dict[str, Any]: 结构化的JSON数据
    """
    extractor = PdfExtractService()
    return extractor.extract_pdf_content(pdf_file_path)


if __name__ == "__main__":
    # 测试代码
    import sys
    
    if len(sys.argv) > 1:
        test_pdf_path = sys.argv[1]
        try:
            result = extract_pdf_content(test_pdf_path)
            print("✅ AI核心PDF提取成功!")
            print(f"📄 文档名称: {result['document_info']['file_name']}")
            print(f"📊 有效元素数: {len(result['elements'])}")
            print(f"📖 总页数: {result['document_info']['total_pages']}")
            print(f"💾 文档哈希: {result['document_info']['file_hash'][:8]}...")
            
            # 显示前3个元素示例
            print("\n🎯 AI核心元素示例:")
            for i, elem in enumerate(result['elements'][:3]):
                print(f"  元素{i+1}:")
                print(f"    - ID: {elem['element_id']}")
                print(f"    - 页码: {elem.get('page_number', 'N/A')}")
                print(f"    - 向量化文本: {elem['vectorization_text'][:50]}...")
            
            if result.get('saved_json_path'):
                print(f"\n💾 JSON已自动保存到: {result['saved_json_path']}")
            
        except Exception as e:
            print(f"❌ 提取失败: {str(e)}")
    else:
        print("使用方法: python PdfExtractService.py <pdf_file_path>")