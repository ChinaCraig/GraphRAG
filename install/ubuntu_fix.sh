#!/bin/bash

# Ubuntu兼容性修复脚本
# 检测和修复GraphRAG install脚本在Ubuntu上的兼容性问题

echo "==========================================="
echo "    GraphRAG Ubuntu兼容性检测工具"
echo "==========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_status() {
    local status=$1
    local message=$2
    if [ "$status" = "OK" ]; then
        echo -e "✅ ${GREEN}$message${NC}"
    elif [ "$status" = "WARNING" ]; then
        echo -e "⚠️  ${YELLOW}$message${NC}"
    elif [ "$status" = "ERROR" ]; then
        echo -e "❌ ${RED}$message${NC}"
    else
        echo -e "ℹ️  ${BLUE}$message${NC}"
    fi
}

# 1. 检查操作系统
echo "🔍 检查运行环境..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    print_status "INFO" "操作系统: $NAME $VERSION"
    
    if [[ "$ID" == "ubuntu" ]]; then
        print_status "OK" "确认为Ubuntu系统"
        UBUNTU_VERSION=$(echo $VERSION_ID | cut -d. -f1)
        print_status "INFO" "Ubuntu版本: $UBUNTU_VERSION"
    else
        print_status "WARNING" "非Ubuntu系统，可能仍存在兼容性问题"
    fi
else
    print_status "WARNING" "无法检测操作系统信息"
fi

# 2. 检查Shell环境
echo ""
echo "🐚 检查Shell环境..."
print_status "INFO" "当前Shell: $SHELL"

# 检查/bin/sh指向
SH_TARGET=$(readlink -f /bin/sh 2>/dev/null || echo "/bin/sh")
print_status "INFO" "/bin/sh 指向: $SH_TARGET"

if [[ "$SH_TARGET" == *"dash"* ]]; then
    print_status "WARNING" "系统默认使用dash，可能影响脚本兼容性"
    FIX_NEEDED=true
elif [[ "$SH_TARGET" == *"bash"* ]]; then
    print_status "OK" "系统默认使用bash"
else
    print_status "WARNING" "未知的Shell类型: $SH_TARGET"
fi

# 检查bash版本
if command -v bash >/dev/null 2>&1; then
    BASH_VERSION=$(bash --version | head -n1 | grep -o '[0-9]\+\.[0-9]\+')
    print_status "OK" "Bash版本: $BASH_VERSION"
    
    # bash 4.0+支持大部分现代特性
    if [ "$(echo "$BASH_VERSION >= 4.0" | bc -l 2>/dev/null)" = "1" ]; then
        print_status "OK" "Bash版本支持现代特性"
    else
        print_status "WARNING" "Bash版本较旧，可能不支持某些特性"
        FIX_NEEDED=true
    fi
else
    print_status "ERROR" "未找到bash"
    exit 1
fi

# 3. 检查Python环境
echo ""
echo "🐍 检查Python环境..."
if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')
    print_status "OK" "Python3版本: $PYTHON_VERSION"
    
    # 检查pip
    if command -v pip3 >/dev/null 2>&1; then
        print_status "OK" "pip3已安装"
    else
        print_status "WARNING" "pip3未找到，可能需要安装"
        echo "          运行: sudo apt-get install python3-pip"
    fi
else
    print_status "ERROR" "未找到python3"
    echo "          运行: sudo apt-get install python3"
fi

# 4. 检查必要的系统工具
echo ""
echo "🔧 检查系统工具..."
tools=("curl" "wget" "bc")
for tool in "${tools[@]}"; do
    if command -v "$tool" >/dev/null 2>&1; then
        print_status "OK" "$tool 已安装"
    else
        print_status "WARNING" "$tool 未安装"
        echo "          运行: sudo apt-get install $tool"
    fi
done

# 5. 检查脚本文件权限
echo ""
echo "📁 检查脚本文件..."
script_files=("download_all_models.sh" "download_nltk_data.sh" "download_sentence_transformers.sh" "download_unstructured_models.sh")

for script in "${script_files[@]}"; do
    script_path="$SCRIPT_DIR/$script"
    if [ -f "$script_path" ]; then
        if [ -x "$script_path" ]; then
            print_status "OK" "$script 权限正确"
        else
            print_status "WARNING" "$script 缺少执行权限"
            echo "          运行: chmod +x $script_path"
        fi
    else
        print_status "ERROR" "$script 文件不存在"
    fi
done

# 6. 生成兼容性修复建议
echo ""
echo "🔧 兼容性修复建议:"
echo "========================================="

echo ""
echo "1️⃣  如果遇到语法错误，请确保使用bash运行："
echo "   bash download_all_models.sh"
echo "   # 而不是: sh download_all_models.sh"

echo ""
echo "2️⃣  如果在非交互式环境中运行，设置环境变量："
echo "   export DEBIAN_FRONTEND=noninteractive"
echo "   # 然后运行脚本"

echo ""
echo "3️⃣  Ubuntu系统建议的依赖安装："
echo "   sudo apt-get update"
echo "   sudo apt-get install -y python3 python3-pip python3-venv"
echo "   sudo apt-get install -y curl wget bc build-essential"

echo ""
echo "4️⃣  创建Python虚拟环境（推荐）："
echo "   python3 -m venv venv"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"

echo ""
echo "5️⃣  如果脚本仍然失败，请检查错误信息："
echo "   - 语法错误：确保使用bash运行"
echo "   - 权限错误：检查文件执行权限"
echo "   - 网络错误：检查网络连接和代理设置"
echo "   - Python错误：确保已安装对应的Python包"

# 7. 创建Ubuntu专用的运行脚本
echo ""
echo "📝 生成Ubuntu专用运行脚本..."

cat > "$SCRIPT_DIR/run_on_ubuntu.sh" << 'UBUNTU_EOF'
#!/bin/bash

# Ubuntu专用的GraphRAG模型下载脚本
# 解决兼容性问题的包装脚本

set -e

echo "🐧 Ubuntu专用GraphRAG模型下载脚本"
echo "=================================="

# 确保在正确的目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查bash
if ! command -v bash >/dev/null 2>&1; then
    echo "❌ 错误: 未找到bash"
    echo "   请安装: sudo apt-get install bash"
    exit 1
fi

# 检查权限
for script in download_*.sh; do
    if [ -f "$script" ] && [ ! -x "$script" ]; then
        echo "🔧 修复脚本权限: $script"
        chmod +x "$script"
    fi
done

# 设置环境变量
export DEBIAN_FRONTEND=noninteractive
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

# 强制使用bash运行主脚本
echo "🚀 使用bash强制执行主脚本..."
exec bash ./download_all_models.sh "$@"
UBUNTU_EOF

chmod +x "$SCRIPT_DIR/run_on_ubuntu.sh"
print_status "OK" "已创建Ubuntu专用脚本: run_on_ubuntu.sh"

echo ""
echo "✅ Ubuntu兼容性检测完成！"
echo ""
echo "📋 使用建议："
echo "   在Ubuntu上请使用以下命令运行："
echo "   cd $SCRIPT_DIR"
echo "   ./run_on_ubuntu.sh"
echo ""
echo "   或者直接使用bash："
echo "   bash download_all_models.sh"
