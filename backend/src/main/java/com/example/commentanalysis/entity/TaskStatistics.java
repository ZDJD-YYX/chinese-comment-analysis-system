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
 * 任务统计表实体，对应数据表 {@code task_statistics}。
 *
 * <p>保存任务整体统计结果，与任务一对一（唯一索引 {@code uk_task}）。
 * 由推理任务收尾阶段一次性写入，供可视化摘要页与历史任务列表直接读取，
 * 避免每次打开页面都触发大范围 {@code GROUP BY}（对应数据库设计优化点 ⑤）。</p>
 *
 * <p>占比为可推导字段，不落库，由应用层按 {@code 条数 / total_count} 计算。</p>
 *
 * <p>注意：本类同时用作 {@code AnalysisResultMapper.selectSummary} 的聚合查询投影，
 * 聚合结果仅填充计数、平均置信度与总耗时字段，主键与时间字段由调用方补齐。</p>
 *
 * @author 闫宇星
 */
@Data
@TableName("task_statistics")
public class TaskStatistics implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 统计编号，主键，数据库自增 */
    @TableId(value = "stat_id", type = IdType.AUTO)
    private Long statId;

    /** 任务编号，唯一，保证一任务一条统计 */
    @TableField("task_id")
    private Long taskId;

    /** 参与统计的评论总数 */
    @TableField("total_count")
    private Integer totalCount;

    /** 正面评论条数 */
    @TableField("positive_count")
    private Integer positiveCount;

    /** 负面评论条数 */
    @TableField("negative_count")
    private Integer negativeCount;

    /** 中性评论条数 */
    @TableField("neutral_count")
    private Integer neutralCount;

    /** 置信度低于阈值、待人工复核的条数 */
    @TableField("review_count")
    private Integer reviewCount;

    /** 推理异常被跳过的条数 */
    @TableField("error_count")
    private Integer errorCount;

    /** 全部结果的平均置信度 */
    @TableField("avg_confidence")
    private BigDecimal avgConfidence;

    /** 推理总耗时（毫秒），用于性能评估 */
    @TableField("total_infer_time_ms")
    private Long totalInferTimeMs;

    /** 统计生成时间 */
    @TableField("create_time")
    private LocalDateTime createTime;

    /** 最近更新时间 */
    @TableField("update_time")
    private LocalDateTime updateTime;
}
