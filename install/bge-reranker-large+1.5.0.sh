#!/bin/sh

# bge-reranker-large 重排模型下载脚本 v1.5.0
# BGE重排模型，用于Cross-Encoder重排，提升检索精度
# 可单独执行此脚本完成模型下载

set -e

echo "=== bge-reranker-large 重排模型下载脚本 v1.5.0 ==="
echo "🎯 正在下载BGE重排模型（Cross-Encoder）..."
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

# 加载网络配置（如果存在）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NETWORK_CONFIG_ALL="$SCRIPT_DIR/.network_config.all"
NETWORK_CONFIG_PROXY="$SCRIPT_DIR/.network_config"
NETWORK_CONFIG_MIRROR="$SCRIPT_DIR/.network_config.mirror"
NETWORK_CONFIG_ENV="$SCRIPT_DIR/.network_config.env"

echo "🌐 检查网络配置..."
if [ -f "$NETWORK_CONFIG_ALL" ]; then
    echo "✅ 加载完整网络配置"
    . "$NETWORK_CONFIG_ALL"
else
    # 分别加载各个配置文件
    [ -f "$NETWORK_CONFIG_PROXY" ] && . "$NETWORK_CONFIG_PROXY" && echo "✅ 加载代理配置"
    [ -f "$NETWORK_CONFIG_MIRROR" ] && . "$NETWORK_CONFIG_MIRROR" && echo "✅ 加载镜像源配置"
    [ -f "$NETWORK_CONFIG_ENV" ] && . "$NETWORK_CONFIG_ENV" && echo "✅ 加载环境优化配置"
fi

# 显示当前网络配置状态
if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ] || [ -n "$ALL_PROXY" ]; then
    echo "🔗 代理: 已配置"
fi
if [ -n "$HF_ENDPOINT" ]; then
    echo "🪞 镜像源: $HF_ENDPOINT"
fi
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
cat > /tmp/download_bge_reranker_large.py << 'EOF'
from sentence_transformers import CrossEncoder
import os
import sys
import time

# 模型信息
MODEL_NAME = "BAAI/bge-reranker-large"
MODEL_DESC = "BGE重排模型（Cross-Encoder）"
MODEL_SIZE = "~560MB"

print(f"🎯 模型: {MODEL_NAME}")
print(f"📝 描述: {MODEL_DESC}")
print(f"📦 大小: {MODEL_SIZE}")
print("⭐ 特别说明: 这是用于提升检索精度的重排模型")
print("")

# 设置缓存目录
cache_dir = os.path.expanduser("~/.cache/huggingface")
os.makedirs(cache_dir, exist_ok=True)
print(f"📁 模型缓存目录: {cache_dir}")
print("")

# 设置环境变量以改善Ubuntu下的下载体验
os.environ['TOKENIZERS_PARALLELISM'] = 'false'  # 避免tokenizers警告
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = 'false'  # 确保显示进度条

# 优先使用稳定的阿里云镜像源
hf_endpoint = os.environ.get('HF_ENDPOINT')

# 检测并修复可能的不稳定镜像源
unstable_mirrors = [
    'https://mirrors.tuna.tsinghua.edu.cn/huggingface',
    'https://mirrors.bfsu.edu.cn/huggingface',
]

if hf_endpoint in unstable_mirrors:
    print(f"⚠️  检测到可能不稳定的镜像源: {hf_endpoint}")
    print("🔄 自动切换到稳定的阿里云镜像源")
    hf_endpoint = None

if not hf_endpoint:
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
    print("🪞 使用稳定的阿里云镜像源: https://hf-mirror.com")
    print("   这是经过验证的稳定镜像源，推荐使用")
else:
    print(f"🪞 使用配置的镜像源: {hf_endpoint}")

# 清除可能冲突的环境变量
if 'HUGGINGFACE_HUB_DEFAULT_ENDPOINT' in os.environ:
    if os.environ['HUGGINGFACE_HUB_DEFAULT_ENDPOINT'] in unstable_mirrors:
        print("🧹 清除不稳定的HUGGINGFACE_HUB_DEFAULT_ENDPOINT设置")
        del os.environ['HUGGINGFACE_HUB_DEFAULT_ENDPOINT']

# 确认最终使用的镜像源
final_hf_endpoint = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')
print(f"✅ 最终使用镜像源: {final_hf_endpoint}")

# 设置huggingface_hub使用镜像源
os.environ['HUGGINGFACE_HUB_DEFAULT_ENDPOINT'] = final_hf_endpoint

# 重试机制 - 重排模型重要性高，使用较多重试
MAX_RETRIES = 5
RETRY_DELAY = 10  # 更长的重试间隔

for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"🔄 开始下载 {MODEL_NAME} 模型... (尝试 {attempt}/{MAX_RETRIES})")
        if attempt > 1:
            print(f"   等待 {RETRY_DELAY} 秒后重试... (重排模型对检索精度很重要)")
            time.sleep(RETRY_DELAY)
        
        print("   这是一个大型重排模型(560MB)，下载可能需要较长时间...")
        print("   请确保网络连接稳定，并有足够的磁盘空间")
        print("   如果没有进度条显示，说明正在后台下载，请稍候...")
        print("   🎯 此模型专门用于提升多路召回的重排精度")
        
        # 下载模型 - CrossEncoder使用不同的参数
        model = CrossEncoder(MODEL_NAME)
    
        print(f"✅ {MODEL_NAME} 下载完成")
        
        # 重排模型测试
        print("🧪 进行重排模型测试...")
        test_pairs = [
            ["什么是机器学习？", "机器学习是人工智能的一个分支"],
            ["什么是机器学习？", "今天天气很好"],
            ["深度学习原理", "深度学习使用神经网络进行学习"],
            ["深度学习原理", "我喜欢吃苹果"],
        ]
        
        scores = model.predict(test_pairs)
        print(f"   ✓ 重排模型测试通过，相关性分数示例:")
        for i, (query, doc) in enumerate(test_pairs):
            print(f"      Query: {query[:20]}...")
            print(f"      Doc: {doc[:30]}...")
            print(f"      Score: {scores[i]:.4f}")
            print()
        
        print("")
        print("🎉 bge-reranker-large 重排模型下载完成！")
        print("")
        print("📍 模型信息:")
        print(f"   - 存储位置: {cache_dir}")
        print("   - 用途: Cross-Encoder重排、提升检索精度")
        print("   - 适用场景: 多路召回后的精确重排")
        print("   - 语言支持: 多语言，包括中文、英文")
        print("   - 架构: BERT-based Cross-Encoder")
        print("")
        print("🔧 使用说明:")
        print("   1. 在config/model.yaml中设置 reranker.enabled: true")
        print("   2. 重启服务即可启用重排功能")
        print("   3. 重排会显著提升检索精度，但会增加计算时间")
        
        # 下载成功，退出重试循环
        break
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ {MODEL_NAME} 下载失败 (尝试 {attempt}/{MAX_RETRIES}): {error_msg}")
        
        if attempt < MAX_RETRIES:
            if "Connection" in error_msg or "ProtocolError" in error_msg or "timeout" in error_msg.lower():
                print("🔄 检测到网络连接问题，准备重试...")
                print(f"   ⚠️  重排模型对检索精度很重要，将在 {RETRY_DELAY} 秒后重试")
                continue
            else:
                print("❌ 非网络错误，停止重试")
                break
        else:
            print("")
            print("❌ 所有重试均失败 - 重排模型下载失败！")
            print("💡 强烈建议的解决方案:")
            print("   1. 检查网络连接和稳定性")
            print("   2. 检查防火墙/代理设置")
            print("   3. 检查磁盘空间(至少需要700MB)")
            print("   4. 尝试使用更稳定的网络环境")
            print("   5. 稍后重新运行脚本")
            print("")
            print("🔧 网络问题解决方案:")
            print("   1. 使用代理: export HTTP_PROXY=http://127.0.0.1:7890")
            print("   2. 切换镜像源: export HF_ENDPOINT=https://mirrors.bfsu.edu.cn/huggingface")
            print("   3. 使用官方源: export HF_ENDPOINT=https://huggingface.co")
            print("   4. 重置环境: unset HF_ENDPOINT && unset HUGGINGFACE_HUB_DEFAULT_ENDPOINT")
            print("")
            print("⚠️  注意: 没有重排模型时系统会使用简单评分函数，精度会有所下降")
            sys.exit(1)
EOF

# 执行下载
echo "🚀 开始执行模型下载..."
python3 /tmp/download_bge_reranker_large.py

# 清理临时文件
rm -f /tmp/download_bge_reranker_large.py

echo ""
echo "✅ bge-reranker-large 重排模型下载脚本执行完成！"
