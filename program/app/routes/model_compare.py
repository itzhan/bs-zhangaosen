"""模型对比分析路由 — LSTM vs SnowNLP"""

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models.comment import Comment
from app.models.brand import Brand

model_compare_bp = Blueprint('model_compare', __name__)


@model_compare_bp.route('/model-compare')
@login_required
def compare():
    """LSTM vs SnowNLP 模型对比分析页面"""
    brands = Brand.query.all()

    # 收集每个品牌上两种方法的分析结果
    brand_comparison = []
    for brand in brands:
        comments = Comment.query.filter_by(brand_id=brand.id).all()
        if not comments:
            continue

        from app.services import sentiment_score, sentiment_label, clean_text

        # 统计 SnowNLP 结果（数据库中已有）
        snow_scores = [c.sentiment_score or 0.5 for c in comments]
        snow_avg = round(sum(snow_scores) / len(snow_scores), 4)
        snow_pos = sum(1 for c in comments if c.sentiment_label == '正向')
        snow_neg = sum(1 for c in comments if c.sentiment_label == '负向')
        snow_mid = len(comments) - snow_pos - snow_neg

        # 抽样用 LSTM 预测（取前50条，避免耗时过长）
        lstm_available = False
        lstm_avg = 0.5
        lstm_pos = 0
        lstm_neg = 0
        lstm_mid = 0
        lstm_agree = 0  # 两种方法一致的数量

        try:
            from app.services.lstm_model import predict
            sample = comments[:50]
            lstm_scores_list = []
            for c in sample:
                text = clean_text(c.content or '')
                if not text:
                    continue
                result = predict(text)
                if result:
                    lstm_scores_list.append(result['score'])
                    if result['label'] == '正向':
                        lstm_pos += 1
                    elif result['label'] == '负向':
                        lstm_neg += 1
                    else:
                        lstm_mid += 1
                    # 一致性检查
                    if result['label'] == c.sentiment_label:
                        lstm_agree += 1

            if lstm_scores_list:
                lstm_available = True
                lstm_avg = round(sum(lstm_scores_list) / len(lstm_scores_list), 4)

        except Exception:
            pass

        sample_size = min(len(comments), 50)
        brand_comparison.append({
            'name': brand.name,
            'total': len(comments),
            'sample_size': sample_size,
            'snow_avg': snow_avg,
            'snow_pos': snow_pos,
            'snow_neg': snow_neg,
            'snow_mid': snow_mid,
            'snow_pos_rate': round(snow_pos / len(comments) * 100, 1),
            'lstm_available': lstm_available,
            'lstm_avg': lstm_avg,
            'lstm_pos': lstm_pos,
            'lstm_neg': lstm_neg,
            'lstm_mid': lstm_mid,
            'lstm_pos_rate': round(lstm_pos / max(sample_size, 1) * 100, 1) if lstm_available else 0,
            'agree_rate': round(lstm_agree / max(sample_size, 1) * 100, 1) if lstm_available else 0,
        })

    return render_template('model_compare.html',
                           brands=brand_comparison,
                           lstm_available=any(b['lstm_available'] for b in brand_comparison))
