"""Spark 任务管理路由"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required

from app.services.spark_task import (
    submit_task, get_task_status, get_task_history,
    get_latest_results, ANALYSIS_TYPES,
)

spark_bp = Blueprint('spark', __name__)


@spark_bp.route('/')
@login_required
def index():
    """Spark 任务管理页面"""
    tasks = get_task_history(20)
    results = get_latest_results()
    return render_template('admin/spark.html',
                           tasks=tasks,
                           results=results,
                           analysis_types=ANALYSIS_TYPES)


@spark_bp.route('/run', methods=['POST'])
@login_required
def run():
    """提交 Spark 分析任务"""
    analysis_type = request.form.get('type', 'all')
    result = submit_task(analysis_type)
    return jsonify(result)


@spark_bp.route('/api/status/<int:task_id>')
@login_required
def api_status(task_id):
    """查询任务进度"""
    status = get_task_status(task_id)
    if not status:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(status)


@spark_bp.route('/api/results')
@login_required
def api_results():
    """获取最近的分析结果"""
    results = get_latest_results()
    return jsonify({"data": results})
