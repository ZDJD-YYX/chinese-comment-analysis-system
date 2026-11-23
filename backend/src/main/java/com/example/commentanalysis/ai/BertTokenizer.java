package com.example.commentanalysis.ai;

import lombok.Getter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * BERT 中文分词器（Java 实现）。
 *
 * <p>对齐 HuggingFace {@code BertTokenizer}（bert-base-chinese，do_lower_case=true）的处理流程：
 * 文本清洗 → 中文逐字加空格 → 空白切分 → 标点切分 → 小写化 → WordPiece 子词切分 →
 * 添加 [CLS]/[SEP] → 按 maxLength 截断并补齐。</p>
 *
 * <p>词表来自训练脚本导出的 {@code vocab.txt}，行号即 token id。
 * 补齐为固定长度（而非批内动态补齐），与 TorchScript 导出时的 dummy 输入形状保持一致，
 * 规避追踪图对动态序列长度的不确定行为。</p>
 *
 * @author 闫宇星
 */
public class BertTokenizer {

    private static final String CLS_TOKEN = "[CLS]";
    private static final String SEP_TOKEN = "[SEP]";
    private static final String PAD_TOKEN = "[PAD]";
    private static final String UNK_TOKEN = "[UNK]";

    /** WordPiece 单个 token 的最大字符数，超过则直接判为未知词（与 HuggingFace 一致） */
    private static final int MAX_CHARS_PER_WORD = 100;

    /** 词表：token -> id */
    private final Map<String, Integer> vocab;

    /** 单条文本最大 token 数 */
    private final int maxLength;

    private final int clsId;

    private final int sepId;

    private final int padId;

    private final int unkId;

    /**
     * 构造分词器并加载词表。
     *
     * @param vocabPath  vocab.txt 路径
     * @param maxLength  单条文本最大 token 数（含 [CLS]/[SEP]）
     * @throws IOException 词表读取失败
     */
    public BertTokenizer(Path vocabPath, int maxLength) throws IOException {
        this.vocab = loadVocab(vocabPath);
        this.maxLength = maxLength;
        // 特殊 token 缺失时回退到 BERT 标准 id，保证不致因词表差异直接失败
        this.clsId = vocab.getOrDefault(CLS_TOKEN, 101);
        this.sepId = vocab.getOrDefault(SEP_TOKEN, 102);
        this.padId = vocab.getOrDefault(PAD_TOKEN, 0);
        this.unkId = vocab.getOrDefault(UNK_TOKEN, 100);
    }

    /**
     * 批量编码文本为模型输入张量数据。
     *
     * @param texts 已清洗的文本列表，非空
     * @return 编码结果（input_ids / attention_mask / token_type_ids，形状 [batch, maxLength]）
     */
    public EncodedBatch encode(List<String> texts) {
        int batchSize = texts.size();
        int seqLength = maxLength;
        long[] inputIds = new long[batchSize * seqLength];
        long[] attentionMask = new long[batchSize * seqLength];
        long[] tokenTypeIds = new long[batchSize * seqLength];

        for (int row = 0; row < batchSize; row++) {
            List<Integer> ids = new ArrayList<>(seqLength);
            ids.add(clsId);
            for (String token : basicTokenize(texts.get(row))) {
                List<Integer> pieceIds = wordPiece(token);
                if (pieceIds.isEmpty()) {
                    pieceIds = Collections.singletonList(unkId);
                }
                for (Integer pieceId : pieceIds) {
                    // 预留 1 个位置给 [SEP]
                    if (ids.size() >= seqLength - 1) {
                        break;
                    }
                    ids.add(pieceId);
                }
                if (ids.size() >= seqLength - 1) {
                    break;
                }
            }
            ids.add(sepId);

            int offset = row * seqLength;
            for (int i = 0; i < seqLength; i++) {
                if (i < ids.size()) {
                    inputIds[offset + i] = ids.get(i);
                    attentionMask[offset + i] = 1L;
                } else {
                    inputIds[offset + i] = padId;
                    attentionMask[offset + i] = 0L;
                }
                tokenTypeIds[offset + i] = 0L;
            }
        }
        return new EncodedBatch(inputIds, attentionMask, tokenTypeIds, batchSize, seqLength);
    }

    /**
     * 读取 vocab.txt，行号即 token id。
     *
     * @param vocabPath 词表路径
     * @return token -> id 映射
     * @throws IOException 读取失败
     */
    private Map<String, Integer> loadVocab(Path vocabPath) throws IOException {
        List<String> lines = Files.readAllLines(vocabPath, StandardCharsets.UTF_8);
        Map<String, Integer> map = new LinkedHashMap<>(lines.size() * 2);
        for (int id = 0; id < lines.size(); id++) {
            // 去除 Windows CRLF 残留的 \r，否则 token 尾部带 \r 将无法命中
            String token = lines.get(id).trim();
            // 重复 token 以首次出现（较小 id）为准
            map.putIfAbsent(token, id);
        }
        if (map.isEmpty()) {
            throw new IOException("词表为空：" + vocabPath);
        }
        return map;
    }

    /**
     * BERT 基础分词：中文逐字切分 + 空白切分 + 标点切分 + 小写化。
     *
     * @param text 原始文本
     * @return 基础 token 列表
     */
    private List<String> basicTokenize(String text) {
        String cleaned = cleanText(text);
        StringBuilder spaced = new StringBuilder(cleaned.length() + 32);
        for (int i = 0; i < cleaned.length(); ) {
            int codePoint = cleaned.codePointAt(i);
            int charCount = Character.charCount(codePoint);
            if (isCjk(codePoint)) {
                // 中文逐字加空格，使每个汉字成为独立 token
                spaced.append(' ').appendCodePoint(codePoint).append(' ');
            } else {
                spaced.appendCodePoint(codePoint);
            }
            i += charCount;
        }

        List<String> tokens = new ArrayList<>();
        for (String piece : spaced.toString().trim().split("\\s+")) {
            if (!piece.isEmpty()) {
                splitOnPunctuation(piece, tokens);
            }
        }
        return tokens;
    }

    /**
     * 按标点切分并做小写化。
     *
     * @param token 基础 token
     * @param out   结果收集列表
     */
    private void splitOnPunctuation(String token, List<String> out) {
        StringBuilder current = new StringBuilder();
        for (int i = 0; i < token.length(); ) {
            int codePoint = token.codePointAt(i);
            int charCount = Character.charCount(codePoint);
            if (isPunctuation(codePoint)) {
                if (current.length() > 0) {
                    out.add(current.toString().toLowerCase(Locale.ROOT));
                    current.setLength(0);
                }
                out.add(new String(Character.toChars(codePoint)));
            } else {
                current.appendCodePoint(codePoint);
            }
            i += charCount;
        }
        if (current.length() > 0) {
            out.add(current.toString().toLowerCase(Locale.ROOT));
        }
    }

    /**
     * WordPiece 最长匹配切分；无法完全匹配时返回空列表（调用方按 [UNK] 处理）。
     *
     * @param token 基础 token
     * @return 子词 id 列表
     */
    private List<Integer> wordPiece(String token) {
        if (token.length() > MAX_CHARS_PER_WORD) {
            return Collections.emptyList();
        }
        List<String> subTokens = new ArrayList<>();
        int start = 0;
        while (start < token.length()) {
            int end = token.length();
            String current = null;
            // 从最长前缀开始回退，寻找词表中存在的子词
            while (start < end) {
                String candidate = (start > 0 ? "##" : "") + token.substring(start, end);
                if (vocab.containsKey(candidate)) {
                    current = candidate;
                    break;
                }
                end--;
            }
            if (current == null) {
                return Collections.emptyList();
            }
            subTokens.add(current);
            start = end;
        }
        List<Integer> ids = new ArrayList<>(subTokens.size());
        for (String subToken : subTokens) {
            ids.add(vocab.get(subToken));
        }
        return ids;
    }

    /**
     * 文本清洗：去除控制字符与不可见字符，空白归一。
     *
     * @param text 原始文本
     * @return 清洗后的文本
     */
    private String cleanText(String text) {
        StringBuilder builder = new StringBuilder(text.length());
        for (int i = 0; i < text.length(); ) {
            int codePoint = text.codePointAt(i);
            int charCount = Character.charCount(codePoint);
            if (codePoint == 0 || codePoint == 0xFFFD) {
                i += charCount;
                continue;
            }
            if (Character.isWhitespace(codePoint) || Character.isSpaceChar(codePoint)
                    || isInvisible(codePoint)) {
                builder.append(' ');
            } else if (Character.getType(codePoint) != Character.CONTROL) {
                builder.appendCodePoint(codePoint);
            }
            i += charCount;
        }
        return builder.toString();
    }

    /**
     * 是否为需过滤的不可见字符（零宽字符、不间断空格、BOM）。
     *
     * @param codePoint 码点
     * @return true 表示不可见字符
     */
    private boolean isInvisible(int codePoint) {
        return (codePoint >= 0x200B && codePoint <= 0x200F)
                || codePoint == 0xFEFF
                || codePoint == 0x00A0;
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
                || (codePoint >= 0x20000 && codePoint <= 0x2A6DF)
                || (codePoint >= 0x2A700 && codePoint <= 0x2B73F)
                || (codePoint >= 0x2B740 && codePoint <= 0x2B81F)
                || (codePoint >= 0x2B820 && codePoint <= 0x2CEAF)
                || (codePoint >= 0xF900 && codePoint <= 0xFAFF)
                || (codePoint >= 0x2F800 && codePoint <= 0x2FA1F);
    }

    /**
     * 是否为标点符号（ASCII 标点区间或 Unicode 标点类目）。
     *
     * @param codePoint 码点
     * @return true 表示标点
     */
    private boolean isPunctuation(int codePoint) {
        if ((codePoint >= 33 && codePoint <= 47)
                || (codePoint >= 58 && codePoint <= 64)
                || (codePoint >= 91 && codePoint <= 96)
                || (codePoint >= 123 && codePoint <= 126)) {
            return true;
        }
        int type = Character.getType(codePoint);
        return type == Character.CONNECTOR_PUNCTUATION
                || type == Character.DASH_PUNCTUATION
                || type == Character.START_PUNCTUATION
                || type == Character.END_PUNCTUATION
                || type == Character.INITIAL_QUOTE_PUNCTUATION
                || type == Character.FINAL_QUOTE_PUNCTUATION
                || type == Character.OTHER_PUNCTUATION;
    }

    /**
     * 编码结果：模型前向所需的三组张量数据。
     */
    @Getter
    public static class EncodedBatch {

        /** 形状 [batch, seqLength] 的 input_ids 扁平数组 */
        private final long[] inputIds;

        /** 形状 [batch, seqLength] 的 attention_mask 扁平数组 */
        private final long[] attentionMask;

        /** 形状 [batch, seqLength] 的 token_type_ids 扁平数组 */
        private final long[] tokenTypeIds;

        /** 批大小 */
        private final int batchSize;

        /** 序列长度 */
        private final int seqLength;

        EncodedBatch(long[] inputIds, long[] attentionMask, long[] tokenTypeIds,
                     int batchSize, int seqLength) {
            this.inputIds = inputIds;
            this.attentionMask = attentionMask;
            this.tokenTypeIds = tokenTypeIds;
            this.batchSize = batchSize;
            this.seqLength = seqLength;
        }
    }
}
