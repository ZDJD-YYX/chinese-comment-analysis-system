package com.example.commentanalysis.ai;

import com.example.commentanalysis.config.InferenceProperties;
import com.example.commentanalysis.vo.ModelInfoVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 情感分析推理服务实现。
 *
 * <p>组合 {@code ModelRepository}（模型单例）、{@code TextPreprocessor}（文本归一化）与
 * {@code KeywordExtractor}（关键词提取），并在本层完成异常兜底，
 * 保证任何推理异常都不会向业务层抛出、不会中断分析任务。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SentimentInferenceServiceImpl implements SentimentInferenceService {

    private final ModelRepository modelRepository;

    private final TextPreprocessor textPreprocessor;

    private final KeywordExtractor keywordExtractor;

    private final InferenceProperties inferenceProperties;

    @Override
    public boolean isAvailable() {
        return modelRepository.isAvailable();
    }

    @Override
    public ModelInfoVO getModelInfo() {
        return modelRepository.getModelInfo();
    }

    @Override
    public SentimentResult infer(String text) {
        List<SentimentResult> results = batchInfer(Collections.singletonList(text));
        return results.isEmpty() ? SentimentResult.fallback(false) : results.get(0);
    }

    @Override
    public List<SentimentResult> batchInfer(List<String> texts) {
        if (texts == null || texts.isEmpty()) {
            return Collections.emptyList();
        }

        // 1) 文本归一化，输出顺序与输入一致
        List<String> cleaned = textPreprocessor.cleanBatch(texts);

        // 2) 默认全部按"空文本兜底"填充，保证结果下标与输入严格对应
        List<SentimentResult> results = new ArrayList<>(cleaned.size());
        for (int i = 0; i < cleaned.size(); i++) {
            results.add(SentimentResult.fallback(false));
        }

        // 3) 收集需要进入模型的非空样本
        List<Integer> indexes = new ArrayList<>();
        List<String> pending = new ArrayList<>();
        for (int i = 0; i < cleaned.size(); i++) {
            if (!textPreprocessor.isBlank(cleaned.get(i))) {
                indexes.add(i);
                pending.add(cleaned.get(i));
            }
        }
        if (pending.isEmpty()) {
            return results;
        }

        // 4) 模型不可用时整批降级为兜底结果（不抛异常，由调度层计入 error_count）
        if (!modelRepository.isAvailable()) {
            log.warn("情感分析模型不可用，{} 条样本全部返回兜底结果。", pending.size());
            for (Integer index : indexes) {
                results.set(index, SentimentResult.fallback(true));
            }
            return results;
        }

        List<String> labels = modelRepository.getLabels();
        double threshold = inferenceProperties.getReviewThreshold();

        // 5) 批量前向推理
        long batchStart = System.nanoTime();
        try {
            float[][] probabilities = modelRepository.predict(pending);
            // 批内均摊单条耗时，对应 analysis_result.infer_time_ms
            double perItemMs = (System.nanoTime() - batchStart) / 1_000_000.0D / pending.size();
            for (int i = 0; i < indexes.size(); i++) {
                results.set(indexes.get(i), toResult(probabilities[i], labels, threshold, perItemMs));
            }
            return results;
        } catch (Exception e) {
            log.error("批量推理失败（{} 条），回退为逐条推理：{}", pending.size(), e.getMessage(), e);
        }

        // 6) 批次整体失败时逐条重试，隔离单条异常，保证批量任务不中断
        for (Integer index : indexes) {
            long itemStart = System.nanoTime();
            try {
                float[][] single = modelRepository.predict(Collections.singletonList(cleaned.get(index)));
                double itemMs = (System.nanoTime() - itemStart) / 1_000_000.0D;
                results.set(index, toResult(single[0], labels, threshold, itemMs));
            } catch (Exception e) {
                log.warn("第 {} 条样本推理异常，返回兜底结果：{}", index, e.getMessage());
                results.set(index, SentimentResult.fallback(true));
            }
        }
        return results;
    }

    @Override
    public List<KeywordResult> extractKeywords(List<String> texts, int topN) {
        int limit = topN > 0 ? topN : inferenceProperties.getKeywordTopN();
        try {
            return keywordExtractor.extract(texts, limit);
        } catch (Exception e) {
            log.warn("关键词提取失败，返回空结果：{}", e.getMessage());
            return Collections.emptyList();
        }
    }

    @Override
    public List<String> extractKeywordsPerText(List<String> texts, int maxPerText) {
        if (texts == null || texts.isEmpty()) {
            return Collections.emptyList();
        }
        int perText = maxPerText > 0 ? maxPerText : inferenceProperties.getKeywordsPerComment();
        try {
            return keywordExtractor.tagDocuments(texts, inferenceProperties.getKeywordTopN(), perText);
        } catch (Exception e) {
            // 关键词仅用于展示，失败时降级为空串，不影响推理结果落库
            log.warn("逐条关键词提取失败，本次关键词置空：{}", e.getMessage());
            return new ArrayList<>(Collections.nCopies(texts.size(), ""));
        }
    }

    @Override
    public KeywordAccumulator createKeywordAccumulator() {
        return keywordExtractor.newAccumulator();
    }

    /**
     * 将类别概率转换为情感结果：取最大概率类别为标签，保留四位小数。
     *
     * @param probabilities 各类别概率
     * @param labels        标签顺序
     * @param threshold     低置信度复核阈值
     * @param inferTimeMs   单条推理耗时（毫秒）
     * @return 情感推理结果
     */
    private SentimentResult toResult(float[] probabilities, List<String> labels,
                                     double threshold, double inferTimeMs) {
        int bestIndex = 0;
        for (int i = 1; i < probabilities.length; i++) {
            if (probabilities[i] > probabilities[bestIndex]) {
                bestIndex = i;
            }
        }
        double score = Math.round(probabilities[bestIndex] * 10000.0D) / 10000.0D;
        String label = bestIndex < labels.size() ? labels.get(bestIndex) : SentimentResult.FALLBACK_LABEL;
        // 低置信度仅标记待复核，标签仍保留模型判定值（FR-AI-05）
        boolean needReview = score < threshold;
        return new SentimentResult(label, score, needReview, Math.round(inferTimeMs * 100.0D) / 100.0D, false);
    }
}
