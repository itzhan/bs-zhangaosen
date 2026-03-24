"""系统监控与日志服务

提供 API 请求日志、爬虫任务监控、情感分析性能统计、系统资源监控等功能，
满足开题报告"系统监控与日志模块"和"系统优化模块"的要求。
"""

from __future__ import annotations

import os
import time
import json
import threading
from collections import deque
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional

import psutil
from sqlalchemy import func
from app import db
from app.models.task import CrawlerTask
from app.models.comment import Comment


# =========================================================
# 请求日志记录器
# =========================================================
class RequestLogger:
    """记录最近的 API 请求日志"""

    def __init__(self, max_entries: int = 500):
        self._logs: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def log(self, method: str, path: str, status: int, duration_ms: float):
        with self._lock:
            self._logs.append({
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'method': method,
                'path': path,
                'status': status,
                'duration_ms': round(duration_ms, 2),
            })

    def get_recent(self, n: int = 50) -> List[dict]:
        with self._lock:
            return list(self._logs)[-n:]

    def get_stats(self) -> dict:
        with self._lock:
            logs = list(self._logs)
        if not logs:
            return {'total': 0, 'avg_duration': 0, 'error_rate': 0}
        total = len(logs)
        avg_dur = sum(l['duration_ms'] for l in logs) / total
        errors = sum(1 for l in logs if l['status'] >= 400)
        return {
            'total': total,
            'avg_duration_ms': round(avg_dur, 2),
            'error_count': errors,
            'error_rate': round(errors / total * 100, 1),
        }


# 全局实例
request_logger = RequestLogger()


# =========================================================
# 性能计时器 / 中间件
# =========================================================
def init_monitor(app):
    """注册 Flask 请求监控中间件"""

    @app.before_request
    def _before():
        from flask import g
        g._start_time = time.time()

    @app.after_request
    def _after(response):
        from flask import g, request
        start = getattr(g, '_start_time', None)
        if start:
            duration = (time.time() - start) * 1000
            request_logger.log(
                method=request.method,
                path=request.path,
                status=response.status_code,
                duration_ms=duration,
            )
        return response


# =========================================================
# 爬虫任务监控
# =========================================================
def get_crawler_stats() -> dict:
    """爬虫任务统计"""
    total = CrawlerTask.query.count()
    completed = CrawlerTask.query.filter_by(status='completed').count()
    failed = CrawlerTask.query.filter_by(status='failed').count()
    running = CrawlerTask.query.filter_by(status='running').count()
    pending = CrawlerTask.query.filter_by(status='pending').count()

    # 平均耗时
    finished_tasks = CrawlerTask.query.filter(
        CrawlerTask.status.in_(['completed', 'failed']),
        CrawlerTask.start_time.isnot(None),
        CrawlerTask.end_time.isnot(None),
    ).all()

    avg_duration = 0
    if finished_tasks:
        durations = [(t.end_time - t.start_time).total_seconds() for t in finished_tasks]
        avg_duration = round(sum(durations) / len(durations), 1)

    total_comments = db.session.query(
        func.sum(CrawlerTask.total_count)
    ).filter(CrawlerTask.status == 'completed').scalar() or 0

    return {
        'total': total,
        'completed': completed,
        'failed': failed,
        'running': running,
        'pending': pending,
        'success_rate': round(completed / max(total, 1) * 100, 1),
        'avg_duration_sec': avg_duration,
        'total_comments_crawled': int(total_comments),
    }


# =========================================================
# 情感分析性能统计
# =========================================================
class AnalysisPerformanceTracker:
    """追踪情感分析方法的执行性能"""

    def __init__(self):
        self._snownlp_times: deque = deque(maxlen=100)
        self._lstm_times: deque = deque(maxlen=100)
        self._lock = threading.Lock()

    def record_snownlp(self, duration_ms: float):
        with self._lock:
            self._snownlp_times.append(duration_ms)

    def record_lstm(self, duration_ms: float):
        with self._lock:
            self._lstm_times.append(duration_ms)

    def get_comparison(self) -> dict:
        with self._lock:
            snlp = list(self._snownlp_times)
            lstm = list(self._lstm_times)
        return {
            'snownlp': {
                'count': len(snlp),
                'avg_ms': round(sum(snlp) / max(len(snlp), 1), 2),
                'max_ms': round(max(snlp, default=0), 2),
            },
            'lstm': {
                'count': len(lstm),
                'avg_ms': round(sum(lstm) / max(len(lstm), 1), 2),
                'max_ms': round(max(lstm, default=0), 2),
            },
        }


performance_tracker = AnalysisPerformanceTracker()


# =========================================================
# 系统资源监控
# =========================================================
def get_system_stats() -> dict:
    """获取系统资源使用情况"""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    process = psutil.Process(os.getpid())
    proc_mem = process.memory_info()

    return {
        'cpu_percent': cpu_percent,
        'memory': {
            'total_gb': round(memory.total / (1024 ** 3), 1),
            'used_gb': round(memory.used / (1024 ** 3), 1),
            'percent': memory.percent,
        },
        'disk': {
            'total_gb': round(disk.total / (1024 ** 3), 1),
            'used_gb': round(disk.used / (1024 ** 3), 1),
            'percent': round(disk.percent, 1),
        },
        'process': {
            'pid': process.pid,
            'memory_mb': round(proc_mem.rss / (1024 ** 2), 1),
            'threads': process.num_threads(),
        },
    }


# =========================================================
# 数据概览
# =========================================================
def get_data_stats() -> dict:
    """数据库数据统计"""
    from app.models.brand import Brand
    from app.models.user import User

    return {
        'total_comments': Comment.query.count(),
        'total_brands': Brand.query.count(),
        'total_users': User.query.count(),
        'total_tasks': CrawlerTask.query.count(),
        'sentiment_dist': dict(
            db.session.query(
                Comment.sentiment_label,
                func.count(Comment.id),
            ).group_by(Comment.sentiment_label).all()
        ),
    }


# =========================================================
# 汇总
# =========================================================
def get_monitor_overview() -> dict:
    """监控总览"""
    return {
        'system': get_system_stats(),
        'data': get_data_stats(),
        'requests': request_logger.get_stats(),
        'crawler': get_crawler_stats(),
        'analysis_perf': performance_tracker.get_comparison(),
    }
