package com.example.commentanalysis.validation;

import com.example.commentanalysis.vo.ImportValidationVO;
import lombok.Data;

import java.nio.charset.Charset;

/**
 * 导入校验的中间结果。
 *
 * <p>携带修复后的字节流、实际格式与解析用编码，同时保留原始字节与原始编码，
 * 以便修复后解析不到有效数据时回退。</p>
 *
 * @author 闫宇星
 */
@Data
public class ValidationOutcome {

    /** 修复后的字节流（无问题时为原始字节） */
    private byte[] data;

    /** 原始字节流，用于异常回退 */
    private byte[] originalData;

    /** 实际格式：csv / xlsx / xls / txt / tsv / json */
    private String actualFormat;

    /** 解析用字符集；二进制格式为 null */
    private Charset charset;

    /** 原始文本检测出的字符集；二进制或无法识别时为 null */
    private Charset originalCharset;

    /** 是否执行过自动修复 */
    private boolean repaired;

    /** 校验报告 */
    private ImportValidationVO report;

    /**
     * 是否因格式错误无法继续解析。
     *
     * @return true 表示应中止导入
     */
    public boolean isBlocking() {
        return report != null && "ERROR".equals(report.getStatus());
    }
}