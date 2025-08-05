# -*- coding: utf-8 -*-
"""
AI核心PDF内容提取服务测试脚本
基于精简化JSON结构的PDF文档结构化内容提取测试
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.service.pdf.PdfExtractService import extract_pdf_content


def test_ai_core_pdf_extraction():
    """测试AI核心PDF内容提取功能"""
    # 测试文件路径（请替换为实际的PDF文件路径）
    test_files = [
        "/Users/craig-mac/Downloads/多宁产品手册/20240906-CHO试剂盒单页.pdf",
        # 可以添加更多测试文件路径
    ]
    
    for pdf_path in test_files:
        if not os.path.exists(pdf_path):
            print(f"⚠️  测试文件不存在，跳过: {pdf_path}")
            continue
            
        print(f"\n{'='*60}")
        print(f"🔍 正在测试PDF文件: {pdf_path}")
        print(f"{'='*60}")
        
        try:
            # 执行AI核心PDF内容提取
            result = extract_pdf_content(pdf_path)
            
            # 验证新的JSON结构
            if 'document_info' not in result or 'elements' not in result:
                print(f"❌ JSON结构错误: 缺少必需的顶级字段")
                continue
            
            # 打印文档核心信息
            doc_info = result['document_info']
            print(f"📄 文档核心信息:")
            print(f"  - 文件名: {doc_info['file_name']}")
            print(f"  - 文档哈希: {doc_info['file_hash'][:16]}...")
            print(f"  - 总页数: {doc_info['total_pages']}")
            
            # 分析AI核心元素
            elements = result['elements']
            print(f"\n🎯 AI核心元素分析:")
            print(f"  - 有效元素数: {len(elements)}")
            
            # 统计各字段完整性
            vectorization_count = sum(1 for elem in elements if elem.get('vectorization_text'))
            coordinates_count = sum(1 for elem in elements if elem.get('coordinates'))
            context_count = sum(1 for elem in elements if elem.get('context_info'))
            
            print(f"  - 可向量化元素: {vectorization_count}/{len(elements)} ({vectorization_count/len(elements)*100:.1f}%)")
            print(f"  - 包含坐标元素: {coordinates_count}/{len(elements)} ({coordinates_count/len(elements)*100:.1f}%)")
            print(f"  - 包含上下文元素: {context_count}/{len(elements)} ({context_count/len(elements)*100:.1f}%)")
            
            # 分析页面分布
            page_distribution = {}
            for elem in elements:
                page = elem.get('page_number')
                if page is None:
                    page = 'Unknown'
                page_distribution[page] = page_distribution.get(page, 0) + 1
            
            print(f"\n📊 页面分布:")
            # 将Unknown放到最后，数字页面按顺序排列
            sorted_pages = []
            unknown_count = 0
            for page, count in page_distribution.items():
                if page == 'Unknown':
                    unknown_count = count
                else:
                    sorted_pages.append((page, count))
            
            # 按页码排序
            sorted_pages.sort(key=lambda x: x[0])
            
            for page, count in sorted_pages:
                print(f"  - 第{page}页: {count}个元素")
            if unknown_count > 0:
                print(f"  - 未知页面: {unknown_count}个元素")
            
            # 分析元素类型（通过context_info）
            type_distribution = {}
            for elem in elements:
                context = elem.get('context_info', {})
                elem_type = context.get('type_context', {}).get('element_type', 'Unknown')
                type_distribution[elem_type] = type_distribution.get(elem_type, 0) + 1
            
            print(f"\n🏷️  元素类型分布:")
            for elem_type, count in type_distribution.items():
                print(f"  - {elem_type}: {count}个")
            
            # 展示AI核心元素示例
            print(f"\n🎯 AI核心元素示例:")
            for i, element in enumerate(elements[:3], 1):
                print(f"  元素{i}:")
                print(f"    - ID: {element['element_id']}")
                print(f"    - 页码: {element.get('page_number', 'N/A')}")
                print(f"    - 向量化文本: {element['vectorization_text'][:60]}...")
                print(f"    - 原始文本: {element['text_content'][:40]}...")
                
                # 显示上下文信息
                context = element.get('context_info', {})
                if context:
                    pos_info = context.get('position_in_document', {})
                    type_info = context.get('type_context', {})
                    print(f"    - 文档位置: 索引{pos_info.get('index', 'N/A')}, 相对位置{pos_info.get('relative_position', 0):.2f}")
                    print(f"    - 元素类型: {type_info.get('element_type', 'N/A')}")
                print()
            
            # 检查是否自动保存了JSON
            if result.get('saved_json_path'):
                saved_path = result['saved_json_path']
                try:
                    file_size = os.path.getsize(saved_path)
                    print(f"💾 自动保存信息:")
                    print(f"  - 保存路径: {saved_path}")
                    print(f"  - 文件大小: {file_size:,} 字节")
                except:
                    print(f"💾 文件已自动保存到: {saved_path}")
            else:
                # 手动保存结果到文件（兼容旧方式）
                output_file = f"{pdf_path}_ai_core_extracted.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"💾 手动保存结果到: {output_file}")
            
            print(f"\n✅ AI核心PDF提取成功!")
            print(f"🎉 JSON结构验证通过，符合AI核心功能要求!")
            
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
    print("🎯 AI核心PDF内容提取服务测试")
    print("=" * 50)
    
    # 创建测试目录结构
    create_sample_test_structure()
    
    # 运行AI核心提取测试
    test_ai_core_pdf_extraction()
    
    print("\n🎉 测试完成!")