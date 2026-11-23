package com.example.commentanalysis.dto;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 批量复核请求参数。
 *
 * <p>对多条分析结果一次性提交相同的复核状态与结论，减少逐条操作的重复劳动。</p>
 *
 * @author 闫宇星
 */
@Data
public class BatchReviewDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 结果编号列表 */
    private List<Long> resultIds;

    /** true 表示标记为已复核，false 表示撤销复核 */
    private Boolean reviewed;

    /** 人工复核后的情感结论：POSITIVE / NEGATIVE / NEUTRAL，可为空 */
    private String sentiment;
}
