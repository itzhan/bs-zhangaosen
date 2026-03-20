"""认证路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.models.favorite import UserFavorite
from app.models.brand import Brand

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next', url_for('main.index'))
            flash('登录成功！', 'success')
            return redirect(next_page)
        flash('用户名或密码错误', 'danger')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        nickname = request.form.get('nickname', '').strip() or username

        if not username or not password:
            flash('用户名和密码不能为空', 'danger')
        elif password != password2:
            flash('两次密码不一致', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
        else:
            user = User(username=username, nickname=nickname)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/profile')
@login_required
def profile():
    """个人中心"""
    favorites = UserFavorite.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', favorites=favorites)


@auth_bp.route('/favorite/<int:brand_id>', methods=['POST'])
@login_required
def toggle_favorite(brand_id):
    """收藏/取消收藏品牌"""
    brand = Brand.query.get_or_404(brand_id)
    fav = UserFavorite.query.filter_by(
        user_id=current_user.id, brand_id=brand_id).first()

    if fav:
        db.session.delete(fav)
        db.session.commit()
        flash(f'已取消收藏 {brand.name}', 'info')
    else:
        fav = UserFavorite(user_id=current_user.id, brand_id=brand_id)
        db.session.add(fav)
        db.session.commit()
        flash(f'已收藏 {brand.name}', 'success')

    return redirect(request.referrer or url_for('brand.detail', brand_id=brand_id))
