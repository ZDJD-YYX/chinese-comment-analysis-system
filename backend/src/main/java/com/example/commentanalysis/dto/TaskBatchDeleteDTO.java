package com.example.commentanalysis.dto;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 批量删除任务请求参数。
 *
 * @author 闫宇星
 */
@Data
public class TaskBatchDeleteDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 任务编号列表 */
    private List<Long> taskIds;
}
