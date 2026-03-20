"""情感分析服务 — 保留原有 jieba + SnowNLP 核心逻辑"""

from __future__ import annotations
import re
from typing import List

import jieba
import jieba.analyse
import pandas as pd
from snownlp import SnowNLP


STOPWORDS = {
    "的", "了", "和", "是", "就", "都", "而", "及", "与", "这", "那", "但",
    "因为", "所以", "如果", "非常", "比较", "还是", "已经", "可以", "没有",
    "商品", "东西", "快递", "物流", "包装", "价格", "质量", "感觉",
    "真的", "就是", "一个", "什么", "不错", "很好", "挺好",
}


def clean_text(text: str) -> str:
    """基础清洗：去除URL、表情符、特殊字符"""
    if not isinstance(text, str):
        return ''
    text = re.sub(r'http[s]?://\S+', ' ', text)
    text = re.sub(r'[\u2600-\u27BF]', ' ', text)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


def tokenize(text: str) -> List[str]:
    """分词并过滤停用词、单字"""
    words = jieba.lcut(text)
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def extract_keywords(text: str, top_k: int = 8) -> List[str]:
    """基于TF-IDF提取关键词"""
    return jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)


def sentiment_score(text: str) -> float:
    """SnowNLP情感得分 (0~1)"""
    try:
        return round(float(SnowNLP(text).sentiments), 4)
    except Exception:
        return 0.5


def sentiment_label(score: float) -> str:
    """根据得分区间划分标签"""
    if score >= 0.65:
        return '正向'
    if score <= 0.35:
        return '负向'
    return '中性'


def analyze_text(text: str) -> dict:
    """对单条文本做完整分析，返回结果字典"""
    cleaned = clean_text(text)
    if not cleaned:
        return {
            'cleaned_content': '',
            'sentiment_score': 0.5,
            'sentiment_label': '中性',
            'keywords': [],
        }
    score = sentiment_score(cleaned)
    return {
        'cleaned_content': cleaned,
        'sentiment_score': score,
        'sentiment_label': sentiment_label(score),
        'keywords': extract_keywords(cleaned),
    }


def batch_analyze(texts: List[str]) -> List[dict]:
    """批量分析"""
    return [analyze_text(t) for t in texts]
