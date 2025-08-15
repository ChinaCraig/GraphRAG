#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BERT中文tokenizer下载脚本 - 知识图谱NER模块专用
模型: bert-base-chinese
版本: transformers-4.36.x compatible
描述: 中文BERT模型的tokenizer，用于知识图谱统计式NER
大小: ~400MB
"""

import os
import sys
import time
from pathlib import Path

# 模型信息
MODEL_NAME = "bert-base-chinese"
MODEL_DESC = "中文BERT模型tokenizer，用于知识图谱NER"
MODEL_SIZE = "~400MB"
FRAMEWORK = "transformers"
VERSION = "4.36.x"

print("=" * 60)
print("📦 GraphRAG 知识图谱模型下载器")
print("=" * 60)

# 检查网络配置
hf_endpoint = os.environ.get('HF_ENDPOINT')
if hf_endpoint:
    print(f"🪞 使用用户配置的镜像源: {hf_endpoint}")
else:
    # 设置默认镜像源（阿里云）
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
    print("🪞 自动使用阿里云镜像源（提高下载成功率）")
    print("   如需使用其他源，请设置 HF_ENDPOINT 环境变量")

print(f"📄 模型: {MODEL_NAME}")
print(f"📝 描述: {MODEL_DESC}")
print(f"📦 大小: {MODEL_SIZE}")
print(f"🔧 框架: {FRAMEWORK} {VERSION}")
print("")

# 设置模型缓存目录（与项目配置一致）
cache_dir = os.path.abspath("./models")
os.makedirs(cache_dir, exist_ok=True)

# 设置环境变量
os.environ['HF_HOME'] = cache_dir
os.environ['TRANSFORMERS_CACHE'] = cache_dir

print(f"📁 模型存储目录: {cache_dir}")
print("")

# 检查是否已存在
model_path = os.path.join(cache_dir, "models--bert-base-chinese")
if os.path.exists(model_path):
    print(f"✓ {MODEL_NAME} 已存在")
    print("⏭️  跳过下载")
    
    # 创建配置说明
    config_info = f"""
# BERT中文tokenizer配置说明
# 
# 模型位置: {cache_dir}/models--bert-base-chinese
# 模型大小: {MODEL_SIZE}
# 
# 在知识图谱配置中使用:
# knowledge_graph:
#   ner:
#     model_name: "bert-base-chinese"
#     cache_dir: "{cache_dir}"
# 
# 主要用途:
# - 统计式NER的tokenizer
# - 中文文本token化
# - offset_mapping支持
"""
    print(config_info)
    sys.exit(0)

print("🚀 开始下载...")
print("   ⏳ 这可能需要几分钟，请耐心等待...")
print("")

# 下载模型
try:
    from transformers import AutoTokenizer
    print("📥 下载tokenizer...")
    
    # 分步下载，显示进度
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        cache_dir=cache_dir,
        force_download=False,  # 不强制重新下载
        resume_download=True   # 支持断点续传
    )
    
    print("✅ tokenizer下载完成")
    
    # 验证模型
    print("🔍 验证模型...")
    test_text = "CHO细胞生产蛋白质"
    inputs = tokenizer(test_text, return_tensors="pt", return_offsets_mapping=True)
    
    print(f"✅ 模型验证成功")
    print(f"   测试文本: {test_text}")
    print(f"   Token数量: {len(inputs['input_ids'][0])}")
    print(f"   Offset映射: {'支持' if 'offset_mapping' in inputs else '不支持'}")
    
    # 显示详细信息
    model_size = sum(f.stat().st_size for f in Path(cache_dir).rglob('*') if f.is_file())
    print(f"📊 实际大小: {model_size / 1024 / 1024:.1f}MB")
    
    print("")
    print("🎉 下载完成！")
    print("")
    
    # 使用说明
    usage_info = f"""
📋 使用说明:

1. 配置文件已更新 (config/model.yaml):
   knowledge_graph:
     ner:
       model_name: "bert-base-chinese"
       cache_dir: "{cache_dir}"

2. 在代码中使用:
   from transformers import AutoTokenizer
   tokenizer = AutoTokenizer.from_pretrained(
       "bert-base-chinese", 
       cache_dir="{cache_dir}"
   )

3. 知识图谱服务会自动使用此模型进行统计式NER

⚠️  注意事项:
- 模型路径: {cache_dir}
- 支持中文文本处理
- 提供offset_mapping功能
- 降级机制：模型加载失败时自动使用规则方法
"""
    print(usage_info)
    
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    print("💡 请先安装: pip install transformers torch")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ 下载失败: {str(e)}")
    print("💡 可能的解决方案:")
    print("   1. 检查网络连接")
    print("   2. 设置代理: export HTTP_PROXY=http://127.0.0.1:7890")
    print("   3. 使用其他镜像: export HF_ENDPOINT=https://hf-mirror.com")
    print("   4. 重新运行脚本")
    sys.exit(1)

