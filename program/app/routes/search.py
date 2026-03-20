"""搜索路由"""
from flask import Blueprint, render_template, request
from app.models.comment import Comment
from app.models.brand import Brand

search_bp = Blueprint('search', __name__)


@search_bp.route('/')
def search():
    """评论搜索页"""
    keyword = request.args.get('q', '').strip()
    brand_id = request.args.get('brand_id', 0, type=int)
    label = request.args.get('label', '')
    page = request.args.get('page', 1, type=int)

    brands = Brand.query.all()
    pagination = None

    if keyword:
        query = Comment.query.filter(Comment.content.contains(keyword))
        if brand_id:
            query = query.filter_by(brand_id=brand_id)
        if label:
            query = query.filter_by(sentiment_label=label)
        pagination = query.order_by(Comment.comment_time.desc()).paginate(
            page=page, per_page=20, error_out=False)

    return render_template('search.html',
                           keyword=keyword,
                           brand_id=brand_id,
                           label=label,
                           brands=brands,
                           pagination=pagination)
