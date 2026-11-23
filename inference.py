# -*- coding: utf-8 -*-
"""中文评论智能分析系统 —— 热点词提取与情感推理封装。

功能概览：
    1. 热点词提取：基于 jieba 分词 + sklearn TfidfVectorizer 的 TF-IDF 算法，
       对批量评论提取 TopN 热点关键词及其权重，并过滤停用词、单字、纯数字与纯标点。
    2. 情感推理封装：SentimentInferencer 类一次性加载标签、tokenizer 与模型，
       提供单条（predict_single）与批量（predict_batch）推理入口，
       统一处理空文本、超长文本等边界情况，并统计推理耗时。

标签体系（与 train.py 导出产物 labels.txt 及后端 ModelInferenceService 约定一致）：
    0 -> POSITIVE（正面）
    1 -> NEGATIVE（负面）
    2 -> NEUTRAL （中性）

--------------------------------------------------------------------------
依赖与准备
--------------------------------------------------------------------------
1. 环境依赖：
       pip install torch transformers scikit-learn jieba numpy

2. 模型目录需由训练脚本 train.py 生成（默认 model/bert-zh-sentiment-v1）：
       python train.py --data-dir output --epochs 3
   目录内需包含 vocab.txt、labels.txt，以及模型权重（HuggingFace 权重
   model.safetensors / pytorch_model.bin 优先，缺失时回退 TorchScript model.pt）。

--------------------------------------------------------------------------
使用示例（Python 调用）
--------------------------------------------------------------------------
>>> from inference import SentimentInferencer, extract_keywords
>>> # 1) 热点词提取：返回按权重降序的 Top20
>>> extract_keywords(["物流很快，包装也很用心", "质量不错，物流一般"], top_n=20)
[{'word': '物流', 'weight': 0.5231, 'wordCount': 2}, ...]
>>> # 2) 情感推理：模型仅加载一次，运行期复用
>>> inferencer = SentimentInferencer()                       # 默认读取 model/bert-zh-sentiment-v1
>>> inferencer.predict_single("这家店服务态度非常差")
{'label': 'NEGATIVE', 'score': 0.9812, 'needReview': False, 'inferTimeMs': 42.5}
>>> inferencer.predict_batch(["太棒了，非常满意", "", "一般般吧"])
[{'label': 'POSITIVE', ...}, {'label': 'NEUTRAL', 'score': 0.0, 'needReview': True, ...}, ...]

--------------------------------------------------------------------------
使用示例（命令行）
--------------------------------------------------------------------------
       python inference.py --top-n 20                              # 运行内置演示数据
       python inference.py --text "物流很快，包装很用心"           # 单条快速推理
       python inference.py --model-dir model/bert-zh-sentiment-v1 --device cpu
"""

import argparse
import json
import logging
import os
import re
import time
from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence, Set

import jieba
import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import BertForSequenceClassification, BertTokenizer

# --------------------------------------------------------------------------- #
# 一、全局配置
# --------------------------------------------------------------------------- #

# 模型目录：与 train.py 的 EXPORT_DIR（model/bert-zh-sentiment-v1）保持一致
DEFAULT_MODEL_DIR = os.path.join("model", "bert-zh-sentiment-v1")

# 标签顺序：顺序即标签 id，必须与 labels.txt 保持一致
LABEL_ORDER = ["POSITIVE", "NEGATIVE", "NEUTRAL"]

# 文本最大长度（token 数），超出部分截断；与训练时的 MAX_LENGTH 一致
MAX_LENGTH = 128

# 单条文本清洗后的最大字符数，超出截断（与详细设计 TextPreprocessor.clean 一致）
MAX_TEXT_CHARS = 512

# 热点词默认返回数量
DEFAULT_TOP_N = 20

# 批量推理默认批大小（与详细设计 batch_size 默认值一致）
DEFAULT_BATCH_SIZE = 32

# 低置信度阈值：score 低于该值时标记为待人工复核
LOW_CONFIDENCE_THRESHOLD = 0.60

# HuggingFace 权重文件名候选：存在其一即按 HuggingFace 格式加载模型
HF_WEIGHT_FILES = ("model.safetensors", "pytorch_model.bin")

# 兜底标签：空文本或推理异常时输出
FALLBACK_LABEL = "NEUTRAL"

# 中文停用词表（内置常用词，避免依赖外部文件即可运行）
# 说明：与 data_preprocessing_eda.py 中的 STOPWORDS 保持同一份词表，
#      修改时请同步两处，保证 EDA 词频统计与热点词提取口径一致。
STOPWORDS = set("""
的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己
这 那 他 她 它 们 这个 那个 这些 那些 什么 怎么 这样 那样 因为 所以 但是 而且 如果
还 就是 只是 已经 可以 应该 能够 需要 觉得 感觉 知道 时候 现在 还是 比较 非常 特别
真的 其实 有点 一点 一下 一直 一些 一样 之后 之前 的话 东西 问题 情况 方面 我们 你们
他们 大家 这里 那里 哪里 谁 为什么 怎样 如何 于是 然后 另外 其中 以及 或者 并且 不过
虽然 然而 因此 从而 对于 关于 根据 通过 由于 为了 除了 甚至 而且 只是 只有 无论 不管
并且 什么 各位 谢谢 请 让 给 被 把 从 向 对 与 及 等 更 最 太 再 又 才 只 没 好 嗯 哦 啊
""".split())

# 预编译正则
RE_HAS_CONTENT = re.compile(r"[\u4e00-\u9fa5a-zA-Z]")      # 至少含一个中文或字母
RE_INVISIBLE = re.compile(r"[\u200b-\u200f\ufeff\xa0]")    # 零宽字符与不间断空格
RE_MULTI_SPACE = re.compile(r"\s+")                        # 连续空白

logger = logging.getLogger("inference")


# --------------------------------------------------------------------------- #
# 二、通用工具
# --------------------------------------------------------------------------- #

def resolve_device(device: str) -> torch.device:
    """解析推理设备。

    :param device: "auto" 自动选择（有 GPU 用 GPU，否则 CPU），也可指定 "cpu" / "cuda"
    :return: torch.device 实例
    """
    if device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def print_section(title: str) -> None:
    """打印统一的分段标题，提升演示输出可读性。"""
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


# --------------------------------------------------------------------------- #
# 三、热点词提取（jieba 分词 + TF-IDF）
# --------------------------------------------------------------------------- #

def is_valid_token(token: str, stopwords: Set[str]) -> bool:
    """判断分词结果是否为有效关键词。

    过滤规则：停用词、长度小于 2 的单字、纯数字、纯标点与空白词。

    :param token: jieba 分词得到的单个词
    :param stopwords: 停用词集合
    :return: 是否为有效词
    """
    token = token.strip()
    if len(token) < 2:                                    # 过滤单字与空白词
        return False
    if token.lower() in stopwords:                        # 过滤停用词
        return False
    if token.isdigit():                                   # 过滤纯数字
        return False
    if not RE_HAS_CONTENT.search(token):                  # 过滤纯标点/纯符号
        return False
    return True


def tokenize_text(text: str, stopwords: Set[str]) -> List[str]:
    """对单条评论文本分词并过滤无效词。

    :param text: 评论文本（非字符串返回空列表，保证调用方无需额外判空）
    :param stopwords: 停用词集合
    :return: 有效词列表
    """
    if not isinstance(text, str):
        return []
    return [token for token in jieba.cut(text) if is_valid_token(token, stopwords)]


def extract_keywords(texts: Sequence[str],
                     top_n: int = DEFAULT_TOP_N,
                     stopwords: Optional[Iterable[str]] = None) -> List[Dict[str, object]]:
    """基于 TF-IDF 提取批量评论的 TopN 热点关键词。

    处理流程：
        1. jieba 分词 + 停用词/单字/数字/标点过滤（全语料仅分词一次，结果复用）；
        2. 统计每个词在全语料的累计词频（wordCount）；
        3. 以分词结果构造文档，交给 TfidfVectorizer 计算 TF-IDF；
        4. 取各词的平均 TF-IDF 作为热度权重，按权重降序截断 TopN。

    :param texts: 评论文本列表，可为空
    :param top_n: 返回的热点词数量，默认 20
    :param stopwords: 自定义停用词集合；为 None 时使用内置停用词表
    :return: [{"word": 关键词, "weight": TF-IDF 权重, "wordCount": 词频}, ...]，按权重降序；
             无有效词时返回空列表
    """
    if not texts:
        logger.warning("输入文本列表为空，无法提取热点词。")
        return []

    stopword_set = set(STOPWORDS) if stopwords is None else set(stopwords)

    # 1) 分词：jieba 只执行一次，后续词频统计与 TF-IDF 均复用该结果
    tokenized_docs = [tokenize_text(text, stopword_set) for text in texts]

    # 2) 词频统计：全语料累计出现次数，对应 KeywordVO.wordCount
    counter: Counter = Counter()
    for tokens in tokenized_docs:
        counter.update(tokens)

    # 3) 构造语料：以空格连接词序列；全部词被过滤的评论不参与计算，
    #    避免产生空文档导致 TfidfVectorizer 抛出 empty vocabulary 异常
    corpus = [" ".join(tokens) for tokens in tokenized_docs if tokens]
    if not corpus:
        logger.warning("分词后无有效词，无法提取热点词。")
        return []

    # 4) TF-IDF 计算：输入已是空格分隔的词序列，直接按空格切分，
    #    避免 TfidfVectorizer 内部重复执行 jieba 分词
    vectorizer = TfidfVectorizer(
        tokenizer=str.split,     # 词序列已切分完成，按空格还原为词
        token_pattern=None,      # 显式置空，避免 sklearn 对未生效参数的告警
        lowercase=False,         # 中文无需小写化
        preprocessor=None,       # 不再改动已清洗的词序列
    )
    try:
        matrix = vectorizer.fit_transform(corpus)
    except ValueError as error:  # 词表为空等异常情况
        logger.warning("TF-IDF 计算失败：%s", error)
        return []

    # 平均 TF-IDF 作为热度权重：与"求和"仅相差常数倍，排序结果一致，取值更直观
    weights = np.asarray(matrix.mean(axis=0)).ravel()
    vocabulary = vectorizer.get_feature_names_out()

    # 5) 权重降序排序并截断 TopN（权重保留 4 位小数，与 KeywordVO.weight 精度一致）
    ranked = sorted(
        (
            {
                "word": str(word),
                "weight": round(float(weight), 4),
                "wordCount": int(counter.get(word, 0)),
            }
            for word, weight in zip(vocabulary, weights)
        ),
        key=lambda item: item["weight"],
        reverse=True,
    )
    return ranked[:max(0, top_n)]


# --------------------------------------------------------------------------- #
# 四、情感推理封装类
# --------------------------------------------------------------------------- #

class SentimentInferencer:
    """中文评论情感三分类推理封装类。

    职责：
        1. 初始化时一次性加载标签、tokenizer 与模型，运行期常驻内存复用；
        2. 提供单条（predict_single）与批量（predict_batch）推理入口；
        3. 统一处理空文本、超长文本等边界情况，单条异常不影响其余样本；
        4. 统计推理耗时（单条耗时与批量平均耗时）。

    标签体系：0 -> POSITIVE，1 -> NEGATIVE，2 -> NEUTRAL（与 labels.txt 一致）。
    """

    def __init__(self,
                 model_dir: str = DEFAULT_MODEL_DIR,
                 device: str = "auto",
                 max_length: int = MAX_LENGTH,
                 batch_size: int = DEFAULT_BATCH_SIZE,
                 low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
                 labels: Optional[Sequence[str]] = None):
        """加载模型与 tokenizer（仅执行一次）。

        :param model_dir: 模型目录（train.py 导出的目录）
        :param device: 推理设备："auto" / "cpu" / "cuda"
        :param max_length: 文本最大 token 数，超出截断
        :param batch_size: 批量推理时的批大小
        :param low_confidence_threshold: 低置信度阈值，score 低于该值标记 needReview
        :param labels: 自定义标签顺序；为 None 时读取 model_dir/labels.txt
        :raises FileNotFoundError: 模型文件缺失
        :raises RuntimeError: tokenizer 或模型加载失败
        """
        # 0) 模型目录校验：目录缺失时立即报错，避免加载库抛出难以理解的异常
        if not os.path.isdir(model_dir):
            raise FileNotFoundError(
                f"模型目录不存在：{os.path.abspath(model_dir)}\n"
                f"请先运行训练脚本生成模型：python train.py --data-dir output"
            )

        self.model_dir = model_dir
        self.device = resolve_device(device)
        self.max_length = int(max_length)
        self.batch_size = max(1, int(batch_size))
        self.low_confidence_threshold = float(low_confidence_threshold)

        load_start = time.perf_counter()

        # 1) 标签顺序：labels.txt 为标签 id 的唯一来源，与后端保持同一口径
        self.labels: List[str] = list(labels) if labels else self._load_labels(model_dir)

        # 2) tokenizer：从模型目录加载（依赖 vocab.txt 与 tokenizer_config.json）
        self.tokenizer: BertTokenizer = self._load_tokenizer(model_dir)

        # 3) 模型：HuggingFace 权重优先，缺失时回退 TorchScript（model.pt）
        self.model, self.is_traced = self._load_model(model_dir)

        # 4) 标签数与模型输出维度一致性校验，避免标签错位导致结果不可用
        num_labels = getattr(getattr(self.model, "config", None), "num_labels", len(self.labels))
        if num_labels != len(self.labels):
            logger.warning("labels.txt 标签数(%d)与模型输出维度(%d)不一致，请检查模型导出产物。",
                           len(self.labels), num_labels)

        logger.info("模型加载完成：%s | 设备 %s | 格式 %s | 标签 %s | 耗时 %.2fs",
                    os.path.abspath(model_dir), self.device,
                    "TorchScript" if self.is_traced else "HuggingFace",
                    " -> ".join(f"{i}={name}" for i, name in enumerate(self.labels)),
                    time.perf_counter() - load_start)

    # ------------------------------------------------------------------ #
    # 4.1 内部加载方法
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_labels(model_dir: str) -> List[str]:
        """读取 labels.txt（每行一个标签，行号即标签 id）。

        :param model_dir: 模型目录
        :return: 标签列表；文件缺失或为空时回退为默认标签顺序
        """
        labels_path = os.path.join(model_dir, "labels.txt")
        if os.path.exists(labels_path):
            with open(labels_path, "r", encoding="utf-8") as file:
                labels = [line.strip() for line in file if line.strip()]
            if labels:
                return labels
        logger.warning("未找到 %s，回退为默认标签顺序：%s", labels_path, LABEL_ORDER)
        return list(LABEL_ORDER)

    @staticmethod
    def _load_tokenizer(model_dir: str) -> BertTokenizer:
        """加载 BertTokenizer。

        :param model_dir: 模型目录
        :return: BertTokenizer 实例
        """
        try:
            return BertTokenizer.from_pretrained(model_dir)
        except Exception as error:
            raise RuntimeError(
                f"加载 Tokenizer 失败：{model_dir}\n"
                f"原始错误：{error}\n"
                f"请先运行训练脚本生成模型目录：python train.py --data-dir output"
            ) from error

    def _load_model(self, model_dir: str):
        """加载情感分类模型。

        优先加载 HuggingFace 权重（config.json + model.safetensors / pytorch_model.bin），
        权重缺失时回退加载 TorchScript 推理模型（model.pt）。

        :param model_dir: 模型目录
        :return: (模型实例, 是否为 TorchScript 格式)
        """
        has_hf_weight = any(os.path.exists(os.path.join(model_dir, name))
                            for name in HF_WEIGHT_FILES)
        if has_hf_weight:
            try:
                model = BertForSequenceClassification.from_pretrained(model_dir)
            except Exception as error:
                raise RuntimeError(
                    f"加载 HuggingFace 模型失败：{model_dir}\n原始错误：{error}"
                ) from error
            return model.to(self.device).eval(), False

        traced_path = os.path.join(model_dir, "model.pt")
        if os.path.exists(traced_path):
            try:
                model = torch.jit.load(traced_path, map_location=self.device)
            except Exception as error:
                raise RuntimeError(
                    f"加载 TorchScript 模型失败：{traced_path}\n原始错误：{error}"
                ) from error
            return model.eval(), True

        raise FileNotFoundError(
            f"未找到可用模型文件：{model_dir}\n"
            f"期望包含 {' / '.join(HF_WEIGHT_FILES)} 或 model.pt，"
            f"请先运行训练脚本：python train.py --data-dir output"
        )

    # ------------------------------------------------------------------ #
    # 4.2 状态与元信息
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        """模型是否已成功加载（供调用方在发起推理前检查）。"""
        return self.model is not None

    def get_model_info(self) -> Dict[str, object]:
        """获取模型元信息（版本、准确率、导出时间等）。

        优先读取 model_dir/model_info.json（由 train.py 导出），
        文件缺失时返回基础信息，便于调用方统一展示。

        :return: 模型信息字典
        """
        info: Dict[str, object] = {
            "modelDir": os.path.abspath(self.model_dir),
            "labels": list(self.labels),
            "maxLength": self.max_length,
            "device": str(self.device),
            "format": "TorchScript" if self.is_traced else "HuggingFace",
        }
        info_path = os.path.join(self.model_dir, "model_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as file:
                info.update(json.load(file))
        else:
            logger.warning("未找到 %s，仅返回基础模型信息。", info_path)
        return info

    # ------------------------------------------------------------------ #
    # 4.3 文本预处理与结果构造
    # ------------------------------------------------------------------ #

    @staticmethod
    def _clean_text(text) -> str:
        """清洗单条文本，兼容空文本与超长文本。

        处理规则：
            1. 非字符串（None、数字等）返回空串，交由兜底逻辑处理；
            2. 去除零宽字符、不间断空格等不可见字符；
            3. 合并连续空白并去除首尾空白；
            4. 超过 MAX_TEXT_CHARS（512）字符时截断，防止超长文本拖慢推理
               （tokenizer 侧还会按 max_length 二次截断）。

        :param text: 原始文本
        :return: 清洗后的文本，空值/空白返回空字符串
        """
        if not isinstance(text, str):
            return ""
        text = RE_INVISIBLE.sub("", text)
        text = RE_MULTI_SPACE.sub(" ", text).strip()
        return text[:MAX_TEXT_CHARS]

    def _to_result(self, probabilities: np.ndarray) -> Dict[str, object]:
        """将类别概率数组转换为情感结果。

        :param probabilities: 各类别概率数组，长度与标签数一致
        :return: {"label": 标签, "score": 置信度, "needReview": 是否待复核}
        """
        index = int(np.argmax(probabilities))
        # 置信度保留 4 位小数，与数据库 analysis_result.confidence 精度一致
        score = round(float(probabilities[index]), 4)
        label = self.labels[index] if index < len(self.labels) else FALLBACK_LABEL
        return {
            "label": label,
            "score": score,
            # 低置信度兜底：标签保留模型判定值，仅标记待人工复核
            "needReview": score < self.low_confidence_threshold,
        }

    @staticmethod
    def _fallback_result() -> Dict[str, object]:
        """空文本或推理异常时的兜底结果：中性 + 置信度 0 + 待复核。

        与详细设计 5.4「异常容错」约定一致，保证不中断批量任务。
        """
        return {
            "label": FALLBACK_LABEL,
            "score": 0.0,
            "needReview": True,
            "inferTimeMs": 0.0,
        }

    # ------------------------------------------------------------------ #
    # 4.4 模型前向推理
    # ------------------------------------------------------------------ #

    @torch.no_grad()
    def _forward(self, texts: List[str]) -> np.ndarray:
        """对一批文本执行前向推理，返回各类别概率。

        :param texts: 已清洗的非空文本列表
        :return: 形状为 [batch_size, num_labels] 的概率矩阵
        """
        encodings = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,          # 批内动态补齐，减少无效计算
            truncation=True,       # 超长文本按 max_length 截断
            max_length=self.max_length,
        )
        input_ids = encodings["input_ids"].to(self.device)
        attention_mask = encodings["attention_mask"].to(self.device)
        # 部分模型不返回 token_type_ids，此处做兼容兜底
        token_type_ids = encodings.get("token_type_ids")
        token_type_ids = (torch.zeros_like(input_ids) if token_type_ids is None
                          else token_type_ids.to(self.device))

        if self.is_traced:
            # TorchScript 模型只接收张量、只返回 logits，需按位置传参
            logits = self.model(input_ids, attention_mask, token_type_ids)
        else:
            logits = self.model(input_ids=input_ids,
                                attention_mask=attention_mask,
                                token_type_ids=token_type_ids).logits

        probabilities = torch.softmax(logits, dim=-1)
        return probabilities.cpu().numpy()

    # ------------------------------------------------------------------ #
    # 4.5 对外推理接口
    # ------------------------------------------------------------------ #

    def predict_single(self, text) -> Dict[str, object]:
        """单条评论情感推理。

        :param text: 评论文本，空值或非字符串返回兜底结果
        :return: {"label": 情感标签, "score": 置信度,
                  "needReview": 是否待复核, "inferTimeMs": 推理耗时（毫秒）}
        """
        return self.predict_batch([text])[0]

    def predict_batch(self, text_list: Sequence[str]) -> List[Dict[str, object]]:
        """批量评论情感推理，输出顺序与输入严格一致。

        处理逻辑：
            1. 文本清洗后为空/非字符串的样本直接产出兜底结果，不进入模型；
            2. 其余样本按 batch_size 分批前向推理，摊薄单条开销；
            3. 整个批次失败时回退为逐条推理，单条异常仅影响该条，
               保证单条异常不中断批量任务。

        :param text_list: 评论文本列表，可为空
        :return: 与输入等长、顺序一致的结果列表，每项结构同 predict_single
        """
        if not text_list:
            return []

        method_start = time.perf_counter()
        results: List[Optional[Dict[str, object]]] = [None] * len(text_list)

        # 1) 清洗与边界处理：空文本直接兜底，不进入模型
        pending: List[tuple] = []
        for index, raw_text in enumerate(text_list):
            cleaned = self._clean_text(raw_text)
            if not cleaned:
                results[index] = self._fallback_result()
            else:
                pending.append((index, cleaned))

        # 2) 分批前向推理
        for start in range(0, len(pending), self.batch_size):
            chunk = pending[start:start + self.batch_size]
            chunk_start = time.perf_counter()
            try:
                probabilities = self._forward([text for _, text in chunk])
                # 批内均摊单条耗时，对应 analysis_result.infer_time_ms
                per_item_ms = round((time.perf_counter() - chunk_start) * 1000 / len(chunk), 2)
                for (index, _), probability in zip(chunk, probabilities):
                    result = self._to_result(probability)
                    result["inferTimeMs"] = per_item_ms
                    results[index] = result
            except Exception as error:
                # 3) 批次整体失败时逐条重试，隔离单条异常
                logger.warning("批次推理失败（%d 条），回退为逐条推理：%s", len(chunk), error)
                for index, text in chunk:
                    item_start = time.perf_counter()
                    try:
                        result = self._to_result(self._forward([text])[0])
                    except Exception as item_error:
                        logger.warning("第 %d 条样本推理异常：%s", index, item_error)
                        result = self._fallback_result()
                    result["inferTimeMs"] = round((time.perf_counter() - item_start) * 1000, 2)
                    results[index] = result

        # 4) 耗时统计：总耗时与平均单条耗时
        total_ms = (time.perf_counter() - method_start) * 1000
        logger.info("批量推理完成：%d 条（空文本 %d 条）| 总耗时 %.2f ms | 平均 %.2f ms/条",
                    len(text_list), len(text_list) - len(pending), total_ms,
                    total_ms / len(text_list))
        return [item for item in results]  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# 五、使用示例（命令行演示）
# --------------------------------------------------------------------------- #

# 内置演示数据：覆盖正面、负面、中性、空文本与超长文本等场景
DEMO_TEXTS = [
    "物流很快，包装也很用心，产品质量非常不错，下次还会再来买。",
    "快递太慢了，客服态度也很差，东西还有破损，非常失望。",
    "东西收到了，还不错，跟描述基本一致，价格也还行。",
    "",
    "价格实惠，性价比很高，就是发货速度稍微慢了一点点。",
    "这家店的服务态度真的让我很无语，退款还一直推诿，差评。",
    "一般般吧，没什么特别的感觉，能用就行。",
]


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="中文评论热点词提取与情感推理演示（TF-IDF + BERT 三分类）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR,
                        help="模型目录（train.py 导出产物所在目录）")
    parser.add_argument("--device", default="auto",
                        help="推理设备：auto / cpu / cuda")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                        help="热点词返回数量")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="批量推理的批大小")
    parser.add_argument("--text", default=None,
                        help="指定单条文本做快速推理；不指定则运行内置演示数据")
    parser.add_argument("--texts-file", default=None,
                        help="指定评论文本文件（每行一条），用于批量推理与热点词提取")
    return parser.parse_args()


def load_texts_from_file(file_path: str) -> List[str]:
    """从文本文件读取评论（每行一条，自动尝试常见中文编码）。

    :param file_path: 文本文件路径
    :return: 评论文本列表（已去除空行）
    """
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            with open(file_path, "r", encoding=encoding) as file:
                return [line.strip() for line in file if line.strip()]
        except UnicodeDecodeError:
            continue  # 编码不匹配，继续尝试下一种
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"无法识别的文件编码：{file_path}")


def demo_extract_keywords(texts: Sequence[str], top_n: int) -> None:
    """演示：提取并打印 TopN 热点词及权重。"""
    print_section(f"一、热点词提取（TF-IDF Top{top_n}）")
    keywords = extract_keywords(texts, top_n=top_n)
    if not keywords:
        print("未提取到有效热点词。")
        return
    print(f"{'排名':<6}{'关键词':<12}{'权重':>10}{'词频':>8}")
    print("-" * 40)
    for rank, item in enumerate(keywords, start=1):
        print(f"{rank:<6}{item['word']:<12}{item['weight']:>10.4f}{item['wordCount']:>8}")


def demo_sentiment_inference(model_dir: str, device: str, batch_size: int,
                             texts: Sequence[str]) -> None:
    """演示：加载模型并执行单条与批量推理。"""
    print_section("二、情感推理")
    try:
        # 模型仅在初始化时加载一次，后续所有推理复用该实例
        inferencer = SentimentInferencer(model_dir=model_dir, device=device, batch_size=batch_size)
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[提示] 模型加载失败，已跳过情感推理演示：\n{error}")
        return

    print(f"模型信息：{json.dumps(inferencer.get_model_info(), ensure_ascii=False)}")

    # 单条推理
    single_text = texts[0]
    single_start = time.perf_counter()
    single_result = inferencer.predict_single(single_text)
    total_ms = (time.perf_counter() - single_start) * 1000
    print(f"\n--- 单条推理 ---\n文本：{single_text}")
    print(f"结果：{single_result}（含加载后首次调用总耗时 {total_ms:.2f} ms）")

    # 批量推理：输出顺序与输入一致，空文本已在类内部兜底
    print(f"\n--- 批量推理（{len(texts)} 条）---")
    batch_start = time.perf_counter()
    results = inferencer.predict_batch(list(texts))
    batch_ms = (time.perf_counter() - batch_start) * 1000
    for text, result in zip(texts, results):
        preview = text if len(text) <= 24 else text[:24] + "..."
        print(f"  [{result['label']:<8} score={result['score']:<6} "
              f"review={str(result['needReview']):<5} {result['inferTimeMs']:>7.2f}ms] {preview}")
    print(f"\n批量总耗时：{batch_ms:.2f} ms，平均 {batch_ms / max(len(texts), 1):.2f} ms/条")


def main() -> None:
    """演示主流程：热点词提取 + 情感推理（单条 / 批量）。"""
    args = parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-5s | %(message)s",
                        datefmt="%H:%M:%S")
    jieba.setLogLevel(20)  # 降低 jieba 日志级别，避免初始化信息干扰输出

    # 准备文本：优先读取指定文件，其次使用命令行单条文本，最后使用内置演示数据
    if args.texts_file:
        texts = load_texts_from_file(args.texts_file)
        print_section("数据加载")
        print(f"已从 {args.texts_file} 读取 {len(texts)} 条评论。")
    elif args.text:
        texts = [args.text]
    else:
        texts = list(DEMO_TEXTS)

    # 1) 热点词提取
    demo_extract_keywords(texts, args.top_n)

    # 2) 情感推理
    demo_sentiment_inference(args.model_dir, args.device, args.batch_size, texts)


if __name__ == "__main__":
    main()
