#!/usr/bin/env python3
"""
Unstructured PDF提取服务测试脚本
测试 _partition_pdf_with_unstructured 函数
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.service.pdf.PdfExtractService import PdfExtractService


def test_partition_pdf():
    """测试 _partition_pdf_with_unstructured 函数"""
    print("=" * 60)
    print("测试 _partition_pdf_with_unstructured 函数")
    print("=" * 60)
    
    # 请替换为实际的PDF文件路径
    pdf_file_path = "/Users/craig-macmini/Downloads/多宁产品手册/20240906-CHO试剂盒单页.pdf"  # 在这里输入你的PDF文件路径
    
    try:
        # 初始化服务
        service = PdfExtractService()
        print(f"✅ PdfExtractService初始化成功")
        
        # 检查文件是否存在
        if not os.path.exists(pdf_file_path):
            print(f"❌ PDF文件不存在: {pdf_file_path}")
            print(f"💡 请将PDF文件路径设置为实际存在的文件")
            return False
        
        print(f"📁 测试文件: {pdf_file_path}")
        
        # 调用完整的 extract_pdf_content 方法
        document_id = 1  # 测试用文档ID
        result = service.extract_pdf_content(pdf_file_path, document_id)
        
        if result['success']:
            print(f"✅ PDF解析成功!")
            elements_json = result['extracted_data']
            print(f"📊 提取到 {len(elements_json)} 个元素")
            
            # 显示前几个元素的信息
            for i, element in enumerate(elements_json[:5]):  # 显示前5个元素
                element_type = element.get('type', 'Unknown')
                element_text = element.get('text', '')[:100]  # 只显示前100个字符
                print(f"📝 元素 {i+1}: {element_type}")
                print(f"   内容: {element_text}...")
                
                # 显示页码信息
                metadata = element.get('metadata', {})
                page_number = metadata.get('page_number')
                if page_number:
                    print(f"   页码: {page_number}")
                print()
            
            if len(elements_json) > 5:
                print(f"... 还有 {len(elements_json) - 5} 个元素")
            
            # 检查JSON文件是否生成
            pdf_filename = os.path.basename(pdf_file_path)
            pdf_name_without_ext = os.path.splitext(pdf_filename)[0]
            json_filename = f"{pdf_name_without_ext}_doc_{document_id}.json"
            json_file_path = f"upload/json/{json_filename}"
            
            if os.path.exists(json_file_path):
                file_size = os.path.getsize(json_file_path)
                print(f"📁 JSON文件已保存: {json_file_path}")
                print(f"📊 文件大小: {file_size} 字节")
            else:
                print(f"⚠️ JSON文件未找到: {json_file_path}")
                
        else:
            print(f"❌ PDF解析失败: {result['message']}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        print("🤖 Unstructured PDF _partition_pdf_with_unstructured 函数测试")
        print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        success = test_partition_pdf()
        
        print("\n" + "=" * 60)
        if success:
            print("🎉 测试完成!")
        else:
            print("⚠️  测试失败")
        print("=" * 60)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n👋 用户取消测试")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 测试脚本异常: {str(e)}")
        sys.exit(1)