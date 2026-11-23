package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;

/**
 * 复核混淆矩阵的查询投影。
 *
 * <p>只承载「模型原判定 / 人工结论 / 条数」，矩阵结构与中文名在应用层补齐。</p>
 *
 * @author 闫宇星
 */
@Data
public class ReviewMatrixRow implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 模型原判定（未改判时取当前标签） */
    private String modelLabel;

    /** 人工结论（复核后的当前标签） */
    private String humanLabel;

    /** 条数 */
    private Long cnt;
}
