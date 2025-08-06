-- GraphRAG数据库初始化脚本
-- 创建GraphRAG系统所需的所有数据库表
-- 数据库连接信息：192.168.16.26:3306, root, !200808Xx

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
DROP TABLE IF EXISTS `document_chunks`;
CREATE TABLE `document_chunks` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '分块ID',
  `document_id` int(11) NOT NULL COMMENT '文档ID',
  `chunk_index` int(11) NOT NULL COMMENT '分块索引',
  `content` text NOT NULL COMMENT '分块内容',
  `content_hash` varchar(64) DEFAULT NULL COMMENT '内容哈希',
  `vector_id` varchar(100) DEFAULT NULL COMMENT '向量ID',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_doc_chunk` (`document_id`, `chunk_index`),
  KEY `idx_document_id` (`document_id`),
  KEY `idx_vector_id` (`vector_id`),
  KEY `idx_content_hash` (`content_hash`),
  CONSTRAINT `fk_chunks_document` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档分块表';

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

-- 插入系统配置
INSERT INTO `system_config` (`config_key`, `config_value`, `config_type`, `description`) VALUES
('system_version', '1.0.0', 'string', '系统版本'),
('max_file_size', '104857600', 'integer', '最大文件大小(字节)'),
('default_chunk_size', '1000', 'integer', '默认文本分块大小'),
('default_chunk_overlap', '200', 'integer', '默认文本分块重叠'),
('vector_dimension', '768', 'integer', '向量维度'),
('search_top_k', '10', 'integer', '默认搜索返回数量'),
('enable_ocr', '1', 'boolean', '是否启用OCR'),
('ocr_language', 'chi_sim+eng', 'string', 'OCR识别语言'),
('log_retention_days', '30', 'integer', '日志保留天数');

-- ===========================
-- 创建索引（优化查询性能）
-- ===========================

-- 复合索引
CREATE INDEX `idx_doc_status_type` ON `documents` (`process_status`, `file_type`);
CREATE INDEX `idx_chunk_doc_vector` ON `document_chunks` (`document_id`, `vector_id`);
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
SELECT 'GraphRAG数据库初始化完成！' AS status;