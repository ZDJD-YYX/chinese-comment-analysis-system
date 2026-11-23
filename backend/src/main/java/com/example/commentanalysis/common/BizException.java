package com.example.commentanalysis.common;

import lombok.Getter;

/**
 * 业务异常。
 *
 * <p>服务层在业务规则不满足时主动抛出，携带明确的 {@link ResultCode} 错误码，
 * 由全局异常处理器统一转换为 {@link Result} 返回，控制器层无需 try-catch。</p>
 *
 * @author 闫宇星
 */
@Getter
public class BizException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    /** 业务错误码 */
    private final Integer code;

    /**
     * 使用预定义错误码构造业务异常。
     *
     * @param resultCode 错误码枚举
     */
    public BizException(ResultCode resultCode) {
        super(resultCode.getMessage());
        this.code = resultCode.getCode();
    }

    /**
     * 使用预定义错误码 + 自定义消息构造业务异常。
     *
     * @param resultCode 错误码枚举
     * @param message    自定义提示信息
     */
    public BizException(ResultCode resultCode, String message) {
        super(message);
        this.code = resultCode.getCode();
    }

    /**
     * 使用自定义错误码与消息构造业务异常。
     *
     * @param code    错误码
     * @param message 提示信息
     */
    public BizException(Integer code, String message) {
        super(message);
        this.code = code;
    }
}
