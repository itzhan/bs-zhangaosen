"""品牌模型"""
from datetime import datetime
from app import db


class Brand(db.Model):
    __tablename__ = 'brands'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    full_name = db.Column(db.String(200), default='')
    jd_url = db.Column(db.String(500), default='')
    image_url = db.Column(db.String(500), default='')
    description = db.Column(db.Text, default='')
    create_time = db.Column(db.DateTime, default=datetime.now)

    comments = db.relationship('Comment', backref='brand', lazy='dynamic')
    tasks = db.relationship('CrawlerTask', backref='brand', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'full_name': self.full_name,
            'jd_url': self.jd_url,
            'image_url': self.image_url,
            'description': self.description,
            'comment_count': self.comments.count(),
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }
