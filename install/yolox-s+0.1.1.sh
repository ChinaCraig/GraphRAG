#!/bin/sh

# yolox-s 模型下载脚本 v0.1.1
# YOLOX-S文档布局检测模型(小型)，速度快，适合实时处理
# 可单独执行此脚本完成模型下载

set -e

echo "=== yolox-s 模型下载脚本 v0.1.1 ==="
echo "📄 正在下载YOLOX-S文档布局检测模型..."
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

# 检查依赖
echo "🔍 检查依赖..."
python3 -c "
try:
    import requests
    print('✅ requests 已安装')
except ImportError:
    print('❌ 缺少依赖: requests')
    print('请先运行: pip install requests')
    exit(1)
" 2>/dev/null

if [ $? -ne 0 ]; then
    echo ""
    echo "💡 提示: 请先安装requests"
    echo "   pip install requests"
    exit 1
fi

# 创建模型下载Python脚本
cat > /tmp/download_yolox_s.py << 'EOF'
import os
import sys
import requests
from pathlib import Path

# 模型信息
MODEL_NAME = "yolox_s.onnx"
MODEL_DESC = "YOLOX-S文档布局检测模型(小型)"
MODEL_SIZE = "~34MB"

# 配置GitHub镜像源 - 多个备用源提高成功率
original_url = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx"

# 如果用户设置了GITHUB_MIRROR，优先使用
github_mirror = os.environ.get('GITHUB_MIRROR')
if github_mirror:
    mirror_urls = [github_mirror + original_url]
    print(f"🪞 使用用户配置的GitHub镜像: {github_mirror}")
else:
    # 多个稳定的镜像源，按稳定性排序
    mirrors = [
        'https://mirror.ghproxy.com/',           # 镜像代理
        'https://ghproxy.net/',                 # 备用代理1
        'https://gh-proxy.com/',                # 备用代理2  
        'https://ghps.cc/',                     # 备用代理3
        '',                                     # 官方源（最后尝试）
    ]
    
    mirror_urls = []
    for mirror in mirrors:
        if mirror:
            mirror_urls.append(mirror + original_url)
        else:
            mirror_urls.append(original_url)
    
    print("🪞 自动使用多个GitHub镜像源（提高下载成功率）")
    print("   镜像源列表:")
    for i, url in enumerate(mirror_urls):
        if i == len(mirror_urls) - 1:
            print(f"   {i+1}. GitHub官方源")
        else:
            mirror_name = url.split('//')[1].split('/')[0]
            print(f"   {i+1}. {mirror_name}")
    print("   如需使用特定源，请设置 GITHUB_MIRROR 环境变量")

print(f"📄 模型: {MODEL_NAME}")
print(f"📝 描述: {MODEL_DESC}")
print(f"📦 大小: {MODEL_SIZE}")
print("")

# 设置模型缓存目录
cache_dir = os.path.expanduser("~/.cache/unstructured")
models_dir = os.path.join(cache_dir, "models")
os.makedirs(models_dir, exist_ok=True)

model_path = os.path.join(models_dir, MODEL_NAME)

print(f"📁 模型存储目录: {models_dir}")
print(f"📁 模型文件路径: {model_path}")
print("")

# 检查文件是否已存在
if os.path.exists(model_path):
    file_size = os.path.getsize(model_path)
    print(f"✓ {MODEL_NAME} 已存在，文件大小: {file_size / 1024 / 1024:.1f}MB")
    print("⏭️  跳过下载")
    
    # 创建配置说明
    config_info = f"""
# YOLOX-S模型配置说明
# 
# 模型位置: {models_dir}/{MODEL_NAME}
# 模型大小: {file_size / 1024 / 1024:.1f}MB
# 
# 在Unstructured配置中使用:
# pdf:
#   hi_res_model_name: "yolox-s"
#   model_path: "{models_dir}"
# 
# 模型特点:
# - 类型: 轻量级文档布局检测
# - 速度: 快速，适合实时处理
# - 精度: 中等
# - 适用场景: 资源受限环境，快速处理
"""
    
    config_path = os.path.join(cache_dir, "yolox_s_config.txt")
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_info)
    
    print(f"📝 配置说明已保存: {config_path}")
    sys.exit(0)

def download_file(url, local_path, description, mirror_name=""):
    """下载文件到本地"""
    if mirror_name:
        print(f"🔄 尝试从 {mirror_name} 下载...")
    else:
        print(f"🔄 开始下载 {description}...")
    
    try:
        # 设置超时和重试参数
        import time
        
        print(f"🌐 下载地址: {url}")
        
        # 发送请求，设置超时
        response = requests.get(url, stream=True, timeout=(10, 30))
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        print(f"📦 文件大小: {total_size / 1024 / 1024:.1f}MB")
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r   下载进度: {percent:.1f}% ({downloaded / 1024 / 1024:.1f}MB/{total_size / 1024 / 1024:.1f}MB)", end='', flush=True)
        
        print(f"\n✅ {description} 下载完成")
        return True
        
    except requests.exceptions.Timeout:
        print(f"\n❌ 下载超时: 连接 {url.split('//')[1].split('/')[0]} 超时")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 连接失败: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ {description} 下载失败: {str(e)}")
        return False

def download_with_retry(urls, local_path, description):
    """使用多个镜像源重试下载"""
    print(f"🚀 开始下载 {MODEL_NAME}...")
    print(f"📋 共有 {len(urls)} 个镜像源可尝试")
    print("")
    
    for i, url in enumerate(urls):
        if i == len(urls) - 1:
            mirror_name = "GitHub官方源"
        else:
            mirror_name = f"镜像源{i+1}({url.split('//')[1].split('/')[0]})"
        
        print(f"[{i+1}/{len(urls)}] 尝试 {mirror_name}...")
        
        if download_file(url, local_path, description, mirror_name):
            return True
        
        if i < len(urls) - 1:
            print("⏭️  切换到下一个镜像源...")
            print("")
    
    return False

# 执行下载
if download_with_retry(mirror_urls, model_path, MODEL_DESC):
    
    # 验证文件
    if os.path.exists(model_path):
        file_size = os.path.getsize(model_path)
        print(f"✓ 文件验证成功，大小: {file_size / 1024 / 1024:.1f}MB")
        
        # 创建配置说明
        config_info = f"""
# YOLOX-S模型配置说明
# 
# 模型位置: {model_path}
# 模型大小: {file_size / 1024 / 1024:.1f}MB
# 下载时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 
# 在Unstructured配置中使用:
# pdf:
#   hi_res_model_name: "yolox-s"
#   model_path: "{models_dir}"
# 
# 模型特点:
# - 类型: 轻量级文档布局检测
# - 速度: 快速，适合实时处理
# - 精度: 中等
# - 适用场景: 资源受限环境，快速处理
"""
        
        config_path = os.path.join(cache_dir, "yolox_s_config.txt")
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_info)
        
        print(f"📝 配置说明已保存: {config_path}")
        
        print("")
        print("🎉 yolox-s 模型下载完成！")
        print("")
        print("📍 模型信息:")
        print(f"   - 存储位置: {model_path}")
        print("   - 用途: PDF文档布局检测、表格识别")
        print("   - 特点: 轻量级，速度快")
        print("   - 适用场景: 资源受限环境，实时处理")
        
    else:
        print("❌ 文件验证失败")
        sys.exit(1)
else:
    print("")
    print("💡 下载失败，但不用担心:")
    print("   - 模型会在首次使用时自动下载")
    print("   - 这不会影响程序正常运行")
    print("   - 可以稍后重新尝试运行此脚本")
    print("")
    print("🔧 故障排除建议:")
    print("   1. 检查网络连接和防火墙设置")
    print("   2. 尝试使用代理: export HTTP_PROXY=http://127.0.0.1:7890")
    print("   3. 使用官方源: export GITHUB_MIRROR=''")
    print("   4. 手动下载文件到: ~/.cache/unstructured/models/yolox_s.onnx")
    sys.exit(1)
EOF

# 执行下载
echo "🚀 开始执行模型下载..."
python3 /tmp/download_yolox_s.py

# 清理临时文件
rm -f /tmp/download_yolox_s.py

echo ""
echo "✅ yolox-s 模型下载脚本执行完成！"
