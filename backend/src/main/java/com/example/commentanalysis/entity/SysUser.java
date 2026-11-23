package com.example.commentanalysis.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 用户表实体，对应数据表 {@code sys_user}。
 *
 * <p>单用户模式下仅保留一条管理员记录，密码以"随机盐 + 哈希"方式存储，禁止明文。</p>
 *
 * @author 闫宇星
 */
@Data
@TableName("sys_user")
public class SysUser implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 用户编号，主键，数据库自增 */
    @TableId(value = "user_id", type = IdType.AUTO)
    private Long userId;

    /** 登录账号，全局唯一 */
    @TableField("username")
    private String username;

    /** 加盐哈希后的密码 */
    @TableField("password_hash")
    private String passwordHash;

    /** 密码盐值 */
    @TableField("salt")
    private String salt;

    /** 账号状态：1 启用 / 0 停用 */
    @TableField("status")
    private Integer status;

    /** 最近一次登录成功时间 */
    @TableField("last_login_time")
    private LocalDateTime lastLoginTime;

    /** 账号创建时间 */
    @TableField("create_time")
    private LocalDateTime createTime;

    /** 最近更新时间 */
    @TableField("update_time")
    private LocalDateTime updateTime;
}
