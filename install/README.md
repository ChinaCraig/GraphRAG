# GraphRAG模型下载脚本说明

## 概述

本目录包含GraphRAG项目所需的所有AI模型下载脚本，按照新的架构重构，每个模型使用单独的脚本下载。

## 🚀 快速开始

### 下载所有模型（推荐）
```bash
cd install
./down_all.sh
```

### 下载特定类型的模型
```bash
cd install
./down_all.sh
# 然后选择对应的选项（1-NLTK, 2-Sentence-Transformers, 3-Unstructured）
```

## 📦 可用的模型下载脚本

### NLTK数据包
| 脚本名称 | 版本 | 描述 | 大小 |
|---------|------|------|------|
| `nltk+3.8.1.sh` | 3.8.1 | NLTK文本处理数据包 | ~50MB |

**包含的数据包：**
- punkt (句子分割)
- punkt_tab (句子分割新版本)
- averaged_perceptron_tagger (词性标注)
- stopwords (停用词)
- wordnet (词网)
- brown (Brown语料库)
- universal_tagset (通用标签集)

### Sentence-Transformers模型
| 脚本名称 | 版本 | 描述 | 大小 | 用途 |
|---------|------|------|------|------|
| `all-MiniLM-L6-v2+2.7.0.sh` | 2.7.0 | 轻量级英文模型 | ~90MB | 快速原型、资源受限环境 |
| `paraphrase-MiniLM-L6-v2+2.7.0.sh` | 2.7.0 | 英文句子相似度模型 | ~90MB | 句子匹配、检索 |
| `all-mpnet-base-v2+2.7.0.sh` | 2.7.0 | 英文高精度模型 | ~420MB | 生产环境、高精度要求 |
| `paraphrase-multilingual-mpnet-base-v2+2.7.0.sh` | 2.7.0 | 多语言模型（项目主要模型） | ~470MB | 中英文混合处理 |

**特别说明：** `paraphrase-multilingual-mpnet-base-v2` 是项目配置文件中指定的主要嵌入模型。

### Unstructured模型
| 脚本名称 | 版本 | 描述 | 大小 | 特点 |
|---------|------|------|------|------|
| `yolox-s+0.1.1.sh` | 0.1.1 | YOLOX-S文档布局检测模型 | ~34MB | 轻量级，速度快 |
| `yolox-m+0.1.1.sh` | 0.1.1 | YOLOX-M文档布局检测模型 | ~97MB | 平衡速度和精度 |
| `yolox-l+0.1.1.sh` | 0.1.1 | YOLOX-L文档布局检测模型 | ~207MB | 最高精度，较慢 |

## 🔧 单独使用脚本

每个脚本都可以单独执行：

```bash
cd install

# 下载NLTK数据包
./nltk+3.8.1.sh

# 下载特定的Sentence-Transformers模型
./all-MiniLM-L6-v2+2.7.0.sh
./paraphrase-multilingual-mpnet-base-v2+2.7.0.sh

# 下载特定的Unstructured模型
./yolox-s+0.1.1.sh
```

## 📁 模型存储位置

下载的模型会存储在以下位置：

- **NLTK数据：** `~/nltk_data`
- **Sentence-Transformers模型：** `~/.cache/sentence_transformers`
- **Unstructured模型：** `~/.cache/unstructured/models`

## 🔄 down_all.sh 总入口说明

`down_all.sh` 是智能总入口脚本，具有以下特性：

1. **自动扫描：** 自动扫描install目录下的所有.sh脚本
2. **分类显示：** 按模型类型分类显示可用脚本
3. **交互选择：** 提供交互式选择界面
4. **批量执行：** 支持批量下载或单独选择
5. **智能扩展：** 添加新脚本后无需修改down_all.sh

### 选择选项：
- `0` - 下载所有模型（推荐）
- `1` - 只下载NLTK数据包
- `2` - 只下载Sentence-Transformers模型
- `3` - 只下载Unstructured模型
- `4` - 自定义选择特定脚本
- `q` - 退出

## 🔀 兼容性

所有脚本都经过测试，支持：

- **操作系统：** Ubuntu、macOS
- **Shell环境：** sh、bash、zsh、dash等POSIX兼容shell
- **Python版本：** Python 3.10+

## 📋 使用前准备

1. **安装Python 3.10+**
   ```bash
   # Ubuntu
   sudo apt-get install python3
   
   # macOS
   brew install python3
   ```

2. **安装项目依赖**
   ```bash
   cd ../  # 返回项目根目录
   pip install -r requirements.txt
   ```

3. **（推荐）使用虚拟环境**
   ```bash
   cd ../  # 返回项目根目录
   python3 -m venv venv
   source venv/bin/activate  # Linux/macOS
   pip install -r requirements.txt
   ```

## ⚠️ 注意事项

1. **网络要求：** 下载过程需要稳定的网络连接
2. **磁盘空间：** 确保有足够的磁盘空间（全部模型约1.2GB）
3. **重复执行：** 脚本支持重复执行，已下载的模型会自动跳过
4. **失败处理：** 如果下载失败，模型会在首次使用时自动下载

## 🆕 添加新模型脚本

如需添加新的模型下载脚本：

1. 按照命名规范创建脚本：`模型名+版本.sh`
2. 确保脚本以`#!/bin/sh`开头
3. 设置执行权限：`chmod +x 新脚本.sh`
4. `down_all.sh`会自动识别新脚本，无需修改

## 🐛 故障排除

### 常见问题

1. **权限错误**
   ```bash
   chmod +x *.sh
   ```

2. **Python未找到**
   ```bash
   # 检查Python安装
   python3 --version
   ```

3. **网络连接问题**
   - 检查网络连接
   - 如果在公司网络，可能需要配置代理

4. **磁盘空间不足**
   ```bash
   # 检查磁盘空间
   df -h
   ```

### 获取帮助

如果遇到问题，可以查看：
1. 脚本执行输出的详细错误信息
2. 项目根目录的README.md
3. 各脚本内的注释说明

## 📝 更新日志

### v1.0.0 (重构版本)
- 重构install目录脚本架构
- 每个模型使用单独的下载脚本
- 新增智能总入口脚本down_all.sh
- 支持Ubuntu和macOS环境
- 完整的POSIX shell兼容性
