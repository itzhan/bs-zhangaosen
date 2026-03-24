"""Spark 任务调度服务

提供 Web 端 Spark 分析任务的提交、进度追踪、结果管理功能，
满足开题报告"系统优化模块（任务调度、性能分析）"的要求。
"""

from __future__ import annotations

import json
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 任务存储（内存队列）
_tasks: List[dict] = []
_tasks_lock = threading.Lock()
_task_id_counter = 0


# 可选的分析类型
ANALYSIS_TYPES = {
    "brand_sentiment": "品牌情感统计",
    "daily_trend": "每日情感趋势",
    "score_distribution": "评分分布统计",
    "all": "全部分析",
}


def _next_id() -> int:
    global _task_id_counter
    _task_id_counter += 1
    return _task_id_counter


def submit_task(analysis_type: str = "all") -> dict:
    """提交新的 Spark 分析任务"""
    with _tasks_lock:
        # 检查是否有正在运行的任务
        running = [t for t in _tasks if t["status"] == "running"]
        if running:
            return {"success": False, "message": "已有任务正在运行，请等待完成"}

    task_id = _next_id()
    task = {
        "id": task_id,
        "type": analysis_type,
        "type_name": ANALYSIS_TYPES.get(analysis_type, analysis_type),
        "status": "pending",
        "progress": 0,
        "progress_text": "排队中...",
        "submit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_time": None,
        "end_time": None,
        "duration_sec": None,
        "result": None,
        "error": None,
    }

    with _tasks_lock:
        _tasks.insert(0, task)

    # 启动后台线程
    t = threading.Thread(
        target=_run_analysis,
        args=(task_id, analysis_type),
        daemon=True,
        name=f"spark-task-{task_id}",
    )
    t.start()

    return {"success": True, "message": f"Spark 分析任务 #{task_id} 已提交", "task_id": task_id}


def get_task_status(task_id: int) -> Optional[dict]:
    """获取单个任务状态"""
    with _tasks_lock:
        for t in _tasks:
            if t["id"] == task_id:
                return dict(t)
    return None


def get_task_history(limit: int = 20) -> List[dict]:
    """获取任务历史"""
    with _tasks_lock:
        return [dict(t) for t in _tasks[:limit]]


def _update_task(task_id: int, **kwargs):
    """更新任务状态"""
    with _tasks_lock:
        for t in _tasks:
            if t["id"] == task_id:
                t.update(kwargs)
                break


def _run_analysis(task_id: int, analysis_type: str):
    """后台执行 Spark 分析"""
    start = time.time()
    _update_task(task_id,
                 status="running",
                 start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 progress=5,
                 progress_text="初始化 Spark...")

    output_dir = Path("output/spark_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    try:
        from app.services.spark_processor import (
            brand_sentiment_stats,
            daily_trend_stats,
            score_distribution_stats,
            save_to_hdfs,
            stop_spark,
        )

        steps = []
        if analysis_type in ("all", "brand_sentiment"):
            steps.append(("brand_sentiment", "品牌情感统计", brand_sentiment_stats))
        if analysis_type in ("all", "daily_trend"):
            steps.append(("daily_trend", "每日情感趋势", daily_trend_stats))
        if analysis_type in ("all", "score_distribution"):
            steps.append(("score_distribution", "评分分布统计", score_distribution_stats))

        total = len(steps)
        for i, (key, name, func) in enumerate(steps):
            progress = int(10 + (i / total) * 80)
            _update_task(task_id, progress=progress, progress_text=f"执行 {name}...")

            # 执行 Spark SQL 分析
            df = func()
            data = [row.asDict() for row in df.collect()]

            # 保存到本地文件
            with open(output_dir / f"{key}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            df.toPandas().to_csv(output_dir / f"{key}.csv", index=False, encoding="utf-8-sig")

            # 尝试保存到 HDFS
            try:
                save_to_hdfs(df, key)
            except Exception:
                pass  # HDFS 不可用时跳过

            results[key] = {
                "name": name,
                "row_count": len(data),
                "sample": data[:5] if data else [],
            }

        _update_task(task_id, progress=95, progress_text="生成汇总报告...")

        # 汇总报告
        summary = {
            "分析类型": ANALYSIS_TYPES.get(analysis_type, analysis_type),
            "分析项目数": len(steps),
            "输出目录": str(output_dir),
            "各分析结果": {k: f"{v['row_count']} 行数据" for k, v in results.items()},
        }
        with open(output_dir / "analysis_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 停止 Spark
        try:
            stop_spark()
        except Exception:
            pass

        duration = round(time.time() - start, 1)
        _update_task(
            task_id,
            status="completed",
            progress=100,
            progress_text="分析完成",
            end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration_sec=duration,
            result=results,
        )

    except ImportError as e:
        duration = round(time.time() - start, 1)
        _update_task(
            task_id,
            status="failed",
            progress=0,
            progress_text="依赖缺失",
            end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration_sec=duration,
            error=f"PySpark 未安装或数据库不可用: {e}",
        )
    except Exception as e:
        duration = round(time.time() - start, 1)
        _update_task(
            task_id,
            status="failed",
            progress=0,
            progress_text="执行失败",
            end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            duration_sec=duration,
            error=str(e),
        )
        traceback.print_exc()


def get_latest_results() -> Optional[dict]:
    """获取最近一次 Spark 分析结果（从文件读取）"""
    result_dir = Path("output/spark_results")
    if not result_dir.exists():
        return None

    results = {}
    for key in ["brand_sentiment", "daily_trend", "score_distribution"]:
        json_path = result_dir / f"{key}.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    results[key] = json.load(f)
            except Exception:
                pass

    return results if results else None
