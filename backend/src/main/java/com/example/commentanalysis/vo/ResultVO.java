package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 分析结果明细视图。
 *
 * <p>在 {@code analysis_result} 基础上回查 {@code comment_data} 补充评论原文，
 * 供结果列表分页展示。</p>
 *
 * @author 闫宇星
 */
@Data
public class ResultVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 结果编号 */
    private Long resultId;

    /** 任务编号 */
    private Long taskId;

    /** 评论编号 */
    private Long commentId;

    /** 评论原文 */
    private String content;

    /** 情感标签：POSITIVE / NEGATIVE / NEUTRAL */
    private String sentiment;

    /** 置信度 */
    private BigDecimal confidence;

    /** 该条评论关键词，逗号分隔 */
    private String keywords;

    /** 是否待人工复核：1 是 / 0 否 */
    private Integer needReview;

    /** 是否经过人工复核：1 是 / 0 否 */
    private Integer reviewed;

    /** 人工改判前的模型原判定，未改判为空 */
    private String originalSentiment;

    /** 单条推理耗时（毫秒） */
    private Integer inferTimeMs;

    /** 结果写入时间 */
    private LocalDateTime createTime;
}
