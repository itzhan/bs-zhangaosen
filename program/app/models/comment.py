"""评论模型"""
import json
from datetime import datetime
from app import db


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.id'), nullable=False, index=True)
    comment_id = db.Column(db.String(50), default='', index=True)
    comment_time = db.Column(db.DateTime, nullable=True)
    content = db.Column(db.Text, default='')
    cleaned_content = db.Column(db.Text, default='')
    score = db.Column(db.Integer, default=5)
    user_nickname = db.Column(db.String(100), default='')
    color = db.Column(db.Text, default='')
    model = db.Column(db.Text, default='')
    sentiment_score = db.Column(db.Float, default=0.5)
    sentiment_label = db.Column(db.Enum('正向', '中性', '负向'), default='中性')
    keywords = db.Column(db.JSON, default=list)
    create_time = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'brand_id': self.brand_id,
            'brand_name': self.brand.name if self.brand else '',
            'comment_id': self.comment_id,
            'comment_time': self.comment_time.strftime('%Y-%m-%d %H:%M:%S') if self.comment_time else None,
            'content': self.content,
            'cleaned_content': self.cleaned_content,
            'score': self.score,
            'user_nickname': self.user_nickname,
            'color': self.color,
            'model': self.model,
            'sentiment_score': self.sentiment_score,
            'sentiment_label': self.sentiment_label,
            'keywords': self.keywords or [],
        }
