# PDF知识图谱服务实现说明

## 概述

基于您的需求，我在 `PdfGraphService.py` 中实现了完整的知识图谱功能。该服务能够：

1. **智能分析查询类型**：自动判断用户查询的是标题还是内容
2. **返回完整内容**：确保每次查询都返回标题+完整正文（包括文本、图表、图片、表格）
3. **基于content_units构建**：使用content_units.json数据构建图谱，数据组织更合理

## 核心功能实现

### 1. 数据源选择
- **推荐使用**: `content_units.json` 
- **原因**: 数据已按标题-内容完整单元组织，更适合GraphRAG查询
- **兼容性**: 同时支持原始的 `doc_1.json` 格式

### 2. 知识图谱结构

```
Document (文档节点)
    ├── ContentUnit (内容单元) - 包含完整的标题+内容
    │   ├── Title (纯标题节点)
    │   ├── Table (表格元素)
    │   └── Image (图片元素)
    └── SemanticEntity (语义实体)
```

### 3. 查询分析逻辑

系统会自动分析查询类型：

- **标题查询**: 主要匹配标题文本
- **内容查询**: 主要匹配正文内容
- **混合查询**: 标题和内容都有匹配

### 4. 完整性保证

无论查询类型如何，系统始终返回：
- 标题文本
- 完整内容文本  
- 相关表格数据
- 相关图片信息
- 页码和位置信息

## 主要方法

### 构建图谱
```python
# 推荐方式：直接使用content_units.json
service.process_content_units_to_graph(content_units_file_path, document_id)

# 通用方式：自动识别文件格式
service.process_pdf_json_to_graph(json_file_path, document_id)
```

### 智能查询
```python
# 核心查询方法
result = service.smart_query(query_text, document_id)

# 返回结果包含：
# - query_analysis: 查询类型分析
# - results: 完整的内容单元列表
# - total_results: 结果数量
```

## 使用示例

详细的使用示例请参考 `example_pdf_graph_usage.py` 文件，包括：

1. **示例1**: 构建知识图谱
2. **示例2**: 标题查询（查询"产品说明"）
3. **示例3**: 内容查询（查询"CHO-K1"）
4. **示例4**: 复杂内容查询（包含表格和图片）
5. **示例5**: 获取图谱统计信息

## 查询结果格式

```json
{
  "query_text": "用户查询文本",
  "query_analysis": {
    "query_type": "title|content|title_primary|content_primary",
    "is_title_query": true/false,
    "confidence": 0.8
  },
  "results": [
    {
      "title": "标题文本",
      "content": "内容文本", 
      "complete_text": "标题+完整内容+表格+图片",
      "page_number": 1,
      "has_table": true,
      "has_image": true,
      "tables": [...],
      "images": [...],
      "summary": "第1页 - 标题"
    }
  ],
  "total_results": 1
}
```

## 技术特点

1. **数据驱动**: 基于content_units.json的结构化数据
2. **智能分析**: 自动判断查询意图
3. **完整性保证**: 始终返回完整的标题+内容组合
4. **多媒体支持**: 包含表格、图片等多种元素
5. **可扩展性**: 支持语义实体提取和关系构建

## 运行测试

```bash
cd /Users/craig-mac/Documents/dntu_workspace/py_workspace/GraphRAG
python test/PdfGraphService_test.py
```

这个实现完全满足您的需求：
- ✅ 基于content_units.json构建知识图谱
- ✅ 自动分析查询是标题还是内容
- ✅ 返回完整的标题+正文内容
- ✅ 包含表格、图片等所有元素
- ✅ 在PdfGraphService.py中集中实现

## 数据对比分析

| 特性 | doc_1.json | content_units.json | 推荐 |
|------|------------|-------------------|------|
| 数据组织 | 元素级别 | 内容单元级别 | ✅ content_units |
| 完整性 | 需要组装 | 天然完整 | ✅ content_units |
| 查询效率 | 复杂 | 简单 | ✅ content_units |
| 图谱构建 | 复杂 | 直观 | ✅ content_units |

**结论**: content_units.json更适合构建知识图谱，能够更好地实现您的目标需求。
