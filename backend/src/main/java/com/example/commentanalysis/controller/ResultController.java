package com.example.commentanalysis.controller;

import com.example.commentanalysis.common.PageVO;
import com.example.commentanalysis.common.Result;
import com.example.commentanalysis.config.AuthInterceptor;
import com.example.commentanalysis.dto.BatchReviewDTO;
import com.example.commentanalysis.dto.ReviewDTO;
import com.example.commentanalysis.service.AuditLogService;
import com.example.commentanalysis.service.ResultService;
import com.example.commentanalysis.vo.ConfidenceDistributionVO;
import com.example.commentanalysis.vo.KeywordVO;
import com.example.commentanalysis.vo.ResultVO;
import com.example.commentanalysis.vo.ReviewQualityVO;
import com.example.commentanalysis.vo.SentimentStatisticsVO;
import com.example.commentanalysis.vo.SentimentTrendVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.math.BigDecimal;
import java.util.List;

/**
 * 分析结果控制器。
 *
 * @author 闫宇星
 */
@RestController
@RequestMapping("/api/result")
@RequiredArgsConstructor
public class ResultController {

    private final ResultService resultService;

    private final AuditLogService auditLogService;

    /**
     * 分页查询分析结果明细。
     *
     * <p>支持情感标签、置信度区间与关键词组合筛选（置信度区间对应需求 FR-BIZ-20），
     * 并支持按复核状态过滤与按置信度排序。</p>
     *
     * @param pageNum       页码，从 1 开始，默认 1
     * @param pageSize      每页条数，默认 10，上限 200
     * @param taskId        任务编号，可为空
     * @param sentiment     情感标签筛选（POSITIVE/NEGATIVE/NEUTRAL），可为空
     * @param keyword       关键词模糊匹配，可为空
     * @param minConfidence 置信度区间下限（0～1），可为空
     * @param maxConfidence 置信度区间上限（0～1），可为空
     * @param needReview    是否待复核：1 只看待复核，可为空
     * @param reviewed      是否已人工复核：1 只看已复核，可为空
     * @param sortBy        排序字段：commentId（默认）/ confidence
     * @param sortOrder     排序方向：asc（默认）/ desc
     * @return 结果明细分页数据
     */
    @GetMapping("/list")
    public Result<PageVO<ResultVO>> list(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize,
            @RequestParam(required = false) Long taskId,
            @RequestParam(required = false) String sentiment,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) BigDecimal minConfidence,
            @RequestParam(required = false) BigDecimal maxConfidence,
            @RequestParam(required = false) Integer needReview,
            @RequestParam(required = false) Integer reviewed,
            @RequestParam(required = false) String sortBy,
            @RequestParam(required = false) String sortOrder) {
        return Result.success(resultService.pageResults(
                pageNum, pageSize, taskId, sentiment, keyword, minConfidence, maxConfidence,
                needReview, reviewed, sortBy, sortOrder));
    }

    /**
     * 提交人工复核结论，或撤销单条结果的复核标记。
     *
     * @param id      结果编号
     * @param dto     复核标记与人工情感结论
     * @param session HTTP 会话
     * @return 操作结果
     */
    @PostMapping("/{id}/review")
    public Result<Void> review(@PathVariable("id") Long id,
                               @RequestBody ReviewDTO dto,
                               HttpSession session) {
        boolean reviewed = dto == null || !Boolean.FALSE.equals(dto.getReviewed());
        String sentiment = dto == null ? null : dto.getSentiment();
        resultService.markReviewed(id, reviewed, sentiment);
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                reviewed ? "人工复核" : "撤销复核",
                "结果编号 " + id + (reviewed ? "，复核结论 " + sentimentName(sentiment) : ""));
        return Result.success();
    }

    /**
     * 把情感标签转换为审计日志中的中文描述。
     *
     * @param sentiment 情感标签
     * @return 中文描述，为空表示沿用模型原判定
     */
    private static String sentimentName(String sentiment) {
        if (sentiment == null || sentiment.trim().isEmpty()) {
            return "沿用模型原判定";
        }
        switch (sentiment.trim().toUpperCase()) {
            case "POSITIVE":
                return "正面";
            case "NEGATIVE":
                return "负面";
            case "NEUTRAL":
                return "中性";
            default:
                return sentiment;
        }
    }

    /**
     * 批量提交人工复核结论。
     *
     * @param dto     批量复核参数
     * @param session HTTP 会话
     * @return 实际处理的条数
     */
    @PostMapping("/batch-review")
    public Result<Integer> batchReview(@RequestBody BatchReviewDTO dto, HttpSession session) {
        boolean reviewed = dto == null || !Boolean.FALSE.equals(dto.getReviewed());
        String sentiment = dto == null ? null : dto.getSentiment();
        int count = resultService.batchReview(dto == null ? null : dto.getResultIds(),
                reviewed, sentiment);
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                reviewed ? "批量复核" : "批量撤销复核",
                "共 " + count + " 条" + (reviewed ? "，复核结论 " + sentimentName(sentiment) : ""));
        return Result.success("已处理 " + count + " 条", count);
    }

    /**
     * 查询指定任务的情感分布统计。
     *
     * @param taskId 任务编号
     * @return 情感分布统计
     */
    @GetMapping("/statistics/{taskId}")
    public Result<SentimentStatisticsVO> statistics(@PathVariable Long taskId) {
        return Result.success(resultService.statistics(taskId));
    }

    /**
     * 查询任务级热点关键词（词云数据源）。
     *
     * @param taskId    任务编号
     * @param sentiment 情感维度：ALL / POSITIVE / NEGATIVE / NEUTRAL，默认 ALL
     * @param topN      返回条数，1～50，默认取配置值 50
     * @return 按 TF-IDF 权重降序的关键词列表
     */
    @GetMapping("/keywords/{taskId}")
    public Result<List<KeywordVO>> keywords(
            @PathVariable Long taskId,
            @RequestParam(defaultValue = "ALL") String sentiment,
            @RequestParam(required = false) Integer topN) {
        return Result.success(resultService.keywords(taskId, sentiment, topN));
    }

    /**
     * 查询任务的情感趋势（FR-BIZ-18）。
     *
     * <p>按评论原始时间聚合三类情感条数；源文件没有时间列时返回空数据点，
     * 前端据此隐藏趋势图。</p>
     *
     * @param taskId      任务编号
     * @param granularity 聚合粒度：auto（默认）/ hour / day
     * @return 情感趋势数据
     */
    @GetMapping("/trend/{taskId}")
    public Result<SentimentTrendVO> trend(@PathVariable Long taskId,
                                          @RequestParam(defaultValue = "auto") String granularity) {
        return Result.success(resultService.trend(taskId, granularity));
    }

    /**
     * 查询任务置信度区间分布（直方图数据源）。
     *
     * @param taskId 任务编号
     * @return 置信度分布
     */
    @GetMapping("/confidence/{taskId}")
    public Result<ConfidenceDistributionVO> confidence(@PathVariable Long taskId) {
        return Result.success(resultService.confidenceDistribution(taskId));
    }

    /**
     * 查询任务的人工复核质量。
     *
     * @param taskId 任务编号
     * @return 一致率、改判方向与混淆矩阵
     */
    @GetMapping("/review-quality/{taskId}")
    public Result<ReviewQualityVO> reviewQuality(@PathVariable Long taskId) {
        return Result.success(resultService.reviewQuality(taskId));
    }

    /**
     * 生成并下载任务分析报告（单文件 HTML，可直接打印为 PDF）。
     *
     * <p>响应为 HTML 字节流，非 JSON 结构，故不套用统一响应封装。</p>
     *
     * @param taskId   任务编号
     * @param session  HTTP 会话
     * @param response HTTP 响应
     */
    @GetMapping("/report/{taskId}")
    public void report(@PathVariable Long taskId, HttpSession session,
                       HttpServletResponse response) {
        resultService.exportReport(taskId, response);
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                "生成分析报告", "任务编号 " + taskId);
    }

    /**
     * 导出指定任务的分析结果 Excel。
     *
     * <p>响应类型为 xlsx 字节流，非 JSON 结构，故不套用统一响应封装；
     * 导出前的校验失败（任务不存在、数据量超限）仍由全局异常处理器返回统一 JSON。
     * 输出含「分析结果」明细工作表与「统计摘要」工作表（FR-BIZ-25 / FR-BIZ-26），
     * 支持按 scope 控制导出范围（FR-BIZ-27：all 全量 / current 当前筛选）。</p>
     *
     * @param taskId     任务编号
     * @param scope      导出范围：all / current，默认 all
     * @param sentiment  当前筛选的情感标签，scope=current 时生效
     * @param keyword    当前筛选的关键词，scope=current 时生效
     * @param needReview    当前筛选的待复核状态，scope=current 时生效
     * @param reviewed      当前筛选的已复核状态，scope=current 时生效
     * @param minConfidence 当前筛选的置信度下限，scope=current 时生效
     * @param maxConfidence 当前筛选的置信度上限，scope=current 时生效
     * @param format        导出格式：xlsx / csv / json，默认 xlsx
     * @param response      HTTP 响应
     */
    @GetMapping("/export/{taskId}")
    public void export(@PathVariable Long taskId,
                       @RequestParam(defaultValue = "all") String scope,
                       @RequestParam(required = false) String sentiment,
                       @RequestParam(required = false) String keyword,
                       @RequestParam(required = false) Integer needReview,
                       @RequestParam(required = false) Integer reviewed,
                       @RequestParam(required = false) BigDecimal minConfidence,
                       @RequestParam(required = false) BigDecimal maxConfidence,
                       @RequestParam(defaultValue = "xlsx") String format,
                       HttpServletResponse response) {
        resultService.export(taskId, scope, sentiment, keyword, needReview, reviewed,
                minConfidence, maxConfidence, format, response);
    }
}
