# -*- coding: utf-8 -*-
"""三分类标签修正与数据集重建脚本（v2）。

背景
----
原始数据的 NEUTRAL 类并非「文本中性」，而是由亚马逊 3 星评分样本直接映射而来。
3 星评论的文本往往带有明确的褒贬倾向（抽检中大量 3 星文本为明显负向，甚至明显正向），
导致「评分标签」与「文本语义」不一致。这类噪声对任何文本分类模型都是不可约误差：
BERT 只能从文本学习，无法从文本推断用户点了几个星。原模型测试集 76% 的错误都落在
NEUTRAL 与 POSITIVE/NEGATIVE 的边界上，正是该问题的直接体现。

本脚本的做法
------------
1. 文本清洗：与 data_preprocessing_eda.py 的 clean_text 保持同一口径。
2. 概率教师：仅用「干净二分类样本」（原始 1-2 星 = NEGATIVE，4-5 星 = POSITIVE）
   训练 TF-IDF + 逻辑回归，得到 P(正向 | 文本)。该教师只依赖文本极性，
   不受 3 星评分噪声影响。
3. 重标注：只用教师修正原始 label=2 的 3 星样本：
       P(正向) >= tau_pos  -> POSITIVE
       P(正向) <= tau_neg  -> NEGATIVE
       其余（极性不确定/褒贬混合） -> NEUTRAL
   原始 0/1 标签保持不变，避免破坏干净的监督信号。
4. 划分：完全沿用原 output 下 train/val/test 的逐行样本，只改标签，
   保证优化前后在「同一批测试样本」上对比。

输出
----
output_v2/train.csv、val.csv、test.csv     与原划分逐行对齐，仅标签变化
output_v2/relabel_report.json              重标注统计、教师质量、阈值敏感性
output_v2/teacher_model.joblib             教师模型（可复现、可复用）

用法
----
    python prepare_dataset_v2.py
    python prepare_dataset_v2.py --src output --dst output_v2 --tau-pos 0.62 --tau-neg 0.38
"""

import argparse
import html
import json
import os
import re
from collections import Counter

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.pipeline import Pipeline

# --------------------------------------------------------------------------- #
# 全局配置
# --------------------------------------------------------------------------- #

# 标签顺序与 train.py / 后端 labels.txt 完全一致
LABEL_ORDER = ["POSITIVE", "NEGATIVE", "NEUTRAL"]

# 原始数值标签 -> 语义标签（0=负向，1=正向，2=3 星/评分中性）
RAW_TO_NAME = {0: "NEGATIVE", 1: "POSITIVE", 2: "NEUTRAL"}
NAME_TO_ID = {name: index for index, name in enumerate(LABEL_ORDER)}

# 教师判定阈值：P(正向) 高于 tau_pos 判正向，低于 tau_neg 判负向，中间保留为 NEUTRAL
TAU_POS = 0.62
TAU_NEG = 0.38

# 标注方案：
#   teacher —— 按教师概率区间划分（NEUTRAL = 极性不确定区间）
#   cue     —— 按「是否存在情感线索」划分（NEUTRAL = 无任何褒贬线索的客观陈述），
#              有线索的文本再由教师给出正/负极性。该方案语义边界更清晰、更易学习。
SCHEME_CHOICES = ("teacher", "cue")

# 情感线索词表（用于 cue 方案判定「是否有褒贬表达」，不参与极性打分）
CUE_POSITIVE_WORDS = """
好 很好 不错 满意 喜欢 推荐 值得 优秀 完美 惊喜 棒 赞 漂亮 好看 舒服 方便 快 实惠 划算
便宜 耐用 清晰 流畅 贴心 专业 热情 干净 整洁 新鲜 好吃 好用 靠谱 放心 精致 细腻 良心 超值 给力
点赞 开心 幸福 感动 惊艳 强大 稳定 顺畅 迅速 及时 周到 细致 耐心 友好 高品质 正品 质量好 性价比
物美价廉 无可挑剔 爱不释手 名副其实 超出预期 物有所值 值得购买 会回购 推荐购买 还行 还可以 尚可 中规中矩
""".split()

CUE_NEGATIVE_WORDS = """
差 很差 垃圾 失望 后悔 退货 退款 坏 损坏 故障 慢 太慢 贵 太贵 难用 难吃 难看 难闻 糟糕 坑 骗 假 假货
次 破 脏 漏 臭 吵 薄 粗糙 敷衍 态度差 不专业 不推荐 不值 浪费 欺骗 虚假 缺德 无语 崩溃 恶心 生气 愤怒
郁闷 烦躁 上当 受骗 缩水 变质 过期 发霉 异味 色差 瑕疵 缺陷 掉色 起球 开胶 断裂 卡顿 闪退 死机 发热
耗电 噪音 漏水 漏电 不结实 不牢固 不好用 不新鲜 差评 极差 太差 差劲 一般般 不怎么样 不理想 不满意
不如 没有想象 失望透顶 再也不买 投诉
""".split()

CUE_POSITIVE = set(CUE_POSITIVE_WORDS)
CUE_NEGATIVE = set(CUE_NEGATIVE_WORDS)
CUE_NEGATORS = {"不", "没", "无", "非", "未", "别", "莫", "勿", "毫无", "并不", "没有"}

# 阈值敏感性分析的候选区间（tau_pos 必须 >= 0.5，保证 tau_neg = 1 - tau_pos 不重叠）
TAU_GRID = [0.50, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70, 0.75]

# 文本清洗正则（与 data_preprocessing_eda.py 保持一致，避免训练/推理口径漂移）
RE_HTML_TAG = re.compile(r"<[^>]+>")
RE_URL = re.compile(r"(https?://\S+|www\.\S+)")
RE_EMAIL = re.compile(r"\S+@\S+\.\S+")
RE_INVISIBLE = re.compile(r"[\u200b-\u200f\ufeff\xa0]")
RE_KEEP_CHARS = re.compile(r"[^\u4e00-\u9fa5a-zA-Z0-9,.;:!?，。；：！？、]")
RE_MULTI_SPACE = re.compile(r"\s+")
RE_REPEAT_PUNCT = re.compile(r"([!?！？。，,.~～])\1{2,}")

SPLITS = ("train", "val", "test")


def clean_text(raw_text) -> str:
    """文本清洗：去 HTML/URL/邮箱/零宽字符，保留中英文数字与常用标点。

    :param raw_text: 原始文本
    :return: 清洗后的文本，非法输入返回空串
    """
    if not isinstance(raw_text, str):
        return ""
    text = html.unescape(raw_text)
    text = RE_HTML_TAG.sub("", text)
    text = RE_URL.sub("", text)
    text = RE_EMAIL.sub("", text)
    text = RE_INVISIBLE.sub("", text)
    text = RE_KEEP_CHARS.sub("", text)
    text = RE_REPEAT_PUNCT.sub(r"\1", text)     # 连续重复标点压缩为一个，抑制噪声特征
    text = RE_MULTI_SPACE.sub(" ", text)
    return text.strip()


def load_split(path: str) -> pd.DataFrame:
    """读取单个划分文件并清洗文本，保留原始数值标签。

    :param path: CSV 路径
    :return: 含 content、raw_label、label_name 的 DataFrame
    """
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df.dropna(how="all").reset_index(drop=True)
    df["content"] = df["content"].fillna("").map(clean_text)
    df = df[df["content"].str.len() > 0].copy()
    df["raw_label"] = df["label"].astype(int)
    df["label_name"] = df["raw_label"].map(RAW_TO_NAME)
    return df.reset_index(drop=True)


def build_teacher(train_df: pd.DataFrame, seed: int = 42) -> Pipeline:
    """在干净二分类样本上训练概率教师：TF-IDF（字符 2~4 gram）+ 逻辑回归。

    只使用原始 0/1 标签，完全避开 3 星噪声。

    :param train_df: 训练集 DataFrame
    :param seed: 随机种子
    :return: 已训练的 sklearn Pipeline
    """
    clean = train_df[train_df["raw_label"].isin([0, 1])]
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",        # 中文无需分词，字符 n-gram 对否定词与口语更鲁棒
            ngram_range=(2, 4),
            min_df=2,
            max_features=200000,
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            C=1.0,
            max_iter=2000,
            class_weight="balanced",
            solver="liblinear",
            random_state=seed,
        )),
    ])
    pipeline.fit(clean["content"].tolist(), (clean["raw_label"] == 1).astype(int).tolist())
    return pipeline


def teacher_quality(teacher: Pipeline, val_df: pd.DataFrame) -> dict:
    """在验证集的干净二分类样本上评估教师，作为重标注可信度的依据。

    :return: 指标字典（accuracy / macro_f1 / auc / n）
    """
    clean = val_df[val_df["raw_label"].isin([0, 1])]
    y_true = (clean["raw_label"] == 1).astype(int).to_numpy()
    prob = teacher.predict_proba(clean["content"].tolist())[:, 1]
    pred = (prob >= 0.5).astype(int)
    return {
        "n": int(len(clean)),
        "accuracy": round(float(accuracy_score(y_true, pred)), 4),
        "macro_f1": round(float(f1_score(y_true, pred, average="macro")), 4),
        "auc": round(float(roc_auc_score(y_true, prob)), 4),
    }


def cue_counts(text: str) -> tuple:
    """统计文本中的正向/负向情感线索数量（含否定翻转）。

    :param text: 评论文本
    :return: (正向线索数, 负向线索数)
    """
    import jieba

    positive = negative = 0
    previous = ""
    for raw in jieba.cut(text):
        token = raw.strip()
        if not token:
            continue
        if token in CUE_NEGATORS:
            previous = token
            continue
        hits_positive = token in CUE_POSITIVE
        hits_negative = token in CUE_NEGATIVE
        if hits_positive or hits_negative:
            negated = previous in CUE_NEGATORS
            if hits_positive:
                negative += 1 if negated else 0
                positive += 0 if negated else 1
            if hits_negative:
                positive += 1 if negated else 0
                negative += 0 if negated else 1
        previous = token
    return positive, negative


def assign_label_cue(prob: float, text: str) -> str:
    """cue 方案：无情感线索 -> NEUTRAL；有线索则按教师概率取极性。

    :param prob: P(正向 | 文本)
    :param text: 评论文本
    :return: POSITIVE / NEGATIVE / NEUTRAL
    """
    positive, negative = cue_counts(text)
    if positive == 0 and negative == 0:
        return "NEUTRAL"
    return "POSITIVE" if prob >= 0.5 else "NEGATIVE"


def assign_label(prob: float, tau_pos: float, tau_neg: float) -> str:
    """依据教师概率给出语义标签。

    :param prob: P(正向 | 文本)
    :param tau_pos: 判定为正向上的阈值
    :param tau_neg: 判定为负向下的阈值
    :return: POSITIVE / NEGATIVE / NEUTRAL
    """
    if prob >= tau_pos:
        return "POSITIVE"
    if prob <= tau_neg:
        return "NEGATIVE"
    return "NEUTRAL"


def threshold_sweep(probs: np.ndarray) -> list:
    """统计不同阈值下 3 星样本的重标注结果，用于选择阈值。

    :param probs: 全部 3 星样本的 P(正向)
    :return: 每个阈值对应的类别计数与 NEUTRAL 占比
    """
    rows = []
    for tau in TAU_GRID:
        pos = int((probs >= tau).sum())
        neg = int((probs <= 1 - tau).sum())
        neu = int(len(probs) - pos - neg)
        rows.append({
            "tau_pos": tau, "tau_neg": round(1 - tau, 2),
            "POSITIVE": pos, "NEGATIVE": neg, "NEUTRAL": neu,
            "neutral_ratio": round(neu / max(len(probs), 1), 4),
        })
    return rows


def relabel_split(df: pd.DataFrame, teacher: Pipeline, scheme: str,
                  tau_pos: float, tau_neg: float) -> pd.DataFrame:
    """对单个划分执行重标注：只修改原始 3 星样本，0/1 标签保持不变。

    :return: 含 content、label（新语义标签）、label_id、origin_label 的 DataFrame
    """
    df = df.copy()
    probs = teacher.predict_proba(df["content"].tolist())[:, 1]

    new_labels = df["label_name"].tolist()
    if scheme == "cue":
        # cue 方案会重标所有样本：情感线索决定是否为 NEUTRAL，教师决定正/负
        new_labels = [assign_label_cue(float(prob), text)
                      for prob, text in zip(probs, df["content"].tolist())]
    else:
        for index in range(len(df)):
            if df["raw_label"].iloc[index] == 2:
                new_labels[index] = assign_label(float(probs[index]), tau_pos, tau_neg)

    df["teacher_prob_pos"] = probs
    df["origin_label"] = df["label_name"]
    df["label"] = new_labels
    df["label_id"] = df["label"].map(NAME_TO_ID).astype(int)
    return df


def summarize(df: pd.DataFrame, name: str) -> dict:
    """输出单个划分的标签分布与重标注变化统计。"""
    if "origin_label" not in df.columns:
        # 扩充后的训练集已混入外部语料，没有单一的原始标签可比对
        counts = {label: int((df["label"] == label).sum()) for label in LABEL_ORDER}
        return {
            "split": name,
            "rows": int(len(df)),
            "label_counts": counts,
            "origin_counts": counts,
            "relabeled_rows": 0,
            "relabeled_detail": {},
        }
    changed = df[df["label"] != df["origin_label"]]
    return {
        "split": name,
        "rows": int(len(df)),
        "label_counts": {label: int((df["label"] == label).sum()) for label in LABEL_ORDER},
        "origin_counts": {label: int((df["origin_label"] == label).sum()) for label in LABEL_ORDER},
        "relabeled_rows": int(len(changed)),
        "relabeled_detail": {
            f"{src}->{dst}": int(count)
            for (src, dst), count in Counter(zip(changed["origin_label"], changed["label"])).items()
        },
    }


def augment_training_set(train_df: pd.DataFrame, teacher: Pipeline, scheme: str,
                         extra_rows: int, seed: int) -> pd.DataFrame:
    """用公开中文情感语料扩充训练集（仅扩充 train，val/test 保持原样）。

    扩充语料的极性标签本身是干净的（公开数据集的人工 0/1 标注），
    但为了让三分类定义与主数据一致，仍统一按同一套规则重标注：
    无情感线索 -> NEUTRAL，有线索 -> 教师极性。

    :param train_df: 现有训练集
    :param teacher: 概率教师
    :param scheme: 标注方案
    :param extra_rows: 期望补充的样本数（0 表示不扩充）
    :param seed: 随机种子
    :return: 扩充后的训练集（含 label、content、label_id）
    """
    if extra_rows <= 0:
        return train_df

    candidates = []
    for path, text_column in (
        ("data/real_public/online_shopping_10_cats/online_shopping_10_cats.csv", "review"),
        ("data/real_public/waimai_10k.csv", "review"),
        ("data/real_public/ChnSentiCorp_htl_all.csv", "review"),
    ):
        if not os.path.exists(path):
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if text_column not in frame.columns or "label" not in frame.columns:
            continue
        frame = frame[["label", text_column]].rename(columns={text_column: "content"})
        frame["content"] = frame["content"].fillna("").map(clean_text)
        frame = frame[frame["content"].str.len() >= 6]
        candidates.append(frame)
        print(f"[信息] 读取扩充语料 {os.path.basename(path)}：{len(frame)} 条")

    if not candidates:
        print("[警告] 未找到可用的扩充语料，训练集保持原样。")
        return train_df

    extra = pd.concat(candidates, ignore_index=True)
    extra = extra.drop_duplicates(subset=["content"]).reset_index(drop=True)

    # 只保留训练集未出现过的文本，避免与训练样本重复
    known = set(train_df["content"])
    extra = extra[~extra["content"].isin(known)].reset_index(drop=True)

    extra["raw_label"] = extra["label"].astype(int)
    extra["label_name"] = extra["raw_label"].map(RAW_TO_NAME)

    # 先按原始二分类比例抽样，再重标注：避免对上万条文本做无谓的教师推理
    if extra_rows < len(extra):
        parts = []
        for label, pool in extra.groupby("raw_label"):
            take = max(1, int(extra_rows * len(pool) / len(extra)))
            parts.append(pool.sample(min(take, len(pool)), random_state=seed))
        extra = pd.concat(parts, ignore_index=True)

    relabeled = relabel_split(extra, teacher, scheme, TAU_POS, TAU_NEG)

    merged = pd.concat([train_df[["label", "content", "label_id"]],
                        relabeled[["label", "content", "label_id"]]], ignore_index=True)
    merged = merged.drop_duplicates(subset=["content"], keep="first").reset_index(drop=True)
    print(f"[信息] 训练集扩充：{len(train_df)} -> {len(merged)} 条")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="三分类标签修正与数据集重建（v2）")
    parser.add_argument("--src", default="output", help="原始数据集目录（train/val/test.csv）")
    parser.add_argument("--dst", default="output_v2", help="输出目录")
    parser.add_argument("--tau-pos", type=float, default=TAU_POS, help="判定正向的概率阈值")
    parser.add_argument("--tau-neg", type=float, default=TAU_NEG, help="判定负向的概率阈值")
    parser.add_argument("--scheme", choices=SCHEME_CHOICES, default="cue",
                        help="标注方案：teacher=概率区间，cue=情感线索")
    parser.add_argument("--augment-rows", type=int, default=0,
                        help="用公开语料补充训练的样本数（0 表示不扩充）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    os.makedirs(args.dst, exist_ok=True)

    # 1) 读取并清洗（保持原划分成员不变）
    frames = {name: load_split(os.path.join(args.src, f"{name}.csv")) for name in SPLITS}
    print("[信息] 原始划分：", {name: len(df) for name, df in frames.items()})

    # 2) 训练概率教师并评估
    teacher = build_teacher(frames["train"], seed=args.seed)
    quality = teacher_quality(teacher, frames["val"])
    print(f"[信息] 教师二分类质量（验证集干净样本）：{quality}")

    # 3) 阈值敏感性分析（仅 teacher 方案需要）
    sweep = []
    if args.scheme == "teacher":
        all_star3 = pd.concat([frames[name] for name in SPLITS])
        all_star3 = all_star3[all_star3["raw_label"] == 2]
        star3_probs = teacher.predict_proba(all_star3["content"].tolist())[:, 1]
        print(f"[信息] 3 星样本共 {len(star3_probs)} 条，P(正向) 均值 "
              f"{star3_probs.mean():.3f}，中位数 {np.median(star3_probs):.3f}")
        sweep = threshold_sweep(star3_probs)
    else:
        print("[信息] 使用 cue 方案：NEUTRAL 由情感线索是否存在决定")

    # 4) 重标注并落盘
    relabeled = {name: relabel_split(frames[name], teacher, args.scheme,
                                     args.tau_pos, args.tau_neg) for name in SPLITS}

    # 4.1) 可选：用公开语料扩充训练集（验证/测试集固定不变，保证指标可比）
    relabeled["train"] = augment_training_set(
        relabeled["train"], teacher, args.scheme, args.augment_rows, args.seed
    )

    for name in SPLITS:
        out = relabeled[name][["label", "content"]].copy()
        out.to_csv(os.path.join(args.dst, f"{name}.csv"), index=False, encoding="utf-8-sig")
        print(f"[信息] 已保存 {os.path.join(args.dst, name + '.csv')}（{len(out)} 条）")

    # 5) 记录报告，保证实验可追溯
    report = {
        "method": "TF-IDF(char 2-4gram) + LogisticRegression teacher trained on clean binary samples",
        "scheme": args.scheme,
        "tau_pos": args.tau_pos,
        "tau_neg": args.tau_neg,
        "teacher_quality": quality,
        "star3_prob_stats": {
            "n": int(len(all_star3)) if args.scheme == "teacher" else 0,
            "mean": round(float(star3_probs.mean()), 4) if args.scheme == "teacher" else None,
            "median": round(float(np.median(star3_probs)), 4) if args.scheme == "teacher" else None,
            "p10": round(float(np.percentile(star3_probs, 10)), 4) if args.scheme == "teacher" else None,
            "p90": round(float(np.percentile(star3_probs, 90)), 4) if args.scheme == "teacher" else None,
        },
        "threshold_sweep": sweep,
        "splits": [summarize(relabeled[name], name) for name in SPLITS],
    }
    with open(os.path.join(args.dst, "relabel_report.json"), "w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    joblib.dump(teacher, os.path.join(args.dst, "teacher_model.joblib"))

    print("[信息] 重标注完成：")
    for item in report["splits"]:
        print(f"  {item['split']}: {item['label_counts']}，改写 {item['relabeled_rows']} 条")
    print(f"[信息] 报告：{os.path.join(args.dst, 'relabel_report.json')}")


if __name__ == "__main__":
    main()
