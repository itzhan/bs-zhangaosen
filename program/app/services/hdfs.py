"""HDFS 数据管理服务

提供 HDFS 连接检测、文件列表、数据上传等功能，
满足开题报告"数据存储模块"中关于 HDFS 分布式存储的要求。
当 HDFS 不可用时（未部署 Hadoop 环境）自动降级，不抛异常。
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# HDFS 配置
HDFS_NAMENODE = os.environ.get("HDFS_NAMENODE", "hdfs://namenode:9000")
HDFS_BASE_DIR = "/jd_comment_analysis"

# HDFS 子目录
HDFS_DIRS = {
    "raw_comments": "原始评论数据",
    "sentiment_results": "情感分析结果",
    "spark_output": "Spark 分析输出",
    "models": "模型文件",
}

# 上传状态追踪
_upload_status = {
    "running": False,
    "last_run": None,
    "last_result": None,
    "uploaded_count": 0,
    "error": None,
}
_upload_lock = threading.Lock()


def _run_hdfs_cmd(args: list, timeout: int = 10) -> Optional[subprocess.CompletedProcess]:
    """执行 HDFS 命令，超时返回 None"""
    cmd = ["hdfs", "dfs"] + args
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None


def check_hdfs_connection() -> dict:
    """检测 HDFS 连接状态"""
    result = _run_hdfs_cmd(["-ls", "/"], timeout=5)
    if result and result.returncode == 0:
        return {
            "online": True,
            "namenode": HDFS_NAMENODE,
            "message": "HDFS 连接正常",
        }
    return {
        "online": False,
        "namenode": HDFS_NAMENODE,
        "message": "HDFS 不可达（未部署 Hadoop 或网络不通）",
    }


def list_hdfs_files(subdir: str = "") -> List[dict]:
    """列出 HDFS 指定目录下的文件"""
    hdfs_path = f"{HDFS_BASE_DIR}/{subdir}" if subdir else HDFS_BASE_DIR
    result = _run_hdfs_cmd(["-ls", hdfs_path], timeout=10)

    files = []
    if result and result.returncode == 0:
        # 标准 hdfs dfs -ls 输出行格式:
        # drwxr-xr-x   - root supergroup          0 2026-03-24 12:00 /path
        # -rw-r--r--   3 root supergroup       1234 2026-03-24 12:00 /path/file
        hdfs_line_re = re.compile(
            r'^([d\-][rwxsStT\-]{9})\s+'   # 权限
            r'[\d\-]+\s+'                   # 副本数
            r'\S+\s+'                        # 用户
            r'\S+\s+'                        # 组
            r'(\d+)\s+'                      # 文件大小
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+'  # 日期时间
            r'(.+)$'                         # 路径
        )

        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            m = hdfs_line_re.match(line)
            if not m:
                continue
            perms, size_str, date_str, path = m.groups()
            is_dir = perms.startswith("d")
            try:
                size = 0 if is_dir else int(size_str)
            except (ValueError, IndexError):
                size = 0
            files.append({
                "name": path.split("/")[-1],
                "path": path,
                "size": size,
                "size_display": _format_size(size) if not is_dir else "-",
                "date": date_str,
                "is_dir": is_dir,
            })
    return files


def _format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_hdfs_overview() -> dict:
    """HDFS 数据概览"""
    status = check_hdfs_connection()

    dirs_info = []
    total_files = 0
    total_size = 0

    if status["online"]:
        for subdir, desc in HDFS_DIRS.items():
            files = list_hdfs_files(subdir)
            file_count = len([f for f in files if not f["is_dir"]])
            dir_size = sum(f["size"] for f in files if not f["is_dir"])
            total_files += file_count
            total_size += dir_size
            dirs_info.append({
                "name": subdir,
                "description": desc,
                "file_count": file_count,
                "size": dir_size,
                "size_display": _format_size(dir_size),
                "files": files,
            })
    else:
        # 降级：显示本地文件信息作为参考
        local_dirs = {
            "raw_comments": Path("评论"),
            "sentiment_results": Path("output/sentiment_batch"),
            "spark_output": Path("output/spark_results"),
        }
        for subdir, desc in HDFS_DIRS.items():
            local_path = local_dirs.get(subdir)
            file_count = 0
            dir_size = 0
            files = []
            if local_path and local_path.exists():
                for fp in local_path.iterdir():
                    if fp.is_file() and fp.suffix.lower() in {".csv", ".xlsx", ".xls", ".json"}:
                        file_count += 1
                        fsize = fp.stat().st_size
                        dir_size += fsize
                        files.append({
                            "name": fp.name,
                            "path": str(fp),
                            "size": fsize,
                            "size_display": _format_size(fsize),
                            "date": datetime.fromtimestamp(fp.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                            "is_dir": False,
                        })
            total_files += file_count
            total_size += dir_size
            dirs_info.append({
                "name": subdir,
                "description": desc,
                "file_count": file_count,
                "size": dir_size,
                "size_display": _format_size(dir_size),
                "files": files,
            })

    return {
        "connection": status,
        "directories": dirs_info,
        "total_files": total_files,
        "total_size": total_size,
        "total_size_display": _format_size(total_size),
        "upload_status": get_upload_status(),
    }


def get_upload_status() -> dict:
    """获取上传任务状态"""
    with _upload_lock:
        return dict(_upload_status)


def trigger_upload() -> dict:
    """触发数据上传到 HDFS（后台线程）"""
    with _upload_lock:
        if _upload_status["running"]:
            return {"success": False, "message": "上传任务已在运行中"}

    # 检查连接
    status = check_hdfs_connection()
    if not status["online"]:
        return {"success": False, "message": "HDFS 不可达，无法上传"}

    # 启动后台上传线程
    t = threading.Thread(target=_do_upload, daemon=True, name="hdfs-upload")
    t.start()
    return {"success": True, "message": "上传任务已启动"}


def _do_upload():
    """后台执行 HDFS 上传"""
    with _upload_lock:
        _upload_status["running"] = True
        _upload_status["uploaded_count"] = 0
        _upload_status["error"] = None
        _upload_status["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        uploaded = 0

        # 确保目录存在
        for subdir in HDFS_DIRS:
            _run_hdfs_cmd(["-mkdir", "-p", f"{HDFS_BASE_DIR}/{subdir}"])

        # 上传原始评论
        comment_dir = Path("评论")
        if comment_dir.exists():
            for fp in sorted(comment_dir.iterdir()):
                if fp.suffix.lower() in {".csv", ".xlsx", ".xls"} and fp.is_file():
                    hdfs_path = f"{HDFS_BASE_DIR}/raw_comments/{fp.name}"
                    check = _run_hdfs_cmd(["-test", "-e", hdfs_path])
                    if check and check.returncode == 0:
                        continue
                    _run_hdfs_cmd(["-put", str(fp), hdfs_path], timeout=60)
                    uploaded += 1

        # 上传情感分析结果
        sentiment_dir = Path("output/sentiment_batch")
        if sentiment_dir.exists():
            for fp in sorted(sentiment_dir.iterdir()):
                if fp.suffix.lower() in {".csv", ".xlsx"} and fp.is_file():
                    hdfs_path = f"{HDFS_BASE_DIR}/sentiment_results/{fp.name}"
                    check = _run_hdfs_cmd(["-test", "-e", hdfs_path])
                    if check and check.returncode == 0:
                        continue
                    _run_hdfs_cmd(["-put", str(fp), hdfs_path], timeout=60)
                    uploaded += 1

        with _upload_lock:
            _upload_status["uploaded_count"] = uploaded
            _upload_status["last_result"] = f"成功上传 {uploaded} 个文件"

    except Exception as e:
        with _upload_lock:
            _upload_status["error"] = str(e)
            _upload_status["last_result"] = f"上传失败: {e}"

    finally:
        with _upload_lock:
            _upload_status["running"] = False
