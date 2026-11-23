# -*- coding: utf-8 -*-
"""中文评论情感三分类 BERT 微调训练脚本。

功能概览：
    1. 加载 data_preprocessing_eda.py 划分好的 train/val/test 数据集
    2. 使用 BertTokenizer 分词编码（最大长度 128），构建自定义 Dataset 与 DataLoader
    3. 基于 bert-base-chinese 微调 BertForSequenceClassification，输出三分类
    4. 训练循环：每个 epoch 训练 + 验证，打印损失与准确率
    5. 测试集评估：准确率 / 精确率 / 召回率 / F1 + 混淆矩阵
    6. 保存最优模型权重与 tokenizer，并导出为可推理格式（TorchScript）

标签体系（与后端 ModelInferenceService 的 labels.txt 约定保持一致）：
    0 -> POSITIVE（正面）
    1 -> NEGATIVE（负面）
    2 -> NEUTRAL （中性）

--------------------------------------------------------------------------
运行说明
--------------------------------------------------------------------------
1. 环境依赖（建议 Python 3.8+，仅 CPU 即可运行）：
       pip install torch transformers scikit-learn pandas numpy matplotlib
   本次交付模型实测环境：Python 3.14 + torch 2.15.0(CPU) + transformers 5.22.2

2. 准备数据（两步）：
   a) 先做标签修正与数据集重建（NEUTRAL 由「无情感线索」定义，不再是 3 星评分）：
          python prepare_dataset_v2.py --scheme cue --dst output_v3
   b) 再用重建后的划分训练（--data-dir 指向 output_v3）

3. 开始训练（默认超参即交付配方：lr 5e-5、批量 32、5 轮、max_length 128、CPU）：
       python train.py --data-dir output_v3 --epochs 5 --max-length 128 --batch-size 32 --lr 5e-5

4. 常用参数覆盖示例：
       python train.py --epochs 8 --ema-decay 0.999      # 开 EMA，需更多算力
       python train.py --model-name ./pretrained/chinese_roberta_L-4_H-256   # 本地模型目录
       python train.py --device cuda                     # 有显卡时切换
       python train.py --no-calibrate                    # 关闭温度校准与类别偏置

5. 首次运行会自动从 HuggingFace 下载 uer/chinese_roberta_L-4_H-256。
   国内网络下载失败时，可先设置镜像后重试：
       Windows PowerShell:  $env:HF_ENDPOINT="https://hf-mirror.com"
       Linux/macOS:         export HF_ENDPOINT=https://hf-mirror.com
   或手动下载模型后通过 --model-name 指定本地目录。

6. 输出产物：
       train.log                          训练日志（同时打印到控制台）
       model/bert-zh-sentiment-v1/model.pt            TorchScript 推理模型（后端 DJL 加载）
       model/bert-zh-sentiment-v1/vocab.txt           词表（后端 DJL 加载）
       model/bert-zh-sentiment-v1/labels.txt          标签顺序（后端 DJL 加载）
       model/bert-zh-sentiment-v1/config.json         HuggingFace 模型配置
       model/bert-zh-sentiment-v1/model.safetensors   最优权重（HuggingFace 格式）
       model/bert-zh-sentiment-v1/best_model.pt       最优轮次权重检查点
       model/bert-zh-sentiment-v1/model_info.json     模型版本、准确率、导出时间
       model/bert-zh-sentiment-v1/evaluation_report.txt 测试集评估报告
       output/figures/confusion_matrix.png            混淆矩阵图（需 matplotlib）
"""

import argparse
import html
import json
import logging
import math
import os
import random
import re
import time
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
)
from torch.nn.utils.rnn import pad_sequence
from torch.utils.data import DataLoader, Dataset
from transformers import BertForSequenceClassification, BertTokenizer
from transformers import get_cosine_schedule_with_warmup
from transformers import logging as hf_logging

# --------------------------------------------------------------------------- #
# 一、全局超参数配置（直接修改此处即可调整训练行为）
# --------------------------------------------------------------------------- #

# 预训练模型：默认在线名称，也可传入本地目录路径
PRETRAINED_MODEL_NAME = "uer/chinese_roberta_L-4_H-256"

# 模型版本号，与设计文档 ModelInfoVO.modelVersion 保持一致
MODEL_VERSION = "bert-zh-sentiment-v3"

# 文本最大长度（超出截断，不足在批次内动态补齐）
# 必须与后端 application.yml 的 app.model.max-length 保持一致（128），
# 否则训练/推理的截断口径不同会直接损失精度。
MAX_LENGTH = 128

# 训练超参数（默认值即本次交付模型的训练配方）
BATCH_SIZE = 32                 # 训练批大小（CPU 环境下 32 实测吞吐最佳）
EVAL_BATCH_SIZE = 32            # 验证/测试批大小，不参与反向传播可适当放大
LEARNING_RATE = 5e-5            # AdamW 学习率，小模型微调用 3e-5~5e-5
WEIGHT_DECAY = 0.01             # AdamW 权重衰减
NUM_EPOCHS = 5                  # 训练轮次（原 3 轮明显欠拟合，第 3 轮验证指标才跃升）
MAX_GRAD_NORM = 1.0             # 梯度裁剪阈值，防止梯度爆炸
WARMUP_RATIO = 0.05             # 线性 warmup 占总步数比例，抑制初期破坏性更新
LABEL_SMOOTHING = 0.05          # 标签平滑，缓解噪声标签过拟合、避免过度自信
EMA_DECAY = 0.0                 # 权重滑动平均衰减系数；0 表示关闭（CPU 预算下省一次验证）
EARLY_STOP_PATIENCE = 2         # 验证集指标连续多少轮不提升则提前停止
SEED = 42                       # 全局随机种子，保证实验可复现

# 是否启用类别重加权（sqrt-inverse）：重标注后 NEUTRAL 样本偏少，
# 直接用反频率会过度惩罚中性类，故采用平方根反频率做温和平衡。
USE_CLASS_WEIGHT = True

# 模型保存与早停依据的验证集指标（可选 "accuracy" 或 "f1"）
BEST_MODEL_METRIC = "f1"

# 运行设备："auto" 自动选择（有 GPU 用 GPU，否则 CPU），也可强制指定 "cpu" / "cuda"
DEVICE = "auto"

# 默认路径配置
DATA_DIR = "output_v3"                              # 数据集目录（含 train/val/test.csv）
EXPORT_DIR = os.path.join("model", MODEL_VERSION)  # 模型导出目录
LOG_FILE = "train.log"                           # 日志文件

# 标签定义：顺序即标签 id 顺序，必须与 labels.txt 保持一致
LABEL_ORDER = ["POSITIVE", "NEGATIVE", "NEUTRAL"]

# 标签别名映射：兼容原始语料中的 0/1/2 数值标签与中英文标签名
# 说明：ChnSentiCorp 原始语料常见取值为 0/1，按 0=负面、1=正面 处理，
#      与 data_preprocessing_eda.py 中的映射约定保持一致。
LABEL_ALIASES = {
    "positive": "POSITIVE", "pos": "POSITIVE", "1": "POSITIVE",
    "front": "POSITIVE", "正面": "POSITIVE", "积极": "POSITIVE",
    "negative": "NEGATIVE", "neg": "NEGATIVE", "0": "NEGATIVE",
    "负面": "NEGATIVE", "消极": "NEGATIVE",
    "neutral": "NEUTRAL", "neu": "NEUTRAL", "2": "NEUTRAL",
    "中性": "NEUTRAL", "客观": "NEUTRAL",
}

# 待识别的列名候选（与预处理脚本保持一致，兼容多种数据源表头）
CONTENT_COLUMN_CANDIDATES = ["content", "text", "comment", "评论", "内容", "评价", "留言"]
LABEL_COLUMN_CANDIDATES = ["label", "sentiment", "标签", "情感"]

# 评估图输出目录
FIGURE_DIR = os.path.join("output", "figures")

# --------------------------------------------------------------------------- #
# 二、日志配置
# --------------------------------------------------------------------------- #

logger = logging.getLogger("train")


def setup_logging(log_file: str) -> None:
    """配置日志：同时输出到控制台与文件，便于训练过程追溯。

    :param log_file: 日志文件路径
    """
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-5s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（UTF-8，追加模式）
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def print_section(title: str) -> None:
    """打印统一的分段标题，提升日志可读性。"""
    logger.info("")
    logger.info("=" * 76)
    logger.info(title)
    logger.info("=" * 76)


# --------------------------------------------------------------------------- #
# 三、通用工具函数
# --------------------------------------------------------------------------- #

def set_seed(seed: int) -> None:
    """固定各类随机种子，保证训练结果可复现。

    :param seed: 随机种子
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def resolve_device(device: str) -> torch.device:
    """解析运行设备。

    :param device: "auto" 表示自动选择，其余取值透传给 torch.device
    :return: torch.device 实例
    """
    if device == "auto":
        # CPU 训练为本脚本的默认目标环境，有显卡时自动提速
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def resolve_column(df: pd.DataFrame, standard_name: str, candidates: list) -> str:
    """在 DataFrame 中定位目标列名，支持标准名与候选别名。

    :param df: 待处理的 DataFrame
    :param standard_name: 标准列名，如 "content"
    :param candidates: 候选列名列表（按优先级排列）
    :return: 实际命中的列名
    """
    for name in candidates:
        if name in df.columns:
            return name
    raise KeyError(
        f"未找到列 '{standard_name}'，当前文件列名为：{list(df.columns)}，"
        f"请确认数据集格式（期望包含 {candidates}）。"
    )


def read_csv_auto(file_path: str) -> pd.DataFrame:
    """读取 CSV 文件，自动尝试常见中文编码。

    :param file_path: CSV 文件路径
    :return: 原始 DataFrame
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"数据文件不存在：{file_path}\n"
            f"请先运行数据预处理脚本生成数据集，例如：\n"
            f"    python data_preprocessing_eda.py --input data/ChnSentiCorp.csv --output output"
        )

    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return pd.read_csv(file_path, encoding=encoding)
        except UnicodeDecodeError:
            continue  # 编码不匹配，继续尝试下一种
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"无法识别的文件编码：{file_path}")


# 文本清洗正则：与 data_preprocessing_eda.clean_text 保持同一口径，
# 避免训练入口与预处理脚本对同一份数据给出不同文本表示。
RE_HTML_TAG = re.compile(r"<[^>]+>")
RE_URL = re.compile(r"(https?://\S+|www\.\S+)")
RE_EMAIL = re.compile(r"\S+@\S+\.\S+")
RE_INVISIBLE = re.compile(r"[\u200b-\u200f\ufeff\xa0]")
RE_KEEP_CHARS = re.compile(r"[^\u4e00-\u9fa5a-zA-Z0-9,.;:!?，。；：！？、]")
RE_MULTI_SPACE = re.compile(r"\s+")
RE_REPEAT_PUNCT = re.compile(r"([!?！？。，,.~～])\1{2,}")


def clean_text(raw_text) -> str:
    """清洗单条评论文本（去 HTML/URL/邮箱/零宽字符，压缩重复标点）。

    原实现只做 strip()，会把网页残留标签、乱码符号等噪声直接送入分词器，
    既浪费 token 预算，也会引入与情感无关的虚假特征。

    :param raw_text: 原始文本
    :return: 清洗后的文本
    """
    if not isinstance(raw_text, str):
        return ""
    text = html.unescape(raw_text)
    text = RE_HTML_TAG.sub("", text)
    text = RE_URL.sub("", text)
    text = RE_EMAIL.sub("", text)
    text = RE_INVISIBLE.sub("", text)
    text = RE_KEEP_CHARS.sub("", text)
    text = RE_REPEAT_PUNCT.sub(r"\1", text)
    text = RE_MULTI_SPACE.sub(" ", text)
    return text.strip()


def normalize_label(value) -> str:
    """将原始标签归一化为 POSITIVE / NEGATIVE / NEUTRAL。

    兼容数值型（0/1/2，含整数与浮点）与字符串型（含中英文标签名）输入。

    :param value: 原始标签值
    :return: 归一化后的标签名；无法识别时返回 None
    """
    if pd.isna(value):
        return None

    # 数值型标签（含 numpy 整型/浮点型）优先转成整数字符串，
    # 避免 1.0 这类浮点写法无法命中别名映射表
    if isinstance(value, (int, np.integer)):
        key = str(int(value))
    elif isinstance(value, (float, np.floating)) and float(value).is_integer():
        key = str(int(value))
    else:
        key = str(value).strip().lower()

    return LABEL_ALIASES.get(key, key.upper())


def label_to_id(label_name: str) -> int:
    """将标签名转换为数值 id（未识别的标签返回 -1，由调用方决定是否丢弃）。"""
    return LABEL_ORDER.index(label_name) if label_name in LABEL_ORDER else -1


# --------------------------------------------------------------------------- #
# 四、数据集加载与自定义 Dataset
# --------------------------------------------------------------------------- #

def load_split(file_path: str, split_name: str) -> pd.DataFrame:
    """加载单个数据划分文件，统一列名并归一化标签。

    :param file_path: CSV 文件路径
    :param split_name: 划分名称（train/val/test），仅用于日志提示
    :return: 含 content、label_name、label_id 三列的 DataFrame
    """
    df = read_csv_auto(file_path)
    df = df.dropna(how="all").reset_index(drop=True)

    # 统一列名，保证后续流程只依赖标准列名
    content_col = resolve_column(df, "content", CONTENT_COLUMN_CANDIDATES)
    label_col = resolve_column(df, "label", LABEL_COLUMN_CANDIDATES)
    df = df.rename(columns={content_col: "content", label_col: "label"})

    # 文本清洗：去空值、转字符串、统一清洗规则、去首尾空白
    df["content"] = df["content"].fillna("").map(clean_text)
    df = df[df["content"].str.len() > 0]

    # 标签归一化并映射为 id
    df["label_name"] = df["label"].map(normalize_label)
    unknown = sorted(set(df.loc[~df["label_name"].isin(LABEL_ORDER), "label_name"].dropna().tolist()))
    if unknown:
        logger.warning("[%s] 存在无法识别的标签取值 %s，对应样本已被剔除。", split_name, unknown)
    df = df[df["label_name"].isin(LABEL_ORDER)].copy()

    df["label_id"] = df["label_name"].map(label_to_id).astype(int)
    df = df.reset_index(drop=True)

    logger.info("加载 %-5s 集：%s，共 %d 条", split_name, file_path, len(df))
    return df


def split_dataframe(df: pd.DataFrame) -> tuple:
    """在缺少验证集/测试集时，按 70%/20%/10% 分层抽样自动划分。

    :param df: 全量 DataFrame（需含 label_name 列）
    :return: (train_df, val_df, test_df)
    """
    from sklearn.model_selection import train_test_split

    # 分层抽样要求每个类别至少 2 条样本
    min_class_size = df["label_name"].value_counts().min()
    if min_class_size < 2:
        logger.warning("最小类别样本数仅为 %d，退化为随机划分（不分层）。", min_class_size)
        stratify_col = None
    else:
        stratify_col = df["label_name"]

    train_df, temp_df = train_test_split(
        df, test_size=0.3, stratify=stratify_col, random_state=SEED
    )
    stratify_temp = None if stratify_col is None else temp_df["label_name"]
    val_df, test_df = train_test_split(
        temp_df, test_size=1 / 3, stratify=stratify_temp, random_state=SEED
    )
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


def load_datasets(data_dir: str) -> tuple:
    """加载训练/验证/测试数据集。

    优先读取 data_dir 下的 train.csv / val.csv / test.csv；
    若验证集或测试集缺失，则从已有数据中分层划分补齐。

    :param data_dir: 数据集目录
    :return: (train_df, val_df, test_df)
    """
    print_section("一、数据集加载")
    train_path = os.path.join(data_dir, "train.csv")
    val_path = os.path.join(data_dir, "val.csv")
    test_path = os.path.join(data_dir, "test.csv")

    if not os.path.exists(train_path):
        raise FileNotFoundError(
            f"未找到训练集：{train_path}\n"
            f"请先运行数据预处理脚本：\n"
            f"    python data_preprocessing_eda.py --input data/ChnSentiCorp.csv --output {data_dir}"
        )

    train_df = load_split(train_path, "train")

    if os.path.exists(val_path) and os.path.exists(test_path):
        val_df = load_split(val_path, "val")
        test_df = load_split(test_path, "test")
    else:
        logger.warning("未找到 val.csv / test.csv，将基于训练集按 70/20/10 自动分层划分。")
        train_df, val_df, test_df = split_dataframe(train_df)

    # 打印各子集类别分布，便于确认样本是否均衡
    for name, subset in (("训练集", train_df), ("验证集", val_df), ("测试集", test_df)):
        counts = subset["label_name"].value_counts().to_dict()
        detail = "  ".join(f"{lb}={counts.get(lb, 0)}" for lb in LABEL_ORDER)
        logger.info("%s类别分布：%s", name, detail)
        if len(counts) < len(LABEL_ORDER):
            logger.warning("%s仅包含 %d 个类别，缺失类别在训练中不会被预测。", name, len(counts))

    return train_df, val_df, test_df


class SentimentDataset(Dataset):
    """情感三分类数据集。

    在初始化阶段一次性完成全部文本的 tokenize，训练时直接按下标取张量，
    避免每个 epoch 重复分词，可显著降低 CPU 环境下的训练耗时。
    """

    def __init__(self, dataframe: pd.DataFrame, tokenizer: BertTokenizer, max_length: int):
        """
        :param dataframe: 含 content、label_id 两列的 DataFrame
        :param tokenizer: BertTokenizer 实例
        :param max_length: 文本最大长度，超出截断
        """
        self.texts = dataframe["content"].tolist()
        self.labels = dataframe["label_id"].tolist()
        self.max_length = max_length

        # 批量分词编码：padding=False 表示不在此处补齐，
        # 由 collate_fn 在批次内按最长样本动态补齐，减少无效计算
        encodings = tokenizer(
            self.texts,
            truncation=True,
            max_length=max_length,
            padding=False,
            return_attention_mask=True,
            return_token_type_ids=True,
        )
        self.input_ids = encodings["input_ids"]
        self.attention_mask = encodings["attention_mask"]
        # 部分模型（如 RoBERTa）不返回 token_type_ids，此处做兼容兜底
        self.token_type_ids = encodings.get("token_type_ids", [[0] * len(ids) for ids in self.input_ids])

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int) -> dict:
        return {
            "input_ids": torch.tensor(self.input_ids[index], dtype=torch.long),
            "attention_mask": torch.tensor(self.attention_mask[index], dtype=torch.long),
            "token_type_ids": torch.tensor(self.token_type_ids[index], dtype=torch.long),
            "label": torch.tensor(self.labels[index], dtype=torch.long),
        }


def build_collate_fn(pad_token_id: int):
    """构建批次组装函数：将同一批次内的样本动态补齐到该批次的最大长度。

    :param pad_token_id: 补齐位置使用的 token id
    :return: 可直接传入 DataLoader 的 collate_fn
    """

    def collate_fn(batch: list) -> dict:
        return {
            "input_ids": pad_sequence([item["input_ids"] for item in batch],
                                      batch_first=True, padding_value=pad_token_id),
            "attention_mask": pad_sequence([item["attention_mask"] for item in batch],
                                           batch_first=True, padding_value=0),
            "token_type_ids": pad_sequence([item["token_type_ids"] for item in batch],
                                           batch_first=True, padding_value=0),
            "labels": torch.stack([item["label"] for item in batch]),
        }

    return collate_fn


def build_dataloaders(train_df, val_df, test_df, tokenizer, batch_size, eval_batch_size, max_length):
    """构建训练/验证/测试 DataLoader。

    :return: (train_loader, val_loader, test_loader)
    """
    collate_fn = build_collate_fn(tokenizer.pad_token_id)

    train_dataset = SentimentDataset(train_df, tokenizer, max_length)
    val_dataset = SentimentDataset(val_df, tokenizer, max_length)
    test_dataset = SentimentDataset(test_df, tokenizer, max_length)

    # 训练集打乱顺序；验证/测试集保持原顺序以便结果与原始数据对齐
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True,
                              collate_fn=collate_fn, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=eval_batch_size, shuffle=False,
                            collate_fn=collate_fn, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=eval_batch_size, shuffle=False,
                             collate_fn=collate_fn, num_workers=0)

    logger.info("DataLoader 构建完成：训练 %d 批 / 验证 %d 批 / 测试 %d 批",
                len(train_loader), len(val_loader), len(test_loader))
    return train_loader, val_loader, test_loader


# --------------------------------------------------------------------------- #
# 五、模型构建
# --------------------------------------------------------------------------- #

def build_tokenizer(model_name_or_path: str) -> BertTokenizer:
    """加载 BertTokenizer。

    :param model_name_or_path: 预训练模型名称或本地目录路径
    :return: BertTokenizer 实例
    """
    try:
        tokenizer = BertTokenizer.from_pretrained(model_name_or_path)
    except Exception as error:  # 网络受限等场景给出明确的排查指引
        raise RuntimeError(
            f"加载 Tokenizer 失败：{model_name_or_path}\n"
            f"原始错误：{error}\n"
            f"若为网络问题，可设置镜像后重试：$env:HF_ENDPOINT=\"https://hf-mirror.com\"，"
            f"或手动下载模型后通过 --model-name 指定本地目录。"
        ) from error
    return tokenizer


def build_model(model_name_or_path: str, num_labels: int, device: torch.device) -> BertForSequenceClassification:
    """加载 BERT 三分类模型。

    :param model_name_or_path: 预训练模型名称或本地目录路径
    :param num_labels: 分类类别数（三分类）
    :param device: 运行设备
    :return: 已迁移到目标设备的模型
    """
    try:
        model = BertForSequenceClassification.from_pretrained(
            model_name_or_path,
            num_labels=num_labels,
            # 显式声明标签映射，导出的 config.json 中会保留该信息
            id2label={i: name for i, name in enumerate(LABEL_ORDER)},
            label2id={name: i for i, name in enumerate(LABEL_ORDER)},
            # 微调都会重新初始化分类头，允许分类层尺寸与原检查点不一致
            # （如原检查点为二分类，或仅含预训练权重而无分类头）
            ignore_mismatched_sizes=True,
            # 正则化：小模型 + 1.3 万样本，略提高 dropout 可抑制末期过拟合
            hidden_dropout_prob=0.2,
            attention_probs_dropout_prob=0.1,
        )
    except Exception as error:
        raise RuntimeError(
            f"加载预训练模型失败：{model_name_or_path}\n"
            f"原始错误：{error}\n"
            f"若为网络问题，请参考脚本头部「运行说明」中的镜像配置方式。"
        ) from error

    model.to(device)
    return model


# --------------------------------------------------------------------------- #
# 六、训练与验证
# --------------------------------------------------------------------------- #

class ModelEMA:
    """权重指数滑动平均（EMA）。

    小数据集微调时，末期参数会在最优点附近抖动；对参数做滑动平均可等效为
    在参数空间做集成，通常能带来 0.5~1.5 个百分点的稳定提升，且不增加推理成本
    （评估时把 EMA 权重写回模型即可）。
    """

    def __init__(self, model: torch.nn.Module, decay: float):
        """
        :param model: 需要跟踪的模型
        :param decay: 衰减系数，越接近 1 越平滑
        """
        self.decay = decay
        self.shadow = {
            name: parameter.detach().clone()
            for name, parameter in model.named_parameters() if parameter.requires_grad
        }

    @torch.no_grad()
    def update(self, model: torch.nn.Module) -> None:
        """用当前参数更新滑动平均。"""
        for name, parameter in model.named_parameters():
            if name in self.shadow:
                self.shadow[name].mul_(self.decay).add_(parameter.detach(), alpha=1 - self.decay)

    def apply_to(self, model: torch.nn.Module) -> None:
        """将滑动平均权重写入模型（原地替换）。"""
        for name, parameter in model.named_parameters():
            if name in self.shadow:
                parameter.data.copy_(self.shadow[name])


def train_one_epoch(model, data_loader, optimizer, criterion, scheduler, ema, device,
                    epoch, total_epochs):
    """执行一个 epoch 的训练。

    :return: (平均训练损失, 训练准确率)
    """
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for step, batch in enumerate(data_loader, start=1):
        # 将批次数据迁移到目标设备
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        token_type_ids = batch["token_type_ids"].to(device)
        labels = batch["labels"].to(device)

        optimizer.zero_grad()  # 清空上一轮梯度

        # 前向传播：BertForSequenceClassification 内部已包含分类头
        outputs = model(input_ids=input_ids,
                        attention_mask=attention_mask,
                        token_type_ids=token_type_ids)
        logits = outputs.logits

        # 交叉熵损失（含标签平滑与可选的类别权重）
        loss = criterion(logits, labels)
        loss.backward()  # 反向传播

        # 梯度裁剪，抑制梯度爆炸
        torch.nn.utils.clip_grad_norm_(model.parameters(), MAX_GRAD_NORM)
        optimizer.step()  # 参数更新
        scheduler.step()  # 学习率按 cosine 曲线衰减
        if ema is not None:
            ema.update(model)

        # 累计统计量
        total_loss += loss.item() * labels.size(0)
        predictions = torch.argmax(logits, dim=-1)
        correct += (predictions == labels).sum().item()
        total += labels.size(0)

        # 每 20 个批次打印一次进度，便于观察训练状态
        if step % 20 == 0 or step == len(data_loader):
            logger.info("  Epoch %d/%d | 批次 %d/%d | 当前平均损失 %.4f | 学习率 %.2e",
                        epoch, total_epochs, step, len(data_loader),
                        total_loss / total, scheduler.get_last_lr()[0])

    return total_loss / max(total, 1), correct / max(total, 1)


@torch.no_grad()
def evaluate(model, data_loader, criterion, device):
    """在验证集/测试集上评估模型。

    :return: (平均损失, 准确率, 预测标签, 真实标签, 类别概率, logits)
    """
    model.eval()
    total_loss = 0.0
    total = 0
    all_preds = []
    all_labels = []
    all_probs = []
    all_logits = []

    for batch in data_loader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        token_type_ids = batch["token_type_ids"].to(device)
        labels = batch["labels"].to(device)

        outputs = model(input_ids=input_ids,
                        attention_mask=attention_mask,
                        token_type_ids=token_type_ids)
        logits = outputs.logits

        loss = criterion(logits, labels)
        total_loss += loss.item() * labels.size(0)
        total += labels.size(0)

        # softmax 转为概率，便于后续置信度分析与低置信度复核
        probabilities = torch.softmax(logits, dim=-1)
        all_probs.append(probabilities.cpu().numpy())
        all_logits.append(logits.cpu().numpy())
        all_preds.append(torch.argmax(logits, dim=-1).cpu().numpy())
        all_labels.append(labels.cpu().numpy())

    all_preds = np.concatenate(all_preds) if all_preds else np.array([])
    all_labels = np.concatenate(all_labels) if all_labels else np.array([])
    all_probs = np.concatenate(all_probs) if all_probs else np.zeros((0, len(LABEL_ORDER)))
    all_logits = np.concatenate(all_logits) if all_logits else np.zeros((0, len(LABEL_ORDER)))

    accuracy = accuracy_score(all_labels, all_preds) if len(all_labels) else 0.0
    return total_loss / max(total, 1), accuracy, all_preds, all_labels, all_probs, all_logits


# --------------------------------------------------------------------------- #
# 七、评估指标与混淆矩阵
# --------------------------------------------------------------------------- #

def compute_metrics(y_true, y_pred) -> dict:
    """计算准确率、宏平均/加权平均的精确率、召回率与 F1。

    :return: 指标字典
    """
    accuracy = accuracy_score(y_true, y_pred)
    macro = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    weighted = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
    return {
        "accuracy": float(accuracy),
        "macro_precision": float(macro[0]),
        "macro_recall": float(macro[1]),
        "macro_f1": float(macro[2]),
        "weighted_precision": float(weighted[0]),
        "weighted_recall": float(weighted[1]),
        "weighted_f1": float(weighted[2]),
    }


def softmax_with_temperature(logits: np.ndarray, temperature: float) -> np.ndarray:
    """带温度的 softmax：温度 T>1 使分布更平滑（降低置信度），T<1 更尖锐。

    :param logits: 模型原始输出
    :param temperature: 温度系数
    :return: 概率矩阵
    """
    scaled = logits / max(temperature, 1e-6)
    scaled = scaled - scaled.max(axis=1, keepdims=True)
    exp = np.exp(scaled)
    return exp / exp.sum(axis=1, keepdims=True)


def fit_temperature(logits: np.ndarray, y_true: np.ndarray) -> float:
    """在验证集上拟合单一温度系数，最小化负对数似然（NLL）。

    温度校准只改变置信度、不改变 argmax，因此不会影响准确率，
    是「提升平均置信度可信度」的标准后处理手段。

    :return: 最优温度
    """
    best_temperature, best_nll = 1.0, float("inf")
    for temperature in np.arange(0.50, 3.01, 0.01):
        probabilities = softmax_with_temperature(logits, float(temperature))
        nll = log_loss(y_true, probabilities, labels=list(range(len(LABEL_ORDER))))
        if nll < best_nll:
            best_nll, best_temperature = nll, float(temperature)
    return round(best_temperature, 2)


def fit_class_bias(logits: np.ndarray, y_true: np.ndarray, rounds: int = 2) -> np.ndarray:
    """在验证集上做坐标搜索，为每个类别拟合一个加性偏置。

    多分类 argmax 对类别先验不敏感，当某个类别召回偏低时，
    仅需给该类别 logit 加一个常数即可校正决策边界。

    :return: 长度为 num_labels 的偏置向量
    """
    bias = np.zeros(len(LABEL_ORDER), dtype=np.float32)
    best_macro_f1 = f1_score(y_true, np.argmax(logits + bias, axis=1), average="macro")
    for _ in range(rounds):
        improved = False
        for label_id in range(len(LABEL_ORDER)):
            for delta in np.arange(-0.50, 0.51, 0.02):
                candidate = bias.copy()
                candidate[label_id] = float(delta)
                score = f1_score(y_true, np.argmax(logits + candidate, axis=1), average="macro")
                if score > best_macro_f1 + 1e-6:
                    best_macro_f1, bias, improved = score, candidate, True
        if not improved:
            break
    return bias


def expected_calibration_error(probabilities: np.ndarray, y_true: np.ndarray, bins: int = 10) -> float:
    """计算期望校准误差（ECE），衡量置信度与实际准确率的偏离程度。"""
    confidence = probabilities.max(axis=1)
    predictions = probabilities.argmax(axis=1)
    correctness = (predictions == y_true).astype(float)
    ece = 0.0
    boundaries = np.linspace(0.0, 1.0, bins + 1)
    for low, high in zip(boundaries[:-1], boundaries[1:]):
        mask = (confidence > low) & (confidence <= high)
        if mask.sum() == 0:
            continue
        gap = abs(correctness[mask].mean() - confidence[mask].mean())
        ece += gap * mask.sum() / len(confidence)
    return float(ece)


def confidence_stats(probabilities: np.ndarray) -> dict:
    """统计平均置信度、低置信度占比与 ECE（不含真实标签时仅返回前两项）。"""
    if len(probabilities) == 0:
        return {"mean_confidence": 0.0, "low_confidence_ratio": 0.0}
    confidence = probabilities.max(axis=1)
    return {
        "mean_confidence": float(confidence.mean()),
        "low_confidence_ratio": float((confidence < 0.60).mean()),
    }


def display_width(text: str) -> int:
    """计算字符串在等宽终端中的显示宽度（中文等全角字符占 2 列，其余占 1 列）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad_display(text: str, width: int, align: str = "left") -> str:
    """按终端显示宽度补齐字符串。

    中文字符等全角字符在等宽终端中占 2 个字符宽度，直接用 str.ljust/rjust
    会导致含中文的表头与纯数字列错位，此处按显示宽度补齐。

    :param text: 待补齐文本
    :param width: 目标显示宽度
    :param align: "left" 左对齐，"right" 右对齐
    :return: 补齐后的字符串
    """
    padding = max(0, width - display_width(text))
    return " " * padding + text if align == "right" else text + " " * padding


def format_confusion_matrix(cm: np.ndarray, labels: list) -> str:
    """将混淆矩阵格式化为对齐的文本表格。

    :param cm: 混淆矩阵（行=真实类别，列=预测类别）
    :param labels: 类别名称列表
    :return: 可直接打印/落盘的字符串
    """
    cell_width = 12
    lines = ["（行 = 真实类别，列 = 预测类别）", ""]
    lines.append(" " * cell_width
                 + "".join(pad_display(lb, cell_width, "right") for lb in labels)
                 + pad_display("合计", cell_width, "right"))
    for i, label in enumerate(labels):
        row = pad_display(label, cell_width) + "".join(pad_display(str(int(v)), cell_width, "right") for v in cm[i])
        lines.append(row + pad_display(str(int(cm[i].sum())), cell_width, "right"))
    lines.append(pad_display("合计", cell_width)
                 + "".join(pad_display(str(int(v)), cell_width, "right") for v in cm.sum(axis=0))
                 + pad_display(str(int(cm.sum())), cell_width, "right"))
    return "\n".join(lines)


def setup_matplotlib_chinese(pyplot_module) -> None:
    """为 matplotlib 配置中文字体，避免图表中的中文显示为方框。

    与 data_preprocessing_eda.py 中的字体配置保持一致，按可用性依次尝试常见中文字体。

    :param pyplot_module: 已导入的 matplotlib.pyplot 模块
    """
    import matplotlib.font_manager

    available_fonts = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for font_name in ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"]:
        if font_name in available_fonts:
            pyplot_module.rcParams["font.sans-serif"] = [font_name]
            break
    else:
        logger.warning("未找到可用中文字体，混淆矩阵图中的中文可能显示异常。")
    pyplot_module.rcParams["axes.unicode_minus"] = False  # 正常显示负号


def save_confusion_matrix_figure(cm: np.ndarray, labels: list, save_path: str) -> None:
    """绘制混淆矩阵热力图（同时标注样本数与行归一化占比）。

    未安装 matplotlib 时仅告警跳过，不影响训练主流程。
    """
    try:
        import matplotlib
        matplotlib.use("Agg")  # 使用非交互后端，避免无显示环境下报错
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("未安装 matplotlib，跳过混淆矩阵图片输出。")
        return

    setup_matplotlib_chinese(plt)

    # 行归一化，真实类别样本数不等时便于横向对比
    normalized = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    size = len(labels)

    fig, ax = plt.subplots(figsize=(2.0 * size + 3.0, 2.0 * size + 1.5), dpi=150)
    image = ax.imshow(normalized, cmap="Blues", vmin=0, vmax=1)

    ax.set_xticks(range(size))
    ax.set_xticklabels(labels)
    ax.set_yticks(range(size))
    ax.set_yticklabels(labels)
    ax.set_xlabel("预测类别")
    ax.set_ylabel("真实类别")
    ax.set_title("测试集混淆矩阵（样本数 / 行占比）")

    for i in range(size):
        for j in range(size):
            ax.text(j, i, f"{int(cm[i, j])}\n{normalized[i, j]:.1%}", ha="center", va="center",
                    fontsize=10, color="white" if normalized[i, j] > 0.5 else "black")

    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    fig.savefig(save_path)
    plt.close(fig)
    logger.info("混淆矩阵图已保存：%s", save_path)


def report_test_results(y_true, y_pred, probs, export_dir: str,
                         raw_probs: np.ndarray = None, temperature: float = 1.0,
                         class_bias: np.ndarray = None) -> dict:
    """输出测试集完整评估结果，并将报告写入文件。

    :param y_true: 真实标签
    :param y_pred: 校准后的预测标签
    :param probs: 校准后的类别概率
    :param export_dir: 报告输出目录
    :param raw_probs: 校准前的类别概率（用于展示校准前后置信度变化）
    :param temperature: 温度系数
    :param class_bias: 类别偏置
    :return: 指标字典
    """
    print_section("四、测试集评估结果")
    metrics = compute_metrics(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(LABEL_ORDER))))

    # 1) 整体指标
    logger.info("准确率 Accuracy        ：%.4f", metrics["accuracy"])
    logger.info("宏平均 Precision       ：%.4f", metrics["macro_precision"])
    logger.info("宏平均 Recall          ：%.4f", metrics["macro_recall"])
    logger.info("宏平均 F1              ：%.4f", metrics["macro_f1"])
    logger.info("加权平均 Precision     ：%.4f", metrics["weighted_precision"])
    logger.info("加权平均 Recall        ：%.4f", metrics["weighted_recall"])
    logger.info("加权平均 F1            ：%.4f", metrics["weighted_f1"])

    # 2) 分类报告（各类别精确率/召回率/F1/样本数）
    report_text = classification_report(
        y_true, y_pred, labels=list(range(len(LABEL_ORDER))),
        target_names=LABEL_ORDER, digits=4, zero_division=0,
    )
    logger.info("\n各类别详细指标：\n%s", report_text)

    # 3) 混淆矩阵
    cm_text = format_confusion_matrix(cm, LABEL_ORDER)
    logger.info("混淆矩阵：\n%s", cm_text)

    # 4) 置信度与校准指标
    calibrated = confidence_stats(probs)
    raw = confidence_stats(raw_probs) if raw_probs is not None else None
    ece_calibrated = expected_calibration_error(probs, y_true) if len(probs) else 0.0
    ece_raw = expected_calibration_error(raw_probs, y_true) if raw_probs is not None else 0.0

    if raw is not None:
        logger.info("校准前：平均置信度 %.4f  低置信度占比 %.2f%%  ECE %.4f",
                    raw["mean_confidence"], raw["low_confidence_ratio"] * 100, ece_raw)
    logger.info("校准后：平均置信度 %.4f  低置信度占比 %.2f%%  ECE %.4f（T=%.2f）",
                calibrated["mean_confidence"], calibrated["low_confidence_ratio"] * 100,
                ece_calibrated, temperature)
    if class_bias is not None:
        logger.info("类别偏置：%s", np.round(class_bias, 2).tolist())

    # 5) 落盘评估报告
    os.makedirs(export_dir, exist_ok=True)
    report_path = os.path.join(export_dir, "evaluation_report.txt")
    with open(report_path, "w", encoding="utf-8") as file:
        file.write(f"模型版本：{MODEL_VERSION}\n")
        file.write(f"评估时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        file.write(f"测试样本数：{len(y_true)}\n")
        file.write(f"标签顺序：{LABEL_ORDER}\n\n")
        file.write("【整体指标】\n")
        file.write(f"准确率 Accuracy        ：{metrics['accuracy']:.4f}\n")
        file.write(f"宏平均 Precision       ：{metrics['macro_precision']:.4f}\n")
        file.write(f"宏平均 Recall          ：{metrics['macro_recall']:.4f}\n")
        file.write(f"宏平均 F1              ：{metrics['macro_f1']:.4f}\n")
        file.write(f"加权平均 Precision     ：{metrics['weighted_precision']:.4f}\n")
        file.write(f"加权平均 Recall        ：{metrics['weighted_recall']:.4f}\n")
        file.write(f"加权平均 F1            ：{metrics['weighted_f1']:.4f}\n")
        file.write(f"平均置信度             ：{calibrated['mean_confidence']:.4f}\n")
        file.write(f"低置信度(<0.60)占比    ：{calibrated['low_confidence_ratio']:.4f}\n")
        file.write(f"ECE（校准后）          ：{ece_calibrated:.4f}\n")
        if raw is not None:
            file.write(f"平均置信度（校准前）   ：{raw['mean_confidence']:.4f}\n")
            file.write(f"ECE（校准前）          ：{ece_raw:.4f}\n")
        file.write(f"温度系数 T             ：{temperature}\n")
        if class_bias is not None:
            file.write(f"类别偏置               ：{[round(float(v), 2) for v in class_bias]}\n")
        file.write("\n【各类别详细指标】\n")
        file.write(report_text + "\n")
        file.write("【混淆矩阵】\n")
        file.write(cm_text + "\n")

    metrics["mean_confidence"] = calibrated["mean_confidence"]
    metrics["low_confidence_ratio"] = calibrated["low_confidence_ratio"]
    metrics["ece"] = ece_calibrated
    metrics["temperature"] = temperature
    logger.info("评估报告已保存：%s", report_path)

    return metrics


# --------------------------------------------------------------------------- #
# 八、模型保存与推理格式导出
# --------------------------------------------------------------------------- #

class InferenceWrapper(torch.nn.Module):
    """推理封装：只接收张量、只返回 logits，便于 TorchScript 追踪导出。

    HuggingFace 的模型默认返回 ModelOutput 对象，直接 trace 会得到复杂结构；
    包装后输出为纯张量，后端（DJL）加载时解析更简单。
    """

    def __init__(self, model: BertForSequenceClassification):
        super().__init__()
        self.model = model

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor, token_type_ids: torch.Tensor) -> torch.Tensor:
        outputs = self.model(input_ids=input_ids,
                             attention_mask=attention_mask,
                             token_type_ids=token_type_ids)
        return outputs.logits  # 形状 [batch_size, num_labels]


def save_vocab_file(tokenizer: BertTokenizer, export_dir: str) -> str:
    """按 id 顺序导出标准 BERT 词表文件 vocab.txt（每行一个 token，行号即 token id）。

    说明：不同 transformers 版本的 save_vocabulary()/save_pretrained() 产物命名并不统一
    （v5 起不再生成 vocab.txt），而后端 ModelRepository 固定读取 vocab.txt，
    因此此处按 tokenizer 实际使用的词表映射显式生成，与版本无关。

    注意：写入时强制使用 "\\n" 换行，避免 Windows 下产生 CRLF 导致后端按行读取时
    token 尾部残留 "\\r" 而查不到对应 id。

    :param tokenizer: BertTokenizer 实例
    :param export_dir: 导出目录
    :return: vocab.txt 的完整路径
    """
    vocab_path = os.path.join(export_dir, "vocab.txt")
    # get_vocab() 返回 {token: id}，按 id 升序排列即为词表原始顺序
    ordered_tokens = sorted(tokenizer.get_vocab().items(), key=lambda item: item[1])
    with open(vocab_path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(token for token, _ in ordered_tokens) + "\n")
    return vocab_path


def export_inference_model(model, tokenizer, export_dir: str, metrics: dict,
                           base_model: str, max_length: int) -> None:
    """导出可推理格式模型与配套文件。

    导出内容：
        model.pt            TorchScript 追踪模型（后端 ModelRepository 加载）
        vocab.txt           词表（后端 ModelRepository 加载）
        labels.txt          标签顺序，行号即标签 id（后端 ModelRepository 加载）
        config.json         HuggingFace 模型配置（含 id2label / label2id）
        model.safetensors   最优权重（HuggingFace 格式，可用于 from_pretrained）
        model_info.json     模型版本、准确率、导出时间等元信息

    :param base_model: 实际使用的预训练模型名，写入 model_info.json 的 baseModel
    :param max_length: 实际使用的最大序列长度，写入 model_info.json 的 maxLength
    """
    print_section("五、模型导出")
    os.makedirs(export_dir, exist_ok=True)

    # 1) 保存 HuggingFace 格式权重与配置（可用于二次微调或 from_pretrained 推理）
    model.save_pretrained(export_dir)
    weight_files = [name for name in ("model.safetensors", "pytorch_model.bin")
                    if os.path.exists(os.path.join(export_dir, name))]
    logger.info("HuggingFace 权重与配置已保存：%s（%s / config.json）",
                export_dir, " / ".join(weight_files) or "权重文件")

    # 2) 保存 tokenizer：vocab.txt 供后端加载，tokenizer 配置供 from_pretrained 复用
    vocab_path = save_vocab_file(tokenizer, export_dir)
    tokenizer.save_pretrained(export_dir)
    logger.info("词表已保存：%s（%d 个 token）", vocab_path, tokenizer.vocab_size)

    # 3) 保存标签顺序，行号即标签 id，必须与训练时的 LABEL_ORDER 一致
    labels_path = os.path.join(export_dir, "labels.txt")
    with open(labels_path, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(LABEL_ORDER) + "\n")
    logger.info("标签文件已保存：%s（顺序 %s）", labels_path, " -> ".join(f"{i}={n}" for i, n in enumerate(LABEL_ORDER)))

    # 4) 导出 TorchScript 推理模型
    model.eval()
    wrapper = InferenceWrapper(model).to("cpu").eval()
    dummy = tokenizer(
        "这是一条用于模型导出的示例评论文本。",
        return_tensors="pt",
        max_length=max_length,
        padding="max_length",
        truncation=True,
    )
    dummy_inputs = (dummy["input_ids"], dummy["attention_mask"], dummy["token_type_ids"])

    traced_model = torch.jit.trace(wrapper, dummy_inputs, strict=False)
    traced_model = torch.jit.freeze(traced_model)  # 冻结图，推理更快、体积更小
    model_path = os.path.join(export_dir, "model.pt")
    traced_model.save(model_path)
    logger.info("TorchScript 推理模型已保存：%s（max_length=%d）", model_path, max_length)

    # 5) 校验导出模型与原始模型输出一致，避免导出后精度丢失
    verify_texts = ["太棒了，非常满意！", "很差劲，再也不会来了。", "房间还可以，没什么特别的感觉。"]
    with torch.no_grad():
        verify_batch = tokenizer(verify_texts, return_tensors="pt", max_length=max_length,
                                 padding="max_length", truncation=True)
        eager_logits = wrapper(verify_batch["input_ids"], verify_batch["attention_mask"],
                               verify_batch["token_type_ids"]).numpy()
        traced_logits = traced_model(verify_batch["input_ids"], verify_batch["attention_mask"],
                                     verify_batch["token_type_ids"]).numpy()
    max_diff = float(np.abs(eager_logits - traced_logits).max())
    if max_diff < 1e-3:
        logger.info("导出校验通过：TorchScript 与原始模型最大输出偏差 %.2e", max_diff)
    else:
        logger.warning("导出校验异常：最大输出偏差 %.2e，请检查导出结果！", max_diff)

    # 6) 保存模型元信息，供后端 getModelInfo() 读取
    info = {
        "modelVersion": MODEL_VERSION,
        "baseModel": base_model,
        "numLabels": len(LABEL_ORDER),
        "labels": LABEL_ORDER,
        "maxLength": max_length,
        "accuracy": round(metrics.get("accuracy", 0.0), 4),
        "macroF1": round(metrics.get("macro_f1", 0.0), 4),
        "meanConfidence": round(metrics.get("mean_confidence", 0.0), 4),
        "temperature": metrics.get("temperature", 1.0),
        "exportTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    info_path = os.path.join(export_dir, "model_info.json")
    with open(info_path, "w", encoding="utf-8") as file:
        json.dump(info, file, ensure_ascii=False, indent=2)
    logger.info("模型信息已保存：%s -> %s", info_path, json.dumps(info, ensure_ascii=False))


# --------------------------------------------------------------------------- #
# 九、命令行参数解析
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    """解析命令行参数，未指定时使用脚本顶部的全局配置。"""
    parser = argparse.ArgumentParser(
        description="中文评论情感三分类 BERT 微调训练脚本（optimized recipe）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-dir", default=DATA_DIR,
                        help="数据集目录，需包含 train.csv/val.csv/test.csv")
    parser.add_argument("--export-dir", default=EXPORT_DIR,
                        help="模型导出目录")
    parser.add_argument("--model-name", default=PRETRAINED_MODEL_NAME,
                        help="预训练模型名称或本地目录路径（可传入 v1 权重做热启动）")
    parser.add_argument("--base-model", default=PRETRAINED_MODEL_NAME,
                        help="写入 model_info.json 的基座模型标识")
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS,
                        help="训练轮次")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help="训练批大小")
    parser.add_argument("--eval-batch-size", type=int, default=EVAL_BATCH_SIZE,
                        help="验证/测试批大小")
    parser.add_argument("--lr", type=float, default=LEARNING_RATE,
                        help="AdamW 学习率")
    parser.add_argument("--weight-decay", type=float, default=WEIGHT_DECAY,
                        help="AdamW 权重衰减系数")
    parser.add_argument("--max-length", type=int, default=MAX_LENGTH,
                        help="文本最大长度")
    parser.add_argument("--label-smoothing", type=float, default=LABEL_SMOOTHING,
                        help="标签平滑系数")
    parser.add_argument("--warmup-ratio", type=float, default=WARMUP_RATIO,
                        help="线性 warmup 占比")
    parser.add_argument("--ema-decay", type=float, default=EMA_DECAY,
                        help="EMA 衰减系数，<=0 表示关闭")
    parser.add_argument("--early-stop-patience", type=int, default=EARLY_STOP_PATIENCE,
                        help="早停耐心轮次，<=0 表示关闭")
    parser.add_argument("--no-class-weight", action="store_true",
                        help="关闭类别重加权")
    parser.add_argument("--no-calibrate", action="store_true",
                        help="关闭温度校准与类别偏置调优")
    parser.add_argument("--ablation-tag", default="final",
                        help="实验标签，写入 ablation 记录")
    parser.add_argument("--num-threads", type=int, default=0,
                        help="CPU 训练线程数，0 表示按物理核数自动设置")
    parser.add_argument("--device", default=DEVICE,
                        help="运行设备：auto / cpu / cuda")
    parser.add_argument("--seed", type=int, default=SEED,
                        help="随机种子")
    parser.add_argument("--log-file", default=LOG_FILE,
                        help="日志文件路径")
    return parser.parse_args()


def build_class_weights(train_df: pd.DataFrame, device: torch.device) -> torch.Tensor:
    """按平方根反频率计算类别权重，温和缓解类别不均衡。

    :return: 形状 [num_labels] 的权重张量
    """
    counts = train_df["label_id"].value_counts().reindex(range(len(LABEL_ORDER)), fill_value=0)
    total = counts.sum()
    weights = np.sqrt(total / (len(LABEL_ORDER) * counts.clip(lower=1)))
    weights = weights / weights.mean()
    logger.info("类别计数：%s，类别权重：%s",
                counts.tolist(), [round(float(w), 3) for w in weights])
    return torch.tensor(weights, dtype=torch.float, device=device)


# --------------------------------------------------------------------------- #
# 十、主流程
# --------------------------------------------------------------------------- #

def main() -> None:
    """训练主流程：加载数据 → 构建模型 → 训练 → 校准 → 评估 → 导出。"""
    args = parse_args()
    setup_logging(args.log_file)
    set_seed(args.seed)
    hf_logging.set_verbosity_error()  # 降低 transformers 提示日志级别

    device = resolve_device(args.device)

    print_section("训练配置")
    logger.info("实验标签  ：%s", args.ablation_tag)
    logger.info("预训练模型：%s", args.model_name)
    logger.info("模型版本  ：%s", MODEL_VERSION)
    logger.info("运行设备  ：%s", device)
    logger.info("最大长度  ：%d", args.max_length)
    logger.info("学习率    ：%s（cosine + %.0f%% warmup）", args.lr, args.warmup_ratio * 100)
    logger.info("批大小    ：训练 %d / 评估 %d", args.batch_size, args.eval_batch_size)
    logger.info("训练轮次  ：%d（早停耐心 %d）", args.epochs, args.early_stop_patience)
    logger.info("标签平滑  ：%.2f；EMA 衰减：%.4f", args.label_smoothing, args.ema_decay)
    logger.info("随机种子  ：%d", args.seed)
    if device.type == "cpu":
        # 线程数过多会与系统进程争抢物理核，反而变慢；默认按物理核数设置
        cpu_count = os.cpu_count() or 4
        thread_count = args.num_threads if args.num_threads > 0 else max(1, cpu_count // 2)
        torch.set_num_threads(thread_count)
        logger.info("CPU 线程数 ：%d（逻辑核 %d，CPU 训练耗时较长，可用 --epochs 减少轮次快速验证流程）",
                    thread_count, cpu_count)

    # 1) 加载数据集
    train_df, val_df, test_df = load_datasets(args.data_dir)

    # 2) 构建 tokenizer、Dataset 与 DataLoader
    print_section("二、模型与数据加载")
    tokenizer = build_tokenizer(args.model_name)
    logger.info("分词器加载完成，词表大小：%d", tokenizer.vocab_size)

    train_loader, val_loader, test_loader = build_dataloaders(
        train_df, val_df, test_df, tokenizer,
        args.batch_size, args.eval_batch_size, args.max_length,
    )

    # 3) 构建三分类模型
    model = build_model(args.model_name, num_labels=len(LABEL_ORDER), device=device)
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info("模型加载完成：%s，可训练参数量 %.2f M",
                model.__class__.__name__, trainable_params / 1e6)

    # 4) 优化器、调度器与损失函数
    # AdamW：BERT 微调的标准选择；对偏置与 LayerNorm 参数不施加权重衰减
    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_grouped_parameters = [
        {"params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
         "weight_decay": args.weight_decay},
        {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)],
         "weight_decay": 0.0},
    ]
    optimizer = torch.optim.AdamW(optimizer_grouped_parameters, lr=args.lr)

    total_steps = max(1, len(train_loader) * args.epochs)
    scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * args.warmup_ratio),
        num_training_steps=total_steps,
    )

    class_weights = None if args.no_class_weight else build_class_weights(train_df, device)
    criterion = torch.nn.CrossEntropyLoss(
        weight=class_weights,
        label_smoothing=args.label_smoothing,
    )

    ema = ModelEMA(model, args.ema_decay) if args.ema_decay > 0 else None

    # 5) 训练循环：每个 epoch 训练 + 验证，按验证宏 F1 保存最优模型
    print_section("三、开始训练")
    best_metric_value = -1.0
    best_epoch = 0
    best_model_path = os.path.join(args.export_dir, "best_model.pt")
    os.makedirs(args.export_dir, exist_ok=True)
    history = []
    no_improve_epochs = 0

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()

        train_loss, train_acc = train_one_epoch(
            model, train_loader, optimizer, criterion, scheduler, ema, device, epoch, args.epochs
        )
        val_loss, val_acc, val_preds, val_labels, _, val_logits = evaluate(
            model, val_loader, criterion, device
        )
        val_f1 = compute_metrics(val_labels, val_preds)["macro_f1"]

        # EMA 模型评估：训练继续使用原始参数，评估时临时替换为滑动平均权重
        ema_metric = None
        if ema is not None:
            raw_state = {name: parameter.detach().clone()
                         for name, parameter in model.named_parameters()}
            ema.apply_to(model)
            ema_loss, ema_acc, ema_preds, ema_labels, _, _ = evaluate(
                model, val_loader, criterion, device
            )
            ema_f1 = compute_metrics(ema_labels, ema_preds)["macro_f1"]
            ema_metric = {"val_loss": ema_loss, "val_accuracy": ema_acc, "val_macro_f1": ema_f1}
            # 还原原始参数，保证后续 epoch 从正常训练轨迹继续
            with torch.no_grad():
                for name, parameter in model.named_parameters():
                    parameter.data.copy_(raw_state[name])

        # 依据配置的指标选择最优模型（原始模型与 EMA 模型择优）
        candidates = [(val_acc if BEST_MODEL_METRIC == "accuracy" else val_f1, "raw", None)]
        if ema_metric is not None:
            ema_score = (ema_metric["val_accuracy"] if BEST_MODEL_METRIC == "accuracy"
                         else ema_metric["val_macro_f1"])
            candidates.append((ema_score, "ema", ema_metric))
        epoch_metric, source, _ = max(candidates, key=lambda item: item[0])
        elapsed = time.time() - epoch_start

        logger.info("-" * 76)
        logger.info("Epoch %d/%d 完成 | 训练损失 %.4f 训练准确率 %.4f | "
                    "验证损失 %.4f 验证准确率 %.4f 验证宏F1 %.4f | 耗时 %.1fs",
                    epoch, args.epochs, train_loss, train_acc, val_loss, val_acc, val_f1, elapsed)
        if ema_metric is not None:
            logger.info("EMA 验证：损失 %.4f 准确率 %.4f 宏F1 %.4f（本轮择优来源：%s）",
                        ema_metric["val_loss"], ema_metric["val_accuracy"],
                        ema_metric["val_macro_f1"], source)
        logger.info("-" * 76)

        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4), "train_accuracy": round(train_acc, 4),
            "val_loss": round(val_loss, 4), "val_accuracy": round(val_acc, 4),
            "val_macro_f1": round(val_f1, 4),
            "ema_val_accuracy": round(ema_metric["val_accuracy"], 4) if ema_metric else None,
            "ema_val_macro_f1": round(ema_metric["val_macro_f1"], 4) if ema_metric else None,
        })

        if epoch_metric > best_metric_value:
            best_metric_value = epoch_metric
            best_epoch = epoch
            # EMA 更优时先写回 EMA 权重再保存，保证 checkpoint 与验证结果一致
            if source == "ema":
                ema.apply_to(model)
            torch.save({"epoch": epoch, "state_dict": model.state_dict(),
                        "metrics": history[-1], "source": source}, best_model_path)
            if source == "ema":
                with torch.no_grad():
                    for name, parameter in model.named_parameters():
                        parameter.copy_(raw_state[name])
            no_improve_epochs = 0
            logger.info("发现更优模型（%s = %.4f，来源 %s），已保存：%s",
                        BEST_MODEL_METRIC, best_metric_value, source, best_model_path)
        else:
            no_improve_epochs += 1
            if 0 < args.early_stop_patience <= no_improve_epochs:
                logger.info("验证集指标连续 %d 轮未提升，提前停止训练。", no_improve_epochs)
                break

    if best_epoch == 0:
        logger.warning("训练过程中未保存任何模型，请检查数据与超参数设置。")

    # 6) 加载最优权重，并在验证集上拟合温度系数与类别偏置
    if os.path.exists(best_model_path):
        checkpoint = torch.load(best_model_path, map_location=device)
        model.load_state_dict(checkpoint["state_dict"])
        logger.info("已加载第 %d 轮的最优模型权重（验证集 %s = %.4f）",
                    best_epoch, BEST_MODEL_METRIC, best_metric_value)

    _, _, _, val_labels, _, val_logits = evaluate(model, val_loader, criterion, device)
    temperature, class_bias = 1.0, np.zeros(len(LABEL_ORDER), dtype=np.float32)
    if not args.no_calibrate:
        temperature = fit_temperature(val_logits, val_labels)
        class_bias = fit_class_bias(val_logits, val_labels)
        logger.info("校准参数（验证集拟合）：温度 T=%.2f，类别偏置=%s",
                    temperature, np.round(class_bias, 2).tolist())

    # 7) 测试集评估（应用温度校准与类别偏置）
    test_loss, test_acc, _, test_labels, raw_probs, test_logits = evaluate(
        model, test_loader, criterion, device
    )
    calibrated_probs = softmax_with_temperature(test_logits, temperature)
    calibrated_preds = np.argmax(test_logits + class_bias, axis=1)
    logger.info("测试集损失：%.4f    测试集准确率（校准后）：%.4f", test_loss, test_acc)
    metrics = report_test_results(
        test_labels, calibrated_preds, calibrated_probs, args.export_dir,
        raw_probs=raw_probs, temperature=temperature, class_bias=class_bias,
    )

    # 混淆矩阵图（需 matplotlib，缺失时自动跳过）
    cm = confusion_matrix(test_labels, calibrated_preds, labels=list(range(len(LABEL_ORDER))))
    save_confusion_matrix_figure(cm, LABEL_ORDER, os.path.join(FIGURE_DIR, "confusion_matrix.png"))

    # 8) 导出推理模型（TorchScript + 词表 + 标签 + 元信息）
    export_inference_model(model, tokenizer, args.export_dir, metrics,
                           args.base_model, args.max_length)

    # 9) 记录实验轨迹，便于逐项对照优化措施
    ablation = {
        "tag": args.ablation_tag,
        "config": {
            "model": args.base_model, "max_length": args.max_length,
            "epochs": args.epochs, "batch_size": args.batch_size, "lr": args.lr,
            "weight_decay": args.weight_decay, "label_smoothing": args.label_smoothing,
            "warmup_ratio": args.warmup_ratio, "ema_decay": args.ema_decay,
            "early_stop_patience": args.early_stop_patience,
            "class_weight": not args.no_class_weight,
            "calibrate": not args.no_calibrate, "seed": args.seed,
        },
        "best_epoch": best_epoch,
        "history": history,
        "test_metrics": {key: (round(value, 4) if isinstance(value, float) else value)
                         for key, value in metrics.items()},
        "temperature": temperature,
        "class_bias": [round(float(v), 3) for v in class_bias],
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    ablation_path = os.path.join(args.export_dir, f"ablation_{args.ablation_tag}.json")
    with open(ablation_path, "w", encoding="utf-8") as file:
        json.dump(ablation, file, ensure_ascii=False, indent=2)
    logger.info("实验记录已保存：%s", ablation_path)

    # 10) 训练总结
    print_section("训练完成")
    logger.info("最优轮次          ：第 %d 轮（验证集 %s = %.4f）", best_epoch, BEST_MODEL_METRIC, best_metric_value)
    logger.info("测试集准确率      ：%.4f", metrics["accuracy"])
    logger.info("测试集宏平均 F1   ：%.4f", metrics["macro_f1"])
    logger.info("测试集平均置信度  ：%.4f", metrics.get("mean_confidence", 0.0))
    logger.info("模型导出目录      ：%s", os.path.abspath(args.export_dir))
    logger.info("训练日志文件      ：%s", os.path.abspath(args.log_file))
    logger.info("后续推理示例（Python）：")
    logger.info("    model = torch.jit.load(r'%s')", os.path.abspath(os.path.join(args.export_dir, "model.pt")))
    logger.info("    # input_ids/attention_mask/token_type_ids 由 tokenizer 编码后传入，输出三分类 logits")


if __name__ == "__main__":
    main()
