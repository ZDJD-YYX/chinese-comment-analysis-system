package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;

/**
 * 热点关键词视图。
 *
 * <p>用于词云与热点词排名展示，对应《详细设计说明书》API-11 响应字段。</p>
 *
 * @author 闫宇星
 */
@Data
public class KeywordVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 关键词 */
    private String word;

    /** TF-IDF 权重 */
    private BigDecimal weight;

    /** 词频 */
    private Integer wordCount;

    /** 所属情感维度：ALL / POSITIVE / NEGATIVE / NEUTRAL */
    private String sentiment;
}
