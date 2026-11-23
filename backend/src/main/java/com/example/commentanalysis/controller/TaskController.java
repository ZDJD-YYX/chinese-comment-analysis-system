package com.example.commentanalysis.controller;

import com.example.commentanalysis.common.PageVO;
import com.example.commentanalysis.common.Result;
import com.example.commentanalysis.config.AuthInterceptor;
import com.example.commentanalysis.dto.TaskBatchDeleteDTO;
import com.example.commentanalysis.dto.TaskRenameDTO;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.service.AnalysisTaskService;
import com.example.commentanalysis.service.AuditLogService;
import com.example.commentanalysis.vo.BatchDeleteVO;
import com.example.commentanalysis.vo.ProgressVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpSession;

/**
 * 分析任务控制器。
 *
 * @author 闫宇星
 */
@RestController
@RequestMapping("/api/task")
@RequiredArgsConstructor
public class TaskController {

    private final AnalysisTaskService analysisTaskService;

    private final AuditLogService auditLogService;

    /**
     * 分页查询任务列表。
     *
     * <p>按创建时间倒序返回；支持按状态、任务名称关键字与创建时间范围组合筛选
     * （时间范围为需求 FR-BIZ-22「按时间范围、任务状态、文件名关键字组合查询」）。</p>
     *
     * @param pageNum   页码，从 1 开始，默认 1
     * @param pageSize  每页条数，默认 10，上限 200
     * @param status    任务状态筛选（PENDING/RUNNING/SUCCESS/FAILED/CANCELED），可为空
     * @param keyword   任务名称关键字，可为空
     * @param startTime 创建时间范围下限（yyyy-MM-dd），可为空
     * @param endTime   创建时间范围上限（yyyy-MM-dd），可为空
     * @return 任务分页数据
     */
    @GetMapping("/list")
    public Result<PageVO<AnalysisTask>> list(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime) {
        return Result.success(
                analysisTaskService.pageTasks(pageNum, pageSize, status, keyword, startTime, endTime));
    }

    /**
     * 查询任务详情。
     *
     * @param id 任务编号
     * @return 任务详情
     */
    @GetMapping("/{id}")
    public Result<AnalysisTask> detail(@PathVariable("id") Long id) {
        return Result.success(analysisTaskService.getTaskDetail(id));
    }

    /**
     * 删除任务（逻辑删除）。
     *
     * @param id 任务编号
     * @return 操作结果
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable("id") Long id, HttpSession session) {
        analysisTaskService.deleteTask(id);
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                "删除任务", "任务编号 " + id);
        return Result.success();
    }

    /**
     * 重命名任务。
     *
     * @param id      任务编号
     * @param dto     新任务名称
     * @param session HTTP 会话
     * @return 更新后的任务详情
     */
    @PostMapping("/{id}/rename")
    public Result<AnalysisTask> rename(@PathVariable("id") Long id,
                                       @RequestBody TaskRenameDTO dto,
                                       HttpSession session) {
        AnalysisTask task = analysisTaskService.renameTask(id,
                dto == null ? null : dto.getTaskName());
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                "重命名任务", "任务编号 " + id + " → " + task.getTaskName());
        return Result.success("任务名称已更新", task);
    }

    /**
     * 批量删除任务。
     *
     * <p>执行中的任务会被跳过，返回删除与跳过的条数供前端提示。</p>
     *
     * @param dto     任务编号列表
     * @param session HTTP 会话
     * @return 删除结果
     */
    @PostMapping("/batch-delete")
    public Result<BatchDeleteVO> batchDelete(@RequestBody TaskBatchDeleteDTO dto,
                                             HttpSession session) {
        BatchDeleteVO result = analysisTaskService.batchDelete(
                dto == null ? null : dto.getTaskIds());
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                "批量删除任务", "删除 " + result.getDeleted() + " 个，跳过 " + result.getSkipped());
        return Result.success("已删除 " + result.getDeleted() + " 个任务，跳过 "
                + result.getSkipped() + " 个", result);
    }

    /**
     * 启动或重试情感分析（异步）。
     *
     * <p>仅待执行或失败任务可启动。接口立即返回，进度通过进度查询接口轮询。</p>
     *
     * @param id 任务编号
     * @return 操作结果
     */
    @PostMapping("/{id}/run")
    public Result<Void> run(@PathVariable("id") Long id, HttpSession session) {
        analysisTaskService.startInference(id);
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                "启动分析", "任务编号 " + id);
        return Result.success("分析任务已提交，请通过任务详情查询进度", null);
    }

    /**
     * 查询任务进度（供前端轮询）。
     *
     * @param id 任务编号
     * @return 进度信息，含状态、已处理条数与百分比
     */
    @GetMapping("/{id}/progress")
    public Result<ProgressVO> progress(@PathVariable("id") Long id) {
        return Result.success(analysisTaskService.getProgress(id));
    }

    /**
     * 终止执行中的任务。
     *
     * <p>终止标志位在当前批次结束后生效，已完成部分结果保留。</p>
     *
     * @param id 任务编号
     * @return 操作结果
     */
    @PostMapping("/{id}/cancel")
    public Result<Void> cancel(@PathVariable("id") Long id) {
        analysisTaskService.cancelTask(id);
        return Result.success("终止请求已受理，任务将在当前批次结束后停止", null);
    }
}
