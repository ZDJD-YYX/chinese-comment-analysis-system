# -*- coding: utf-8 -*-
"""中文评论情感分析系统 —— 数据处理与 EDA 分析脚本。

功能概览：
    1. 数据加载与基本信息查看（样本量、类别分布、缺失值统计）
    2. 数据清洗（空值、重复值、特殊符号、HTML 标签、多余空格）
    3. 文本长度分布统计与直方图绘制
    4. 词频统计与可视化（各类别高频词 Top20）
    5. 数据集分层划分（训练集 70% / 验证集 20% / 测试集 10%）
    6. 划分结果落盘为 train.csv / val.csv / test.csv

数据集：ChnSentiCorp 中文情感评论数据集，CSV 格式，字段为 label、content。

用法示例：
    python data_preprocessing_eda.py --input data/ChnSentiCorp.csv --output output
"""

import argparse
import html
import os
import re
from collections import Counter

import jieba
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.model_selection import train_test_split

# --------------------------------------------------------------------------- #
# 全局配置
# --------------------------------------------------------------------------- #

# 列名兼容：优先使用标准列名，缺失时按候选名自动识别
CONTENT_COLUMN_CANDIDATES = ["content", "text", "comment", "评论", "内容", "评价", "留言"]
LABEL_COLUMN_CANDIDATES = ["label", "sentiment", "标签", "情感"]

# 标签别名映射：统一归一到项目约定的三分类取值
# 说明：ChnSentiCorp 原始语料常见取值为 0/1，此处按 0=负面、1=正面 处理，
#      如需调整映射关系，直接修改本字典即可（映射表与实现解耦）。
LABEL_ALIASES = {
    "positive": "POSITIVE", "pos": "POSITIVE", "1": "POSITIVE",
    "front": "POSITIVE", "正面": "POSITIVE", "积极": "POSITIVE",
    "negative": "NEGATIVE", "neg": "NEGATIVE", "0": "NEGATIVE",
    "负面": "NEGATIVE", "消极": "NEGATIVE",
    "neutral": "NEUTRAL", "neu": "NEUTRAL", "2": "NEUTRAL",
    "中性": "NEUTRAL", "客观": "NEUTRAL",
}

# 三分类展示顺序，保证图表与打印结果顺序稳定
LABEL_ORDER = ["POSITIVE", "NEGATIVE", "NEUTRAL"]

# 中文停用词表（内置常用词，避免脚本依赖外部文件即可运行）
STOPWORDS = set("""
的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己
这 那 他 她 它 们 这个 那个 这些 那些 什么 怎么 这样 那样 因为 所以 但是 而且 如果
还 就是 只是 已经 可以 应该 能够 需要 觉得 感觉 知道 时候 现在 还是 比较 非常 特别
真的 其实 有点 一点 一下 一直 一些 一样 之后 之前 的话 东西 问题 情况 方面 我们 你们
他们 大家 这里 那里 哪里 谁 为什么 怎样 如何 于是 然后 另外 其中 以及 或者 并且 不过
虽然 然而 因此 从而 对于 关于 根据 通过 由于 为了 除了 甚至 而且 只是 只有 无论 不管
并且 什么 各位 谢谢 请 让 给 被 把 从 向 对 与 及 等 更 最 太 再 又 才 只 没 好 嗯 哦 啊
""".split())

# 划分比例与随机种子，保证实验可复现
TRAIN_RATIO, VAL_RATIO, TEST_RATIO = 0.7, 0.2, 0.1
RANDOM_STATE = 42

# 词频统计与可视化参数
TOP_N = 20

# 绘图风格
PLOT_DPI = 150
FIG_WIDTH = 9.0
FIG_HEIGHT = 5.0


# --------------------------------------------------------------------------- #
# 通用工具函数
# --------------------------------------------------------------------------- #

def setup_matplotlib() -> None:
    """配置 matplotlib：使用中文字体，避免图表中文显示为方框。"""
    available_fonts = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for font_name in ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"]:
        if font_name in available_fonts:
            plt.rcParams["font.sans-serif"] = [font_name]
            break
    else:
        print("[警告] 未找到可用中文字体，图表中的中文可能显示异常。")
    plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号


def print_section(title: str) -> None:
    """打印统一的段落分隔标题，提升控制台输出可读性。"""
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def resolve_column(df: pd.DataFrame, standard_name: str, candidates: list) -> str:
    """在 DataFrame 中定位目标列名，支持标准名与候选别名。

    :param df: 待处理的 DataFrame
    :param standard_name: 标准列名，如 "content"
    :param candidates: 候选列名列表（按优先级排列）
    :return: 实际命中的列名
    :raises KeyError: 所有候选名均未命中时抛出，并提示现有列名
    """
    for name in candidates:
        if name in df.columns:
            return name
    raise KeyError(
        f"未找到列 '{standard_name}'，当前文件列名为：{list(df.columns)}，"
        f"请确认数据集格式（期望包含 {candidates}）。"
    )


# --------------------------------------------------------------------------- #
# 1. 数据加载与基本信息
# --------------------------------------------------------------------------- #

def load_dataset(file_path: str) -> pd.DataFrame:
    """加载 CSV 数据集，自动尝试常见中文编码。

    :param file_path: CSV 文件路径
    :return: 含 label、content 两列的 DataFrame
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"数据文件不存在：{file_path}")

    last_error = None
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            print(f"[信息] 数据加载成功，使用编码：{encoding}")
            break
        except UnicodeDecodeError as error:  # 编码不匹配，尝试下一种
            last_error = error
    else:
        raise UnicodeDecodeError(
            "utf-8", b"", 0, 1, f"无法识别的文件编码，最后一次错误：{last_error}"
        )

    # 统一列名，保证后续流程只依赖标准列名
    label_col = resolve_column(df, "label", LABEL_COLUMN_CANDIDATES)
    content_col = resolve_column(df, "content", CONTENT_COLUMN_CANDIDATES)
    df = df.rename(columns={label_col: "label", content_col: "content"})

    # 去除全空行，并将文本列强制转为字符串以便后续清洗
    df = df.dropna(how="all").reset_index(drop=True)
    df["label"] = df["label"].astype("string")
    df["content"] = df["content"].astype("string")
    return df[["label", "content"]]


def normalize_labels(df: pd.DataFrame) -> pd.DataFrame:
    """将原始标签归一化为 POSITIVE / NEGATIVE / NEUTRAL 三分类。

    无法识别的标签保留原值并给出提示，便于人工核查数据源。

    :param df: 含 label 列的 DataFrame
    :return: 新增 label_name 列（统一后的标签）的 DataFrame
    """
    def _map_one(value) -> str:
        if pd.isna(value):
            return "UNKNOWN"
        key = str(value).strip().lower()
        return LABEL_ALIASES.get(key, str(value).strip().upper())

    df = df.copy()
    df["label_name"] = df["label"].map(_map_one)

    unknown = sorted(set(df.loc[~df["label_name"].isin(LABEL_ORDER), "label_name"].tolist()))
    if unknown:
        print(f"[警告] 存在未在映射表中的标签取值：{unknown}，已按原值保留。")
    return df


def show_basic_info(df: pd.DataFrame) -> None:
    """打印数据集基本信息：样本量、类别分布、缺失值统计。"""
    print_section("一、数据基本信息")
    print(f"样本总量：{len(df)} 条")
    print(f"字段列表：{list(df.columns)}")

    print("\n--- 类别分布 ---")
    label_counts = df["label_name"].value_counts()
    for label in LABEL_ORDER:
        if label in label_counts.index:
            count = int(label_counts[label])
            print(f"{label:<10} {count:>6} 条    占比 {count / len(df):.2%}")
    other_counts = label_counts.drop(index=[l for l in LABEL_ORDER if l in label_counts.index])
    for label, count in other_counts.items():
        print(f"{label:<10} {count:>6} 条    占比 {count / len(df):.2%}")

    print("\n--- 缺失值统计 ---")
    missing = df[["label", "content"]].isna().sum()
    for column, count in missing.items():
        print(f"{column:<10} 缺失 {count:>6} 条    缺失率 {count / len(df):.2%}")

    print("\n--- 清洗前文本样例 ---")
    for content in df["content"].dropna().head(3):
        print(f"  · {content}")


# --------------------------------------------------------------------------- #
# 2. 数据清洗
# --------------------------------------------------------------------------- #

# 预编译正则，避免在循环中重复编译带来的额外开销
RE_HTML_TAG = re.compile(r"<[^>]+>")
RE_URL = re.compile(r"(https?://\S+|www\.\S+)")
RE_EMAIL = re.compile(r"\S+@\S+\.\S+")
RE_INVISIBLE = re.compile(r"[\u200b-\u200f\ufeff\xa0]")  # 零宽字符与不间断空格
RE_KEEP_CHARS = re.compile(r"[^\u4e00-\u9fa5a-zA-Z0-9,.;:!?，。；：！？、]")
RE_MULTI_SPACE = re.compile(r"\s+")


def clean_text(raw_text: str) -> str:
    """清洗单条评论文本。

    清洗规则：
        1. 去除 HTML 标签并反转义 HTML 实体
        2. 去除 URL、邮箱、零宽字符
        3. 去除表情、特殊符号等非文本字符（保留中英文、数字与常用标点）
        4. 合并连续空白并去除首尾空格

    说明：中文文本词间无空格，因此上述删除动作一律以空串替换而非空格，
          避免清洗后中文语句被割裂成空格分隔的片段。

    :param raw_text: 原始文本
    :return: 清洗后的文本，空值返回空字符串
    """
    if not isinstance(raw_text, str):
        return ""
    text = html.unescape(raw_text)
    text = RE_HTML_TAG.sub("", text)
    text = RE_URL.sub("", text)
    text = RE_EMAIL.sub("", text)
    text = RE_INVISIBLE.sub("", text)
    text = RE_KEEP_CHARS.sub("", text)
    text = RE_MULTI_SPACE.sub(" ", text)
    return text.strip()


def clean_dataset(df: pd.DataFrame) -> tuple:
    """对整个数据集执行清洗：去空值、去重复、文本规范化。

    :param df: 原始 DataFrame
    :return: (清洗后的 DataFrame, 清洗统计信息 dict)
    """
    print_section("二、数据清洗")
    total = len(df)
    stats = {"原始样本数": total}

    df = df.copy()
    df["content"] = df["content"].fillna("").map(clean_text)

    # 去除清洗后为空的样本
    df = df[df["content"].str.len() > 0]
    stats["空值/空白样本数"] = total - len(df)
    print(f"去除空值及空白样本后剩余：{len(df)} 条（剔除 {stats['空值/空白样本数']} 条）")

    # 按文本内容去重，保留首次出现的记录
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["content"], keep="first")
    stats["重复样本数"] = before_dedup - len(df)
    print(f"去除重复评论后剩余：{len(df)} 条（剔除 {stats['重复样本数']} 条）")

    # 去除标签缺失的样本
    before_label_drop = len(df)
    df = df[df["label_name"].notna() & (df["label_name"] != "UNKNOWN")]
    stats["标签异常样本数"] = before_label_drop - len(df)
    print(f"去除标签异常样本后剩余：{len(df)} 条（剔除 {stats['标签异常样本数']} 条）")

    df = df.reset_index(drop=True)
    stats["有效样本数"] = len(df)
    stats["整体保留率"] = f"{len(df) / total:.2%}" if total else "0.00%"
    print(f"清洗完成，有效样本数：{len(df)} 条，整体保留率：{stats['整体保留率']}")

    print("\n--- 清洗后文本样例 ---")
    for content in df["content"].head(3):
        print(f"  · {content}")

    return df, stats


# --------------------------------------------------------------------------- #
# 3. 文本长度分布统计
# --------------------------------------------------------------------------- #

def analyze_text_length(df: pd.DataFrame) -> pd.DataFrame:
    """统计文本长度（字符数）与分词后词数，并打印分布指标。

    :param df: 清洗后的 DataFrame
    :return: 新增 char_length、word_count 列的 DataFrame
    """
    print_section("三、文本长度分布统计")
    df = df.copy()
    df["char_length"] = df["content"].str.len()
    df["word_count"] = df["content"].map(lambda text: len(list(jieba.cut(text))))

    for column, title in (("char_length", "字符长度"), ("word_count", "分词词数")):
        series = df[column]
        print(f"\n--- {title}统计 ---")
        print(f"最小值：{series.min():>8.0f}    最大值：{series.max():>8.0f}")
        print(f"平均值：{series.mean():>8.2f}    标准差：{series.std():>8.2f}")
        print(f"中位数：{series.median():>8.2f}")
        percentiles = series.quantile([0.25, 0.5, 0.75, 0.9, 0.95, 0.99])
        print("分位数：", "  ".join(f"P{int(q * 100)}={v:.0f}" for q, v in percentiles.items()))

    print("\n--- 各情感类别平均字符长度 ---")
    grouped = df.groupby("label_name")["char_length"].agg(["count", "mean", "median"])
    for label in LABEL_ORDER:
        if label in grouped.index:
            row = grouped.loc[label]
            print(f"{label:<10} 样本 {int(row['count']):>6} 条    "
                  f"平均长度 {row['mean']:>7.2f}    中位长度 {row['median']:>7.2f}")

    return df


def plot_length_distribution(df: pd.DataFrame, save_path: str) -> None:
    """绘制文本长度分布直方图，并标注均值与中位数。

    :param df: 含 char_length 列的 DataFrame
    :param save_path: 图片保存路径
    """
    series = df["char_length"]
    mean_value, median_value = series.mean(), series.median()

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT), dpi=PLOT_DPI)
    # bins 依据样本量自适应，避免长尾导致分布图形状失真
    bins = min(60, max(10, int(series.nunique() ** 0.5)))
    ax.hist(series, bins=bins, color="#4C72B0", edgecolor="white", alpha=0.85)
    ax.axvline(mean_value, color="#C44E52", linestyle="--", linewidth=1.5,
               label=f"均值 = {mean_value:.1f}")
    ax.axvline(median_value, color="#55A868", linestyle="-.", linewidth=1.5,
               label=f"中位数 = {median_value:.1f}")
    ax.set_title("评论文本长度分布直方图")
    ax.set_xlabel("字符长度")
    ax.set_ylabel("样本数量")
    ax.legend()
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    fig.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)
    print(f"[信息] 长度分布直方图已保存：{save_path}")


# --------------------------------------------------------------------------- #
# 4. 词频统计与可视化
# --------------------------------------------------------------------------- #

def is_valid_token(token: str) -> bool:
    """判断分词结果是否为有效关键词。

    过滤规则：停用词、单字、纯数字、纯标点与空白词。
    """
    token = token.strip()
    if len(token) < 2:                      # 过滤单字与空白
        return False
    if token.lower() in STOPWORDS:          # 过滤停用词
        return False
    if token.isdigit():                     # 过滤纯数字
        return False
    if not re.search(r"[\u4e00-\u9fa5a-zA-Z]", token):  # 过滤纯标点
        return False
    return True


def count_word_frequency(df: pd.DataFrame) -> dict:
    """按情感类别统计词频，同时给出全量词频。

    :param df: 清洗后的 DataFrame
    :return: {类别名或 "ALL": Counter(词 -> 频次)}
    """
    counters = {label: Counter() for label in LABEL_ORDER if label in set(df["label_name"])}
    counters["ALL"] = Counter()

    for content, label_name in zip(df["content"], df["label_name"]):
        tokens = [token for token in jieba.cut(content) if is_valid_token(token)]
        counters["ALL"].update(tokens)
        if label_name in counters:
            counters[label_name].update(tokens)
    return counters


def report_top_words(counters: dict, top_n: int) -> None:
    """在控制台打印各类别高频词 Top-N 及词频占比。"""
    print_section(f"四、词频统计（各类别高频词 Top{top_n}）")
    for name, counter in counters.items():
        total = sum(counter.values())
        title = "全量数据" if name == "ALL" else f"{name} 类别"
        print(f"\n--- {title} 高频词 Top{top_n}（有效词总量 {total}）---")
        if not counter:
            print("  （该类别无有效词，已跳过）")
            continue
        for rank, (word, freq) in enumerate(counter.most_common(top_n), start=1):
            print(f"  {rank:>2}. {word:<10} 频次 {freq:>6}    占比 {freq / total:.2%}")


def plot_top_words(counters: dict, top_n: int, save_path: str) -> None:
    """绘制各类别高频词 Top-N 水平柱状图（子图排布）。

    :param counters: count_word_frequency 返回的词典
    :param top_n: 展示的高频词数量
    :param save_path: 图片保存路径
    """
    panels = [(name, counter) for name, counter in counters.items() if counter]
    if not panels:
        print("[警告] 无有效词频数据，跳过高频词可视化。")
        return

    columns = 2 if len(panels) > 1 else 1
    rows = (len(panels) + columns - 1) // columns
    fig, axes = plt.subplots(rows, columns, figsize=(7.0 * columns, 4.2 * rows), dpi=PLOT_DPI)
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for ax, (name, counter) in zip(axes, panels):
        words, freqs = zip(*counter.most_common(top_n))
        # 水平柱状图按频次升序排布，最热词显示在顶部
        ax.barh(list(words)[::-1], list(freqs)[::-1], color="#4C72B0", alpha=0.85)
        title = "全量数据" if name == "ALL" else f"{name} 类别"
        ax.set_title(f"{title} 高频词 Top{len(words)}")
        ax.set_xlabel("词频")
        ax.grid(axis="x", linestyle=":", alpha=0.5)

    # 隐藏多余的空子图
    for ax in axes[len(panels):]:
        ax.axis("off")

    fig.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)
    print(f"[信息] 高频词柱状图已保存：{save_path}")


# --------------------------------------------------------------------------- #
# 5. 数据集划分与保存
# --------------------------------------------------------------------------- #

def split_dataset(df: pd.DataFrame) -> tuple:
    """按 70%/20%/10% 分层抽样划分训练集、验证集与测试集。

    先切分出测试集，再从剩余数据中切分验证集，两次切分均以标签分层，
    保证三个子集的类别分布与原始数据一致。

    :param df: 清洗后的 DataFrame
    :return: (train_df, val_df, test_df)
    """
    print_section("五、数据集划分（分层抽样）")
    # 样本数过少时分层抽样会报错，此处给出明确提示
    min_class_size = df["label_name"].value_counts().min()
    if min_class_size < 2:
        raise ValueError(
            f"最小类别样本数仅为 {min_class_size}，无法执行分层抽样，请补充数据后重试。"
        )

    train_df, temp_df = train_test_split(
        df,
        test_size=VAL_RATIO + TEST_RATIO,
        stratify=df["label_name"],
        random_state=RANDOM_STATE,
    )
    # 在剩余数据中按比例切分验证集与测试集：0.2 / 0.3 = 2/3
    val_df, test_df = train_test_split(
        temp_df,
        test_size=TEST_RATIO / (VAL_RATIO + TEST_RATIO),
        stratify=temp_df["label_name"],
        random_state=RANDOM_STATE,
    )

    for name, subset in (("训练集", train_df), ("验证集", val_df), ("测试集", test_df)):
        ratio = len(subset) / len(df)
        print(f"{name}：{len(subset):>6} 条    占比 {ratio:.2%}")

    print("\n--- 各子集类别分布 ---")
    print(f"{'类别':<10}{'训练集':>10}{'验证集':>10}{'测试集':>10}")
    for label in LABEL_ORDER:
        row = []
        for subset in (train_df, val_df, test_df):
            count = int((subset["label_name"] == label).sum())
            row.append(f"{count}({count / len(subset):.1%})")
        if int((df["label_name"] == label).sum()) == 0:
            continue
        print(f"{label:<10}{row[0]:>14}{row[1]:>14}{row[2]:>14}")

    return train_df, val_df, test_df


def save_datasets(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame,
                  output_dir: str) -> None:
    """将划分后的数据集保存为 CSV 文件（UTF-8-SIG 编码，便于 Excel 打开）。

    :param train_df: 训练集
    :param val_df: 验证集
    :param test_df: 测试集
    :param output_dir: 输出目录
    """
    print_section("六、结果保存")
    os.makedirs(output_dir, exist_ok=True)
    # 落盘字段固定为 label 与 content，便于直接用于模型训练
    for file_name, subset in (("train.csv", train_df), ("val.csv", val_df), ("test.csv", test_df)):
        save_path = os.path.join(output_dir, file_name)
        subset[["label", "content"]].to_csv(save_path, index=False, encoding="utf-8-sig")
        print(f"[信息] 已保存：{save_path}（{len(subset)} 条）")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="ChnSentiCorp 中文评论数据清洗与 EDA 分析")
    parser.add_argument("--input", default=os.path.join("data", "ChnSentiCorp.csv"),
                        help="输入数据集 CSV 路径，默认 data/ChnSentiCorp.csv")
    parser.add_argument("--output", default="output",
                        help="输出目录，默认 output")
    parser.add_argument("--top-n", type=int, default=TOP_N,
                        help=f"高频词展示数量，默认 {TOP_N}")
    return parser.parse_args()


def main() -> None:
    """脚本主流程：加载 → 清洗 → 长度分析 → 词频分析 → 划分 → 保存。"""
    args = parse_args()

    jieba.setLogLevel(20)          # 降低 jieba 日志级别，避免初始化信息干扰输出
    setup_matplotlib()

    figure_dir = os.path.join(args.output, "figures")
    os.makedirs(figure_dir, exist_ok=True)

    # 1. 数据加载与基本信息
    raw_df = load_dataset(args.input)
    raw_df = normalize_labels(raw_df)
    show_basic_info(raw_df)

    # 2. 数据清洗
    clean_df, _ = clean_dataset(raw_df)
    if clean_df.empty:
        print("[错误] 清洗后无有效样本，流程终止。")
        return

    # 3. 文本长度分布
    clean_df = analyze_text_length(clean_df)
    plot_length_distribution(clean_df, os.path.join(figure_dir, "text_length_distribution.png"))

    # 4. 词频统计与可视化
    counters = count_word_frequency(clean_df)
    report_top_words(counters, args.top_n)
    plot_top_words(counters, args.top_n, os.path.join(figure_dir, "top_words_by_label.png"))

    # 5. 数据集划分
    train_df, val_df, test_df = split_dataset(clean_df)

    # 6. 结果保存
    save_datasets(train_df, val_df, test_df, args.output)

    print_section("处理完成")
    print(f"EDA 图表目录：{figure_dir}")
    print(f"数据集目录：{args.output}")


if __name__ == "__main__":
    main()
