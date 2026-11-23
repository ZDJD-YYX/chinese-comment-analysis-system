package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

/**
 * 导入校验报告。
 *
 * <p>记录一次文件导入的自动校验与修复结果：检测到的编码、实际格式、
 * 处理状态、问题明细以及原始文件备份信息。</p>
 *
 * @author 闫宇星
 */
@Data
public class ImportValidationVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 校验状态：PASS 通过 / FIXED 已自动修复 / WARNING 有需关注项 / ERROR 无法处理 */
    private String status = "PASS";

    /** 上传时的扩展名 */
    private String originalFormat;

    /** 实际识别出的格式（扩展名与内容不一致时会被纠正） */
    private String actualFormat;

    /** 检测到的原始编码，二进制格式为「二进制」 */
    private String encodingDetected;

    /** 实际用于解析的编码 */
    private String encodingUsed;

    /** 是否执行过自动修复 */
    private boolean repaired;

    /** 修复后无有效数据、已回退原始文件解析 */
    private boolean fallbackUsed;

    /** 一句话结论，直接展示给用户 */
    private String summary;

    /** 问题明细 */
    private List<ValidationIssueVO> issues = new ArrayList<>();

    /** 原始文件备份文件名（用于下载回退），为空表示未备份 */
    private String backupFile;

    /** 原始文件字节数 */
    private Long backupSize;
}