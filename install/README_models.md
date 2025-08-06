# GraphRAG项目模型下载说明

## 概述

GraphRAG项目使用多种AI模型来处理文档和生成向量。为了提高首次运行速度，建议预先下载这些模型。

## 模型类型

### 1. NLTK数据包
- **用途**: 文本预处理、句子分割、词性标注
- **大小**: ~50MB
- **必需性**: 高
- **存储位置**: `~/nltk_data`

#### 包含数据包:
- `punkt`: 句子分割器
- `averaged_perceptron_tagger`: 词性标注器
- `stopwords`: 停用词表
- `wordnet`: WordNet词汇数据库

### 2. Sentence-Transformers模型
- **用途**: 文本向量化、语义相似度计算
- **必需性**: 高
- **存储位置**: `~/.cache/sentence_transformers`

#### 推荐模型:
| 模型名称 | 大小 | 描述 | 推荐场景 |
|---------|------|------|----------|
| `all-MiniLM-L6-v2` | ~90MB | 轻量级英文模型 | 快速原型、资源受限环境 |
| `paraphrase-MiniLM-L6-v2` | ~90MB | 英文句子相似度 | 句子匹配、检索 |
| `all-mpnet-base-v2` | ~420MB | 高精度英文模型 | 生产环境、高精度要求 |
| `paraphrase-multilingual-MiniLM-L12-v2` | ~470MB | 多语言支持 | 中英文混合处理 |

### 3. Unstructured文档处理模型
- **用途**: PDF文档布局检测、表格识别
- **必需性**: 中等 (可自动下载)
- **存储位置**: `~/.cache/unstructured/models`

#### YOLOX系列模型:
| 模型文件 | 大小 | 描述 | 性能 |
|---------|------|------|------|
| `yolox_s.onnx` | ~34MB | 小型模型 | 快速，适合实时处理 |
| `yolox_m.onnx` | ~97MB | 中型模型 | 平衡速度和精度 |
| `yolox_l.onnx` | ~207MB | 大型模型 | 最高精度，较慢 |

## 快速开始

### 一键下载所有模型
```bash
cd install
chmod +x download_all_models.sh
./download_all_models.sh
```

### 单独下载特定模型

#### 下载NLTK数据包
```bash
cd install
chmod +x download_nltk_data.sh
./download_nltk_data.sh
```

#### 下载Sentence-Transformers模型
```bash
cd install
chmod +x download_sentence_transformers.sh
./download_sentence_transformers.sh
```

#### 下载Unstructured模型
```bash
cd install
chmod +x download_unstructured_models.sh
./download_unstructured_models.sh
```

## 配置说明

### Unstructured模型配置
在 `config/Unstructured.yaml` 中配置:

```yaml
pdf:
  strategy: "hi_res"
  hi_res_model_name: "yolox"  # 使用YOLOX模型
  # 可选: 指定本地模型路径
  # model_path: "~/.cache/unstructured/models"
```

### Sentence-Transformers配置
在代码中使用:

```python
from sentence_transformers import SentenceTransformer

# 使用默认缓存位置的模型
model = SentenceTransformer('all-MiniLM-L6-v2')
```

## 故障排除

### SSL证书问题
如果遇到SSL证书错误，这是正常现象（特别是NLTK下载）。脚本已包含错误处理，不会影响功能。

### 网络连接问题
如果下载失败：
1. 检查网络连接
2. 使用VPN或更换网络
3. 模型会在首次使用时自动下载

### 磁盘空间不足
所有模型总大小约 1-2GB，请确保有足够的磁盘空间。

### 手动下载
如果自动下载失败，可以手动下载模型文件并放置到相应目录：

1. **NLTK数据**: 下载到 `~/nltk_data/`
2. **Sentence-Transformers**: 下载到 `~/.cache/sentence_transformers/`
3. **Unstructured模型**: 下载到 `~/.cache/unstructured/models/`

## 验证安装

### 测试NLTK
```python
import nltk
nltk.download('punkt')  # 如果已下载会跳过
```

### 测试Sentence-Transformers
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print("✅ Sentence-Transformers可用")
```

### 测试Unstructured
```python
from unstructured.partition.pdf import partition_pdf
print("✅ Unstructured可用")
```

## 模型更新

模型会定期更新，建议：
1. 定期运行下载脚本更新模型
2. 关注模型版本变化
3. 测试新模型兼容性

## 注意事项

1. **首次运行**: 即使不预下载，模型也会在首次使用时自动下载
2. **网络要求**: 模型下载需要稳定的网络连接
3. **存储空间**: 建议预留2GB以上空间存储所有模型
4. **权限要求**: 脚本需要写入权限到用户主目录

## 支持

如果遇到问题：
1. 检查网络连接和权限
2. 查看错误日志
3. 尝试单独下载失败的模型
4. 检查磁盘空间和Python环境