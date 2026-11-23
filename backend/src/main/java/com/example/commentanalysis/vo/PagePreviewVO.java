package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;

/**
 * 网页正文抽取预览。
 *
 * <p>抓取网页后不直接建任务，先把抽到的标题、篇幅、段落数与正文开头返回给用户确认，
 * 避免"抽错内容却默默分析完"（对应正文抽取确认流程）。</p>
 *
 * @author 闫宇星
 */
@Data
public class PagePreviewVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 确认令牌，确认分析时回传 */
    private String token;

    /** 网页最终地址（跟随重定向后） */
    private String url;

    /** 网页标题 */
    private String title;

    /** 抽取到的正文字符数 */
    private Integer inputChars;

    /** 正文段落数 */
    private Integer paragraphCount;

    /** 预计切分出的评论条数 */
    private Integer commentCount;

    /** 链接密度（0～1），越高越可能是导航或列表 */
    private Double linkDensity;

    /** 是否建议用户重点确认（抽取质量可疑） */
    private Boolean suspect;

    /** 可疑原因提示，正常时为空 */
    private String warning;

    /** 正文开头片段，供用户快速判断 */
    private String excerpt;
}
