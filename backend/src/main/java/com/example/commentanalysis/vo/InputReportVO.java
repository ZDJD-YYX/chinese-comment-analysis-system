package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;

/**
 * 智能输入接收回执。
 *
 * <p>返回识别出的输入类型、提取到的字符数与评论条数，以及本次创建的分析任务编号，
 * 前端据此提示用户内容已接收并进入分析流程。</p>
 *
 * @author 闫宇星
 */
@Data
public class InputReportVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 本次创建的分析任务编号 */
    private Long taskId;

    /** 任务名称 */
    private String taskName;

    /** 输入类型：WEB_PAGE（网页链接）/ PLAIN_TEXT（纯文本） */
    private String sourceType;

    /** 输入类型中文名 */
    private String sourceTypeLabel;

    /** 网页标题；纯文本输入时为空 */
    private String sourceTitle;

    /** 网页最终地址；纯文本输入时为空 */
    private String sourceUrl;

    /** 接收到的正文字符数 */
    private Integer inputChars;

    /** 切分后的评论条数（即本次任务分析条数） */
    private Integer commentCount;

    /** 内容接收与解析耗时（毫秒） */
    private Long elapsedMs;

    /** 可直接展示的接收结果提示 */
    private String message;
}
