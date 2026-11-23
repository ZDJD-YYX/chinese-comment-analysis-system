package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;

/**
 * 任务情感分布统计视图。
 *
 * <p>占比字段由应用层按 条数 / 总数 计算，不落库，避免冗余数据与明细不一致
 * （对应数据库设计 3.5 节设计说明）。</p>
 *
 * @author 闫宇星
 */
@Data
public class SentimentStatisticsVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 任务编号 */
    private Long taskId;

    /** 参与统计的评论总数 */
    private Long totalCount;

    /** 正面条数 */
    private Long positiveCount;

    /** 负面条数 */
    private Long negativeCount;

    /** 中性条数 */
    private Long neutralCount;

    /** 正面占比 */
    private BigDecimal positiveRatio;

    /** 负面占比 */
    private BigDecimal negativeRatio;

    /** 中性占比 */
    private BigDecimal neutralRatio;

    /** 待人工复核条数 */
    private Long reviewCount;

    /** 异常样本数 */
    private Integer errorCount;

    /** 平均置信度 */
    private BigDecimal avgConfidence;
}
