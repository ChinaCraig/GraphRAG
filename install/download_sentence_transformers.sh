#!/bin/bash

# Sentence-Transformers模型下载脚本
# 下载项目常用的预训练模型

set -e

echo "=== Sentence-Transformers模型下载脚本 ==="
echo "正在下载项目所需的预训练模型..."

# 检查Python是否可用
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3命令"
    exit 1
fi

# 创建模型下载Python脚本
cat > /tmp/download_st_models.py << 'EOF'
from sentence_transformers import SentenceTransformer
import os
import sys

# 设置缓存目录
cache_dir = os.path.expanduser("~/.cache/sentence_transformers")
os.makedirs(cache_dir, exist_ok=True)
print(f"📁 模型缓存目录: {cache_dir}")

# 推荐的模型列表（按优先级排序）
models = [
    {
        'name': 'all-MiniLM-L6-v2',
        'description': '轻量级英文模型，速度快',
        'size': '~90MB',
        'priority': 'high'
    },
    {
        'name': 'paraphrase-MiniLM-L6-v2', 
        'description': '英文句子相似度模型',
        'size': '~90MB',
        'priority': 'medium'
    },
    {
        'name': 'all-mpnet-base-v2',
        'description': '英文高精度模型',
        'size': '~420MB', 
        'priority': 'low'
    },
    {
        'name': 'paraphrase-multilingual-MiniLM-L12-v2',
        'description': '多语言模型（包含中文）',
        'size': '~470MB',
        'priority': 'medium'
    }
]

print("🤖 可下载的模型列表:")
for i, model in enumerate(models, 1):
    print(f"  {i}. {model['name']}")
    print(f"     - 描述: {model['description']}")
    print(f"     - 大小: {model['size']}")
    print(f"     - 优先级: {model['priority']}")
    print()

# 询问用户选择
print("请选择要下载的模型:")
print("1 - 只下载高优先级模型 (推荐)")
print("2 - 下载高优先级和中优先级模型")
print("3 - 下载所有模型")
print("4 - 手动选择模型")
print("0 - 退出")

try:
    choice = input("\n请输入选择 (默认为1): ").strip()
    if not choice:
        choice = "1"
except (KeyboardInterrupt, EOFError):
    print("\n👋 用户取消下载")
    sys.exit(0)

selected_models = []

if choice == "1":
    selected_models = [m for m in models if m['priority'] == 'high']
elif choice == "2":
    selected_models = [m for m in models if m['priority'] in ['high', 'medium']]
elif choice == "3":
    selected_models = models
elif choice == "4":
    print("\n请选择要下载的模型 (用空格分隔数字):")
    try:
        indices = input("模型编号: ").strip().split()
        for idx in indices:
            if idx.isdigit() and 1 <= int(idx) <= len(models):
                selected_models.append(models[int(idx)-1])
    except:
        print("❌ 输入格式错误")
        sys.exit(1)
elif choice == "0":
    print("👋 用户选择退出")
    sys.exit(0)
else:
    print("❌ 无效选择")
    sys.exit(1)

if not selected_models:
    print("❌ 未选择任何模型")
    sys.exit(1)

print(f"\n🔄 开始下载 {len(selected_models)} 个模型...")

success_count = 0
for i, model in enumerate(selected_models, 1):
    try:
        print(f"\n📦 ({i}/{len(selected_models)}) 下载 {model['name']}...")
        print(f"   描述: {model['description']}")
        print(f"   预估大小: {model['size']}")
        
        # 下载模型
        model_obj = SentenceTransformer(model['name'], cache_folder=cache_dir)
        
        print(f"✅ {model['name']} 下载完成")
        success_count += 1
        
        # 简单测试
        test_sentences = ["Hello world", "你好世界"]
        embeddings = model_obj.encode(test_sentences)
        print(f"   ✓ 模型测试通过，输出维度: {embeddings.shape}")
        
    except Exception as e:
        print(f"❌ {model['name']} 下载失败: {str(e)}")

print(f"\n📊 下载统计: {success_count}/{len(selected_models)} 个模型下载成功")

if success_count > 0:
    print("🎉 模型下载完成！")
    print(f"📁 模型存储位置: {cache_dir}")
else:
    print("❌ 所有模型下载失败")
    sys.exit(1)
EOF

# 执行下载
echo "🚀 开始执行模型下载..."
python3 /tmp/download_st_models.py

# 清理临时文件
rm -f /tmp/download_st_models.py

echo ""
echo "📍 Sentence-Transformers模型信息:"
echo "   - 缓存位置: ~/.cache/sentence_transformers"  
echo "   - 用途: 文本向量化、句子相似度计算"
echo "   - 支持: 英文、多语言文本处理"

echo ""
echo "✅ Sentence-Transformers模型下载脚本执行完成！"