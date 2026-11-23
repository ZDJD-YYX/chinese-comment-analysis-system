package com.example.commentanalysis.vo;

import com.alibaba.excel.annotation.ExcelProperty;
import com.alibaba.excel.annotation.write.style.ColumnWidth;
import lombok.Data;

import java.io.Serializable;

/**
 * 导出统计摘要工作表行模型。
 *
 * <p>用于「统计摘要」工作表（FR-BIZ-26）：每行由「项目 / 数值 / 备注」三列组成，
 * 情感占比段使用项目与数值列，热点词段三项均使用。</p>
 *
 * @author 闫宇星
 */
@Data
public class SummaryRowVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 项目名称 */
    @ExcelProperty("项目")
    @ColumnWidth(28)
    private String item;

    /** 数值 */
    @ExcelProperty("数值")
    @ColumnWidth(26)
    private String value;

    /** 备注（热点词部分的词频等） */
    @ExcelProperty("备注")
    @ColumnWidth(14)
    private String extra;
}