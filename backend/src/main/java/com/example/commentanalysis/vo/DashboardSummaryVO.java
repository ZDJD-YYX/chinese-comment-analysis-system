package com.example.commentanalysis.vo;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;

/**
 * 数据看板汇总视图。
 *
 * <p>跨任务聚合：任务与评论总量、整体情感分布、待复核规模，
 * 以及最近 7 天的任务量走势和最近任务列表。</p>
 *
 * @author 闫宇星
 */
@Data
public class DashboardSummaryVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 任务总数（不含已删除） */
    private long totalTasks;

    /** 已完成任务数 */
    private long successTasks;

    /** 执行中任务数 */
    private long runningTasks;

    /** 累计评论条数（按任务解析条数汇总） */
    private long totalComments;

    /** 正面条数 */
    private long positiveCount;

    /** 负面条数 */
    private long negativeCount;

    /** 中性条数 */
    private long neutralCount;

    /** 待人工复核条数 */
    private long reviewCount;

    /** 整体加权平均置信度 */
    private BigDecimal avgConfidence;

    /** 最近 7 天任务量走势 */
    private List<DailyCount> trend = Collections.emptyList();

    /** 最近任务 */
    private List<TaskBrief> recentTasks = Collections.emptyList();

    /**
     * 单日任务量。
     */
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DailyCount implements Serializable {

        private static final long serialVersionUID = 1L;

        /** 日期，格式 MM-dd */
        private String date;

        /** 当日任务数 */
        private long count;
    }

    /**
     * 任务摘要。
     */
    @Data
    public static class TaskBrief implements Serializable {

        private static final long serialVersionUID = 1L;

        /** 任务编号 */
        private Long taskId;

        /** 任务名称 */
        private String taskName;

        /** 任务状态 */
        private String status;

        /** 评论条数 */
        private Integer totalCount;

        /** 创建时间 */
        private LocalDateTime createTime;
    }
}