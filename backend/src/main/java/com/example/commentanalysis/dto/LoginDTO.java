package com.example.commentanalysis.dto;

import lombok.Data;

import javax.validation.constraints.NotBlank;
import java.io.Serializable;

/**
 * 登录请求参数。
 *
 * @author 闫宇星
 */
@Data
public class LoginDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 登录账号 */
    @NotBlank(message = "账号不能为空")
    private String username;

    /** 登录密码（明文，服务端加盐哈希后比对） */
    @NotBlank(message = "密码不能为空")
    private String password;
}
