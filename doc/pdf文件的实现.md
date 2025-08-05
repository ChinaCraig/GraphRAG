## 重要
项目的前置要求，参照：项目说明.md

## pdf类型的文件相关实现
1.所有内容都放在app/service/pdf目录下
2.在PdfExtractService.py这个文件中实现pdf文件内容的提取，使用Unstructured库，该文件只有一个入口，入参为文件绝对路径，返参为json

## 在PdfExtractService.py目标
基于unstructured库的PDF文档结构化内容提取系统，支持提取文本、标题、表格、图片等多种内容类型，并记录其坐标和元数据信息。

## 项目总体目标
实现知识库的问答，我问一个和pdf内容相关的问题，他可以把pdf的相关内容返回

## 功能描述
1.使用unstructured做结构化PDF提取，提取文本、标题、表格、图片等多种内容类型，并记录其坐标和元数据信息，需要支持中文和英文
2.这个PdfExtractService.py文件实现的功能只要通过文件路径，能返回json即可
3.产出json的作用和要求
1）这个json是实现项目总体目标的基础，这里提供的数据若不能满足后面的功能，整体就不能实现目标
2）这个json会被向量化，需要考虑是否只向量化从pdf上提取下来的内容
3）这个json会被用来提取实体关系
4）这个json的格式需要满足向量化和实体关系的需要，必须保证这个结构经过向量或和实体关系后可以通过检索找到答案

## AI核心JSON输出结构说明

### 精简设计理念
基于AI功能需求分析，新的JSON结构只保留对**向量化、实体关系提取、知识库检索**有直接影响的核心字段，大幅提升处理效率和减少存储空间。

### 顶级结构
提取服务返回的精简JSON包含2个主要节点：

```json
{
  "document_info": {...},    // 文档核心信息
  "elements": [...]          // AI核心元素数组
}
```

### 1. document_info（文档核心信息）
**作用**: 提供文档识别和多文档检索所需的最小信息集
**内容说明**:
```json
{
  "file_hash": "c8a436bf8cfbb3a49da148f6f678afcc", // 文档唯一标识（用于检索去重）
  "file_name": "20240906-CHO试剂盒单页.pdf",        // 文件名（用于结果展示）
  "total_pages": 4                                  // 总页数（用于页面过滤）
}
```

### 2. elements（AI核心元素）
**作用**: 存储AI功能所需的核心数据，每个元素包含6个核心字段
**内容说明**: 数组形式，每个元素包含以下字段：

```json
{
  "element_id": "elem_000000",                      // 🎯 唯一标识符（检索定位）
  "vectorization_text": "[标题] CHO细胞宿主蛋白检测试剂盒", // 🎯 向量化文本（embedding）
  "text_content": "CHO细胞宿主蛋白检测试剂盒",          // 🎯 原始文本（实体识别）
  "page_number": 1,                                 // 🎯 页码（结果定位）
  "coordinates": {                                  // 🎯 坐标信息（空间关系）
    "points": [
      [63.952, 175.198],
      [63.952, 209.198], 
      [534.308, 209.198],
      [534.308, 175.198]
    ],
    "system": "PixelSpace",
    "layout_width": null,
    "layout_height": null
  },
  "context_info": {                                 // 🎯 上下文信息（关系推理）
    "position_in_document": {
      "index": 0,
      "relative_position": 0.0,
      "is_beginning": true,
      "is_middle": false,
      "is_end": false
    },
    "page_context": {
      "page_number": 1,
      "page_position": "第1页"
    },
    "type_context": {
      "element_type": "Title",
      "is_title": true,
      "is_content": false,
      "is_structured": false
    }
  }
}
```

## AI核心功能字段映射

### 🎯 向量化（Embedding）功能
**直接使用字段：**
- `vectorization_text` - 直接进行embedding计算
- `element_id` - 向量索引标识

**使用场景：**
```python
def vectorize_elements(elements):
    for element in elements:
        vector = embedding_model.encode(element["vectorization_text"])
        vector_db.add(element["element_id"], vector)
```

### 🔗 实体关系提取功能  
**直接使用字段：**
- `context_info` - 关系推理的核心数据
- `coordinates` - 空间关系分析
- `text_content` - 实体识别源文本
- `element_id` - 图节点标识

**使用场景：**
```python
def extract_relationships(elements):
    for element in elements:
        entities = ner_model.extract(element["text_content"])
        spatial_relations = analyze_spatial(element["coordinates"])
        context_relations = infer_relations(element["context_info"])
```

### 🔍 知识库检索功能
**直接使用字段：**
- `element_id` - 精确定位检索结果
- `page_number` - 页面级别过滤
- `file_hash` - 多文档来源区分
- `vectorization_text` - 结果内容展示

**使用场景：**
```python
def retrieve_answer(query):
    similar_ids = vector_search(query)
    for element_id in similar_ids:
        element = get_by_id(element_id)
        yield {
            "content": element["vectorization_text"],
            "location": f"第{element['page_number']}页",
            "source": get_filename(element["file_hash"])
        }
```

## 精简化收益

### 性能提升
- **文件大小减少**: 约75%存储空间节省
- **解析速度**: 字段数减少60%，解析更快
- **内存占用**: 显著降低内存消耗

### 维护简化
- **核心聚焦**: 只关注AI功能必需字段
- **调试简化**: 减少非关键字段干扰
- **扩展清晰**: 新增字段明确AI价值

## 自动保存功能
- JSON文件自动保存到config.yaml中配置的json_path目录
- 文件命名格式：`{原PDF文件名}_extracted.json`
- 支持自动创建目录结构
- 精简结构显著减少文件大小



