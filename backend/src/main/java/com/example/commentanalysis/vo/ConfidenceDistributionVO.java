package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 置信度分布视图。
 *
 * <p>按区间统计置信度条数，用于直方图展示（P2 分析深度）：能直观看出低置信度样本的占比，
 * 比只看平均置信度更有判断价值。</p>
 *
 * @author 闫宇星
 */
@Data
public class ConfidenceDistributionVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 任务编号 */
    private Long taskId;

    /** 参与统计的结果总数 */
    private long totalCount;

    /** 低于复核阈值的条数 */
    private long belowThresholdCount;

    /** 低于复核阈值的占比（0～1） */
    private BigDecimal belowThresholdRatio;

    /** 低置信度复核阈值 */
    private double threshold;

    /** 区间分布，按区间升序 */
    private List<Bucket> buckets = new ArrayList<>();

    /**
     * 单个置信度区间。
     */
    @Data
    public static class Bucket implements Serializable {

        private static final long serialVersionUID = 1L;

        /** 区间标签，如 0.6～0.7 */
        private String label;

        /** 区间下限（含） */
        private double lower;

        /** 区间上限（不含，最后一档含） */
        private double upper;

        /** 该区间条数 */
        private long count;

        /** 该区间占比（0～1） */
        private BigDecimal ratio;
    }
}
