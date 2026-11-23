package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 登录/注册成功后的返回视图。
 *
 * <p>不包含密码哈希与盐值，避免敏感信息外泄。</p>
 *
 * @author 闫宇星
 */
@Data
public class LoginVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 用户编号 */
    private Long userId;

    /** 登录账号 */
    private String username;

    /** 最近一次登录成功时间 */
    private LocalDateTime lastLoginTime;

    /** 账号创建时间 */
    private LocalDateTime createTime;
}
