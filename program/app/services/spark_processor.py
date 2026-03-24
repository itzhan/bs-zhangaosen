"""Spark 数据处理模块 — 基于 PySpark + Hadoop HDFS

提供分布式数据处理与分析功能：
- 从 HDFS 读取原始评论数据
- Spark SQL 评论数据聚合统计
- 分布式情感分析（Spark UDF）
- 分析结果写回 HDFS
- 品牌对比分析 / 时间趋势分析
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional

# PySpark 延迟导入
_spark_session = None

# HDFS 配置
HDFS_NAMENODE = os.environ.get("HDFS_NAMENODE", "hdfs://namenode:9000")
HDFS_BASE_DIR = "/jd_comment_analysis"


def _get_spark():
    """获取或创建 SparkSession（连接 HDFS）"""
    global _spark_session
    if _spark_session is not None:
        return _spark_session

    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder
        .appName("JD-Comment-Analysis")
        .master("local[*]")
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.showConsoleProgress", "false")
    )

    # 配置 HDFS 连接
    hadoop_conf = os.environ.get("HADOOP_CONF_DIR", "")
    if hadoop_conf:
        builder = builder.config("spark.hadoop.fs.defaultFS", HDFS_NAMENODE)

    _spark_session = builder.getOrCreate()
    _spark_session.sparkContext.setLogLevel("WARN")
    return _spark_session


def _get_jdbc_props() -> dict:
    """获取 MySQL JDBC 连接参数"""
    return {
        "url": "jdbc:mysql://{}:{}/{}?useSSL=false&characterEncoding=utf8mb4".format(
            os.environ.get("DB_HOST", "localhost"),
            os.environ.get("DB_PORT", "3306"),
            os.environ.get("DB_NAME", "jd_comment_analysis"),
        ),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASS", "ab123168"),
        "driver": "com.mysql.cj.jdbc.Driver",
    }


# =========================================================
# HDFS 数据读写
# =========================================================
def load_comments_from_hdfs():
    """从 HDFS 读取原始评论 CSV 文件到 Spark DataFrame"""
    spark = _get_spark()
    hdfs_path = f"{HDFS_NAMENODE}{HDFS_BASE_DIR}/raw_comments/"
    try:
        df = spark.read.csv(hdfs_path, header=True, inferSchema=True, encoding="utf-8")
        print(f"  ✓ 从 HDFS 读取评论数据: {df.count()} 条")
        return df
    except Exception as e:
        print(f"  ! 从 HDFS 读取失败: {e}，回退到 MySQL")
        return None


def load_sentiment_from_hdfs():
    """从 HDFS 读取情感分析结果"""
    spark = _get_spark()
    hdfs_path = f"{HDFS_NAMENODE}{HDFS_BASE_DIR}/sentiment_results/"
    try:
        df = spark.read.csv(hdfs_path, header=True, inferSchema=True, encoding="utf-8")
        print(f"  ✓ 从 HDFS 读取情感结果: {df.count()} 条")
        return df
    except Exception as e:
        print(f"  ! 从 HDFS 读取情感结果失败: {e}")
        return None


def save_to_hdfs(df, subdir: str, mode: str = "overwrite"):
    """将 Spark DataFrame 保存到 HDFS"""
    hdfs_path = f"{HDFS_NAMENODE}{HDFS_BASE_DIR}/spark_output/{subdir}"
    try:
        df.coalesce(1).write.mode(mode).option("header", "true").csv(hdfs_path)
        print(f"  ✓ 已保存到 HDFS: {hdfs_path}")
        return True
    except Exception as e:
        print(f"  ! 保存到 HDFS 失败: {e}")
        return False


# =========================================================
# MySQL 数据读取（备选）
# =========================================================
def load_comments_df():
    """从 MySQL 读取评论数据到 Spark DataFrame"""
    spark = _get_spark()
    props = _get_jdbc_props()
    df = (
        spark.read.format("jdbc")
        .option("url", props["url"])
        .option("dbtable", "comments")
        .option("user", props["user"])
        .option("password", props["password"])
        .option("driver", props["driver"])
        .load()
    )
    return df


def load_brands_df():
    """从 MySQL 读取品牌数据到 Spark DataFrame"""
    spark = _get_spark()
    props = _get_jdbc_props()
    df = (
        spark.read.format("jdbc")
        .option("url", props["url"])
        .option("dbtable", "brands")
        .option("user", props["user"])
        .option("password", props["password"])
        .option("driver", props["driver"])
        .load()
    )
    return df


# =========================================================
# Spark SQL 分析
# =========================================================
def brand_sentiment_stats():
    """各品牌情感统计 — Spark SQL 实现"""
    spark = _get_spark()
    comments_df = load_comments_df()
    brands_df = load_brands_df()

    comments_df.createOrReplaceTempView("comments")
    brands_df.createOrReplaceTempView("brands")

    result = spark.sql("""
        SELECT
            b.name AS brand_name,
            COUNT(c.id) AS comment_count,
            ROUND(AVG(c.sentiment_score), 4) AS avg_sentiment,
            SUM(CASE WHEN c.sentiment_label = '正向' THEN 1 ELSE 0 END) AS pos_count,
            SUM(CASE WHEN c.sentiment_label = '中性' THEN 1 ELSE 0 END) AS mid_count,
            SUM(CASE WHEN c.sentiment_label = '负向' THEN 1 ELSE 0 END) AS neg_count,
            ROUND(SUM(CASE WHEN c.sentiment_label = '正向' THEN 1 ELSE 0 END) * 100.0
                  / COUNT(c.id), 1) AS pos_rate
        FROM comments c
        JOIN brands b ON c.brand_id = b.id
        GROUP BY b.name
        ORDER BY avg_sentiment DESC
    """)
    return result


def daily_trend_stats():
    """按天统计情感趋势 — Spark SQL 实现"""
    spark = _get_spark()
    comments_df = load_comments_df()
    brands_df = load_brands_df()

    comments_df.createOrReplaceTempView("comments")
    brands_df.createOrReplaceTempView("brands")

    result = spark.sql("""
        SELECT
            b.name AS brand_name,
            DATE(c.comment_time) AS date,
            COUNT(c.id) AS count,
            ROUND(AVG(c.sentiment_score), 4) AS avg_score
        FROM comments c
        JOIN brands b ON c.brand_id = b.id
        WHERE c.comment_time IS NOT NULL
        GROUP BY b.name, DATE(c.comment_time)
        ORDER BY b.name, date
    """)
    return result


def score_distribution_stats():
    """评分分布统计 — Spark SQL"""
    spark = _get_spark()
    comments_df = load_comments_df()
    brands_df = load_brands_df()

    comments_df.createOrReplaceTempView("comments")
    brands_df.createOrReplaceTempView("brands")

    result = spark.sql("""
        SELECT
            b.name AS brand_name,
            c.score AS rating,
            COUNT(*) AS count
        FROM comments c
        JOIN brands b ON c.brand_id = b.id
        GROUP BY b.name, c.score
        ORDER BY b.name, c.score
    """)
    return result


def spark_batch_sentiment(texts_rdd):
    """使用 Spark UDF 进行分布式情感分析"""
    from pyspark.sql.functions import udf
    from pyspark.sql.types import FloatType, StringType
    from snownlp import SnowNLP

    @udf(returnType=FloatType())
    def snownlp_score_udf(text):
        if not text:
            return 0.5
        try:
            return float(SnowNLP(text).sentiments)
        except Exception:
            return 0.5

    @udf(returnType=StringType())
    def sentiment_label_udf(score):
        if score is None:
            return "中性"
        if score >= 0.65:
            return "正向"
        if score <= 0.35:
            return "负向"
        return "中性"

    return snownlp_score_udf, sentiment_label_udf


def stop_spark():
    """停止 SparkSession"""
    global _spark_session
    if _spark_session:
        _spark_session.stop()
        _spark_session = None

