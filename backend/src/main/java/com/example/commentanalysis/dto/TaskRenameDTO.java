package com.example.commentanalysis.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 任务重命名请求参数。
 *
 * @author 闫宇星
 */
@Data
public class TaskRenameDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 新的任务名称 */
    private String taskName;
}
