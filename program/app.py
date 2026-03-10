"""Flask + Bootstrap + ECharts 可视化服务

默认读取 output/sentiment_batch 下的情感分析结果；
若目录不存在或为空，会回退读取 评论/ 目录下的 csv/xlsx。
每个文件生成一组图表，可通过下拉框切换。
运行：FLASK_APP=app.py flask run
"""

from __future__ import annotations

import ast
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
from flask import Flask, render_template_string, request
from pyecharts import options as opts
from pyecharts.charts import Bar, Line, Pie, WordCloud
from pyecharts.globals import CurrentConfig, ThemeType

# 使用线上 ECharts 静态资源
CurrentConfig.ONLINE_HOST = "https://assets.pyecharts.org/assets/"


app = Flask(__name__)

DATA_DIR_PRI = Path("output/sentiment_batch")
DATA_DIR_FALLBACK = Path("评论")


def find_files() -> List[Path]:
    """按优先级查找数据文件，支持 csv/xlsx/xls。"""
    candidates: List[Path] = []
    for base in (DATA_DIR_PRI, DATA_DIR_FALLBACK):
        if base.exists():
            candidates.extend(
                p
                for p in base.iterdir()
                if p.is_file() and p.suffix.lower() in {".csv", ".xlsx", ".xls"}
            )
        if candidates:
            break
    return sorted(candidates)


def read_frame(path: Path) -> pd.DataFrame:
    """根据扩展名读取 DataFrame。"""
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.read_excel(path)


def parse_keywords(cell) -> List[str]:
    """解析关键词列：可能是字符串化的列表，也可能是空值。"""
    if pd.isna(cell):
        return []
    if isinstance(cell, list):
        return cell
    text = str(cell).strip()
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    return [w for w in text.replace("[", "").replace("]", "").replace("'", "").split(",") if w.strip()]


def build_pie_sentiment(df: pd.DataFrame, title: str) -> Pie:
    counts = df["情感标签"].value_counts().to_dict()
    data = list(counts.items()) or [("无数据", 1)]
    pie = (
        Pie(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="420px", height="320px"))
        .add("", data, radius=["30%", "60%"])
        .set_global_opts(title_opts=opts.TitleOpts(title=title))
        .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)"))
    )
    return pie


def build_line_trend(df: pd.DataFrame, title: str) -> Line:
    if "评论时间" not in df.columns:
        return Line().add_xaxis([]).add_yaxis("情感得分", [])
    time_series = df.copy()
    time_series["评论时间"] = pd.to_datetime(time_series["评论时间"], errors="coerce")
    time_series = time_series.dropna(subset=["评论时间"])
    if time_series.empty:
        return Line().add_xaxis([]).add_yaxis("情感得分", [])
    grp = time_series.resample("D", on="评论时间")["情感得分"].mean().dropna()
    x = [d.strftime("%m-%d") for d in grp.index]
    y = grp.round(3).tolist()
    line = (
        Line(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="680px", height="340px"))
        .add_xaxis(x)
        .add_yaxis("平均情感得分", y, is_smooth=True)
        .set_global_opts(title_opts=opts.TitleOpts(title=title), yaxis_opts=opts.AxisOpts(min_=0, max_=1))
    )
    return line


def build_bar_keywords(df: pd.DataFrame, title: str, topk: int = 15) -> Bar:
    keyword_series = (
        df["关键词"]
        .dropna()
        .apply(parse_keywords)
        .explode()
        .dropna()
        .astype(str)
    )
    stats = keyword_series.value_counts().head(topk)
    bar = (
        Bar(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="680px", height="340px"))
        .add_xaxis(stats.index.tolist())
        .add_yaxis("出现次数", stats.tolist(), category_gap="40%")
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title),
            xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=35)),
        )
    )
    return bar


def build_wordcloud(df: pd.DataFrame, title: str) -> WordCloud:
    keyword_series = (
        df["关键词"]
        .dropna()
        .apply(parse_keywords)
        .explode()
        .dropna()
        .astype(str)
    )
    stats = keyword_series.value_counts().head(80)
    data = list(zip(stats.index.tolist(), stats.tolist()))
    wc = (
        WordCloud(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="680px", height="340px"))
        .add(series_name="关键词", data_pair=data, word_size_range=[15, 60])
        .set_global_opts(title_opts=opts.TitleOpts(title=title))
    )
    return wc


def get_datasets() -> Dict[str, pd.DataFrame]:
    files = find_files()
    datasets: Dict[str, pd.DataFrame] = {}
    for path in files:
        try:
            df = read_frame(path)
            if "情感得分" not in df.columns or "情感标签" not in df.columns:
                # 没有情感列时跳过
                print(f"跳过 {path.name}：缺少情感分析列")
                continue
            datasets[path.name] = df
        except Exception as exc:  # 保证其他文件继续
            print(f"读取 {path} 失败: {exc}")
    return datasets


TEMPLATE = """
<!doctype html>
<html lang="zh-cn">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  {% for js in js_list %}
    <script src="{{ host }}{{ js }}"></script>
  {% endfor %}
  <title>京东评论可视化</title>
  <style>
    body {
      padding: 32px;
      background: #f4f6fb;
      min-height: 100vh;
    }
    .page-shell {
      background: #fff;
      border-radius: 1rem;
      padding: 2rem 2.5rem;
      box-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);
    }
    .metrics-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      margin-bottom: 1.75rem;
    }
    .metric-card {
      flex: 1 1 160px;
      min-width: 160px;
      border-radius: 0.75rem;
      padding: 1rem 1.25rem;
      background: #ffffff;
      box-shadow: 0 12px 24px rgba(15, 23, 42, 0.05);
    }
    .metric-card .label {
      color: #6c757d;
      letter-spacing: 0.04em;
      font-size: 0.8rem;
    }
    .metric-card .value {
      font-size: 1.8rem;
      font-weight: 600;
      color: #0f172a;
    }
    .metric-card .sub {
      font-weight: 500;
      color: #475569;
    }
    .chart-panel {
      display: grid;
      gap: 1.25rem;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      align-items: stretch;
    }
    .chart-box {
      border-radius: 1rem;
      padding: 1.25rem;
      background: #ffffff;
      box-shadow: 0 18px 36px rgba(15, 23, 42, 0.09);
    }
    .chart-box .echarts {
      min-height: 320px;
    }
    @media (min-width: 992px) {
      body {
        padding: 40px;
      }
      .chart-panel {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
  </style>
</head>
<body>
  <div class="container-fluid">
    <div class="page-shell">
      <div class="d-flex align-items-center mb-3">
        <h4 class="me-3 mb-0">评论情感分析可视化</h4>
        <form method="get" class="d-flex align-items-center">
          <label class="me-2">选择文件：</label>
          <select name="file" class="form-select form-select-sm" onchange="this.form.submit()">
            {% for f in files %}
              <option value="{{ f }}" {% if f == current %}selected{% endif %}>{{ f }}</option>
            {% endfor %}
          </select>
        </form>
      </div>
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="label">总评论</div>
          <div class="value">{{ metrics.total }}</div>
        </div>
        <div class="metric-card">
          <div class="label">平均情感得分</div>
          <div class="value">{{ metrics.mean_score }}</div>
        </div>
        <div class="metric-card">
          <div class="label">情感分布</div>
          <div class="sub">正向 {{ metrics.pos }} / 中性 {{ metrics.mid }} / 负向 {{ metrics.neg }}</div>
        </div>
        <div class="metric-card">
          <div class="label">更新时间</div>
          <div class="sub">{{ metrics.updated }}</div>
        </div>
      </div>
      <div class="chart-panel">
        <div class="chart-box">{{ pie|safe }}</div>
        <div class="chart-box">{{ line|safe }}</div>
        <div class="chart-box">{{ bar|safe }}</div>
        <div class="chart-box">{{ wordcloud|safe }}</div>
      </div>
    </div>
  </div>
</body>
</html>
"""


@app.route("/")
def index():
    datasets = get_datasets()
    if not datasets:
        return "未找到可用的情感分析结果，请先运行 sentiment_analysis.py", 400

    files = list(datasets.keys())
    current = request.args.get("file", files[0])
    if current not in datasets:
        current = files[0]
    df = datasets[current]

    # 指标
    total = len(df)
    mean_score = round(df["情感得分"].mean(), 4)
    dist = df["情感标签"].value_counts()
    pos = int(dist.get("正向", 0))
    mid = int(dist.get("中性", 0))
    neg = int(dist.get("负向", 0))

    pie = build_pie_sentiment(df, "情感占比")
    line = build_line_trend(df, "情感得分时间趋势")
    bar = build_bar_keywords(df, "关键词 TopN")
    wc = build_wordcloud(df, "关键词词云")

    # 收集 JS 依赖，兼容不同版本的 pyecharts
    def deps(chart):
        if hasattr(chart, "get_js_dependencies"):
            try:
                return chart.get_js_dependencies()
            except Exception:
                pass
        if hasattr(chart, "js_dependencies"):
            try:
                return list(chart.js_dependencies)
            except Exception:
                return []
        return []

    js_list = list({js for chart in (pie, line, bar, wc) for js in deps(chart)})

    return render_template_string(
        TEMPLATE,
        files=files,
        current=current,
        metrics={
            "total": total,
            "mean_score": mean_score,
            "pos": pos,
            "mid": mid,
            "neg": neg,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        pie=pie.render_embed(),
        line=line.render_embed(),
        bar=bar.render_embed(),
        wordcloud=wc.render_embed(),
        js_list=js_list,
        host=CurrentConfig.ONLINE_HOST,
    )


if __name__ == "__main__":
    # 方便直接运行调试
    app.run(debug=True)
