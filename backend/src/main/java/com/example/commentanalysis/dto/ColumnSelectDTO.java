package com.example.commentanalysis.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 评论列手工指定请求参数。
 *
 * <p>自动识别失败后，前端携带待处理文件的令牌与用户选择的列序号重新导入，
 * 对应需求 FR-BIZ-06。</p>
 *
 * @author 闫宇星
 */
@Data
public class ColumnSelectDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 待处理文件令牌（上传接口返回） */
    private String token;

    /** 用户选择的评论列序号，从 0 开始 */
    private Integer column;
}
