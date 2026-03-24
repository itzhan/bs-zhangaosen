#!/usr/bin/env python3
"""LSTM 情感分类模型训练脚本

用法:
    python train_lstm.py                        # 从数据库读取训练数据
    python train_lstm.py --source csv            # 从 output/sentiment_batch/*.csv 读取
    python train_lstm.py --epochs 20 --lr 0.001  # 自定义超参
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Tuple

import jieba
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.lstm_model import (
    LABEL_MAP,
    LABEL_INV,
    MODEL_DIR,
    MODEL_PATH,
    VOCAB_PATH,
    CommentDataset,
    LSTMSentimentModel,
    Vocabulary,
)


# ========== 停用词 ==========
STOPWORDS = {
    "的", "了", "和", "是", "就", "都", "而", "及", "与", "这", "那", "但",
    "因为", "所以", "如果", "非常", "比较", "还是", "已经", "可以", "没有",
    "商品", "东西", "快递", "物流", "包装", "价格", "质量", "感觉",
    "真的", "就是", "一个", "什么", "不错", "很好", "挺好",
}


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"http[s]?://\S+", " ", text)
    text = re.sub(r"[\u2600-\u27BF]", " ", text)
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    words = jieba.lcut(text)
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


# =========================================================
# 数据加载
# =========================================================
def load_from_database() -> pd.DataFrame:
    """从 MySQL 读取已有情感标注的评论数据"""
    from app import create_app, db
    from app.models.comment import Comment

    app = create_app()
    with app.app_context():
        comments = Comment.query.filter(
            Comment.cleaned_content != "",
            Comment.sentiment_label.isnot(None),
        ).all()
        data = []
        for c in comments:
            data.append({
                "text": c.cleaned_content or c.content,
                "label": c.sentiment_label,
            })
    return pd.DataFrame(data)


def load_from_csv() -> pd.DataFrame:
    """从 CSV 文件读取数据"""
    data_dir = Path("output/sentiment_batch")
    if not data_dir.exists():
        data_dir = Path("评论")
    if not data_dir.exists():
        raise FileNotFoundError("找不到数据目录: output/sentiment_batch 或 评论/")

    frames = []
    for fp in data_dir.iterdir():
        if fp.suffix.lower() not in {".csv", ".xlsx"} or "summary" in fp.name.lower():
            continue
        try:
            df = pd.read_csv(fp, encoding="utf-8-sig") if fp.suffix == ".csv" else pd.read_excel(fp)
            if "评论内容" in df.columns and "情感标签" in df.columns:
                frames.append(df[["评论内容", "情感标签"]].rename(
                    columns={"评论内容": "text", "情感标签": "label"}
                ))
        except Exception as e:
            print(f"  跳过 {fp.name}: {e}")
    if not frames:
        raise ValueError("未找到包含 评论内容 和 情感标签 列的数据文件")
    return pd.concat(frames, ignore_index=True)


# =========================================================
# 训练
# =========================================================
def train(
    source: str = "db",
    epochs: int = 15,
    batch_size: int = 64,
    lr: float = 0.001,
    embed_dim: int = 128,
    hidden_dim: int = 128,
    num_layers: int = 2,
    max_len: int = 128,
    min_freq: int = 2,
    test_size: float = 0.2,
):
    print("=" * 60)
    print("  LSTM 情感分类模型训练")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/6] 加载数据...")
    if source == "db":
        df = load_from_database()
    else:
        df = load_from_csv()

    df = df.dropna(subset=["text", "label"])
    df = df[df["label"].isin(LABEL_MAP.keys())]
    print(f"  总样本数: {len(df)}")
    print(f"  标签分布: {dict(df['label'].value_counts())}")

    if len(df) < 50:
        print("[!] 样本过少（<50），无法训练。请先采集更多评论数据。")
        return

    # 2. 分词
    print("\n[2/6] 文本分词...")
    df["tokens"] = df["text"].apply(lambda x: tokenize(clean_text(str(x))))
    df = df[df["tokens"].map(len) > 0]

    # 3. 构建词表
    print("\n[3/6] 构建词表...")
    vocab = Vocabulary(min_freq=min_freq)
    vocab.build(df["tokens"].tolist())
    print(f"  词表大小: {len(vocab)}")

    # 编码
    df["ids"] = df["tokens"].apply(vocab.encode)
    df["label_id"] = df["label"].map(LABEL_MAP)

    # 4. 划分数据集
    print("\n[4/6] 划分训练/测试集...")
    X_train, X_test, y_train, y_test = train_test_split(
        df["ids"].tolist(), df["label_id"].tolist(),
        test_size=test_size, random_state=42, stratify=df["label_id"].tolist(),
    )
    print(f"  训练集: {len(X_train)}, 测试集: {len(X_test)}")

    train_ds = CommentDataset(X_train, y_train, max_len)
    test_ds = CommentDataset(X_test, y_test, max_len)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=batch_size)

    # 5. 训练
    print(f"\n[5/6] 开始训练 ({epochs} epochs)...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  设备: {device}")

    model = LSTMSentimentModel(
        vocab_size=len(vocab),
        embed_dim=embed_dim,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
    ).to(device)

    # 类别权重（处理不平衡）
    label_counts = Counter(y_train)
    total = sum(label_counts.values())
    weights = torch.tensor(
        [total / (len(label_counts) * label_counts.get(i, 1)) for i in range(3)],
        dtype=torch.float32,
    ).to(device)

    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.5)

    history = {"train_loss": [], "train_acc": [], "test_acc": []}

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, correct, total_samples = 0, 0, 0

        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            total_loss += loss.item() * labels.size(0)
            correct += (outputs.argmax(1) == labels).sum().item()
            total_samples += labels.size(0)

        scheduler.step()

        train_loss = total_loss / total_samples
        train_acc = correct / total_samples

        # 测试集评估
        model.eval()
        test_correct, test_total = 0, 0
        with torch.no_grad():
            for inputs, labels in test_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                test_correct += (outputs.argmax(1) == labels).sum().item()
                test_total += labels.size(0)
        test_acc = test_correct / test_total

        history["train_loss"].append(round(train_loss, 4))
        history["train_acc"].append(round(train_acc, 4))
        history["test_acc"].append(round(test_acc, 4))

        print(f"  Epoch {epoch:02d}/{epochs} | "
              f"Loss: {train_loss:.4f} | "
              f"Train Acc: {train_acc:.4f} | "
              f"Test Acc: {test_acc:.4f}")

    # 6. 评估 & 保存
    print(f"\n[6/6] 模型评估与保存...")

    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for inputs, labels in test_loader:
            inputs = inputs.to(device)
            outputs = model(inputs)
            all_preds.extend(outputs.argmax(1).cpu().tolist())
            all_labels.extend(labels.tolist())

    target_names = [LABEL_INV[i] for i in range(3)]
    report = classification_report(all_labels, all_preds, target_names=target_names)
    cm = confusion_matrix(all_labels, all_preds)

    print("\n  分类报告:")
    print(report)
    print("  混淆矩阵:")
    print(f"  {cm}")

    # 保存模型
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "embed_dim": embed_dim,
        "hidden_dim": hidden_dim,
        "num_layers": num_layers,
        "vocab_size": len(vocab),
        "history": history,
    }, MODEL_PATH)
    vocab.save(VOCAB_PATH)
    print(f"\n  ✓ 模型已保存: {MODEL_PATH}")
    print(f"  ✓ 词表已保存: {VOCAB_PATH}")

    # 保存训练报告
    report_path = MODEL_DIR / "training_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "epochs": epochs,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "vocab_size": len(vocab),
            "final_train_acc": history["train_acc"][-1],
            "final_test_acc": history["test_acc"][-1],
            "classification_report": report,
            "history": history,
        }, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 训练报告: {report_path}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="训练 LSTM 情感分类模型")
    parser.add_argument("--source", choices=["db", "csv"], default="db",
                        help="数据来源: db=数据库, csv=CSV文件")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--embed-dim", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=128)
    args = parser.parse_args()

    train(
        source=args.source,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        embed_dim=args.embed_dim,
        hidden_dim=args.hidden_dim,
    )
