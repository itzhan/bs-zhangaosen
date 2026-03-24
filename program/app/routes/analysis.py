"""行为分析 & 系统监控路由"""

from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from app.services.behavior import get_behavior_overview, get_user_profile_tags
from app.services.monitor import get_monitor_overview, request_logger

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/behavior')
@login_required
def behavior():
    """用户行为分析页面"""
    data = get_behavior_overview()
    return render_template('behavior.html', data=data)


@analysis_bp.route('/monitor')
@login_required
def monitor():
    """系统监控仪表盘"""
    data = get_monitor_overview()
    recent_logs = request_logger.get_recent(30)
    return render_template('admin/monitor.html', data=data, logs=recent_logs)


# ---- API 接口 ----

@analysis_bp.route('/api/behavior')
@login_required
def api_behavior():
    return jsonify(get_behavior_overview())


@analysis_bp.route('/api/monitor')
@login_required
def api_monitor():
    return jsonify(get_monitor_overview())


@analysis_bp.route('/api/user-tags')
@login_required
def api_user_tags():
    from flask import request
    brand_id = request.args.get('brand_id', type=int)
    tags = get_user_profile_tags(brand_id)
    return jsonify(tags)
