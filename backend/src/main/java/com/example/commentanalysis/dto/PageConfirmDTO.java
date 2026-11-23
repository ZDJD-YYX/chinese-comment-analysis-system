package com.example.commentanalysis.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 网页正文确认请求参数。
 *
 * @author 闫宇星
 */
@Data
public class PageConfirmDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 预览接口返回的确认令牌 */
    private String token;
}
