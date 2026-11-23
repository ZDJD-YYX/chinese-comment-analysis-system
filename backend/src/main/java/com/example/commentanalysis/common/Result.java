package com.example.commentanalysis.common;

import lombok.Data;

import java.io.Serializable;

/**
 * 统一响应结果封装类。
 *
 * <p>所有 REST 接口均返回该结构，三段式固定为 {@code code / message / data}，
 * 前端据此统一处理成功与失败分支。约定 {@code code = 0} 表示成功，非 0 表示失败。</p>
 *
 * @param <T> 业务数据体类型
 * @author 闫宇星
 */
@Data
public class Result<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 业务状态码，0 表示成功 */
    private Integer code;

    /** 提示信息，失败时为可直接展示给用户的中文文案 */
    private String message;

    /** 业务数据体，失败时为 null */
    private T data;

    private Result(Integer code, String message, T data) {
        this.code = code;
        this.message = message;
        this.data = data;
    }

    /**
     * 成功响应（无数据）。
     */
    public static <T> Result<T> success() {
        return new Result<>(ResultCode.SUCCESS.getCode(), ResultCode.SUCCESS.getMessage(), null);
    }

    /**
     * 成功响应（携带数据）。
     *
     * @param data 业务数据体
     */
    public static <T> Result<T> success(T data) {
        return new Result<>(ResultCode.SUCCESS.getCode(), ResultCode.SUCCESS.getMessage(), data);
    }

    /**
     * 成功响应（自定义提示信息 + 数据）。
     *
     * @param message 提示信息
     * @param data    业务数据体
     */
    public static <T> Result<T> success(String message, T data) {
        return new Result<>(ResultCode.SUCCESS.getCode(), message, data);
    }

    /**
     * 失败响应（使用预定义错误码）。
     *
     * @param resultCode 错误码枚举
     */
    public static <T> Result<T> fail(ResultCode resultCode) {
        return new Result<>(resultCode.getCode(), resultCode.getMessage(), null);
    }

    /**
     * 失败响应（自定义错误码与提示信息）。
     *
     * @param code    错误码
     * @param message 提示信息
     */
    public static <T> Result<T> fail(Integer code, String message) {
        return new Result<>(code, message, null);
    }
}
