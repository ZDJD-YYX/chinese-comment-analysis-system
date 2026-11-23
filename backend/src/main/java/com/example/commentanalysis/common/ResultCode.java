package com.example.commentanalysis.common;

/**
 * 业务错误码定义。
 *
 * <p>取值与《详细设计说明书》8.2 节错误码表严格一致，便于前后端约定统一。</p>
 *
 * @author 闫宇星
 */
public enum ResultCode {

    /** 成功 */
    SUCCESS(0, "成功"),

    /** 请求参数错误 */
    BAD_REQUEST(400, "请求参数错误"),
    /** 未登录或会话过期 */
    UNAUTHORIZED(401, "登录已过期，请重新登录"),
    /** 资源不存在 */
    NOT_FOUND(404, "请求的资源不存在"),
    /** 系统内部错误 */
    SYSTEM_ERROR(500, "系统繁忙，请稍后重试"),

    /** 账号或密码错误 */
    LOGIN_FAILED(1001, "账号或密码错误"),
    /** 会话已过期 */
    SESSION_EXPIRED(1002, "登录已过期，请重新登录"),
    /** 原密码不正确 */
    OLD_PASSWORD_ERROR(1003, "原密码不正确"),
    /** 新密码不符合规则 */
    NEW_PASSWORD_INVALID(1004, "密码长度不得少于 6 位"),

    /** 文件格式不支持 */
    FILE_TYPE_UNSUPPORTED(2001, "仅支持 .xlsx/.xls/.csv/.txt/.tsv/.json 格式文件"),
    /** 文件超出大小限制 */
    FILE_TOO_LARGE(2002, "文件大小超过 50 MB 限制，请拆分后上传"),
    /** 表头缺失或为空 */
    HEADER_MISSING(2003, "文件缺少有效表头，请检查文件格式"),
    /** 未解析到有效评论 */
    NO_VALID_COMMENT(2004, "未解析到有效评论数据"),
    /** 文件编码无法识别 */
    ENCODING_UNRECOGNIZED(2005, "文件编码无法识别，请另存为 UTF-8 后重试"),
    /** 评论列识别失败 */
    COMMENT_COLUMN_UNRECOGNIZED(2006, "未识别到评论列，请手工指定"),
    /** 导入校验未通过 */
    IMPORT_VALIDATION_FAILED(2007, "文件校验未通过，请按提示处理后重试"),

    /** 网页链接格式不正确 */
    INPUT_URL_INVALID(2008, "网页链接格式不正确，请检查后重试"),
    /** 网页链接指向内网或受限地址 */
    INPUT_URL_BLOCKED(2009, "该链接指向内网或受限地址，无法抓取"),
    /** 网页抓取失败 */
    INPUT_FETCH_FAILED(2010, "网页抓取失败，请确认链接可公开访问"),
    /** 网页未提取到正文 */
    INPUT_CONTENT_EMPTY(2011, "网页未提取到可分析的正文内容"),
    /** 输入内容过大 */
    INPUT_CONTENT_TOO_LARGE(2012, "输入内容过大，请分段提交"),

    /** 智能模型不可用 */
    MODEL_UNAVAILABLE(3001, "智能模型不可用，请联系维护人员检查模型文件"),
    /** 任务不存在 */
    TASK_NOT_FOUND(3002, "任务不存在或已被删除"),
    /** 任务状态不允许该操作 */
    TASK_STATUS_ILLEGAL(3003, "任务正在执行中，请先终止任务后再操作"),
    /** 分析执行失败 */
    ANALYSIS_FAILED(3004, "分析失败，请查看日志或重试"),
    /** 结果数据不完整 */
    RESULT_INCOMPLETE(3005, "该任务结果数据不完整，仅可查看任务信息"),
    /** 任务状态不允许重新分析 */
    TASK_NOT_RETRYABLE(3006, "仅待执行或失败的任务可重新分析"),
    /** 任务状态不允许终止 */
    TASK_NOT_CANCELABLE(3007, "仅执行中的任务可终止"),

    /** 导出失败 */
    EXPORT_FAILED(4001, "导出失败，请联系维护人员"),
    /** 导出数据量过大 */
    EXPORT_TOO_LARGE(4002, "数据量较大，请缩小导出范围后重试");

    private final Integer code;

    private final String message;

    ResultCode(Integer code, String message) {
        this.code = code;
        this.message = message;
    }

    public Integer getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
