"""推荐服务 — 基于情感得分的推荐"""

from sqlalchemy import func, case
from app import db
from app.models.comment import Comment
from app.models.brand import Brand


def recommend_brands(limit=6):
    """基于情感得分的品牌推荐"""
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
        })

    results.sort(key=lambda x: x['composite_score'], reverse=True)
    return results[:limit]


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
