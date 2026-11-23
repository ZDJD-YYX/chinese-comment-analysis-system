package com.example.commentanalysis.ai;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * 关键词及 TF-IDF 权重。
 *
 * @author 闫宇星
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class KeywordResult implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 关键词 */
    private String word;

    /** TF-IDF 权重（保留四位小数） */
    private double weight;

    /** 该词在语料中的累计词频 */
    private int wordCount;
}
