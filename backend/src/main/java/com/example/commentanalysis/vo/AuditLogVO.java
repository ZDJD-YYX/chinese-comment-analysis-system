package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;

/**
 * 操作记录视图。
 *
 * <p>时间以已格式化的字符串返回，前端直接展示，避免时区与序列化格式差异。</p>
 *
 * @author 闫宇星
 */
@Data
public class AuditLogVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 操作时间（yyyy-MM-dd HH:mm:ss） */
    private String time;

    /** 操作账号 */
    private String username;

    /** 操作类型，如 登录 / 退出登录 / 修改密码 / 删除任务 */
    private String action;

    /** 操作详情 */
    private String detail;
}