"""情感分析服务 — SnowNLP 词典法 + LSTM 深度学习双引擎

同时保留两种方法的结果，供论文对比分析。
LSTM 模型可选：若模型文件不存在则仅返回 SnowNLP 结果。
"""

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


def _lstm_predict(text: str) -> dict | None:
    """尝试使用 LSTM 模型预测，模型未加载则返回 None"""
    try:
        from app.services.lstm_model import predict
        return predict(text)
    except Exception:
        return None


def analyze_text(text: str) -> dict:
    """对单条文本做完整分析（SnowNLP + LSTM 双引擎）

    返回字段:
        - cleaned_content: 清洗后文本
        - snownlp_score: SnowNLP 情感得分 (0~1)
        - snownlp_label: SnowNLP 情感标签
        - lstm_score: LSTM 预测置信度 (若模型可用)
        - lstm_label: LSTM 预测标签 (若模型可用)
        - lstm_probs: LSTM 三分类概率 [负向, 中性, 正向]
        - sentiment_score: 最终采用的情感得分
        - sentiment_label: 最终采用的情感标签
        - keywords: TF-IDF 关键词列表
    """
    cleaned = clean_text(text)
    if not cleaned:
        return {
            'cleaned_content': '',
            'snownlp_score': 0.5,
            'snownlp_label': '中性',
            'lstm_score': None,
            'lstm_label': None,
            'lstm_probs': None,
            'sentiment_score': 0.5,
            'sentiment_label': '中性',
            'keywords': [],
        }

    # SnowNLP 词典法
    snow_score = sentiment_score(cleaned)
    snow_label = sentiment_label(snow_score)

    # LSTM 深度学习（可选）
    lstm_result = _lstm_predict(cleaned)
    lstm_score = lstm_result['score'] if lstm_result else None
    lstm_label = lstm_result['label'] if lstm_result else None
    lstm_probs = lstm_result['probs'] if lstm_result else None

    # 最终结果：优先使用 LSTM，回退到 SnowNLP
    final_score = lstm_score if lstm_score is not None else snow_score
    final_label = lstm_label if lstm_label is not None else snow_label

    return {
        'cleaned_content': cleaned,
        'snownlp_score': snow_score,
        'snownlp_label': snow_label,
        'lstm_score': lstm_score,
        'lstm_label': lstm_label,
        'lstm_probs': lstm_probs,
        'sentiment_score': final_score,
        'sentiment_label': final_label,
        'keywords': extract_keywords(cleaned),
    }


def batch_analyze(texts: List[str]) -> List[dict]:
    """批量分析"""
    return [analyze_text(t) for t in texts]
