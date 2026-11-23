package com.example.commentanalysis.service.impl;

import com.alibaba.excel.EasyExcel;
import com.alibaba.excel.ExcelWriter;
import com.alibaba.excel.write.metadata.WriteSheet;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.PageVO;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.config.InferenceProperties;
import com.example.commentanalysis.entity.AnalysisResult;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.entity.CommentData;
import com.example.commentanalysis.entity.KeywordStatistics;
import com.example.commentanalysis.entity.TaskStatistics;
import com.example.commentanalysis.mapper.AnalysisResultMapper;
import com.example.commentanalysis.mapper.AnalysisTaskMapper;
import com.example.commentanalysis.mapper.CommentDataMapper;
import com.example.commentanalysis.mapper.KeywordStatisticsMapper;
import com.example.commentanalysis.mapper.TaskStatisticsMapper;
import com.example.commentanalysis.service.ResultService;
import com.example.commentanalysis.vo.CommentTimeRangeVO;
import com.example.commentanalysis.vo.ConfidenceBucketRow;
import com.example.commentanalysis.vo.ConfidenceDistributionVO;
import com.example.commentanalysis.vo.KeywordVO;
import com.example.commentanalysis.vo.ResultExportVO;
import com.example.commentanalysis.vo.ResultVO;
import com.example.commentanalysis.vo.ReviewMatrixRow;
import com.example.commentanalysis.vo.ReviewQualityVO;
import com.example.commentanalysis.vo.SentimentStatisticsVO;
import com.example.commentanalysis.vo.SentimentTrendVO;
import com.example.commentanalysis.vo.SummaryRowVO;
import com.fasterxml.jackson.core.JsonEncoding;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.io.UncheckedIOException;
import java.io.UnsupportedEncodingException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Consumer;
import java.util.stream.Collectors;

/**
 * 分析结果业务服务实现。
 *
 * @author 闫宇星
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ResultServiceImpl implements ResultService {

    /** 情感标签：正面 */
    private static final String SENTIMENT_POSITIVE = "POSITIVE";

    /** 情感标签：负面 */
    private static final String SENTIMENT_NEGATIVE = "NEGATIVE";

    /** 情感标签：中性 */
    private static final String SENTIMENT_NEUTRAL = "NEUTRAL";

    /** 待人工复核标记：是 */
    private static final int NEED_REVIEW_YES = 1;

    /** 全局热词的情感维度标记 */
    private static final String SENTIMENT_ALL = "ALL";

    /** 热点词返回条数上限（对应需求 FR-BIZ-17「取权重前 50 项」与配置 keyword-top-n） */
    private static final int MAX_KEYWORD_TOP_N = 50;

    /** 默认每页条数 */
    private static final int DEFAULT_PAGE_SIZE = 10;

    /** 每页条数上限 */
    private static final int MAX_PAGE_SIZE = 200;

    /** 单次批量复核条数上限 */
    private static final int MAX_BATCH_REVIEW = 1000;

    /** 分析报告中展示的热词条数 */
    private static final int REPORT_KEYWORD_TOP_N = 10;

    /** 导出数据量上限（对应需求 FR-BIZ-27） */
    private static final long MAX_EXPORT_ROWS = 200_000L;

    /** 导出分批读取条数，控制内存占用 */
    private static final int EXPORT_PAGE_SIZE = 2000;

    /** 导出文件名中的时间戳格式 */
    private static final DateTimeFormatter FILE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    /** 导出内容中的时间格式 */
    private static final DateTimeFormatter EXPORT_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 导出格式：Excel */
    private static final String EXPORT_XLSX = "xlsx";

    /** 导出格式：CSV */
    private static final String EXPORT_CSV = "csv";

    /** 导出格式：JSON */
    private static final String EXPORT_JSON = "json";

    /** 支持的导出格式集合 */
    private static final Set<String> EXPORT_FORMATS =
            new HashSet<>(Arrays.asList(EXPORT_XLSX, EXPORT_CSV, EXPORT_JSON));

    private final AnalysisResultMapper analysisResultMapper;

    private final AnalysisTaskMapper analysisTaskMapper;

    private final CommentDataMapper commentDataMapper;

    private final KeywordStatisticsMapper keywordStatisticsMapper;

    private final TaskStatisticsMapper taskStatisticsMapper;

    private final InferenceProperties inferenceProperties;

    private final ObjectMapper objectMapper;

    @Override
    public PageVO<ResultVO> pageResults(Integer pageNum, Integer pageSize, Long taskId,
                                        String sentiment, String keyword,
                                        BigDecimal minConfidence, BigDecimal maxConfidence,
                                        Integer needReview, Integer reviewed,
                                        String sortBy, String sortOrder) {
        if (taskId != null) {
            requireTask(taskId);
        }
        Page<AnalysisResult> page = new Page<>(normalizePageNum(pageNum), normalizePageSize(pageSize));
        LambdaQueryWrapper<AnalysisResult> wrapper = new LambdaQueryWrapper<AnalysisResult>()
                .eq(taskId != null, AnalysisResult::getTaskId, taskId)
                .eq(StringUtils.hasText(sentiment), AnalysisResult::getSentiment, sentiment)
                .ge(minConfidence != null, AnalysisResult::getConfidence, minConfidence)
                .le(maxConfidence != null, AnalysisResult::getConfidence, maxConfidence)
                .eq(needReview != null, AnalysisResult::getNeedReview, needReview)
                .eq(reviewed != null, AnalysisResult::getReviewed, reviewed);
        // 排序：默认按评论号升序；置信度列可切换升降序，便于快速定位低置信度结果
        boolean confidenceSort = "confidence".equalsIgnoreCase(sortBy);
        boolean desc = "desc".equalsIgnoreCase(sortOrder);
        if (confidenceSort) {
            wrapper.orderBy(true, desc, AnalysisResult::getConfidence)
                    .orderByAsc(AnalysisResult::getCommentId);
        } else {
            wrapper.orderBy(true, desc, AnalysisResult::getCommentId);
        }
        // 关键词搜索同时匹配「该条关键词」与「评论正文」，与前端“搜索评论内容或关键词”的提示一致。
        // 使用 apply 的 {n} 占位符绑定参数，避免 SQL 注入。
        if (StringUtils.hasText(keyword)) {
            String kw = keyword.trim();
            wrapper.apply("(keywords LIKE CONCAT('%', {0}, '%') OR comment_id IN ("
                            + "SELECT c.comment_id FROM comment_data c "
                            + "WHERE c.task_id = analysis_result.task_id "
                            + "AND c.content LIKE CONCAT('%', {1}, '%')))",
                    kw, kw);
        }
        analysisResultMapper.selectPage(page, wrapper);
        return PageVO.of(page, assembleResultVOs(page.getRecords()));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void markReviewed(Long resultId, boolean reviewed, String sentiment) {
        if (resultId == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "结果编号不能为空");
        }
        AnalysisResult result = analysisResultMapper.selectById(resultId);
        if (result == null) {
            throw new BizException(ResultCode.NOT_FOUND, "结果不存在或已被删除");
        }

        // 撤销复核时保留已确认的人工结论，仅把记录退回待复核队列
        String conclusion = reviewed ? normalizeReviewSentiment(sentiment) : null;
        String original = result.getSentiment();
        // 模型原判定：改判过则取首次记录的原判定，否则就是当前标签
        String modelLabel = StringUtils.hasText(result.getOriginalSentiment())
                ? result.getOriginalSentiment() : original;
        boolean corrected = conclusion != null && !conclusion.equals(modelLabel);
        // 改判后又选回模型原判定：需要清除改判痕迹，否则一致率仍按改判统计
        boolean revertedToModel = conclusion != null && !corrected
                && StringUtils.hasText(result.getOriginalSentiment());

        AnalysisResult update = new AnalysisResult();
        update.setResultId(resultId);
        // 已复核置 0；撤销复核重新置 1，重新回到待复核列表
        update.setNeedReview(reviewed ? 0 : NEED_REVIEW_YES);
        update.setReviewed(reviewed ? 1 : 0);
        if (corrected) {
            update.setSentiment(conclusion);
            // 仅首次改判记录模型原判定，多次改判时保留最初的原判定
            if (!StringUtils.hasText(result.getOriginalSentiment())) {
                update.setOriginalSentiment(original);
            }
        }
        if (revertedToModel) {
            // 标签回到模型判定，并清空原判定字段，一致率不再按改判统计
            update.setSentiment(conclusion);
        }
        analysisResultMapper.updateById(update);
        if (revertedToModel) {
            analysisResultMapper.clearOriginalSentiment(resultId);
        }

        // 复核会改变情感分布、待复核条数与平均置信度，统一按最新明细重算统计快照
        refreshTaskStatistics(result.getTaskId());

        log.info("{}复核结果：resultId={}, taskId={}, 原判定={}, 人工结论={}",
                reviewed ? "已提交" : "已撤销", resultId, result.getTaskId(), modelLabel,
                conclusion == null ? "沿用原判定" : conclusion);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int batchReview(List<Long> resultIds, boolean reviewed, String sentiment) {
        if (resultIds == null || resultIds.isEmpty()) {
            throw new BizException(ResultCode.BAD_REQUEST, "请先选择要复核的结果");
        }
        List<Long> ids = resultIds.stream()
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());
        if (ids.isEmpty()) {
            throw new BizException(ResultCode.BAD_REQUEST, "请先选择要复核的结果");
        }
        if (ids.size() > MAX_BATCH_REVIEW) {
            throw new BizException(ResultCode.BAD_REQUEST,
                    "单次最多复核 " + MAX_BATCH_REVIEW + " 条，请缩小选择范围");
        }
        List<AnalysisResult> records = analysisResultMapper.selectBatchIds(ids);
        if (records.isEmpty()) {
            throw new BizException(ResultCode.NOT_FOUND, "所选结果不存在或已被删除");
        }

        String conclusion = reviewed ? normalizeReviewSentiment(sentiment) : null;
        Set<Long> taskIds = new HashSet<>();
        int updated = 0;
        for (AnalysisResult record : records) {
            AnalysisResult update = new AnalysisResult();
            update.setResultId(record.getResultId());
            update.setNeedReview(reviewed ? 0 : NEED_REVIEW_YES);
            update.setReviewed(reviewed ? 1 : 0);
            boolean reverted = false;
            if (conclusion != null) {
                String modelLabel = StringUtils.hasText(record.getOriginalSentiment())
                        ? record.getOriginalSentiment() : record.getSentiment();
                if (!conclusion.equals(modelLabel)) {
                    update.setSentiment(conclusion);
                    if (!StringUtils.hasText(record.getOriginalSentiment())) {
                        update.setOriginalSentiment(record.getSentiment());
                    }
                } else {
                    update.setSentiment(conclusion);
                    reverted = StringUtils.hasText(record.getOriginalSentiment());
                }
            }
            analysisResultMapper.updateById(update);
            if (reverted) {
                // 批量复核选回模型原判定时同样清除改判痕迹
                analysisResultMapper.clearOriginalSentiment(record.getResultId());
            }
            if (record.getTaskId() != null) {
                taskIds.add(record.getTaskId());
            }
            updated++;
        }
        taskIds.forEach(this::refreshTaskStatistics);

        log.info("批量{}复核完成：条数={}, 涉及任务数={}, 人工结论={}",
                reviewed ? "" : "撤销", updated, taskIds.size(),
                conclusion == null ? "沿用原判定" : conclusion);
        return updated;
    }

    /**
     * 按最新明细重算任务统计快照。
     *
     * <p>人工复核会改变情感分布、待复核条数与平均置信度，重算比逐字段增量修正更可靠，
     * 也能避免多次改判后统计出现漂移。异常条数沿用任务表口径。</p>
     *
     * @param taskId 任务编号
     */
    private void refreshTaskStatistics(Long taskId) {
        if (taskId == null) {
            return;
        }
        TaskStatistics existing = taskStatisticsMapper.selectOne(new LambdaQueryWrapper<TaskStatistics>()
                .eq(TaskStatistics::getTaskId, taskId));
        TaskStatistics summary = analysisResultMapper.selectSummary(taskId);
        if (summary == null) {
            return;
        }
        LocalDateTime now = LocalDateTime.now();
        summary.setTaskId(taskId);
        summary.setErrorCount(existing == null || existing.getErrorCount() == null
                ? 0 : existing.getErrorCount());
        // 统计快照重建时沿用原创建时间，便于追溯任务统计首次生成时间
        summary.setCreateTime(existing == null || existing.getCreateTime() == null
                ? now : existing.getCreateTime());
        summary.setUpdateTime(now);
        // 先清理旧行，规避 uk_task 唯一索引冲突
        taskStatisticsMapper.delete(new LambdaQueryWrapper<TaskStatistics>()
                .eq(TaskStatistics::getTaskId, taskId));
        taskStatisticsMapper.insert(summary);
    }

    /**
     * 校验并规范化人工复核的情感结论。
     *
     * @param sentiment 复核结论
     * @return 规范化后的标签；为空表示沿用模型原判定
     */
    private static String normalizeReviewSentiment(String sentiment) {
        if (!StringUtils.hasText(sentiment)) {
            return null;
        }
        String value = sentiment.trim().toUpperCase(Locale.ROOT);
        if (!SENTIMENT_POSITIVE.equals(value)
                && !SENTIMENT_NEGATIVE.equals(value)
                && !SENTIMENT_NEUTRAL.equals(value)) {
            throw new BizException(ResultCode.BAD_REQUEST,
                    "复核结论只能是 POSITIVE / NEGATIVE / NEUTRAL");
        }
        return value;
    }

    @Override
    public SentimentStatisticsVO statistics(Long taskId) {
        if (taskId == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务编号不能为空");
        }
        AnalysisTask task = requireTask(taskId);

        // 优先读取预聚合统计：把"扫描上万行明细做分组统计"降级为"读取 1 行"（优化点 ⑤）
        TaskStatistics statistics = taskStatisticsMapper.selectOne(new LambdaQueryWrapper<TaskStatistics>()
                .eq(TaskStatistics::getTaskId, taskId));
        if (statistics == null) {
            // 任务被终止或早于预聚合逻辑的历史数据没有统计行，回退为实时聚合
            statistics = analysisResultMapper.selectSummary(taskId);
            if (statistics == null) {
                statistics = new TaskStatistics();
            }
            statistics.setErrorCount(task.getErrorCount());
        }
        return toStatisticsVO(taskId, statistics);
    }

    @Override
    public SentimentTrendVO trend(Long taskId, String granularity) {
        if (taskId == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务编号不能为空");
        }
        requireTask(taskId);

        boolean hourly;
        if ("hour".equalsIgnoreCase(granularity)) {
            hourly = true;
        } else if ("day".equalsIgnoreCase(granularity)) {
            hourly = false;
        } else {
            // auto：时间跨度不超过 48 小时按小时聚合，否则按天聚合
            CommentTimeRangeVO range = analysisResultMapper.selectCommentTimeRange(taskId);
            if (range == null || range.getMinTime() == null || range.getMaxTime() == null) {
                SentimentTrendVO empty = new SentimentTrendVO();
                empty.setGranularity("day");
                return empty;
            }
            hourly = Duration.between(range.getMinTime(), range.getMaxTime()).toHours() <= 48L;
        }

        SentimentTrendVO vo = new SentimentTrendVO();
        vo.setGranularity(hourly ? "hour" : "day");
        List<SentimentTrendVO.Point> points = analysisResultMapper.selectTrend(taskId,
                hourly ? "%Y-%m-%d %H:00" : "%Y-%m-%d");
        vo.setPoints(points == null ? Collections.emptyList() : points);
        return vo;
    }

    @Override
    public ConfidenceDistributionVO confidenceDistribution(Long taskId) {
        if (taskId == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务编号不能为空");
        }
        requireTask(taskId);

        double threshold = inferenceProperties.getReviewThreshold();
        Map<Integer, Long> counts = new HashMap<>(16);
        long total = 0L;
        for (ConfidenceBucketRow row : analysisResultMapper.selectConfidenceBuckets(taskId)) {
            long count = row.getCnt() == null ? 0L : row.getCnt();
            counts.merge(row.getBucketIndex() == null ? 0 : row.getBucketIndex(), count, Long::sum);
            total += count;
        }

        ConfidenceDistributionVO vo = new ConfidenceDistributionVO();
        vo.setTaskId(taskId);
        vo.setTotalCount(total);
        vo.setThreshold(threshold);
        for (int index = 0; index < 10; index++) {
            double lower = index / 10.0D;
            double upper = (index + 1) / 10.0D;
            long count = counts.getOrDefault(index, 0L);
            ConfidenceDistributionVO.Bucket bucket = new ConfidenceDistributionVO.Bucket();
            bucket.setLower(lower);
            bucket.setUpper(upper);
            bucket.setLabel(String.format(Locale.ROOT, "%.1f～%.1f", lower, upper));
            bucket.setCount(count);
            bucket.setRatio(ratio(count, total));
            vo.getBuckets().add(bucket);
        }

        long below = analysisResultMapper.countBelowConfidence(taskId, threshold);
        vo.setBelowThresholdCount(below);
        vo.setBelowThresholdRatio(ratio(below, total));
        return vo;
    }

    @Override
    public ReviewQualityVO reviewQuality(Long taskId) {
        if (taskId == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务编号不能为空");
        }
        requireTask(taskId);

        long reviewed = analysisResultMapper.countReviewed(taskId);
        long corrected = analysisResultMapper.countCorrected(taskId);
        long agreement = Math.max(reviewed - corrected, 0L);

        ReviewQualityVO vo = new ReviewQualityVO();
        vo.setTaskId(taskId);
        vo.setReviewedCount(reviewed);
        vo.setCorrectedCount(corrected);
        vo.setAgreementCount(agreement);
        vo.setAgreementRate(reviewed > 0
                ? BigDecimal.valueOf(agreement).divide(BigDecimal.valueOf(reviewed), 4, RoundingMode.HALF_UP)
                : null);

        List<String> labels = Arrays.asList(SENTIMENT_POSITIVE, SENTIMENT_NEGATIVE, SENTIMENT_NEUTRAL);
        vo.setLabels(labels);
        vo.setLabelNames(labels.stream().map(this::sentimentLabel).collect(Collectors.toList()));

        // 先建立完整的 3×3 矩阵，再把有数据的单元格填进去，保证前端渲染稳定
        Map<String, Long> cellCounts = new HashMap<>(16);
        for (ReviewMatrixRow row : analysisResultMapper.selectReviewMatrix(taskId)) {
            if (row.getModelLabel() == null || row.getHumanLabel() == null) {
                continue;
            }
            cellCounts.put(row.getModelLabel() + '\u0000' + row.getHumanLabel(),
                    row.getCnt() == null ? 0L : row.getCnt());
        }
        for (String modelLabel : labels) {
            for (String humanLabel : labels) {
                ReviewQualityVO.MatrixCell cell = new ReviewQualityVO.MatrixCell();
                cell.setModelLabel(modelLabel);
                cell.setHumanLabel(humanLabel);
                cell.setCount(cellCounts.getOrDefault(modelLabel + '\u0000' + humanLabel, 0L));
                vo.getMatrix().add(cell);
            }
        }

        for (String from : labels) {
            for (String to : labels) {
                if (from.equals(to)) {
                    continue;
                }
                long count = cellCounts.getOrDefault(from + '\u0000' + to, 0L);
                if (count <= 0) {
                    continue;
                }
                ReviewQualityVO.Correction correction = new ReviewQualityVO.Correction();
                correction.setFromLabel(from);
                correction.setToLabel(to);
                correction.setCount(count);
                vo.getCorrections().add(correction);
            }
        }
        vo.getCorrections().sort((a, b) -> Long.compare(b.getCount(), a.getCount()));
        return vo;
    }

    @Override
    public void exportReport(Long taskId, HttpServletResponse response) {
        if (taskId == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务编号不能为空");
        }
        AnalysisTask task = requireTask(taskId);
        SentimentStatisticsVO stats = statistics(taskId);
        ConfidenceDistributionVO confidence = confidenceDistribution(taskId);
        ReviewQualityVO quality = reviewQuality(taskId);
        List<KeywordVO> topKeywords = keywords(taskId, SENTIMENT_ALL, REPORT_KEYWORD_TOP_N);
        List<KeywordVO> negativeKeywords = keywords(taskId, SENTIMENT_NEGATIVE, REPORT_KEYWORD_TOP_N);

        String html = buildReportHtml(task, stats, confidence, quality, topKeywords, negativeKeywords);

        String fileName = "分析报告_" + safeFileName(task.getTaskName())
                + "_" + LocalDateTime.now().format(FILE_TIME_FORMATTER) + ".html";
        try {
            String encoded = URLEncoder.encode(fileName, "UTF-8").replaceAll("\\+", "%20");
            response.setContentType("text/html");
            response.setCharacterEncoding("UTF-8");
            response.setHeader("Content-Disposition", "attachment;filename*=utf-8''" + encoded);
            byte[] bytes = html.getBytes(StandardCharsets.UTF_8);
            response.setContentLength(bytes.length);
            response.getOutputStream().write(bytes);
            response.flushBuffer();
        } catch (UnsupportedEncodingException e) {
            throw new BizException(ResultCode.EXPORT_FAILED, "报告文件名编码失败");
        } catch (IOException e) {
            throw new BizException(ResultCode.EXPORT_FAILED, "报告写出失败，请重试");
        }
        log.info("分析报告已生成：taskId={}, fileName={}", taskId, fileName);
    }

    /**
     * 组装单文件 HTML 分析报告。
     *
     * <p>样式与图形全部内联（CSS 条块），不依赖外部 CDN，双击即可打开并可直接打印为 PDF。</p>
     *
     * @param task             任务实体
     * @param stats            情感统计
     * @param confidence       置信度分布
     * @param quality          复核质量
     * @param topKeywords      全局热词
     * @param negativeKeywords 负面热词
     * @return HTML 文本
     */
    private String buildReportHtml(AnalysisTask task, SentimentStatisticsVO stats,
                                   ConfidenceDistributionVO confidence, ReviewQualityVO quality,
                                   List<KeywordVO> topKeywords, List<KeywordVO> negativeKeywords) {
        long total = stats.getTotalCount() == null ? 0L : stats.getTotalCount();
        String positivePct = percentText(stats.getPositiveCount() == null ? 0 : stats.getPositiveCount(), total);
        String negativePct = percentText(stats.getNegativeCount() == null ? 0 : stats.getNegativeCount(), total);
        String neutralPct = percentText(stats.getNeutralCount() == null ? 0 : stats.getNeutralCount(), total);

        StringBuilder html = new StringBuilder(8192);
        html.append("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">")
                .append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
                .append("<title>分析报告 - ").append(escapeHtml(task.getTaskName())).append("</title>")
                .append("<style>")
                .append(":root{--ink:#2E241C;--muted:#6A5645;--faint:#7C6855;--line:#E8D9C8;--line-soft:#F1E6D9;")
                .append("--brand:#A64A2B;--pos:#2F9E6B;--neg:#D9534F;--neu:#9C8F84;--bg:#FBF6EF;}")
                .append("*{box-sizing:border-box;}body{margin:0;padding:36px 24px;background:var(--bg);")
                .append("color:var(--ink);font-family:\"PingFang SC\",\"Microsoft YaHei\",system-ui,sans-serif;")
                .append("font-size:14px;line-height:1.7;}")
                .append(".wrap{max-width:920px;margin:0 auto;}")
                .append("h1{font-size:24px;margin:0 0 6px;}h2{font-size:16px;margin:26px 0 12px;")
                .append("padding-left:10px;border-left:3px solid var(--brand);}")
                .append(".meta{color:var(--faint);font-size:12.5px;margin:0 0 22px;}")
                .append(".kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;}")
                .append(".kpi{padding:14px 16px;border:1px solid var(--line);border-radius:10px;background:#fff;}")
                .append(".kpi span{display:block;font-size:11.5px;color:var(--faint);}")
                .append(".kpi b{font-size:22px;font-weight:700;}")
                .append(".card{padding:16px 18px;border:1px solid var(--line);border-radius:10px;")
                .append("background:#fff;margin-bottom:14px;}")
                .append(".row{display:flex;align-items:center;gap:12px;margin-bottom:9px;font-size:12.5px;}")
                .append(".row .name{width:82px;flex:none;color:var(--muted);}")
                .append(".row .track{flex:1;height:10px;border-radius:6px;background:var(--line-soft);overflow:hidden;}")
                .append(".row .fill{display:block;height:100%;border-radius:6px;}")
                .append(".row .val{width:110px;flex:none;text-align:right;font-variant-numeric:tabular-nums;color:var(--muted);}")
                .append(".pos{background:var(--pos);}.neg{background:var(--neg);}.neu{background:var(--neu);}")
                .append("table{width:100%;border-collapse:collapse;font-size:12.5px;}")
                .append("th,td{padding:7px 10px;border-bottom:1px solid var(--line-soft);text-align:left;}")
                .append("th{color:var(--faint);font-weight:600;background:#FCF7F1;}")
                .append("td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;}")
                .append(".matrix td{text-align:center;}.matrix td.diag{background:rgba(47,158,107,.10);font-weight:600;}")
                .append(".tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;}")
                .append(".tag.pos{background:rgba(47,158,107,.12);color:#1F7A50;}")
                .append(".tag.neg{background:rgba(217,83,79,.12);color:#A5382F;}")
                .append(".tag.neu{background:rgba(156,143,132,.14);color:#6E6156;}")
                .append(".foot{margin-top:26px;padding-top:14px;border-top:1px solid var(--line);")
                .append("color:var(--faint);font-size:11.5px;}")
                .append("@media print{body{background:#fff;padding:0;}.card,.kpi{break-inside:avoid;}}")
                .append("@media (max-width:720px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr));}}")
                .append("</style></head><body><div class=\"wrap\">");

        html.append("<h1>").append(escapeHtml(task.getTaskName())).append("</h1>")
                .append("<p class=\"meta\">源文件 ").append(escapeHtml(task.getFileName()))
                .append("　·　评论 ").append(total).append(" 条")
                .append("　·　模型 ").append(escapeHtml(task.getModelVersion()))
                .append("　·　生成于 ").append(formatTime(LocalDateTime.now())).append("</p>");

        // KPI
        html.append("<div class=\"kpis\">");
        appendKpi(html, "评论总数", String.valueOf(total));
        appendKpi(html, "平均置信度", stats.getAvgConfidence() == null ? "—"
                : String.format(Locale.ROOT, "%.1f%%", stats.getAvgConfidence().doubleValue() * 100));
        appendKpi(html, "待人工复核", String.valueOf(toLong(stats.getReviewCount())));
        appendKpi(html, "已人工复核", String.valueOf(quality.getReviewedCount()));
        html.append("</div>");

        // 情感分布
        html.append("<h2>情感分布</h2><div class=\"card\">");
        appendBar(html, "正面", positivePct, stats.getPositiveCount(), total, "pos");
        appendBar(html, "负面", negativePct, stats.getNegativeCount(), total, "neg");
        appendBar(html, "中性", neutralPct, stats.getNeutralCount(), total, "neu");
        html.append("</div>");

        // 置信度分布
        html.append("<h2>置信度分布</h2><div class=\"card\">")
                .append("<p class=\"meta\" style=\"margin:0 0 12px;\">复核阈值 ")
                .append(String.format(Locale.ROOT, "%.0f%%", confidence.getThreshold() * 100))
                .append("，低于阈值的样本 ")
                .append(confidence.getBelowThresholdCount()).append(" 条（")
                .append(String.format(Locale.ROOT, "%.1f%%",
                        confidence.getBelowThresholdRatio() == null ? 0D
                                : confidence.getBelowThresholdRatio().doubleValue() * 100))
                .append("）</p>");
        for (ConfidenceDistributionVO.Bucket bucket : confidence.getBuckets()) {
            long count = bucket.getCount();
            String pct = bucket.getRatio() == null ? "0%"
                    : String.format(Locale.ROOT, "%.1f%%", bucket.getRatio().doubleValue() * 100);
            appendBarWithWidth(html, bucket.getLabel(), pct, count,
                    bucket.getUpper() <= confidence.getThreshold() ? "neg" : "pos");
        }
        html.append("</div>");

        // 热点词
        html.append("<h2>热点关键词</h2><div class=\"card\"><table><thead><tr>")
                .append("<th>排名</th><th>关键词</th><th class=\"num\">TF-IDF 权重</th><th class=\"num\">出现次数</th>")
                .append("</tr></thead><tbody>");
        appendKeywordRows(html, topKeywords);
        html.append("</tbody></table></div>");

        // 负面关键词
        html.append("<h2>负面评论集中关注点</h2><div class=\"card\">");
        if (negativeKeywords == null || negativeKeywords.isEmpty()) {
            html.append("<p class=\"meta\" style=\"margin:0;\">该任务没有负面评论，或未提取到负面关键词。</p>");
        } else {
            html.append("<table><thead><tr><th>排名</th><th>关键词</th>")
                    .append("<th class=\"num\">TF-IDF 权重</th><th class=\"num\">出现次数</th></tr></thead><tbody>");
            appendKeywordRows(html, negativeKeywords);
            html.append("</tbody></table>");
        }
        html.append("</div>");

        // 复核质量
        html.append("<h2>人工复核质量</h2><div class=\"card\">");
        if (quality.getReviewedCount() <= 0) {
            html.append("<p class=\"meta\" style=\"margin:0;\">该任务还没有人工复核记录，")
                    .append("完成复核后可在此查看模型与人工的一致率与混淆矩阵。</p>");
        } else {
            html.append("<p class=\"meta\" style=\"margin:0 0 12px;\">已复核 ")
                    .append(quality.getReviewedCount()).append(" 条，模型与人工一致 ")
                    .append(quality.getAgreementCount()).append(" 条，改判 ")
                    .append(quality.getCorrectedCount()).append(" 条，一致率 ")
                    .append(quality.getAgreementRate() == null ? "—"
                            : String.format(Locale.ROOT, "%.1f%%",
                                    quality.getAgreementRate().doubleValue() * 100))
                    .append("。</p>");
            html.append("<table class=\"matrix\"><thead><tr><th>模型 \\ 人工</th>");
            for (String name : quality.getLabelNames()) {
                html.append("<th class=\"num\">").append(escapeHtml(name)).append("</th>");
            }
            html.append("</tr></thead><tbody>");
            for (int row = 0; row < quality.getLabels().size(); row++) {
                String modelLabel = quality.getLabels().get(row);
                html.append("<tr><th>").append(escapeHtml(quality.getLabelNames().get(row))).append("</th>");
                for (String humanLabel : quality.getLabels()) {
                    long count = 0L;
                    for (ReviewQualityVO.MatrixCell cell : quality.getMatrix()) {
                        if (cell.getModelLabel().equals(modelLabel)
                                && cell.getHumanLabel().equals(humanLabel)) {
                            count = cell.getCount();
                            break;
                        }
                    }
                    html.append("<td").append(modelLabel.equals(humanLabel) ? " class=\"diag\"" : "")
                            .append(">").append(count).append("</td>");
                }
                html.append("</tr>");
            }
            html.append("</tbody></table>");

            if (!quality.getCorrections().isEmpty()) {
                html.append("<table style=\"margin-top:14px;\"><thead><tr>")
                        .append("<th>改判方向</th><th class=\"num\">条数</th></tr></thead><tbody>");
                for (ReviewQualityVO.Correction correction : quality.getCorrections()) {
                    html.append("<tr><td>").append(escapeHtml(sentimentLabel(correction.getFromLabel())))
                            .append(" → ").append(escapeHtml(sentimentLabel(correction.getToLabel())))
                            .append("</td><td class=\"num\">").append(correction.getCount())
                            .append("</td></tr>");
                }
                html.append("</tbody></table>");
            }
        }
        html.append("</div>");

        html.append("<div class=\"foot\">本报告由中文评论智能分析系统自动生成，")
                .append("数据来源为任务 ").append(task.getTaskId()).append(" 的分析结果。</div>")
                .append("</div></body></html>");
        return html.toString();
    }

    /**
     * 追加一个 KPI 块。
     *
     * @param html  HTML 缓冲
     * @param label 指标名
     * @param value 指标值
     */
    private void appendKpi(StringBuilder html, String label, String value) {
        html.append("<div class=\"kpi\"><span>").append(escapeHtml(label))
                .append("</span><b>").append(escapeHtml(value)).append("</b></div>");
    }

    /**
     * 按条目占比追加条形。
     *
     * @param html  HTML 缓冲
     * @param name  条目名
     * @param text  右侧数值文案
     * @param count 条数
     * @param total 总数
     * @param tone  颜色类名
     */
    private void appendBar(StringBuilder html, String name, String text, Number count,
                           long total, String tone) {
        double width = total <= 0 ? 0D : (count.doubleValue() / total) * 100;
        appendBarWithWidth(html, name, text, count.longValue(), tone, width);
    }

    /**
     * 按固定宽度追加条形。
     *
     * @param html  HTML 缓冲
     * @param name  条目名
     * @param text  右侧数值文案
     * @param count 条数
     * @param tone  颜色类名
     */
    private void appendBarWithWidth(StringBuilder html, String name, String text, long count, String tone) {
        appendBarWithWidth(html, name, text, count, tone, Math.min(count, 100));
    }

    /**
     * 追加条形（指定宽度百分比）。
     */
    private void appendBarWithWidth(StringBuilder html, String name, String text, long count,
                                    String tone, double width) {
        html.append("<div class=\"row\"><span class=\"name\">").append(escapeHtml(name))
                .append("</span><span class=\"track\"><i class=\"fill ").append(tone)
                .append("\" style=\"width:").append(String.format(Locale.ROOT, "%.2f", width))
                .append("%\"></i></span><span class=\"val\">").append(escapeHtml(text))
                .append("（").append(count).append(" 条）</span></div>");
    }

    /**
     * 追加关键词表格行。
     *
     * @param html     HTML 缓冲
     * @param keywords 关键词列表
     */
    private void appendKeywordRows(StringBuilder html, List<KeywordVO> keywords) {
        if (keywords == null || keywords.isEmpty()) {
            html.append("<tr><td colspan=\"4\">暂无关键词</td></tr>");
            return;
        }
        int rank = 1;
        for (KeywordVO keyword : keywords) {
            html.append("<tr><td>").append(rank++).append("</td><td>")
                    .append(escapeHtml(keyword.getWord())).append("</td><td class=\"num\">")
                    .append(keyword.getWeight() == null ? "—" : keyword.getWeight().toPlainString())
                    .append("</td><td class=\"num\">")
                    .append(keyword.getWordCount() == null ? 0 : keyword.getWordCount())
                    .append("</td></tr>");
        }
    }

    /**
     * 转义 HTML 特殊字符，避免任务名或评论内容破坏报告结构。
     *
     * @param value 原始文本
     * @return 转义后的文本
     */
    private String escapeHtml(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }

    /**
     * 清洗文件名中的非法字符。
     *
     * @param name 原始名称
     * @return 安全文件名
     */
    private String safeFileName(String name) {
        if (!StringUtils.hasText(name)) {
            return "任务";
        }
        String cleaned = name.replaceAll("[\\\\/:*?\"<>|\\s]", "_");
        return cleaned.length() > 40 ? cleaned.substring(0, 40) : cleaned;
    }

    /**
     * 统计实体转视图，占比在应用层计算。
     *
     * @param taskId     任务编号
     * @param statistics 统计实体
     * @return 情感分布统计视图
     */
    private SentimentStatisticsVO toStatisticsVO(Long taskId, TaskStatistics statistics) {
        long totalCount = toLong(statistics.getTotalCount());
        long positiveCount = toLong(statistics.getPositiveCount());
        long negativeCount = toLong(statistics.getNegativeCount());
        long neutralCount = toLong(statistics.getNeutralCount());

        SentimentStatisticsVO vo = new SentimentStatisticsVO();
        vo.setTaskId(taskId);
        vo.setTotalCount(totalCount);
        vo.setPositiveCount(positiveCount);
        vo.setNegativeCount(negativeCount);
        vo.setNeutralCount(neutralCount);
        vo.setPositiveRatio(ratio(positiveCount, totalCount));
        vo.setNegativeRatio(ratio(negativeCount, totalCount));
        vo.setNeutralRatio(ratio(neutralCount, totalCount));
        vo.setReviewCount(toLong(statistics.getReviewCount()));
        vo.setErrorCount(statistics.getErrorCount() == null ? 0 : statistics.getErrorCount());
        vo.setAvgConfidence(statistics.getAvgConfidence());
        return vo;
    }

    @Override
    public List<KeywordVO> keywords(Long taskId, String sentiment, Integer topN) {
        requireTask(taskId);
        // 情感维度归一：为空按全局 ALL，大小写不敏感
        String dimension = StringUtils.hasText(sentiment)
                ? sentiment.trim().toUpperCase(Locale.ROOT)
                : SENTIMENT_ALL;
        // 返回条数受「请求值 / 配置上限 / 需求上限 50」三重约束
        int limit = (topN == null || topN < 1)
                ? Math.min(inferenceProperties.getKeywordTopN(), MAX_KEYWORD_TOP_N)
                : Math.min(Math.min(topN, inferenceProperties.getKeywordTopN()), MAX_KEYWORD_TOP_N);

        // idx_task_weight (task_id, weight DESC) 支撑权重降序直接输出，免排序
        Page<KeywordStatistics> page = new Page<>(1, limit, false);
        keywordStatisticsMapper.selectPage(page, new LambdaQueryWrapper<KeywordStatistics>()
                .eq(KeywordStatistics::getTaskId, taskId)
                .eq(KeywordStatistics::getSentiment, dimension)
                .orderByDesc(KeywordStatistics::getWeight));

        List<KeywordVO> list = new ArrayList<>(page.getRecords().size());
        for (KeywordStatistics row : page.getRecords()) {
            KeywordVO vo = new KeywordVO();
            vo.setWord(row.getWord());
            vo.setWeight(row.getWeight());
            vo.setWordCount(row.getWordCount());
            vo.setSentiment(row.getSentiment());
            list.add(vo);
        }
        return list;
    }

    @Override
    public void export(Long taskId, String scope, String sentiment, String keyword,
                       Integer needReview, Integer reviewed,
                       BigDecimal minConfidence, BigDecimal maxConfidence,
                       String format, HttpServletResponse response) {
        if (taskId == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "任务编号不能为空");
        }
        String exportFormat = normalizeExportFormat(format);
        // 1. 校验任务存在与数据量上限（校验失败时尚未写入响应头，仍可返回统一 JSON 错误）
        AnalysisTask task = requireTask(taskId);
        // 导出范围：current 且携带筛选条件时按当前筛选导出，否则全量（FR-BIZ-27）
        boolean filtered = "current".equalsIgnoreCase(scope)
                && (StringUtils.hasText(sentiment) || StringUtils.hasText(keyword)
                || needReview != null || reviewed != null
                || minConfidence != null || maxConfidence != null);
        String filterSentiment = filtered ? sentiment : null;
        String filterKeyword = filtered ? keyword : null;
        Integer filterNeedReview = filtered ? needReview : null;
        Integer filterReviewed = filtered ? reviewed : null;
        BigDecimal filterMinConfidence = filtered ? minConfidence : null;
        BigDecimal filterMaxConfidence = filtered ? maxConfidence : null;
        Long total = filtered
                ? analysisResultMapper.countFiltered(taskId, filterSentiment, filterKeyword,
                        filterNeedReview, filterReviewed, filterMinConfidence, filterMaxConfidence)
                : analysisResultMapper.selectCount(new LambdaQueryWrapper<AnalysisResult>()
                        .eq(AnalysisResult::getTaskId, taskId));
        if (total != null && total > MAX_EXPORT_ROWS) {
            throw new BizException(ResultCode.EXPORT_TOO_LARGE);
        }

        // 2. 校验通过后再设置响应头
        writeExportHeader(response, taskId, task.getTaskName(), exportFormat);

        // 3. 按格式流式写出行数据
        try {
            if (EXPORT_XLSX.equals(exportFormat)) {
                writeExcelRows(taskId, filtered, filterSentiment, filterKeyword,
                        filterNeedReview, filterReviewed, filterMinConfidence, filterMaxConfidence,
                        total, task.getTaskName(), response);
            } else if (EXPORT_CSV.equals(exportFormat)) {
                writeCsvRows(taskId, filtered, filterSentiment, filterKeyword,
                        filterNeedReview, filterReviewed, filterMinConfidence, filterMaxConfidence,
                        total, response);
            } else {
                writeJsonRows(taskId, filtered, filterSentiment, filterKeyword,
                        filterNeedReview, filterReviewed, filterMinConfidence, filterMaxConfidence,
                        total, response);
            }
        } catch (IOException e) {
            log.error("导出分析结果失败：taskId={}, format={}", taskId, exportFormat, e);
            throw new BizException(ResultCode.EXPORT_FAILED);
        }
        log.info("导出分析结果完成：taskId={}, 范围={}, 格式={}, 总条数={}",
                taskId, filtered ? "当前筛选" : "全量", exportFormat, total);
    }

    /**
     * 校验并归一导出格式。
     *
     * @param format 请求格式
     * @return xlsx / csv / json
     */
    private String normalizeExportFormat(String format) {
        String value = format == null ? EXPORT_XLSX : format.trim().toLowerCase(Locale.ROOT);
        if (!EXPORT_FORMATS.contains(value)) {
            throw new BizException(ResultCode.BAD_REQUEST, "导出格式仅支持 xlsx / csv / json");
        }
        return value;
    }

    /**
     * 分批读取导出数据并交给调用方写出，避免一次性加载全量结果。
     *
     * @param taskId           任务编号
     * @param filtered         是否按当前筛选导出
     * @param filterSentiment  情感筛选
     * @param filterKeyword    关键词筛选
     * @param filterNeedReview 复核状态筛选
     * @param total            预计总条数，用于提前结束
     * @param consumer         每批数据的写出逻辑
     */
    private void streamExportRows(Long taskId, boolean filtered, String filterSentiment,
                                  String filterKeyword, Integer filterNeedReview, Integer filterReviewed,
                                  BigDecimal filterMinConfidence, BigDecimal filterMaxConfidence,
                                  Long total, Consumer<List<AnalysisResult>> consumer) {
        long offset = 0L;
        while (true) {
            List<AnalysisResult> records = filtered
                    ? analysisResultMapper.selectExportPageFiltered(
                            taskId, filterSentiment, filterKeyword, filterNeedReview, filterReviewed,
                            filterMinConfidence, filterMaxConfidence, offset, EXPORT_PAGE_SIZE)
                    : analysisResultMapper.selectExportPage(taskId, offset, EXPORT_PAGE_SIZE);
            if (records.isEmpty()) {
                return;
            }
            consumer.accept(records);
            offset += records.size();
            if (records.size() < EXPORT_PAGE_SIZE || (total != null && offset >= total)) {
                return;
            }
        }
    }

    /**
     * 导出 Excel：明细工作表 + 统计摘要工作表（FR-BIZ-25 / FR-BIZ-26）。
     *
     * @param taskId           任务编号
     * @param filtered         是否按筛选导出
     * @param filterSentiment  情感筛选
     * @param filterKeyword    关键词筛选
     * @param filterNeedReview 复核状态筛选
     * @param total            预计总条数
     * @param taskName         任务名称
     * @param response         HTTP 响应
     * @throws IOException 写出失败
     */
    private void writeExcelRows(Long taskId, boolean filtered, String filterSentiment,
                                String filterKeyword, Integer filterNeedReview, Integer filterReviewed,
                                BigDecimal filterMinConfidence, BigDecimal filterMaxConfidence,
                                Long total, String taskName, HttpServletResponse response) throws IOException {
        try (ExcelWriter excelWriter = EasyExcel.write(response.getOutputStream()).build()) {
            WriteSheet sheet = EasyExcel.writerSheet(0, "分析结果").head(ResultExportVO.class).build();
            streamExportRows(taskId, filtered, filterSentiment, filterKeyword, filterNeedReview,
                    filterReviewed, filterMinConfidence, filterMaxConfidence, total,
                    records -> excelWriter.write(assembleExportRows(records), sheet));
            // 统计摘要工作表：情感占比 + 热点词摘要（FR-BIZ-26）
            writeSummarySheet(excelWriter, taskId, taskName);
        }
    }

    /**
     * 导出 CSV：UTF-8 BOM + 与 Excel 一致的列顺序。
     *
     * @param taskId           任务编号
     * @param filtered         是否按筛选导出
     * @param filterSentiment  情感筛选
     * @param filterKeyword    关键词筛选
     * @param filterNeedReview 复核状态筛选
     * @param total            预计总条数
     * @param response         HTTP 响应
     * @throws IOException 写出失败
     */
    private void writeCsvRows(Long taskId, boolean filtered, String filterSentiment,
                              String filterKeyword, Integer filterNeedReview, Integer filterReviewed,
                              BigDecimal filterMinConfidence, BigDecimal filterMaxConfidence,
                              Long total, HttpServletResponse response) throws IOException {
        try (PrintWriter writer = new PrintWriter(
                new OutputStreamWriter(response.getOutputStream(), StandardCharsets.UTF_8))) {
            // BOM 让 Excel 直接双击打开时按 UTF-8 解析，避免中文乱码
            writer.write('\uFEFF');
            writer.print("评论编号,评论内容,情感标签,置信度,关键词,是否待人工复核,是否人工复核,是否改判,模型原判定,推理耗时(ms),分析时间\r\n");
            streamExportRows(taskId, filtered, filterSentiment, filterKeyword, filterNeedReview,
                    filterReviewed, filterMinConfidence, filterMaxConfidence, total,
                    records -> assembleExportRows(records).forEach(row -> writer.print(csvLine(row))));
            writer.flush();
        }
    }

    /**
     * 拼装一行 CSV，按需加引号并转义内部双引号。
     *
     * @param row 导出行
     * @return CSV 行文本（含换行）
     */
    private String csvLine(ResultExportVO row) {
        StringBuilder builder = new StringBuilder(160);
        builder.append(csvCell(row.getCommentId())).append(',')
                .append(csvCell(row.getContent())).append(',')
                .append(csvCell(row.getSentimentLabel())).append(',')
                .append(csvCell(row.getConfidence() == null ? null : row.getConfidence().toPlainString())).append(',')
                .append(csvCell(row.getKeywords())).append(',')
                .append(csvCell(row.getReviewLabel())).append(',')
                .append(csvCell(row.getReviewedLabel())).append(',')
                .append(csvCell(row.getCorrectedLabel())).append(',')
                .append(csvCell(row.getOriginalSentimentLabel())).append(',')
                .append(csvCell(row.getInferTimeMs())).append(',')
                .append(csvCell(formatTime(row.getCreateTime())))
                .append("\r\n");
        return builder.toString();
    }

    /**
     * CSV 单元格转义。
     *
     * @param value 原始值
     * @return 转义后的单元格
     */
    private String csvCell(Object value) {
        if (value == null) {
            return "";
        }
        String text = String.valueOf(value);
        boolean needQuote = text.indexOf('"') >= 0 || text.indexOf(',') >= 0
                || text.indexOf('\n') >= 0 || text.indexOf('\r') >= 0;
        if (!needQuote) {
            return text;
        }
        return "\"" + text.replace("\"", "\"\"") + "\"";
    }

    /**
     * 导出 JSON 数组，字段与 CSV 列一一对应。
     *
     * @param taskId           任务编号
     * @param filtered         是否按筛选导出
     * @param filterSentiment  情感筛选
     * @param filterKeyword    关键词筛选
     * @param filterNeedReview 复核状态筛选
     * @param total            预计总条数
     * @param response         HTTP 响应
     * @throws IOException 写出失败
     */
    private void writeJsonRows(Long taskId, boolean filtered, String filterSentiment,
                               String filterKeyword, Integer filterNeedReview, Integer filterReviewed,
                               BigDecimal filterMinConfidence, BigDecimal filterMaxConfidence,
                               Long total, HttpServletResponse response) throws IOException {
        try (JsonGenerator generator = objectMapper.getFactory()
                .createGenerator(response.getOutputStream(), JsonEncoding.UTF8)) {
            generator.writeStartArray();
            streamExportRows(taskId, filtered, filterSentiment, filterKeyword, filterNeedReview,
                    filterReviewed, filterMinConfidence, filterMaxConfidence, total,
                    records -> {
                        try {
                            for (ResultExportVO row : assembleExportRows(records)) {
                                writeJsonObject(generator, row);
                            }
                        } catch (IOException e) {
                            throw new UncheckedIOException(e);
                        }
                    });
            generator.writeEndArray();
            generator.flush();
        } catch (UncheckedIOException e) {
            throw e.getCause();
        }
    }

    /**
     * 写单条 JSON 对象。
     *
     * @param generator JSON 生成器
     * @param row       导出行
     * @throws IOException 写出失败
     */
    private void writeJsonObject(JsonGenerator generator, ResultExportVO row) throws IOException {
        generator.writeStartObject();
        generator.writeNumberField("commentId", row.getCommentId() == null ? 0L : row.getCommentId());
        generator.writeStringField("content", row.getContent());
        generator.writeStringField("sentiment", row.getSentimentLabel());
        if (row.getConfidence() == null) {
            generator.writeNullField("confidence");
        } else {
            generator.writeNumberField("confidence", row.getConfidence());
        }
        generator.writeStringField("keywords", row.getKeywords());
        generator.writeBooleanField("needReview", "是".equals(row.getReviewLabel()));
        generator.writeBooleanField("reviewed", "是".equals(row.getReviewedLabel()));
        generator.writeBooleanField("corrected", "是".equals(row.getCorrectedLabel()));
        generator.writeStringField("originalSentiment",
                "—".equals(row.getOriginalSentimentLabel()) ? null : row.getOriginalSentimentLabel());
        if (row.getInferTimeMs() == null) {
            generator.writeNullField("inferTimeMs");
        } else {
            generator.writeNumberField("inferTimeMs", row.getInferTimeMs());
        }
        generator.writeStringField("createTime", formatTime(row.getCreateTime()));
        generator.writeEndObject();
    }

    /**
     * 格式化导出时间。
     *
     * @param time 时间
     * @return yyyy-MM-dd HH:mm:ss 文本，空值返回空串
     */
    private String formatTime(LocalDateTime time) {
        return time == null ? "" : time.format(EXPORT_TIME_FORMATTER);
    }

    /**
     * 写入「统计摘要」工作表：情感占比与热点词统计摘要（FR-BIZ-26）。
     *
     * @param excelWriter Excel 写出器
     * @param taskId      任务编号
     * @param taskName    任务名称
     */
    private void writeSummarySheet(ExcelWriter excelWriter, Long taskId, String taskName) {
        List<SummaryRowVO> rows = new ArrayList<>();

        TaskStatistics stats = taskStatisticsMapper.selectOne(new LambdaQueryWrapper<TaskStatistics>()
                .eq(TaskStatistics::getTaskId, taskId));
        if (stats == null) {
            stats = analysisResultMapper.selectSummary(taskId);
        }
        if (stats == null) {
            stats = new TaskStatistics();
        }
        long total = toLong(stats.getTotalCount());
        long positive = toLong(stats.getPositiveCount());
        long negative = toLong(stats.getNegativeCount());
        long neutral = toLong(stats.getNeutralCount());

        rows.add(row("任务名称", taskName));
        rows.add(row("统计条数", String.valueOf(total)));
        rows.add(row("正面条数及占比", positive + "（" + percentText(positive, total) + "）"));
        rows.add(row("负面条数及占比", negative + "（" + percentText(negative, total) + "）"));
        rows.add(row("中性条数及占比", neutral + "（" + percentText(neutral, total) + "）"));
        rows.add(row("待人工复核条数", String.valueOf(toLong(stats.getReviewCount()))));
        rows.add(row("平均置信度", stats.getAvgConfidence() == null
                ? "—" : stats.getAvgConfidence().toPlainString()));
        rows.add(row("推理异常条数", String.valueOf(stats.getErrorCount() == null
                ? 0 : stats.getErrorCount())));
        rows.add(row("热点词 TOP " + MAX_KEYWORD_TOP_N, ""));
        rows.add(row("关键词", "权重", "词频"));

        List<KeywordStatistics> topKeywords = keywordStatisticsMapper.selectList(
                new LambdaQueryWrapper<KeywordStatistics>()
                        .eq(KeywordStatistics::getTaskId, taskId)
                        .eq(KeywordStatistics::getSentiment, SENTIMENT_ALL)
                        .orderByDesc(KeywordStatistics::getWeight)
                        .last("LIMIT " + MAX_KEYWORD_TOP_N));
        for (KeywordStatistics keyword : topKeywords) {
            rows.add(row(keyword.getWord(),
                    keyword.getWeight() == null ? "" : keyword.getWeight().toPlainString(),
                    String.valueOf(keyword.getWordCount() == null ? 0 : keyword.getWordCount())));
        }

        WriteSheet summarySheet = EasyExcel.writerSheet(1, "统计摘要").head(SummaryRowVO.class).build();
        excelWriter.write(rows, summarySheet);
    }

    /**
     * 组装统计摘要行（两列）。
     *
     * @param item  项目
     * @param value 数值
     * @return 摘要行
     */
    private SummaryRowVO row(String item, String value) {
        return row(item, value, null);
    }

    /**
     * 组装统计摘要行（三列）。
     *
     * @param item  项目
     * @param value 数值
     * @param extra 备注
     * @return 摘要行
     */
    private SummaryRowVO row(String item, String value, String extra) {
        SummaryRowVO vo = new SummaryRowVO();
        vo.setItem(item);
        vo.setValue(value);
        vo.setExtra(extra);
        return vo;
    }

    /**
     * 计算占比文案（保留两位小数百分比）。
     *
     * @param part  分子
     * @param total 分母
     * @return 百分比文案，分母为 0 时返回 0%
     */
    private String percentText(long part, long total) {
        if (total <= 0) {
            return "0%";
        }
        return BigDecimal.valueOf(part)
                .multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(total), 2, RoundingMode.HALF_UP)
                .toPlainString() + "%";
    }

    /**
     * 校验任务存在且未被逻辑删除。
     *
     * @param taskId 任务编号
     * @return 任务实体
     */
    private AnalysisTask requireTask(Long taskId) {
        AnalysisTask task = analysisTaskMapper.selectById(taskId);
        if (task == null) {
            throw new BizException(ResultCode.TASK_NOT_FOUND);
        }
        return task;
    }

    /**
     * 将结果实体转换为明细视图，并回查评论原文。
     *
     * @param records 结果实体列表
     * @return 明细视图列表
     */
    private List<ResultVO> assembleResultVOs(List<AnalysisResult> records) {
        if (records == null || records.isEmpty()) {
            return Collections.emptyList();
        }
        Map<Long, String> contentMap = loadCommentContents(records);
        List<ResultVO> list = new ArrayList<>(records.size());
        for (AnalysisResult result : records) {
            ResultVO vo = new ResultVO();
            BeanUtils.copyProperties(result, vo);
            vo.setContent(contentMap.get(result.getCommentId()));
            list.add(vo);
        }
        return list;
    }

    /**
     * 将结果实体转换为导出模型。
     *
     * @param records 结果实体列表
     * @return 导出模型列表
     */
    private List<ResultExportVO> assembleExportRows(List<AnalysisResult> records) {
        Map<Long, String> contentMap = loadCommentContents(records);
        List<ResultExportVO> rows = new ArrayList<>(records.size());
        for (AnalysisResult result : records) {
            ResultExportVO vo = new ResultExportVO();
            vo.setCommentId(result.getCommentId());
            vo.setContent(contentMap.get(result.getCommentId()));
            vo.setSentimentLabel(sentimentLabel(result.getSentiment()));
            vo.setConfidence(result.getConfidence());
            vo.setKeywords(result.getKeywords());
            vo.setReviewLabel(result.getNeedReview() != null && result.getNeedReview() == NEED_REVIEW_YES ? "是" : "否");
            vo.setReviewedLabel(result.getReviewed() != null && result.getReviewed() == 1 ? "是" : "否");
            boolean corrected = StringUtils.hasText(result.getOriginalSentiment());
            vo.setCorrectedLabel(corrected ? "是" : "否");
            vo.setOriginalSentimentLabel(corrected
                    ? sentimentLabel(result.getOriginalSentiment()) : "—");
            vo.setInferTimeMs(result.getInferTimeMs());
            vo.setCreateTime(result.getCreateTime());
            rows.add(vo);
        }
        return rows;
    }

    /**
     * 按评论编号批量回查评论原文。
     *
     * @param records 结果实体列表
     * @return 评论编号 → 评论原文
     */
    private Map<Long, String> loadCommentContents(List<AnalysisResult> records) {
        List<Long> commentIds = records.stream()
                .map(AnalysisResult::getCommentId)
                .filter(Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());
        if (commentIds.isEmpty()) {
            return Collections.emptyMap();
        }
        List<CommentData> comments = commentDataMapper.selectBatchIds(commentIds);
        Map<Long, String> contentMap = new HashMap<>(comments.size());
        for (CommentData comment : comments) {
            contentMap.put(comment.getCommentId(), comment.getContent());
        }
        return contentMap;
    }

    /**
     * 写入 Excel 下载响应头。
     *
     * @param response HTTP 响应
     * @param taskId   任务编号
     * @param taskName 任务名称
     */
    private void writeExportHeader(HttpServletResponse response, Long taskId,
                                   String taskName, String format) {
        String rawName = "分析结果_" + (StringUtils.hasText(taskName) ? taskName : String.valueOf(taskId))
                + "_" + LocalDateTime.now().format(FILE_TIME_FORMATTER) + "." + format;
        try {
            String encodedName = URLEncoder.encode(rawName, "UTF-8").replaceAll("\\+", "%20");
            if (EXPORT_CSV.equals(format)) {
                response.setContentType("text/csv");
            } else if (EXPORT_JSON.equals(format)) {
                response.setContentType("application/json");
            } else {
                response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
            }
            response.setCharacterEncoding("UTF-8");
            response.setHeader("Content-Disposition", "attachment;filename*=utf-8''" + encodedName);
        } catch (UnsupportedEncodingException e) {
            // UTF-8 为 JDK 必备字符集，正常不会触发
            throw new BizException(ResultCode.EXPORT_FAILED);
        }
    }

    /**
     * 情感标签转中文展示文案。
     *
     * @param sentiment 情感标签编码
     * @return 中文标签
     */
    private String sentimentLabel(String sentiment) {
        if (SENTIMENT_POSITIVE.equals(sentiment)) {
            return "正面";
        }
        if (SENTIMENT_NEGATIVE.equals(sentiment)) {
            return "负面";
        }
        if (SENTIMENT_NEUTRAL.equals(sentiment)) {
            return "中性";
        }
        return sentiment;
    }

    /**
     * 计算占比，保留四位小数。
     *
     * @param part  分子
     * @param total 分母
     * @return 占比，分母为 0 时返回 0
     */
    private BigDecimal ratio(long part, long total) {
        if (total <= 0) {
            return BigDecimal.ZERO;
        }
        return BigDecimal.valueOf(part).divide(BigDecimal.valueOf(total), 4, RoundingMode.HALF_UP);
    }

    /**
     * 将聚合查询结果安全转换为 long。
     *
     * @param value 聚合值
     * @return long 值，为空时返回 0
     */
    private long toLong(Object value) {
        if (value == null) {
            return 0L;
        }
        return value instanceof Number ? ((Number) value).longValue() : Long.parseLong(value.toString());
    }

    /**
     * 归一化页码。
     *
     * @param pageNum 原始页码
     * @return 合法页码，最小为 1
     */
    private int normalizePageNum(Integer pageNum) {
        return (pageNum == null || pageNum < 1) ? 1 : pageNum;
    }

    /**
     * 归一化每页条数。
     *
     * @param pageSize 原始每页条数
     * @return 合法每页条数，默认 10，上限 200
     */
    private int normalizePageSize(Integer pageSize) {
        if (pageSize == null || pageSize < 1) {
            return DEFAULT_PAGE_SIZE;
        }
        return Math.min(pageSize, MAX_PAGE_SIZE);
    }
}
