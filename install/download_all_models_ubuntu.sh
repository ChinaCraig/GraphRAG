#!/bin/bash

# GraphRAG项目模型一键下载脚本 - Ubuntu兼容版本
# 下载项目所需的所有AI模型和数据包
# 修复了Ubuntu/Linux兼容性问题

set -e

echo "========================================"
echo "    GraphRAG项目模型下载工具"
echo "    (Ubuntu兼容版本)"
echo "========================================"
echo ""

# 获取脚本所在目录 - 使用兼容性更好的方法
if [ -n "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    # 回退方法，适用于dash等shell
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📁 项目根目录: $PROJECT_ROOT"
echo "📁 安装脚本目录: $SCRIPT_DIR"
echo ""

# 检查Python环境 - 使用POSIX兼容的重定向
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 错误: 未找到python3命令"
    echo "   请确保已安装Python 3.10或更高版本"
    echo "   Ubuntu安装命令: sudo apt-get install python3"
    exit 1
fi

echo "🐍 Python版本信息:"
python3 --version
echo ""

# 检查虚拟环境 - 使用单方括号进行条件测试
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✅ 检测到虚拟环境: $VIRTUAL_ENV"
else
    echo "⚠️  未检测到虚拟环境"
    echo "   建议在虚拟环境中运行此脚本"
    
    # 检查是否为交互式终端
    if [ -t 0 ]; then
        echo -n "是否继续? [y/N] "
        read -r REPLY
        # 使用case语句替代正则表达式匹配
        case "$REPLY" in
            [Yy]|[Yy][Ee][Ss])
                echo "👍 用户选择继续"
                ;;
            *)
                echo "👋 用户取消操作"
                exit 0
                ;;
        esac
    else
        echo "⚠️  非交互式环境，自动继续..."
    fi
fi
echo ""

# 检查依赖是否已安装
echo "🔍 检查项目依赖..."
python3 -c "
try:
    import sentence_transformers, unstructured, nltk
    print('✅ 核心依赖已安装')
except ImportError as e:
    print(f'❌ 缺少依赖: {e}')
    print('请先运行: pip install -r requirements.txt')
    exit(1)
" 2>/dev/null

exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo ""
    echo "💡 提示: 请先安装项目依赖"
    echo "   cd $PROJECT_ROOT"
    echo "   pip install -r requirements.txt"
    exit 1
fi

echo ""
echo "🎯 可下载的模型类型:"
echo "   1. NLTK数据包 (文本处理基础数据)"
echo "   2. Sentence-Transformers模型 (文本向量化)"
echo "   3. Unstructured文档处理模型 (PDF布局检测)"
echo ""

# 简化选择逻辑，避免复杂的交互
download_nltk=true
download_st=true
download_unstructured=true

# 检查是否为交互式环境
if [ -t 0 ]; then
    echo "请选择下载方式:"
    echo "1 - 下载所有模型 (推荐)"
    echo "2 - 只下载NLTK数据包"
    echo "3 - 只下载Sentence-Transformers模型"
    echo "4 - 只下载Unstructured模型"
    echo "0 - 退出"
    echo ""
    echo -n "请输入选择 [1]: "
    read -r choice
    
    # 设置默认值
    if [ -z "$choice" ]; then
        choice=1
    fi
else
    echo "🤖 非交互式环境，默认下载所有模型"
    choice=1
fi

# 重置下载选项
download_nltk=false
download_st=false
download_unstructured=false

case $choice in
    1)
        echo "📦 选择下载所有模型"
        download_nltk=true
        download_st=true
        download_unstructured=true
        ;;
    2)
        echo "📦 选择下载NLTK数据包"
        download_nltk=true
        ;;
    3)
        echo "📦 选择下载Sentence-Transformers模型"
        download_st=true
        ;;
    4)
        echo "📦 选择下载Unstructured模型"
        download_unstructured=true
        ;;
    0)
        echo "👋 用户选择退出"
        exit 0
        ;;
    *)
        echo "❌ 无效选择，使用默认选项 (下载所有模型)"
        download_nltk=true
        download_st=true
        download_unstructured=true
        ;;
esac

echo ""
echo "🚀 开始模型下载..."
echo "========================================"

# 计数器
total_scripts=0
success_scripts=0

# 检查子脚本是否存在
check_script() {
    local script_name="$1"
    local script_path="$SCRIPT_DIR/$script_name"
    
    if [ ! -f "$script_path" ]; then
        echo "❌ 错误: 找不到脚本 $script_name"
        return 1
    fi
    
    if [ ! -x "$script_path" ]; then
        echo "🔧 修复脚本权限: $script_name"
        chmod +x "$script_path"
    fi
    
    return 0
}

# 1. 下载NLTK数据包
if [ "$download_nltk" = true ]; then
    echo ""
    echo "📚 [1/3] 下载NLTK数据包..."
    total_scripts=$((total_scripts + 1))
    
    if check_script "download_nltk_data.sh"; then
        if bash "$SCRIPT_DIR/download_nltk_data.sh"; then
            success_scripts=$((success_scripts + 1))
            echo "✅ NLTK数据包下载完成"
        else
            echo "⚠️  NLTK数据包下载失败，但不影响其他功能"
        fi
    else
        echo "⚠️  跳过NLTK数据包下载 (脚本不存在)"
    fi
fi

# 2. 下载Sentence-Transformers模型
if [ "$download_st" = true ]; then
    echo ""
    echo "🤖 [2/3] 下载Sentence-Transformers模型..."
    total_scripts=$((total_scripts + 1))
    
    if check_script "download_sentence_transformers.sh"; then
        if bash "$SCRIPT_DIR/download_sentence_transformers.sh"; then
            success_scripts=$((success_scripts + 1))
            echo "✅ Sentence-Transformers模型下载完成"
        else
            echo "⚠️  Sentence-Transformers模型下载失败"
        fi
    else
        echo "⚠️  跳过Sentence-Transformers模型下载 (脚本不存在)"
    fi
fi

# 3. 下载Unstructured模型
if [ "$download_unstructured" = true ]; then
    echo ""
    echo "📄 [3/3] 下载Unstructured文档处理模型..."
    total_scripts=$((total_scripts + 1))
    
    if check_script "download_unstructured_models.sh"; then
        if bash "$SCRIPT_DIR/download_unstructured_models.sh"; then
            success_scripts=$((success_scripts + 1))
            echo "✅ Unstructured模型下载完成"
        else
            echo "⚠️  Unstructured模型下载失败，会在首次使用时自动下载"
        fi
    else
        echo "⚠️  跳过Unstructured模型下载 (脚本不存在)"
    fi
fi

echo ""
echo "========================================"
echo "📊 下载统计: $success_scripts/$total_scripts 个脚本执行成功"

if [ $success_scripts -eq $total_scripts ] && [ $total_scripts -gt 0 ]; then
    echo "🎉 所有模型下载完成！"
    echo ""
    echo "📁 模型存储位置:"
    echo "   - NLTK数据: ~/nltk_data"
    echo "   - Sentence-Transformers: ~/.cache/sentence_transformers"
    echo "   - Unstructured模型: ~/.cache/unstructured/models"
    echo ""
    echo "🚀 现在可以运行GraphRAG项目了！"
    echo "   cd $PROJECT_ROOT"
    echo "   python app.py"
elif [ $success_scripts -gt 0 ]; then
    echo "⚠️  部分模型下载成功，项目仍可正常运行"
    echo "   失败的模型会在首次使用时自动下载"
else
    echo "❌ 模型下载失败"
    echo "💡 不用担心，项目仍可运行，模型会在需要时自动下载"
fi

echo ""
echo "✅ 模型下载脚本执行完成！"
echo ""
echo "🐧 Ubuntu使用提示:"
echo "   如果遇到权限问题，请确保脚本有执行权限"
echo "   如果遇到依赖问题，请安装: sudo apt-get install python3-pip"
echo "   如果遇到网络问题，请检查网络连接和代理设置"
