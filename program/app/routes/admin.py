"""管理后台路由"""
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.brand import Brand
from app.models.comment import Comment

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
    """评论管理"""
    page = request.args.get('page', 1, type=int)
    brand_id = request.args.get('brand_id', 0, type=int)
    query = Comment.query
    if brand_id:
        query = query.filter_by(brand_id=brand_id)
    pagination = query.order_by(Comment.create_time.desc()).paginate(
        page=page, per_page=30, error_out=False)
    brands_list = Brand.query.all()
    return render_template('admin/comments.html',
                           pagination=pagination,
                           brands=brands_list,
                           brand_id=brand_id)
