package com.example.commentanalysis.dto;

import lombok.Data;

import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;
import java.io.Serializable;

/**
 * 注册请求参数。
 *
 * <p>系统为单用户模式，注册即创建管理员账号，不涉及角色与权限。</p>
 *
 * @author 闫宇星
 */
@Data
public class RegisterDTO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 登录账号 */
    @NotBlank(message = "账号不能为空")
    @Size(max = 50, message = "账号长度不得超过 50 位")
    private String username;

    /** 登录密码 */
    @NotBlank(message = "密码不能为空")
    @Size(min = 6, max = 64, message = "密码长度需为 6～64 位")
    private String password;
}
