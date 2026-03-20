"""爬虫任务模型"""
from datetime import datetime
from app import db


class CrawlerTask(db.Model):
    __tablename__ = 'crawler_tasks'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.id'), nullable=True)
    jd_url = db.Column(db.String(500), nullable=False)
    status = db.Column(db.Enum('pending', 'running', 'completed', 'failed'), default='pending')
    total_count = db.Column(db.Integer, default=0)
    error_msg = db.Column(db.Text, default='')
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    create_time = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'brand_id': self.brand_id,
            'brand_name': self.brand.name if self.brand else '',
            'jd_url': self.jd_url,
            'status': self.status,
            'total_count': self.total_count,
            'error_msg': self.error_msg,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
        }
