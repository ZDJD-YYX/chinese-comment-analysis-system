package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.util.List;
import java.util.Map;

/**
 * 文件上传解析报告。
 *
 * <p>与《详细设计说明书》API-04 响应结构对齐，上传解析成功后即时返回，
 * 同时给出本次解析所创建的分析任务编号。字段覆盖需求 FR-BIZ-10
 * 「总条数、有效条数、过滤条数与失败原因分布」。</p>
 *
 * @author 闫宇星
 */
@Data
public class ParseReportVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 本次解析创建的分析任务编号 */
    private Long taskId;

    /** 任务名称（默认取文件名去扩展名） */
    private String taskName;

    /** 源文件名称 */
    private String fileName;

    /** 源文件大小（字节） */
    private Long fileSize;

    /** 源文件扫描到的数据行数（不含表头） */
    private Integer totalCount;

    /** 有效评论条数（已入库） */
    private Integer validCount;

    /** 被过滤条数（空白行、重复行等） */
    private Integer filteredCount;

    /** 过滤原因分布：原因 → 条数（失败原因分布，对应 FR-BIZ-10） */
    private Map<String, Integer> filterReasons;

    /** 识别到的评论列序号（从 0 开始） */
    private Integer commentColumn;

    /** 是否需要人工指定评论列（自动识别失败时为 true） */
    private Boolean needsColumnSelection;

    /** 重新导入用的文件令牌，needsColumnSelection 为 true 时才有值 */
    private String pendingToken;

    /** 评论列候选，needsColumnSelection 为 true 时返回 */
    private List<ColumnCandidateVO> candidateColumns;

    /** 识别到的时间列序号（从 0 开始），未识别到时为空 */
    private Integer timeColumn;

    /** 导入校验与自动修复结果 */
    private ImportValidationVO validation;
}
