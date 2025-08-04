# GraphRAG系统

GraphRAG是一个基于图数据库和向量数据库的智能文档检索系统，支持多种文档格式的处理和智能搜索。

## 项目架构

```
GraphRAG/
├── app/                    # 应用主目录
│   ├── routes/            # 路由层
│   │   ├── FileRoutes.py  # 文件管理路由
│   │   └── SearchRoutes.py # 智能检索路由
│   └── service/           # 服务层
│       ├── FileService.py # 文件管理服务
│       ├── SearchService.py # 智能检索服务
│       └── pdf/           # PDF处理服务
│           ├── PdfExtractService.py # PDF内容提取
│           └── PdfVectorService.py  # PDF向量化
├── config/                # 配置文件
│   ├── db.yaml           # 数据库配置
│   ├── model.yaml        # 模型配置
│   ├── config.yaml       # 应用配置
│   └── prompt.yaml       # 提示词配置
├── utils/                 # 工具类
│   ├── MySQLManager.py   # MySQL管理器
│   ├── Neo4jManager.py   # Neo4j管理器
│   └── MilvusManager.py  # Milvus管理器
├── install/              # 安装文件
│   ├── db.sql           # 数据库脚本
│   └── download_embedding_model.py # 模型下载脚本
├── templates/            # 前端模板
├── test/                # 测试文件
├── app.py               # 主应用文件
├── requirements.txt      # 依赖包
└── README.md           # 项目说明
```

## 技术栈

- **后端框架**: Flask 2.3.3
- **数据库**: MySQL 8.0, Neo4j, Milvus
- **ORM**: SQLAlchemy 2.0.23
- **向量模型**: paraphrase-multilingual-mpnet-base-v2
- **大语言模型**: DeepSeek API
- **文档处理**: Unstructured

## 环境要求

- Python 3.11+
- MySQL 8.0
- Neo4j 5.x
- Milvus 2.3.x

## 安装部署

### 1. 克隆项目

```bash
git clone <repository-url>
cd GraphRAG
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库

编辑 `config/db.yaml` 文件，配置数据库连接信息：

```yaml
mysql:
  host: 192.168.16.26
  port: 3306
  username: root
  password: !200808Xx
  database: graph_rag

milvus:
  host: 192.168.16.26
  port: 19530
  database: graph_rag
  collection: graph_rag

neo4j:
  host: 192.168.16.26
  port: 7687
  username: neo4j
  password: !200808Xx
```

### 4. 初始化数据库

执行数据库初始化脚本：

```bash
mysql -h 192.168.16.26 -u root -p < install/db.sql
```

### 5. 下载嵌入模型

```bash
python install/download_embedding_model.py
```

### 6. 启动应用

```bash
python app.py
```

应用将在 `http://localhost:5000` 启动。

## API接口

### 文件管理接口

- `POST /api/file/upload` - 文件上传
- `GET /api/file/list` - 获取文件列表
- `GET /api/file/{file_id}` - 获取文件信息
- `DELETE /api/file/{file_id}` - 删除文件
- `POST /api/file/{file_id}/process` - 处理文件
- `GET /api/file/{file_id}/status` - 获取文件状态

### 智能检索接口

- `POST /api/search/query` - 智能检索
- `POST /api/search/semantic` - 语义搜索
- `POST /api/search/keyword` - 关键词搜索
- `POST /api/search/hybrid` - 混合搜索
- `POST /api/search/answer` - 生成答案
- `GET /api/search/history` - 获取搜索历史

## 配置说明

### 数据库配置 (config/db.yaml)

包含MySQL、Milvus、Neo4j的配置信息，支持连接池配置。

### 模型配置 (config/model.yaml)

配置DeepSeek API和嵌入模型的相关参数。

### 应用配置 (config/config.yaml)

配置文件保存目录、Flask应用参数等。

### 提示词配置 (config/prompt.yaml)

配置各种场景下的提示词模板。

## 开发说明

### 项目结构

- **路由层**: 只处理入参和返参，具体实现调用服务层
- **服务层**: 实现具体的业务逻辑
- **工具层**: 提供数据库连接、模型管理等基础功能

### 扩展新文件类型

1. 在 `app/service/` 下创建对应的处理服务
2. 在 `FileService.py` 中添加对应的处理逻辑
3. 更新配置文件中的路径映射

### 添加新的搜索方式

1. 在 `SearchService.py` 中实现新的搜索方法
2. 在 `SearchRoutes.py` 中添加对应的路由
3. 更新相关配置

## 注意事项

1. 所有配置文件都需要写清注释
2. 数据库脚本需要手动执行，不会自动初始化
3. 嵌入模型需要手动下载部署
4. 确保所有依赖的数据库服务正常运行

## 许可证

本项目采用 MIT 许可证。 