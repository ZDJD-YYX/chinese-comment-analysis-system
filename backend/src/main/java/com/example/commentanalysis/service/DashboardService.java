package com.example.commentanalysis.service;

import com.example.commentanalysis.vo.DashboardSummaryVO;

/**
 * 数据看板服务。
 *
 * @author 闫宇星
 */
public interface DashboardService {

    /**
     * 跨任务汇总统计。
     *
     * @return 看板汇总数据
     */
    DashboardSummaryVO summary();
}