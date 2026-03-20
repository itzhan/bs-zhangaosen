-- ============================================================
-- 京东手机评论分析系统 — 建表语句
-- 数据库: jd_comment_analysis  字符集: utf8mb4
-- ============================================================

CREATE DATABASE IF NOT EXISTS jd_comment_analysis
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE jd_comment_analysis;

-- ---------- 用户表 ----------
DROP TABLE IF EXISTS user_favorites;
DROP TABLE IF EXISTS crawler_tasks;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS brands;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nickname    VARCHAR(100) DEFAULT '',
    role        ENUM('user','admin') DEFAULT 'user',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 品牌表 ----------
CREATE TABLE brands (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    full_name   VARCHAR(200) DEFAULT '',
    jd_url      VARCHAR(500) DEFAULT '',
    image_url   VARCHAR(500) DEFAULT '',
    description TEXT,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 评论表 ----------
CREATE TABLE comments (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    brand_id        INT NOT NULL,
    comment_id      VARCHAR(50) DEFAULT '',
    comment_time    DATETIME,
    content         TEXT,
    cleaned_content TEXT,
    score           INT DEFAULT 5,
    user_nickname   VARCHAR(100) DEFAULT '',
    color           TEXT,
    model           TEXT,
    sentiment_score FLOAT DEFAULT 0.5,
    sentiment_label ENUM('正向','中性','负向') DEFAULT '中性',
    keywords        JSON,
    create_time     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    INDEX idx_brand (brand_id),
    INDEX idx_comment_id (comment_id),
    INDEX idx_sentiment (sentiment_label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 爬虫任务表 ----------
CREATE TABLE crawler_tasks (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    brand_id    INT,
    jd_url      VARCHAR(500) NOT NULL,
    status      ENUM('pending','running','completed','failed') DEFAULT 'pending',
    total_count INT DEFAULT 0,
    error_msg   TEXT,
    start_time  DATETIME,
    end_time    DATETIME,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (brand_id) REFERENCES brands(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- 用户收藏表 ----------
CREATE TABLE user_favorites (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    brand_id    INT NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    UNIQUE KEY uq_user_brand (user_id, brand_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
