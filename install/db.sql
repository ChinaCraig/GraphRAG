-- GraphRAG数据库初始化脚本 v2.4 (进一步清理版)
-- 创建GraphRAG系统实际使用的数据库表
-- 基于深度代码分析，移除了所有未使用的表以优化数据库结构
--
-- 更新日志：
-- v2.4: 进一步清理未使用的系统配置表
--   - 删除未使用的system_config表：经分析该表完全未被项目代码使用
--   - 系统配置改为使用YAML文件管理，更适合当前项目规模
--   - 数据库利用率达到100%，只保留实际使用的核心表
-- v2.3: 数据库结构清理优化
--   - 删除未使用的表：document_chunks, entities, relations, graph_nodes, graph_relations, search_history, search_feedback
--   - 保留实际使用的表：documents, sections, figures, tables, table_rows, operation_logs
--   - 移除相关的未使用视图、索引、存储过程和触发器
-- v2.2: 新增GraphRAG专用图谱表和问题修复（已移除未使用部分）
-- v2.1: 新增PDF结构化数据MySQL存储功能
--   - 新增sections表：存储PDF章节信息（一节一行）
--   - 新增figures表：存储PDF图片信息（一图一行，遍历blocks.type='figure'）
--   - 新增tables表：存储PDF表格信息（一表一行，遍历blocks.type='table'）
--   - 新增table_rows表：存储PDF表格行数据（一行一行）

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `graph_rag` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE `graph_rag`;

-- 设置字符集
SET NAMES utf8mb4;

-- ===========================
-- 核心数据表（实际使用）
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

-- ===========================
-- PDF结构化数据表
-- ===========================

-- sections表（一节一行）
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
-- 系统日志表
-- ===========================

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
-- 注意事项
-- ===========================
-- 
-- 系统配置说明：
-- 本系统的配置管理采用YAML文件方式，配置文件位于config/目录下：
-- - config/config.yaml: 主应用配置（文件大小、路径等）
-- - config/db.yaml: 数据库连接配置
-- - config/model.yaml: 模型和算法配置
-- - config/prompt.yaml: 提示词配置
-- 
-- 这种方式更适合当前项目规模，便于开发调试和版本控制。
--

-- ===========================
-- 创建索引（优化查询性能）
-- ===========================

-- 文档表复合索引
CREATE INDEX `idx_doc_status_type` ON `documents` (`process_status`, `file_type`);

-- PDF结构化数据表的复合索引
CREATE INDEX `idx_sections_doc_page` ON `sections` (`doc_id`, `page_start`, `page_end`) COMMENT 'sections按文档和页码范围查询优化';
CREATE INDEX `idx_figures_section_page` ON `figures` (`section_id`, `page`) COMMENT 'figures按section和页码查询优化';
CREATE INDEX `idx_tables_section_size` ON `tables` (`section_id`, `n_rows`, `n_cols`) COMMENT 'tables按section和表格尺寸查询优化';
CREATE INDEX `idx_table_rows_elem_index` ON `table_rows` (`table_elem_id`, `row_index`) COMMENT 'table_rows按表格和行索引查询优化';

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

-- 获取PDF结构化数据统计存储过程
CREATE PROCEDURE `sp_get_pdf_structure_stats`(IN document_id INT)
BEGIN
    SELECT 
        d.id,
        d.filename,
        COUNT(DISTINCT s.section_id) as sections_count,
        COUNT(DISTINCT f.elem_id) as figures_count,
        COUNT(DISTINCT t.elem_id) as tables_count,
        COUNT(DISTINCT tr.id) as table_rows_count
    FROM documents d
    LEFT JOIN sections s ON d.id = s.doc_id
    LEFT JOIN figures f ON s.section_id = f.section_id
    LEFT JOIN tables t ON s.section_id = t.section_id
    LEFT JOIN table_rows tr ON t.elem_id = tr.table_elem_id
    WHERE d.id = document_id OR document_id IS NULL
    GROUP BY d.id, d.filename
    ORDER BY d.id;
END //

DELIMITER ;

-- ===========================
-- 创建触发器（数据完整性）
-- ===========================

DELIMITER //

-- 文档删除触发器（级联清理和日志记录）
CREATE TRIGGER `tr_document_delete_cleanup`
AFTER DELETE ON `documents`
FOR EACH ROW
BEGIN
    -- 记录删除操作
    INSERT INTO operation_logs (operation_type, operation_target, operation_detail, status)
    VALUES ('document_delete', CONCAT('document_id:', OLD.id), 
            CONCAT('filename:', OLD.filename, ', file_size:', OLD.file_size), 'success');
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
SELECT 'GraphRAG数据库v2.4（深度清理版）初始化完成！只保留实际使用的核心表' AS status;

-- 显示当前保留的表
SELECT '保留的数据表:' AS info;
SELECT TABLE_NAME, TABLE_COMMENT, TABLE_ROWS 
FROM information_schema.TABLES 
WHERE TABLE_SCHEMA = 'graph_rag' 
AND TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;

-- 显示配置说明
SELECT '配置文件位置:' AS info;
SELECT 'config/config.yaml - 主应用配置' AS config_file
UNION ALL
SELECT 'config/db.yaml - 数据库配置' AS config_file
UNION ALL
SELECT 'config/model.yaml - 模型配置' AS config_file
UNION ALL
SELECT 'config/prompt.yaml - 提示词配置' AS config_file;

-- 显示索引状态
SELECT '索引状态验证:' AS info;
SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX
FROM information_schema.STATISTICS 
WHERE TABLE_SCHEMA = 'graph_rag' 
AND INDEX_NAME NOT IN ('PRIMARY')
ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;
