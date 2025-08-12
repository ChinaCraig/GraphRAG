#!/bin/sh

# paraphrase-multilingual-mpnet-base-v2 模型下载脚本 v2.7.0
# 多语言模型（包含中文），项目主要使用的嵌入模型
# 可单独执行此脚本完成模型下载

set -e

echo "=== paraphrase-multilingual-mpnet-base-v2 模型下载脚本 v2.7.0 ==="
echo "🤖 正在下载多语言Sentence-Transformers模型..."
echo "📝 注意: 这是项目主要使用的嵌入模型"
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
cat > /tmp/download_paraphrase_multilingual_mpnet_base_v2.py << 'EOF'
from sentence_transformers import SentenceTransformer
import os
import sys
import time

# 模型信息
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
MODEL_DESC = "多语言模型（包含中文）"
MODEL_SIZE = "~470MB"

print(f"🤖 模型: {MODEL_NAME}")
print(f"📝 描述: {MODEL_DESC}")
print(f"📦 大小: {MODEL_SIZE}")
print("⭐ 特别说明: 这是项目配置文件中指定的主要嵌入模型")
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

# 确认最终使用的镜像源
final_hf_endpoint = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')
print(f"✅ 最终使用镜像源: {final_hf_endpoint}")

# 设置huggingface_hub使用镜像源
os.environ['HUGGINGFACE_HUB_DEFAULT_ENDPOINT'] = final_hf_endpoint

# 重试机制 - 对于项目主要模型，提高重试次数
MAX_RETRIES = 5  # 项目主要模型，提高重试次数
RETRY_DELAY = 10  # 更长的重试间隔

for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"🔄 开始下载 {MODEL_NAME} 模型... (尝试 {attempt}/{MAX_RETRIES})")
        if attempt > 1:
            print(f"   等待 {RETRY_DELAY} 秒后重试... (项目主要模型，耐心等待)")
            time.sleep(RETRY_DELAY)
        
        print("   这是一个大型多语言模型(470MB)，下载可能需要较长时间...")
        print("   请确保网络连接稳定，并有足够的磁盘空间")
        print("   如果没有进度条显示，说明正在后台下载，请稍候...")
        print("   ⭐ 这是项目的主要嵌入模型，建议优先下载")
        
        # 下载模型
        model = SentenceTransformer(MODEL_NAME, cache_folder=cache_dir)
    
        print(f"✅ {MODEL_NAME} 下载完成")
        
        # 多语言测试
        print("🧪 进行多语言模型测试...")
        test_sentences = [
            "Hello, this is an English sentence.",
            "你好，这是一个中文句子。",
            "Bonjour, ceci est une phrase en français.",
            "Hola, esta es una oración en español."
        ]
        embeddings = model.encode(test_sentences)
        print(f"   ✓ 模型测试通过，输出维度: {embeddings.shape}")
        print(f"   ✓ 向量维度: {embeddings.shape[1]}")
        
        # 计算中英文相似度示例
        from sentence_transformers.util import cos_sim
        english_text = "This is a test sentence"
        chinese_text = "这是一个测试句子"
        
        eng_emb = model.encode([english_text])
        chi_emb = model.encode([chinese_text])
        similarity = cos_sim(eng_emb, chi_emb)
        print(f"   ✓ 中英文相似度测试: {similarity.item():.4f}")
        
        print("")
        print("🎉 paraphrase-multilingual-mpnet-base-v2 模型下载完成！")
        print("")
        print("📍 模型信息:")
        print(f"   - 存储位置: {cache_dir}")
        print("   - 用途: 多语言文本向量化、跨语言语义理解")
        print("   - 适用场景: 中英文混合处理、多语言应用")
        print("   - 语言支持: 50+ 种语言，包括中文、英文")
        print("   - 项目状态: 主要嵌入模型 (config/model.yaml)")
        
        # 下载成功，退出重试循环
        break
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ {MODEL_NAME} 下载失败 (尝试 {attempt}/{MAX_RETRIES}): {error_msg}")
        
        if attempt < MAX_RETRIES:
            if "Connection" in error_msg or "ProtocolError" in error_msg or "timeout" in error_msg.lower():
                print("🔄 检测到网络连接问题，准备重试...")
                print(f"   ⚠️  主要模型下载异常重要，将在 {RETRY_DELAY} 秒后重试")
                continue
            else:
                print("❌ 非网络错误，停止重试")
                break
        else:
            print("")
            print("❌ 所有重试均失败 - 主要模型下载异常严重！")
            print("💡 强烈建议的解决方案:")
            print("   1. 检查网络连接和稳定性")
            print("   2. 检查防火墙/代理设置")
            print("   3. 检查磁盘空间(至少需要600MB)")
            print("   4. 尝试使用更稳定的网络环境")
            print("   5. 稍后重新运行脚本")
            print("   6. 模型会在首次使用时自动下载")
            print("")
            print("🔧 Ubuntu特定解决方案:")
            print("   - 尝试: export HF_HUB_DISABLE_PROGRESS_BARS=false")
            print("   - 或者: pip install --upgrade requests urllib3 certifi")
            print("   - 或者: pip install --upgrade huggingface_hub")
            print("")
            print("🔧 网络问题解决方案:")
            print("   1. 使用代理: export HTTP_PROXY=http://127.0.0.1:7890")
            print("   2. 切换镜像源: export HF_ENDPOINT=https://mirrors.bfsu.edu.cn/huggingface")
            print("   3. 使用官方源: export HF_ENDPOINT=https://huggingface.co")
            print("   4. 重置环境: unset HF_ENDPOINT && unset HUGGINGFACE_HUB_DEFAULT_ENDPOINT")
            print("")
            print("⚠️  注意: 这是项目的主要嵌入模型，建议优先解决此问题")
            sys.exit(1)
EOF

# 执行下载
echo "🚀 开始执行模型下载..."
python3 /tmp/download_paraphrase_multilingual_mpnet_base_v2.py

# 清理临时文件
rm -f /tmp/download_paraphrase_multilingual_mpnet_base_v2.py

echo ""
echo "✅ paraphrase-multilingual-mpnet-base-v2 模型下载脚本执行完成！"
