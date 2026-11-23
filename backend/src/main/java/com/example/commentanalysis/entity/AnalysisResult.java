package com.example.commentanalysis.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 分析结果表实体，对应数据表 {@code analysis_result}。
 *
 * <p>系统核心结果表，每条评论对应一条记录，保存情感标签、置信度、关键词与推理耗时。
 * 置信度使用 {@link BigDecimal} 承载 DECIMAL(6,4)，禁止用浮点数存储概率值。</p>
 *
 * @author 闫宇星
 */
@Data
@TableName("analysis_result")
public class AnalysisResult implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 结果编号，主键，数据库自增 */
    @TableId(value = "result_id", type = IdType.AUTO)
    private Long resultId;

    /** 任务编号（冗余字段，规避关联查询） */
    @TableField("task_id")
    private Long taskId;

    /** 评论编号，关联 comment_data.comment_id */
    @TableField("comment_id")
    private Long commentId;

    /** 情感标签：POSITIVE / NEGATIVE / NEUTRAL */
    @TableField("sentiment")
    private String sentiment;

    /** 置信度，取值 [0.0000, 1.0000]，保留四位小数 */
    @TableField("confidence")
    private BigDecimal confidence;

    /** 该条评论提取的关键词，多个用英文逗号分隔 */
    @TableField("keywords")
    private String keywords;

    /** 是否待人工复核：置信度 < 0.60 时置 1 */
    @TableField("need_review")
    private Integer needReview;

    /** 是否经过人工复核：1 是 / 0 否 */
    @TableField("reviewed")
    private Integer reviewed;

    /** 人工改判前的模型原判定，未改判为 null */
    @TableField("original_sentiment")
    private String originalSentiment;

    /** 单条评论推理耗时（毫秒，不含数据库写入） */
    @TableField("infer_time_ms")
    private Integer inferTimeMs;

    /** 结果写入时间 */
    @TableField("create_time")
    private LocalDateTime createTime;
}
