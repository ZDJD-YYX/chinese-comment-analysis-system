package com.example.commentanalysis.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.PageVO;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.entity.AnalysisResult;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.entity.CommentData;
import com.example.commentanalysis.entity.KeywordStatistics;
import com.example.commentanalysis.entity.TaskStatistics;
import com.example.commentanalysis.mapper.AnalysisResultMapper;
import com.example.commentanalysis.mapper.AnalysisTaskMapper;
import com.example.commentanalysis.mapper.CommentDataMapper;
import com.example.commentanalysis.mapper.KeywordStatisticsMapper;
import com.example.commentanalysis.mapper.TaskStatisticsMapper;
import com.example.commentanalysis.scheduler.InferenceScheduler;
import com.example.commentanalysis.service.AnalysisTaskService;
import com.example.commentanalysis.vo.BatchDeleteVO;
import com.example.commentanalysis.vo.ProgressVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

/**
 * 分析任务业务服务实现。
 *
 * @author 闫宇星
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AnalysisTaskServiceImpl extends ServiceImpl<AnalysisTaskMapper, AnalysisTask>
        implements AnalysisTaskService {

    /** 任务初始状态：待执行 */
    private static final String STATUS_PENDING = "PENDING";

    /** 任务状态：执行中 */
    private static final String STATUS_RUNNING = "RUNNING";

    /** 任务状态：失败 */
    private static final String STATUS_FAILED = "FAILED";

    /** 默认每页条数 */
    private static final int DEFAULT_PAGE_SIZE = 10;

    /** 异步推理调度器 */
    private final InferenceScheduler inferenceScheduler;

    /** 评论原始数据 Mapper（删除任务时级联清理） */
    private final CommentDataMapper commentDataMapper;

    /** 分析结果表 Mapper（删除任务时级联清理） */
    private final AnalysisResultMapper analysisResultMapper;

    /** 任务统计表 Mapper（删除任务时级联清理） */
    private final TaskStatisticsMapper taskStatisticsMapper;

    /** 关键词统计表 Mapper（删除任务时级联清理） */
    private final KeywordStatisticsMapper keywordStatisticsMapper;

    /** 每页条数上限 */
    private static final int MAX_PAGE_SIZE = 200;

    /** 单次批量删除任务数上限 */
    private static final int MAX_BATCH_DELETE = 100;

    /** 任务名称长度上限，与 analysis_task.task_name 列宽一致 */
    private static final int MAX_TASK_NAME_LENGTH = 100;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AnalysisTask createTask(AnalysisTask task) {
        if (task == null || !StringUtils.hasText(task.getTaskName())) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务名称不能为空");
        }
        LocalDateTime now = LocalDateTime.now();
        if (!StringUtils.hasText(task.getStatus())) {
            task.setStatus(STATUS_PENDING);
        }
        if (task.getTotalCount() == null) {
            task.setTotalCount(0);
        }
        if (task.getProcessedCount() == null) {
            task.setProcessedCount(0);
        }
        if (task.getErrorCount() == null) {
            task.setErrorCount(0);
        }
        if (task.getCreateTime() == null) {
            task.setCreateTime(now);
        }
        task.setUpdateTime(now);
        save(task);
        log.info("创建分析任务成功：taskId={}, taskName={}", task.getTaskId(), task.getTaskName());
        return task;
    }

    @Override
    public PageVO<AnalysisTask> pageTasks(Integer pageNum, Integer pageSize, String status, String keyword,
                                         String startTime, String endTime) {
        Page<AnalysisTask> page = new Page<>(normalizePageNum(pageNum), normalizePageSize(pageSize));
        LocalDateTime start = parseDate(startTime, false);
        LocalDateTime end = parseDate(endTime, true);
        LambdaQueryWrapper<AnalysisTask> wrapper = new LambdaQueryWrapper<AnalysisTask>()
                .eq(StringUtils.hasText(status), AnalysisTask::getStatus, status)
                .like(StringUtils.hasText(keyword), AnalysisTask::getTaskName, keyword)
                .ge(start != null, AnalysisTask::getCreateTime, start)
                .le(end != null, AnalysisTask::getCreateTime, end)
                .orderByDesc(AnalysisTask::getCreateTime);
        page(page, wrapper);
        return PageVO.of(page, page.getRecords());
    }

    /**
     * 解析任务列表的时间范围参数。
     *
     * <p>支持 yyyy-MM-dd（天粒度）与 yyyy-MM-dd HH:mm:ss（秒粒度）；
     * 解析失败时不抛异常，忽略该条件。</p>
     *
     * @param text   时间文本，可为空
     * @param endOfDay true 表示解析为当天的结束时刻（23:59:59）
     * @return 解析结果，空或非法时返回 null
     */
    private LocalDateTime parseDate(String text, boolean endOfDay) {
        if (!StringUtils.hasText(text)) {
            return null;
        }
        String value = text.trim();
        String format = value.length() >= 16 ? "yyyy-MM-dd HH:mm:ss" : "yyyy-MM-dd";
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern(format);
        try {
            LocalDateTime dateTime = format.length() >= 16
                    ? LocalDateTime.parse(value, formatter)
                    : LocalDate.parse(value, formatter).atTime(endOfDay ? 23 : 0, endOfDay ? 59 : 0, endOfDay ? 59 : 0);
            return dateTime;
        } catch (DateTimeParseException e) {
            log.warn("忽略非法的时间范围参数：{}", text);
            return null;
        }
    }

    @Override
    public AnalysisTask getTaskDetail(Long taskId) {
        if (taskId == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务编号不能为空");
        }
        // 逻辑删除的任务由 MyBatis-Plus 自动过滤，查不到即视为不存在
        AnalysisTask task = getById(taskId);
        if (task == null) {
            throw new BizException(ResultCode.TASK_NOT_FOUND);
        }
        return task;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteTask(Long taskId) {
        AnalysisTask task = getTaskDetail(taskId);
        if (STATUS_RUNNING.equals(task.getStatus())) {
            throw new BizException(ResultCode.TASK_STATUS_ILLEGAL, "任务正在执行中，请先终止任务后再操作");
        }
        // 级联删除评论原文、分析结果、任务统计与热点关键词数据（对应 FR-BIZ-24、概要设计 5.5⑤ 数据约束：
        // 子表未设 is_deleted 逻辑删除列，删除任务时于同一事务内清理，任务主表置 is_deleted=1；
        // 任一步失败整体回滚）
        commentDataMapper.delete(new LambdaQueryWrapper<CommentData>()
                .eq(CommentData::getTaskId, taskId));
        analysisResultMapper.delete(new LambdaQueryWrapper<AnalysisResult>()
                .eq(AnalysisResult::getTaskId, taskId));
        taskStatisticsMapper.delete(new LambdaQueryWrapper<TaskStatistics>()
                .eq(TaskStatistics::getTaskId, taskId));
        keywordStatisticsMapper.delete(new LambdaQueryWrapper<KeywordStatistics>()
                .eq(KeywordStatistics::getTaskId, taskId));
        removeById(taskId);
        log.info("逻辑删除分析任务并级联清理结果数据：taskId={}", taskId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public BatchDeleteVO batchDelete(List<Long> taskIds) {
        if (taskIds == null || taskIds.isEmpty()) {
            throw new BizException(ResultCode.BAD_REQUEST, "请先选择要删除的任务");
        }
        List<Long> ids = taskIds.stream()
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());
        if (ids.isEmpty()) {
            throw new BizException(ResultCode.BAD_REQUEST, "请先选择要删除的任务");
        }
        if (ids.size() > MAX_BATCH_DELETE) {
            throw new BizException(ResultCode.BAD_REQUEST,
                    "单次最多删除 " + MAX_BATCH_DELETE + " 个任务");
        }

        BatchDeleteVO result = new BatchDeleteVO();
        for (Long taskId : ids) {
            AnalysisTask task = getById(taskId);
            // 已删除或执行中的任务跳过，避免误删正在跑的结果
            if (task == null || STATUS_RUNNING.equals(task.getStatus())) {
                result.setSkipped(result.getSkipped() + 1);
                continue;
            }
            cascadeRemove(taskId);
            result.setDeleted(result.getDeleted() + 1);
        }
        log.info("批量删除任务完成：请求={}, 删除={}, 跳过={}",
                ids.size(), result.getDeleted(), result.getSkipped());
        return result;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AnalysisTask renameTask(Long taskId, String taskName) {
        AnalysisTask task = getTaskDetail(taskId);
        String name = taskName == null ? "" : taskName.trim();
        if (name.isEmpty()) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务名称不能为空");
        }
        if (name.length() > MAX_TASK_NAME_LENGTH) {
            throw new BizException(ResultCode.BAD_REQUEST,
                    "任务名称不能超过 " + MAX_TASK_NAME_LENGTH + " 个字符");
        }
        AnalysisTask update = new AnalysisTask();
        update.setTaskId(task.getTaskId());
        update.setTaskName(name);
        update.setUpdateTime(LocalDateTime.now());
        updateById(update);
        task.setTaskName(name);
        log.info("任务重命名成功：taskId={}, taskName={}", taskId, name);
        return task;
    }

    /**
     * 级联清理任务的分析结果、统计与关键词，并把任务置为逻辑删除。
     *
     * @param taskId 任务编号
     */
    private void cascadeRemove(Long taskId) {
        commentDataMapper.delete(new LambdaQueryWrapper<CommentData>()
                .eq(CommentData::getTaskId, taskId));
        analysisResultMapper.delete(new LambdaQueryWrapper<AnalysisResult>()
                .eq(AnalysisResult::getTaskId, taskId));
        taskStatisticsMapper.delete(new LambdaQueryWrapper<TaskStatistics>()
                .eq(TaskStatistics::getTaskId, taskId));
        keywordStatisticsMapper.delete(new LambdaQueryWrapper<KeywordStatistics>()
                .eq(KeywordStatistics::getTaskId, taskId));
        removeById(taskId);
    }

    @Override
    public void startInference(Long taskId) {
        AnalysisTask task = getTaskDetail(taskId);
        // 仅待执行与失败任务可启动，避免重复推理已完成任务
        if (!STATUS_PENDING.equals(task.getStatus()) && !STATUS_FAILED.equals(task.getStatus())) {
            throw new BizException(ResultCode.TASK_NOT_RETRYABLE);
        }
        // 异步提交，立即返回；队列满时提示稍后重试，任务保持待执行
        if (!inferenceScheduler.submitAsync(taskId)) {
            throw new BizException(ResultCode.SYSTEM_ERROR, "系统繁忙，任务队列已满，请稍后重试");
        }
    }

    @Override
    public void cancelTask(Long taskId) {
        AnalysisTask task = getTaskDetail(taskId);
        if (!STATUS_RUNNING.equals(task.getStatus())) {
            throw new BizException(ResultCode.TASK_NOT_CANCELABLE);
        }
        // 置终止标志位，当前批次结束后停止，已完成部分结果保留
        inferenceScheduler.cancel(taskId);
    }

    @Override
    public ProgressVO getProgress(Long taskId) {
        AnalysisTask task = getTaskDetail(taskId);
        int totalCount = task.getTotalCount() == null ? 0 : task.getTotalCount();
        int processedCount = task.getProcessedCount() == null ? 0 : task.getProcessedCount();
        // 百分比由应用层计算，不入库，避免同步更新的一致性问题
        int percent = totalCount <= 0
                ? 0
                : (int) Math.min(100L, Math.round(processedCount * 100.0D / totalCount));

        ProgressVO vo = new ProgressVO();
        vo.setTaskId(task.getTaskId());
        vo.setStatus(task.getStatus());
        vo.setTotalCount(totalCount);
        vo.setProcessedCount(processedCount);
        vo.setPercent(percent);
        vo.setStartTime(task.getStartTime());
        vo.setFinishTime(task.getFinishTime());
        return vo;
    }

    /**
     * 归一化页码。
     *
     * @param pageNum 原始页码
     * @return 合法页码，最小为 1
     */
    private int normalizePageNum(Integer pageNum) {
        return (pageNum == null || pageNum < 1) ? 1 : pageNum;
    }

    /**
     * 归一化每页条数。
     *
     * @param pageSize 原始每页条数
     * @return 合法每页条数，默认 10，上限 200
     */
    private int normalizePageSize(Integer pageSize) {
        if (pageSize == null || pageSize < 1) {
            return DEFAULT_PAGE_SIZE;
        }
        return Math.min(pageSize, MAX_PAGE_SIZE);
    }
}
