package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 评论时间范围投影。
 *
 * <p>用于判断趋势图应按小时还是按天聚合。</p>
 *
 * @author 闫宇星
 */
@Data
public class CommentTimeRangeVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 最早评论时间 */
    private LocalDateTime minTime;

    /** 最晚评论时间 */
    private LocalDateTime maxTime;
}
