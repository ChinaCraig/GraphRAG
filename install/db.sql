-- GraphRAG系统数据库初始化脚本
-- 数据库名称: graph_rag
-- 字符集: utf8mb4

-- 创建数据库
CREATE DATABASE IF NOT EXISTS graph_rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE graph_rag;

-- 文件信息表
CREATE TABLE IF NOT EXISTS file_info (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL COMMENT '文件名',
    file_path VARCHAR(500) NOT NULL COMMENT '文件路径',
    file_type VARCHAR(50) NOT NULL COMMENT '文件类型',
    file_size BIGINT NOT NULL COMMENT '文件大小(字节)',
    upload_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    process_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '处理状态',
    json_path VARCHAR(500) COMMENT 'JSON文件路径',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_file_name (file_name),
    INDEX idx_file_type (file_type),
    INDEX idx_process_status (process_status),
    INDEX idx_upload_time (upload_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文件信息表';

-- 向量数据表
CREATE TABLE IF NOT EXISTS vector_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_id BIGINT NOT NULL COMMENT '关联的文件ID',
    content_type VARCHAR(50) NOT NULL COMMENT '内容类型(text, table, image等)',
    content TEXT NOT NULL COMMENT '原始内容',
    vector_id VARCHAR(100) NOT NULL COMMENT '向量数据库中的ID',
    embedding_model VARCHAR(100) NOT NULL COMMENT '嵌入模型名称',
    position_info JSON COMMENT '位置信息',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (file_id) REFERENCES file_info(id) ON DELETE CASCADE,
    INDEX idx_file_id (file_id),
    INDEX idx_content_type (content_type),
    INDEX idx_vector_id (vector_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='向量数据表';

-- 图数据表
CREATE TABLE IF NOT EXISTS graph_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_id BIGINT NOT NULL COMMENT '关联的文件ID',
    entity_type VARCHAR(100) NOT NULL COMMENT '实体类型',
    entity_name VARCHAR(255) NOT NULL COMMENT '实体名称',
    entity_properties JSON COMMENT '实体属性',
    relationship_type VARCHAR(100) COMMENT '关系类型',
    target_entity VARCHAR(255) COMMENT '目标实体',
    relationship_properties JSON COMMENT '关系属性',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (file_id) REFERENCES file_info(id) ON DELETE CASCADE,
    INDEX idx_file_id (file_id),
    INDEX idx_entity_type (entity_type),
    INDEX idx_entity_name (entity_name),
    INDEX idx_relationship_type (relationship_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='图数据表';

-- 搜索历史表
CREATE TABLE IF NOT EXISTS search_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    query_text TEXT NOT NULL COMMENT '查询文本',
    query_type VARCHAR(50) NOT NULL COMMENT '查询类型',
    result_count INT NOT NULL DEFAULT 0 COMMENT '结果数量',
    search_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '搜索时间',
    user_ip VARCHAR(45) COMMENT '用户IP',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_query_type (query_type),
    INDEX idx_search_time (search_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='搜索历史表'; 