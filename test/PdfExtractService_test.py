# -*- coding: utf-8 -*-
"""
PDF内容提取服务测试脚本
基于unstructured库的PDF文档结构化内容提取测试
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.service.pdf.PdfExtractService import extract_pdf_content


def test_pdf_extraction():
    """测试PDF内容提取功能"""
    # 测试文件路径（请替换为实际的PDF文件路径）
    test_files = [
        "/Users/craig-mac/Downloads/多宁产品手册/20240906-CHO试剂盒单页.pdf",
        # 可以添加更多测试文件路径
    ]
    
    for pdf_path in test_files:
        if not os.path.exists(pdf_path):
            print(f"测试文件不存在，跳过: {pdf_path}")
            continue
            
        print(f"\n{'='*60}")
        print(f"正在测试PDF文件: {pdf_path}")
        print(f"{'='*60}")
        
        try:
            # 执行PDF内容提取
            result = extract_pdf_content(pdf_path)
            
            # 打印文档基本信息
            doc_metadata = result['document_metadata']
            print(f"文档信息:")
            print(f"  - 文件名: {doc_metadata['file_name']}")
            print(f"  - 文件大小: {doc_metadata['file_size']} 字节")
            print(f"  - 文件哈希: {doc_metadata['file_hash'][:8]}...")
            
            # 打印内容摘要
            content_summary = result['content_summary']
            print(f"\n内容摘要:")
            print(f"  - 总字符数: {content_summary['total_characters']}")
            print(f"  - 总页数: {content_summary['total_pages']}")
            print(f"  - 页面范围: {content_summary['page_range']}")
            print(f"  - 包含表格: {'是' if content_summary['has_tables'] else '否'}")
            print(f"  - 包含图片: {'是' if content_summary['has_images'] else '否'}")
            print(f"  - 内容密度: {content_summary['content_density']:.2f} 字符/元素")
            
            # 打印元素类型分布
            print(f"\n元素类型分布:")
            for element_type, count in content_summary['element_distribution'].items():
                print(f"  - {element_type}: {count}个")
            
            # 打印标题层次结构
            if content_summary['title_hierarchy']:
                print(f"\n标题层次结构:")
                for i, title in enumerate(content_summary['title_hierarchy'][:5], 1):
                    print(f"  {i}. {title[:50]}{'...' if len(title) > 50 else ''}")
            
            # 打印提取元数据
            extraction_metadata = result['extraction_metadata']
            print(f"\n提取元数据:")
            print(f"  - 提取时间: {extraction_metadata['extraction_time']}")
            print(f"  - 总元素数: {extraction_metadata['total_elements']}")
            print(f"  - 处理策略: {extraction_metadata['processing_strategy']}")
            print(f"  - 支持语言: {extraction_metadata['languages_detected']}")
            
            # 展示前几个结构化元素的示例
            print(f"\n结构化内容示例:")
            structured_content = result['structured_content']
            for i, element in enumerate(structured_content[:3], 1):
                print(f"  元素{i}:")
                print(f"    - ID: {element['element_id']}")
                print(f"    - 类型: {element['element_type_cn']}")
                print(f"    - 页码: {element.get('page_number', '未知')}")
                print(f"    - 内容: {element['text_content'][:80]}{'...' if len(element['text_content']) > 80 else ''}")
                if element.get('is_table'):
                    print(f"    - [表格元素]")
                if element.get('is_image'):
                    print(f"    - [图片元素]")
                print()
            
            # 保存结果到文件
            output_file = f"{pdf_path}_extracted.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"提取结果已保存到: {output_file}")
            
            print(f"✅ PDF提取成功!")
            
        except Exception as e:
            print(f"❌ PDF提取失败: {str(e)}")
            import traceback
            traceback.print_exc()


def create_sample_test_structure():
    """创建示例测试结构"""
    upload_dir = Path(project_root) / "upload" / "pdf"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"已创建上传目录: {upload_dir}")
    print(f"请将测试PDF文件放入此目录，然后运行测试")


if __name__ == "__main__":
    print("PDF内容提取服务测试")
    print("=" * 40)
    
    # 创建测试目录结构
    create_sample_test_structure()
    
    # 运行测试
    test_pdf_extraction()
    
    print("\n测试完成!")