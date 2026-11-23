package com.example.commentanalysis.controller;

import com.example.commentanalysis.common.Result;
import com.example.commentanalysis.service.DashboardService;
import com.example.commentanalysis.vo.DashboardSummaryVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 数据看板控制器。
 *
 * @author 闫宇星
 */
@RestController
@RequestMapping("/api/dashboard")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    /**
     * 查询跨任务汇总数据。
     *
     * @return 看板汇总
     */
    @GetMapping("/summary")
    public Result<DashboardSummaryVO> summary() {
        return Result.success(dashboardService.summary());
    }
}