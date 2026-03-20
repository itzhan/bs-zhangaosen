"""用户收藏模型"""
from datetime import datetime
from app import db


class UserFavorite(db.Model):
    __tablename__ = 'user_favorites'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.id'), nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now)

    brand = db.relationship('Brand', backref='favorites')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'brand_id', name='uq_user_brand'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'brand_id': self.brand_id,
            'brand_name': self.brand.name if self.brand else '',
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M:%S') if self.create_time else None,
        }
