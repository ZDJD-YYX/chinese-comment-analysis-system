package com.example.commentanalysis.ai;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 关键词增量累加器（TF-IDF）。
 *
 * <p>大文件分析时若把全部评论文本常驻内存，内存占用与文件大小线性增长，容易 OOM。
 * 本类只保留「词频 + 文档频率」的聚合结果，每批评论处理完即可丢弃原文，
 * 任务结束时再一次性计算 TopN，语义与 {@link KeywordExtractor#extract(List, int)} 完全一致。</p>
 *
 * @author 闫宇星
 */
public class KeywordAccumulator {

    private final KeywordExtractor extractor;

    /** 词 → 总词频 */
    private final Map<String, Integer> wordCounts = new HashMap<>();

    /** 词 → 出现的评论篇数 */
    private final Map<String, Integer> documentFrequency = new HashMap<>();

    /** 参与统计的评论篇数（至少含一个有效词） */
    private int documentCount;

    /** 有效词总数 */
    private long totalTokens;

    KeywordAccumulator(KeywordExtractor extractor) {
        this.extractor = extractor;
    }

    /**
     * 累加一批评论文本。
     *
     * @param texts 评论文本列表，可为空
     */
    public void addAll(List<String> texts) {
        if (texts == null || texts.isEmpty()) {
            return;
        }
        for (String text : texts) {
            add(text);
        }
    }

    /**
     * 累加单条评论文本。
     *
     * @param text 评论文本
     */
    public void add(String text) {
        List<String> tokens = extractor.segment(text);
        if (tokens.isEmpty()) {
            return;
        }
        documentCount++;
        totalTokens += tokens.size();
        for (String token : tokens) {
            wordCounts.merge(token, 1, Integer::sum);
        }
        // 同一条评论内重复出现的词只计一次文档频率
        for (String token : new java.util.HashSet<>(tokens)) {
            documentFrequency.merge(token, 1, Integer::sum);
        }
    }

    /**
     * 计算当前语料的 TopN 关键词。
     *
     * @param topN 返回条数上限
     * @return 按权重降序的关键词列表；无有效词时返回空列表
     */
    public List<KeywordResult> topN(int topN) {
        if (topN <= 0 || wordCounts.isEmpty() || documentCount == 0 || totalTokens == 0L) {
            return Collections.emptyList();
        }
        List<KeywordResult> results = new ArrayList<>(wordCounts.size());
        for (Map.Entry<String, Integer> entry : wordCounts.entrySet()) {
            String word = entry.getKey();
            int wordCount = entry.getValue();
            double tf = (double) wordCount / totalTokens;
            int df = documentFrequency.getOrDefault(word, 0);
            double idf = Math.log((double) documentCount / (df + 1)) + 1.0D;
            results.add(new KeywordResult(word, round4(tf * idf), wordCount));
        }
        results.sort((left, right) -> Double.compare(right.getWeight(), left.getWeight()));
        return results.size() > topN ? new ArrayList<>(results.subList(0, topN)) : results;
    }

    /**
     * 保留四位小数。
     *
     * @param value 原始值
     * @return 四位小数结果
     */
    private double round4(double value) {
        return Math.round(value * 10000.0D) / 10000.0D;
    }
}
