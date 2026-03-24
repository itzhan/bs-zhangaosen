#!/usr/bin/env python3
"""HDFS 初始化脚本 — 创建目录结构并上传评论数据到 HDFS

在 Docker 容器启动时自动运行，将本地评论数据上传到 HDFS。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


HDFS_NAMENODE = os.environ.get("HDFS_NAMENODE", "hdfs://namenode:9000")
HDFS_BASE_DIR = "/jd_comment_analysis"


def run_hdfs_cmd(args: list, check: bool = True) -> subprocess.CompletedProcess:
    """执行 HDFS 命令"""
    cmd = ["hdfs", "dfs"] + args
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def wait_for_hdfs(max_retries: int = 30) -> bool:
    """等待 HDFS NameNode 就绪"""
    for i in range(max_retries):
        result = run_hdfs_cmd(["-ls", "/"], check=False)
        if result.returncode == 0:
            print("  ✓ HDFS 已就绪")
            return True
        print(f"  等待 HDFS... ({i + 1}/{max_retries})")
        time.sleep(3)
    print("  ✗ HDFS 未就绪，超时退出")
    return False


def init_hdfs_dirs():
    """创建 HDFS 目录结构"""
    dirs = [
        f"{HDFS_BASE_DIR}",
        f"{HDFS_BASE_DIR}/raw_comments",        # 原始评论数据
        f"{HDFS_BASE_DIR}/sentiment_results",    # 情感分析结果
        f"{HDFS_BASE_DIR}/spark_output",         # Spark 分析输出
        f"{HDFS_BASE_DIR}/models",               # 模型文件
    ]
    for d in dirs:
        run_hdfs_cmd(["-mkdir", "-p", d], check=False)
    print("  ✓ HDFS 目录结构已创建")


def upload_comments():
    """上传评论数据文件到 HDFS"""
    uploaded = 0

    # 上传原始评论目录
    comment_dir = Path("评论")
    if comment_dir.exists():
        for fp in sorted(comment_dir.iterdir()):
            if fp.suffix.lower() in {".csv", ".xlsx", ".xls"} and fp.is_file():
                hdfs_path = f"{HDFS_BASE_DIR}/raw_comments/{fp.name}"
                # 检查是否已上传
                check = run_hdfs_cmd(["-test", "-e", hdfs_path], check=False)
                if check.returncode == 0:
                    print(f"  = {fp.name} 已存在于 HDFS，跳过")
                    continue
                run_hdfs_cmd(["-put", str(fp), hdfs_path], check=False)
                uploaded += 1
                print(f"  ↑ {fp.name} → HDFS")

    # 上传情感分析结果
    sentiment_dir = Path("output/sentiment_batch")
    if sentiment_dir.exists():
        for fp in sorted(sentiment_dir.iterdir()):
            if fp.suffix.lower() in {".csv", ".xlsx"} and fp.is_file():
                hdfs_path = f"{HDFS_BASE_DIR}/sentiment_results/{fp.name}"
                check = run_hdfs_cmd(["-test", "-e", hdfs_path], check=False)
                if check.returncode == 0:
                    continue
                run_hdfs_cmd(["-put", str(fp), hdfs_path], check=False)
                uploaded += 1

    print(f"  ✓ 共上传 {uploaded} 个文件到 HDFS")

    # 显示 HDFS 文件列表
    print("\n  HDFS 文件列表:")
    run_hdfs_cmd(["-ls", "-R", HDFS_BASE_DIR], check=False)


def main():
    print("=" * 50)
    print("  HDFS 初始化")
    print("=" * 50)

    # 设置 Hadoop 配置
    os.environ.setdefault("HADOOP_CONF_DIR", "/app/hadoop-conf")

    print("\n[1/3] 等待 HDFS NameNode...")
    if not wait_for_hdfs():
        print("[!] HDFS 未就绪，跳过 HDFS 初始化")
        return

    print("\n[2/3] 创建 HDFS 目录结构...")
    init_hdfs_dirs()

    print("\n[3/3] 上传数据到 HDFS...")
    upload_comments()

    print("\n" + "=" * 50)
    print("  ✓ HDFS 初始化完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
