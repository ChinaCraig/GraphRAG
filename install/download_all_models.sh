#!/bin/bash

# GraphRAG项目模型一键下载脚本
# 下载项目所需的所有AI模型和数据包

set -e

echo "========================================"
echo "    GraphRAG项目模型下载工具"
echo "========================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📁 项目根目录: $PROJECT_ROOT"
echo "📁 安装脚本目录: $SCRIPT_DIR"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3命令"
    echo "   请确保已安装Python 3.10或更高版本"
    exit 1
fi

echo "🐍 Python版本信息:"
python3 --version
echo ""

# 检查虚拟环境
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ 检测到虚拟环境: $VIRTUAL_ENV"
else
    echo "⚠️  未检测到虚拟环境"
    echo "   建议在虚拟环境中运行此脚本"
    read -p "是否继续? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "👋 用户取消操作"
        exit 0
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
"

if [ $? -ne 0 ]; then
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

echo "请选择下载方式:"
echo "1 - 下载所有模型 (推荐)"
echo "2 - 只下载NLTK数据包"
echo "3 - 只下载Sentence-Transformers模型"
echo "4 - 只下载Unstructured模型"
echo "5 - 自定义选择"
echo "0 - 退出"

read -p "请输入选择 [1]: " choice
choice=${choice:-1}

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
    5)
        echo "📦 自定义选择"
        read -p "下载NLTK数据包? [Y/n] " -r
        [[ ! $REPLY =~ ^[Nn]$ ]] && download_nltk=true
        
        read -p "下载Sentence-Transformers模型? [Y/n] " -r
        [[ ! $REPLY =~ ^[Nn]$ ]] && download_st=true
        
        read -p "下载Unstructured模型? [Y/n] " -r  
        [[ ! $REPLY =~ ^[Nn]$ ]] && download_unstructured=true
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

# 1. 下载NLTK数据包
if [ "$download_nltk" = true ]; then
    echo ""
    echo "📚 [1/3] 下载NLTK数据包..."
    total_scripts=$((total_scripts + 1))
    
    if bash "$SCRIPT_DIR/download_nltk_data.sh"; then
        success_scripts=$((success_scripts + 1))
        echo "✅ NLTK数据包下载完成"
    else
        echo "⚠️  NLTK数据包下载失败，但不影响其他功能"
    fi
fi

# 2. 下载Sentence-Transformers模型
if [ "$download_st" = true ]; then
    echo ""
    echo "🤖 [2/3] 下载Sentence-Transformers模型..."
    total_scripts=$((total_scripts + 1))
    
    if bash "$SCRIPT_DIR/download_sentence_transformers.sh"; then
        success_scripts=$((success_scripts + 1))
        echo "✅ Sentence-Transformers模型下载完成"
    else
        echo "⚠️  Sentence-Transformers模型下载失败"
    fi
fi

# 3. 下载Unstructured模型
if [ "$download_unstructured" = true ]; then
    echo ""
    echo "📄 [3/3] 下载Unstructured文档处理模型..."
    total_scripts=$((total_scripts + 1))
    
    if bash "$SCRIPT_DIR/download_unstructured_models.sh"; then
        success_scripts=$((success_scripts + 1))
        echo "✅ Unstructured模型下载完成"
    else
        echo "⚠️  Unstructured模型下载失败，会在首次使用时自动下载"
    fi
fi

echo ""
echo "========================================"
echo "📊 下载统计: $success_scripts/$total_scripts 个脚本执行成功"

if [ $success_scripts -eq $total_scripts ]; then
    echo "🎉 所有模型下载完成！"
    echo ""
    echo "📁 模型存储位置:"
    echo "   - NLTK数据: ~/nltk_data"
    echo "   - Sentence-Transformers: ~/.cache/sentence_transformers"
    echo "   - Unstructured模型: ~/.cache/unstructured/models"
    echo ""
    echo "🚀 现在可以运行GraphRAG项目了！"
    echo "   cd $PROJECT_ROOT"
    echo "   python start.py"
elif [ $success_scripts -gt 0 ]; then
    echo "⚠️  部分模型下载成功，项目仍可正常运行"
    echo "   失败的模型会在首次使用时自动下载"
else
    echo "❌ 模型下载失败"
    echo "💡 不用担心，项目仍可运行，模型会在需要时自动下载"
fi

echo ""
echo "✅ 模型下载脚本执行完成！"