"""数据导入脚本 — 将现有 CSV/Excel 评论数据导入 MySQL"""

import ast
import sys
import os
from pathlib import Path
from datetime import datetime

import pandas as pd

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.brand import Brand
from app.models.comment import Comment


# 品牌映射：文件名前缀 -> (品牌短名, 全称)
BRAND_MAP = {
    'iphone17': ('iPhone17', 'Apple iPhone 17'),
    'oppoReno': ('OPPO Reno', 'OPPO Reno 系列'),
    'vivoX300': ('vivo X300', 'vivo X300 系列'),
    '一加ACE6': ('一加 ACE6', 'OnePlus ACE 6'),
    '华为Pura70': ('华为 Pura70', 'HUAWEI Pura 70'),
    '小米17pro': ('小米 17Pro', 'Xiaomi 17 Pro'),
}


def parse_keywords(cell):
    """解析关键词：可能是字符串化的列表或空值"""
    if pd.isna(cell):
        return []
    if isinstance(cell, list):
        return cell
    text = str(cell).strip()
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    return [w.strip() for w in text.replace('[', '').replace(']', '').replace("'", '').split(',') if w.strip()]


def import_data():
    app = create_app()
    with app.app_context():
        # 创建表
        db.create_all()

        # 创建管理员（如果不存在）
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', nickname='管理员', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            print('[+] 创建管理员账号: admin / admin123')

        # 创建普通用户
        user = User.query.filter_by(username='user').first()
        if not user:
            user = User(username='user', nickname='测试用户', role='user')
            user.set_password('user123')
            db.session.add(user)
            print('[+] 创建测试用户: user / user123')

        db.session.commit()

        # 读取情感分析结果目录
        data_dir = Path('output/sentiment_batch')
        if not data_dir.exists():
            print('[!] output/sentiment_batch 目录不存在，尝试直接读取评论目录...')
            data_dir = Path('评论')

        if not data_dir.exists():
            print('[!] 未找到数据目录，跳过数据导入')
            return

        files = sorted([f for f in data_dir.iterdir()
                        if f.is_file() and f.suffix.lower() in {'.csv', '.xlsx', '.xls'}
                        and 'summary' not in f.name.lower()])

        total_imported = 0
        for filepath in files:
            # 匹配品牌
            stem = filepath.stem.replace('输出', '')
            brand_info = BRAND_MAP.get(stem, (stem, stem))
            brand_name, full_name = brand_info

            # 创建或获取品牌
            brand = Brand.query.filter_by(name=brand_name).first()
            if not brand:
                brand = Brand(name=brand_name, full_name=full_name)
                db.session.add(brand)
                db.session.flush()
                print(f'[+] 创建品牌: {brand_name}')

            # 如果品牌已有评论则跳过
            existing = Comment.query.filter_by(brand_id=brand.id).count()
            if existing > 0:
                print(f'[=] {brand_name} 已有 {existing} 条评论，跳过')
                continue

            # 读取数据
            try:
                if filepath.suffix.lower() == '.csv':
                    df = pd.read_csv(filepath, encoding='utf-8-sig')
                else:
                    df = pd.read_excel(filepath)
            except Exception as e:
                print(f'[!] 读取 {filepath.name} 失败: {e}')
                continue

            count = 0
            for _, row in df.iterrows():
                # 解析时间
                ct = None
                if '评论时间' in df.columns and pd.notna(row.get('评论时间')):
                    try:
                        ct = pd.to_datetime(row['评论时间'])
                    except Exception:
                        pass

                # 关键词
                kws = parse_keywords(row.get('关键词', ''))

                # 颜色/型号（过滤掉误入的图片URL）
                color = str(row.get('商品_颜色', '') or row.get('商品颜色', '') or '').strip()
                model = str(row.get('商品_型号', '') or row.get('商品型号', '') or '').strip()
                if color.startswith('http') or len(color) > 100:
                    color = ''
                if model.startswith('http') or len(model) > 100:
                    model = ''

                comment = Comment(
                    brand_id=brand.id,
                    comment_id=str(row.get('评论ID', '')),
                    comment_time=ct,
                    content=str(row.get('评论内容', '')),
                    cleaned_content=str(row.get('清洗后评论', '')),
                    score=int(row.get('评论得分', 5)) if pd.notna(row.get('评论得分')) else 5,
                    user_nickname=str(row.get('用户昵称', '')),
                    color=color,
                    model=model,
                    sentiment_score=float(row.get('情感得分', 0.5)) if pd.notna(row.get('情感得分')) else 0.5,
                    sentiment_label=str(row.get('情感标签', '中性')),
                    keywords=kws,
                )
                db.session.add(comment)
                count += 1

            db.session.commit()
            total_imported += count
            print(f'[+] {brand_name}: 导入 {count} 条评论')

        print(f'\n=== 导入完成，共 {total_imported} 条评论 ===')


if __name__ == '__main__':
    import_data()
