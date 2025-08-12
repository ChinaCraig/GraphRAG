# GraphRAG模型下载脚本说明

## 概述

本目录包含GraphRAG项目所需的所有AI模型下载脚本，按照新的架构重构，每个模型使用单独的脚本下载。

**🔧 Ubuntu环境优化更新：**
- ✅ 修复了Ubuntu环境下下载没有进度条的问题
- ✅ 添加了网络连接中断的重试机制  
- ✅ 针对主要模型(paraphrase-multilingual-mpnet-base-v2)增强了重试策略

**🌐 网络优化特性：**
- ✅ **默认使用阿里云镜像源** - Sentence-Transformers模型无需配置，开箱即用
- ✅ **默认使用清华镜像源** - NLTK数据包无需配置，开箱即用
- ✅ **默认使用GitHub镜像加速** - YOLOX模型无需配置，开箱即用
- ✅ 支持环境变量自定义镜像源
- ✅ 所有脚本内置最优镜像配置
- ✅ 零配置，开箱即用的网络优化

## 🚀 快速开始

### 方法1: 直接下载（推荐，零配置）
```bash
cd install
./down_all.sh
# 所有模型自动使用最优镜像源，无需任何配置
```

### 方法2: 自定义镜像源（可选）

#### 🔗 使用代理（科学上网用户）
```bash
cd install
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
./down_all.sh
```

#### 🪞 自定义镜像源
```bash
cd install
# Hugging Face其他镜像
export HF_ENDPOINT=https://mirrors.tuna.tsinghua.edu.cn/huggingface
# NLTK官方源
export NLTK_DATA_URL=https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/
# GitHub官方源
unset GITHUB_MIRROR

./down_all.sh
```

### 下载特定模型
```bash
cd install
./down_all.sh
# 然后输入对应的编号，如：
# 3 - 下载nltk+3.8.1.sh  
# 5 - 下载paraphrase-multilingual-mpnet-base-v2+2.7.0.sh
```

## 📦 可用的模型下载脚本

### NLTK数据包
| 脚本名称 | 版本 | 描述 | 大小 |
|---------|------|------|------|
| `nltk+3.8.1.sh` | 3.8.1 | NLTK文本处理数据包 | ~50MB | + 🪞 清华镜像 + ✅ 3次重试 + 📊 详细进度 |

**包含的数据包：**
- punkt (句子分割)
- punkt_tab (句子分割新版本)
- averaged_perceptron_tagger (词性标注)
- stopwords (停用词)
- wordnet (词网)
- brown (Brown语料库)
- universal_tagset (通用标签集)

### Sentence-Transformers模型 (已优化Ubuntu支持)
| 脚本名称 | 版本 | 描述 | 大小 | 用途 | Ubuntu优化 |
|---------|------|------|------|------|------------|
| `all-MiniLM-L6-v2+2.7.0.sh` | 2.7.0 | 轻量级英文模型 | ~90MB | 快速原型、资源受限环境 | ✅ 3次重试 + 🪞 阿里云镜像 |
| `paraphrase-MiniLM-L6-v2+2.7.0.sh` | 2.7.0 | 英文句子相似度模型 | ~90MB | 句子匹配、检索 | ✅ 3次重试 + 🪞 阿里云镜像 |
| `all-mpnet-base-v2+2.7.0.sh` | 2.7.0 | 英文高精度模型 | ~420MB | 生产环境、高精度要求 | ✅ 3次重试 + 🪞 阿里云镜像 |
| `paraphrase-multilingual-mpnet-base-v2+2.7.0.sh` | 2.7.0 | 多语言模型（项目主要模型） | ~470MB | 中英文混合处理 | ⭐ **5次重试 + 🪞 阿里云镜像** |

**特别说明：** 
- `paraphrase-multilingual-mpnet-base-v2` 是项目配置文件中指定的主要嵌入模型
- 🪞 **所有Sentence-Transformers模型默认使用阿里云镜像源，无需额外配置**
- 🪞 **所有YOLOX模型默认使用GitHub镜像加速，无需额外配置**

### Unstructured模型
| 脚本名称 | 版本 | 描述 | 大小 | 特点 |
|---------|------|------|------|------|
| `yolox-s+0.1.1.sh` | 0.1.1 | YOLOX-S文档布局检测模型 | ~34MB | 轻量级，速度快 + 🪞 GitHub镜像 |
| `yolox-m+0.1.1.sh` | 0.1.1 | YOLOX-M文档布局检测模型 | ~97MB | 平衡速度和精度 + 🪞 GitHub镜像 |
| `yolox-l+0.1.1.sh` | 0.1.1 | YOLOX-L文档布局检测模型 | ~207MB | 最高精度，较慢 + 🪞 GitHub镜像 |

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

`down_all.sh` 是智能总入口脚本，现在的选择选项直接对应具体的.sh文件：

### 使用方式：
```bash
./down_all.sh
```

### 选择选项：
- `0` - 下载所有模型（推荐）
- `1` - all-MiniLM-L6-v2+2.7.0.sh  
- `2` - all-mpnet-base-v2+2.7.0.sh
- `3` - nltk+3.8.1.sh
- `4` - paraphrase-MiniLM-L6-v2+2.7.0.sh  
- `5` - paraphrase-multilingual-mpnet-base-v2+2.7.0.sh
- `6` - yolox-l+0.1.1.sh
- `7` - yolox-m+0.1.1.sh
- `8` - yolox-s+0.1.1.sh
- `q` - 退出

### 🌐 网络优化特性：
- 所有模型自动使用最优镜像源
- 支持环境变量自定义配置
- 零配置，开箱即用

### 特性：
1. **自动扫描：** 自动扫描install目录下的所有.sh脚本
2. **直接选择：** 选项名就是.sh文件名
3. **智能扩展：** 添加新脚本后无需修改down_all.sh

## 🔀 兼容性

所有脚本都经过测试，支持：

- **操作系统：** Ubuntu、macOS
- **Shell环境：** sh、bash、zsh、dash等POSIX兼容shell
- **Python版本：** Python 3.10+

## 🌐 高级网络配置

### 自定义镜像源

#### Hugging Face镜像源
```bash
# 清华大学镜像
export HF_ENDPOINT=https://mirrors.tuna.tsinghua.edu.cn/huggingface

# 北京外国语大学镜像
export HF_ENDPOINT=https://mirrors.bfsu.edu.cn/huggingface

# 使用官方源
unset HF_ENDPOINT
```

#### NLTK镜像源
```bash
# 使用官方源
export NLTK_DATA_URL=https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/

# 恢复默认清华镜像
unset NLTK_DATA_URL
```

#### GitHub镜像源
```bash
# 使用官方源
unset GITHUB_MIRROR

# 自定义镜像
export GITHUB_MIRROR=https://mirror.ghproxy.com/
```

### 代理配置
```bash
# HTTP代理
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# SOCKS5代理
export ALL_PROXY=socks5://127.0.0.1:1080
```

## 🐧 Ubuntu环境特别优化

### 已解决的问题：
1. **✅ 进度条显示问题**
   - 设置 `HF_HUB_DISABLE_PROGRESS_BARS=false`
   - 优化了输出显示逻辑

2. **✅ 网络连接中断问题**
   - 添加了智能重试机制（3-5次重试）
   - 网络错误自动识别和重试
   - 非网络错误立即停止重试

3. **✅ 针对主要模型的增强重试**
   - `paraphrase-multilingual-mpnet-base-v2` 使用5次重试和10秒延迟
   - 其他模型使用3次重试和5秒延迟

### Ubuntu使用建议：

#### 1. 直接运行（推荐，零配置）
```bash
cd install
./down_all.sh
# 所有模型自动使用最优镜像源
```

#### 2. 故障排除（如有网络问题）
```bash
# 尝试其他镜像源
export HF_ENDPOINT=https://mirrors.tuna.tsinghua.edu.cn/huggingface  # 清华镜像
export HF_ENDPOINT=https://mirrors.bfsu.edu.cn/huggingface          # 北外镜像

# 或使用代理
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# 运行下载
./down_all.sh
```

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
4. **失败处理：** 如果下载失败，脚本会自动重试，最终失败的模型会在首次使用时自动下载

## 🆕 添加新模型脚本

如需添加新的模型下载脚本：

1. 按照命名规范创建脚本：`模型名+版本.sh`
2. 确保脚本以`#!/bin/sh`开头
3. 设置执行权限：`chmod +x 新脚本.sh`
4. `down_all.sh`会自动识别新脚本，无需修改

## 🐛 故障排除

### 网络问题解决方案

1. **网络连接问题 (ProtocolError)**
   ```bash
   # 脚本默认已使用最优镜像，如仍有问题可尝试:
   
   # 方案1: 使用代理
   export HTTP_PROXY=http://127.0.0.1:7890
   export HTTPS_PROXY=http://127.0.0.1:7890
   
   # 方案2: 使用其他镜像源
   export HF_ENDPOINT=https://mirrors.tuna.tsinghua.edu.cn/huggingface
   
   # 方案3: 使用官方源
   unset HF_ENDPOINT
   unset NLTK_DATA_URL
   unset GITHUB_MIRROR
   ```

2. **进度条不显示**
   ```bash
   export HF_HUB_DISABLE_PROGRESS_BARS=false
   ```

3. **SSL证书问题**
   ```bash
   # 手动配置SSL
   export PYTHONHTTPSVERIFY=0
   export CURL_CA_BUNDLE=""
   export REQUESTS_CA_BUNDLE=""
   ```

4. **依赖版本冲突**
   ```bash
   pip install --upgrade huggingface_hub sentence-transformers requests urllib3
   ```

5. **超时问题**
   ```bash
   export REQUESTS_TIMEOUT=600
   export HF_HUB_DOWNLOAD_TIMEOUT=600
   ```

### 通用问题

1. **权限错误**
   ```bash
   chmod +x *.sh
   ```

2. **Python未找到**
   ```bash
   # 检查Python安装
   python3 --version
   ```

3. **磁盘空间不足**
   ```bash
   # 检查磁盘空间
   df -h
   ```

### 获取帮助

如果遇到问题，可以查看：
1. **脚本错误输出：** 查看详细的错误信息和解决建议
2. **项目根目录：** README.md - 整体项目说明
3. **脚本注释：** 各脚本内的详细说明

## 📝 更新日志

### v1.4.0 (简化优化版本)
- ⭐ **简化脚本架构，移除网络配置检查环节**
- ✅ 删除network_config.sh，简化使用流程
- ✅ down_all.sh直接启动，零配置使用
- ✅ 保留所有内置镜像优化功能

### v1.3.3 (进度显示优化版本)
- ⭐ **NLTK脚本大幅改进进度显示和状态反馈**
- ✅ 解决Ubuntu下载无进度条问题
- ✅ 添加网络连接测试和下载计时
- ✅ 增强用户中断处理和错误提示

### v1.3.2 (YOLOX网络优化版本)
- ⭐ **YOLOX脚本默认使用GitHub镜像加速服务**
- ✅ 所有YOLOX模型支持ghproxy.com镜像加速
- ✅ 网络配置向导支持GitHub镜像源配置
- ✅ 完整覆盖所有模型类型的网络优化

### v1.3.1 (NLTK网络优化版本)
- ⭐ **NLTK脚本默认使用清华大学镜像源**
- ✅ NLTK下载增加3次重试机制和智能错误处理
- ✅ 网络配置向导支持NLTK镜像源配置
- ✅ 完整的网络优化覆盖所有模型类型

### v1.3.0 (默认镜像源版本)
- ⭐ **所有Sentence-Transformers脚本默认使用阿里云镜像源**
- ✅ 无需任何配置，开箱即用的网络优化
- ✅ 自动镜像源检测和提示功能

### v1.2.0 (网络优化版本)
- ✅ 新增网络配置向导 `network_config.sh`
- ✅ 支持HTTP/HTTPS/SOCKS代理自动配置
- ✅ 支持国内镜像源 (阿里云、清华、北外)
- ✅ 智能网络配置检测和应用
- ✅ 完整的网络优化指南 `NETWORK_GUIDE.md`

### v1.1.0 (Ubuntu优化版本)
- ✅ 修复Ubuntu环境下进度条显示问题
- ✅ 添加网络连接中断重试机制
- ✅ 为主要模型增强重试策略
- ✅ 改进down_all.sh选择逻辑，选项直接对应.sh文件名
- ✅ 增加更详细的Ubuntu环境错误提示

### v1.0.0 (重构版本)
- 重构install目录脚本架构
- 每个模型使用单独的下载脚本
- 新增智能总入口脚本down_all.sh
- 支持Ubuntu和macOS环境
- 完整的POSIX shell兼容性