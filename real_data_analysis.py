# -*- coding: utf-8 -*-
"""真实公开数据支撑下的中文评论分析（可复现脚本）。

数据来源均为公开可下载、可校验的数据文件：
    1. ChnSentiCorp_htl_all 酒店评论
    2. online_shopping_10_cats 电商评论（本脚本剔除与酒店语料重叠的“酒店”类）
    3. waimai_10k 外卖评论

脚本完成：
    - 原始文件校验（SHA256）
    - 文本清洗、去重、跨数据集去重
    - 样本规模、情感分布、文本长度、词汇丰富度统计
    - 字符二元组高频词与正负情感对数几率词分析
    - 字符二元组 + 多项式朴素贝叶斯基线（域内 / 跨域）
    - 图表与指标落盘，供分析报告引用

用法：
    python real_data_analysis.py
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import os
import random
import re
from collections import Counter, defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# --------------------------------------------------------------------------- #
# 路径与数据源登记
# --------------------------------------------------------------------------- #

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data", "real_public")
OUT_DIR = os.path.join(BASE_DIR, "output", "real_data")
FIG_DIR = os.path.join(OUT_DIR, "figures")
COLLECTED_AT = "2026-11-06 20:11"
os.makedirs(FIG_DIR, exist_ok=True)

SOURCES = [
    {
        "key": "hotel",
        "domain": "酒店评论",
        "name": "ChnSentiCorp_htl_all",
        "path": os.path.join(DATA_DIR, "ChnSentiCorp_htl_all.csv"),
        "url": "https://raw.githubusercontent.com/SophonPlus/ChineseNlpCorpus/master/datasets/ChnSentiCorp_htl_all/ChnSentiCorp_htl_all.csv",
        "sha256": "1D414B9C65CAF3A836ABDB4EFDED621968502AD3338E1A9D885AE131C86083F0",
        "text_col": "review",
        "label_col": "label",
        "cat_col": None,
        "description": "7,000 余条酒店评论，5,000 余条正向、2,000 余条负向",
    },
    {
        "key": "ecommerce",
        "domain": "电商评论",
        "name": "online_shopping_10_cats",
        "path": os.path.join(DATA_DIR, "online_shopping_10_cats", "online_shopping_10_cats.csv"),
        "url": "https://raw.githubusercontent.com/SophonPlus/ChineseNlpCorpus/master/datasets/online_shopping_10_cats/online_shopping_10_cats.zip",
        "sha256": "F6C5B724122D8547B700AC4524898EB7E28ABBEE63F798E95A8FAA408829AFDB",
        "archive_sha256": "6816DED66FDE9D0927ECBD370B5E12D0174D1ABAC35192EC014AC2A0A8D25858",
        "text_col": "review",
        "label_col": "label",
        "cat_col": "cat",
        "description": "10 个类别、6 万余条商品评论，正负向各约 3 万条",
    },
    {
        "key": "waimai",
        "domain": "外卖评论",
        "name": "waimai_10k",
        "path": os.path.join(DATA_DIR, "waimai_10k.csv"),
        "url": "https://raw.githubusercontent.com/SophonPlus/ChineseNlpCorpus/master/datasets/waimai_10k/waimai_10k.csv",
        "sha256": "B8B5C11C00B51578D35937FCA56E03A126B45381F1EA4B22893237CB377A26FE",
        "text_col": "review",
        "label_col": "label",
        "cat_col": None,
        "description": "某外卖平台用户评价，正向 4,000 条、负向约 8,000 条",
    },
]

# 项目原有模型评估结果（由 model/bert-zh-sentiment-v1/evaluation_report.txt 生成）
EVAL_REPORT = os.path.join(BASE_DIR, "model", "bert-zh-sentiment-v1", "evaluation_report.txt")

# 中文停用字符：用于过滤由功能词构成的二元组碎片
STOP_CHARS = set(
    "的了是在我有和就不人都一上也很到说要去你会着没看好自己这那他她它们个什么怎么这样那样"
    "因为所以但是如果而且还是就是只是已经可以应该能够需要觉得感觉知道时候现在比较非常特别"
    "真的其实有点一点一下一直一些一样之后之前的话东西问题情况方面我们你们他们大家这里那里"
    "哪里谁为什么怎样如何于是然后另外其中以及或者并且不过虽然然而因此从而对于关于根据通过"
    "由于为了除了甚至只有无论不管各位谢谢请让给被把从向对与及等更最太再又才只嗯哦啊"
)

HAN_RUN = re.compile(r"[\u4e00-\u9fff]+")
HTML_TAG = re.compile(r"<[^>]+>")
URL_PAT = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
SPACE_PAT = re.compile(r"\s+")

POSITIVE_WORDS = [
    "很好", "不错", "满意", "喜欢", "推荐", "舒服", "方便", "实惠", "值得", "惊喜",
    "干净", "热情", "耐心", "专业", "清晰", "流畅", "好看", "好吃", "给力", "棒",
    "赞", "优秀", "完美", "贴心", "划算", "稳定", "耐用", "漂亮", "美味", "及时",
    "礼貌", "周到", "舒适", "便宜", "新鲜", "快", "好",
]
NEGATIVE_WORDS = [
    "差劲", "失望", "垃圾", "难吃", "不新鲜", "破损", "退货", "退款", "投诉", "恶心",
    "生气", "无语", "后悔", "态度差", "敷衍", "太差", "不好", "不行", "不满意", "劣质",
    "假货", "骗", "脏", "吵", "卡顿", "漏", "慢", "贵", "臭", "硬", "咸", "油",
    "少", "缺", "延迟", "坏", "差",
]

COLORS = ["#2E5BFF", "#FF6B6B", "#FFB020", "#12B886", "#6C5CE7"]


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def clean_text(raw: str) -> str:
    """保留语义字符的清洗：去 BOM/HTML/URL，统一空白。"""
    text = (raw or "").replace("\ufeff", "").replace("\u200b", "")
    text = html.unescape(text)
    text = HTML_TAG.sub("", text)
    text = URL_PAT.sub("", text)
    text = text.replace("\u3000", " ")
    return SPACE_PAT.sub(" ", text).strip()


def dedup_key(text: str) -> str:
    """去重键：去除空白与常见标点后比较，避免仅标点差异造成重复。"""
    return re.sub(r"[\s，。！？!?、,.；;：:\"'“”‘’（）()【】\[\]…—\-]+", "", text)


def bigrams(text: str) -> list[str]:
    """与系统 JVM 侧一致的中文二元组近似分词。"""
    grams: list[str] = []
    for run in HAN_RUN.findall(text):
        for i in range(len(run) - 1):
            gram = run[i:i + 2]
            if gram[0] in STOP_CHARS or gram[1] in STOP_CHARS:
                continue
            grams.append(gram)
    return grams


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def chi2_2x2(a: int, b: int, c: int, d: int) -> float:
    """2x2 列联表卡方统计量。a/b 为组1正/负，c/d 为组2正/负。"""
    n = a + b + c + d
    if n == 0:
        return 0.0
    row1, row2 = a + b, c + d
    col1, col2 = a + c, b + d
    expected = [row1 * col1 / n, row1 * col2 / n, row2 * col1 / n, row2 * col2 / n]
    observed = [a, b, c, d]
    return sum((o - e) ** 2 / e for o, e in zip(observed, expected) if e > 0)


def chi2_sf(x: float, df: int) -> float:
    """仅实现本报告需要的 df=1/2 卡方分布生存函数。"""
    if df == 1:
        return math.erfc(math.sqrt(max(0.0, x) / 2.0))
    if df == 2:
        return math.exp(-max(0.0, x) / 2.0)
    raise ValueError("only df=1/2 supported")


def cohens_h(p1: float, p2: float) -> float:
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


def fmt_p(p: float) -> str:
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


# --------------------------------------------------------------------------- #
# 数据加载与清洗
# --------------------------------------------------------------------------- #

def load_source(src: dict) -> list[dict]:
    if not os.path.exists(src["path"]):
        raise FileNotFoundError(f"缺少数据文件：{src['path']}，请先下载 {src['url']}")
    actual = sha256_file(src["path"])
    if actual != src["sha256"]:
        raise ValueError(
            f"文件校验失败：{src['path']}\n期望 {src['sha256']}\n实际 {actual}"
        )
    rows: list[dict] = []
    with open(src["path"], encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp)
        for idx, row in enumerate(reader):
            text = clean_text(row.get(src["text_col"], ""))
            label_raw = str(row.get(src["label_col"], "")).strip()
            if label_raw not in {"0", "1"}:
                continue
            rows.append(
                {
                    "dataset": src["name"],
                    "domain": src["domain"],
                    "domain_key": src["key"],
                    "category": (row.get(src["cat_col"], "") if src["cat_col"] else "").strip(),
                    "label": int(label_raw),
                    "text": text,
                    "raw_len": len(text),
                    "row_no": idx + 2,
                }
            )
    return rows


def build_corpus() -> tuple[list[dict], list[dict], list[dict]]:
    """返回 (原始记录, 清洗漏斗记录, 最终语料)。"""
    raw: list[dict] = []
    funnel: list[dict] = []
    for src in SOURCES:
        rows = load_source(src)
        funnel.append({"dataset": src["name"], "domain": src["domain"], "step": "原始可解析记录", "count": len(rows)})
        raw.extend(rows)

    # 1) 去空文本
    non_empty = [r for r in raw if r["text"]]
    removed_empty = len(raw) - len(non_empty)
    funnel.append({"dataset": "合计", "domain": "全部", "step": "剔除空文本", "count": -removed_empty})

    # 2) 剔除电商语料中的“酒店”类，避免与 ChnSentiCorp 主题重叠
    no_hotel_cat = [r for r in non_empty if not (r["domain_key"] == "ecommerce" and r["category"] == "酒店")]
    removed_hotel_cat = len(non_empty) - len(no_hotel_cat)
    funnel.append({"dataset": "online_shopping_10_cats", "domain": "电商评论", "step": "剔除“酒店”子类（与酒店语料重叠）", "count": -removed_hotel_cat})

    # 3) 域内去重
    seen: set[str] = set()
    deduped: list[dict] = []
    removed_within = 0
    for r in no_hotel_cat:
        key = r["domain_key"] + "|" + dedup_key(r["text"])
        if key in seen:
            removed_within += 1
            continue
        seen.add(key)
        deduped.append(r)
    funnel.append({"dataset": "合计", "domain": "全部", "step": "域内重复文本去重", "count": -removed_within})

    # 4) 跨数据集去重（酒店 -> 电商 -> 外卖，保留先出现者）
    order = {"hotel": 0, "ecommerce": 1, "waimai": 2}
    deduped.sort(key=lambda r: order.get(r["domain_key"], 9))
    seen_global: set[str] = set()
    final: list[dict] = []
    removed_cross = 0
    for r in deduped:
        key = dedup_key(r["text"])
        if key in seen_global:
            removed_cross += 1
            continue
        seen_global.add(key)
        final.append(r)
    funnel.append({"dataset": "合计", "domain": "全部", "step": "跨数据集重复文本去重", "count": -removed_cross})
    funnel.append({"dataset": "合计", "domain": "全部", "step": "最终有效样本", "count": len(final)})

    # 恢复为域内原始顺序，便于复现
    final.sort(key=lambda r: (order.get(r["domain_key"], 9), r["row_no"]))
    return raw, funnel, final


# --------------------------------------------------------------------------- #
# 统计与可视化
# --------------------------------------------------------------------------- #

def domain_stats(final: list[dict]) -> list[dict]:
    stats: list[dict] = []
    for key, label in [("hotel", "酒店评论"), ("ecommerce", "电商评论"), ("waimai", "外卖评论")]:
        subset = [r for r in final if r["domain_key"] == key]
        n = len(subset)
        pos = sum(1 for r in subset if r["label"] == 1)
        neg = n - pos
        lo, hi = wilson_ci(pos, n)
        lengths = np.array([r["raw_len"] for r in subset], dtype=float)
        stats.append(
            {
                "domain_key": key,
                "domain": label,
                "n": n,
                "positive": pos,
                "negative": neg,
                "positive_rate": pos / n if n else 0.0,
                "ci_low": lo,
                "ci_high": hi,
                "len_mean": float(lengths.mean()),
                "len_std": float(lengths.std(ddof=1)),
                "len_median": float(np.median(lengths)),
                "len_p90": float(np.percentile(lengths, 90)),
                "len_p95": float(np.percentile(lengths, 95)),
                "len_p99": float(np.percentile(lengths, 99)),
                "len_max": float(lengths.max()),
                "share_le50": float((lengths <= 50).mean()),
                "share_gt128": float((lengths > 128).mean()),
                "share_gt256": float((lengths > 256).mean()),
                "share_gt512": float((lengths > 512).mean()),
                "grams_per_doc": float(np.mean([len(bigrams(r["text"])) for r in subset])) if subset else 0.0,
            }
        )
    # 总体
    n = len(final)
    pos = sum(1 for r in final if r["label"] == 1)
    lo, hi = wilson_ci(pos, n)
    lengths = np.array([r["raw_len"] for r in final], dtype=float)
    stats.append(
        {
            "domain_key": "all",
            "domain": "合计",
            "n": n,
            "positive": pos,
            "negative": n - pos,
            "positive_rate": pos / n if n else 0.0,
            "ci_low": lo,
            "ci_high": hi,
            "len_mean": float(lengths.mean()),
            "len_std": float(lengths.std(ddof=1)),
            "len_median": float(np.median(lengths)),
            "len_p90": float(np.percentile(lengths, 90)),
            "len_p95": float(np.percentile(lengths, 95)),
            "len_p99": float(np.percentile(lengths, 99)),
            "len_max": float(lengths.max()),
            "share_le50": float((lengths <= 50).mean()),
            "share_gt128": float((lengths > 128).mean()),
            "share_gt256": float((lengths > 256).mean()),
            "share_gt512": float((lengths > 512).mean()),
            "grams_per_doc": float(np.mean([len(bigrams(r["text"])) for r in final])) if final else 0.0,
        }
    )
    return stats


def category_stats(final: list[dict]) -> list[dict]:
    """电商语料 9 个子类的样本量、正向率与长度中位数。"""
    rows: list[dict] = []
    ecom = [r for r in final if r["domain_key"] == "ecommerce"]
    for cat in sorted({r["category"] for r in ecom}):
        subset = [r for r in ecom if r["category"] == cat]
        n = len(subset)
        pos = sum(1 for r in subset if r["label"] == 1)
        rows.append(
            {
                "category": cat,
                "n": n,
                "positive": pos,
                "positive_rate": pos / n if n else 0.0,
                "len_median": float(np.median([r["raw_len"] for r in subset])) if subset else 0.0,
            }
        )
    rows.sort(key=lambda r: r["n"], reverse=True)
    return rows


def plot_domain_overview(stats: list[dict]) -> None:
    data = [s for s in stats if s["domain_key"] != "all"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    names = [s["domain"] for s in data]
    ns = [s["n"] for s in data]
    rates = [s["positive_rate"] * 100 for s in data]
    errs = [
        [(s["positive_rate"] - s["ci_low"]) * 100 for s in data],
        [(s["ci_high"] - s["positive_rate"]) * 100 for s in data],
    ]

    bars = axes[0].bar(names, ns, color=COLORS[:3], width=0.55)
    for bar, n in zip(bars, ns):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(ns) * 0.015,
                     f"{n:,}", ha="center", va="bottom", fontsize=9)
    axes[0].set_title("各领域有效样本量", fontsize=11)
    axes[0].set_ylabel("样本数（条）")
    axes[0].set_ylim(0, max(ns) * 1.18)
    axes[0].grid(axis="y", alpha=0.25)

    bars = axes[1].bar(names, rates, color=COLORS[:3], width=0.55,
                       yerr=errs, capsize=4, error_kw={"ecolor": "#333333", "lw": 1})
    for bar, rate in zip(bars, rates):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2,
                     f"{rate:.1f}%", ha="center", va="bottom", fontsize=9)
    axes[1].set_title("各领域正向评论占比（95% Wilson 置信区间）", fontsize=11)
    axes[1].set_ylabel("正向占比（%）")
    axes[1].set_ylim(0, 100)
    axes[1].grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig01_domain_overview.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_lengths(final: list[dict]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
    for ax, (key, label, color) in zip(
        axes,
        [("hotel", "酒店评论", COLORS[0]), ("ecommerce", "电商评论", COLORS[1]), ("waimai", "外卖评论", COLORS[2])],
    ):
        lengths = np.array([r["raw_len"] for r in final if r["domain_key"] == key], dtype=float)
        bins = np.logspace(0, math.log10(max(10, lengths.max())), 40)
        ax.hist(lengths, bins=bins, color=color, alpha=0.82)
        ax.set_xscale("log")
        ax.axvline(np.median(lengths), color="#333333", linestyle="--", linewidth=1)
        ax.text(0.97, 0.92, f"n={len(lengths):,}\n中位数={np.median(lengths):.0f}字",
                transform=ax.transAxes, ha="right", va="top", fontsize=8.5)
        ax.set_title(label, fontsize=10.5)
        ax.set_xlabel("评论字符数（对数刻度）")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("评论条数")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig02_length_distribution.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def keyword_analysis(final: list[dict]) -> tuple[list[dict], list[dict]]:
    domains = ["酒店评论", "电商评论", "外卖评论"]
    domain_counters: dict[str, Counter] = {d: Counter() for d in domains}
    domain_pos: dict[str, Counter] = {d: Counter() for d in domains}
    domain_neg: dict[str, Counter] = {d: Counter() for d in domains}
    domain_pos_docs: dict[str, int] = {d: 0 for d in domains}
    domain_neg_docs: dict[str, int] = {d: 0 for d in domains}

    for r in final:
        grams = set(bigrams(r["text"]))
        d = r["domain"]
        domain_counters[d].update(grams)
        if r["label"] == 1:
            domain_pos[d].update(grams)
            domain_pos_docs[d] += 1
        else:
            domain_neg[d].update(grams)
            domain_neg_docs[d] += 1

    top_rows: list[dict] = []
    for domain in domains:
        counter = domain_counters[domain]
        total = sum(counter.values())
        for rank, (gram, count) in enumerate(counter.most_common(20), 1):
            top_rows.append(
                {
                    "domain": domain,
                    "rank": rank,
                    "gram": gram,
                    "count": count,
                    "share_per_1000": 1000 * count / total if total else 0.0,
                }
            )

    # 分层对数几率：先在每个领域内估计情感判别力，再按逆方差加权合并。
    # 这样可避免“酒店评论更长、用词更具体”导致的领域混杂，
    # 只在至少两个领域中稳定的词才进入结果。
    alpha = 0.5
    vocab = set()
    for d in domains:
        vocab |= set(domain_pos[d]) | set(domain_neg[d])
    logodds_rows: list[dict] = []
    for gram in vocab:
        deltas: list[float] = []
        variances: list[float] = []
        for d in domains:
            y = domain_pos[d].get(gram, 0)
            x = domain_neg[d].get(gram, 0)
            if y + x < 5:
                continue
            n1, n2 = domain_pos_docs[d], domain_neg_docs[d]
            delta = math.log((y + alpha) / (n1 + 2 * alpha - y - alpha)) - math.log(
                (x + alpha) / (n2 + 2 * alpha - x - alpha)
            )
            var = (
                1 / (y + alpha)
                + 1 / (n1 + 2 * alpha - y - alpha)
                + 1 / (x + alpha)
                + 1 / (n2 + 2 * alpha - x - alpha)
            )
            deltas.append(delta)
            variances.append(var)
        if len(deltas) < 2:
            continue
        delta_meta = sum(dt / v for dt, v in zip(deltas, variances)) / sum(1 / v for v in variances)
        var_meta = 1 / sum(1 / v for v in variances)
        z = delta_meta / math.sqrt(var_meta)
        logodds_rows.append(
            {
                "gram": gram,
                "n_domains": len(deltas),
                "delta": delta_meta,
                "z": z,
            }
        )
    logodds_rows.sort(key=lambda r: r["z"], reverse=True)
    return top_rows, logodds_rows


def plot_top_bigrams(top_rows: list[dict]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.9))
    for ax, (domain, color) in zip(axes, [("酒店评论", COLORS[0]), ("电商评论", COLORS[1]), ("外卖评论", COLORS[2])]):
        rows = [r for r in top_rows if r["domain"] == domain][:15]
        rows = rows[::-1]
        labels = [r["gram"] for r in rows]
        values = [r["count"] for r in rows]
        ax.barh(labels, values, color=color, alpha=0.85)
        ax.set_title(f"{domain}高频二元组 Top15", fontsize=12)
        ax.set_xlabel("出现评论数（文档频次）", fontsize=9.5)
        ax.tick_params(axis="both", labelsize=9)
        ax.grid(axis="x", alpha=0.2)
        for y, v in enumerate(values):
            ax.text(v, y, f" {v:,}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig03_top_bigrams.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_logodds(logodds_rows: list[dict]) -> None:
    positives = logodds_rows[:15]
    negatives = logodds_rows[-15:]
    rows = negatives + positives
    labels = [r["gram"] for r in rows]
    zs = [r["z"] for r in rows]
    colors = [COLORS[1] if z < 0 else COLORS[0] for z in zs]

    fig, ax = plt.subplots(figsize=(9.4, 6.4))
    ax.barh(labels, zs, color=colors, alpha=0.88)
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("分层对数几率 z 值（负值偏负面，正值偏正面）", fontsize=9.5)
    ax.set_title("跨领域分层对数几率：与正向/负向评论关联最强的二元组", fontsize=12)
    ax.tick_params(axis="both", labelsize=9)
    ax.grid(axis="x", alpha=0.2)
    for y, z in enumerate(zs):
        ax.text(z, y, f" {z:.1f}", va="center", ha="left" if z >= 0 else "right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig04_logodds.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def lexicon_rates(final: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for key, label in [("hotel", "酒店评论"), ("ecommerce", "电商评论"), ("waimai", "外卖评论")]:
        for lab, lab_name in [(1, "正向"), (0, "负向")]:
            subset = [r for r in final if r["domain_key"] == key and r["label"] == lab]
            n = len(subset)
            if n == 0:
                continue
            pos_hit = sum(1 for r in subset if any(w in r["text"] for w in POSITIVE_WORDS))
            neg_hit = sum(1 for r in subset if any(w in r["text"] for w in NEGATIVE_WORDS))
            rows.append(
                {
                    "domain": label,
                    "label": lab_name,
                    "n": n,
                    "positive_word_hit_per_1000": 1000 * pos_hit / n,
                    "negative_word_hit_per_1000": 1000 * neg_hit / n,
                }
            )
    return rows


def plot_lexicon(rates: list[dict]) -> None:
    domains = ["酒店评论", "电商评论", "外卖评论"]
    x = np.arange(len(domains))
    width = 0.36

    def get(domain: str, label: str, field: str) -> float:
        return next(r[field] for r in rates if r["domain"] == domain and r["label"] == label)

    pos_in_pos = [get(d, "正向", "positive_word_hit_per_1000") for d in domains]
    pos_in_neg = [get(d, "负向", "positive_word_hit_per_1000") for d in domains]
    neg_in_pos = [get(d, "正向", "negative_word_hit_per_1000") for d in domains]
    neg_in_neg = [get(d, "负向", "negative_word_hit_per_1000") for d in domains]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8), sharey=False)
    axes[0].bar(x - width / 2, pos_in_pos, width, label="正向评论", color=COLORS[0])
    axes[0].bar(x + width / 2, pos_in_neg, width, label="负向评论", color="#9AA5B1")
    for i, (a, b) in enumerate(zip(pos_in_pos, pos_in_neg)):
        axes[0].text(i - width / 2, a + 8, f"{a:.0f}", ha="center", fontsize=8)
        axes[0].text(i + width / 2, b + 8, f"{b:.0f}", ha="center", fontsize=8)
    axes[0].set_xticks(x, domains)
    axes[0].set_ylabel("每千条评论命中数")
    axes[0].set_title("正面词命中率：正向评论 vs 负向评论", fontsize=10.5)
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(x - width / 2, neg_in_neg, width, label="负向评论", color=COLORS[1])
    axes[1].bar(x + width / 2, neg_in_pos, width, label="正向评论", color="#9AA5B1")
    for i, (a, b) in enumerate(zip(neg_in_neg, neg_in_pos)):
        axes[1].text(i - width / 2, a + 8, f"{a:.0f}", ha="center", fontsize=8)
        axes[1].text(i + width / 2, b + 8, f"{b:.0f}", ha="center", fontsize=8)
    axes[1].set_xticks(x, domains)
    axes[1].set_ylabel("每千条评论命中数")
    axes[1].set_title("负面词命中率：负向评论 vs 正向评论", fontsize=10.5)
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="y", alpha=0.2)

    fig.suptitle("情感词典效度检验：情感词与人工标注的一致性", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig05_lexicon_validity.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 轻量基线：字符二元组 + 多项式朴素贝叶斯
# --------------------------------------------------------------------------- #

def stratified_split(records: list[dict], test_ratio: float = 0.2, seed: int = 42) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    train: list[dict] = []
    test: list[dict] = []
    by_label: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        by_label[r["label"]].append(r)
    for label, rows in by_label.items():
        rows = rows[:]
        rng.shuffle(rows)
        cut = int(round(len(rows) * test_ratio))
        test.extend(rows[:cut])
        train.extend(rows[cut:])
    train.sort(key=lambda r: (r["domain_key"], r["row_no"]))
    test.sort(key=lambda r: (r["domain_key"], r["row_no"]))
    return train, test


def build_vocab(records: list[dict], max_features: int = 30000, min_df: int = 3) -> dict[str, int]:
    df: Counter = Counter()
    for r in records:
        df.update(set(bigrams(r["text"])))
    vocab: dict[str, int] = {}
    for gram, count in df.most_common(max_features):
        if count < min_df:
            continue
        vocab[gram] = len(vocab)
    return vocab


def train_nb(records: list[dict], vocab: dict[str, int], alpha: float = 1.0):
    n_features = len(vocab)
    counts = np.zeros((2, n_features), dtype=np.float64)
    doc_counts = np.zeros(2, dtype=np.float64)
    for r in records:
        idxs = sorted({vocab[g] for g in set(bigrams(r["text"])) if g in vocab})
        if not idxs:
            continue
        counts[r["label"], idxs] += 1
        doc_counts[r["label"]] += 1
    loglik = np.log((counts + alpha) / (doc_counts[:, None] + alpha * n_features))
    logprior = np.log(doc_counts / max(1.0, doc_counts.sum()))
    return loglik, logprior


def predict_nb(records: list[dict], vocab: dict[str, int], loglik: np.ndarray, logprior: np.ndarray) -> list[int]:
    preds: list[int] = []
    for r in records:
        idxs = sorted({vocab[g] for g in set(bigrams(r["text"])) if g in vocab})
        scores = logprior.copy()
        if idxs:
            scores = scores + loglik[:, idxs].sum(axis=1)
        preds.append(int(np.argmax(scores)))
    return preds


def metrics(y_true: list[int], y_pred: list[int]) -> dict:
    cm = np.zeros((2, 2), dtype=int)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1
    per_class = {}
    f1s = []
    for label, name in [(0, "负向"), (1, "正向")]:
        tp = cm[label, label]
        fp = cm[1 - label, label]
        fn = cm[label, 1 - label]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[name] = {"precision": precision, "recall": recall, "f1": f1, "support": int(cm[label].sum())}
        f1s.append(f1)
    return {
        "n": int(cm.sum()),
        "accuracy": float(np.trace(cm) / cm.sum()) if cm.sum() else 0.0,
        "macro_f1": float(np.mean(f1s)),
        "confusion": cm.tolist(),
        "per_class": per_class,
    }


def baseline_analysis(final: list[dict]) -> tuple[dict, list[dict]]:
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for r in final:
        by_domain[r["domain_key"]].append(r)

    train_all: list[dict] = []
    test_all: list[dict] = []
    for key in ["hotel", "ecommerce", "waimai"]:
        train, test = stratified_split(by_domain[key])
        train_all.extend(train)
        test_all.extend(test)

    vocab = build_vocab(train_all, max_features=30000, min_df=3)
    loglik, logprior = train_nb(train_all, vocab)
    preds = predict_nb(test_all, vocab, loglik, logprior)
    combined = metrics([r["label"] for r in test_all], preds)
    combined["vocab_size"] = len(vocab)
    combined["train_n"] = len(train_all)

    # 分领域指标
    domain_rows: list[dict] = []
    for key, label in [("hotel", "酒店评论"), ("ecommerce", "电商评论"), ("waimai", "外卖评论")]:
        idxs = [i for i, r in enumerate(test_all) if r["domain_key"] == key]
        m = metrics([test_all[i]["label"] for i in idxs], [preds[i] for i in idxs])
        domain_rows.append({"domain": label, **m})

    # 3x3 跨域迁移矩阵（源域训练、目标域测试）
    transfer: list[dict] = []
    for src in ["hotel", "ecommerce", "waimai"]:
        src_train, _ = stratified_split(by_domain[src])
        v = build_vocab(src_train, max_features=20000, min_df=3)
        ll, lp = train_nb(src_train, v)
        for tgt in ["hotel", "ecommerce", "waimai"]:
            _, tgt_test = stratified_split(by_domain[tgt])
            p = predict_nb(tgt_test, v, ll, lp)
            m = metrics([r["label"] for r in tgt_test], p)
            transfer.append(
                {
                    "source": src,
                    "target": tgt,
                    "accuracy": m["accuracy"],
                    "macro_f1": m["macro_f1"],
                }
            )

    return {
        "combined": combined,
        "per_domain": domain_rows,
        "transfer": transfer,
    }, domain_rows


def plot_baseline(combined: dict, domain_rows: list[dict], transfer: list[dict]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    cm = np.array(combined["confusion"])
    im = axes[0].imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            axes[0].text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                         color="white" if cm[i, j] > cm.max() * 0.55 else "#222222", fontsize=11)
    axes[0].set_xticks([0, 1], ["预测负向", "预测正向"])
    axes[0].set_yticks([0, 1], ["真实负向", "真实正向"])
    axes[0].set_title(f"朴素贝叶斯基线混淆矩阵（Acc={combined['accuracy']:.2%}）", fontsize=10.5)
    fig.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04)

    labels = [r["domain"] for r in domain_rows]
    accs = [r["accuracy"] * 100 for r in domain_rows]
    f1s = [r["macro_f1"] * 100 for r in domain_rows]
    x = np.arange(len(labels))
    w = 0.36
    axes[1].bar(x - w / 2, accs, w, label="准确率", color=COLORS[0])
    axes[1].bar(x + w / 2, f1s, w, label="宏平均 F1", color=COLORS[3])
    for i, (a, f) in enumerate(zip(accs, f1s)):
        axes[1].text(i - w / 2, a + 1, f"{a:.1f}", ha="center", fontsize=8)
        axes[1].text(i + w / 2, f + 1, f"{f:.1f}", ha="center", fontsize=8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels)
    axes[1].set_ylim(0, 100)
    axes[1].set_ylabel("百分比（%）")
    axes[1].set_title("域内测试集表现", fontsize=10.5)
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig06_baseline.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)

    keys = ["hotel", "ecommerce", "waimai"]
    names = {"hotel": "酒店", "ecommerce": "电商", "waimai": "外卖"}
    matrix = np.zeros((3, 3))
    for row in transfer:
        matrix[keys.index(row["source"]), keys.index(row["target"])] = row["accuracy"]
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    im = ax.imshow(matrix, cmap="YlGnBu", vmin=0.4, vmax=1.0)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{matrix[i, j]:.1%}", ha="center", va="center",
                    color="white" if matrix[i, j] > 0.75 else "#222222", fontsize=10)
    ax.set_xticks(range(3), [f"测试：{names[k]}" for k in keys])
    ax.set_yticks(range(3), [f"训练：{names[k]}" for k in keys])
    ax.set_title("跨领域迁移准确率矩阵", fontsize=10.5)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig07_domain_transfer.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 现有 BERT 模型评估结果解析
# --------------------------------------------------------------------------- #

def parse_model_eval() -> dict:
    with open(EVAL_REPORT, encoding="utf-8") as fp:
        text = fp.read()
    def pick(pattern: str) -> float:
        m = re.search(pattern, text)
        return float(m.group(1)) if m else float("nan")

    result = {
        "accuracy": pick(r"准确率 Accuracy\s*：([0-9.]+)"),
        "macro_precision": pick(r"宏平均 Precision\s*：([0-9.]+)"),
        "macro_recall": pick(r"宏平均 Recall\s*：([0-9.]+)"),
        "macro_f1": pick(r"宏平均 F1\s*：([0-9.]+)"),
        "low_conf_ratio": pick(r"低置信度\(<0\.60\)占比\s*：([0-9.]+)"),
        "n_test": int(pick(r"测试样本数：([0-9]+)")),
        "per_class": {},
        "confusion": [],
    }
    for name in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
        m = re.search(rf"^\s*{name}\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9]+)\s*$", text, re.M)
        if m:
            result["per_class"][name] = {
                "precision": float(m.group(1)),
                "recall": float(m.group(2)),
                "f1": float(m.group(3)),
                "support": int(m.group(4)),
            }
    for name in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
        m = re.search(rf"^{name}\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s*$", text, re.M)
        if m:
            result["confusion"].append([int(m.group(i)) for i in range(1, 4)])
    return result


def plot_model_eval(model: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    names = ["POSITIVE", "NEGATIVE", "NEUTRAL"]
    cn = ["正面", "负面", "中性"]
    f1s = [model["per_class"][n]["f1"] * 100 for n in names]
    bars = axes[0].bar(cn, f1s, color=[COLORS[3], COLORS[1], COLORS[2]], width=0.55)
    for bar, v in zip(bars, f1s):
        axes[0].text(bar.get_x() + bar.get_width() / 2, v + 1, f"{v:.1f}%", ha="center", fontsize=9)
    axes[0].set_ylim(0, 100)
    axes[0].set_ylabel("F1（%）")
    axes[0].set_title("现有 BERT 模型分类别 F1（测试集 1,854 条）", fontsize=10.5)
    axes[0].grid(axis="y", alpha=0.2)

    cm = np.array(model["confusion"])
    im = axes[1].imshow(cm, cmap="Oranges")
    for i in range(3):
        for j in range(3):
            axes[1].text(j, i, f"{cm[i, j]:,}", ha="center", va="center",
                         color="white" if cm[i, j] > cm.max() * 0.55 else "#222222", fontsize=10)
    axes[1].set_xticks(range(3), [f"预测{c}" for c in cn])
    axes[1].set_yticks(range(3), [f"真实{c}" for c in cn])
    axes[1].set_title("现有 BERT 模型混淆矩阵", fontsize=10.5)
    fig.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig08_model_eval.png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def write_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    set_chinese_font()
    raw, funnel, final = build_corpus()
    print(f"[信息] 原始记录 {len(raw):,} 条，最终有效语料 {len(final):,} 条")

    stats = domain_stats(final)
    cat_stats = category_stats(final)
    plot_domain_overview(stats)
    plot_lengths(final)

    # 领域差异检验
    domain_rows = [s for s in stats if s["domain_key"] != "all"]
    # 3 组卡方（df=2）
    n_total = sum(s["n"] for s in domain_rows)
    pos_total = sum(s["positive"] for s in domain_rows)
    overall_p = pos_total / n_total
    chi = sum(
        (s["positive"] - s["n"] * overall_p) ** 2 / (s["n"] * overall_p)
        + (s["negative"] - s["n"] * (1 - overall_p)) ** 2 / (s["n"] * (1 - overall_p))
        for s in domain_rows
    )
    chi_p = chi2_sf(chi, 2)

    pairwise: list[dict] = []
    for i in range(len(domain_rows)):
        for j in range(i + 1, len(domain_rows)):
            a, b = domain_rows[i], domain_rows[j]
            x2 = chi2_2x2(a["positive"], a["negative"], b["positive"], b["negative"])
            pairwise.append(
                {
                    "group_a": a["domain"],
                    "group_b": b["domain"],
                    "rate_a": a["positive_rate"],
                    "rate_b": b["positive_rate"],
                    "diff_pp": (a["positive_rate"] - b["positive_rate"]) * 100,
                    "cohens_h": cohens_h(a["positive_rate"], b["positive_rate"]),
                    "chi2": x2,
                    "p_value": chi2_sf(x2, 1),
                }
            )

    top_rows, logodds_rows = keyword_analysis(final)
    plot_top_bigrams(top_rows)
    plot_logodds(logodds_rows)
    rates = lexicon_rates(final)
    plot_lexicon(rates)

    baseline, per_domain_metrics = baseline_analysis(final)
    plot_baseline(baseline["combined"], baseline["per_domain"], baseline["transfer"])

    model_eval = parse_model_eval()
    plot_model_eval(model_eval)

    # 数据源清单
    manifest: list[dict] = []
    for src in SOURCES:
        used = [r for r in final if r["dataset"] == src["name"]]
        manifest.append(
            {
                "dataset": src["name"],
                "domain": src["domain"],
                "url": src["url"],
                "sha256": src["sha256"],
                "archive_sha256": src.get("archive_sha256", ""),
                "description": src["description"],
                "collected_at": COLLECTED_AT,
                "raw_rows": len([r for r in raw if r["dataset"] == src["name"]]),
                "used_rows": len(used),
                "fields": f"{src['label_col']},{src['text_col']}" + (f",{src['cat_col']}" if src["cat_col"] else ""),
                "label_scheme": "0=负向，1=正向（无中性标注）",
            }
        )

    summary = {
        "raw_total": len(raw),
        "final_total": len(final),
        "funnel": funnel,
        "domain_stats": stats,
        "category_stats": cat_stats,
        "chi_square": {"chi2": chi, "df": 2, "p_value": chi_p},
        "pairwise": pairwise,
        "top_bigrams": top_rows,
        "logodds": logodds_rows,
        "lexicon_rates": rates,
        "baseline": baseline,
        "model_eval": model_eval,
        "manifest": manifest,
        "generated_at": "2026-11-06",
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as fp:
        json.dump(to_jsonable(summary), fp, ensure_ascii=False, indent=2)

    write_csv(
        os.path.join(OUT_DIR, "data_source_manifest.csv"),
        manifest,
        ["dataset", "domain", "url", "sha256", "archive_sha256", "description", "collected_at", "raw_rows", "used_rows", "fields", "label_scheme"],
    )
    write_csv(
        os.path.join(OUT_DIR, "domain_stats.csv"),
        stats,
        ["domain_key", "domain", "n", "positive", "negative", "positive_rate", "ci_low", "ci_high",
         "len_mean", "len_std", "len_median", "len_p90", "len_p95", "len_p99", "len_max",
         "share_le50", "share_gt128", "share_gt256", "share_gt512", "grams_per_doc"],
    )
    write_csv(
        os.path.join(OUT_DIR, "category_stats.csv"),
        cat_stats,
        ["category", "n", "positive", "positive_rate", "len_median"],
    )
    write_csv(
        os.path.join(OUT_DIR, "top_bigrams.csv"),
        top_rows,
        ["domain", "rank", "gram", "count", "share_per_1000"],
    )
    write_csv(
        os.path.join(OUT_DIR, "logodds_bigrams.csv"),
        logodds_rows,
        ["gram", "n_domains", "delta", "z"],
    )
    write_csv(
        os.path.join(OUT_DIR, "lexicon_rates.csv"),
        rates,
        ["domain", "label", "n", "positive_word_hit_per_1000", "negative_word_hit_per_1000"],
    )
    write_csv(
        os.path.join(OUT_DIR, "baseline_metrics.csv"),
        baseline["per_domain"],
        ["domain", "n", "accuracy", "macro_f1", "confusion", "per_class"],
    )
    write_csv(
        os.path.join(OUT_DIR, "domain_transfer.csv"),
        baseline["transfer"],
        ["source", "target", "accuracy", "macro_f1"],
    )

    # 控制台摘要
    print("\n=== 真实数据复核摘要 ===")
    for s in stats:
        print(
            f"{s['domain']:<6} n={s['n']:>6,} 正向率={s['positive_rate']:.2%} "
            f"[{s['ci_low']:.2%}, {s['ci_high']:.2%}] 长度中位数={s['len_median']:.0f} "
            f">512字={s['share_gt512']:.2%}"
        )
    print(f"领域正负向比例差异卡方={chi:.2f}, df=2, p={fmt_p(chi_p)}")
    print(f"基线：Acc={baseline['combined']['accuracy']:.2%}, MacroF1={baseline['combined']['macro_f1']:.2%}")
    for row in baseline["per_domain"]:
        print(f"  {row['domain']}：Acc={row['accuracy']:.2%}, MacroF1={row['macro_f1']:.2%}")
    print(f"现有BERT：Acc={model_eval['accuracy']:.2%}, MacroF1={model_eval['macro_f1']:.2%}, "
          f"低置信度={model_eval['low_conf_ratio']:.2%}")
    print(f"输出目录：{OUT_DIR}")


def set_chinese_font() -> None:
    """优先使用 Windows 自带中文字体，避免图中中文乱码。"""
    for font in ["Microsoft YaHei", "SimHei", "SimSun", "Noto Sans CJK SC"]:
        try:
            matplotlib.font_manager.findfont(font, fallback_to_default=False)
            plt.rcParams["font.sans-serif"] = [font]
            break
        except Exception:
            continue
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120


if __name__ == "__main__":
    main()
