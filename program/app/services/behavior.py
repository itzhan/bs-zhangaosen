"""用户行为分析服务

提供用户活跃度、评分分布、用户画像标签等分析功能，
满足开题报告"用户行为分析模块"的要求。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import func, case, extract
from app import db
from app.models.comment import Comment
from app.models.brand import Brand
from app.models.user import User
from app.models.favorite import UserFavorite


def get_activity_by_hour() -> List[dict]:
    """按小时统计评论活跃度（用户发评的时间段分布）"""
    result = db.session.query(
        extract('hour', Comment.comment_time).label('hour'),
        func.count(Comment.id).label('count'),
    ).filter(
        Comment.comment_time.isnot(None),
    ).group_by(
        extract('hour', Comment.comment_time)
    ).order_by('hour').all()

    return [{'hour': int(r.hour), 'count': int(r.count)} for r in result]


def get_activity_by_weekday() -> List[dict]:
    """按星期统计评论活跃度"""
    result = db.session.query(
        extract('dow', Comment.comment_time).label('weekday'),
        func.count(Comment.id).label('count'),
    ).filter(
        Comment.comment_time.isnot(None),
    ).group_by(
        extract('dow', Comment.comment_time)
    ).order_by('weekday').all()

    weekday_names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return [
        {'weekday': weekday_names[int(r.weekday) % 7], 'count': int(r.count)}
        for r in result
    ]


def get_rating_distribution() -> Dict[str, List[dict]]:
    """各品牌评分区间分布"""
    brands = Brand.query.all()
    result = {}
    for brand in brands:
        dist = db.session.query(
            Comment.score,
            func.count(Comment.id).label('count'),
        ).filter(
            Comment.brand_id == brand.id,
        ).group_by(Comment.score).order_by(Comment.score).all()

        result[brand.name] = [
            {'rating': int(d.score), 'count': int(d.count)} for d in dist
        ]
    return result


def get_user_engagement_stats() -> dict:
    """用户参与度统计"""
    total_users = User.query.count()
    total_comments = Comment.query.count()
    total_favorites = UserFavorite.query.count()

    # 评论用户数（按昵称去重）
    unique_commenters = db.session.query(
        func.count(func.distinct(Comment.user_nickname))
    ).filter(
        Comment.user_nickname != '',
        Comment.user_nickname.isnot(None),
    ).scalar() or 0

    # 平均每用户评论数
    avg_comments = round(total_comments / max(unique_commenters, 1), 1)

    return {
        'total_users': total_users,
        'total_comments': total_comments,
        'total_favorites': total_favorites,
        'unique_commenters': unique_commenters,
        'avg_comments_per_user': avg_comments,
    }


def get_user_profile_tags(brand_id: int = None) -> List[dict]:
    """用户画像标签（基于评论行为生成）"""
    query = Comment.query
    if brand_id:
        query = query.filter(Comment.brand_id == brand_id)

    comments = query.all()

    tags = Counter()
    for c in comments:
        # 基于情感标签
        if c.sentiment_label == '正向':
            tags['好评用户'] += 1
        elif c.sentiment_label == '负向':
            tags['差评用户'] += 1
        else:
            tags['中立用户'] += 1

        # 基于评分
        if c.score and c.score >= 4:
            tags['高分评价'] += 1
        elif c.score and c.score <= 2:
            tags['低分评价'] += 1

        # 基于评论长度
        content = c.content or ''
        if len(content) > 100:
            tags['深度评论'] += 1
        elif len(content) < 20:
            tags['简短评论'] += 1

        # 基于关键词
        if c.keywords:
            for kw in c.keywords:
                if kw in ('手感', '屏幕', '外观', '设计', '颜值'):
                    tags['外观关注'] += 1
                    break
            for kw in c.keywords:
                if kw in ('性能', '速度', '流畅', '处理器', '运行'):
                    tags['性能关注'] += 1
                    break
            for kw in c.keywords:
                if kw in ('拍照', '摄像', '镜头', '相机', '照片'):
                    tags['拍照关注'] += 1
                    break
            for kw in c.keywords:
                if kw in ('电池', '续航', '充电', '电量'):
                    tags['续航关注'] += 1
                    break

    return [
        {'tag': tag, 'count': count}
        for tag, count in tags.most_common(20)
    ]


def get_comment_length_distribution() -> List[dict]:
    """评论长度分布"""
    comments = Comment.query.with_entities(Comment.content).all()

    ranges = {'0-20字': 0, '20-50字': 0, '50-100字': 0, '100-200字': 0, '200字以上': 0}
    for (content,) in comments:
        length = len(content or '')
        if length <= 20:
            ranges['0-20字'] += 1
        elif length <= 50:
            ranges['20-50字'] += 1
        elif length <= 100:
            ranges['50-100字'] += 1
        elif length <= 200:
            ranges['100-200字'] += 1
        else:
            ranges['200字以上'] += 1

    return [{'range': k, 'count': v} for k, v in ranges.items()]


def get_behavior_overview() -> dict:
    """行为分析总览"""
    return {
        'engagement': get_user_engagement_stats(),
        'hourly_activity': get_activity_by_hour(),
        'rating_distribution': get_rating_distribution(),
        'user_tags': get_user_profile_tags(),
        'comment_length_dist': get_comment_length_distribution(),
    }
