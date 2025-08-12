#!/bin/sh

# yolox-m 模型下载脚本 v0.1.1
# YOLOX-M文档布局检测模型(中型)，平衡速度和精度
# 可单独执行此脚本完成模型下载

set -e

echo "=== yolox-m 模型下载脚本 v0.1.1 ==="
echo "📄 正在下载YOLOX-M文档布局检测模型..."
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
cat > /tmp/download_yolox_m.py << 'EOF'
import os
import sys
import requests
from pathlib import Path

# 模型信息
MODEL_NAME = "yolox_m.onnx"
MODEL_DESC = "YOLOX-M文档布局检测模型(中型)"
MODEL_SIZE = "~97MB"
MODEL_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_m.onnx"

print(f"📄 模型: {MODEL_NAME}")
print(f"📝 描述: {MODEL_DESC}")
print(f"📦 大小: {MODEL_SIZE}")
print(f"🌐 下载地址: {MODEL_URL}")
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
# YOLOX-M模型配置说明
# 
# 模型位置: {models_dir}/{MODEL_NAME}
# 模型大小: {file_size / 1024 / 1024:.1f}MB
# 
# 在Unstructured配置中使用:
# pdf:
#   hi_res_model_name: "yolox-m"
#   model_path: "{models_dir}"
# 
# 模型特点:
# - 类型: 中等大小文档布局检测
# - 速度: 中等
# - 精度: 平衡性能
# - 适用场景: 生产环境，平衡速度和精度
"""
    
    config_path = os.path.join(cache_dir, "yolox_m_config.txt")
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_info)
    
    print(f"📝 配置说明已保存: {config_path}")
    sys.exit(0)

def download_file(url, local_path, description):
    """下载文件到本地"""
    print(f"🔄 开始下载 {description}...")
    
    try:
        # 发送请求
        response = requests.get(url, stream=True)
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
        
    except Exception as e:
        print(f"\n❌ {description} 下载失败: {str(e)}")
        return False

# 执行下载
print(f"🚀 开始下载 {MODEL_NAME}...")
print("⚠️  注意: 这是一个中等大小的模型(97MB)，下载可能需要几分钟")
if download_file(MODEL_URL, model_path, MODEL_DESC):
    
    # 验证文件
    if os.path.exists(model_path):
        file_size = os.path.getsize(model_path)
        print(f"✓ 文件验证成功，大小: {file_size / 1024 / 1024:.1f}MB")
        
        # 创建配置说明
        config_info = f"""
# YOLOX-M模型配置说明
# 
# 模型位置: {model_path}
# 模型大小: {file_size / 1024 / 1024:.1f}MB
# 下载时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 
# 在Unstructured配置中使用:
# pdf:
#   hi_res_model_name: "yolox-m"
#   model_path: "{models_dir}"
# 
# 模型特点:
# - 类型: 中等大小文档布局检测
# - 速度: 中等
# - 精度: 平衡性能
# - 适用场景: 生产环境，平衡速度和精度
"""
        
        config_path = os.path.join(cache_dir, "yolox_m_config.txt")
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_info)
        
        print(f"📝 配置说明已保存: {config_path}")
        
        print("")
        print("🎉 yolox-m 模型下载完成！")
        print("")
        print("📍 模型信息:")
        print(f"   - 存储位置: {model_path}")
        print("   - 用途: PDF文档布局检测、表格识别")
        print("   - 特点: 中等大小，平衡速度和精度")
        print("   - 适用场景: 生产环境，平衡性能需求")
        
    else:
        print("❌ 文件验证失败")
        sys.exit(1)
else:
    print("")
    print("💡 下载失败，但不用担心:")
    print("   - 模型会在首次使用时自动下载")
    print("   - 这不会影响程序正常运行")
    print("   - 可以稍后重新尝试运行此脚本")
    sys.exit(1)
EOF

# 执行下载
echo "🚀 开始执行模型下载..."
python3 /tmp/download_yolox_m.py

# 清理临时文件
rm -f /tmp/download_yolox_m.py

echo ""
echo "✅ yolox-m 模型下载脚本执行完成！"
