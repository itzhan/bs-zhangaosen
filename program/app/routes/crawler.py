"""爬虫管理路由"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required
from app import db
from app.models.task import CrawlerTask
from app.models.brand import Brand

crawler_bp = Blueprint('crawler', __name__)


@crawler_bp.route('/')
@login_required
def index():
    """爬虫任务列表"""
    tasks = CrawlerTask.query.order_by(CrawlerTask.create_time.desc()).all()
    brands = Brand.query.all()
    return render_template('crawler.html', tasks=tasks, brands=brands)


@crawler_bp.route('/create', methods=['POST'])
@login_required
def create_task():
    """创建并立即启动爬虫任务"""
    jd_url = request.form.get('jd_url', '').strip()
    brand_id = request.form.get('brand_id', 0, type=int)
    max_pages = request.form.get('max_pages', 10, type=int)

    if not jd_url:
        flash('请输入京东商品链接', 'danger')
        return redirect(url_for('crawler.index'))

    if not jd_url.startswith('http'):
        jd_url = 'https://' + jd_url

    # 创建任务记录
    task = CrawlerTask(
        jd_url=jd_url,
        brand_id=brand_id if brand_id else None,
        status='pending',
    )
    db.session.add(task)
    db.session.commit()

    # 立即启动后台爬虫线程
    try:
        from app.services.crawler import start_crawler_task
        start_crawler_task(
            app=current_app._get_current_object(),
            task_id=task.id,
            jd_url=jd_url,
            brand_id=brand_id if brand_id else None,
            max_pages=max_pages,
        )
        flash(f'爬虫任务 #{task.id} 已启动，正在后台采集评论...', 'success')
    except ImportError:
        task.status = 'failed'
        task.error_msg = '未安装 DrissionPage'
        db.session.commit()
        flash('启动失败：未安装 DrissionPage，请先运行 pip install DrissionPage', 'danger')
    except Exception as e:
        task.status = 'failed'
        task.error_msg = str(e)[:500]
        db.session.commit()
        flash(f'启动失败：{e}', 'danger')

    return redirect(url_for('crawler.index'))


@crawler_bp.route('/status/<int:task_id>')
@login_required
def task_status(task_id):
    """查询任务实时状态（AJAX 接口）"""
    task = CrawlerTask.query.get_or_404(task_id)
    return jsonify({
        'id': task.id,
        'status': task.status,
        'total_count': task.total_count,
        'error_msg': task.error_msg or '',
        'start_time': str(task.start_time) if task.start_time else '',
        'end_time': str(task.end_time) if task.end_time else '',
    })


@crawler_bp.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    """删除任务"""
    task = CrawlerTask.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('任务已删除', 'success')
    return redirect(url_for('crawler.index'))
