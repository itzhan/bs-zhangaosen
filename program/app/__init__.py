"""Flask 应用工厂"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # 配置
    app.config.from_object('app.config.Config')

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)

    # 注册蓝图
    from app.routes.main import main_bp
    from app.routes.brand import brand_bp
    from app.routes.search import search_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.crawler import crawler_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(brand_bp, url_prefix='/brand')
    app.register_blueprint(search_bp, url_prefix='/search')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(crawler_bp, url_prefix='/crawler')
    app.register_blueprint(api_bp, url_prefix='/api')

    # 创建表
    with app.app_context():
        db.create_all()

    return app
