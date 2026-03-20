"""JSON API 路由 — 供前端 ECharts 异步请求"""
from flask import Blueprint, jsonify, request
from app.services.stats import (
    get_overview, get_brand_sentiment, get_brand_keywords,
    get_compare_data, get_brand_color_dist,
)
from app.services.recommend import recommend_brands, recommend_by_keyword
from app.models.brand import Brand
from app.models.comment import Comment

api_bp = Blueprint('api', __name__)


@api_bp.route('/stats/overview')
def overview():
    return jsonify(code=200, data=get_overview())


@api_bp.route('/brands')
def brands():
    brands_list = Brand.query.all()
    return jsonify(code=200, data=[b.to_dict() for b in brands_list])


@api_bp.route('/brands/<int:brand_id>/sentiment')
def brand_sentiment(brand_id):
    data = get_brand_sentiment(brand_id)
    if not data:
        return jsonify(code=404, message='品牌不存在'), 404
    return jsonify(code=200, data=data)


@api_bp.route('/brands/<int:brand_id>/keywords')
def brand_keywords(brand_id):
    top_k = request.args.get('top', 30, type=int)
    kws = get_brand_keywords(brand_id, top_k)
    return jsonify(code=200, data=[{'word': w, 'count': c} for w, c in kws])


@api_bp.route('/brands/<int:brand_id>/colors')
def brand_colors(brand_id):
    return jsonify(code=200, data=get_brand_color_dist(brand_id))


@api_bp.route('/compare')
def compare():
    ids = request.args.getlist('ids', type=int)
    if not ids:
        return jsonify(code=400, message='请选择品牌'), 400
    return jsonify(code=200, data=get_compare_data(ids))


@api_bp.route('/recommend')
def recommend():
    keyword = request.args.get('keyword', '').strip()
    if keyword:
        data = recommend_by_keyword(keyword)
    else:
        data = recommend_brands()
    return jsonify(code=200, data=data)


@api_bp.route('/comments/search')
def search():
    keyword = request.args.get('q', '').strip()
    brand_id = request.args.get('brand_id', 0, type=int)
    label = request.args.get('label', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Comment.query
    if keyword:
        query = query.filter(Comment.content.contains(keyword))
    if brand_id:
        query = query.filter_by(brand_id=brand_id)
    if label:
        query = query.filter_by(sentiment_label=label)

    pagination = query.order_by(Comment.comment_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False)

    return jsonify(code=200, data={
        'items': [c.to_dict() for c in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
    })
