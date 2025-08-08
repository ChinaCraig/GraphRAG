# 🔧 查询优化JSON解析问题修复说明

## 🚨 问题描述

用户在使用查询优化功能时遇到错误：
```
[2025-08-08 12:26:32,131] ERROR in SearchService: 查询优化失败: '\n  "core_keywords"'
```

**问题根因：** DeepSeek API返回的响应不是纯JSON格式，包含额外的文本或格式问题，导致`json.loads()`解析失败。

## 🎯 解决方案

### 1. **增强JSON解析容错能力**

添加了`_parse_deepseek_json_response()`方法，包含4种解析策略：

#### **方法1：标准JSON解析**
```python
return json.loads(response.strip())
```
适用于标准JSON响应。

#### **方法2：正则提取JSON块**
```python
json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
matches = re.findall(json_pattern, response, re.DOTALL)
```
适用于包含解释文字的响应。

#### **方法3：逐行解析**
```python
for line in lines:
    if line.startswith('{'):
        # 开始收集JSON行
```
适用于多行格式响应。

#### **方法4：应急解析**
```python
pattern = r'\"core_keywords\":\\s*\"([^\"]*)\";
# 手动提取关键信息
```
当所有标准方法失败时的保底方案。

### 2. **优化提示词格式**

**原提示词问题：**
- 格式要求不够严格
- 没有明确禁止额外文字
- 缺少示例

**新提示词特点：**
```yaml
**重要：请严格按照以下JSON格式返回，不要添加任何解释文字或其他内容：**

{
  "core_keywords": "核心关键词",
  "search_intent": "检索意图",
  "refined_query": "优化查询",
  "removed_noise": ["噪音词1", "噪音词2"]
}

示例：
用户查询："帮我查询一下HCP的相关内容"
返回：{
  "core_keywords": "HCP",
  "search_intent": "查找HCP(宿主细胞蛋白)相关信息",
  "refined_query": "HCP",
  "removed_noise": ["帮我", "查询", "一下", "相关", "内容"]
}
```

### 3. **改进错误处理和日志**

**原错误处理：**
```python
except json.JSONDecodeError as e:
    self.logger.warning(f\"无法解析查询优化结果: {response}, 错误: {str(e)}\")
```

**新错误处理：**
```python
except Exception as e:
    self.logger.error(f\"查询优化失败: {str(e)}, 原始响应: {response[:200]}...\")
```

## 📊 修复效果对比

### **修复前 ❌**
```
DeepSeek响应: "根据分析，\n  \"core_keywords\": \"HCP\""
解析结果: JSONDecodeError - 查询优化失败
降级处理: 使用原始查询（精度下降）
```

### **修复后 ✅**
```
DeepSeek响应: "根据分析，\n  \"core_keywords\": \"HCP\""
解析策略: 方法1失败 → 方法2失败 → 方法4成功提取
解析结果: {"core_keywords": "HCP", "refined_query": "HCP"}
优化效果: 查询"帮我查询一下HCP" → "HCP"（精度提升）
```

## 🧪 测试验证

运行测试脚本验证修复效果：
```bash
python test_query_optimization.py
```

**测试覆盖：**
- ✅ 标准JSON响应
- ✅ 包含解释文字的响应  
- ✅ 多行JSON格式
- ✅ 带换行和空格的JSON
- ✅ 不完整JSON的应急处理

## ⚙️ 配置选项

在`model.yaml`中添加了控制开关：
```yaml
query_optimization:
  enabled: true                    # 启用/禁用查询优化
  fallback_on_failure: true       # 失败时降级为原始查询  
  log_optimization_details: true  # 记录优化详情
```

## 🎯 使用建议

1. **监控日志**：观察优化成功率和错误模式
2. **性能调优**：根据实际效果调整提示词
3. **备用方案**：如果API不稳定，可临时禁用优化功能
4. **定期测试**：使用测试脚本验证功能正常

## 🔮 后续改进方向

1. **缓存机制**：缓存常见查询的优化结果
2. **本地NER**：集成本地实体识别减少API依赖
3. **智能降级**：根据查询复杂度选择是否启用优化
4. **A/B测试**：对比优化前后的检索效果

通过这次修复，查询优化功能的健壮性大幅提升，能够处理各种格式的API响应，确保用户查询能够得到最优的检索效果。
