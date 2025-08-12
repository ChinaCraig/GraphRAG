#!/bin/sh

# all-mpnet-base-v2 模型下载脚本 v2.7.0
# 英文高精度模型，适合生产环境和高精度要求
# 可单独执行此脚本完成模型下载

set -e

echo "=== all-mpnet-base-v2 模型下载脚本 v2.7.0 ==="
echo "🤖 正在下载高精度英文Sentence-Transformers模型..."
echo ""

# 检查Python是否可用
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 错误: 未找到python3命令"
    echo "   Ubuntu安装命令: sudo apt-get install python3"
    echo "   macOS安装命令: brew install python3"
    exit 1
fi

echo "🐍 Python版本信息:"
python3 --version
echo ""

# 检查sentence-transformers是否已安装
echo "🔍 检查依赖..."
python3 -c "
try:
    import sentence_transformers
    print('✅ sentence-transformers 已安装')
except ImportError:
    print('❌ 缺少依赖: sentence-transformers')
    print('请先运行: pip install sentence-transformers')
    exit(1)
" 2>/dev/null

if [ $? -ne 0 ]; then
    echo ""
    echo "💡 提示: 请先安装sentence-transformers"
    echo "   pip install sentence-transformers"
    exit 1
fi

# 创建模型下载Python脚本
cat > /tmp/download_all_mpnet_base_v2.py << 'EOF'
from sentence_transformers import SentenceTransformer
import os
import sys

# 模型信息
MODEL_NAME = "all-mpnet-base-v2"
MODEL_DESC = "英文高精度模型"
MODEL_SIZE = "~420MB"

print(f"🤖 模型: {MODEL_NAME}")
print(f"📝 描述: {MODEL_DESC}")
print(f"📦 大小: {MODEL_SIZE}")
print("")

# 设置缓存目录
cache_dir = os.path.expanduser("~/.cache/sentence_transformers")
os.makedirs(cache_dir, exist_ok=True)
print(f"📁 模型缓存目录: {cache_dir}")
print("")

try:
    print(f"🔄 开始下载 {MODEL_NAME} 模型...")
    print("   这是一个大型模型(420MB)，下载可能需要较长时间...")
    print("   请确保网络连接稳定，并有足够的磁盘空间")
    
    # 下载模型
    model = SentenceTransformer(MODEL_NAME, cache_folder=cache_dir)
    
    print(f"✅ {MODEL_NAME} 下载完成")
    
    # 简单测试
    print("🧪 进行模型测试...")
    test_sentences = [
        "Artificial intelligence is transforming the world",
        "Machine learning algorithms are becoming more sophisticated",
        "Natural language processing enables computers to understand text"
    ]
    embeddings = model.encode(test_sentences)
    print(f"   ✓ 模型测试通过，输出维度: {embeddings.shape}")
    print(f"   ✓ 向量维度: {embeddings.shape[1]}")
    
    # 计算相似度示例
    from sentence_transformers.util import cos_sim
    similarity = cos_sim(embeddings[0], embeddings[1])
    print(f"   ✓ 句子相似度测试: {similarity.item():.4f}")
    
    print("")
    print("🎉 all-mpnet-base-v2 模型下载完成！")
    print("")
    print("📍 模型信息:")
    print(f"   - 存储位置: {cache_dir}")
    print("   - 用途: 高精度文本向量化、语义理解")
    print("   - 适用场景: 生产环境、高精度要求的应用")
    print("   - 语言支持: 英文")
    print("   - 性能: 高精度，但计算相对较慢")
    
except Exception as e:
    print(f"❌ {MODEL_NAME} 下载失败: {str(e)}")
    print("")
    print("💡 可能的解决方案:")
    print("   1. 检查网络连接")
    print("   2. 检查磁盘空间(至少需要500MB)")
    print("   3. 尝试重新运行脚本")
    print("   4. 模型会在首次使用时自动下载")
    sys.exit(1)
EOF

# 执行下载
echo "🚀 开始执行模型下载..."
python3 /tmp/download_all_mpnet_base_v2.py

# 清理临时文件
rm -f /tmp/download_all_mpnet_base_v2.py

echo ""
echo "✅ all-mpnet-base-v2 模型下载脚本执行完成！"
