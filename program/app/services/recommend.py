"""推荐服务 — 协同过滤(ALS) + 情感加权混合推荐

实现三种推荐策略:
1. 基于情感得分的规则推荐（兜底）
2. ALS 协同过滤推荐（Spark MLlib）
3. 混合推荐（协同过滤 + 情感加权）
"""

from __future__ import annotations

import os
import traceback
from typing import List, Optional

from sqlalchemy import func, case
from app import db
from app.models.comment import Comment
from app.models.brand import Brand
from app.models.favorite import UserFavorite


# =========================================================
# 1. 基于情感得分的规则推荐（原有逻辑，保留为兜底方案）
# =========================================================
def recommend_brands(limit=6):
    """基于情感得分的品牌推荐（规则方法）"""
    brand_scores = db.session.query(
        Brand.id,
        Brand.name,
        Brand.image_url,
        func.count(Comment.id).label('comment_count'),
        func.avg(Comment.sentiment_score).label('avg_score'),
        func.sum(case((Comment.sentiment_label == '正向', 1), else_=0)).label('pos_count'),
    ).outerjoin(Comment, Comment.brand_id == Brand.id) \
        .group_by(Brand.id).all()

    results = []
    for b in brand_scores:
        if b.comment_count == 0:
            continue
        pos_rate = float(b.pos_count) / float(b.comment_count)
        # 综合得分 = 正向率 × 0.4 + 平均情感分 × 0.4 + 评论量权重 × 0.2
        volume_weight = min(float(b.comment_count) / 500.0, 1.0)
        composite = pos_rate * 0.4 + float(b.avg_score or 0) * 0.4 + volume_weight * 0.2
        results.append({
            'id': b.id,
            'name': b.name,
            'image_url': b.image_url,
            'comment_count': int(b.comment_count),
            'avg_score': round(float(b.avg_score or 0), 4),
            'pos_rate': round(float(pos_rate * 100), 1),
            'composite_score': round(float(composite), 4),
            'method': 'rule',  # 标记推荐方法
        })

    results.sort(key=lambda x: x['composite_score'], reverse=True)
    return results[:limit]


# =========================================================
# 2. ALS 协同过滤推荐（Spark MLlib）
# =========================================================
def _build_user_brand_ratings():
    """构建用户-品牌评分矩阵

    评分来源:
    - 用户收藏 → 隐式评分 5.0
    - 评论评分 → 显式评分 (1-5)
    - 情感得分 → 加权评分 (sentiment_score * 5)
    """
    ratings = []

    # 从收藏表获取隐式反馈
    favorites = db.session.query(
        UserFavorite.user_id,
        UserFavorite.brand_id,
    ).all()
    for fav in favorites:
        ratings.append((int(fav.user_id), int(fav.brand_id), 5.0))

    # 从评论表获取评分（按用户昵称聚合为虚拟用户）
    user_comments = db.session.query(
        Comment.user_nickname,
        Comment.brand_id,
        func.avg(Comment.score).label('avg_rating'),
        func.avg(Comment.sentiment_score).label('avg_sentiment'),
    ).filter(
        Comment.user_nickname != '',
        Comment.user_nickname.isnot(None),
    ).group_by(Comment.user_nickname, Comment.brand_id).all()

    # 虚拟用户 ID 映射 (从 1000 开始，避免与真实用户冲突)
    nickname_map = {}
    uid_counter = 1000
    for uc in user_comments:
        if uc.user_nickname not in nickname_map:
            nickname_map[uc.user_nickname] = uid_counter
            uid_counter += 1
        uid = nickname_map[uc.user_nickname]
        # 综合评分 = 评论评分 * 0.6 + 情感评分 * 5 * 0.4
        combined = float(uc.avg_rating or 3) * 0.6 + float(uc.avg_sentiment or 0.5) * 5 * 0.4
        ratings.append((uid, int(uc.brand_id), round(combined, 2)))

    return ratings


def als_recommend(user_id: int, limit: int = 6) -> Optional[List[dict]]:
    """ALS 协同过滤推荐

    Args:
        user_id: 用户 ID
        limit: 推荐数量

    Returns:
        推荐结果列表，失败则返回 None
    """
    try:
        from pyspark.sql import SparkSession, Row
        from pyspark.ml.recommendation import ALS
        from pyspark.sql.types import StructType, StructField, IntegerType, FloatType

        # 构建评分数据
        ratings_data = _build_user_brand_ratings()
        if len(ratings_data) < 5:
            return None  # 数据不足

        # 创建 Spark Session
        spark = (
            SparkSession.builder
            .appName("ALS-Recommend")
            .master("local[*]")
            .config("spark.driver.memory", "1g")
            .config("spark.ui.showConsoleProgress", "false")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("ERROR")

        schema = StructType([
            StructField("user_id", IntegerType(), False),
            StructField("brand_id", IntegerType(), False),
            StructField("rating", FloatType(), False),
        ])

        rows = [Row(user_id=int(r[0]), brand_id=int(r[1]), rating=float(r[2]))
                for r in ratings_data]
        ratings_df = spark.createDataFrame(rows, schema)

        # 训练 ALS 模型
        als = ALS(
            maxIter=10,
            regParam=0.1,
            rank=10,
            userCol="user_id",
            itemCol="brand_id",
            ratingCol="rating",
            coldStartStrategy="drop",
        )
        model = als.fit(ratings_df)

        # 为目标用户生成推荐
        user_df = spark.createDataFrame([(user_id,)], ["user_id"])
        recommendations = model.recommendForUserSubset(user_df, limit)

        results = []
        if recommendations.count() > 0:
            recs = recommendations.collect()[0]["recommendations"]
            for rec in recs:
                brand = Brand.query.get(rec["brand_id"])
                if brand:
                    results.append({
                        'id': brand.id,
                        'name': brand.name,
                        'image_url': brand.image_url,
                        'predicted_rating': round(float(rec["rating"]), 4),
                        'method': 'als',
                    })

        spark.stop()
        return results if results else None

    except Exception as e:
        print(f"[推荐] ALS 推荐失败: {e}")
        traceback.print_exc()
        return None


# =========================================================
# 3. 混合推荐（协同过滤 + 情感加权）
# =========================================================
def hybrid_recommend(user_id: int = None, limit: int = 6) -> list:
    """混合推荐：尝试 ALS 协同过滤 → 回退到规则推荐

    将 ALS 预测评分与品牌情感得分加权融合。
    """
    # 尝试 ALS 推荐
    als_results = None
    if user_id:
        als_results = als_recommend(user_id, limit=limit * 2)

    if als_results:
        # 用品牌情感数据增强 ALS 结果
        for item in als_results:
            brand_id = item['id']
            stats = db.session.query(
                func.avg(Comment.sentiment_score).label('avg_sentiment'),
                func.count(Comment.id).label('count'),
            ).filter(Comment.brand_id == brand_id).first()

            avg_sent = float(stats.avg_sentiment or 0.5) if stats else 0.5
            count = int(stats.count or 0) if stats else 0

            # 混合得分 = ALS预测 * 0.6 + 情感得分*5 * 0.3 + 评论量权重 * 0.1
            als_score = item['predicted_rating']
            volume_w = min(count / 500.0, 1.0)
            item['hybrid_score'] = round(
                als_score * 0.6 + avg_sent * 5 * 0.3 + volume_w * 0.1, 4
            )
            item['avg_sentiment'] = round(avg_sent, 4)
            item['comment_count'] = count
            item['method'] = 'hybrid'

        als_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        return als_results[:limit]

    # 回退到规则推荐
    return recommend_brands(limit)


def recommend_by_keyword(keyword, limit=5):
    """基于关键词匹配的品牌推荐"""
    from collections import Counter

    brands = Brand.query.all()
    scores = []

    for brand in brands:
        comments = Comment.query.filter_by(brand_id=brand.id).all()
        match_count = 0
        total = len(comments)
        total_sentiment = 0

        for c in comments:
            if c.keywords and keyword in c.keywords:
                match_count += 1
                total_sentiment += c.sentiment_score

        if match_count > 0:
            avg_sentiment = total_sentiment / match_count
            relevance = match_count / total if total > 0 else 0
            scores.append({
                'id': brand.id,
                'name': brand.name,
                'match_count': match_count,
                'avg_sentiment': round(avg_sentiment, 4),
                'relevance': round(relevance, 4),
            })

    scores.sort(key=lambda x: (x['avg_sentiment'], x['relevance']), reverse=True)
    return scores[:limit]

