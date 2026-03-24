"""HDFS 数据管理路由"""

import traceback
from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from app.services.hdfs import get_hdfs_overview, trigger_upload, get_upload_status

hdfs_bp = Blueprint('hdfs', __name__)


@hdfs_bp.route('/')
@login_required
def index():
    """HDFS 数据管理页面"""
    try:
        data = get_hdfs_overview()
    except Exception as e:
        traceback.print_exc()
        data = {
            'connection': {'online': False, 'namenode': 'N/A', 'message': f'服务异常: {e}'},
            'directories': [],
            'total_files': 0,
            'total_size': 0,
            'total_size_display': '0 B',
            'upload_status': {'running': False, 'last_run': None, 'last_result': None},
        }
    return render_template('admin/hdfs.html', data=data)


@hdfs_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """触发数据上传到 HDFS"""
    try:
        result = trigger_upload()
    except Exception as e:
        result = {'success': False, 'message': f'上传失败: {e}'}
    return jsonify(result)


@hdfs_bp.route('/api/status')
@login_required
def api_status():
    """上传任务状态查询"""
    return jsonify(get_upload_status())


@hdfs_bp.route('/api/overview')
@login_required
def api_overview():
    """HDFS 数据概览 API"""
    try:
        return jsonify(get_hdfs_overview())
    except Exception as e:
        return jsonify({'error': str(e)}), 500
