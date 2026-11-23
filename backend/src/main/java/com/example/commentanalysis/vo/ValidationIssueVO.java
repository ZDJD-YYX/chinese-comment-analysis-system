package com.example.commentanalysis.vo;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;

/**
 * 导入校验问题项。
 *
 * <p>每条记录描述一类检测结果（如编码转换、不可见字符），
 * 并标明是否已自动修复，供前端展示。</p>
 *
 * @author 闫宇星
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ValidationIssueVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 问题类型，如「编码异常」「不可见字符」「格式不符」 */
    private String type;

    /** 处理结果：FIXED 已自动修复 / WARNING 需关注 / ERROR 无法修复 */
    private String level;

    /** 涉及数量（字符数、行数等），无数量概念时为 0 */
    private int count;

    /** 详细说明 */
    private String detail;
}