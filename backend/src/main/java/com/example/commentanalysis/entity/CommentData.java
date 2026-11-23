package com.example.commentanalysis.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 评论原始数据表实体，对应数据表 {@code comment_data}。
 *
 * <p>存放文件解析并清洗后的评论原文，是推理任务的输入源。</p>
 *
 * @author 闫宇星
 */
@Data
@TableName("comment_data")
public class CommentData implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 评论编号，主键，数据库自增 */
    @TableId(value = "comment_id", type = IdType.AUTO)
    private Long commentId;

    /** 所属任务编号，关联 analysis_task.task_id */
    @TableField("task_id")
    private Long taskId;

    /** 评论原文（清洗后，1～512 字符） */
    @TableField("content")
    private String content;

    /** 该评论在源文件中的原始行号，用于问题定位 */
    @TableField("row_no")
    private Integer rowNo;

    /**
     * 评论原始时间。
     *
     * <p>源文件存在时间/日期列时解析写入，用于按时间聚合情感趋势；
     * 无此列时为 null，对应需求 FR-BIZ-18「数据无时间字段时不展示趋势图」。</p>
     */
    @TableField("comment_time")
    private LocalDateTime commentTime;

    /** 入库时间 */
    @TableField("create_time")
    private LocalDateTime createTime;
}
