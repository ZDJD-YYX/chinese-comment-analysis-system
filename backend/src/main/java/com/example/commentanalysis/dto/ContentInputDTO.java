package com.example.commentanalysis.dto;

import lombok.Data;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;
import java.io.Serializable;

/**
 * 智能输入请求体。
 *
 * <p>同一字段承载纯文本与网页链接，由后端自动识别，前端无需切换模式。</p>
 *
 * @author 闫宇星
 */
@Data
public class ContentInputDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 用户粘贴的评论文本或网页链接 */
    @NotBlank(message = "请输入要分析的评论内容或网页链接")
    @Size(max = 500000, message = "输入内容过大，请分段提交")
    private String content;
}
