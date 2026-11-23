package com.example.commentanalysis.service;

import com.example.commentanalysis.common.PageVO;
import com.example.commentanalysis.vo.ConfidenceDistributionVO;
import com.example.commentanalysis.vo.KeywordVO;
import com.example.commentanalysis.vo.ResultVO;
import com.example.commentanalysis.vo.ReviewQualityVO;
import com.example.commentanalysis.vo.SentimentStatisticsVO;
import com.example.commentanalysis.vo.SentimentTrendVO;

import javax.servlet.http.HttpServletResponse;
import java.math.BigDecimal;
import java.util.List;

/**
 * 分析结果业务服务接口。
 *
 * <p>提供结果明细分页、任务情感分布统计与结果 Excel 导出能力。</p>
 *
 * @author 闫宇星
 */
public interface ResultService {

    /**
     * 分页查询分析结果明细。
     *
     * <p>支持按任务、情感标签、置信度区间与关键词组合筛选（FR-BIZ-19 / FR-BIZ-20），
     * 默认按评论编号升序返回，并回查评论原文一并返回。</p>
     *
     * @param pageNum       页码，从 1 开始，非法值按 1 处理
     * @param pageSize      每页条数，非法值按 10 处理，上限 200
     * @param taskId        任务编号，可为空表示不限任务
     * @param sentiment     情感标签，可为空
     * @param keyword       关键词，可为空
     * @param minConfidence 置信度区间下限，可为空
     * @param maxConfidence 置信度区间上限，可为空
     * @param needReview    复核状态：1 只看待复核 / 0 只看已复核，为空表示不限
     * @param sortBy        排序字段：commentId（默认）/ confidence
     * @param sortOrder     排序方向：asc（默认）/ desc
     * @return 结果明细分页数据
     */
    PageVO<ResultVO> pageResults(Integer pageNum, Integer pageSize, Long taskId, String sentiment,
                                 String keyword, BigDecimal minConfidence, BigDecimal maxConfidence,
                                 Integer needReview, Integer reviewed, String sortBy, String sortOrder);

    /**
     * 提交人工复核结论，或撤销单条结果的复核标记。
     *
     * <p>复核结论与模型原判定不一致时覆盖最终情感标签，并同步刷新所属任务的
     * 情感条数与待复核条数快照，避免概览卡与实际明细不一致。</p>
     *
     * @param resultId  结果编号
     * @param reviewed  true 表示已复核，false 表示撤销复核
     * @param sentiment 人工复核后的情感结论，可为空表示沿用模型原判定
     */
    void markReviewed(Long resultId, boolean reviewed, String sentiment);

    /**
     * 批量提交人工复核结论。
     *
     * <p>一次为多条结果写入相同的复核状态与结论，并重算所属任务的统计快照。</p>
     *
     * @param resultIds 结果编号列表，非空且不超过 1000 条
     * @param reviewed  true 表示标记为已复核，false 表示撤销复核
     * @param sentiment 人工复核后的情感结论，可为空表示沿用各自模型原判定
     * @return 实际处理的条数
     */
    int batchReview(List<Long> resultIds, boolean reviewed, String sentiment);

    /**
     * 统计指定任务的情感分布。
     *
     * @param taskId 任务编号
     * @return 情感分布统计（含各情感条数、占比、待复核条数与平均置信度）
     */
    SentimentStatisticsVO statistics(Long taskId);

    /**
     * 查询任务级热点关键词（词云数据源）。
     *
     * @param taskId    任务编号
     * @param sentiment 情感维度：ALL / POSITIVE / NEGATIVE / NEUTRAL，为空按 ALL
     * @param topN      返回条数，1～50，为空取配置值
     * @return 按 TF-IDF 权重降序的关键词列表
     */
    List<KeywordVO> keywords(Long taskId, String sentiment, Integer topN);

    /**
     * 查询任务的情感趋势（FR-BIZ-18）。
     *
     * <p>按评论原始时间聚合三类情感条数；源文件没有时间列时返回空数据点，
     * 前端据此隐藏趋势图。</p>
     *
     * @param taskId      任务编号
     * @param granularity 聚合粒度：auto（默认，按时间跨度自动选择）/ hour / day
     * @return 情感趋势数据
     */
    SentimentTrendVO trend(Long taskId, String granularity);

    /**
     * 查询任务置信度区间分布（直方图数据源）。
     *
     * @param taskId 任务编号
     * @return 置信度分布，含低置信度样本占比
     */
    ConfidenceDistributionVO confidenceDistribution(Long taskId);

    /**
     * 查询任务的人工复核质量。
     *
     * <p>输出一致率、改判规模、改判方向分布与模型/人工混淆矩阵；
     * 只统计已复核样本，未复核样本不计入分母。</p>
     *
     * @param taskId 任务编号
     * @return 复核质量数据
     */
    ReviewQualityVO reviewQuality(Long taskId);

    /**
     * 生成任务分析报告（单文件 HTML，内联样式与图形，可直接打印或转 PDF）。
     *
     * @param taskId   任务编号
     * @param response HTTP 响应，用于输出 HTML 字节流
     */
    void exportReport(Long taskId, HttpServletResponse response);

    /**
     * 导出指定任务的分析结果 Excel。
     *
     * <p>导出前会校验任务存在与数据量上限；校验通过后才写入响应头并分批流式输出，
     * 避免大数据量导出时内存溢出。输出包含「分析结果」明细工作表与「统计摘要」工作表
     * （情感占比与热点词摘要，对应 FR-BIZ-26）。</p>
     *
     * @param taskId    任务编号
     * @param scope     导出范围：all 全量 / current 当前筛选（默认 all，对应 FR-BIZ-27）
     * @param sentiment 当前筛选的情感标签，scope=current 时生效
     * @param keyword   当前筛选的关键词，scope=current 时生效
     * @param needReview 当前筛选的复核状态，scope=current 时生效
     * @param format    导出格式：xlsx（默认）/ csv / json
     * @param response  HTTP 响应，用于输出文件字节流
     */
    void export(Long taskId, String scope, String sentiment, String keyword, Integer needReview,
                Integer reviewed, BigDecimal minConfidence, BigDecimal maxConfidence,
                String format, HttpServletResponse response);
}
