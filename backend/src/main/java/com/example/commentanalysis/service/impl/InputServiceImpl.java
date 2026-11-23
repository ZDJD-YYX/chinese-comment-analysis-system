package com.example.commentanalysis.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.dto.ContentInputDTO;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.entity.CommentData;
import com.example.commentanalysis.entity.SysUser;
import com.example.commentanalysis.input.InputTextProcessor;
import com.example.commentanalysis.input.WebPageContent;
import com.example.commentanalysis.input.WebPageReader;
import com.example.commentanalysis.mapper.AnalysisTaskMapper;
import com.example.commentanalysis.mapper.CommentDataMapper;
import com.example.commentanalysis.mapper.SysUserMapper;
import com.example.commentanalysis.service.InputService;
import com.example.commentanalysis.service.PendingPageStore;
import com.example.commentanalysis.vo.InputReportVO;
import com.example.commentanalysis.vo.PagePreviewVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 智能输入业务服务实现。
 *
 * <p>流程：自动识别输入类型 → 网页抓取并提取正文 / 纯文本直接归一化 → 按句切分为评论 →
 * 创建分析任务 → 评论分批入库 → 返回接收回执。批次提交后没有整体事务，
 * 失败时显式清理半成品任务，避免任务列表出现空任务。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class InputServiceImpl implements InputService {

    /** 评论批量入库分片大小 */
    private static final int INSERT_BATCH_SIZE = 1000;

    /** 任务初始状态：待执行 */
    private static final String STATUS_PENDING = "PENDING";

    /** analysis_task.task_name 字段长度上限 */
    private static final int TASK_NAME_MAX_LENGTH = 100;

    /** analysis_task.file_name 字段长度上限 */
    private static final int FILE_NAME_MAX_LENGTH = 255;

    /** 纯文本任务名中展示的内容片段长度 */
    private static final int TEXT_TITLE_LENGTH = 24;

    /** 预览弹窗中展示的正文片段长度 */
    private static final int EXCERPT_LENGTH = 400;

    /** 正文短于该长度时提示用户重点确认 */
    private static final int MIN_EXPECTED_LENGTH = 160;

    /** 链接密度超过该值时提示用户重点确认 */
    private static final double MAX_LINK_DENSITY = 0.5D;

    private final AnalysisTaskMapper analysisTaskMapper;

    private final CommentDataMapper commentDataMapper;

    private final SysUserMapper sysUserMapper;

    private final WebPageReader webPageReader;

    private final PendingPageStore pendingPageStore;

    /** 单条评论最大字符数，与文件导入保持一致 */
    @Value("${app.inference.max-text-length:512}")
    private int maxTextLength;

    /** 推理批量大小快照，写入任务表 */
    @Value("${app.inference.batch-size:32}")
    private int batchSize;

    /** 默认模型版本号 */
    @Value("${app.model.version:bert-zh-sentiment-v1}")
    private String modelVersion;

    /** 单次输入字符上限 */
    @Value("${app.input.max-input-chars:500000}")
    private int maxInputChars;

    @Override
    public InputReportVO analyze(ContentInputDTO dto) {
        long startedAt = System.currentTimeMillis();
        String raw = dto == null || dto.getContent() == null ? "" : dto.getContent();
        if (!StringUtils.hasText(raw)) {
            throw new BizException(ResultCode.BAD_REQUEST, "请输入要分析的评论内容或网页链接");
        }
        if (raw.length() > maxInputChars) {
            throw new BizException(ResultCode.INPUT_CONTENT_TOO_LARGE);
        }

        InputTextProcessor.Detected detected = InputTextProcessor.detect(raw);
        if (detected.getKind() == InputTextProcessor.InputKind.WEB_PAGE) {
            WebPageContent page = webPageReader.fetch(detected.getUrl());
            if (!StringUtils.hasText(page.getText())) {
                throw new BizException(ResultCode.INPUT_CONTENT_EMPTY);
            }
            return createWebTask(page, startedAt);
        }

        int inputChars = raw.length();
        List<String> comments = InputTextProcessor.segment(raw, maxTextLength);
        if (comments.isEmpty()) {
            throw new BizException(ResultCode.NO_VALID_COMMENT, "未识别到可分析的文本内容");
        }
        String taskName = buildTextTaskName(raw);
        String fileName = "粘贴文本.txt";
        long fileSize = raw.getBytes(StandardCharsets.UTF_8).length;

        Long userId = resolveUserId();
        AnalysisTask task = createTask(taskName, fileName, fileSize, userId, comments.size());
        try {
            saveComments(task.getTaskId(), comments);
        } catch (RuntimeException e) {
            cleanupAfterFailure(task.getTaskId(), e);
            throw e;
        }

        long elapsed = System.currentTimeMillis() - startedAt;
        log.info("智能输入解析完成：taskId={}, 类型={}, 正文字符={}, 评论条数={}, 耗时={}ms",
                task.getTaskId(), detected.getKind(), inputChars, comments.size(), elapsed);
        return buildReport(task, false, null, null, inputChars, comments.size(), elapsed);
    }

    @Override
    public PagePreviewVO previewPage(ContentInputDTO dto) {
        String raw = dto == null || dto.getContent() == null ? "" : dto.getContent();
        if (!StringUtils.hasText(raw)) {
            throw new BizException(ResultCode.BAD_REQUEST, "请输入网页链接");
        }
        if (raw.length() > maxInputChars) {
            throw new BizException(ResultCode.INPUT_CONTENT_TOO_LARGE);
        }
        InputTextProcessor.Detected detected = InputTextProcessor.detect(raw);
        if (detected.getKind() != InputTextProcessor.InputKind.WEB_PAGE) {
            throw new BizException(ResultCode.BAD_REQUEST, "正文预览仅适用于网页链接");
        }

        WebPageContent page = webPageReader.fetch(detected.getUrl());
        if (!StringUtils.hasText(page.getText())) {
            throw new BizException(ResultCode.INPUT_CONTENT_EMPTY);
        }
        List<String> comments = InputTextProcessor.segment(page.getText(), maxTextLength);
        if (comments.isEmpty()) {
            throw new BizException(ResultCode.INPUT_CONTENT_EMPTY);
        }

        String token = pendingPageStore.save(page);
        PagePreviewVO vo = new PagePreviewVO();
        vo.setToken(token);
        vo.setUrl(page.getUrl());
        vo.setTitle(page.getTitle());
        vo.setInputChars(page.getText().length());
        vo.setParagraphCount(page.getParagraphCount());
        vo.setCommentCount(comments.size());
        vo.setLinkDensity(round(page.getLinkDensity()));
        vo.setExcerpt(buildExcerpt(page.getText()));
        boolean suspect = WebPageReader.isSuspect(page);
        vo.setSuspect(suspect);
        vo.setWarning(suspect ? buildWarning(page) : null);
        log.info("网页正文预览：url={}, 标题={}, 正文字符={}, 段落={}, 链接密度={}, 可疑={}",
                page.getUrl(), page.getTitle(), page.getText().length(),
                page.getParagraphCount(), vo.getLinkDensity(), suspect);
        return vo;
    }

    @Override
    public InputReportVO confirmPage(String token) {
        long startedAt = System.currentTimeMillis();
        WebPageContent page = pendingPageStore.take(token);
        if (page == null || !StringUtils.hasText(page.getText())) {
            throw new BizException(ResultCode.INPUT_CONTENT_EMPTY);
        }
        return createWebTask(page, startedAt);
    }

    /**
     * 按已抓取的网页正文创建分析任务。
     *
     * @param page      网页抓取结果
     * @param startedAt 流程开始时间（毫秒）
     * @return 接收回执
     */
    private InputReportVO createWebTask(WebPageContent page, long startedAt) {
        List<String> comments = InputTextProcessor.segment(page.getText(), maxTextLength);
        if (comments.isEmpty()) {
            throw new BizException(ResultCode.INPUT_CONTENT_EMPTY);
        }
        String taskName = buildWebTaskName(page);
        String fileName = page.getUrl();
        long fileSize = page.getText().getBytes(StandardCharsets.UTF_8).length;

        Long userId = resolveUserId();
        AnalysisTask task = createTask(taskName, fileName, fileSize, userId, comments.size());
        try {
            saveComments(task.getTaskId(), comments);
        } catch (RuntimeException e) {
            cleanupAfterFailure(task.getTaskId(), e);
            throw e;
        }

        long elapsed = System.currentTimeMillis() - startedAt;
        log.info("网页正文已建任务：taskId={}, 正文字符={}, 评论条数={}, 耗时={}ms",
                task.getTaskId(), page.getText().length(), comments.size(), elapsed);
        return buildReport(task, true, page.getTitle(), page.getUrl(),
                page.getText().length(), comments.size(), elapsed);
    }

    /**
     * 截取正文开头片段，供预览弹窗展示。
     *
     * @param text 正文
     * @return 前若干字符
     */
    private String buildExcerpt(String text) {
        String flattened = text.replace("\n", " ");
        int limit = Math.min(flattened.length(), EXCERPT_LENGTH);
        return limit >= flattened.length() ? flattened : flattened.substring(0, limit) + "…";
    }

    /**
     * 生成可疑原因提示。
     *
     * @param page 抓取结果
     * @return 提示文案
     */
    private String buildWarning(WebPageContent page) {
        if (page.getText().length() < MIN_EXPECTED_LENGTH) {
            return "抽取到的正文很短，页面可能是动态渲染或需要登录，建议先确认下方内容";
        }
        if (page.getLinkDensity() > MAX_LINK_DENSITY) {
            return "链接占比过高，可能抽到了导航或列表页，建议确认后改用文本粘贴";
        }
        return "未识别到段落结构，可能不是正文主体，建议确认下方内容";
    }

    /**
     * 保留四位小数，避免前端的浮点展示过长。
     *
     * @param value 原始值
     * @return 保留四位小数的值
     */
    private double round(double value) {
        return Math.round(value * 10000D) / 10000D;
    }

    /**
     * 批量写入评论。
     *
     * @param taskId   任务编号
     * @param comments 评论文本
     */
    private void saveComments(Long taskId, List<String> comments) {
        List<CommentData> pending = new ArrayList<>(INSERT_BATCH_SIZE);
        int rowNo = 0;
        for (String content : comments) {
            CommentData comment = new CommentData();
            comment.setTaskId(taskId);
            comment.setContent(content);
            comment.setRowNo(++rowNo);
            comment.setCreateTime(LocalDateTime.now());
            pending.add(comment);
            if (pending.size() >= INSERT_BATCH_SIZE) {
                commentDataMapper.insertBatch(pending);
                pending.clear();
            }
        }
        if (!pending.isEmpty()) {
            commentDataMapper.insertBatch(pending);
        }
    }

    /**
     * 创建待执行的分析任务。
     *
     * @param taskName   任务名称
     * @param fileName   源内容名称（网页地址或「粘贴文本.txt」）
     * @param fileSize   正文字节数
     * @param userId     创建人
     * @param totalCount 评论条数
     * @return 已持久化的任务
     */
    private AnalysisTask createTask(String taskName, String fileName, long fileSize,
                                    Long userId, int totalCount) {
        LocalDateTime now = LocalDateTime.now();
        AnalysisTask task = new AnalysisTask();
        task.setTaskName(truncate(taskName, TASK_NAME_MAX_LENGTH));
        task.setFileName(truncate(fileName, FILE_NAME_MAX_LENGTH));
        task.setFileSize(fileSize);
        task.setUserId(userId);
        task.setModelVersion(modelVersion);
        task.setTotalCount(totalCount);
        task.setProcessedCount(0);
        task.setErrorCount(0);
        task.setBatchSize(batchSize);
        task.setStatus(STATUS_PENDING);
        task.setCreateTime(now);
        task.setUpdateTime(now);
        task.setIsDeleted(0);
        analysisTaskMapper.insert(task);
        return task;
    }

    /**
     * 网页任务名：优先页面标题，缺失时回退域名。
     *
     * @param page 网页内容
     * @return 任务名称
     */
    private String buildWebTaskName(WebPageContent page) {
        String title = page.getTitle();
        if (!StringUtils.hasText(title)) {
            try {
                title = URI.create(page.getUrl()).getHost();
            } catch (IllegalArgumentException e) {
                title = page.getUrl();
            }
        }
        return truncate("网页 · " + title, TASK_NAME_MAX_LENGTH);
    }

    /**
     * 文本任务名：取首行内容片段，便于在任务列表区分。
     *
     * @param raw 原始文本
     * @return 任务名称
     */
    private String buildTextTaskName(String raw) {
        String normalized = InputTextProcessor.normalize(raw);
        String firstLine = normalized.isEmpty() ? "" : normalized.split("\n")[0];
        if (firstLine.length() > TEXT_TITLE_LENGTH) {
            firstLine = firstLine.substring(0, TEXT_TITLE_LENGTH) + "…";
        }
        return truncate("文本 · " + firstLine, TASK_NAME_MAX_LENGTH);
    }

    /**
     * 组装接收回执。
     *
     * @param task         任务
     * @param web          是否为网页来源
     * @param sourceTitle  网页标题
     * @param sourceUrl    网页地址
     * @param inputChars   正文字符数
     * @param commentCount 评论条数
     * @param elapsedMs    处理耗时
     * @return 接收回执
     */
    private InputReportVO buildReport(AnalysisTask task, boolean web,
                                      String sourceTitle, String sourceUrl, int inputChars,
                                      int commentCount, long elapsedMs) {
        InputReportVO report = new InputReportVO();
        report.setTaskId(task.getTaskId());
        report.setTaskName(task.getTaskName());
        report.setSourceType(web ? "WEB_PAGE" : "PLAIN_TEXT");
        report.setSourceTypeLabel(web ? "网页链接" : "纯文本");
        report.setSourceTitle(sourceTitle);
        report.setSourceUrl(sourceUrl);
        report.setInputChars(inputChars);
        report.setCommentCount(commentCount);
        report.setElapsedMs(elapsedMs);
        report.setMessage(web ? "网页正文已接收，分析任务已提交" : "文本内容已接收，分析任务已提交");
        return report;
    }

    /**
     * 解析失败时清理半成品任务（子表通过外键级联删除）。
     *
     * @param taskId 任务编号
     * @param cause  失败原因
     */
    private void cleanupAfterFailure(Long taskId, Throwable cause) {
        try {
            analysisTaskMapper.deletePhysically(taskId);
            log.warn("智能输入入库失败，已清理半成品任务：taskId={}, 原因={}", taskId, cause.getMessage());
        } catch (Exception cleanupError) {
            log.error("清理半成品任务失败：taskId={}", taskId, cleanupError);
        }
    }

    /**
     * 解析任务创建人（单用户模式取首个账号）。
     *
     * @return 用户编号
     */
    private Long resolveUserId() {
        SysUser user = sysUserMapper.selectOne(new LambdaQueryWrapper<SysUser>()
                .orderByAsc(SysUser::getUserId)
                .last("LIMIT 1"));
        if (user == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "系统尚未初始化管理员账号，请先注册后再使用");
        }
        return user.getUserId();
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
}
