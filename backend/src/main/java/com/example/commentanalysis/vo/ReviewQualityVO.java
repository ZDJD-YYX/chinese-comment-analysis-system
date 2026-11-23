package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 复核质量视图。
 *
 * <p>基于人工复核记录评估模型表现：一致率、改判规模、改判方向分布与模型/人工混淆矩阵。
 * 只有经过人工复核的样本参与统计，未复核样本不计入分母，避免拉高一致率。</p>
 *
 * @author 闫宇星
 */
@Data
public class ReviewQualityVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 任务编号 */
    private Long taskId;

    /** 已复核样本数 */
    private long reviewedCount;

    /** 人工同意模型判定的样本数 */
    private long agreementCount;

    /** 人工改判的样本数 */
    private long correctedCount;

    /** 一致率（0～1），已复核为 0 时为空 */
    private BigDecimal agreementRate;

    /** 情感标签顺序，矩阵行列均按此顺序 */
    private List<String> labels = new ArrayList<>();

    /** 情感标签中文名，与 labels 一一对应 */
    private List<String> labelNames = new ArrayList<>();

    /** 混淆矩阵单元格：模型原判定 → 人工结论 */
    private List<MatrixCell> matrix = new ArrayList<>();

    /** 改判方向分布：原判定 → 人工结论 */
    private List<Correction> corrections = new ArrayList<>();

    /**
     * 混淆矩阵单元格。
     */
    @Data
    public static class MatrixCell implements Serializable {

        private static final long serialVersionUID = 1L;

        /** 模型原判定 */
        private String modelLabel;

        /** 人工结论 */
        private String humanLabel;

        /** 条数 */
        private long count;
    }

    /**
     * 改判方向。
     */
    @Data
    public static class Correction implements Serializable {

        private static final long serialVersionUID = 1L;

        /** 原判定 */
        private String fromLabel;

        /** 改判后的结论 */
        private String toLabel;

        /** 条数 */
        private long count;
    }
}
