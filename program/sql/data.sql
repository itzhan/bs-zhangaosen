-- ============================================================
-- 京东手机评论分析系统 — 初始数据（测试账号 + 品牌信息）
-- 评论数据通过 import_data.py 脚本从 CSV/Excel 导入
-- ============================================================

SET NAMES utf8mb4;
USE jd_comment_analysis;

-- ---------- 管理员账号 ----------
-- 密码: admin123  (使用 werkzeug generate_password_hash 生成)
INSERT IGNORE INTO users (username, password_hash, nickname, role) VALUES
('admin', 'scrypt:32768:8:1$mNt0rD6VtemIVHRG$06048cbe10dc902525b805b13a7743d4c9ae54f77026a61931a17506e80ffad57af1bc74b68e6d530e7d30594e1df4a545ef16e70241e3b1ecd53c93f665856f', '管理员', 'admin');

-- ---------- 测试用户 ----------
-- 密码: user123
INSERT IGNORE INTO users (username, password_hash, nickname, role) VALUES
('user', 'scrypt:32768:8:1$0RHoTw7WvtXWimFb$fb72136a77219b401c58ac72f792d2ff897c5d7d5a8fb860ab3bfe514c5a0036da4dcba9ae1bc0d35acac6c8e363cc5754779bf2867bf5a29fa9fd9f83fbc94b', '测试用户', 'user');


-- ---------- 品牌初始数据 ----------
INSERT IGNORE INTO brands (name, full_name, description) VALUES
('iPhone17', 'Apple iPhone 17', 'Apple 最新旗舰手机，搭载 A19 芯片，支持 Apple Intelligence'),
('OPPO Reno', 'OPPO Reno 系列', 'OPPO 中端旗舰，主打拍照和轻薄设计'),
('vivo X300', 'vivo X300 系列', 'vivo 影像旗舰，蔡司光学镜头系统'),
('一加 ACE6', 'OnePlus ACE 6', '一加性能手机，主打高性能游戏体验'),
('华为 Pura70', 'HUAWEI Pura 70', '华为影像旗舰，超聚光摄像系统'),
('小米 17Pro', 'Xiaomi 17 Pro', '小米旗舰手机，徕卡光学镜头');

-- ---------- 评论数据 ----------
-- 评论数据量大（7000+ 条），通过 Python 脚本导入：
--   cd program
--   source venv/bin/activate  
--   python import_data.py
-- 
-- 该脚本会自动从 output/sentiment_batch/ 目录读取 CSV 文件
-- 并导入到 comments 表（含情感分析结果和关键词）
