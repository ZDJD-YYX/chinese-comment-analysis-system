package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 任务进度视图。
 *
 * <p>对应《详细设计说明书》API-07 响应结构，供前端进度条轮询使用。</p>
 *
 * @author 闫宇星
 */
@Data
public class ProgressVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 任务编号 */
    private Long taskId;

    /** 任务状态：PENDING / RUNNING / SUCCESS / FAILED / CANCELED */
    private String status;

    /** 评论总数 */
    private Integer totalCount;

    /** 已处理条数 */
    private Integer processedCount;

    /** 进度百分比（0～100），由 processedCount / totalCount 计算，不入库 */
    private Integer percent;

    /** 开始时间 */
    private LocalDateTime startTime;

    /** 结束时间 */
    private LocalDateTime finishTime;
}
