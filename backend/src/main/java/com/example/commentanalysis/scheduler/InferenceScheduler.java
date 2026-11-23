package com.example.commentanalysis.scheduler;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.commentanalysis.ai.KeywordAccumulator;
import com.example.commentanalysis.ai.KeywordResult;
import com.example.commentanalysis.ai.SentimentInferenceService;
import com.example.commentanalysis.ai.SentimentResult;
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
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.RejectedExecutionException;

/**
 * 分析任务调度器。
 *
 * <p>任务创建后异步提交到推理线程池，逐批「读取待处理评论 → 批量推理 → 批量落库 → 更新进度」，
 * 不阻塞上传与查询等交互操作。核心设计点：</p>
 * <ul>
 *     <li><b>续跑不重不漏</b>：每批通过反连接查询「尚无结果的评论」，重试时自动跳过已处理数据，
 *         配合唯一索引 {@code uk_task_comment} 保证幂等；</li>
 *     <li><b>短事务</b>：推理与关键词提取在事务外执行，仅「写结果 + 更新进度」放入单个短事务，
 *         避免上万行数据形成长事务；</li>
 *     <li><b>可终止</b>：终止标志位在批次边界检查，当前批次结束后停止并置为 {@code CANCELED}，
 *         已完成部分结果保留；</li>
 *     <li><b>异常隔离</b>：单条样本异常由推理层兜底并计入 {@code error_count}；
 *         任务级异常兜底置为 {@code FAILED}，不影响其他任务。</li>
 * </ul>
 *
 * @author 闫宇星
 */
@Slf4j
@Component
public class InferenceScheduler {

    /** 任务状态：执行中 */
    private static final String STATUS_RUNNING = "RUNNING";

    /** 任务状态：已完成 */
    private static final String STATUS_SUCCESS = "SUCCESS";

    /** 任务状态：失败 */
    private static final String STATUS_FAILED = "FAILED";

    /** 任务状态：已终止 */
    private static final String STATUS_CANCELED = "CANCELED";

    /** 全局热词的情感维度标记 */
    private static final String SENTIMENT_ALL = "ALL";

    /** 结果批量入库分片大小 */
    private static final int RESULT_INSERT_BATCH_SIZE = 1000;

    /** keyword_statistics.word 字段长度上限 */
    private static final int WORD_MAX_LENGTH = 64;

    /** analysis_result.keywords 字段长度上限 */
    private static final int KEYWORDS_MAX_LENGTH = 255;

    /** analysis_task.error_message 字段长度上限 */
    private static final int ERROR_MESSAGE_MAX_LENGTH = 500;

    private final SentimentInferenceService sentimentInferenceService;

    private final CommentDataMapper commentDataMapper;

    private final AnalysisResultMapper analysisResultMapper;

    private final AnalysisTaskMapper analysisTaskMapper;

    private final KeywordStatisticsMapper keywordStatisticsMapper;

    private final TaskStatisticsMapper taskStatisticsMapper;

    private final InferenceProperties inferenceProperties;

    private final ExecutorService inferenceExecutor;

    private final TransactionTemplate transactionTemplate;

    /** 正在执行的任务编号，防止同一任务被重复提交 */
    private final Set<Long> runningTaskIds = ConcurrentHashMap.newKeySet();

    /** 已请求终止的任务编号，在批次边界生效 */
    private final Set<Long> cancelRequestedTaskIds = ConcurrentHashMap.newKeySet();

    public InferenceScheduler(SentimentInferenceService sentimentInferenceService,
                              CommentDataMapper commentDataMapper,
                              AnalysisResultMapper analysisResultMapper,
                              AnalysisTaskMapper analysisTaskMapper,
                              KeywordStatisticsMapper keywordStatisticsMapper,
                              TaskStatisticsMapper taskStatisticsMapper,
                              InferenceProperties inferenceProperties,
                              @Qualifier("inferenceExecutor") ExecutorService inferenceExecutor,
                              PlatformTransactionManager transactionManager) {
        this.sentimentInferenceService = sentimentInferenceService;
        this.commentDataMapper = commentDataMapper;
        this.analysisResultMapper = analysisResultMapper;
        this.analysisTaskMapper = analysisTaskMapper;
        this.keywordStatisticsMapper = keywordStatisticsMapper;
        this.taskStatisticsMapper = taskStatisticsMapper;
        this.inferenceProperties = inferenceProperties;
        this.inferenceExecutor = inferenceExecutor;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    /**
     * 异步提交任务到推理线程池，立即返回。
     *
     * @param taskId 任务编号
     * @return true 表示提交成功；队列已满返回 false，由调用方提示用户重试
     */
    public boolean submitAsync(Long taskId) {
        if (taskId == null) {
            return false;
        }
        try {
            inferenceExecutor.submit(() -> run(taskId));
            log.info("提交分析任务至推理线程池：taskId={}", taskId);
            return true;
        } catch (RejectedExecutionException e) {
            log.error("推理线程池队列已满，任务提交被拒绝：taskId={}", taskId);
            return false;
        }
    }

    /**
     * 请求终止任务。
     *
     * <p>若任务正在本进程执行，仅置终止标志位，当前批次结束后停止（保证已写入批次的一致性）；
     * 若本进程未在执行（例如重启后残留的 {@code RUNNING}），直接置为已终止，避免状态长期不一致。</p>
     *
     * @param taskId 任务编号
     */
    public void cancel(Long taskId) {
        if (taskId == null) {
            return;
        }
        if (runningTaskIds.contains(taskId)) {
            cancelRequestedTaskIds.add(taskId);
            log.info("已置终止标志位，任务将在当前批次结束后停止：taskId={}", taskId);
            return;
        }
        log.warn("任务不在本进程执行，直接置为已终止：taskId={}", taskId);
        markCanceled(taskId);
    }

    /**
     * 执行分析任务主循环（线程池内运行）。
     *
     * @param taskId 任务编号
     */
    public void run(Long taskId) {
        if (!runningTaskIds.add(taskId)) {
            log.warn("任务已在执行中，忽略重复提交：taskId={}", taskId);
            return;
        }
        try {
            AnalysisTask task = analysisTaskMapper.selectById(taskId);
            if (task == null) {
                log.warn("任务不存在或已删除，跳过推理：taskId={}", taskId);
                return;
            }
            if (STATUS_SUCCESS.equals(task.getStatus())) {
                log.info("任务已完成，跳过重复推理：taskId={}", taskId);
                return;
            }
            // 任务在排队阶段已被终止：不能再被工作线程重新拉起
            if (STATUS_CANCELED.equals(task.getStatus())) {
                log.info("任务已终止，跳过推理：taskId={}", taskId);
                return;
            }
            if (!sentimentInferenceService.isAvailable()) {
                String reason = "情感分析模型不可用，无法执行推理";
                log.error("{}, taskId={}", reason, taskId);
                markFailed(taskId, reason);
                return;
            }

            markRunning(taskId);

            int processed = 0;
            int errors = 0;
            // 批量大小以任务创建时写入 analysis_task.batch_size 的快照为准（表 3-6 字段语义：
            // batch_size 为「创建任务时的批量大小快照」，保证任务重试时切批行为一致）；
            // 快照缺失或非法时回退到当前配置值（1～256）
            int batchSize = normalizeBatchSize(task.getBatchSize());
            // 按情感维度增量累加词频/文档频率，任务收尾时据此计算全局与分情感热词；
            // 只保留聚合结果，不缓存全部评论文本，避免大文件 OOM
            Map<String, KeywordAccumulator> keywordsBySentiment = new HashMap<>(8);
            while (true) {
                List<CommentData> pending = commentDataMapper.selectPendingComments(taskId, batchSize);
                if (pending.isEmpty()) {
                    break;
                }
                BatchOutcome outcome = processBatch(taskId, pending, keywordsBySentiment);
                if (outcome.processed == 0) {
                    // 防御性退出，避免异常情况下进度不前进导致死循环
                    log.warn("本批次未写入任何结果，提前结束任务：taskId={}", taskId);
                    break;
                }
                processed += outcome.processed;
                errors += outcome.errors;

                // 批次边界检查终止标志，保证已提交批次的数据一致性
                if (cancelRequestedTaskIds.contains(taskId)) {
                    log.info("任务收到终止请求，停止后续批次：taskId={}, 已处理={}", taskId, processed);
                    markCanceled(taskId);
                    return;
                }
            }

            finishSuccess(taskId, processed, errors, keywordsBySentiment);
        } catch (Exception e) {
            log.error("分析任务执行失败：taskId={}", taskId, e);
            markFailed(taskId, "分析执行失败：" + e.getMessage());
        } finally {
            runningTaskIds.remove(taskId);
            cancelRequestedTaskIds.remove(taskId);
        }
    }

    /**
     * 处理单批次：推理 → 组装结果 → 单事务内批量写入并累加进度。
     *
     * @param taskId             任务编号
     * @param pending            本批待处理评论（顺序与结果一一对应）
     * @param keywordsBySentiment 情感维度 → 关键词增量累加器
     * @return 本批处理结果
     */
    private BatchOutcome processBatch(Long taskId, List<CommentData> pending,
                                      Map<String, KeywordAccumulator> keywordsBySentiment) {
        List<String> texts = new ArrayList<>(pending.size());
        for (CommentData comment : pending) {
            texts.add(comment.getContent());
        }

        // 推理与关键词提取在事务外执行（耗时长，避免长事务）
        List<SentimentResult> results = sentimentInferenceService.batchInfer(texts);
        List<String> keywords = sentimentInferenceService.extractKeywordsPerText(
                texts, inferenceProperties.getKeywordsPerComment());

        LocalDateTime now = LocalDateTime.now();
        List<AnalysisResult> rows = new ArrayList<>(pending.size());
        int batchErrors = 0;
        for (int i = 0; i < pending.size(); i++) {
            CommentData comment = pending.get(i);
            SentimentResult result = i < results.size() ? results.get(i) : SentimentResult.fallback(true);
            if (result.isError()) {
                batchErrors++;
            }
            AnalysisResult row = new AnalysisResult();
            row.setTaskId(taskId);
            row.setCommentId(comment.getCommentId());
            row.setSentiment(result.getLabel());
            // 置信度按 DECIMAL(6,4) 精度落库
            row.setConfidence(BigDecimal.valueOf(result.getScore()).setScale(4, RoundingMode.HALF_UP));
            row.setKeywords(truncate(i < keywords.size() ? keywords.get(i) : "", KEYWORDS_MAX_LENGTH));
            row.setNeedReview(result.isNeedReview() ? 1 : 0);
            row.setInferTimeMs((int) Math.round(result.getInferTimeMs()));
            row.setCreateTime(now);
            rows.add(row);

            // 同一文本同时计入全局与所属情感维度（仅累加词频，不保留原文）
            keywordsBySentiment.computeIfAbsent(SENTIMENT_ALL,
                    key -> sentimentInferenceService.createKeywordAccumulator()).add(texts.get(i));
            keywordsBySentiment.computeIfAbsent(result.getLabel(),
                    key -> sentimentInferenceService.createKeywordAccumulator()).add(texts.get(i));
        }
        if (rows.isEmpty()) {
            return new BatchOutcome(0, 0);
        }

        // 单批次「写结果 + 累加进度」在同一事务内提交，保证进度与数据量一致；
        // 进度用数据库原子累加，重试续跑时不会抹掉历史进度与异常数。
        final int batchErrorCount = batchErrors;
        transactionTemplate.execute(status -> {
            for (int from = 0; from < rows.size(); from += RESULT_INSERT_BATCH_SIZE) {
                int to = Math.min(from + RESULT_INSERT_BATCH_SIZE, rows.size());
                analysisResultMapper.insertBatch(rows.subList(from, to));
            }
            analysisTaskMapper.incrementProgress(taskId, rows.size(), batchErrorCount, LocalDateTime.now());
            return null;
        });

        log.info("任务批次处理完成：taskId={}, 本批条数={}, 本批异常={}",
                taskId, rows.size(), batchErrorCount);
        return new BatchOutcome(rows.size(), batchErrorCount);
    }

    /**
     * 任务收尾：写入任务级统计与热词，并将任务置为已完成。
     *
     * <p>三步在同一事务内提交，保证「统计结果与任务状态」一致；任一步失败则整体回滚，
     * 任务由外层 catch 置为 {@code FAILED}，已写入的明细结果保留。</p>
     *
     * @param taskId           任务编号
     * @param processed        本次运行处理条数（仅用于日志，任务表由原子累加维护）
     * @param errors           本次运行异常条数（数据库已有累计值时以数据库为准）
     * @param keywordsBySentiment 情感维度 → 关键词累加器
     */
    private void finishSuccess(Long taskId, int processed, int errors,
                               Map<String, KeywordAccumulator> keywordsBySentiment) {
        LocalDateTime now = LocalDateTime.now();
        // 任务级异常数取数据库累计值，避免重试后丢失历史异常计数
        AnalysisTask current = analysisTaskMapper.selectById(taskId);
        int totalErrors = current != null && current.getErrorCount() != null
                ? current.getErrorCount() : errors;
        transactionTemplate.execute(status -> {
            persistStatistics(taskId, totalErrors, now);
            persistKeywords(taskId, keywordsBySentiment, now);

            AnalysisTask update = new AnalysisTask();
            update.setTaskId(taskId);
            update.setStatus(STATUS_SUCCESS);
            update.setFinishTime(now);
            update.setUpdateTime(now);
            analysisTaskMapper.updateById(update);
            return null;
        });
        log.info("分析任务执行完成：taskId={}, 本次处理条数={}, 累计异常条数={}, 热词维度数={}",
                taskId, processed, totalErrors, keywordsBySentiment.size());
    }

    /**
     * 聚合任务整体统计并写入 {@code task_statistics}。
     *
     * <p>统计值由一条聚合 SQL 基于 {@code analysis_result} 全量计算，而不是累加本进程的内存计数，
     * 因此任务经「失败重试续跑」后统计依然覆盖全部结果。</p>
     *
     * @param taskId 任务编号
     * @param errors 累计异常条数（来自任务表口径，分析结果表中无此信息）
     * @param now    统计生成时间
     */
    private void persistStatistics(Long taskId, int errors, LocalDateTime now) {
        TaskStatistics summary = analysisResultMapper.selectSummary(taskId);
        if (summary == null) {
            summary = new TaskStatistics();
        }
        summary.setTaskId(taskId);
        summary.setErrorCount(errors);
        summary.setCreateTime(now);
        summary.setUpdateTime(now);

        // 先清理旧行，规避 uk_task 唯一索引冲突
        taskStatisticsMapper.delete(new LambdaQueryWrapper<TaskStatistics>()
                .eq(TaskStatistics::getTaskId, taskId));
        taskStatisticsMapper.insert(summary);
    }

    /**
     * 计算并写入任务级热词。
     *
     * <p>先按任务清理旧热词，使任务重试时写入幂等（规避 {@code uk_task_word_sentiment} 冲突）。</p>
     *
     * @param taskId              任务编号
     * @param keywordsBySentiment 情感维度 → 关键词累加器
     * @param now                 生成时间
     */
    private void persistKeywords(Long taskId, Map<String, KeywordAccumulator> keywordsBySentiment,
                                 LocalDateTime now) {
        keywordStatisticsMapper.delete(new LambdaQueryWrapper<KeywordStatistics>()
                .eq(KeywordStatistics::getTaskId, taskId));

        int topN = inferenceProperties.getKeywordTopN();
        // 超长词截断后可能与同维度其他词重名，先按 (情感, 词) 去重，
        // 否则会触发 uk_task_word_sentiment 导致整个收尾事务回滚
        Map<String, KeywordStatistics> uniqueRows = new LinkedHashMap<>();
        for (Map.Entry<String, KeywordAccumulator> entry : keywordsBySentiment.entrySet()) {
            for (KeywordResult keyword : entry.getValue().topN(topN)) {
                String word = truncate(keyword.getWord(), WORD_MAX_LENGTH);
                String key = entry.getKey() + '\u0000' + word;
                BigDecimal weight = BigDecimal.valueOf(keyword.getWeight())
                        .setScale(4, RoundingMode.HALF_UP);
                KeywordStatistics existing = uniqueRows.get(key);
                if (existing != null) {
                    // 保留权重更高的一条
                    if (weight.compareTo(existing.getWeight()) > 0) {
                        existing.setWeight(weight);
                        existing.setWordCount(keyword.getWordCount());
                    }
                    continue;
                }
                KeywordStatistics row = new KeywordStatistics();
                row.setTaskId(taskId);
                row.setWord(word);
                row.setWeight(weight);
                row.setWordCount(keyword.getWordCount());
                row.setSentiment(entry.getKey());
                row.setCreateTime(now);
                uniqueRows.put(key, row);
            }
        }
        if (!uniqueRows.isEmpty()) {
            keywordStatisticsMapper.insertBatch(new ArrayList<>(uniqueRows.values()));
        }
    }

    /**
     * 任务置为执行中并记录开始时间。
     *
     * @param taskId 任务编号
     */
    private void markRunning(Long taskId) {
        LocalDateTime now = LocalDateTime.now();
        AnalysisTask update = new AnalysisTask();
        update.setTaskId(taskId);
        update.setStatus(STATUS_RUNNING);
        update.setStartTime(now);
        update.setUpdateTime(now);
        analysisTaskMapper.updateById(update);
        // 重试场景需要清掉上一次的失败原因，避免界面继续展示过期错误
        analysisTaskMapper.clearErrorMessage(taskId, now);
        log.info("分析任务开始执行：taskId={}", taskId);
    }

    /**
     * 任务置为已终止并记录结束时间（已完成部分结果保留）。
     *
     * @param taskId 任务编号
     */
    private void markCanceled(Long taskId) {
        LocalDateTime now = LocalDateTime.now();
        AnalysisTask update = new AnalysisTask();
        update.setTaskId(taskId);
        update.setStatus(STATUS_CANCELED);
        update.setFinishTime(now);
        update.setUpdateTime(now);
        analysisTaskMapper.updateById(update);
        log.info("分析任务已终止：taskId={}", taskId);
    }

    /**
     * 任务置为失败并记录结束时间与失败原因。
     *
     * @param taskId 任务编号
     * @param reason 失败原因，写入 analysis_task.error_message 供界面展示
     */
    private void markFailed(Long taskId, String reason) {
        LocalDateTime now = LocalDateTime.now();
        AnalysisTask update = new AnalysisTask();
        update.setTaskId(taskId);
        update.setStatus(STATUS_FAILED);
        update.setFinishTime(now);
        update.setUpdateTime(now);
        update.setErrorMessage(failureMessage(reason));
        analysisTaskMapper.updateById(update);
        log.warn("分析任务置为失败：taskId={}, 原因={}", taskId, reason);
    }

    /**
     * 归一化失败原因：去掉异常类名前缀噪声并限制在列宽内。
     *
     * @param reason 原始失败原因
     * @return 可展示的失败原因
     */
    private String failureMessage(String reason) {
        String text = reason == null || reason.trim().isEmpty() ? "分析执行失败" : reason.trim();
        return truncate(text, ERROR_MESSAGE_MAX_LENGTH);
    }

    /**
     * 归一化批量大小：优先使用任务快照，非法时回退配置值（1～256，对应表 4-3）。
     *
     * @param snapshot 任务表 batch_size 快照
     * @return 有效的批量大小
     */
    private int normalizeBatchSize(Integer snapshot) {
        int value = (snapshot != null && snapshot >= 1 && snapshot <= 256)
                ? snapshot
                : inferenceProperties.getBatchSize();
        return Math.max(1, Math.min(value, 256));
    }

    /**
     * 按字段长度上限截断字符串。
     *
     * @param value     原始值
     * @param maxLength 长度上限
     * @return 截断后的值
     */
    private String truncate(String value, int maxLength) {
        if (value == null) {
            return "";
        }
        return value.length() > maxLength ? value.substring(0, maxLength) : value;
    }

    /**
     * 单批次处理结果。
     */
    private static class BatchOutcome {

        /** 本批写入条数 */
        private final int processed;

        /** 本批异常条数 */
        private final int errors;

        BatchOutcome(int processed, int errors) {
            this.processed = processed;
            this.errors = errors;
        }
    }
}
