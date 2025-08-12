#!/bin/sh

# all-MiniLM-L6-v2 模型下载脚本 v2.7.0
# 轻量级英文模型，速度快，适合资源受限环境
# 可单独执行此脚本完成模型下载

set -e

echo "=== all-MiniLM-L6-v2 模型下载脚本 v2.7.0 ==="
echo "🤖 正在下载轻量级英文Sentence-Transformers模型..."
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
cat > /tmp/download_all_minilm_l6_v2.py << 'EOF'
from sentence_transformers import SentenceTransformer
import os
import sys
import time

# 模型信息
MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_DESC = "轻量级英文模型，速度快"
MODEL_SIZE = "~90MB"

print(f"🤖 模型: {MODEL_NAME}")
print(f"📝 描述: {MODEL_DESC}")
print(f"📦 大小: {MODEL_SIZE}")
print("")

# 设置缓存目录
cache_dir = os.path.expanduser("~/.cache/sentence_transformers")
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

# 网络优化配置
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置requests会话以支持重试和代理
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# 应用代理配置（如果存在）
proxies = {}
if os.environ.get('HTTP_PROXY'):
    proxies['http'] = os.environ.get('HTTP_PROXY')
if os.environ.get('HTTPS_PROXY'):
    proxies['https'] = os.environ.get('HTTPS_PROXY')
if os.environ.get('ALL_PROXY'):
    proxies['http'] = os.environ.get('ALL_PROXY')
    proxies['https'] = os.environ.get('ALL_PROXY')

if proxies:
    session.proxies.update(proxies)
    print(f"🔗 使用代理配置: {list(proxies.values())[0]}")

# 应用镜像源配置
hf_endpoint = os.environ.get('HF_ENDPOINT')
if hf_endpoint:
    print(f"🪞 使用镜像源: {hf_endpoint}")
    # 设置huggingface_hub使用镜像源
    os.environ['HUGGINGFACE_HUB_DEFAULT_ENDPOINT'] = hf_endpoint

# 重试机制
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒

for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"🔄 开始下载 {MODEL_NAME} 模型... (尝试 {attempt}/{MAX_RETRIES})")
        if attempt > 1:
            print(f"   等待 {RETRY_DELAY} 秒后重试...")
            time.sleep(RETRY_DELAY)
        
        print("   这可能需要几分钟时间，请耐心等待...")
        print("   如果没有进度条显示，说明正在后台下载，请稍候...")
        
        # 下载模型，设置超时和重试参数
        model = SentenceTransformer(MODEL_NAME, cache_folder=cache_dir)
        
        print(f"✅ {MODEL_NAME} 下载完成")
        
        # 简单测试
        print("🧪 进行模型测试...")
        test_sentences = [
            "Hello world",
            "This is a test sentence",
            "Machine learning is amazing"
        ]
        embeddings = model.encode(test_sentences)
        print(f"   ✓ 模型测试通过，输出维度: {embeddings.shape}")
        print(f"   ✓ 向量维度: {embeddings.shape[1]}")
        
        print("")
        print("🎉 all-MiniLM-L6-v2 模型下载完成！")
        print("")
        print("📍 模型信息:")
        print(f"   - 存储位置: {cache_dir}")
        print("   - 用途: 文本向量化、语义相似度计算")
        print("   - 适用场景: 快速原型、资源受限环境")
        print("   - 语言支持: 英文")
        
        # 下载成功，退出重试循环
        break
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ {MODEL_NAME} 下载失败 (尝试 {attempt}/{MAX_RETRIES}): {error_msg}")
        
        if attempt < MAX_RETRIES:
            if "Connection" in error_msg or "ProtocolError" in error_msg or "timeout" in error_msg.lower():
                print("🔄 检测到网络连接问题，准备重试...")
                continue
            else:
                print("❌ 非网络错误，停止重试")
                break
        else:
            print("")
            print("❌ 所有重试均失败")
            print("💡 可能的解决方案:")
            print("   1. 检查网络连接和稳定性")
            print("   2. 检查防火墙/代理设置")
            print("   3. 尝试使用不同的网络环境")
            print("   4. 稍后重新运行脚本")
            print("   5. 模型会在首次使用时自动下载")
            print("")
            print("🔧 网络问题解决方案:")
            print("   1. 配置代理: ./network_config.sh -> 选择1")
            print("   2. 使用镜像源: ./network_config.sh -> 选择2")
            print("   3. 环境优化: ./network_config.sh -> 选择3")
            print("   4. 或者: export HF_HUB_DISABLE_PROGRESS_BARS=false")
            print("   5. 或者: pip install --upgrade requests urllib3")
            print("")
            print("💡 快速配置命令:")
            print("   ./network_config.sh  # 运行网络配置向导")
            sys.exit(1)
EOF

# 执行下载
echo "🚀 开始执行模型下载..."
python3 /tmp/download_all_minilm_l6_v2.py

# 清理临时文件
rm -f /tmp/download_all_minilm_l6_v2.py

echo ""
echo "✅ all-MiniLM-L6-v2 模型下载脚本执行完成！"
