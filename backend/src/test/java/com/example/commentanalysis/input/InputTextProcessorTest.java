package com.example.commentanalysis.input;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 智能输入文本识别与分段测试。
 *
 * @author 闫宇星
 */
class InputTextProcessorTest {

    @Test
    void detectsSingleUrlAsWebPage() {
        InputTextProcessor.Detected detected =
                InputTextProcessor.detect("  https://example.com/news/1  ");
        assertEquals(InputTextProcessor.InputKind.WEB_PAGE, detected.getKind());
        assertEquals("https://example.com/news/1", detected.getUrl());
    }

    @Test
    void detectsWwwPrefixAndStripsTrailingPunctuation() {
        InputTextProcessor.Detected detected =
                InputTextProcessor.detect("www.example.com/article。");
        assertEquals(InputTextProcessor.InputKind.WEB_PAGE, detected.getKind());
        assertEquals("https://www.example.com/article", detected.getUrl());
    }

    @Test
    void treatsMixedTextAsPlainText() {
        assertEquals(InputTextProcessor.InputKind.PLAIN_TEXT,
                InputTextProcessor.detect("这个链接不错 https://example.com").getKind());
        assertEquals(InputTextProcessor.InputKind.PLAIN_TEXT,
                InputTextProcessor.detect("第一行\nhttps://example.com").getKind());
        assertEquals(InputTextProcessor.InputKind.PLAIN_TEXT,
                InputTextProcessor.detect("   ").getKind());
    }

    @Test
    void segmentKeepsEveryLine() {
        List<String> comments = InputTextProcessor.segment(
                "第一行评论\n\n第二行评论\n   \n第三行评论", 512);
        assertEquals(3, comments.size());
        assertEquals("第一行评论", comments.get(0));
        assertEquals("第三行评论", comments.get(2));
    }

    @Test
    void segmentSplitsLongTextWithoutLosingCharacters() {
        StringBuilder source = new StringBuilder();
        for (int i = 0; i < 600; i++) {
            source.append("这是一句测试评论。");
        }
        List<String> comments = InputTextProcessor.segment(source.toString(), 100);

        assertTrue(comments.size() > 1);
        assertTrue(comments.stream().allMatch(item -> item.length() <= 100));
        assertEquals(source.toString(), String.join("", comments));
    }

    @Test
    void segmentHardSplitsSentenceLongerThanLimit() {
        StringBuilder source = new StringBuilder();
        for (int i = 0; i < 50; i++) {
            source.append("没有标点的超长文本");
        }
        List<String> comments = InputTextProcessor.segment(source.toString(), 20);

        assertEquals(source.toString(), String.join("", comments));
        assertTrue(comments.stream().allMatch(item -> item.length() <= 20));
        assertFalse(comments.isEmpty());
    }
}
