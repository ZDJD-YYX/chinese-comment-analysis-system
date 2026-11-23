package com.example.commentanalysis.vo;

import com.alibaba.excel.annotation.ExcelProperty;
import com.alibaba.excel.annotation.format.DateTimeFormat;
import com.alibaba.excel.annotation.write.style.ColumnWidth;
import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 分析结果导出模型（EasyExcel 写入模型）。
 *
 * <p>每个字段对应导出 Excel 的一列，列名由 {@link ExcelProperty} 声明。</p>
 *
 * @author 闫宇星
 */
@Data
public class ResultExportVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 评论编号 */
    @ExcelProperty("评论编号")
    @ColumnWidth(12)
    private Long commentId;

    /** 评论原文 */
    @ExcelProperty("评论内容")
    @ColumnWidth(50)
    private String content;

    /** 情感标签（中文） */
    @ExcelProperty("情感标签")
    @ColumnWidth(12)
    private String sentimentLabel;

    /** 置信度 */
    @ExcelProperty("置信度")
    @ColumnWidth(12)
    private BigDecimal confidence;

    /** 关键词 */
    @ExcelProperty("关键词")
    @ColumnWidth(30)
    private String keywords;

    /** 是否待人工复核（中文） */
    @ExcelProperty("是否待人工复核")
    @ColumnWidth(16)
    private String reviewLabel;

    /** 是否经过人工复核（中文） */
    @ExcelProperty("是否人工复核")
    @ColumnWidth(14)
    private String reviewedLabel;

    /** 是否发生人工改判（中文） */
    @ExcelProperty("是否改判")
    @ColumnWidth(12)
    private String correctedLabel;

    /** 模型原判定（中文，未改判时为空） */
    @ExcelProperty("模型原判定")
    @ColumnWidth(14)
    private String originalSentimentLabel;

    /** 推理耗时（毫秒） */
    @ExcelProperty("推理耗时(ms)")
    @ColumnWidth(14)
    private Integer inferTimeMs;

    /** 分析时间 */
    @ExcelProperty("分析时间")
    @ColumnWidth(22)
    @DateTimeFormat("yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;
}
