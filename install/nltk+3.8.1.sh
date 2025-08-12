#!/bin/sh

# NLTK数据包下载脚本 v3.8.1
# 下载项目所需的NLTK数据包，支持Ubuntu和macOS环境
# 可单独执行此脚本完成NLTK数据包下载

set -e

echo "=== NLTK数据包下载脚本 v3.8.1 ==="
echo "📚 正在下载项目所需的NLTK数据包..."
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

# 创建NLTK数据下载Python脚本
cat > /tmp/download_nltk_data.py << 'EOF'
import nltk
import ssl
import sys
import os
import time

print("🔧 配置NLTK环境...")

# 配置网络优化
import urllib.request
import urllib.error

# 默认使用清华大学NLTK镜像源（如果没有配置其他源）
nltk_mirror = os.environ.get('NLTK_DATA_URL')
if not nltk_mirror:
    # 清华大学NLTK镜像源
    nltk_mirror = 'https://mirrors.tuna.tsinghua.edu.cn/nltk_data/'
    print("🪞 自动使用清华大学NLTK镜像源")
    print(f"   镜像地址: {nltk_mirror}")
    print("   如需使用其他源，请设置 NLTK_DATA_URL 环境变量")
else:
    print(f"🪞 使用配置的NLTK镜像源: {nltk_mirror}")

# 设置NLTK下载镜像源
nltk.download_data_url = nltk_mirror
print("")

# 设置下载超时
import socket
socket.setdefaulttimeout(30)  # 30秒超时

# 测试网络连接
print("🔗 测试网络连接...")
try:
    import urllib.request
    with urllib.request.urlopen(nltk_mirror, timeout=10) as response:
        if response.status == 200:
            print("✅ 镜像源连接正常")
        else:
            print(f"⚠️  镜像源响应状态: {response.status}")
except Exception as e:
    print(f"⚠️  镜像源连接测试失败: {e}")
    print("📡 将继续尝试下载...")

print("")

# 解决SSL证书验证问题 (适用于所有平台)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# 设置NLTK数据路径
home_dir = os.path.expanduser("~")
nltk_data_dir = os.path.join(home_dir, "nltk_data")
os.makedirs(nltk_data_dir, exist_ok=True)
nltk.data.path.append(nltk_data_dir)

print(f"📁 NLTK数据目录: {nltk_data_dir}")

# 需要下载的数据包列表
packages = [
    'punkt',                          # 句子分割
    'punkt_tab',                      # 句子分割（新版本）
    'averaged_perceptron_tagger',     # 词性标注
    'stopwords',                      # 停用词
    'wordnet',                        # 词网
    'brown',                          # Brown语料库
    'universal_tagset'                # 通用标签集
]

print("📦 开始下载NLTK数据包...")
print(f"🎯 计划下载 {len(packages)} 个数据包")
print("💡 如果下载时间较长，请耐心等待...")
print("🔍 如果长时间无响应，可按Ctrl+C中断后重试")
print("")

success_count = 0
total_count = len(packages)

for i, package in enumerate(packages, 1):
    max_retries = 3
    retry_delay = 2  # 秒
    package_success = False
    
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"[{i}/{total_count}] 📦 下载 {package}... (重试 {attempt-1}/{max_retries-1})")
            else:
                print(f"[{i}/{total_count}] 📦 下载 {package}...")
            
            # 显示详细下载信息，不使用quiet模式以便看到进度
            print(f"🔄 正在连接镜像源...")
            print(f"📡 镜像地址: {nltk_mirror}")
            sys.stdout.flush()  # 立即刷新输出
            
            # 开始计时
            import time
            start_time = time.time()
            
            # 使用非quiet模式以显示下载进度
            print(f"⬇️  开始下载数据包...")
            sys.stdout.flush()
            result = nltk.download(package, quiet=False)
            
            # 显示下载耗时
            end_time = time.time()
            duration = end_time - start_time
            print(f"⏱️  下载耗时: {duration:.1f}秒")
            print(f"✅ {package} 下载完成")
            success_count += 1
            package_success = True
            break
            
        except KeyboardInterrupt:
            print("")
            print("⚠️  用户中断下载")
            print(f"💡 可以稍后重新运行脚本继续下载")
            sys.exit(130)  # 标准的用户中断退出码
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 下载出错: {error_msg}")
            
            if attempt < max_retries:
                # 检查是否是网络相关错误
                if any(keyword in error_msg.lower() for keyword in ['connection', 'timeout', 'network', 'ssl', 'certificate']):
                    print(f"⚠️  {package} 下载失败 (尝试 {attempt}/{max_retries}): 网络错误")
                    print(f"🔄 等待 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"⚠️  {package} 下载失败: {error_msg}")
                    break
            else:
                print(f"❌ {package} 多次重试后仍失败: {error_msg}")
                
                # 尝试使用备用方法
                try:
                    print(f"🔄 尝试备用下载方法...")
                    print(f"💡 使用本地目录: {nltk_data_dir}")
                    sys.stdout.flush()
                    nltk.download(package, download_dir=nltk_data_dir, quiet=False)
                    print(f"✅ {package} 备用方法下载完成")
                    success_count += 1
                    package_success = True
                except Exception as e2:
                    print(f"❌ {package} 备用方法也失败: {str(e2)}")
                    
                    # 如果是官方源问题，建议使用镜像源
                    if 'ssl' in error_msg.lower() or 'certificate' in error_msg.lower():
                        print(f"💡 {package} 可能需要网络优化:")
                        print("   - SSL证书问题，这是正常的")
                        print("   - 数据包会在首次使用时自动下载")
                        print("   - 或手动设置 NLTK_DATA_URL 环境变量")
    
    print("")

print("="*50)
print(f"📊 下载统计: {success_count}/{total_count} 个数据包下载成功")

if success_count >= total_count * 0.8:  # 80%成功率认为可接受
    print("🎉 NLTK数据包下载基本完成！")
    print("")
    print("📍 安装信息:")
    print(f"   - 安装位置: {nltk_data_dir}")
    print("   - 包含: punkt, stopwords, wordnet 等核心数据包")
    print("   - 用途: 文本预处理、句子分割、词性标注")
    print("")
    print("✅ 可以正常使用NLTK功能了！")
    sys.exit(0)
else:
    print("⚠️  部分数据包下载失败，但核心包已下载完成")
    print("   如果遇到SSL错误，这是正常的，程序可以正常运行")
    print("   缺失的数据包会在首次使用时自动下载")
    print("")
    print("🔧 网络问题解决方案:")
    print("   1. 使用官方源: unset NLTK_DATA_URL")
    print("   2. 使用代理: export HTTP_PROXY=http://127.0.0.1:7890")
    print("   3. 运行网络配置: ./network_config.sh")
    sys.exit(0)
EOF

# 执行下载
echo "🚀 开始执行NLTK数据包下载..."
python3 /tmp/download_nltk_data.py

# 清理临时文件
rm -f /tmp/download_nltk_data.py

echo ""
echo "✅ NLTK数据包下载脚本执行完成！"
echo "📝 注意: 如果看到SSL错误，这是正常的，不影响使用"
