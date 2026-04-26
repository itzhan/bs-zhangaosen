"""管理后台路由"""
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.brand import Brand
from app.models.comment import Comment


SENTIMENT_LABELS = ('正向', '中性', '负向')


def _parse_comment_form(form):
    """从表单解析评论字段，返回 (data_dict, error_msg)"""
    brand_id = form.get('brand_id', type=int)
    if not brand_id or not Brand.query.get(brand_id):
        return None, '请选择有效的品牌'

    content = (form.get('content') or '').strip()
    if not content:
        return None, '评论内容不能为空'

    score = form.get('score', type=int) or 5
    score = max(1, min(5, score))

    sentiment_label = form.get('sentiment_label') or '中性'
    if sentiment_label not in SENTIMENT_LABELS:
        sentiment_label = '中性'

    try:
        sentiment_score = float(form.get('sentiment_score') or 0.5)
    except ValueError:
        sentiment_score = 0.5
    sentiment_score = max(0.0, min(1.0, sentiment_score))

    comment_time_raw = (form.get('comment_time') or '').strip()
    comment_time = None
    if comment_time_raw:
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                comment_time = datetime.strptime(comment_time_raw, fmt)
                break
            except ValueError:
                continue

    return {
        'brand_id': brand_id,
        'content': content,
        'cleaned_content': content,
        'score': score,
        'user_nickname': (form.get('user_nickname') or '').strip(),
        'color': (form.get('color') or '').strip(),
        'model': (form.get('model') or '').strip(),
        'sentiment_label': sentiment_label,
        'sentiment_score': sentiment_score,
        'comment_time': comment_time,
    }, None

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('需要管理员权限', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@admin_required
def dashboard():
    """管理后台首页"""
    user_count = User.query.count()
    brand_count = Brand.query.count()
    comment_count = Comment.query.count()
    return render_template('admin/dashboard.html',
                           user_count=user_count,
                           brand_count=brand_count,
                           comment_count=comment_count)


@admin_bp.route('/users')
@admin_required
def users():
    """用户管理"""
    page = request.args.get('page', 1, type=int)
    pagination = User.query.order_by(User.create_time.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', pagination=pagination)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('不能删除自己', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'已删除用户 {user.username}', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/brands')
@admin_required
def brands():
    """品牌管理"""
    brands_list = Brand.query.all()
    return render_template('admin/brands.html', brands=brands_list)


@admin_bp.route('/brands/add', methods=['POST'])
@admin_required
def add_brand():
    name = request.form.get('name', '').strip()
    full_name = request.form.get('full_name', '').strip()
    jd_url = request.form.get('jd_url', '').strip()
    if not name:
        flash('品牌名不能为空', 'danger')
    elif Brand.query.filter_by(name=name).first():
        flash('品牌名已存在', 'danger')
    else:
        brand = Brand(name=name, full_name=full_name, jd_url=jd_url)
        db.session.add(brand)
        db.session.commit()
        flash(f'已添加品牌 {name}', 'success')
    return redirect(url_for('admin.brands'))


@admin_bp.route('/brands/<int:brand_id>/delete', methods=['POST'])
@admin_required
def delete_brand(brand_id):
    brand = Brand.query.get_or_404(brand_id)
    Comment.query.filter_by(brand_id=brand_id).delete()
    db.session.delete(brand)
    db.session.commit()
    flash(f'已删除品牌 {brand.name} 及其所有评论', 'success')
    return redirect(url_for('admin.brands'))


@admin_bp.route('/comments')
@admin_required
def comments():
    """评论管理 — 列表 + 关键词/品牌筛选"""
    page = request.args.get('page', 1, type=int)
    brand_id = request.args.get('brand_id', 0, type=int)
    keyword = (request.args.get('keyword') or '').strip()
    sentiment = (request.args.get('sentiment') or '').strip()

    query = Comment.query
    if brand_id:
        query = query.filter_by(brand_id=brand_id)
    if keyword:
        query = query.filter(Comment.content.like(f'%{keyword}%'))
    if sentiment in SENTIMENT_LABELS:
        query = query.filter_by(sentiment_label=sentiment)

    pagination = query.order_by(Comment.create_time.desc()).paginate(
        page=page, per_page=30, error_out=False)
    brands_list = Brand.query.all()
    return render_template('admin/comments.html',
                           pagination=pagination,
                           brands=brands_list,
                           brand_id=brand_id,
                           keyword=keyword,
                           sentiment=sentiment,
                           sentiment_labels=SENTIMENT_LABELS)


@admin_bp.route('/comments/add', methods=['POST'])
@admin_required
def add_comment():
    data, err = _parse_comment_form(request.form)
    if err:
        flash(err, 'danger')
        return redirect(url_for('admin.comments'))
    comment = Comment(**data)
    db.session.add(comment)
    db.session.commit()
    flash(f'已新增评论 #{comment.id}', 'success')
    return redirect(url_for('admin.comments'))


@admin_bp.route('/comments/<int:comment_id>/edit', methods=['POST'])
@admin_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    data, err = _parse_comment_form(request.form)
    if err:
        flash(err, 'danger')
        return redirect(url_for('admin.comments', page=request.args.get('page', 1)))
    for k, v in data.items():
        setattr(comment, k, v)
    db.session.commit()
    flash(f'已更新评论 #{comment.id}', 'success')
    return redirect(url_for('admin.comments', page=request.args.get('page', 1)))


@admin_bp.route('/comments/<int:comment_id>/delete', methods=['POST'])
@admin_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash(f'已删除评论 #{comment_id}', 'success')
    return redirect(url_for('admin.comments', page=request.args.get('page', 1)))


@admin_bp.route('/comments/<int:comment_id>')
@admin_required
def get_comment(comment_id):
    """JSON 接口：供编辑模态框预填表单"""
    comment = Comment.query.get_or_404(comment_id)
    return jsonify(comment.to_dict())
