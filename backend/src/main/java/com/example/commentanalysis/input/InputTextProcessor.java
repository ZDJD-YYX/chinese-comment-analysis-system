package com.example.commentanalysis.input;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.ArrayList;
import java.util.List;

/**
 * 智能输入的内容识别与文本分段工具。
 *
 * <p>负责两件事：判断用户粘贴的是「网页链接」还是「纯文本」，以及把内容切分为
 * 适合逐条情感分析的评论文本。切分只按句末标点与长度边界进行，不丢弃任何正文，
 * 避免长内容被直接截断。</p>
 *
 * @author 闫宇星
 */
public final class InputTextProcessor {

    /** 句末标点：中文为主，兼容英文问号与叹号 */
    private static final String SENTENCE_END = "。！？!?；;";

    /** 链接末尾可能被一起复制进来的标点 */
    private static final String TRAILING_PUNCTUATION = "。，；、！？）》】”’\"'";

    /**
     * 输入类型。
     */
    public enum InputKind {
        /** 网页链接 */
        WEB_PAGE,
        /** 纯文本 */
        PLAIN_TEXT
    }

    /**
     * 识别结果。
     */
    public static final class Detected {
        private final InputKind kind;
        private final String url;

        private Detected(InputKind kind, String url) {
            this.kind = kind;
            this.url = url;
        }

        public InputKind getKind() {
            return kind;
        }

        /**
         * 规范化后的链接，仅 {@link InputKind#WEB_PAGE} 时有值。
         *
         * @return 完整 http/https 链接
         */
        public String getUrl() {
            return url;
        }
    }

    private InputTextProcessor() {
    }

    /**
     * 自动识别输入类型，无需用户手动切换模式。
     *
     * <p>仅当整段输入（忽略首尾空白）就是一个链接时判定为网页；链接与文字混排时
     * 按纯文本处理，避免误把用户评论里的网址当作抓取目标。</p>
     *
     * @param raw 用户输入
     * @return 识别结果，永不为 null
     */
    public static Detected detect(String raw) {
        String value = raw == null ? "" : raw.replace('\u3000', ' ').replace("\uFEFF", "").trim();
        if (value.isEmpty()) {
            return new Detected(InputKind.PLAIN_TEXT, null);
        }
        String candidate = stripTrailingPunctuation(value);
        if (candidate.indexOf('\n') >= 0 || candidate.indexOf('\r') >= 0
                || containsWhitespace(candidate)) {
            return new Detected(InputKind.PLAIN_TEXT, null);
        }
        String lower = candidate.toLowerCase();
        String normalized;
        if (lower.startsWith("http://") || lower.startsWith("https://")) {
            normalized = candidate;
        } else if (lower.startsWith("www.")) {
            normalized = "https://" + candidate;
        } else {
            return new Detected(InputKind.PLAIN_TEXT, null);
        }
        String url = null;
        try {
            URI uri = new URI(normalized);
            String scheme = uri.getScheme();
            if (scheme != null && ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))
                    && uri.getHost() != null && !uri.getHost().isEmpty()) {
                url = uri.toString();
            }
        } catch (URISyntaxException ignored) {
            // 不是合法链接，按纯文本处理
        }
        if (url == null) {
            return new Detected(InputKind.PLAIN_TEXT, null);
        }
        return new Detected(InputKind.WEB_PAGE, url);
    }

    /**
     * 把原始文本切分为评论列表。
     *
     * <p>先按换行拆分；单行超过 {@code maxLength} 时按句末标点合并切分，单句仍然超长
     * 则按长度硬切。所有字符都保留在切分结果中，不做截断。</p>
     *
     * @param raw       原始文本
     * @param maxLength 单条评论最大字符数
     * @return 评论文本列表，可能为空
     */
    public static List<String> segment(String raw, int maxLength) {
        List<String> result = new ArrayList<>();
        String normalized = normalize(raw);
        if (normalized.isEmpty() || maxLength <= 0) {
            return result;
        }
        for (String line : normalized.split("\n")) {
            String text = line.trim();
            if (text.isEmpty()) {
                continue;
            }
            if (text.length() <= maxLength) {
                result.add(text);
            } else {
                splitLongLine(text, maxLength, result);
            }
        }
        return result;
    }

    /**
     * 文本归一化：统一换行、全角空格与不可见字符，逐行折叠空白。
     *
     * @param raw 原始文本
     * @return 归一化后的文本
     */
    public static String normalize(String raw) {
        if (raw == null) {
            return "";
        }
        String text = raw.replace("\r\n", "\n")
                .replace('\r', '\n')
                .replace('\u00a0', ' ')
                .replace('\u3000', ' ')
                .replace("\uFEFF", "")
                .replace("\u200B", "");
        StringBuilder builder = new StringBuilder(text.length());
        for (String line : text.split("\n", -1)) {
            String cleaned = line.replaceAll("[\\t\\x0B\\f ]+", " ").trim();
            if (cleaned.isEmpty()) {
                continue;
            }
            if (builder.length() > 0) {
                builder.append('\n');
            }
            builder.append(cleaned);
        }
        return builder.toString();
    }

    /**
     * 按句子合并切分超长行。
     *
     * @param line      超长文本
     * @param maxLength 单条上限
     * @param result    结果容器
     */
    private static void splitLongLine(String line, int maxLength, List<String> result) {
        StringBuilder chunk = new StringBuilder(maxLength);
        for (String sentence : splitSentences(line)) {
            if (sentence.isEmpty()) {
                continue;
            }
            if (sentence.length() > maxLength) {
                flush(chunk, result);
                hardSplit(sentence, maxLength, result);
                continue;
            }
            if (chunk.length() > 0 && chunk.length() + sentence.length() > maxLength) {
                flush(chunk, result);
            }
            chunk.append(sentence);
        }
        flush(chunk, result);
    }

    /**
     * 按句末标点切句，标点保留在句子末尾。
     *
     * @param text 文本
     * @return 句子列表
     */
    private static List<String> splitSentences(String text) {
        List<String> sentences = new ArrayList<>();
        int start = 0;
        for (int i = 0; i < text.length(); i++) {
            char current = text.charAt(i);
            boolean end = SENTENCE_END.indexOf(current) >= 0;
            if (!end && current == '.' && (i + 1 == text.length()
                    || Character.isWhitespace(text.charAt(i + 1)))) {
                end = true;
            }
            if (end) {
                sentences.add(text.substring(start, i + 1));
                start = i + 1;
            }
        }
        if (start < text.length()) {
            sentences.add(text.substring(start));
        }
        return sentences;
    }

    /**
     * 单句仍超长时按长度硬切，避免代理对字符被从中间截断。
     *
     * @param text      超长句子
     * @param maxLength 单条上限
     * @param result    结果容器
     */
    private static void hardSplit(String text, int maxLength, List<String> result) {
        int index = 0;
        while (index < text.length()) {
            int end = Math.min(index + maxLength, text.length());
            if (end < text.length() && Character.isHighSurrogate(text.charAt(end - 1))) {
                end--;
            }
            String piece = text.substring(index, end).trim();
            if (!piece.isEmpty()) {
                result.add(piece);
            }
            index = end;
        }
    }

    /**
     * 把合并缓冲区写入结果。
     *
     * @param chunk  缓冲区
     * @param result 结果容器
     */
    private static void flush(StringBuilder chunk, List<String> result) {
        if (chunk.length() == 0) {
            return;
        }
        String text = chunk.toString().trim();
        if (!text.isEmpty()) {
            result.add(text);
        }
        chunk.setLength(0);
    }

    /**
     * 去掉整段链接末尾误带入的中文标点。
     *
     * @param value 原始值
     * @return 去除尾随标点后的值
     */
    private static String stripTrailingPunctuation(String value) {
        int end = value.length();
        while (end > 0 && TRAILING_PUNCTUATION.indexOf(value.charAt(end - 1)) >= 0) {
            end--;
        }
        return value.substring(0, end);
    }

    /**
     * 是否包含空白字符。
     *
     * @param value 待检查文本
     * @return 含空白返回 true
     */
    private static boolean containsWhitespace(String value) {
        for (int i = 0; i < value.length(); i++) {
            if (Character.isWhitespace(value.charAt(i))) {
                return true;
            }
        }
        return false;
    }
}
