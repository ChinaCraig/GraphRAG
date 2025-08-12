#!/bin/sh

# GraphRAG项目模型下载总入口脚本
# 自动扫描install目录下的所有模型下载脚本，提供选择界面
# 支持Ubuntu和macOS环境，兼容sh/bash/zsh等shell

set -e

echo "========================================"
echo "    GraphRAG 模型下载总入口"
echo "    自动扫描并管理所有模型下载脚本"
echo "========================================"
echo ""

# 获取脚本所在目录 - 使用POSIX兼容的方法
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📁 项目根目录: $PROJECT_ROOT"
echo "📁 脚本目录: $SCRIPT_DIR"
echo ""

# 检查Python环境
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 错误: 未找到python3命令"
    echo "   Ubuntu安装命令: sudo apt-get install python3"
    echo "   macOS安装命令: brew install python3"
    exit 1
fi

echo "🐍 Python版本信息:"
python3 --version
echo ""

# 检查虚拟环境
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✅ 检测到虚拟环境: $VIRTUAL_ENV"
else
    echo "⚠️  未检测到虚拟环境"
    echo "   建议在虚拟环境中运行此脚本"
    
    # 检查是否为交互式终端
    if [ -t 0 ]; then
        printf "是否继续? [y/N] "
        read REPLY
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

# 扫描install目录下的所有.sh文件(排除自身)
echo "🔍 扫描可用的模型下载脚本..."
CURRENT_SCRIPT="$(basename "$0")"

# 创建临时文件存储脚本列表
SCRIPTS_LIST="/tmp/graphrag_scripts_$$.txt"
> "$SCRIPTS_LIST"

# 扫描.sh文件
script_count=0
for script_file in "$SCRIPT_DIR"/*.sh; do
    # 检查文件是否存在(处理通配符无匹配的情况)
    if [ ! -f "$script_file" ]; then
        continue
    fi
    
    script_name="$(basename "$script_file")"
    
    # 跳过自身
    if [ "$script_name" = "$CURRENT_SCRIPT" ]; then
        continue
    fi
    
    # 提取模型信息
    model_name=""
    version=""
    if echo "$script_name" | grep -q "+"; then
        model_name="$(echo "$script_name" | cut -d'+' -f1)"
        version="$(echo "$script_name" | cut -d'+' -f2 | sed 's/\.sh$//')"
    else
        model_name="$(echo "$script_name" | sed 's/\.sh$//')"
        version="unknown"
    fi
    
    script_count=$((script_count + 1))
    echo "$script_count|$script_name|$model_name|$version" >> "$SCRIPTS_LIST"
done

if [ $script_count -eq 0 ]; then
    echo "❌ 未找到任何模型下载脚本"
    echo "💡 请确保install目录下有模型下载脚本(*.sh)"
    rm -f "$SCRIPTS_LIST"
    exit 1
fi

echo "✅ 找到 $script_count 个模型下载脚本"
echo ""

# 显示脚本列表
echo "📦 可用的模型下载脚本:"
echo "----------------------------------------"
while IFS='|' read -r num script_name model_name version; do
    printf "  %2s. %-35s (v%s)\n" "$num" "$model_name" "$version"
done < "$SCRIPTS_LIST"
echo "----------------------------------------"
echo ""

# 分类显示
echo "📊 按类型分类:"
echo "🔤 NLTK数据包:"
grep "|nltk" "$SCRIPTS_LIST" | while IFS='|' read -r num script_name model_name version; do
    printf "     - %s (v%s)\n" "$model_name" "$version"
done

echo "🤖 Sentence-Transformers模型:"
grep -E "(all-MiniLM|paraphrase-MiniLM|all-mpnet|paraphrase-multilingual)" "$SCRIPTS_LIST" | while IFS='|' read -r num script_name model_name version; do
    printf "     - %s (v%s)\n" "$model_name" "$version"
done

echo "📄 Unstructured模型:"
grep "yolox" "$SCRIPTS_LIST" | while IFS='|' read -r num script_name model_name version; do
    printf "     - %s (v%s)\n" "$model_name" "$version"
done
echo ""

# 交互式选择(如果是交互式环境)
if [ -t 0 ]; then
    echo "请选择下载方式:"
    echo "0 - 下载所有模型 (推荐)"
    
    # 显示所有可用的脚本选项
    while IFS='|' read -r num script_name model_name version; do
        printf "  %s - %s\n" "$num" "$script_name"
    done < "$SCRIPTS_LIST"
    
    echo "q - 退出"
    echo ""
    printf "请输入选择 [0]: "
    read choice
    
    # 设置默认值
    if [ -z "$choice" ]; then
        choice=0
    fi
else
    echo "🤖 非交互式环境，默认下载所有模型"
    choice=0
fi

# 处理选择
selected_scripts=""
if [ "$choice" = "0" ]; then
    echo "📦 选择下载所有模型"
    selected_scripts="all"
elif [ "$choice" = "q" ] || [ "$choice" = "Q" ]; then
    echo "👋 用户选择退出"
    rm -f "$SCRIPTS_LIST"
    exit 0
else
    # 查找对应编号的脚本
    script_name="$(grep "^$choice|" "$SCRIPTS_LIST" | cut -d'|' -f2)"
    if [ -n "$script_name" ]; then
        echo "📦 选择下载: $script_name"
        selected_scripts="$script_name"
    else
        echo "❌ 无效选择 ($choice)，使用默认选项 (下载所有模型)"
        selected_scripts="all"
    fi
fi

echo ""
echo "🚀 开始模型下载..."
echo "========================================"

# 执行选择的脚本
total_scripts=0
success_scripts=0

if [ "$selected_scripts" = "all" ]; then
    # 下载所有脚本
    while IFS='|' read -r num script_name model_name version; do
        total_scripts=$((total_scripts + 1))
        script_path="$SCRIPT_DIR/$script_name"
        
        echo ""
        echo "📦 [$total_scripts/$script_count] 执行: $model_name (v$version)"
        echo "🔄 运行脚本: $script_name"
        
        # 确保脚本有执行权限
        chmod +x "$script_path"
        
        # 执行脚本
        if sh "$script_path"; then
            success_scripts=$((success_scripts + 1))
            echo "✅ $model_name 下载完成"
        else
            echo "⚠️  $model_name 下载失败，但不影响其他脚本执行"
        fi
    done < "$SCRIPTS_LIST"
else
    # 下载选择的脚本
    for script_name in $selected_scripts; do
        if [ -f "$SCRIPT_DIR/$script_name" ]; then
            total_scripts=$((total_scripts + 1))
            
            # 获取模型信息
            model_info="$(grep "|$script_name|" "$SCRIPTS_LIST")"
            if [ -n "$model_info" ]; then
                model_name="$(echo "$model_info" | cut -d'|' -f3)"
                version="$(echo "$model_info" | cut -d'|' -f4)"
            else
                model_name="$script_name"
                version="unknown"
            fi
            
            echo ""
            echo "📦 [$total_scripts/?] 执行: $model_name (v$version)"
            echo "🔄 运行脚本: $script_name"
            
            script_path="$SCRIPT_DIR/$script_name"
            chmod +x "$script_path"
            
            if sh "$script_path"; then
                success_scripts=$((success_scripts + 1))
                echo "✅ $model_name 下载完成"
            else
                echo "⚠️  $model_name 下载失败，但不影响其他脚本执行"
            fi
        else
            echo "❌ 脚本不存在: $script_name"
        fi
    done
fi

# 清理临时文件
rm -f "$SCRIPTS_LIST"

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
echo "✅ 模型下载总入口脚本执行完成！"
echo ""
echo "💡 使用提示:"
echo "   - 此脚本会自动扫描install目录下的所有.sh脚本"
echo "   - 添加新的模型下载脚本后无需修改此文件"
echo "   - 支持Ubuntu和macOS环境"
echo "   - 可以重复运行，已下载的模型会自动跳过"
