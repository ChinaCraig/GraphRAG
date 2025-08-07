#!/usr/bin/env python3
"""
PDF向量化服务测试脚本
直接执行此脚本来测试向量化功能
"""

import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.service.pdf.PdfVectorService import PdfVectorService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_pdf_vectorization():
    """测试PDF向量化功能"""
    
    # ========== 测试参数配置 ==========
    # 手动修改以下参数进行测试
    
    # JSON文件路径（相对于项目根目录）
    json_file_path = "upload/json/20240906-CHO试剂盒单页_doc_1.json"
    
    # 文档ID（用于数据库存储）
    document_id = 1
    
    # ================================
    
    print("=" * 60)
    print("PDF向量化服务测试")
    print("=" * 60)
    print(f"JSON文件路径: {json_file_path}")
    print(f"文档ID: {document_id}")
    print("-" * 60)
    
    try:
        # 检查JSON文件是否存在
        full_json_path = project_root / json_file_path
        if not full_json_path.exists():
            print(f"❌ 错误: JSON文件不存在: {full_json_path}")
            print("请检查文件路径是否正确")
            return
        
        print(f"✅ JSON文件存在: {full_json_path}")
        print()
        
        # 初始化向量化服务
        print("🔧 初始化PDF向量化服务...")
        vector_service = PdfVectorService()
        print("✅ 向量化服务初始化成功")
        print()
        
        # 执行向量化处理
        print("🚀 开始向量化处理...")
        result = vector_service.process_pdf_json_to_vectors(
            json_file_path=str(full_json_path),
            document_id=document_id
        )
        
        # 显示结果
        print("📊 处理结果:")
        print(f"  成功状态: {result.get('success', False)}")
        print(f"  处理消息: {result.get('message', 'N/A')}")
        print(f"  向量化数量: {result.get('vectorized_count', 0)}")
        print(f"  文档ID: {result.get('document_id', 'N/A')}")
        
        if result.get('success'):
            print()
            print("🎉 向量化处理成功！")
            
            # 可选：测试搜索功能
            print()
            print("🔍 测试搜索功能...")
            search_results = vector_service.search_similar_content(
                query="CHO细胞",
                top_k=3,
                document_id=document_id
            )
            
            print(f"搜索结果数量: {len(search_results)}")
            for i, result in enumerate(search_results[:2], 1):  # 只显示前2个结果
                print(f"  结果 {i}:")
                print(f"    相似度得分: {result.get('score', 0):.4f}")
                print(f"    标题: {result.get('title', 'N/A')}")
                print(f"    内容类型: {result.get('content_type', 'N/A')}")
                print(f"    页码: {result.get('page_number', 'N/A')}")
                print(f"    内容预览: {result.get('content', '')[:100]}...")
                print()
            
            # 显示统计信息
            print("📈 获取向量统计信息...")
            stats = vector_service.get_document_vector_stats(document_id)
            if stats:
                print(f"  文档ID: {stats.get('document_id')}")
                print(f"  总向量数: {stats.get('total_vectors')}")
                print(f"  MySQL分块数: {stats.get('mysql_chunks')}")
                print(f"  向量维度: {stats.get('dimension')}")
                print(f"  内容类型分布: {stats.get('content_types', {})}")
        else:
            print()
            print("❌ 向量化处理失败")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

def test_cleanup(document_id: int):
    """清理测试数据（可选）"""
    print()
    print("🧹 清理测试数据...")
    
    try:
        vector_service = PdfVectorService()
        success = vector_service.delete_document_vectors(document_id)
        
        if success:
            print(f"✅ 文档 {document_id} 的向量数据已清理")
        else:
            print(f"❌ 清理文档 {document_id} 的向量数据失败")
    except Exception as e:
        print(f"❌ 清理过程中发生错误: {str(e)}")

if __name__ == "__main__":
    """
    直接运行此脚本进行测试
    
    使用方法:
    1. 修改上面 test_pdf_vectorization() 函数中的参数
    2. 运行: python test/PdfVectorService_test.py
    
    参数说明:
    - json_file_path: JSON文件的路径（相对于项目根目录）
    - document_id: 文档ID（整数）
    """
    
    # 运行测试
    test_pdf_vectorization()
    
    # 可选：清理测试数据
    # 取消下面的注释来清理测试数据
    # cleanup_document_id = 1  # 修改为要清理的文档ID
    # test_cleanup(cleanup_document_id)
