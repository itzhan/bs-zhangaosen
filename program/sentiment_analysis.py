"""京东评论第二步：分词与情感分析

读取评论数据 -> 文本清洗 -> 分词/关键词提取 -> SnowNLP情感打分 -> 保存结果与概览。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Tuple

import jieba
import jieba.analyse
import pandas as pd
from snownlp import SnowNLP


# 简单停用词表，可按需扩充
STOPWORDS = {
    "的",
    "了",
    "和",
    "是",
    "就",
    "都",
    "而",
    "及",
    "与",
    "这",
    "那",
    "但",
    "因为",
    "所以",
    "如果",
    "非常",
    "比较",
    "还是",
    "已经",
    "可以",
    "没有",
    "商品",
    "东西",
    "快递",
    "物流",
    "包装",
    "价格",
    "质量",
    "感觉",
    "真的",
    "还是",
    "就是",
}


def ensure_output_dir(subdir: str | None = None) -> Path:
    """确保输出目录存在，返回 Path 对象。"""
    base = Path("output")
    if subdir:
        base = base / subdir
    base.mkdir(parents=True, exist_ok=True)
    return base


def clean_comment(text: str) -> str:
    """基础清洗：去除URL、表情符、重复空格，仅保留中英文及数字。"""
    if not isinstance(text, str):
        text = "" if pd.isna(text) else str(text)
    text = re.sub(r"http[s]?://\S+", " ", text)  # 去掉链接
    text = re.sub(r"[\u2600-\u27BF]", " ", text)  # 去掉常见表情符
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text)  # 保留中英文和数字
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    """分词并过滤停用词、单字。"""
    words = jieba.lcut(text)
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def extract_keywords(text: str, top_k: int = 5) -> List[str]:
    """基于TF-IDF提取关键词。"""
    return jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)


def sentiment_score(text: str) -> float:
    """SnowNLP情感得分，异常时返回0.5。"""
    try:
        return float(SnowNLP(text).sentiments)
    except Exception:
        return 0.5


def sentiment_label(score: float) -> str:
    """根据得分区间划分标签。"""
    if score >= 0.65:
        return "正向"
    if score <= 0.35:
        return "负向"
    return "中性"


def load_dataframe(path: Path) -> pd.DataFrame:
    """根据扩展名读取 csv 或 xlsx。"""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"不支持的文件类型: {path}")


def analyze_single(
    input_path: Path,
    output_dir: Path,
) -> Tuple[pd.DataFrame, dict, Path]:
    """处理单个文件，返回结果、概要、输出路径。"""
    if not input_path.exists():
        raise FileNotFoundError(f"找不到输入文件: {input_path}")

    df = load_dataframe(input_path)
    if "评论内容" not in df.columns:
        raise ValueError(f"{input_path.name} 缺少“评论内容”列，无法做情感分析。")

    base_cols = [
        "评论ID",
        "评论时间",
        "评论内容",
        "评论得分",
        "用户昵称",
        "商品_颜色",
        "商品_型号",
    ]
    keep_cols = [c for c in base_cols if c in df.columns]
    df = df[keep_cols].copy()

    df["清洗后评论"] = df["评论内容"].apply(clean_comment)
    df = df[df["清洗后评论"].str.len() > 0]

    if df.empty:
        raise ValueError(f"{input_path.name} 经过清洗后没有可用评论。")

    df["分词"] = df["清洗后评论"].apply(tokenize)
    df["关键词"] = df["清洗后评论"].apply(extract_keywords)
    df["情感得分"] = df["清洗后评论"].apply(sentiment_score)
    df["情感标签"] = df["情感得分"].apply(sentiment_label)

    summary = {
        "文件名": input_path.name,
        "总评论数": int(len(df)),
        "平均情感得分": round(df["情感得分"].mean(), 4),
        "情感分布": df["情感标签"].value_counts().to_dict(),
        "高频关键词": (
            pd.Series(jieba.lcut(" ".join(df["清洗后评论"].tolist())))
            .pipe(lambda s: s[s.str.len() > 1])
            .pipe(lambda s: s[~s.isin(STOPWORDS)])
            .value_counts()
            .head(30)
            .to_dict()
        ),
    }

    output_path = output_dir / f"{input_path.stem}输出.csv"
    summary_path = output_dir / f"{input_path.stem}输出_summary.json"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"{input_path.name} 情感分析完成 -> {output_path.name}")
    print(f"情感分布: {summary['情感分布']}")
    return df, summary, output_path


def analyze_folder(
    folder: str | Path = "评论",
    output_subdir: str = "sentiment_batch",
) -> list[dict]:
    """循环处理指定目录下的 csv/xlsx 文件。"""
    folder_path = Path(folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"找不到评论文件夹: {folder_path}")

    files = sorted(
        [
            p
            for p in folder_path.iterdir()
            if p.suffix.lower() in {".csv", ".xlsx", ".xls"} and p.is_file()
        ]
    )
    if not files:
        raise ValueError("评论文件夹中没有 csv 或 xlsx 文件。")

    output_dir = ensure_output_dir(output_subdir)
    results = []
    for fp in files:
        try:
            _, summary, out_path = analyze_single(fp, output_dir)
            results.append({"文件": fp.name, "输出": out_path.name, **summary})
        except Exception as e:
            print(f"处理 {fp.name} 时出错: {e}")
    return results


if __name__ == "__main__":
    analyze_folder()
