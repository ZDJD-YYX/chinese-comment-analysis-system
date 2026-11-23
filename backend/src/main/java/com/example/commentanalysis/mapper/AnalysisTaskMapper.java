package com.example.commentanalysis.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.commentanalysis.entity.AnalysisTask;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDateTime;

/**
 * 分析任务表 Mapper，继承 {@link BaseMapper} 获得通用 CRUD 能力。
 *
 * <p>逻辑删除由 MyBatis-Plus 依据实体 {@code @TableLogic} 标记自动追加条件。</p>
 *
 * @author 闫宇星
 */
public interface AnalysisTaskMapper extends BaseMapper<AnalysisTask> {

    /**
     * 原子累加任务进度与异常数。
     *
     * <p>重试续跑时只处理剩余评论，若直接覆盖 processed_count 会把历史进度抹掉；
     * 此处用数据库自增语义累加，保证「失败重试」后进度仍能收敛到 100%。</p>
     *
     * @param taskId    任务编号
     * @param processed 本批新增处理条数
     * @param errors    本批新增异常条数
     * @param updateTime 更新时间
     * @return 受影响行数
     */
    @Update("UPDATE analysis_task SET processed_count = processed_count + #{processed}, "
            + "error_count = error_count + #{errors}, update_time = #{updateTime} "
            + "WHERE task_id = #{taskId} AND is_deleted = 0")
    int incrementProgress(@Param("taskId") Long taskId,
                          @Param("processed") int processed,
                          @Param("errors") int errors,
                          @Param("updateTime") LocalDateTime updateTime);

    /**
     * 清空任务的失败原因。
     *
     * <p>重试开始或任务成功时调用。MyBatis-Plus 的 {@code updateById} 默认忽略 null 字段，
     * 无法把列更新为 NULL，因此这里使用显式 UPDATE。</p>
     *
     * @param taskId     任务编号
     * @param updateTime 更新时间
     * @return 受影响行数
     */
    @Update("UPDATE analysis_task SET error_message = NULL, update_time = #{updateTime} "
            + "WHERE task_id = #{taskId} AND is_deleted = 0")
    int clearErrorMessage(@Param("taskId") Long taskId,
                          @Param("updateTime") LocalDateTime updateTime);

    /**
     * 物理删除任务（解析失败时清理半成品数据）。
     *
     * <p>解析改为分批提交后不再有整体事务回滚，失败时需要显式删除任务；
     * 子表通过外键 {@code ON DELETE CASCADE} 一并清理。</p>
     *
     * @param taskId 任务编号
     * @return 受影响行数
     */
    @Delete("DELETE FROM analysis_task WHERE task_id = #{taskId}")
    int deletePhysically(@Param("taskId") Long taskId);
}
