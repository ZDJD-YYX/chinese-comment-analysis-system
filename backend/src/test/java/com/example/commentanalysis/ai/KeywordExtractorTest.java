package com.example.commentanalysis.ai;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 关键词提取与增量累加的一致性测试。
 *
 * @author 闫宇星
 */
class KeywordExtractorTest {

    private final KeywordExtractor extractor = new KeywordExtractor();

    @Test
    void extractReturnsKeywordsByTfIdf() {
        List<KeywordResult> results = extractor.extract(
                Arrays.asList("推荐 推荐 售后 很好", "推荐 售后 服务"), 5);

        assertFalse(results.isEmpty());
        assertEquals("推荐", results.get(0).getWord());
        assertTrue(results.get(0).getWeight() > 0);
        assertTrue(results.size() <= 5);
        for (KeywordResult result : results) {
            assertTrue(result.getWord().length() >= 2, "单字不应作为关键词：" + result.getWord());
        }
    }

    @Test
    void accumulatorMatchesBatchExtract() {
        List<String> texts = Arrays.asList("推荐 推荐 售后 很好", "推荐 售后 服务");

        List<KeywordResult> expected = extractor.extract(texts, 10);
        KeywordAccumulator accumulator = extractor.newAccumulator();
        accumulator.addAll(texts);
        List<KeywordResult> actual = accumulator.topN(10);

        assertEquals(expected.size(), actual.size());
        for (int i = 0; i < expected.size(); i++) {
            assertEquals(expected.get(i).getWord(), actual.get(i).getWord());
            assertEquals(expected.get(i).getWeight(), actual.get(i).getWeight(), 0.0001D);
            assertEquals(expected.get(i).getWordCount(), actual.get(i).getWordCount());
        }
    }

    @Test
    void emptyInputReturnsEmpty() {
        assertTrue(extractor.extract(Collections.emptyList(), 10).isEmpty());
        assertTrue(extractor.extract(null, 10).isEmpty());
        KeywordAccumulator accumulator = extractor.newAccumulator();
        assertTrue(accumulator.topN(10).isEmpty());
    }
}
