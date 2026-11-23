package com.example.commentanalysis.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.example.commentanalysis.common.PageVO;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.vo.BatchDeleteVO;
import com.example.commentanalysis.vo.ProgressVO;

import java.util.List;

/**
 * 分析任务业务服务接口。
 *
 * <p>继承 {@link IService} 获得通用业务 CRUD 能力，并在此之上提供
 * 任务创建、分页查询、详情查询与删除等业务方法。</p>
 *
 * @author 闫宇星
 */
public interface AnalysisTaskService extends IService<AnalysisTask> {

    /**
     * 创建分析任务。
     *
     * <p>校验任务名称非空，并补全状态、进度等技术字段的默认值。</p>
     *
     * @param task 任务实体（至少需包含任务名称）
     * @return 已持久化的任务实体（含自增主键）
     */
    AnalysisTask createTask(AnalysisTask task);

    /**
     * 分页查询任务列表。
     *
     * <p>按创建时间倒序返回，支持按状态精确筛选、任务名称模糊检索与创建时间范围筛选
     * （对应 FR-BIZ-21 / FR-BIZ-22）。</p>
     *
     * @param pageNum   页码，从 1 开始，非法值按 1 处理
     * @param pageSize  每页条数，非法值按 10 处理，上限 200
     * @param status    任务状态，可为空
     * @param keyword   任务名称关键字，可为空
     * @param startTime 创建时间范围下限（yyyy-MM-dd），可为空
     * @param endTime   创建时间范围上限（yyyy-MM-dd），可为空
     * @return 任务分页结果
     */
    PageVO<AnalysisTask> pageTasks(Integer pageNum, Integer pageSize, String status, String keyword,
                                  String startTime, String endTime);

    /**
     * 查询任务详情。
     *
     * @param taskId 任务编号
     * @return 任务详情
     */
    AnalysisTask getTaskDetail(Long taskId);

    /**
     * 删除任务（逻辑删除，级联清理结果数据）。
     *
     * <p>校验任务非执行中；同一事务内删除分析结果、任务统计与热点关键词数据，
     * 任务主表置 {@code is_deleted = 1}；任一步失败整体回滚。</p>
     *
     * @param taskId 任务编号
     */
    void deleteTask(Long taskId);

    /**
     * 批量删除任务（逻辑删除，级联清理结果数据）。
     *
     * <p>执行中的任务会被跳过，其余任务逐条清理分析结果、统计与关键词数据。</p>
     *
     * @param taskIds 任务编号列表
     * @return 删除结果（成功条数与跳过条数）
     */
    BatchDeleteVO batchDelete(List<Long> taskIds);

    /**
     * 重命名任务。
     *
     * @param taskId   任务编号
     * @param taskName 新任务名称，长度 1～100
     * @return 更新后的任务详情
     */
    AnalysisTask renameTask(Long taskId, String taskName);

    /**
     * 启动（或重试）分析任务。
     *
     * <p>校验任务状态为待执行或失败，随后异步提交至推理线程池，方法立即返回。
     * 前端可通过进度接口轮询 {@code status} 与 {@code percent}。</p>
     *
     * @param taskId 任务编号
     */
    void startInference(Long taskId);

    /**
     * 终止执行中的任务。
     *
     * <p>仅置终止标志位，当前批次结束后停止并置为 {@code CANCELED}，已完成部分结果保留。</p>
     *
     * @param taskId 任务编号
     */
    void cancelTask(Long taskId);

    /**
     * 查询任务进度。
     *
     * @param taskId 任务编号
     * @return 进度信息（含百分比）
     */
    ProgressVO getProgress(Long taskId);
}
