package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;

/**
 * 置信度区间计数的查询投影。
 *
 * <p>只承载「区间序号 + 条数」，具体标签与占比在应用层补齐。</p>
 *
 * @author 闫宇星
 */
@Data
public class ConfidenceBucketRow implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 区间序号：0 表示 0.0～0.1，9 表示 0.9～1.0 */
    private Integer bucketIndex;

    /** 该区间条数 */
    private Long cnt;
}
