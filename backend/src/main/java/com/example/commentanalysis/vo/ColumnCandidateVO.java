package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;

/**
 * 评论列候选视图。
 *
 * <p>当自动识别评论列失败时返回，供用户手工指定（对应需求 FR-BIZ-06
 * 「识别失败时提供候选列供人工指定」）。</p>
 *
 * @author 闫宇星
 */
@Data
public class ColumnCandidateVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 列序号，从 0 开始 */
    private Integer index;

    /** 表头名称，无表头时为空 */
    private String header;

    /** 该列的一条样例内容 */
    private String sample;

    /** 样例内容长度，用于辅助判断哪一列是评论正文 */
    private Integer sampleLength;
}
