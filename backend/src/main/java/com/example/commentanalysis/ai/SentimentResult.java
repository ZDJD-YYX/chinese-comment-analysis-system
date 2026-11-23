package com.example.commentanalysis.ai;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * 单条评论的情感推理结果。
 *
 * <p>纯数据结构，不依赖任何 DJL 类型，业务层可直接使用。</p>
 *
 * @author 闫宇星
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class SentimentResult implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 兜底标签：空文本或推理异常时输出 */
    public static final String FALLBACK_LABEL = "NEUTRAL";

    /** 情感标签：POSITIVE / NEGATIVE / NEUTRAL */
    private String label;

    /** 置信度（最大类别概率），取值 [0,1]，保留四位小数 */
    private double score;

    /** 是否待人工复核：score 低于阈值时为 true */
    private boolean needReview;

    /** 单条推理耗时（毫秒） */
    private double inferTimeMs;

    /** 是否为异常兜底结果（用于调度层累计 error_count） */
    private boolean error;

    /**
     * 构造兜底结果：中性 + 置信度 0 + 待复核。
     *
     * <p>与《详细设计说明书》5.4 异常容错约定一致，保证单条异常不中断批量任务。</p>
     *
     * @param error 是否为异常导致（true 计入任务 error_count；空文本传 false）
     * @return 兜底结果
     */
    public static SentimentResult fallback(boolean error) {
        return new SentimentResult(FALLBACK_LABEL, 0.0D, true, 0.0D, error);
    }
}
