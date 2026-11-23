package com.example.commentanalysis.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.entity.TaskStatistics;
import com.example.commentanalysis.mapper.AnalysisTaskMapper;
import com.example.commentanalysis.mapper.TaskStatisticsMapper;
import com.example.commentanalysis.service.DashboardService;
import com.example.commentanalysis.vo.DashboardSummaryVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 数据看板服务实现。
 *
 * <p>任务与统计均取未删除记录；任务量级为单用户本地场景（千级以内），
 * 因此直接在应用层聚合，避免为看板额外增加 SQL 复杂度。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DashboardServiceImpl implements DashboardService {

    /** 任务状态：已完成 */
    private static final String STATUS_SUCCESS = "SUCCESS";

    /** 任务状态：执行中 */
    private static final String STATUS_RUNNING = "RUNNING";

    /** 趋势图展示天数 */
    private static final int TREND_DAYS = 7;

    /** 最近任务展示条数 */
    private static final int RECENT_TASK_SIZE = 5;

    /** 趋势图日期格式 */
    private static final DateTimeFormatter TREND_FORMATTER = DateTimeFormatter.ofPattern("MM-dd");

    private final AnalysisTaskMapper analysisTaskMapper;

    private final TaskStatisticsMapper taskStatisticsMapper;

    @Override
    public DashboardSummaryVO summary() {
        DashboardSummaryVO vo = new DashboardSummaryVO();

        List<AnalysisTask> tasks = analysisTaskMapper.selectList(
                new LambdaQueryWrapper<AnalysisTask>()
                        .orderByDesc(AnalysisTask::getCreateTime));

        vo.setTotalTasks(tasks.size());
        vo.setSuccessTasks(tasks.stream().filter(task -> STATUS_SUCCESS.equals(task.getStatus())).count());
        vo.setRunningTasks(tasks.stream().filter(task -> STATUS_RUNNING.equals(task.getStatus())).count());
        vo.setTotalComments(tasks.stream()
                .map(AnalysisTask::getTotalCount)
                .filter(count -> count != null)
                .mapToLong(Integer::longValue)
                .sum());

        List<Long> taskIds = tasks.stream()
                .map(AnalysisTask::getTaskId)
                .collect(Collectors.toList());
        fillSentimentSummary(vo, taskIds);
        vo.setTrend(buildTrend(tasks));
        vo.setRecentTasks(buildRecentTasks(tasks));
        return vo;
    }

    /**
     * 汇总各任务预聚合统计中的情感条数、待复核条数与加权平均置信度。
     *
     * @param vo      看板视图
     * @param taskIds 未删除任务编号
     */
    private void fillSentimentSummary(DashboardSummaryVO vo, List<Long> taskIds) {
        if (taskIds.isEmpty()) {
            vo.setAvgConfidence(null);
            return;
        }
        List<TaskStatistics> statisticsList = taskStatisticsMapper.selectList(
                new LambdaQueryWrapper<TaskStatistics>().in(TaskStatistics::getTaskId, taskIds));

        long positive = 0L;
        long negative = 0L;
        long neutral = 0L;
        long review = 0L;
        long total = 0L;
        BigDecimal weightedSum = BigDecimal.ZERO;

        for (TaskStatistics statistics : statisticsList) {
            long taskTotal = toLong(statistics.getTotalCount());
            positive += toLong(statistics.getPositiveCount());
            negative += toLong(statistics.getNegativeCount());
            neutral += toLong(statistics.getNeutralCount());
            review += toLong(statistics.getReviewCount());
            total += taskTotal;
            if (statistics.getAvgConfidence() != null && taskTotal > 0) {
                // 以各任务条数为权重汇总平均置信度，避免小任务与大任务等权平均带来的偏差
                weightedSum = weightedSum.add(
                        statistics.getAvgConfidence().multiply(BigDecimal.valueOf(taskTotal)));
            }
        }

        vo.setPositiveCount(positive);
        vo.setNegativeCount(negative);
        vo.setNeutralCount(neutral);
        vo.setReviewCount(review);
        vo.setAvgConfidence(total > 0
                ? weightedSum.divide(BigDecimal.valueOf(total), 4, RoundingMode.HALF_UP)
                : null);
    }

    /**
     * 统计最近 7 天每天创建的任务数。
     *
     * @param tasks 全部任务
     * @return 按日期升序的走势数据
     */
    private List<DashboardSummaryVO.DailyCount> buildTrend(List<AnalysisTask> tasks) {
        if (tasks.isEmpty()) {
            return Collections.emptyList();
        }
        LocalDate today = LocalDate.now();
        List<DashboardSummaryVO.DailyCount> trend = new ArrayList<>(TREND_DAYS);
        for (int i = TREND_DAYS - 1; i >= 0; i--) {
            LocalDate date = today.minusDays(i);
            long count = tasks.stream()
                    .filter(task -> task.getCreateTime() != null
                            && date.equals(task.getCreateTime().toLocalDate()))
                    .count();
            trend.add(new DashboardSummaryVO.DailyCount(date.format(TREND_FORMATTER), count));
        }
        return trend;
    }

    /**
     * 取最近的若干任务。
     *
     * @param tasks 按创建时间倒序排列的任务
     * @return 最近任务摘要
     */
    private List<DashboardSummaryVO.TaskBrief> buildRecentTasks(List<AnalysisTask> tasks) {
        return tasks.stream()
                .limit(RECENT_TASK_SIZE)
                .map(task -> {
                    DashboardSummaryVO.TaskBrief brief = new DashboardSummaryVO.TaskBrief();
                    brief.setTaskId(task.getTaskId());
                    brief.setTaskName(task.getTaskName());
                    brief.setStatus(task.getStatus());
                    brief.setTotalCount(task.getTotalCount());
                    brief.setCreateTime(task.getCreateTime());
                    return brief;
                })
                .collect(Collectors.toList());
    }

    private long toLong(Integer value) {
        return value == null ? 0L : value.longValue();
    }
}