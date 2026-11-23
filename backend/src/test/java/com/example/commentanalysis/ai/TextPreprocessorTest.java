package com.example.commentanalysis.ai;

import com.example.commentanalysis.config.InferenceProperties;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * 文本预处理器单元测试。
 *
 * @author 闫宇星
 */
class TextPreprocessorTest {

    @Test
    void cleanRemovesInvisibleCharactersAndCollapsesWhitespace() {
        InferenceProperties properties = new InferenceProperties();
        properties.setMaxTextLength(128);
        TextPreprocessor preprocessor = new TextPreprocessor(properties);

        assertEquals("abc def", preprocessor.clean("a\u200bbc    def"));
        assertEquals("", preprocessor.clean(null));
    }

    @Test
    void cleanTruncatesToConfiguredLength() {
        InferenceProperties properties = new InferenceProperties();
        properties.setMaxTextLength(5);
        TextPreprocessor preprocessor = new TextPreprocessor(properties);

        assertEquals("12345", preprocessor.clean("1234567890"));
    }
}
