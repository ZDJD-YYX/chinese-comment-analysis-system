package com.example.commentanalysis.ai;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * 关键词提取器（TF-IDF，纯 Java 实现）。
 *
 * <p>由于 JVM 侧没有 jieba，此处采用「中文二元组（bigram）滑动窗口 + 英数字整词」的切分近似方案，
 * 其余流程与 Python 侧 {@code inference.extract_keywords} 及《详细设计说明书》5.5 保持一致：</p>
 * <ol>
 *     <li>切分并过滤停用词、长度小于 2 的单字、纯数字、纯标点；</li>
 *     <li>统计词频 {@code wordCount} 与文档频率 {@code df}（出现的评论篇数）；</li>
 *     <li>权重 {@code weight = tf × idf}，其中 {@code tf = 词频 / 总词数}，
 *         {@code idf = ln(总评论数 / (含该词的评论数 + 1)) + 1}；</li>
 *     <li>按权重降序返回前 TopN。</li>
 * </ol>
 *
 * @author 闫宇星
 */
@Slf4j
@Component
public class KeywordExtractor {

    /** 中文停用词表（与 data_preprocessing_eda.py / inference.py 的 STOPWORDS 保持同一份词表） */
    private static final Set<String> STOPWORDS = new HashSet<>(Arrays.asList(
            "的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己"
                    .split("\\s+")));

    static {
        STOPWORDS.addAll(Arrays.asList(
                ("这 那 他 她 它 们 这个 那个 这些 那些 什么 怎么 这样 那样 因为 所以 但是 而且 如果"
                        + " 还 就是 只是 已经 可以 应该 能够 需要 觉得 感觉 知道 时候 现在 还是 比较 非常 特别"
                        + " 真的 其实 有点 一点 一下 一直 一些 一样 之后 之前 的话 东西 问题 情况 方面 我们 你们"
                        + " 他们 大家 这里 那里 哪里 谁 为什么 怎样 如何 于是 然后 另外 其中 以及 或者 并且 不过"
                        + " 虽然 然而 因此 从而 对于 关于 根据 通过 由于 为了 除了 甚至 只有 无论 不管"
                        + " 各位 谢谢 请 让 给 被 把 从 向 对 与 及 等 更 最 太 再 又 才 只 没 嗯 哦 啊")
                        .split("\\s+")));
    }

    /**
     * 提取语料级 TopN 热点关键词。
     *
     * @param texts 评论文本列表，可为空
     * @param topN  返回条数上限
     * @return 按权重降序的关键词列表；无有效词时返回空列表
     */
    public List<KeywordResult> extract(List<String> texts, int topN) {
        if (texts == null || texts.isEmpty() || topN <= 0) {
            return Collections.emptyList();
        }
        KeywordAccumulator accumulator = new KeywordAccumulator(this);
        accumulator.addAll(texts);
        return accumulator.topN(topN);
    }

    /**
     * 创建增量累加器，供调度器按批累加、任务结束时统一计算 TopN。
     *
     * @return 新的累加器实例
     */
    public KeywordAccumulator newAccumulator() {
        return new KeywordAccumulator(this);
    }

    /**
     * 为每条评论打上关键词标签。
     *
     * <p>先取语料级 TopN 关键词构成候选词集合，再逐条评论挑选其命中该集合的词，
     * 结果以英文逗号拼接，写入 {@code analysis_result.keywords}。</p>
     *
     * @param texts      评论文本列表
     * @param corpusTopN 候选词集合大小
     * @param maxPerText 单条评论关键词数量上限
     * @return 与输入等长的关键词串列表（无命中时为空串）
     */
    public List<String> tagDocuments(List<String> texts, int corpusTopN, int maxPerText) {
        if (texts == null || texts.isEmpty()) {
            return Collections.emptyList();
        }
        Set<String> candidates = new HashSet<>();
        for (KeywordResult keyword : extract(texts, corpusTopN)) {
            candidates.add(keyword.getWord());
        }

        List<String> tags = new ArrayList<>(texts.size());
        for (String text : texts) {
            LinkedHashSet<String> picked = new LinkedHashSet<>();
            if (!candidates.isEmpty()) {
                for (String token : segment(text)) {
                    if (candidates.contains(token)) {
                        picked.add(token);
                        if (picked.size() >= maxPerText) {
                            break;
                        }
                    }
                }
            }
            tags.add(String.join(",", picked));
        }
        return tags;
    }

    /**
     * 中文/英数文本切分与过滤。
     *
     * @param text 文本
     * @return 有效词列表
     */
    public List<String> segment(String text) {
        if (text == null || text.isEmpty()) {
            return Collections.emptyList();
        }
        String normalized = text.toLowerCase(Locale.ROOT);
        List<String> rawTokens = new ArrayList<>();
        StringBuilder cjkRun = new StringBuilder();
        StringBuilder wordRun = new StringBuilder();

        for (int i = 0; i < normalized.length(); ) {
            int codePoint = normalized.codePointAt(i);
            int charCount = Character.charCount(codePoint);
            if (isCjk(codePoint)) {
                flushWord(wordRun, rawTokens);
                cjkRun.appendCodePoint(codePoint);
            } else if (Character.isLetterOrDigit(codePoint)) {
                flushCjk(cjkRun, rawTokens);
                wordRun.appendCodePoint(codePoint);
            } else {
                flushCjk(cjkRun, rawTokens);
                flushWord(wordRun, rawTokens);
            }
            i += charCount;
        }
        flushCjk(cjkRun, rawTokens);
        flushWord(wordRun, rawTokens);

        List<String> tokens = new ArrayList<>(rawTokens.size());
        for (String token : rawTokens) {
            if (isValidToken(token)) {
                tokens.add(token);
            }
        }
        return tokens;
    }

    /**
     * 中文串按二元组滑动窗口切分。
     *
     * @param run 中文连续串缓冲
     * @param out 输出列表
     */
    private void flushCjk(StringBuilder run, List<String> out) {
        if (run.length() == 0) {
            return;
        }
        String text = run.toString();
        if (text.length() == 1) {
            out.add(text);
        } else {
            for (int i = 0; i + 2 <= text.length(); i++) {
                out.add(text.substring(i, i + 2));
            }
        }
        run.setLength(0);
    }

    /**
     * 英数字整词落盘。
     *
     * @param run 英数字缓冲
     * @param out 输出列表
     */
    private void flushWord(StringBuilder run, List<String> out) {
        if (run.length() == 0) {
            return;
        }
        out.add(run.toString());
        run.setLength(0);
    }

    /**
     * 有效词判定：过滤单字、停用词、纯数字与无实义字符的词。
     *
     * @param token 词
     * @return true 表示有效
     */
    private boolean isValidToken(String token) {
        if (token.length() < 2) {
            return false;
        }
        if (STOPWORDS.contains(token)) {
            return false;
        }
        boolean allDigits = true;
        boolean hasContent = false;
        for (int i = 0; i < token.length(); ) {
            int codePoint = token.codePointAt(i);
            if (!Character.isDigit(codePoint)) {
                allDigits = false;
            }
            if (isCjk(codePoint) || Character.isLetter(codePoint)) {
                hasContent = true;
            }
            i += Character.charCount(codePoint);
        }
        return !allDigits && hasContent;
    }

    /**
     * 是否为中日韩表意文字。
     *
     * @param codePoint 码点
     * @return true 表示 CJK 字符
     */
    private boolean isCjk(int codePoint) {
        return (codePoint >= 0x4E00 && codePoint <= 0x9FFF)
                || (codePoint >= 0x3400 && codePoint <= 0x4DBF)
                || (codePoint >= 0xF900 && codePoint <= 0xFAFF);
    }
}
