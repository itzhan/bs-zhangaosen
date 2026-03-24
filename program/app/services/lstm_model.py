"""LSTM 情感分类模型 — 基于 PyTorch

提供双向 LSTM + Attention 的情感三分类器（正向/中性/负向），
与 SnowNLP 词典法形成对比，满足论文"两种方法对比分析"的要求。
"""

from __future__ import annotations

import os
import json
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import jieba
import numpy as np

# ---- PyTorch ----
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# 标签映射
LABEL_MAP = {"正向": 2, "中性": 1, "负向": 0}
LABEL_INV = {v: k for k, v in LABEL_MAP.items()}
NUM_CLASSES = 3

# 默认模型存储路径
MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "lstm_sentiment.pt"
VOCAB_PATH = MODEL_DIR / "vocab.pkl"


# =========================================================
# 词表
# =========================================================
class Vocabulary:
    """词 -> 索引映射，支持序列化。"""

    PAD, UNK = "<PAD>", "<UNK>"

    def __init__(self, min_freq: int = 2):
        self.word2idx: dict[str, int] = {self.PAD: 0, self.UNK: 1}
        self.idx2word: dict[int, str] = {0: self.PAD, 1: self.UNK}
        self.freq: dict[str, int] = {}
        self.min_freq = min_freq

    def build(self, tokenized_texts: List[List[str]]):
        for tokens in tokenized_texts:
            for w in tokens:
                self.freq[w] = self.freq.get(w, 0) + 1
        idx = len(self.word2idx)
        for w, f in self.freq.items():
            if f >= self.min_freq and w not in self.word2idx:
                self.word2idx[w] = idx
                self.idx2word[idx] = w
                idx += 1

    def encode(self, tokens: List[str]) -> List[int]:
        return [self.word2idx.get(w, 1) for w in tokens]

    def save(self, path: str | Path):
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: str | Path) -> "Vocabulary":
        with open(path, "rb") as f:
            return pickle.load(f)

    def __len__(self):
        return len(self.word2idx)


# =========================================================
# Dataset
# =========================================================
class CommentDataset(Dataset):
    def __init__(self, texts: List[List[int]], labels: List[int], max_len: int = 128):
        self.texts = texts
        self.labels = labels
        self.max_len = max_len

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        seq = self.texts[idx][: self.max_len]
        padded = seq + [0] * (self.max_len - len(seq))
        return (
            torch.tensor(padded, dtype=torch.long),
            torch.tensor(self.labels[idx], dtype=torch.long),
        )


# =========================================================
# LSTM + Attention 模型
# =========================================================
class LSTMSentimentModel(nn.Module):
    """双向 LSTM + Self-Attention 情感分类器"""

    def __init__(
        self,
        vocab_size: int,
        embed_dim: int = 128,
        hidden_dim: int = 128,
        num_layers: int = 2,
        num_classes: int = NUM_CLASSES,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(
            embed_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.attention = nn.Linear(hidden_dim * 2, 1)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim * 2, num_classes)

    def forward(self, x):
        # x: (batch, seq_len)
        emb = self.embedding(x)  # (batch, seq_len, embed_dim)
        lstm_out, _ = self.lstm(emb)  # (batch, seq_len, hidden*2)

        # Attention
        attn_weights = torch.softmax(self.attention(lstm_out), dim=1)  # (batch, seq, 1)
        context = (lstm_out * attn_weights).sum(dim=1)  # (batch, hidden*2)
        context = self.dropout(context)
        out = self.fc(context)
        return out


# =========================================================
# 推理接口
# =========================================================
_model: Optional[LSTMSentimentModel] = None
_vocab: Optional[Vocabulary] = None


def _ensure_loaded():
    """懒加载模型和词表"""
    global _model, _vocab
    if _model is not None:
        return True
    if not MODEL_PATH.exists() or not VOCAB_PATH.exists():
        return False
    _vocab = Vocabulary.load(VOCAB_PATH)
    device = torch.device("cpu")
    checkpoint = torch.load(MODEL_PATH, map_location=device, weights_only=False)
    _model = LSTMSentimentModel(
        vocab_size=len(_vocab),
        embed_dim=checkpoint.get("embed_dim", 128),
        hidden_dim=checkpoint.get("hidden_dim", 128),
        num_layers=checkpoint.get("num_layers", 2),
    )
    _model.load_state_dict(checkpoint["state_dict"])
    _model.eval()
    return True


def predict(text: str, max_len: int = 128) -> dict:
    """
    LSTM 预测单条文本的情感。

    Returns:
        {'label': '正向', 'score': 0.91, 'probs': [0.03, 0.06, 0.91]}
        如果模型未加载则返回 None
    """
    if not _ensure_loaded():
        return None

    tokens = list(jieba.lcut(text))
    ids = _vocab.encode(tokens)[:max_len]
    padded = ids + [0] * (max_len - len(ids))
    tensor = torch.tensor([padded], dtype=torch.long)

    with torch.no_grad():
        logits = _model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze().tolist()

    pred_idx = int(np.argmax(probs))
    return {
        "label": LABEL_INV[pred_idx],
        "score": round(probs[pred_idx], 4),
        "probs": [round(p, 4) for p in probs],  # [负向, 中性, 正向]
    }


def predict_batch(texts: List[str], max_len: int = 128) -> List[dict]:
    """批量预测"""
    if not _ensure_loaded():
        return [None] * len(texts)
    return [predict(t, max_len) for t in texts]
