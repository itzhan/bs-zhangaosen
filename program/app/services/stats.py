"""统计聚合服务 — 为各页面/API提供数据"""

from sqlalchemy import func, case
from app import db
from app.models.comment import Comment
from app.models.brand import Brand


def get_overview():
    """首页总览数据"""
    total_comments = Comment.query.count()
    total_brands = Brand.query.count()
    avg_score = db.session.query(func.avg(Comment.sentiment_score)).scalar() or 0

    sentiment_dist = db.session.query(
        Comment.sentiment_label,
        func.count(Comment.id)
    ).group_by(Comment.sentiment_label).all()

    dist = {label: count for label, count in sentiment_dist}

    # 各品牌概览
    brand_stats = db.session.query(
        Brand.id,
        Brand.name,
        Brand.image_url,
        func.count(Comment.id).label('comment_count'),
        func.avg(Comment.sentiment_score).label('avg_score'),
        func.sum(case((Comment.sentiment_label == '正向', 1), else_=0)).label('pos_count'),
    ).outerjoin(Comment, Comment.brand_id == Brand.id) \
        .group_by(Brand.id).all()

    brands = []
    for b in brand_stats:
        cc = int(b.comment_count or 0)
        pc = int(b.pos_count or 0)
        pos_rate = round(float(pc) / float(cc) * 100, 1) if cc > 0 else 0
        brands.append({
            'id': b.id,
            'name': b.name,
            'image_url': b.image_url,
            'comment_count': cc,
            'avg_score': round(float(b.avg_score or 0), 4),
            'pos_rate': float(pos_rate),
        })

    return {
        'total_comments': total_comments,
        'total_brands': total_brands,
        'avg_score': round(float(avg_score), 4),
        'sentiment_dist': dist,
        'brands': sorted(brands, key=lambda x: x['avg_score'], reverse=True),
    }


def get_brand_sentiment(brand_id):
    """品牌情感分析数据"""
    brand = Brand.query.get(brand_id)
    if not brand:
        return None

    comments = Comment.query.filter_by(brand_id=brand_id)

    # 情感分布
    dist = db.session.query(
        Comment.sentiment_label,
        func.count(Comment.id)
    ).filter(Comment.brand_id == brand_id) \
        .group_by(Comment.sentiment_label).all()

    # 时间趋势（按天）
    trend = db.session.query(
        func.date(Comment.comment_time).label('date'),
        func.avg(Comment.sentiment_score).label('avg_score'),
        func.count(Comment.id).label('count'),
    ).filter(
        Comment.brand_id == brand_id,
        Comment.comment_time.isnot(None),
    ).group_by(func.date(Comment.comment_time)) \
        .order_by(func.date(Comment.comment_time)).all()

    return {
        'brand': brand.to_dict(),
        'sentiment_dist': {label: count for label, count in dist},
        'trend': [
            {
                'date': str(t.date),
                'avg_score': round(float(t.avg_score), 4),
                'count': t.count,
            } for t in trend
        ],
        'total': comments.count(),
        'avg_score': round(float(
            db.session.query(func.avg(Comment.sentiment_score))
            .filter(Comment.brand_id == brand_id).scalar() or 0
        ), 4),
    }


def get_brand_keywords(brand_id, top_k=30):
    """品牌关键词统计"""
    comments = Comment.query.filter_by(brand_id=brand_id).all()
    from collections import Counter
    counter = Counter()
    for c in comments:
        if c.keywords:
            for kw in c.keywords:
                if kw and len(kw) > 1:
                    counter[kw] += 1
    return counter.most_common(top_k)


def get_compare_data(brand_ids):
    """多品牌对比数据"""
    results = []
    for bid in brand_ids:
        data = get_brand_sentiment(bid)
        if data:
            kws = get_brand_keywords(bid, 10)
            data['top_keywords'] = kws
            results.append(data)
    return results


def get_brand_color_dist(brand_id):
    """品牌颜色/型号分布"""
    color_dist = db.session.query(
        Comment.color,
        func.count(Comment.id).label('count'),
        func.avg(Comment.sentiment_score).label('avg_score'),
    ).filter(
        Comment.brand_id == brand_id,
        Comment.color != '',
        Comment.color.isnot(None),
    ).group_by(Comment.color).all()

    return [
        {
            'color': c.color,
            'count': c.count,
            'avg_score': round(float(c.avg_score or 0), 4),
        } for c in color_dist
    ]
