package com.example.commentanalysis.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 分析任务表实体，对应数据表 {@code analysis_task}。
 *
 * <p>系统核心表，一次"上传文件 + 全量分析"对应一条任务记录，同时承载上传文件元信息、
 * 执行进度与状态。{@code is_deleted} 为逻辑删除标记，由 MyBatis-Plus 自动处理。</p>
 *
 * @author 闫宇星
 */
@Data
@TableName("analysis_task")
public class AnalysisTask implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 任务编号，主键，数据库自增 */
    @TableId(value = "task_id", type = IdType.AUTO)
    private Long taskId;

    /** 任务名称，默认取文件名（去扩展名），允许用户修改 */
    @TableField("task_name")
    private String taskName;

    /** 上传的源文件名称，含扩展名 */
    @TableField("file_name")
    private String fileName;

    /** 源文件大小（字节） */
    @TableField("file_size")
    private Long fileSize;

    /** 创建人，关联 sys_user.user_id */
    @TableField("user_id")
    private Long userId;

    /** 本次任务使用的模型版本号，保证结果可追溯 */
    @TableField("model_version")
    private String modelVersion;

    /** 解析入库的评论总数 */
    @TableField("total_count")
    private Integer totalCount;

    /** 已完成推理的条数，进度 = processed_count / total_count */
    @TableField("processed_count")
    private Integer processedCount;

    /** 推理异常并跳过的样本数 */
    @TableField("error_count")
    private Integer errorCount;

    /** 创建任务时的批量大小快照，保证重试行为一致 */
    @TableField("batch_size")
    private Integer batchSize;

    /** 任务状态：PENDING / RUNNING / SUCCESS / FAILED / CANCELED */
    @TableField("status")
    private String status;

    /** 任务由待执行转为执行中的时间 */
    @TableField("start_time")
    private LocalDateTime startTime;

    /** 任务结束时间（成功、失败、终止均记录） */
    @TableField("finish_time")
    private LocalDateTime finishTime;

    /** 最近一次执行失败的原因，执行成功后清空 */
    @TableField("error_message")
    private String errorMessage;

    /** 任务创建时间 */
    @TableField("create_time")
    private LocalDateTime createTime;

    /** 最近更新时间 */
    @TableField("update_time")
    private LocalDateTime updateTime;

    /** 逻辑删除标记：0 未删除 / 1 已删除 */
    @TableLogic
    @TableField("is_deleted")
    private Integer isDeleted;
}
