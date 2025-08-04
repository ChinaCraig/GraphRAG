#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最简单的PDF提取测试类
只需要给个文件路径，打印返参
"""

import os
import sys
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入PDF提取服务的唯一入口
from app.service.pdf.PdfExtractService import extract_pdf_content

class SimplePdfTest:
    """
    最简单的PDF提取测试类
    """
    
    def test(self, pdf_path: str):
        """
        测试PDF提取功能
        
        Args:
            pdf_path: PDF文件路径
        """
        print(f"📄 测试文件: {pdf_path}")
        
        # 检查文件是否存在
        if not os.path.exists(pdf_path):
            print(f"❌ 文件不存在: {pdf_path}")
            return
        
        try:
            # 调用唯一入口
            result = extract_pdf_content(pdf_path)
            
            # 打印返参
            print(f"✅ 提取成功，共 {len(result)} 个内容块")
            print("\n📋 返参内容:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
        except Exception as e:
            print(f"❌ 提取失败: {e}")

# 使用示例
if __name__ == "__main__":
    # 创建测试实例
    test = SimplePdfTest()
    
    # 测试（请修改为你的PDF文件路径）
    pdf_file = "/Users/craig-mac/Downloads/多宁产品手册/中空纤维产品单页-印刷稿.pdf"  # 修改这里
    
    test.test(pdf_file)