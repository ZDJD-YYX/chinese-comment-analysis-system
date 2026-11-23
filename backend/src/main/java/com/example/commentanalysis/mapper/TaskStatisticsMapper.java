package com.example.commentanalysis.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.commentanalysis.entity.TaskStatistics;

/**
 * 任务统计表 Mapper，继承 {@link BaseMapper} 获得通用 CRUD 能力。
 *
 * <p>统计行由推理任务收尾阶段一次性写入；写入前按 {@code task_id} 清理旧行，
 * 保证与唯一索引 {@code uk_task} 不冲突。</p>
 *
 * @author 闫宇星
 */
public interface TaskStatisticsMapper extends BaseMapper<TaskStatistics> {
}
