package com.example.commentanalysis.ai;

import com.example.commentanalysis.config.InferenceProperties;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.regex.Pattern;

/**
 * 文本预处理器。
 *
 * <p>负责推理前的文本归一化：去除零宽字符与不可见字符、合并连续空白、去除首尾空白，
 * 并按配置截断超长文本（对应《详细设计说明书》5.4 第 2 步）。</p>
 *
 * @author 闫宇星
 */
@Component
public class TextPreprocessor {

    /** 零宽字符与不间断空格 */
    private static final Pattern INVISIBLE = Pattern.compile("[\\u200b-\\u200f\\ufeff\\xa0]");

    /** 连续空白（含换行、制表符） */
    private static final Pattern MULTI_SPACE = Pattern.compile("\\s+");

    private final InferenceProperties inferenceProperties;

    public TextPreprocessor(InferenceProperties inferenceProperties) {
        this.inferenceProperties = inferenceProperties;
    }

    /**
     * 清洗单条文本。
     *
     * @param raw 原始文本，可为 null
     * @return 清洗后的文本；null、非文本型内容返回空串
     */
    public String clean(String raw) {
        if (raw == null) {
            return "";
        }
        String text = INVISIBLE.matcher(raw).replaceAll("");
        text = MULTI_SPACE.matcher(text).replaceAll(" ").trim();
        int maxTextLength = inferenceProperties.getMaxTextLength();
        if (maxTextLength > 0 && text.length() > maxTextLength) {
            text = text.substring(0, maxTextLength);
        }
        return text;
    }

    /**
     * 批量清洗文本，输出顺序与输入严格一致。
     *
     * @param texts 原始文本列表，可为 null
     * @return 清洗后的文本列表
     */
    public List<String> cleanBatch(List<String> texts) {
        if (texts == null || texts.isEmpty()) {
            return Collections.emptyList();
        }
        List<String> cleaned = new ArrayList<>(texts.size());
        for (String text : texts) {
            cleaned.add(clean(text));
        }
        return cleaned;
    }

    /**
     * 判断清洗后的文本是否为空（全空白视为空）。
     *
     * @param cleanedText 清洗后的文本
     * @return true 表示无可推理内容
     */
    public boolean isBlank(String cleanedText) {
        return !StringUtils.hasText(cleanedText);
    }
}
