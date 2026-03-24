"""首页/总览路由"""
from flask import Blueprint, render_template
from flask_login import current_user
from app.services.stats import get_overview
from app.services.recommend import hybrid_recommend

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首页数据大屏"""
    overview = get_overview()
    # 登录用户 → ALS + 情感加权混合推荐; 未登录 → 规则推荐
    user_id = current_user.id if current_user.is_authenticated else None
    recommended = hybrid_recommend(user_id=user_id, limit=6)
    return render_template('index.html',
                           overview=overview,
                           recommended=recommended)

