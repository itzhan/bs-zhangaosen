#!/usr/bin/env python3
"""Spark 数据分析脚本 — 独立可运行

使用 PySpark 对京东评论数据进行分布式分析，输出分析报告到 output/spark_results/。

用法:
    python spark_analysis.py
    python spark_analysis.py --output output/spark_results
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(output_dir: str = "output/spark_results"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  Spark 数据分析报告生成")
    print("=" * 60)

    from app.services.spark_processor import (
        brand_sentiment_stats,
        daily_trend_stats,
        score_distribution_stats,
        save_to_hdfs,
        stop_spark,
    )

    # 1. 品牌情感统计
    print("\n[1/4] 品牌情感统计分析 (Spark SQL)...")
    brand_df = brand_sentiment_stats()
    brand_df.show(truncate=False)
    brand_data = [row.asDict() for row in brand_df.collect()]
    with open(out / "brand_sentiment.json", "w", encoding="utf-8") as f:
        json.dump(brand_data, f, ensure_ascii=False, indent=2, default=str)
    brand_df.toPandas().to_csv(out / "brand_sentiment.csv", index=False, encoding="utf-8-sig")
    print(f"  ✓ 已保存: brand_sentiment.json / .csv")

    # 2. 时间趋势
    print("\n[2/4] 每日情感趋势分析 (Spark SQL)...")
    trend_df = daily_trend_stats()
    trend_df.show(20, truncate=False)
    trend_data = [row.asDict() for row in trend_df.collect()]
    with open(out / "daily_trend.json", "w", encoding="utf-8") as f:
        json.dump(trend_data, f, ensure_ascii=False, indent=2, default=str)
    trend_df.toPandas().to_csv(out / "daily_trend.csv", index=False, encoding="utf-8-sig")
    print(f"  ✓ 已保存: daily_trend.json / .csv")

    # 3. 评分分布
    print("\n[3/4] 评分分布统计 (Spark SQL)...")
    score_df = score_distribution_stats()
    score_df.show(truncate=False)
    score_data = [row.asDict() for row in score_df.collect()]
    with open(out / "score_distribution.json", "w", encoding="utf-8") as f:
        json.dump(score_data, f, ensure_ascii=False, indent=2, default=str)
    score_df.toPandas().to_csv(out / "score_distribution.csv", index=False, encoding="utf-8-sig")
    print(f"  ✓ 已保存: score_distribution.json / .csv")

    # 4. 将分析结果写入 HDFS
    print("\n[4/4] 写入分析结果到 HDFS...")
    save_to_hdfs(brand_df, "brand_sentiment")
    save_to_hdfs(trend_df, "daily_trend")
    save_to_hdfs(score_df, "score_distribution")

    # 生成汇总报告
    summary = {
        "品牌数": len(brand_data),
        "总评论数": sum(b.get("comment_count", 0) for b in brand_data),
        "品牌排名(按情感得分)": [
            {"品牌": b["brand_name"], "平均情感": b["avg_sentiment"], "正向率": f"{b['pos_rate']}%"}
            for b in brand_data
        ],
    }
    with open(out / "analysis_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  ✓ 所有分析结果已保存到: {out}/ 和 HDFS")
    print(f"{'=' * 60}")

    stop_spark()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spark 分布式数据分析")
    parser.add_argument("--output", default="output/spark_results", help="输出目录")
    args = parser.parse_args()
    main(args.output)
