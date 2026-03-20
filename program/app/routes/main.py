"""首页/总览路由"""
from flask import Blueprint, render_template
from app.services.stats import get_overview
from app.services.recommend import recommend_brands

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首页数据大屏"""
    overview = get_overview()
    recommended = recommend_brands(limit=6)
    return render_template('index.html',
                           overview=overview,
                           recommended=recommended)
