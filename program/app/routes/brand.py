"""品牌路由"""
from flask import Blueprint, render_template, request, jsonify
from app.models.brand import Brand
from app.services.stats import get_brand_sentiment, get_brand_keywords, get_compare_data, get_brand_color_dist
from app.models.comment import Comment

brand_bp = Blueprint('brand', __name__)


@brand_bp.route('/<int:brand_id>')
def detail(brand_id):
    """品牌详情页"""
    brand = Brand.query.get_or_404(brand_id)
    sentiment = get_brand_sentiment(brand_id)
    keywords = get_brand_keywords(brand_id, 30)
    color_dist = get_brand_color_dist(brand_id)

    # 分页评论列表
    page = request.args.get('page', 1, type=int)
    label_filter = request.args.get('label', '')
    query = Comment.query.filter_by(brand_id=brand_id)
    if label_filter:
        query = query.filter_by(sentiment_label=label_filter)
    pagination = query.order_by(Comment.comment_time.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('brand_detail.html',
                           brand=brand,
                           sentiment=sentiment,
                           keywords=keywords,
                           color_dist=color_dist,
                           pagination=pagination,
                           label_filter=label_filter)


@brand_bp.route('/compare')
def compare():
    """品牌对比页"""
    brands = Brand.query.all()
    # 获取选中的品牌
    selected_ids = request.args.getlist('ids', type=int)
    compare_data = []
    if selected_ids:
        compare_data = get_compare_data(selected_ids)
    return render_template('compare.html',
                           brands=brands,
                           selected_ids=selected_ids,
                           compare_data=compare_data)
