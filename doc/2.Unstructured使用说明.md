# Unstructured PDF提取服务使用说明

## 概述

本项目已完成从PyMuPDF到Unstructured库的迁移重构。新的实现提供了更强大和灵活的PDF内容提取能力。

## 主要改进

### 1. 使用Unstructured库
- **更强大的内容提取**: 支持复杂布局、表格、图片等多种元素
- **智能内容分类**: 自动识别标题、正文、表格、列表等不同类型的内容
- **坐标信息**: 保留元素在页面中的位置信息
- **多种提取策略**: 支持auto、fast、ocr_only、hi_res等不同策略

### 2. 丰富的配置选项
- **完整的配置文件**: `config/Unstructured.yaml`包含所有配置项
- **灵活的参数调整**: 支持分块策略、OCR语言、表格提取等多种配置
- **性能优化选项**: 支持多进程、缓存、内存管理等性能配置

### 3. 结构化输出
- **JSON格式输出**: 返回结构化的JSON数据
- **元数据保留**: 包含丰富的元数据信息
- **分类存储**: 按内容类型分类存储不同元素

## 配置说明

### 核心配置项

```yaml
# 基础配置
basic:
  output_format: "application/json"     # 输出格式
  chunking_strategy: "by_title"         # 分块策略
  max_characters: 1000                  # 最大字符数
  coordinates: true                     # 是否包含坐标信息

# PDF处理配置
pdf:
  strategy: "auto"                      # 提取策略
  ocr_languages: ["chi_sim", "eng"]    # OCR语言
  pdf_infer_table_structure: true      # 表格结构推断
  pdf_extract_images: true             # 图片提取
```

### 提取策略说明

- **auto**: 自动选择最佳策略
- **fast**: 快速提取，适合简单文档
- **ocr_only**: 仅使用OCR，适合图片化PDF
- **hi_res**: 高分辨率提取，适合复杂布局

## API变化

### 输入参数保持不变
```python
# 调用方式不变
result = pdf_extract_service.extract_pdf_content(file_path, document_id)
```

### 输出格式变化
```json
{
  "success": true,
  "message": "PDF内容提取成功",
  "extracted_data": {
    "basic_info": {
      "document_id": 1,
      "total_elements": 25,
      "element_type_distribution": {
        "Title": 3,
        "NarrativeText": 15,
        "Table": 2,
        "Image": 5
      },
      "total_text_length": 5000,
      "total_pages": 10
    },
    "unstructured_elements": [
      {
        "type": "Title",
        "text": "文档标题",
        "metadata": {
          "page_number": 1,
          "filename": "document.pdf"
        },
        "coordinates": {
          "points": [[10, 10], [100, 30]],
          "system": "PixelSpace"
        },
        "category": "Title"
      }
    ],
    "structured_content": {
      "titles": [],
      "text_blocks": [],
      "tables": [],
      "lists": [],
      "images": [],
      "headers": [],
      "footers": []
    },
    "chunks": [],
    "extraction_metadata": {
      "total_elements": 25,
      "total_pages": 10,
      "extraction_time": "2024-01-01T00:00:00",
      "unstructured_version": "0.12.0",
      "extraction_strategy": "auto"
    }
  }
}
```

## 测试和验证

### 运行测试脚本
```bash
# 运行Unstructured实现测试
python test/test_unstructured_pdf_extract.py
```

### 测试内容
1. **配置加载测试**: 验证Unstructured.yaml配置正确加载
2. **PDF提取模拟测试**: 模拟PDF内容提取过程
3. **文本分块测试**: 验证分块功能正常工作
4. **版本信息测试**: 获取Unstructured库版本信息

## 性能优化建议

### 1. 策略选择
- **简单文档**: 使用`fast`策略
- **复杂布局**: 使用`hi_res`策略
- **图片化PDF**: 使用`ocr_only`策略
- **不确定**: 使用`auto`策略让系统自动选择

### 2. 缓存配置
```yaml
performance:
  cache_dir: "./temp/unstructured_cache"
  skip_download: false
```

### 3. 多进程处理
```yaml
performance:
  multiprocessing: true
  num_processes: 4
```

## 故障排除

### 常见问题

1. **依赖安装失败**
   ```bash
   # 更新pip和setuptools
   pip install --upgrade pip setuptools
   
   # 安装依赖
   pip install -r requirements.txt
   ```

2. **OCR识别失败**
   - 检查OCR语言配置
   - 确保tesseract正确安装
   - 调整OCR语言设置

3. **内存使用过高**
   - 调整`max_characters`减少分块大小
   - 启用缓存减少重复处理
   - 关闭不必要的功能（如图片提取）

4. **提取速度慢**
   - 使用`fast`策略
   - 关闭坐标信息提取
   - 减少OCR语言数量

### 日志检查
```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误信息
grep ERROR logs/app.log
```

## 迁移注意事项

### 1. 数据库兼容性
- 分块表结构保持不变
- 新增extraction_metadata字段信息
- 兼容现有的向量化和图处理流程

### 2. API兼容性
- 输入参数完全兼容
- 输出格式更加丰富
- 错误处理机制增强

### 3. 性能影响
- 首次运行需要下载模型
- 内存使用可能增加
- 处理时间可能延长（但质量提升）

## 最佳实践

### 1. 配置优化
- 根据文档类型选择合适的策略
- 合理设置分块大小和重叠
- 启用必要的功能，关闭不需要的特性

### 2. 错误处理
- 设置合理的重试次数
- 记录详细的错误日志
- 提供降级处理方案

### 3. 监控和维护
- 定期清理缓存目录
- 监控内存和磁盘使用
- 更新Unstructured库版本

## 技术支持

如遇到问题，请：
1. 检查配置文件格式和内容
2. 运行测试脚本验证功能
3. 查看详细的错误日志
4. 参考Unstructured官方文档