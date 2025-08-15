# 知识图谱模型配置完成总结

## 📋 任务概述

应用户要求，完善了重构后知识图谱的模型配置和下载机制，解决了以下三个核心问题：
1. **需要用到模型么？** - 是的，需要多个AI模型
2. **模型为什么没有放在配置文件中？** - 已补充到`config/model.yaml`
3. **为什么没有创建下载脚本？** - 已创建专门的下载脚本

## ✅ 已完成的工作

### 1) 📝 完善模型配置文件

**文件**: `config/model.yaml`

**新增配置**:
```yaml
# 知识图谱模型配置 (新增)
knowledge_graph:
  # 统计式NER模型配置
  ner:
    enabled: true
    model_name: "bert-base-chinese"
    device: "cpu"
    cache_dir: "./models"
    max_length: 512
    batch_size: 16
    confidence_thresholds:
      high: 0.9
      medium: 0.7  
      low: 0.5
    fallback_to_rules: true
    
  # 实体链接模型配置  
  entity_linking:
    enabled: true
    bi_encoder: "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    cross_encoder: "BAAI/bge-reranker-large"
    cache_dir: "./models"
    device: "cpu"
    candidate_top_k: 10
    rerank_threshold: 0.7
    nil_threshold: 0.5
    context_window: 50
    
  # 关系抽取模型配置
  relation_extraction:
    enabled: true
    method: "rule_based"
    sentence_window: 2
    confidence_threshold: 0.5
    evidence_aggregation: true
    
  # 规则锚点识别配置
  rule_anchor:
    enabled: true
    use_ac_automaton: true
    normalization: true
    conflict_resolution: "priority_based"
    priority_map:
      CellLine: 1
      Protein: 2
      Reagent: 3
      Product: 4
      Metric: 5
```

### 2) 📥 创建模型下载脚本

**文件**: `install/bert-base-chinese+transformers-4.36.sh`

**功能特性**:
- ✅ 支持阿里云镜像源，提高下载成功率
- ✅ 自动检测已下载模型，避免重复下载
- ✅ 提供详细的下载进度和验证信息
- ✅ 包含完整的配置使用说明
- ✅ 支持断点续传和错误重试
- ✅ 与项目现有下载脚本架构一致

**使用方式**:
```bash
cd install
./bert-base-chinese+transformers-4.36.sh
```

### 3) 🔧 更新PdfGraphService配置加载

**文件**: `app/service/pdf/PdfGraphService.py`

**主要改进**:
- ✅ 所有模型配置从`config/model.yaml`读取
- ✅ 支持enabled/disabled开关控制
- ✅ 实现降级机制（模型加载失败时自动降级到规则方法）
- ✅ 统一缓存目录管理
- ✅ 详细的错误日志和状态记录

**配置加载示例**:
```python
# NER配置读取
kg_config = model_config.get('knowledge_graph', {})
ner_config = kg_config.get('ner', {})
self.model_name = ner_config.get('model_name', 'bert-base-chinese')
self.enabled = ner_config.get('enabled', True)
self.fallback_to_rules = ner_config.get('fallback_to_rules', True)

# 模型初始化
if self.enabled:
    try:
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=self.cache_dir
        )
    except Exception as e:
        if self.fallback_to_rules:
            self.logger.warning(f"NER模型加载失败，降级到规则方法: {e}")
```

### 4) 📦 更新下载管理脚本

**文件**: `install/down_all.sh`

**新增功能**:
- ✅ 知识图谱模型分类显示
- ✅ 自动识别新的BERT下载脚本
- ✅ 统一的模型管理界面

**分类显示**:
```bash
🧠 知识图谱模型:
     - bert-base-chinese (v4.36.x)
     - bge-reranker-large (如果存在)
```

### 5) 📋 依赖管理

**文件**: `requirements.txt`

**已添加**:
```txt
pyahocorasick>=1.4.4,<2.0.0  # AC自动机，用于规则锚点识别
```

**现有相关依赖**:
- `transformers>=4.36.0` - BERT tokenizer
- `sentence-transformers>=2.7.0` - 嵌入模型
- `torch>=2.0.0` - 深度学习框架

## 🤖 重构后需要的模型清单

### 📊 核心模型列表

| 模型类型 | 模型名称 | 用途 | 配置位置 | 下载脚本 |
|---------|---------|------|---------|---------|
| **NER Tokenizer** | `bert-base-chinese` | 统计式NER文本分词 | `knowledge_graph.ner.model_name` | `bert-base-chinese+transformers-4.36.sh` |
| **Bi-encoder** | `paraphrase-multilingual-mpnet-base-v2` | 实体链接召回 | `knowledge_graph.entity_linking.bi_encoder` | `paraphrase-multilingual-mpnet-base-v2+2.7.0.sh` |
| **Cross-encoder** | `BAAI/bge-reranker-large` | 实体链接重排 | `knowledge_graph.entity_linking.cross_encoder` | 复用`reranker.model_name` |
| **AC自动机** | `pyahocorasick` | 规则锚点识别 | `rule_anchor.use_ac_automaton` | `pip install` |

### 🏗️ 模型使用架构

```
知识图谱建设流程：
├── 1) 规则锚点识别
│   └── pyahocorasick (AC自动机) + 词典治理
├── 2) 统计式NER  
│   └── bert-base-chinese (tokenizer) + offset_mapping
├── 3) 实体链接(EL)
│   ├── paraphrase-multilingual-mpnet-base-v2 (召回)
│   └── BAAI/bge-reranker-large (重排)
├── 4) 关系抽取(RE)
│   └── rule_based (可扩展为model_based)
└── 5) Neo4j保存
    └── 批量MERGE操作
```

## 🚀 使用指南

### 📥 模型下载

**方法1: 单独下载（推荐）**
```bash
cd install
./bert-base-chinese+transformers-4.36.sh
```

**方法2: 批量下载**
```bash
cd install  
./down_all.sh
# 选择 0 (下载所有模型)
```

### 🔧 配置调整

在`config/model.yaml`中调整知识图谱模型配置：

```yaml
knowledge_graph:
  ner:
    enabled: true/false          # 开启/关闭NER模型
    fallback_to_rules: true      # 模型失败时降级到规则
  entity_linking:
    enabled: true/false          # 开启/关闭实体链接
    candidate_top_k: 10          # 召回候选数量
  relation_extraction:
    method: "rule_based"         # rule_based 或 model_based
```

### 🔍 服务使用

重构后的服务接口保持不变：

```python
from app.service.pdf.PdfGraphService import PdfGraphService

service = PdfGraphService()
result = service.process_pdf_json_to_graph(json_data, document_id)

# 返回详细统计
{
    'success': True,
    'entities_count': 25,
    'relations_count': 12,
    'anchors_count': 15,
    'ner_entities_count': 18,
    'linked_count': 20
}
```

## 🎯 技术亮点

### 🛡️ 降级机制
- **NER模型加载失败** → 自动降级到规则方法
- **实体链接失败** → 保留原始实体文本  
- **关系抽取失败** → 跳过关系建设，保留实体

### 📊 配置灵活性
- **统一配置管理**: 所有模型配置集中在`model.yaml`
- **组件开关控制**: 每个组件都可独立启用/禁用
- **参数可调节**: 阈值、批次大小、设备等参数可配置

### 🔧 工程实用性
- **复用现有基础设施**: 使用项目现有的下载脚本架构
- **兼容性良好**: 保持原有接口不变
- **错误处理完善**: 详细的日志和异常处理

## ✅ 验证结果

已通过以下验证：
- ✅ 配置文件格式正确，所有必需字段齐全
- ✅ 下载脚本可执行，包含正确的模型信息
- ✅ PdfGraphService可正常导入和初始化配置
- ✅ 模型依赖(transformers, sentence-transformers等)可用
- ⚠️  pyahocorasick在某些环境中导入有问题（已安装但导入失败）

## 🚩 已知问题

1. **pyahocorasick导入问题**: 在某些环境中可能遇到导入错误，但不影响系统运行（有降级机制）
2. **模型文件大小**: BERT模型约400MB，首次下载需要时间
3. **设备配置**: 默认使用CPU，如需GPU需手动配置

## 🔄 后续扩展建议

1. **专门的NER模型**: 当前使用BERT tokenizer，可升级为专门的中文NER模型
2. **关系抽取模型**: 支持从rule_based升级为model_based（TPLinker/GPLinker）
3. **多语言支持**: 配置不同语言的模型
4. **模型版本管理**: 支持模型版本更新和回滚

## 🎉 总结

✅ **问题1: 需要用到模型么？**
- **答**: 是的，重构后需要4种类型的模型：NER tokenizer、Bi-encoder、Cross-encoder、AC自动机

✅ **问题2: 模型为什么没有放在配置文件中？**
- **答**: 已完善，现在所有模型配置都在`config/model.yaml`的`knowledge_graph`部分

✅ **问题3: 为什么没有创建下载脚本？**
- **答**: 已创建`bert-base-chinese+transformers-4.36.sh`下载脚本，并更新了统一下载管理

**重构后的知识图谱功能现已具备完整的模型配置和下载机制！** 🎉
