package com.example.commentanalysis.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 复核标记请求参数。
 *
 * <p>把单条分析结果标记为「已复核」或撤销该标记，用于低置信度结果的人工复核流程。</p>
 *
 * @author 闫宇星
 */
@Data
public class ReviewDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** true 表示标记为已复核，false 表示撤销复核标记 */
    private Boolean reviewed;

    /**
     * 人工复核后的情感结论：POSITIVE / NEGATIVE / NEUTRAL。
     *
     * <p>为空表示沿用模型原判定，仅确认复核；填写时会覆盖该条结果的最终情感标签，
     * 使汇总统计与导出结果与人工结论保持一致。</p>
     */
    private String sentiment;
}