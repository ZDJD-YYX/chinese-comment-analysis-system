package com.example.commentanalysis.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

/**
 * 全局异常处理器。
 *
 * <p>捕获各类异常并统一转换为 {@link Result} 返回，控制器层不写 try-catch。
 * 面向用户的消息与内部异常信息分离：{@code message} 只含可展示的中文文案，
 * 堆栈与内部细节仅写日志，避免泄露实现细节。</p>
 *
 * <p>HTTP 状态码与业务语义对齐：未登录 401、参数错误 400、上传超限 413、
 * 唯一键冲突 409、系统异常 500；业务错误（如任务状态不允许）仍返回 200，
 * 由响应体 {@code code} 表达。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 业务异常：使用异常携带的错误码与消息返回。
     *
     * @param e 业务异常
     * @return 统一响应结果
     */
    @ExceptionHandler(BizException.class)
    public ResponseEntity<Result<Void>> handleBiz(BizException e) {
        log.warn("业务异常：code={}, message={}", e.getCode(), e.getMessage());
        HttpStatus status = isUnauthorized(e.getCode())
                ? HttpStatus.UNAUTHORIZED : HttpStatus.OK;
        return ResponseEntity.status(status).body(Result.fail(e.getCode(), e.getMessage()));
    }

    /**
     * 参数校验失败：取首个字段错误信息返回。
     *
     * @param e 参数校验异常
     * @return 统一响应结果
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Result<Void>> handleValid(MethodArgumentNotValidException e) {
        String message = firstErrorMessage(e.getBindingResult().getFieldError());
        log.warn("参数校验失败：{}", message);
        return ResponseEntity.badRequest()
                .body(Result.fail(ResultCode.BAD_REQUEST.getCode(), message));
    }

    /**
     * 表单参数绑定校验失败。
     *
     * @param e 参数绑定异常
     * @return 统一响应结果
     */
    @ExceptionHandler(BindException.class)
    public ResponseEntity<Result<Void>> handleBind(BindException e) {
        String message = firstErrorMessage(e.getBindingResult().getFieldError());
        log.warn("参数绑定失败：{}", message);
        return ResponseEntity.badRequest()
                .body(Result.fail(ResultCode.BAD_REQUEST.getCode(), message));
    }

    /**
     * 请求体不是合法 JSON。
     *
     * @param e 请求体解析异常
     * @return 统一响应结果
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Result<Void>> handleUnreadable(HttpMessageNotReadableException e) {
        log.warn("请求体解析失败：{}", e.getMessage());
        return ResponseEntity.badRequest()
                .body(Result.fail(ResultCode.BAD_REQUEST.getCode(), "请求体格式错误"));
    }

    /**
     * 上传文件超出大小限制。
     *
     * @param e 上传超限异常
     * @return 统一响应结果
     */
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<Result<Void>> handleUpload(MaxUploadSizeExceededException e) {
        log.warn("上传文件超出大小限制：{}", e.getMessage());
        return ResponseEntity.status(HttpStatus.PAYLOAD_TOO_LARGE)
                .body(Result.fail(ResultCode.FILE_TOO_LARGE));
    }

    /**
     * 唯一索引冲突（如 uk_task_comment 幂等去重触发）。
     *
     * @param e 唯一键冲突异常
     * @return 统一响应结果
     */
    @ExceptionHandler(DuplicateKeyException.class)
    public ResponseEntity<Result<Void>> handleDuplicate(DuplicateKeyException e) {
        log.warn("唯一索引冲突，数据重复已跳过：{}", e.getMessage());
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Result.fail(ResultCode.ANALYSIS_FAILED.getCode(), "数据重复，已跳过"));
    }

    /**
     * 数据库访问异常。
     *
     * @param e 数据访问异常
     * @return 统一响应结果
     */
    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<Result<Void>> handleDb(DataAccessException e) {
        log.error("数据库访问异常", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Result.fail(ResultCode.SYSTEM_ERROR));
    }

    /**
     * 未预期异常兜底处理。
     *
     * @param e 异常
     * @return 统一响应结果
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Void>> handleUncaught(Exception e) {
        log.error("系统未预期异常", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Result.fail(ResultCode.SYSTEM_ERROR));
    }

    /**
     * 是否为登录态失效错误码。
     *
     * @param code 业务错误码
     * @return 登录态失效返回 true
     */
    private boolean isUnauthorized(Integer code) {
        return ResultCode.UNAUTHORIZED.getCode().equals(code)
                || ResultCode.SESSION_EXPIRED.getCode().equals(code);
    }

    /**
     * 提取首个字段校验错误信息，缺省时返回通用参数错误提示。
     *
     * @param fieldError 字段校验错误
     * @return 可展示的中文提示
     */
    private String firstErrorMessage(FieldError fieldError) {
        if (fieldError == null) {
            return ResultCode.BAD_REQUEST.getMessage();
        }
        return fieldError.getDefaultMessage();
    }
}
