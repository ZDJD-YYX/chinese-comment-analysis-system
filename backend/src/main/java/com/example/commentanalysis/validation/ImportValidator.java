package com.example.commentanalysis.validation;

import com.example.commentanalysis.vo.ImportValidationVO;
import com.example.commentanalysis.vo.ValidationIssueVO;
import org.springframework.stereotype.Component;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

/**
 * 导入文件校验与自动修复器。
 *
 * <p>在文件进入解析链路之前做一次"体检 + 修复"，覆盖：
 * <ul>
 *   <li>编码异常：UTF-8 BOM、UTF-16、GBK/ANSI、GB18030；UTF-8 解码失败时自动转码；</li>
 *   <li>编码转换错误：典型的"UTF-8 被按 Latin-1 解码"形成的乱码串，尝试反向还原；</li>
 *   <li>不可见字符：零宽空格/连接符、BOM 残留、软连字符、双向控制符、NBSP 与全角空格、非法控制字符；</li>
 *   <li>文件格式：扩展名与实际内容不一致（如 .csv 实际是 xlsx、.csv 实际是 TSV/JSON）时自动纠正。</li>
 * </ul>
 * 检测结果全部写入 {@link ImportValidationVO}，修复后的 UTF-8 字节流交给解析器使用。</p>
 *
 * @author 闫宇星
 */
@Component
public class ImportValidator {

    /** 文本类扩展名 */
    private static final Set<String> TEXT_EXTENSIONS =
            new HashSet<>(Arrays.asList("csv", "txt", "tsv", "json"));

    /** 二进制类扩展名 */
    private static final Set<String> BINARY_EXTENSIONS =
            new HashSet<>(Arrays.asList("xlsx", "xls"));

    /** xlsx 的 ZIP 文件头 */
    private static final byte[] ZIP_MAGIC = {0x50, 0x4B, 0x03, 0x04};

    /** xls 的 OLE2 文件头 */
    private static final byte[] OLE_MAGIC = {(byte) 0xD0, (byte) 0xCF, 0x11, (byte) 0xE0};

    /** 处理级别 */
    private static final String LEVEL_FIXED = "FIXED";
    private static final String LEVEL_WARNING = "WARNING";
    private static final String LEVEL_ERROR = "ERROR";

    /** 状态 */
    private static final String STATUS_PASS = "PASS";
    private static final String STATUS_FIXED = "FIXED";
    private static final String STATUS_WARNING = "WARNING";
    private static final String STATUS_ERROR = "ERROR";

    /**
     * 校验并修复文件内容。
     *
     * @param extension 上传文件的扩展名（小写，不含点）
     * @param bytes     原始字节
     * @return 校验结果（含修复后的字节、实际格式、编码与报告）
     */
    public ValidationOutcome validate(String extension, byte[] bytes) {
        String ext = normalizeExtension(extension);
        ImportValidationVO report = new ImportValidationVO();
        report.setOriginalFormat(ext);

        ValidationOutcome outcome = new ValidationOutcome();
        outcome.setOriginalData(bytes);
        outcome.setReport(report);
        outcome.setData(bytes);
        outcome.setActualFormat(ext);

        if (bytes == null || bytes.length == 0) {
            addIssue(report, "空文件", LEVEL_ERROR, 0, "文件内容为空，无法解析");
            report.setStatus(STATUS_ERROR);
            report.setSummary("文件内容为空，无法解析");
            outcome.setActualFormat(ext);
            return outcome;
        }

        // 1. 先按文件头判断真实格式：扩展名与内容不一致时自动纠正
        String binaryFormat = sniffBinaryFormat(bytes);
        String actualFormat = ext;
        if (binaryFormat != null) {
            actualFormat = binaryFormat;
            if (!binaryFormat.equals(ext)) {
                addIssue(report, "格式不符", LEVEL_FIXED, 0,
                        "扩展名为 ." + ext + "，实际内容为 " + binaryFormat + "，已按实际格式解析");
                report.setRepaired(true);
            }
            return finishBinary(outcome, report, actualFormat, bytes);
        }

        if (BINARY_EXTENSIONS.contains(ext)) {
            addIssue(report, "格式不符", LEVEL_FIXED, 0,
                    "扩展名为 ." + ext + "，但内容不是有效的 Excel 文件，已按文本格式解析");
            report.setRepaired(true);
            actualFormat = "csv";
        }

        // 2. 文本类：编码识别与转码
        Decoded decoded = decodeText(bytes);
        report.setEncodingDetected(decoded.detected);
        if (decoded.error != null) {
            addIssue(report, "编码异常", LEVEL_ERROR, 0, decoded.error);
            report.setStatus(STATUS_ERROR);
            report.setSummary("文件编码无法识别：" + decoded.error);
            outcome.setActualFormat(actualFormat);
            report.setActualFormat(actualFormat);
            return outcome;
        }
        if (decoded.transcoded) {
            addIssue(report, "编码异常", LEVEL_FIXED, 0,
                    "检测到 " + decoded.detected + " 编码，已自动转换为 UTF-8");
            report.setRepaired(true);
        }

        String text = decoded.text;

        // 3. UTF-8 被误读造成的乱码串：尝试反向还原
        String repairedText = repairMojibake(text);
        if (!repairedText.equals(text)) {
            addIssue(report, "编码转换错误", LEVEL_FIXED, 0,
                    "检测到 UTF-8 被错误解码形成的乱码，已反向还原");
            text = repairedText;
            report.setRepaired(true);
        }

        // 4. 不可见字符与非法控制字符清理
        CleanResult clean = cleanInvisible(text);
        if (clean.removed > 0) {
            addIssue(report, "不可见字符", LEVEL_FIXED, clean.removed,
                    "已清理零宽字符、软连字符、BOM 残留与非法控制字符");
            text = clean.text;
            report.setRepaired(true);
        }

        // 5. 仍然存在的替换字符：说明有损，给出警告但不阻断
        int replacement = countChar(text, '\uFFFD');
        if (replacement > 0) {
            addIssue(report, "编码转换错误", LEVEL_WARNING, replacement,
                    "存在 " + replacement + " 个无法还原的替换字符，建议核对原文");
        }

        // 6. 文本内容进一步判断实际格式（csv / tsv / json / txt）
        String textFormat = sniffTextFormat(text, actualFormat);
        if (!textFormat.equals(actualFormat)) {
            addIssue(report, "格式不符", LEVEL_FIXED, 0,
                    "内容结构更符合 " + textFormat.toUpperCase()
                            + "，已按该格式解析（原扩展名 ." + ext + "）");
            report.setRepaired(true);
        }
        actualFormat = textFormat;

        byte[] repairedBytes = text.getBytes(StandardCharsets.UTF_8);
        outcome.setData(repairedBytes);
        outcome.setActualFormat(actualFormat);
        outcome.setCharset(StandardCharsets.UTF_8);
        outcome.setOriginalCharset(decoded.sourceCharset);
        outcome.setRepaired(report.isRepaired());
        report.setActualFormat(actualFormat);
        report.setEncodingUsed("UTF-8");
        finalizeStatus(report);
        return outcome;
    }

    /**
     * 二进制格式直接通过校验（只校验文件头一致性）。
     *
     * @param outcome      校验结果
     * @param report       报告
     * @param actualFormat 实际格式
     * @param bytes        原始字节
     * @return 校验结果
     */
    private ValidationOutcome finishBinary(ValidationOutcome outcome, ImportValidationVO report,
                                           String actualFormat, byte[] bytes) {
        report.setActualFormat(actualFormat);
        report.setEncodingDetected("二进制");
        report.setEncodingUsed("二进制");
        outcome.setActualFormat(actualFormat);
        outcome.setCharset(null);
        outcome.setData(bytes);
        outcome.setRepaired(report.isRepaired());
        finalizeStatus(report);
        return outcome;
    }

    /**
     * 计算最终状态与结论文案。
     *
     * @param report 报告
     */
    private void finalizeStatus(ImportValidationVO report) {
        boolean hasWarning = report.getIssues().stream()
                .anyMatch(issue -> LEVEL_WARNING.equals(issue.getLevel()));
        boolean hasError = report.getIssues().stream()
                .anyMatch(issue -> LEVEL_ERROR.equals(issue.getLevel()));

        if (hasError) {
            report.setStatus(STATUS_ERROR);
        } else if (hasWarning) {
            report.setStatus(STATUS_WARNING);
        } else if (report.isRepaired()) {
            report.setStatus(STATUS_FIXED);
        } else {
            report.setStatus(STATUS_PASS);
        }

        if (STATUS_PASS.equals(report.getStatus())) {
            report.setSummary("文件校验通过，格式与编码均正常");
        } else if (STATUS_FIXED.equals(report.getStatus())) {
            report.setSummary("检测到 " + report.getIssues().size() + " 项问题，已全部自动修复");
        } else if (STATUS_WARNING.equals(report.getStatus())) {
            report.setSummary("文件已导入，但存在需人工关注的项");
        } else {
            report.setSummary("文件无法导入，请处理后重试");
        }
    }

    /* ==========================================================================
       编码识别
       ========================================================================== */

    /**
     * 识别文本编码并解码。
     *
     * <p>判定顺序：BOM → 严格 UTF-8 → GBK → GB18030；都不成立时标记为无法识别。</p>
     *
     * @param bytes 原始字节
     * @return 解码结果
     */
    private Decoded decodeText(byte[] bytes) {
        if (startsWith(bytes, new byte[]{(byte) 0xEF, (byte) 0xBB, (byte) 0xBF})) {
            return decodeSkip(bytes, 3, StandardCharsets.UTF_8, "UTF-8 BOM", true);
        }
        if (startsWith(bytes, new byte[]{(byte) 0xFF, (byte) 0xFE})) {
            return decodeSkip(bytes, 2, StandardCharsets.UTF_16LE, "UTF-16LE", true);
        }
        if (startsWith(bytes, new byte[]{(byte) 0xFE, (byte) 0xFF})) {
            return decodeSkip(bytes, 2, StandardCharsets.UTF_16BE, "UTF-16BE", true);
        }

        String utf8 = tryDecode(bytes, StandardCharsets.UTF_8);
        if (utf8 != null) {
            return Decoded.ok(utf8, "UTF-8", StandardCharsets.UTF_8, false);
        }
        String gbk = tryDecode(bytes, Charset.forName("GBK"));
        if (gbk != null) {
            return Decoded.ok(gbk, "GBK/ANSI", Charset.forName("GBK"), true);
        }
        String gb18030 = tryDecode(bytes, Charset.forName("GB18030"));
        if (gb18030 != null) {
            return Decoded.ok(gb18030, "GB18030", Charset.forName("GB18030"), true);
        }
        return Decoded.error("既不是有效的 UTF-8，也不是有效的 GBK/GB18030 编码");
    }

    /**
     * 跳过 BOM 后按指定编码解码。
     *
     * @param bytes    原始字节
     * @param skip     BOM 长度
     * @param charset  目标编码
     * @param detected 编码名称
     * @param transcoded 是否发生转码
     * @return 解码结果
     */
    private Decoded decodeSkip(byte[] bytes, int skip, Charset charset,
                               String detected, boolean transcoded) {
        String text = tryDecode(Arrays.copyOfRange(bytes, skip, bytes.length), charset);
        if (text == null) {
            return Decoded.error("声明为 " + detected + "，但内容无法按该编码解码");
        }
        return Decoded.ok(text, detected, charset, transcoded);
    }

    /**
     * 严格解码：遇到非法字节返回 null，而不是静默替换成替换字符。
     *
     * @param bytes   原始字节
     * @param charset 编码
     * @return 解码文本，失败返回 null
     */
    private String tryDecode(byte[] bytes, Charset charset) {
        CharsetDecoder decoder = charset.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT);
        try {
            CharBuffer buffer = decoder.decode(ByteBuffer.wrap(bytes));
            return buffer.toString();
        } catch (CharacterCodingException e) {
            return null;
        }
    }

    /* ==========================================================================
       乱码与不可见字符
       ========================================================================== */

    /**
     * 尝试还原"UTF-8 字节被按 Latin-1 解码"形成的乱码。
     *
     * <p>判定思路：正常中文文本一定含汉字；若文本完全没有汉字、却出现
     * Latin-1 扩展区字符，把它按单字节还原后能严格解出 UTF-8 且包含汉字，
     * 即可判定为编码转换错误并还原。</p>
     *
     * @param text 解码后的文本
     * @return 还原后的文本；无需或无法还原时返回原文
     */
    private String repairMojibake(String text) {
        if (text.isEmpty() || containsCjk(text)) {
            return text;
        }
        boolean hasLatinSupplement = false;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c > 0xFF) {
                // 出现 Latin-1 之外的字符，不是这种乱码形态
                return text;
            }
            if (c >= 0x80) {
                hasLatinSupplement = true;
            }
        }
        if (!hasLatinSupplement) {
            return text;
        }
        byte[] latinBytes = text.getBytes(StandardCharsets.ISO_8859_1);
        String repaired = tryDecode(latinBytes, StandardCharsets.UTF_8);
        if (repaired == null || !containsCjk(repaired)) {
            return text;
        }
        return repaired;
    }

    /**
     * 是否包含中日韩统一表意文字。
     *
     * @param text 文本
     * @return true 表示包含汉字
     */
    private boolean containsCjk(String text) {
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c >= '\u4E00' && c <= '\u9FA5') {
                return true;
            }
        }
        return false;
    }

    /**
     * 清理不可见字符与非法控制字符。
     *
     * @param text 文本
     * @return 清理结果
     */
    private CleanResult cleanInvisible(String text) {
        StringBuilder builder = new StringBuilder(text.length());
        int removed = 0;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '\u00A0' || c == '\u3000') {
                // 不间断空格与全角空格统一为普通空格，避免分词与比较异常
                builder.append(' ');
                removed++;
                continue;
            }
            if (isInvisible(c)) {
                removed++;
                continue;
            }
            builder.append(c);
        }
        return new CleanResult(builder.toString(), removed);
    }

    /**
     * 是否为需要剔除的不可见字符。
     *
     * @param c 字符
     * @return true 表示应剔除
     */
    private boolean isInvisible(char c) {
        // 零宽空格 / 零宽非连接符 / 零宽连接符 / 词连接符 / BOM
        if (c == '\u200B' || c == '\u200C' || c == '\u200D'
                || c == '\u2060' || c == '\uFEFF') {
            return true;
        }
        // 软连字符
        if (c == '\u00AD') {
            return true;
        }
        // 双向文本控制符
        if ((c >= '\u202A' && c <= '\u202E') || (c >= '\u2066' && c <= '\u2069')) {
            return true;
        }
        // 除换行、回车、制表符外的 C0 控制字符
        if (c < 0x20 && c != '\n' && c != '\r' && c != '\t') {
            return true;
        }
        // C1 控制字符
        return c >= 0x7F && c <= 0x9F;
    }

    /* ==========================================================================
       格式识别
       ========================================================================== */

    /**
     * 按文件头识别二进制格式。
     *
     * @param bytes 原始字节
     * @return xlsx / xls；非二进制返回 null
     */
    private String sniffBinaryFormat(byte[] bytes) {
        if (startsWith(bytes, ZIP_MAGIC)) {
            return "xlsx";
        }
        if (startsWith(bytes, OLE_MAGIC)) {
            return "xls";
        }
        return null;
    }

    /**
     * 按文本内容推断实际格式。
     *
     * @param text 已解码文本
     * @param ext  当前格式
     * @return 推断后的格式
     */
    private String sniffTextFormat(String text, String ext) {
        String trimmed = text.trim();
        // 只有整体构成 JSON 数组/对象时才纠正，避免把以「{」开头的普通评论误判
        if ((trimmed.startsWith("[") && trimmed.endsWith("]"))
                || (trimmed.startsWith("{") && trimmed.endsWith("}"))) {
            return "json";
        }
        if ("json".equals(ext)) {
            // 声明是 JSON 但结构不是数组/对象，交由 JSON 解析器给出明确错误
            return "json";
        }
        if ("txt".equals(ext) || "tsv".equals(ext)) {
            return ext;
        }
        String firstLine = firstNonBlankLine(text);
        if (firstLine != null && firstLine.indexOf('\t') >= 0 && firstLine.indexOf(',') < 0) {
            return "tsv";
        }
        return "csv";
    }

    /**
     * 取第一行非空文本。
     *
     * @param text 文本
     * @return 首行；全为空行时返回 null
     */
    private String firstNonBlankLine(String text) {
        for (String line : text.split("\r?\n")) {
            if (!line.trim().isEmpty()) {
                return line;
            }
        }
        return null;
    }

    /* ==========================================================================
       工具方法
       ========================================================================== */

    private String normalizeExtension(String extension) {
        return extension == null ? "" : extension.trim().toLowerCase(Locale.ROOT);
    }

    private boolean startsWith(byte[] bytes, byte[] prefix) {
        if (bytes == null || bytes.length < prefix.length) {
            return false;
        }
        for (int i = 0; i < prefix.length; i++) {
            if (bytes[i] != prefix[i]) {
                return false;
            }
        }
        return true;
    }

    private int countChar(String text, char target) {
        int count = 0;
        for (int i = 0; i < text.length(); i++) {
            if (text.charAt(i) == target) {
                count++;
            }
        }
        return count;
    }

    /**
     * 追加问题项。
     *
     * @param report 报告
     * @param type   类型
     * @param level  级别
     * @param count  数量
     * @param detail 说明
     */
    private void addIssue(ImportValidationVO report, String type, String level, int count, String detail) {
        report.getIssues().add(new ValidationIssueVO(type, level, count, detail));
    }

    /**
     * 解码结果。
     */
    private static class Decoded {

        private String text;

        private String detected;

        private Charset sourceCharset;

        private boolean transcoded;

        private String error;

        static Decoded ok(String text, String detected, Charset sourceCharset, boolean transcoded) {
            Decoded decoded = new Decoded();
            decoded.text = text;
            decoded.detected = detected;
            decoded.sourceCharset = sourceCharset;
            decoded.transcoded = transcoded;
            return decoded;
        }

        static Decoded error(String message) {
            Decoded decoded = new Decoded();
            decoded.error = message;
            return decoded;
        }
    }

    /**
     * 不可见字符清理结果。
     */
    private static class CleanResult {

        private final String text;

        private final int removed;

        CleanResult(String text, int removed) {
            this.text = text;
            this.removed = removed;
        }
    }
}