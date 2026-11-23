package com.example.commentanalysis.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 系统设置修改参数。
 *
 * <p>仅开放两个安全可调项；批量大小、词条上限等影响任务队列的参数不在线修改。</p>
 *
 * @author 闫宇星
 */
@Data
public class SettingsUpdateDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 低置信度人工复核阈值，取值 0.50～0.99 */
    private Double reviewThreshold;

    /** 写入单条评论的关键词数量上限，取值 1～10 */
    private Integer keywordsPerComment;
}