#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF知识图谱服务测试

直接调用process_pdf_json_to_graph函数进行测试
"""

import sys
import os
import json
from typing import Dict, Any

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.service.pdf.PdfGraphService import PdfGraphService


class PdfGraphTest:
    """PDF知识图谱测试类"""
    
    def __init__(self):
        """初始化测试"""
        self.pdf_graph_service = PdfGraphService()
    
    def test_process_pdf_json_to_graph(self, json_file_path: str, document_id: int) -> Dict[str, Any]:
        """
        测试process_pdf_json_to_graph函数
        
        Args:
            json_file_path: JSON文件路径
            document_id: 文档ID
            
        Returns:
            Dict[str, Any]: 执行结果
        """
        print("=" * 80)
        print("PDF知识图谱构建测试")
        print("=" * 80)
        print(f"输入参数:")
        print(f"  - JSON文件路径: {json_file_path}")
        print(f"  - 文档ID: {document_id}")
        print("-" * 80)
        
        try:
            # 检查文件是否存在
            if not os.path.exists(json_file_path):
                error_msg = f"文件不存在: {json_file_path}"
                print(f"❌ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'nodes_count': 0,
                    'relationships_count': 0
                }
            
            print(f"✅ 文件存在，开始处理...")
            
            # 调用process_pdf_json_to_graph函数
            result = self.pdf_graph_service.process_pdf_json_to_graph(
                json_file_path=json_file_path,
                document_id=document_id
            )
            
            # 打印结果
            print(f"\n📊 执行结果:")
            print(f"  - 成功状态: {result['success']}")
            
            if result['success']:
                print(f"  - 节点数量: {result['nodes_count']}")
                print(f"  - 关系数量: {result['relationships_count']}")
                print(f"  - 文档ID: {result['document_id']}")
                print(f"  - 消息: {result['message']}")
                print(f"✅ 知识图谱构建成功！")
            else:
                print(f"  - 错误消息: {result['message']}")
                print(f"❌ 知识图谱构建失败！")
            
            return result
            
        except Exception as e:
            error_msg = f"执行异常: {str(e)}"
            print(f"❌ {error_msg}")
            
            import traceback
            print(f"\n🔍 详细错误信息:")
            traceback.print_exc()
            
            return {
                'success': False,
                'error': error_msg,
                'nodes_count': 0,
                'relationships_count': 0
            }



def main():
    """主函数"""
    # ==================== 测试参数配置 ====================
    # 📝 手动调整这些变量进行测试
    # 文档ID - 根据需要修改
    document_id = 1
    json_file_path = "upload/json/20240906-CHO试剂盒单页_content_units.json"
    # ==================== 执行测试 ====================
    try:
        print("🚀 开始PDF知识图谱构建测试")
        print(f"📅 测试时间: {__import__('datetime').datetime.now()}")
        
        # 创建测试实例
        test_instance = PdfGraphTest()
        
        # 执行测试
        result = test_instance.test_process_pdf_json_to_graph(
            json_file_path=json_file_path,
            document_id=document_id
        )
        
        # 最终结果总结
        print("\n" + "=" * 80)
        print("🎯 测试完成")
        print("=" * 80)
        
        if result['success']:
            print("🎉 测试成功！知识图谱构建完成")
            print(f"📊 最终统计:")
            print(f"   - 创建节点: {result['nodes_count']} 个")
            print(f"   - 创建关系: {result['relationships_count']} 个")
            print(f"   - 处理文档: {result.get('document_id', document_id)}")
        else:
            print("❌ 测试失败！")
            print(f"💥 错误信息: {result.get('error', result.get('message', '未知错误'))}")
        
        return result
        
    except Exception as e:
        print(f"❌ 测试执行异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    # 打印使用说明
    print("=" * 80)
    print("📚 PDF知识图谱构建测试工具")
    print("=" * 80)
    print("🔧 使用方法:")
    print("   1. 修改main()函数中的json_file_path变量")
    print("   2. 修改main()函数中的document_id变量")
    print("   3. 运行: python PdfGraphService_test.py")
    print("=" * 80)
    
    main()
