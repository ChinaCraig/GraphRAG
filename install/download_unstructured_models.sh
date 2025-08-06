#!/bin/bash

# Unstructured模型下载脚本
# 下载用于文档处理的ONNX模型

set -e

echo "=== Unstructured文档处理模型下载脚本 ==="
echo "正在下载文档布局检测和OCR相关模型..."

# 检查Python是否可用
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3命令"
    exit 1
fi

# 创建模型下载Python脚本
cat > /tmp/download_unstructured_models.py << 'EOF'
import os
import sys
import requests
from pathlib import Path
import tempfile

def download_file(url, local_path, description):
    """下载文件到本地"""
    print(f"📦 下载 {description}...")
    print(f"   URL: {url}")
    print(f"   保存位置: {local_path}")
    
    try:
        # 创建目录
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # 下载文件
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r   进度: {percent:.1f}%", end='', flush=True)
        
        print(f"\n✅ {description} 下载完成")
        return True
        
    except Exception as e:
        print(f"\n❌ {description} 下载失败: {str(e)}")
        return False

# 设置模型缓存目录
cache_dir = os.path.expanduser("~/.cache/unstructured")
models_dir = os.path.join(cache_dir, "models")
os.makedirs(models_dir, exist_ok=True)

print(f"📁 模型缓存目录: {models_dir}")

# 模型列表（这些是常用的开源模型）
models = [
    {
        'name': 'yolox_s.onnx',
        'description': 'YOLOX-S文档布局检测模型 (小型)',
        'url': 'https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx',
        'size': '~34MB',
        'priority': 'high'
    },
    {
        'name': 'yolox_m.onnx', 
        'description': 'YOLOX-M文档布局检测模型 (中型)',
        'url': 'https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_m.onnx',
        'size': '~97MB',
        'priority': 'medium'
    },
    {
        'name': 'yolox_l.onnx',
        'description': 'YOLOX-L文档布局检测模型 (大型)',
        'url': 'https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_l.onnx',
        'size': '~207MB', 
        'priority': 'low'
    }
]

print("🤖 可下载的模型列表:")
for i, model in enumerate(models, 1):
    print(f"  {i}. {model['name']}")
    print(f"     - 描述: {model['description']}")
    print(f"     - 大小: {model['size']}")
    print(f"     - 优先级: {model['priority']}")
    print()

print("请选择要下载的模型:")
print("1 - 下载YOLOX-S (推荐，轻量级)")
print("2 - 下载YOLOX-S和YOLOX-M (平衡)")
print("3 - 下载所有模型")
print("0 - 跳过模型下载")

try:
    choice = input("\n请输入选择 (默认为1): ").strip()
    if not choice:
        choice = "1"
except (KeyboardInterrupt, EOFError):
    print("\n👋 用户取消下载")
    sys.exit(0)

selected_models = []

if choice == "1":
    selected_models = [models[0]]  # 只下载YOLOX-S
elif choice == "2":
    selected_models = models[:2]   # 下载YOLOX-S和YOLOX-M
elif choice == "3":
    selected_models = models       # 下载所有模型
elif choice == "0":
    print("⏭️  跳过模型下载")
    sys.exit(0)
else:
    print("❌ 无效选择，默认下载YOLOX-S")
    selected_models = [models[0]]

if not selected_models:
    print("❌ 未选择任何模型")
    sys.exit(1)

print(f"\n🔄 开始下载 {len(selected_models)} 个模型...")

success_count = 0
for i, model in enumerate(selected_models, 1):
    model_path = os.path.join(models_dir, model['name'])
    
    # 检查文件是否已存在
    if os.path.exists(model_path):
        print(f"✓ {model['name']} 已存在，跳过下载")
        success_count += 1
        continue
    
    print(f"\n📦 ({i}/{len(selected_models)}) 开始下载...")
    if download_file(model['url'], model_path, model['description']):
        success_count += 1

print(f"\n📊 下载统计: {success_count}/{len(selected_models)} 个模型下载/验证成功")

if success_count > 0:
    print("🎉 Unstructured模型下载完成！")
    print(f"📁 模型存储位置: {models_dir}")
    
    # 创建配置说明
    config_info = f"""
# Unstructured模型配置说明
# 
# 模型位置: {models_dir}
# 
# 在Unstructured.yaml中配置:
# pdf:
#   hi_res_model_name: "yolox-s"  # 对应 yolox_s.onnx
#   model_path: "{models_dir}"    # 模型路径
# 
# 可用模型:
# - yolox-s: 轻量级，速度快 (~34MB)
# - yolox-m: 中等大小，平衡性能 (~97MB)  
# - yolox-l: 大型模型，最高精度 (~207MB)
"""
    
    with open(os.path.join(cache_dir, "README.txt"), 'w', encoding='utf-8') as f:
        f.write(config_info)
    
    print("📝 配置说明已保存到: ~/.cache/unstructured/README.txt")
else:
    print("❌ 所有模型下载失败")
    print("💡 提示: 这些模型会在首次使用时自动下载")
    print("        跳过手动下载不会影响程序正常运行")
EOF

# 执行下载
echo "🚀 开始执行模型下载..."
python3 /tmp/download_unstructured_models.py

# 清理临时文件
rm -f /tmp/download_unstructured_models.py

echo ""
echo "📍 Unstructured模型信息:"
echo "   - 缓存位置: ~/.cache/unstructured/models"
echo "   - 用途: PDF文档布局检测、表格识别"  
echo "   - 模型类型: YOLOX ONNX模型"
echo "   - 配置: 在Unstructured.yaml中指定模型路径"

echo ""
echo "✅ Unstructured模型下载脚本执行完成！"
echo "💡 注意: 如果下载失败，模型会在首次使用时自动下载"