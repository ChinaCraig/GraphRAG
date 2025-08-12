-- GraphRAG数据库初始化脚本 v2.2
-- 创建GraphRAG系统所需的所有数据库表
-- 数据库连接信息：192.168.2.202:3306, root, zhang
--
-- 更新日志：
-- v2.2: 新增GraphRAG专用图谱表和问题修复
--   - 新增graph_nodes表：GraphRAG专用节点表，支持Section/Block/Entity/Claim等多种节点类型
--   - 新增graph_relations表：GraphRAG专用关系表，支持MENTIONS/HAS_ENTITY/MEASURES等关系类型
--   - 修复了中文实体识别的正则表达式边界问题（移除\b单词边界）
--   - 修复了bbox规范化支持列表格式数据：[[x1,y1],[x2,y2]]
--   - 修复了figures/tables表重复主键问题：elem_id加section_id前缀确保唯一性
--   - 修复了table_rows表外键约束问题：确保与tables表主键一致
--   - node_id字段设置为可空，解决数据插入失败问题
-- v2.1: 新增PDF结构化数据MySQL存储功能
--   - 新增sections表：存储PDF章节信息（一节一行）
--   - 新增figures表：存储PDF图片信息（一图一行，遍历blocks.type='figure'）
--   - 新增tables表：存储PDF表格信息（一表一行，遍历blocks.type='table'）
--   - 新增table_rows表：存储PDF表格行数据（一行一行）
--   - 主键elem_id/section_id与Neo4j、向量库、ES保持一致
--   - 支持bbox坐标规范化、表格列数推断、行文本格式化
--   - 优化索引结构，提升PDF结构化数据查询性能
-- v2.0: 完整支持"一家子"概念的GraphRAG系统
--   - document_chunks表支持element_id字段，实现内容关联
--   - content字段改为JSON类型，存储完整的content_units数据
--   - 支持table、img、chars结构化数据存储
--   - 添加content_hash字段用于内容去重和校验
--   - 优化索引结构，提升查询性能
--   - 增加GraphRAG专用配置项

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `graph_rag` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE `graph_rag`;

-- 设置字符集
SET NAMES utf8mb4;

-- ===========================
-- 文档管理相关表
-- ===========================

-- 文档表
DROP TABLE IF EXISTS `documents`;
CREATE TABLE `documents` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '文档ID',
  `filename` varchar(255) NOT NULL COMMENT '文件名',
  `file_path` varchar(500) NOT NULL COMMENT '文件路径',
  `file_type` varchar(50) NOT NULL COMMENT '文件类型',
  `file_size` bigint(20) NOT NULL COMMENT '文件大小(字节)',
  `upload_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  `process_status` varchar(50) NOT NULL DEFAULT 'pending' COMMENT '处理状态',
  `process_time` datetime DEFAULT NULL COMMENT '处理时间',
  `content_hash` varchar(64) DEFAULT NULL COMMENT '内容哈希',
  `metadata` text COMMENT '元数据(JSON格式)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_content_hash` (`content_hash`),
  KEY `idx_file_type` (`file_type`),
  KEY `idx_process_status` (`process_status`),
  KEY `idx_upload_time` (`upload_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档表';

-- 文档分块表
-- 更新：支持"一家子"概念的完整结构，element_id用于关联同一标题下的所有内容
-- content字段存储完整的content_units JSON数据，包含table、img、chars结构化信息
DROP TABLE IF EXISTS `document_chunks`;
CREATE TABLE `document_chunks` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '分块ID',
  `document_id` int(11) NOT NULL COMMENT '文档ID',
  `element_id` varchar(50) NOT NULL COMMENT '一家子的唯一标识符（标题ID），用于关联同一标题下的所有内容',
  `chunk_index` int(11) NOT NULL COMMENT '分块索引',
  `content` json NOT NULL COMMENT 'content_units的完整JSON数据，包含向量化内容和结构化数据(table/img/chars)',
  `content_hash` varchar(64) DEFAULT NULL COMMENT '内容哈希值（SHA256），用于去重和校验',
  `vector_id` varchar(100) DEFAULT NULL COMMENT '对应Milvus中的向量ID',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_doc_chunk` (`document_id`, `chunk_index`) COMMENT '文档和分块索引的唯一约束',
  KEY `idx_document_id` (`document_id`) COMMENT '文档ID索引',
  KEY `idx_element_id` (`element_id`) COMMENT '一家子ID索引，用于快速检索相关内容',
  KEY `idx_vector_id` (`vector_id`) COMMENT '向量ID索引，用于关联Milvus数据',
  KEY `idx_create_time` (`create_time`) COMMENT '创建时间索引，用于时间范围查询',
  CONSTRAINT `fk_chunks_document` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档分块表 - 存储向量化后的内容单元和完整结构化数据';

-- ===========================
-- PDF结构化数据表（新增）
-- ===========================

-- sections表（一节一行）
-- 主键section_id与Neo4j、向量库、ES保持一致
DROP TABLE IF EXISTS `sections`;
CREATE TABLE `sections` (
  `section_id` varchar(100) NOT NULL COMMENT 'section唯一标识符（主键，与Neo4j、向量库、ES一致）',
  `doc_id` int(11) NOT NULL COMMENT '文档ID（关联documents表）',
  `version` int(11) NOT NULL DEFAULT 1 COMMENT '版本号',
  `title` text COMMENT 'section标题',
  `page_start` int(11) NOT NULL DEFAULT 1 COMMENT '起始页码',
  `page_end` int(11) NOT NULL DEFAULT 1 COMMENT '结束页码',
  `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`section_id`),
  KEY `idx_doc_id` (`doc_id`),
  KEY `idx_version` (`version`),
  KEY `idx_page_range` (`page_start`, `page_end`),
  CONSTRAINT `fk_sections_document` FOREIGN KEY (`doc_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='PDF sections表 - 存储文档章节信息';

-- figures表（一图一行）
-- 遍历blocks.type='figure'，主键elem_id与Neo4j、向量库、ES一致
DROP TABLE IF EXISTS `figures`;
CREATE TABLE `figures` (
  `elem_id` varchar(100) NOT NULL COMMENT '图片元素唯一标识符（主键，与Neo4j、向量库、ES一致）',
  `section_id` varchar(100) NOT NULL COMMENT '所属section_id',
  `image_path` varchar(500) DEFAULT NULL COMMENT '图片路径',
  `caption` text COMMENT '图片说明文字',
  `page` int(11) NOT NULL DEFAULT 1 COMMENT '所在页码',
  `bbox_norm` json DEFAULT NULL COMMENT '规范化边界框坐标（相对坐标）',
  `bind_to_elem_id` varchar(100) DEFAULT NULL COMMENT '绑定的元素ID（图文绑定关系）',
  `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`elem_id`),
  KEY `idx_section_id` (`section_id`),
  KEY `idx_page` (`page`),
  KEY `idx_bind_to_elem` (`bind_to_elem_id`),
  CONSTRAINT `fk_figures_section` FOREIGN KEY (`section_id`) REFERENCES `sections` (`section_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='PDF figures表 - 存储文档图片信息';

-- tables表（一表一行）
-- 遍历blocks.type='table'，主键elem_id与Neo4j、向量库、ES一致
DROP TABLE IF EXISTS `tables`;
CREATE TABLE `tables` (
  `elem_id` varchar(100) NOT NULL COMMENT '表格元素唯一标识符（主键，与Neo4j、向量库、ES一致）',
  `section_id` varchar(100) NOT NULL COMMENT '所属section_id',
  `table_html` longtext COMMENT '表格HTML内容',
  `n_rows` int(11) NOT NULL DEFAULT 0 COMMENT '表格行数',
  `n_cols` int(11) NOT NULL DEFAULT 0 COMMENT '表格列数（推断/解析）',
  `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`elem_id`),
  KEY `idx_section_id` (`section_id`),
  KEY `idx_table_size` (`n_rows`, `n_cols`),
  CONSTRAINT `fk_tables_section` FOREIGN KEY (`section_id`) REFERENCES `sections` (`section_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='PDF tables表 - 存储文档表格信息';

-- table_rows表（一行一行）
-- 对每个表格的rows进行存储
DROP TABLE IF EXISTS `table_rows`;
CREATE TABLE `table_rows` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `table_elem_id` varchar(100) NOT NULL COMMENT '所属表格elem_id',
  `row_index` int(11) NOT NULL COMMENT '行索引（从0开始）',
  `row_text` text COMMENT '规范化行文本（格式：项目: 线性范围 | 数值: 1–100 ng/mL | R²: 0.998）',
  `row_json` json COMMENT '行的原始键值对数据',
  `created_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_table_row` (`table_elem_id`, `row_index`) COMMENT '表格和行索引的唯一约束',
  KEY `idx_table_elem_id` (`table_elem_id`),
  KEY `idx_row_index` (`row_index`),
  CONSTRAINT `fk_table_rows_table` FOREIGN KEY (`table_elem_id`) REFERENCES `tables` (`elem_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='PDF table_rows表 - 存储表格行数据';

-- ===========================
-- 知识图谱相关表
-- ===========================

-- 实体表
DROP TABLE IF EXISTS `entities`;
CREATE TABLE `entities` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '实体ID',
  `name` varchar(255) NOT NULL COMMENT '实体名称',
  `entity_type` varchar(100) NOT NULL COMMENT '实体类型',
  `description` text COMMENT '实体描述',
  `properties` text COMMENT '实体属性(JSON格式)',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_name_type` (`name`, `entity_type`),
  KEY `idx_entity_type` (`entity_type`),
  KEY `idx_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实体表';

-- 关系表
DROP TABLE IF EXISTS `relations`;
CREATE TABLE `relations` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '关系ID',
  `head_entity_id` int(11) NOT NULL COMMENT '头实体ID',
  `tail_entity_id` int(11) NOT NULL COMMENT '尾实体ID',
  `relation_type` varchar(100) NOT NULL COMMENT '关系类型',
  `confidence` float(4,3) DEFAULT NULL COMMENT '置信度',
  `source_document_id` int(11) DEFAULT NULL COMMENT '来源文档ID',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_head_entity` (`head_entity_id`),
  KEY `idx_tail_entity` (`tail_entity_id`),
  KEY `idx_relation_type` (`relation_type`),
  KEY `idx_source_document` (`source_document_id`),
  KEY `idx_confidence` (`confidence`),
  CONSTRAINT `fk_relations_head_entity` FOREIGN KEY (`head_entity_id`) REFERENCES `entities` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_relations_tail_entity` FOREIGN KEY (`tail_entity_id`) REFERENCES `entities` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_relations_source_document` FOREIGN KEY (`source_document_id`) REFERENCES `documents` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='关系表';

-- ===========================
-- GraphRAG专用图谱表（MySQL简化实现）
-- ===========================

-- 图谱节点表（支持Section/Block/Entity/Claim等多种节点类型）
DROP TABLE IF EXISTS `graph_nodes`;
CREATE TABLE `graph_nodes` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '节点ID',
  `document_id` int(11) NOT NULL COMMENT '文档ID',
  `node_id` varchar(255) DEFAULT NULL COMMENT '节点唯一标识符（可选）',
  `node_type` varchar(100) NOT NULL COMMENT '节点类型(Section/Block/Entity/Claim)',
  `name` varchar(255) DEFAULT NULL COMMENT '节点名称',
  `section_id` varchar(100) DEFAULT NULL COMMENT '所属section ID',
  `elem_id` varchar(100) DEFAULT NULL COMMENT '元素ID',
  `entity_uid` varchar(255) DEFAULT NULL COMMENT '实体唯一标识符',
  `entity_type` varchar(100) DEFAULT NULL COMMENT '实体类型',
  `claim_id` varchar(255) DEFAULT NULL COMMENT 'Claim ID',
  `metric_type` varchar(100) DEFAULT NULL COMMENT '指标类型',
  `title` text COMMENT '标题内容',
  `properties` text COMMENT '节点属性(JSON格式)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_document_id` (`document_id`),
  KEY `idx_node_type` (`node_type`),
  KEY `idx_section_id` (`section_id`),
  KEY `idx_entity_type` (`entity_type`),
  KEY `idx_entity_uid` (`entity_uid`),
  KEY `idx_node_id` (`node_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='图谱节点表 - GraphRAG专用MySQL简化实现';

-- 图谱关系表（支持MENTIONS/HAS_ENTITY/MEASURES等多种关系类型）
DROP TABLE IF EXISTS `graph_relations`;
CREATE TABLE `graph_relations` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '关系ID',
  `document_id` int(11) NOT NULL COMMENT '文档ID',
  `source_id` varchar(255) NOT NULL COMMENT '源节点ID',
  `target_id` varchar(255) NOT NULL COMMENT '目标节点ID',
  `relation_type` varchar(100) NOT NULL COMMENT '关系类型(MENTIONS/HAS_ENTITY/MEASURES)',
  `confidence` float(4,3) DEFAULT NULL COMMENT '置信度',
  `properties` text COMMENT '关系属性(JSON格式)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_document_id` (`document_id`),
  KEY `idx_source_id` (`source_id`),
  KEY `idx_target_id` (`target_id`),
  KEY `idx_relation_type` (`relation_type`),
  KEY `idx_confidence` (`confidence`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='图谱关系表 - GraphRAG专用MySQL简化实现';

-- ===========================
-- 搜索和日志相关表
-- ===========================

-- 搜索历史表
DROP TABLE IF EXISTS `search_history`;
CREATE TABLE `search_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '搜索历史ID',
  `query` text NOT NULL COMMENT '搜索查询',
  `search_type` varchar(50) NOT NULL COMMENT '搜索类型',
  `results_count` int(11) DEFAULT 0 COMMENT '结果数量',
  `response_time` float(8,3) DEFAULT NULL COMMENT '响应时间(秒)',
  `user_id` varchar(100) DEFAULT NULL COMMENT '用户ID',
  `session_id` varchar(100) DEFAULT NULL COMMENT '会话ID',
  `ip_address` varchar(45) DEFAULT NULL COMMENT 'IP地址',
  `user_agent` text COMMENT '用户代理',
  `search_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '搜索时间',
  PRIMARY KEY (`id`),
  KEY `idx_search_type` (`search_type`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_search_time` (`search_time`),
  KEY `idx_session_id` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='搜索历史表';

-- 搜索反馈表
DROP TABLE IF EXISTS `search_feedback`;
CREATE TABLE `search_feedback` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '反馈ID',
  `search_history_id` int(11) DEFAULT NULL COMMENT '搜索历史ID',
  `rating` tinyint(1) DEFAULT NULL COMMENT '评分(1-5)',
  `feedback_text` text COMMENT '反馈内容',
  `helpful_results` text COMMENT '有用的结果(JSON格式)',
  `user_id` varchar(100) DEFAULT NULL COMMENT '用户ID',
  `feedback_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '反馈时间',
  PRIMARY KEY (`id`),
  KEY `idx_search_history` (`search_history_id`),
  KEY `idx_rating` (`rating`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_feedback_time` (`feedback_time`),
  CONSTRAINT `fk_feedback_search_history` FOREIGN KEY (`search_history_id`) REFERENCES `search_history` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='搜索反馈表';

-- ===========================
-- 系统配置和日志表
-- ===========================

-- 系统配置表
DROP TABLE IF EXISTS `system_config`;
CREATE TABLE `system_config` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '配置ID',
  `config_key` varchar(100) NOT NULL COMMENT '配置键',
  `config_value` text COMMENT '配置值',
  `config_type` varchar(50) DEFAULT 'string' COMMENT '配置类型',
  `description` varchar(255) DEFAULT NULL COMMENT '配置描述',
  `is_active` tinyint(1) DEFAULT 1 COMMENT '是否激活',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_config_key` (`config_key`),
  KEY `idx_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- 操作日志表
DROP TABLE IF EXISTS `operation_logs`;
CREATE TABLE `operation_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '日志ID',
  `operation_type` varchar(50) NOT NULL COMMENT '操作类型',
  `operation_target` varchar(100) DEFAULT NULL COMMENT '操作目标',
  `operation_detail` text COMMENT '操作详情',
  `user_id` varchar(100) DEFAULT NULL COMMENT '用户ID',
  `ip_address` varchar(45) DEFAULT NULL COMMENT 'IP地址',
  `user_agent` text COMMENT '用户代理',
  `status` varchar(20) DEFAULT 'success' COMMENT '操作状态',
  `error_message` text COMMENT '错误信息',
  `execution_time` float(8,3) DEFAULT NULL COMMENT '执行时间(秒)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_operation_type` (`operation_type`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';

-- ===========================
-- 插入初始数据
-- ===========================

-- 插入系统配置（包含GraphRAG优化后的配置）
INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`) VALUES
('system_version', '1.0.0', 'string', '系统版本'),
('max_file_size', '104857600', 'integer', '最大文件大小(字节)'),
('default_chunk_size', '2000', 'integer', '默认文本分块大小（优化后避免过度分割）'),
('default_chunk_overlap', '200', 'integer', '默认文本分块重叠'),
('vector_dimension', '768', 'integer', '向量维度（sentence-transformers模型）'),
('search_top_k', '10', 'integer', '默认搜索返回数量'),
('enable_ocr', '1', 'boolean', '是否启用OCR'),
('ocr_language', 'chi_sim+eng', 'string', 'OCR识别语言'),
('log_retention_days', '30', 'integer', '日志保留天数'),
('graphrag_version', '2.1.0', 'string', 'GraphRAG系统版本'),
('enable_element_id', '1', 'boolean', '是否启用一家子element_id功能'),
('enable_structured_data', '1', 'boolean', '是否启用table/img/chars结构化数据存储'),
('enable_pdf_mysql_storage', '1', 'boolean', '是否启用PDF结构化数据MySQL存储'),
('pdf_bbox_normalization', '1', 'boolean', '是否启用PDF边界框坐标规范化'),
('pdf_table_column_inference', '1', 'boolean', '是否启用PDF表格列数自动推断'),
('pdf_row_text_formatting', '1', 'boolean', '是否启用PDF表格行文本格式化');

-- ===========================
-- 创建索引（优化查询性能）
-- ===========================

-- 复合索引
CREATE INDEX `idx_doc_status_type` ON `documents` (`process_status`, `file_type`);

-- document_chunks表的复合索引（优化GraphRAG查询）
CREATE INDEX `idx_chunk_doc_vector` ON `document_chunks` (`document_id`, `vector_id`);
CREATE INDEX `idx_chunk_element_doc` ON `document_chunks` (`element_id`, `document_id`) COMMENT '按一家子ID和文档ID查询优化';
CREATE INDEX `idx_chunk_doc_element_index` ON `document_chunks` (`document_id`, `element_id`, `chunk_index`) COMMENT '完整内容检索优化';
CREATE INDEX `idx_chunk_hash_doc` ON `document_chunks` (`content_hash`, `document_id`) COMMENT '内容去重查询优化';

-- PDF结构化数据表的复合索引（优化查询性能）
CREATE INDEX `idx_sections_doc_page` ON `sections` (`doc_id`, `page_start`, `page_end`) COMMENT 'sections按文档和页码范围查询优化';
CREATE INDEX `idx_figures_section_page` ON `figures` (`section_id`, `page`) COMMENT 'figures按section和页码查询优化';
CREATE INDEX `idx_tables_section_size` ON `tables` (`section_id`, `n_rows`, `n_cols`) COMMENT 'tables按section和表格尺寸查询优化';
CREATE INDEX `idx_table_rows_elem_index` ON `table_rows` (`table_elem_id`, `row_index`) COMMENT 'table_rows按表格和行索引查询优化';

-- 其他表的复合索引
CREATE INDEX `idx_entity_name_type` ON `entities` (`name`, `entity_type`);
CREATE INDEX `idx_relation_head_tail` ON `relations` (`head_entity_id`, `tail_entity_id`);
CREATE INDEX `idx_search_type_time` ON `search_history` (`search_type`, `search_time`);

-- ===========================
-- 创建视图（便于查询）
-- ===========================

-- 文档统计视图
CREATE OR REPLACE VIEW `v_document_stats` AS
SELECT 
    d.file_type,
    COUNT(*) as total_count,
    SUM(d.file_size) as total_size,
    AVG(d.file_size) as avg_size,
    COUNT(CASE WHEN d.process_status = 'completed' THEN 1 END) as completed_count,
    COUNT(CASE WHEN d.process_status = 'pending' THEN 1 END) as pending_count,
    COUNT(CASE WHEN d.process_status LIKE '%failed%' THEN 1 END) as failed_count
FROM documents d
GROUP BY d.file_type;

-- 实体关系统计视图
CREATE OR REPLACE VIEW `v_entity_relation_stats` AS
SELECT 
    e.entity_type,
    COUNT(DISTINCT e.id) as entity_count,
    COUNT(DISTINCT r1.id) as out_relation_count,
    COUNT(DISTINCT r2.id) as in_relation_count
FROM entities e
LEFT JOIN relations r1 ON e.id = r1.head_entity_id
LEFT JOIN relations r2 ON e.id = r2.tail_entity_id
GROUP BY e.entity_type;

-- 搜索统计视图
CREATE OR REPLACE VIEW `v_search_stats` AS
SELECT 
    DATE(search_time) as search_date,
    search_type,
    COUNT(*) as search_count,
    AVG(response_time) as avg_response_time,
    AVG(results_count) as avg_results_count
FROM search_history
WHERE search_time >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
GROUP BY DATE(search_time), search_type;

-- PDF结构化数据统计视图
CREATE OR REPLACE VIEW `v_pdf_structure_stats` AS
SELECT 
    d.id as doc_id,
    d.filename,
    COUNT(DISTINCT s.section_id) as sections_count,
    COUNT(DISTINCT f.elem_id) as figures_count,
    COUNT(DISTINCT t.elem_id) as tables_count,
    COUNT(DISTINCT tr.id) as table_rows_count,
    SUM(t.n_rows) as total_table_rows,
    AVG(t.n_cols) as avg_table_cols
FROM documents d
LEFT JOIN sections s ON d.id = s.doc_id
LEFT JOIN figures f ON s.section_id = f.section_id
LEFT JOIN tables t ON s.section_id = t.section_id
LEFT JOIN table_rows tr ON t.elem_id = tr.table_elem_id
WHERE d.file_type = 'pdf'
GROUP BY d.id, d.filename;

-- ===========================
-- 创建存储过程（数据维护）
-- ===========================

DELIMITER //

-- 清理过期日志存储过程
CREATE PROCEDURE `sp_cleanup_expired_logs`(IN retention_days INT)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;
    
    -- 清理过期搜索历史
    DELETE FROM search_history 
    WHERE search_time < DATE_SUB(NOW(), INTERVAL retention_days DAY);
    
    -- 清理过期操作日志
    DELETE FROM operation_logs 
    WHERE created_at < DATE_SUB(NOW(), INTERVAL retention_days DAY);
    
    COMMIT;
END //

-- 文档处理状态统计存储过程
CREATE PROCEDURE `sp_get_document_process_stats`()
BEGIN
    SELECT 
        process_status,
        COUNT(*) as count,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM documents), 2) as percentage
    FROM documents
    GROUP BY process_status
    ORDER BY count DESC;
END //

-- 获取热门搜索查询存储过程
CREATE PROCEDURE `sp_get_popular_queries`(IN days INT, IN limit_count INT)
BEGIN
    SELECT 
        query,
        COUNT(*) as search_count,
        AVG(response_time) as avg_response_time,
        AVG(results_count) as avg_results_count
    FROM search_history
    WHERE search_time >= DATE_SUB(NOW(), INTERVAL days DAY)
    GROUP BY query
    ORDER BY search_count DESC
    LIMIT limit_count;
END //

DELIMITER ;

-- ===========================
-- 创建触发器（数据完整性）
-- ===========================

DELIMITER //

-- 文档删除触发器（级联清理）
CREATE TRIGGER `tr_document_delete_cleanup`
AFTER DELETE ON `documents`
FOR EACH ROW
BEGIN
    -- 记录删除操作
    INSERT INTO operation_logs (operation_type, operation_target, operation_detail, status)
    VALUES ('document_delete', CONCAT('document_id:', OLD.id), 
            CONCAT('filename:', OLD.filename, ', file_size:', OLD.file_size), 'success');
END //

-- 搜索历史插入触发器（数据验证）
CREATE TRIGGER `tr_search_history_insert`
BEFORE INSERT ON `search_history`
FOR EACH ROW
BEGIN
    -- 验证搜索类型
    IF NEW.search_type NOT IN ('vector', 'graph', 'hybrid', 'semantic', 'qa') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid search_type';
    END IF;
    
    -- 设置默认值
    IF NEW.results_count IS NULL THEN
        SET NEW.results_count = 0;
    END IF;
END //

DELIMITER ;

-- ===========================
-- 权限设置（生产环境建议）
-- ===========================

-- 创建应用用户（生产环境建议使用专门的应用用户）
-- CREATE USER 'graphrag_app'@'%' IDENTIFIED BY 'your_secure_password';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON graph_rag.* TO 'graphrag_app'@'%';
-- FLUSH PRIVILEGES;

-- ===========================
-- 数据库初始化完成
-- ===========================

-- 显示表创建结果
SHOW TABLES;

-- 显示数据库大小
SELECT 
    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Database Size (MB)'
FROM information_schema.tables 
WHERE table_schema = 'graph_rag';

-- 输出初始化完成信息
SELECT 'GraphRAG数据库v2.1初始化完成！包含PDF结构化数据存储功能' AS status;

-- 显示document_chunks表的详细结构（验证更新）
SELECT 'document_chunks表结构验证:' AS info;
DESCRIBE document_chunks;

-- 显示系统配置（验证GraphRAG配置）
SELECT 'GraphRAG系统配置:' AS info;
SELECT config_key, config_value, description 
FROM system_config 
WHERE config_key IN ('graphrag_version', 'enable_element_id', 'enable_structured_data', 'enable_pdf_mysql_storage', 'default_chunk_size', 'vector_dimension');

-- 验证PDF结构化数据表
SELECT 'PDF结构化数据表验证:' AS info;
SELECT TABLE_NAME, TABLE_COMMENT, TABLE_ROWS 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'graph_rag' 
AND TABLE_NAME IN ('sections', 'figures', 'tables', 'table_rows')
ORDER BY TABLE_NAME;

-- 显示PDF结构化数据表的索引
SELECT 'PDF表索引验证:' AS info;
SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX
FROM information_schema.STATISTICS 
WHERE TABLE_SCHEMA = 'graph_rag' 
AND TABLE_NAME IN ('sections', 'figures', 'tables', 'table_rows')
AND INDEX_NAME NOT IN ('PRIMARY')
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;