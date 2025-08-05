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

## JSON输出结构详细说明

### 顶级结构
提取服务返回的JSON包含4个主要节点：

```json
{
  "document_metadata": {...},      // 文档元数据信息
  "content_summary": {...},        // 内容摘要统计
  "structured_content": [...],     // 结构化内容元素数组
  "extraction_metadata": {...}     // 提取过程元数据
}
```

### 1. document_metadata（文档元数据）
**作用**: 记录PDF文档的基础信息，用于文档管理和来源追踪
**内容说明**:
```json
{
  "file_name": "文件名.pdf",                    // PDF文件名
  "file_path": "/absolute/path/to/file.pdf",   // PDF文件绝对路径
  "file_size": 18926541,                       // 文件大小（字节）
  "file_hash": "c8a436bf8cfbb3a49da148f6f678afcc", // MD5哈希值，用于文件唯一标识
  "created_time": "2025-08-05T11:24:11.713114", // 文件创建时间（ISO格式）
  "modified_time": "2025-06-12T14:18:12",       // 文件修改时间（ISO格式）
  "file_extension": ".pdf"                       // 文件扩展名
}
```

### 2. content_summary（内容摘要）
**作用**: 提供文档内容的整体统计信息，便于快速了解文档结构和特征
**内容说明**:
```json
{
  "total_characters": 1546,           // 文档总字符数
  "total_pages": 4,                   // 文档总页数
  "page_range": "1-4",                // 页面范围描述
  "title_hierarchy": [                // 文档标题层次结构（前10个）
    "CHO细胞宿主蛋白检测试剂盒",
    "产品单页",
    "应用范围"
  ],
  "element_distribution": {           // 各类型元素的数量分布
    "标题": 42,                      // 标题元素数量
    "未知类型": 35,                  // 未分类元素数量
    "页眉": 3,                      // 页眉元素数量
    "正文": 1,                      // 正文段落数量
    "列表项": 8,                    // 列表项数量
    "页脚": 3                       // 页脚元素数量
  },
  "has_tables": false,               // 是否包含表格
  "has_images": false,               // 是否包含图片
  "content_density": 16.80           // 内容密度（字符数/元素数）
}
```

### 3. structured_content（结构化内容）
**作用**: 存储文档的所有结构化元素，这是向量化和实体关系提取的核心数据
**内容说明**: 数组形式，每个元素包含以下字段：

```json
{
  "element_id": "elem_000000",              // 元素唯一标识符
  "element_type": "Title",                  // 元素类型（英文）
  "element_type_cn": "标题",                // 元素类型（中文）
  "text_content": "CHO细胞宿主蛋白检测试剂盒", // 元素文本内容
  "text_length": 14,                       // 文本长度
  "page_number": 1,                        // 所在页码
  "coordinates": {                         // 坐标信息
    "points": [                           // 元素边界框坐标点
      [63.952, 175.198],                 // 左上角坐标
      [63.952, 209.198],                 // 左下角坐标
      [534.308, 209.198],                // 右下角坐标
      [534.308, 175.198]                 // 右上角坐标
    ],
    "system": "PixelSpace",               // 坐标系统类型
    "layout_width": null,                 // 布局宽度
    "layout_height": null                 // 布局高度
  },
  "source_filename": "文件名.pdf",          // 来源文件名
  "source_filetype": "application/pdf",    // 来源文件类型
  "detected_languages": ["kor"],           // 检测到的语言
  "vectorization_text": "[标题] CHO细胞宿主蛋白检测试剂盒", // 向量化专用文本
  "context_info": {                       // 上下文信息（用于实体关系提取）
    "position_in_document": {             // 在文档中的位置信息
      "index": 0,                        // 元素索引
      "relative_position": 0.0,          // 相对位置（0-1）
      "is_beginning": true,              // 是否在文档开头
      "is_middle": false,                // 是否在文档中间
      "is_end": false                    // 是否在文档末尾
    },
    "page_context": {                    // 页面上下文
      "page_number": 1,                  // 页码
      "page_position": "第1页"            // 页面位置描述
    },
    "type_context": {                    // 类型上下文
      "element_type": "Title",           // 元素类型
      "is_title": true,                  // 是否为标题
      "is_content": false,               // 是否为内容
      "is_structured": false             // 是否为结构化元素（表格/图片）
    }
  }
}
```

### 4. extraction_metadata（提取元数据）
**作用**: 记录提取过程的技术信息，用于质量控制和调试
**内容说明**:
```json
{
  "extraction_time": "2025-08-05T17:50:01.541996", // 提取时间
  "total_elements": 92,                             // 提取的总元素数
  "element_type_counts": {                          // 各类型元素统计
    "标题": 42,
    "未知类型": 35,
    "页眉": 3,
    "正文": 1,
    "列表项": 8,
    "页脚": 3
  },
  "processing_strategy": "fast",                    // 处理策略
  "languages_detected": ["zh", "en"]               // 支持的语言列表
}
```

## JSON结构的设计理念

### 向量化优化
- **vectorization_text字段**: 专门为向量化设计，包含元素类型标签和内容，格式："[类型] 内容"
- **text_content字段**: 原始文本内容，保持PDF中的原始格式
- **element_type_cn字段**: 中文类型标识，支持中文场景的类型过滤

### 实体关系提取优化
- **context_info字段**: 提供丰富的上下文信息，支持基于位置和类型的关系推理
- **coordinates字段**: 精确的空间位置信息，支持空间关系分析
- **page_context字段**: 页面级别的上下文，支持跨页关系识别

### 知识库检索优化
- **element_id字段**: 唯一标识符，支持精确定位和引用
- **page_number字段**: 支持页面级别的过滤和定位
- **file_hash字段**: 文档唯一标识，支持多文档场景的来源追踪
- **hierarchical结构**: 保持文档的层次结构，支持结构化检索

## 自动保存功能
- JSON文件自动保存到config.yaml中配置的json_path目录
- 文件命名格式：`{原PDF文件名}_extracted.json`
- 支持自动创建目录结构
- 在提取结果中返回保存路径信息



