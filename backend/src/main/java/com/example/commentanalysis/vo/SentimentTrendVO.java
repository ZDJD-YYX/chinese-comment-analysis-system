package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

/**
 * 情感趋势视图。
 *
 * <p>按评论原始时间聚合三类情感条数，供前端绘制折线图（对应需求 FR-BIZ-18：
 * 数据无时间字段时不返回数据点，前端据此隐藏图表）。</p>
 *
 * @author 闫宇星
 */
@Data
public class SentimentTrendVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 聚合粒度：hour / day */
    private String granularity;

    /** 时间桶数据点，按时间升序 */
    private List<Point> points = new ArrayList<>();

    /**
     * 单个时间桶。
     */
    @Data
    public static class Point implements Serializable {

        private static final long serialVersionUID = 1L;

        /** 时间桶标签：按天 yyyy-MM-dd、按小时 yyyy-MM-dd HH:00 */
        private String bucket;

        /** 正面条数 */
        private long positive;

        /** 负面条数 */
        private long negative;

        /** 中性条数 */
        private long neutral;

        /** 该时间桶总条数 */
        private long total;
    }
}
