package com.example.commentanalysis.dto;

import lombok.Data;

import javax.validation.constraints.NotBlank;
import java.io.Serializable;

/**
 * 修改密码请求参数。
 *
 * <p>原密码与新密码均为必填；新密码长度规则（6～64 位）在业务层校验，
 * 以复用设计文档错误码表 1004（密码长度不得少于 6 位）。</p>
 *
 * @author 闫宇星
 */
@Data
public class ChangePasswordDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 原密码（明文，服务端比对后才会更新） */
    @NotBlank(message = "原密码不能为空")
    private String oldPassword;

    /** 新密码（明文，更新前做长度校验） */
    @NotBlank(message = "新密码不能为空")
    private String newPassword;
}