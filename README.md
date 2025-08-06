# GraphRAG 系统

基于知识图谱的检索增强生成系统，使用Python 3.11、Flask、MySQL、Milvus、Neo4j构建。

## 系统架构

```
GraphRAG/
├── app/                    # 应用主目录
│   ├── routes/            # 路由层
│   ├── service/           # 服务层
│   └── __init__.py
├── config/                # 配置文件
├── utils/                 # 数据库管理器
├── install/               # 安装脚本
├── logs/                  # 日志文件
├── uploads/               # 上传文件
├── processed/             # 处理后文件
├── temp/                  # 临时文件
└── templates/             # 前端模板
```

## 功能特性

- 📄 多格式文档处理（PDF、Word、Excel、PPT等）
- 🔍 智能内容提取和分块
- 🧠 基于Transformer的向量化
- 🌐 知识图谱构建和管理
- 🔎 多模式智能搜索（向量、图谱、混合）
- 💬 智能问答系统
- 📊 统计分析和可视化

## 环境要求

- Python 3.11+
- MySQL 8.0+
- Milvus 2.3+
- Neo4j 5.0+

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository_url>
cd GraphRAG

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据库配置

#### MySQL
```bash
# 连接MySQL并执行初始化脚本
mysql -h 192.168.16.26 -P 3306 -u root -p < install/db.sql
```

#### Milvus
确保Milvus服务运行在 `192.168.16.26:19530`

#### Neo4j
确保Neo4j服务运行在 `192.168.16.26:7687`

### 3. 配置文件

检查并修改 `config/` 目录下的配置文件：

- `db.yaml`: 数据库连接配置
- `model.yaml`: AI模型配置
- `config.yaml`: 应用配置
- `prompt.yaml`: 提示词配置

### 4. 启动服务

```bash
# 直接启动
python app.py

# 或使用命令行参数
python app.py run-server --host 0.0.0.0 --port 5000

# 调试模式
python app.py run-server --debug
```

### 5. 访问系统

- 主页: http://localhost:5000
- API文档: http://localhost:5000/docs
- 健康检查: http://localhost:5000/health

## API 使用示例

### 文件上传
```bash
curl -X POST http://localhost:5000/api/file/upload \
  -F "file=@document.pdf" \
  -F "metadata={\"uploader\": \"user1\"}"
```

### 文件处理
```bash
curl -X POST http://localhost:5000/api/file/1/process \
  -H "Content-Type: application/json" \
  -d '{"steps": ["extract", "vectorize", "graph"]}'
```

### 向量搜索
```bash
curl -X POST http://localhost:5000/api/search/vector \
  -H "Content-Type: application/json" \
  -d '{"query": "人工智能的应用", "top_k": 10}'
```

### 智能问答
```bash
curl -X POST http://localhost:5000/api/search/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是GraphRAG？", "context_limit": 5}'
```

## 项目结构说明

### 服务层 (app/service/)
- `FileService.py`: 文件管理服务
- `SearchService.py`: 智能检索服务
- `pdf/`: PDF文档处理服务
  - `PdfExtractService.py`: 内容提取
  - `PdfVectorService.py`: 向量化处理
  - `PdfGraphService.py`: 图数据库处理

### 路由层 (app/routes/)
- `FileRoutes.py`: 文件管理API路由
- `SearchRoutes.py`: 搜索和问答API路由

### 数据库管理 (utils/)
- `MySQLManager.py`: MySQL数据库管理
- `MilvusManager.py`: Milvus向量数据库管理
- `Neo4jManager.py`: Neo4j图数据库管理

## 开发指南

### 添加新的文件类型支持

1. 在 `app/service/` 下创建对应的文件夹（如`word/`）
2. 实现提取、向量化和图处理服务
3. 在 `FileService.py` 中添加支持逻辑

### 自定义AI模型

1. 修改 `config/model.yaml` 中的模型配置
2. 在服务类中调整模型加载逻辑

### 扩展搜索功能

1. 在 `SearchService.py` 中添加新的搜索方法
2. 在 `SearchRoutes.py` 中添加对应的API路由

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查配置文件中的连接信息
   - 确保数据库服务正常运行
   - 检查网络连通性

2. **模型加载失败**
   - 检查模型路径和缓存目录
   - 确保有足够的磁盘空间
   - 检查网络连接（首次下载模型时）

3. **文件上传失败**
   - 检查文件大小限制
   - 确保上传目录有写权限
   - 检查文件类型是否支持

### 日志查看

```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
grep ERROR logs/app.log
```

## 性能优化

### 数据库优化
- 定期清理过期日志和临时数据
- 为大表创建适当的索引
- 监控数据库性能指标

### 向量搜索优化
- 调整Milvus索引参数
- 控制向量批处理大小
- 使用GPU加速（如果可用）

### 缓存策略
- 启用Redis缓存
- 缓存热门查询结果
- 预加载常用模型

## 部署建议

### 生产环境
- 使用WSGI服务器（如Gunicorn）
- 配置反向代理（如Nginx）
- 设置进程监控（如Supervisor）
- 配置日志轮转和监控

### Docker部署
项目包含Dockerfile和docker-compose.yml（需要创建）

### 扩展性
- 使用负载均衡器分发请求
- 数据库读写分离
- 分布式向量存储

## 贡献指南

1. Fork项目
2. 创建特性分支
3. 提交变更
4. 推送到分支
5. 创建Pull Request

## 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 联系方式

如有问题或建议，请通过以下方式联系：
- 邮箱: [your-email@example.com]
- 项目地址: [repository_url]