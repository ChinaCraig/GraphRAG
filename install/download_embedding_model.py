#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嵌入模型下载脚本
用于下载 paraphrase-multilingual-mpnet-base-v2 模型
"""

import os
import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def download_embedding_model():
    """
    下载 paraphrase-multilingual-mpnet-base-v2 嵌入模型
    """
    model_name = "paraphrase-multilingual-mpnet-base-v2"
    model_path = Path("./models") / model_name
    
    try:
        logger.info(f"开始下载模型: {model_name}")
        logger.info(f"模型将保存到: {model_path}")
        
        # 创建模型目录
        model_path.mkdir(parents=True, exist_ok=True)
        
        # 下载模型
        logger.info("正在下载模型文件...")
        model = SentenceTransformer(model_name)
        
        # 保存模型到本地
        logger.info("正在保存模型到本地...")
        model.save(str(model_path))
        
        logger.info(f"模型下载完成！保存在: {model_path}")
        
        # 测试模型
        logger.info("正在测试模型...")
        test_texts = ["这是一个测试文本", "This is a test text"]
        embeddings = model.encode(test_texts)
        logger.info(f"模型测试成功！向量维度: {embeddings.shape[1]}")
        
        return True
        
    except Exception as e:
        logger.error(f"模型下载失败: {str(e)}")
        return False

def main():
    """
    主函数
    """
    logger.info("=== 嵌入模型下载脚本 ===")
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        logger.error("需要Python 3.8或更高版本")
        sys.exit(1)
    
    # 下载模型
    success = download_embedding_model()
    
    if success:
        logger.info("模型下载脚本执行完成！")
        sys.exit(0)
    else:
        logger.error("模型下载脚本执行失败！")
        sys.exit(1)

if __name__ == "__main__":
    main() 