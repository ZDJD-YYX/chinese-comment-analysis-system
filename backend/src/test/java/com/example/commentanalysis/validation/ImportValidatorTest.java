package com.example.commentanalysis.validation;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 导入校验与自动修复测试。
 *
 * <p>覆盖编码异常、乱码串还原、不可见字符清理、格式纠正与无法识别场景。</p>
 *
 * @author 闫宇星
 */
class ImportValidatorTest {

    private final ImportValidator validator = new ImportValidator();

    @Test
    @DisplayName("GBK 编码：自动转码为 UTF-8")
    void gbkShouldBeTranscoded() {
        String text = "耳机音质很好，物流很快。";
        ValidationOutcome outcome = validator.validate("csv", text.getBytes(Charset.forName("GBK")));

        assertEquals("FIXED", outcome.getReport().getStatus());
        assertEquals("UTF-8", outcome.getReport().getEncodingUsed());
        assertNotNull(outcome.getOriginalCharset(), "应记录原始编码用于回退");
        assertTrue(decode(outcome).contains("耳机音质很好"));
    }

    @Test
    @DisplayName("UTF-8 BOM：跳过 BOM，内容不残留标记")
    void utf8BomShouldBeStripped() {
        byte[] payload = "评论内容\n很好用".getBytes(StandardCharsets.UTF_8);
        byte[] bytes = concat(new byte[]{(byte) 0xEF, (byte) 0xBB, (byte) 0xBF}, payload);

        ValidationOutcome outcome = validator.validate("csv", bytes);

        assertEquals("FIXED", outcome.getReport().getStatus());
        assertTrue(outcome.getReport().getEncodingDetected().contains("BOM"));
        assertEquals("评论内容\n很好用", decode(outcome));
    }

    @Test
    @DisplayName("UTF-16LE：识别并转码为 UTF-8")
    void utf16ShouldBeTranscoded() {
        byte[] payload = "评论内容\n很好用".getBytes(StandardCharsets.UTF_16LE);
        byte[] bytes = concat(new byte[]{(byte) 0xFF, (byte) 0xFE}, payload);

        ValidationOutcome outcome = validator.validate("txt", bytes);

        assertEquals("FIXED", outcome.getReport().getStatus());
        assertEquals("UTF-8", outcome.getReport().getEncodingUsed());
        assertTrue(decode(outcome).contains("很好用"));
    }

    @Test
    @DisplayName("不可见字符：零宽字符、NBSP、控制字符被清理")
    void invisibleCharsShouldBeCleaned() {
        String dirty = "很好\u200B用\u00A0的\u3000产品\u0001，物流快\uFEFF。";

        ValidationOutcome outcome = validator.validate("txt", dirty.getBytes(StandardCharsets.UTF_8));

        assertEquals("FIXED", outcome.getReport().getStatus());
        assertTrue(outcome.getReport().getIssues().stream()
                .anyMatch(issue -> "不可见字符".equals(issue.getType())));
        String repaired = decode(outcome);
        assertFalse(repaired.contains("\u200B"));
        assertFalse(repaired.contains("\u0001"));
        assertFalse(repaired.contains("\uFEFF"));
        assertTrue(repaired.contains("很好用"));
    }

    @Test
    @DisplayName("编码转换错误：UTF-8 被按 Latin-1 解码的乱码可反向还原")
    void mojibakeShouldBeRepaired() {
        String original = "这款商品非常好用，物流也很快。";
        String mojibake = new String(original.getBytes(StandardCharsets.UTF_8),
                StandardCharsets.ISO_8859_1);

        ValidationOutcome outcome = validator.validate("csv", mojibake.getBytes(StandardCharsets.UTF_8));

        assertEquals("FIXED", outcome.getReport().getStatus());
        assertTrue(outcome.getReport().getIssues().stream()
                .anyMatch(issue -> "编码转换错误".equals(issue.getType())));
        assertEquals(original, decode(outcome));
    }

    @Test
    @DisplayName("正常 UTF-8：校验通过，不做任何修改")
    void validUtf8ShouldPass() {
        String text = "评论编号,评论内容\nC001,音质不错";

        ValidationOutcome outcome = validator.validate("csv", text.getBytes(StandardCharsets.UTF_8));

        assertEquals("PASS", outcome.getReport().getStatus());
        assertFalse(outcome.isRepaired());
        assertEquals(text, decode(outcome));
    }

    @Test
    @DisplayName("扩展名与实际内容不符：.csv 实际是 xlsx 时自动纠正格式")
    void binaryFormatShouldBeCorrected() {
        byte[] bytes = {(byte) 0x50, 0x4B, 0x03, 0x04, 0x14, 0x00, 0x00, 0x00};

        ValidationOutcome outcome = validator.validate("csv", bytes);

        assertEquals("xlsx", outcome.getActualFormat());
        assertEquals("FIXED", outcome.getReport().getStatus());
        assertTrue(outcome.getReport().getIssues().stream()
                .anyMatch(issue -> "格式不符".equals(issue.getType())));
    }

    @Test
    @DisplayName("扩展名与实际内容不符：逗号文件实为制表符分隔时按 TSV 解析")
    void tsvShouldBeDetectedFromCsv() {
        String text = "评论编号\t评论内容\nT001\t音质不错\n";

        ValidationOutcome outcome = validator.validate("csv", text.getBytes(StandardCharsets.UTF_8));

        assertEquals("tsv", outcome.getActualFormat());
        assertEquals("FIXED", outcome.getReport().getStatus());
    }

    @Test
    @DisplayName("无法识别的编码：返回 ERROR 并阻断导入")
    void unreadableBytesShouldFail() {
        ValidationOutcome outcome = validator.validate("csv",
                new byte[]{(byte) 0xFF, (byte) 0xFF, (byte) 0xFF, (byte) 0xFF});

        assertEquals("ERROR", outcome.getReport().getStatus());
        assertTrue(outcome.isBlocking());
    }

    @Test
    @DisplayName("空文件：返回 ERROR 并阻断导入")
    void emptyFileShouldFail() {
        ValidationOutcome outcome = validator.validate("csv", new byte[0]);

        assertEquals("ERROR", outcome.getReport().getStatus());
        assertTrue(outcome.isBlocking());
    }

    private String decode(ValidationOutcome outcome) {
        return new String(outcome.getData(), StandardCharsets.UTF_8);
    }

    private byte[] concat(byte[] head, byte[] tail) {
        byte[] result = Arrays.copyOf(head, head.length + tail.length);
        System.arraycopy(tail, 0, result, head.length, tail.length);
        return result;
    }
}