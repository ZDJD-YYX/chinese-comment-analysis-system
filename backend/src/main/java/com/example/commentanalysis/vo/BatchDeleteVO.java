package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;

/**
 * 批量删除任务结果。
 *
 * <p>执行中的任务不允许删除，返回成功条数与跳过条数，便于前端给出准确提示。</p>
 *
 * @author 闫宇星
 */
@Data
public class BatchDeleteVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 实际删除的任务数 */
    private int deleted;

    /** 因执行中或其他原因跳过的任务数 */
    private int skipped;
}
