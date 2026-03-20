-- ============================================================
-- 京东手机评论分析系统 — 初始数据（测试账号 + 品牌信息）
-- 评论数据通过 import_data.py 脚本从 CSV/Excel 导入
-- ============================================================

USE jd_comment_analysis;

-- ---------- 管理员账号 ----------
-- 密码: admin123  (使用 werkzeug generate_password_hash 生成)
INSERT INTO users (username, password_hash, nickname, role) VALUES
('admin', 'scrypt:32768:8:1$placeholder$admin123hash', '管理员', 'admin');

-- ---------- 测试用户 ----------
-- 密码: user123
INSERT INTO users (username, password_hash, nickname, role) VALUES
('user', 'scrypt:32768:8:1$placeholder$user123hash', '测试用户', 'user');

-- 注意：上述密码哈希为占位值，实际运行 import_data.py 会正确生成哈希

-- ---------- 品牌初始数据 ----------
INSERT INTO brands (name, full_name, description) VALUES
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
