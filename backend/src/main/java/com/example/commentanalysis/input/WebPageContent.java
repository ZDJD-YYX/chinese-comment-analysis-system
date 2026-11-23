package com.example.commentanalysis.input;

import lombok.Data;

import java.io.Serializable;

/**
 * 网页抓取与正文提取结果。
 *
 * @author 闫宇星
 */
@Data
public class WebPageContent implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 页面标题，缺失时回退为域名 */
    private String title;

    /** 最终访问地址（跟随重定向后） */
    private String url;

    /** 已过滤导航、广告等无关内容后的正文 */
    private String text;

    /** 正文容器内的段落数，用于前端预览判断抽取质量 */
    private int paragraphCount;

    /** 正文容器的链接密度（0～1），过高说明可能抽到了导航或列表 */
    private double linkDensity;
}
