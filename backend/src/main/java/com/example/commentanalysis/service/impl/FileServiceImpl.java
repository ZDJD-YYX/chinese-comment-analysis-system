package com.example.commentanalysis.service.impl;

import com.alibaba.excel.EasyExcel;
import com.alibaba.excel.context.AnalysisContext;
import com.alibaba.excel.event.AnalysisEventListener;
import com.alibaba.excel.exception.ExcelAnalysisException;
import com.alibaba.excel.read.builder.ExcelReaderBuilder;
import com.alibaba.excel.support.ExcelTypeEnum;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.entity.CommentData;
import com.example.commentanalysis.entity.SysUser;
import com.example.commentanalysis.mapper.AnalysisTaskMapper;
import com.example.commentanalysis.mapper.CommentDataMapper;
import com.example.commentanalysis.mapper.SysUserMapper;
import com.example.commentanalysis.service.FileService;
import com.example.commentanalysis.service.ImportBackupService;
import com.example.commentanalysis.service.PendingImportStore;
import com.example.commentanalysis.validation.ImportValidator;
import com.example.commentanalysis.validation.ValidationOutcome;
import com.example.commentanalysis.vo.ColumnCandidateVO;
import com.example.commentanalysis.vo.ImportValidationVO;
import com.example.commentanalysis.vo.ParseReportVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/**
 * 文件上传解析业务服务实现。
 *
 * <p>导入前先经过 {@link ImportValidator} 做编码与乱码校验修复，并备份原始文件；
 * 随后按实际格式解析：Excel/CSV 走 EasyExcel 流式监听，TXT/TSV/JSON 走逐行/逐节点解析，
 * 两种入口共用同一套评论列识别、清洗与分批入库逻辑。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FileServiceImpl implements FileService {

    /** 单文件大小上限：50 MB */
    private static final long MAX_FILE_SIZE_BYTES = 50L * 1024 * 1024;

    /** 支持的扩展名（小写） */
    private static final Set<String> SUPPORTED_EXTENSIONS =
            new HashSet<>(Arrays.asList("xlsx", "xls", "csv", "txt", "tsv", "json"));

    /** 评论批量入库分片大小，避免单条 INSERT 过大 */
    private static final int INSERT_BATCH_SIZE = 1000;

    /** 任务初始状态：待执行 */
    private static final String STATUS_PENDING = "PENDING";

    /** analysis_task.task_name 字段长度上限 */
    private static final int TASK_NAME_MAX_LENGTH = 100;

    /** analysis_task.file_name 字段长度上限 */
    private static final int FILE_NAME_MAX_LENGTH = 255;

    /** 表头关键词，用于自动识别评论列（英文关键词需为小写） */
    private static final String[] HEADER_KEYWORDS = {
            "评论", "内容", "文本", "评价", "留言", "comment", "content", "text", "review"
    };

    /**
     * 明确属于标识/元信息的列名关键词。
     *
     * <p>这些列即使包含上面的表头关键词（如「评论编号」含「评论」），也不应被当作评论列，
     * 否则会把编号、时间之类的列送进模型分析。</p>
     */
    private static final String[] NON_COMMENT_KEYWORDS = {
            "编号", "序号", "时间", "日期", "评分", "星级", "分数", "数量", "名称", "用户", "昵称", "账号"
    };

    /** 表头标签的最长字符数：整行都不超过该长度时才认为首行是表头 */
    private static final int MAX_HEADER_CELL_LENGTH = 20;

    /** 表头关键词未命中时，用于按文本长度推断评论列的最大采样行数 */
    private static final int COMMENT_COLUMN_SAMPLE_ROWS = 200;

    /** 评论列候选返回条数上限 */
    private static final int MAX_COLUMN_CANDIDATES = 30;

    /** 时间列表头关键词（英文需为小写） */
    private static final String[] TIME_HEADER_KEYWORDS = {
            "时间", "日期", "time", "date", "发布时间", "评论时间", "创建时间", "发表时间", "timestamp"
    };

    /** 时间列候补解析格式（数值型日期见 parseTime 中的序列号分支） */
    private static final DateTimeFormatter[] TIME_FORMATTERS = {
            DateTimeFormatter.ofPattern("yyyy-M-d H:m:s"),
            DateTimeFormatter.ofPattern("yyyy-M-d H:m"),
            DateTimeFormatter.ofPattern("yyyy-M-d")
    };

    /** 推断出的评论列平均文本长度下限，低于该值说明该列不是可分析的评论文本 */
    private static final int MIN_COMMENT_AVG_LENGTH = 2;

    /** JSON 中常见的评论文本字段名（按优先级） */
    private static final String[] JSON_COMMENT_KEYS = {
            "comment", "content", "text", "review", "评论", "评论内容", "内容", "评价"
    };

    /** 解析报告中的过滤原因：空白行 */
    private static final String REASON_BLANK = "空白行";

    /** 解析报告中的过滤原因：重复行 */
    private static final String REASON_DUPLICATE = "重复行";

    private final AnalysisTaskMapper analysisTaskMapper;

    private final CommentDataMapper commentDataMapper;

    private final SysUserMapper sysUserMapper;

    private final ImportValidator importValidator;

    private final ImportBackupService importBackupService;

    private final PendingImportStore pendingImportStore;

    private final ObjectMapper objectMapper;

    /** 推理批量大小快照，写入任务表 */
    @Value("${app.inference.batch-size:32}")
    private int batchSize;

    /** 单条评论最大字符数，超出部分截断 */
    @Value("${app.inference.max-text-length:512}")
    private int maxTextLength;

    /** 默认模型版本号 */
    @Value("${app.model.version:bert-zh-sentiment-v1}")
    private String modelVersion;

    @Override
    public ParseReportVO uploadAndParse(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BizException(ResultCode.BAD_REQUEST, "上传文件不能为空");
        }
        String fileName = file.getOriginalFilename();
        String extension = extensionOf(fileName);
        if (!SUPPORTED_EXTENSIONS.contains(extension)) {
            throw new BizException(ResultCode.FILE_TYPE_UNSUPPORTED);
        }
        if (file.getSize() > MAX_FILE_SIZE_BYTES) {
            throw new BizException(ResultCode.FILE_TOO_LARGE);
        }

        Long userId = resolveUserId();
        AnalysisTask task = createTask(fileName, file.getSize(), userId);

        // 1. 读取原始字节并做导入校验：编码识别、乱码检测、不可见字符清理、格式纠正
        byte[] originalBytes;
        try {
            originalBytes = file.getBytes();
        } catch (IOException e) {
            cleanupAfterFailure(task.getTaskId(), e);
            throw new BizException(ResultCode.SYSTEM_ERROR, "文件读取失败，请重试");
        }
        ValidationOutcome validation = importValidator.validate(extension, originalBytes);
        if (validation.isBlocking()) {
            cleanupAfterFailure(task.getTaskId(), new BizException(ResultCode.IMPORT_VALIDATION_FAILED));
            throw new BizException(ResultCode.IMPORT_VALIDATION_FAILED,
                    validation.getReport().getSummary());
        }

        // 2. 备份原始文件，便于异常回退与人工核对
        String backupFile = importBackupService.save(task.getTaskId(), fileName, originalBytes);

        try {
            // 3. 按修复后的内容解析；修复后无有效数据时回退原始内容重试一次
            ParseOutcome outcome = parseContent(validation.getActualFormat(),
                    validation.getData(), validation.getCharset(), task.getTaskId(), -1, false);
            if (outcome.needsColumnSelection) {
                // 评论列识别失败：暂存文件并返回候选列，由用户手工指定后重新导入（FR-BIZ-06）
                return buildColumnSelectionReport(task, fileName, file.getSize(), outcome,
                        validation.getReport(), backupFile, (long) originalBytes.length,
                        validation.getData(), validation.getCharset(), validation.getActualFormat());
            }
            if (outcome.validCount == 0 && validation.isRepaired()
                    && validation.getOriginalCharset() != null) {
                ParseOutcome fallback = parseContent(validation.getActualFormat(),
                        validation.getOriginalData(), validation.getOriginalCharset(),
                        task.getTaskId(), -1, false);
                if (fallback.validCount > 0) {
                    outcome = fallback;
                    validation.getReport().setFallbackUsed(true);
                    validation.getReport().getIssues().add(new com.example.commentanalysis.vo.ValidationIssueVO(
                            "自动回退", "WARNING", 0,
                            "修复后未解析到有效评论，已回退使用原始文件重新解析"));
                }
            }
            if (outcome.validCount == 0) {
                throw new BizException(ResultCode.NO_VALID_COMMENT);
            }
            updateTotalCount(task.getTaskId(), outcome.validCount);

            log.info("文件解析入库完成：taskId={}, fileName={}, 实际格式={}, 校验状态={}, 有效评论={}, 过滤={}",
                    task.getTaskId(), fileName, validation.getActualFormat(),
                    validation.getReport().getStatus(), outcome.validCount, outcome.filteredCount);
            return buildReport(task, fileName, file.getSize(), outcome,
                    validation.getReport(), backupFile, (long) originalBytes.length);
        } catch (RuntimeException e) {
            // 分批提交后没有整体事务回滚，失败时显式清理半成品数据
            cleanupAfterFailure(task.getTaskId(), e);
            throw e;
        }
    }

    @Override
    public ParseReportVO confirmColumn(String token, Integer column) {
        if (column == null || column < 0) {
            throw new BizException(ResultCode.BAD_REQUEST, "请选择评论列后再继续导入");
        }
        // 先取出但不移除：选错列时允许在同一令牌上重试，避免用户反复上传大文件
        PendingImportStore.PendingImport pending = pendingImportStore.get(token);
        Long userId = resolveUserId();
        AnalysisTask task = createTask(pending.getFileName(), pending.getFileSize(), userId);
        try {
            ParseOutcome outcome = parseContent(pending.getFormat(), pending.getData(),
                    pending.charset(), task.getTaskId(), column, pending.isHeaderPresent());
            if (outcome.validCount == 0) {
                throw new BizException(ResultCode.NO_VALID_COMMENT,
                        "第 " + (column + 1) + " 列未解析到有效评论，请改选其他列");
            }
            updateTotalCount(task.getTaskId(), outcome.validCount);
            pendingImportStore.remove(token);
            log.info("按人工指定评论列导入完成：taskId={}, commentColumn={}, 有效评论={}, 时间列={}",
                    task.getTaskId(), column, outcome.validCount, outcome.timeColumn);
            return buildReport(task, pending.getFileName(), pending.getFileSize(), outcome,
                    null, pending.getBackupFile(), null);
        } catch (RuntimeException e) {
            cleanupAfterFailure(task.getTaskId(), e);
            throw e;
        }
    }

    /**
     * 组装「需要人工指定评论列」的解析报告，并暂存文件内容。
     *
     * @param task       已创建的半成品任务（随后会被清理）
     * @param fileName   源文件名
     * @param fileSize   源文件大小
     * @param outcome    解析中间结果（含候选列）
     * @param validation 导入校验报告
     * @param backupFile 原始文件备份名
     * @param backupSize 原始文件大小
     * @param data       待解析字节
     * @param charset    文本编码
     * @param format     实际格式
     * @return 需要人工指定列的报告
     */
    private ParseReportVO buildColumnSelectionReport(AnalysisTask task, String fileName, long fileSize,
                                                     ParseOutcome outcome, ImportValidationVO validation,
                                                     String backupFile, Long backupSize,
                                                     byte[] data, Charset charset, String format) {
        String token = pendingImportStore.save(fileName, fileSize, format,
                charset == null ? null : charset.name(), data, true, backupFile);
        // 未产出任何评论，清理半成品任务；备份文件保留，供重新导入时展示
        cleanupAfterFailure(task.getTaskId(), new BizException(ResultCode.COMMENT_COLUMN_UNRECOGNIZED));

        ParseReportVO report = new ParseReportVO();
        report.setFileName(fileName);
        report.setFileSize(fileSize);
        report.setTotalCount(0);
        report.setValidCount(0);
        report.setFilteredCount(0);
        report.setFilterReasons(new LinkedHashMap<>());
        report.setNeedsColumnSelection(true);
        report.setPendingToken(token);
        report.setCandidateColumns(outcome.candidates);
        if (validation != null) {
            validation.setBackupFile(backupFile);
            validation.setBackupSize(backupSize);
        }
        report.setValidation(validation);
        log.warn("评论列自动识别失败，已暂存文件等待人工指定：fileName={}, 候选列数={}",
                fileName, outcome.candidates == null ? 0 : outcome.candidates.size());
        return report;
    }

    /**
     * 按实际格式分发解析。
     *
     * @param format  实际格式：csv / xlsx / xls / txt / tsv / json
     * @param data    待解析字节（文本格式已统一为 UTF-8）
     * @param charset 文本编码，二进制格式为 null
     * @param taskId  任务编号
     * @return 解析统计
     */
    private ParseOutcome parseContent(String format, byte[] data, Charset charset, Long taskId,
                                      int forcedColumn, boolean headerPresent) {
        switch (format) {
            case "xlsx":
                return parseExcel(data, ExcelTypeEnum.XLSX, null, taskId, forcedColumn, headerPresent);
            case "xls":
                return parseExcel(data, ExcelTypeEnum.XLS, null, taskId, forcedColumn, headerPresent);
            case "csv":
                return parseExcel(data, ExcelTypeEnum.CSV, charset, taskId, forcedColumn, headerPresent);
            case "txt":
                return parsePlainLines(data, charset, taskId);
            case "tsv":
                return parseDelimitedText(data, charset, taskId, forcedColumn, headerPresent);
            case "json":
                return parseJson(data, charset, taskId);
            default:
                throw new BizException(ResultCode.FILE_TYPE_UNSUPPORTED);
        }
    }

    /**
     * 使用 EasyExcel 解析 Excel / CSV。
     *
     * @param data    字节内容
     * @param type    文件类型
     * @param charset 字符集，CSV 必填
     * @param taskId  任务编号
     * @return 解析统计
     */
    private ParseOutcome parseExcel(byte[] data, ExcelTypeEnum type,
                                    Charset charset, Long taskId,
                                    int forcedColumn, boolean headerPresent) {
        try (InputStream inputStream = new ByteArrayInputStream(data)) {
            ParseListener listener = forcedColumn >= 0
                    ? new ParseListener(taskId, forcedColumn, headerPresent)
                    : new ParseListener(taskId);
            // headRowNumber(0) 表示不指定表头行，每行以 Map<列序号, 单元格文本> 交给监听器
            ExcelReaderBuilder readerBuilder = EasyExcel.read(inputStream, listener)
                    .excelType(type)
                    .headRowNumber(0);
            if (charset != null) {
                readerBuilder.charset(charset);
            }
            readerBuilder.sheet().doRead();
            return listener.finish();
        } catch (IOException e) {
            log.error("读取文件内容失败：taskId={}", taskId, e);
            throw new BizException(ResultCode.SYSTEM_ERROR, "文件读取失败，请重试");
        } catch (ExcelAnalysisException e) {
            Throwable cause = findCause(e);
            if (cause instanceof BizException) {
                throw (BizException) cause;
            }
            if (cause instanceof DataAccessException) {
                log.error("解析过程中写入数据库失败：taskId={}", taskId, cause);
                throw (DataAccessException) cause;
            }
            log.error("解析文件失败：taskId={}", taskId, e);
            throw new BizException(ResultCode.ENCODING_UNRECOGNIZED);
        }
    }

    /**
     * 解析纯文本（一行一条评论）。
     *
     * @param data    字节内容
     * @param charset 字符集
     * @param taskId  任务编号
     * @return 解析统计
     */
    private ParseOutcome parsePlainLines(byte[] data, Charset charset, Long taskId) {
        ParseListener listener = new ParseListener(taskId, 0);
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new ByteArrayInputStream(data), charset))) {
            String line = reader.readLine();
            // 首行若恰好是「评论内容」这类表头文字则跳过，避免把表头当成一条评论
            if (line != null && isSingleColumnHeader(line)) {
                line = reader.readLine();
            }
            while (line != null) {
                Map<Integer, String> row = new HashMap<>(1);
                row.put(0, line);
                listener.collect(row);
                line = reader.readLine();
            }
        } catch (IOException e) {
            log.error("读取文本文件失败：taskId={}", taskId, e);
            throw new BizException(ResultCode.SYSTEM_ERROR, "文件读取失败，请重试");
        }
        return listener.finish();
    }

    /**
     * 解析制表符分隔文本（TSV），首行按表头识别规则处理。
     *
     * @param data    字节内容
     * @param charset 字符集
     * @param taskId  任务编号
     * @return 解析统计
     */
    private ParseOutcome parseDelimitedText(byte[] data, Charset charset, Long taskId,
                                            int forcedColumn, boolean headerPresent) {
        ParseListener listener = forcedColumn >= 0
                ? new ParseListener(taskId, forcedColumn, headerPresent)
                : new ParseListener(taskId);
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new ByteArrayInputStream(data), charset))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String[] cells = line.split("\t", -1);
                Map<Integer, String> row = new HashMap<>(cells.length);
                for (int i = 0; i < cells.length; i++) {
                    row.put(i, cells[i]);
                }
                listener.collect(row);
            }
        } catch (IOException e) {
            log.error("读取 TSV 文件失败：taskId={}", taskId, e);
            throw new BizException(ResultCode.SYSTEM_ERROR, "文件读取失败，请重试");
        }
        return listener.finish();
    }

    /**
     * 解析 JSON 评论文件。
     *
     * <p>支持「字符串数组」与「对象数组」两种结构；对象数组按常见字段名取评论，
     * 全部缺失时取最长的字符串字段。</p>
     *
     * @param data    字节内容
     * @param charset 字符集
     * @param taskId  任务编号
     * @return 解析统计
     */
    private ParseOutcome parseJson(byte[] data, Charset charset, Long taskId) {
        JsonNode root;
        try {
            root = objectMapper.readTree(new String(data, charset));
        } catch (IOException e) {
            log.warn("JSON 解析失败：taskId={}", taskId, e);
            throw new BizException(ResultCode.BAD_REQUEST, "JSON 解析失败：文件不是合法的 JSON");
        }
        List<String> comments = extractJsonComments(root);
        if (comments.isEmpty()) {
            throw new BizException(ResultCode.NO_VALID_COMMENT,
                    "JSON 中未找到评论文本，支持字段：comment / content / text / review / 评论 / 内容");
        }
        ParseListener listener = new ParseListener(taskId, 0);
        for (String comment : comments) {
            Map<Integer, String> row = new HashMap<>(1);
            row.put(0, comment);
            listener.collect(row);
        }
        return listener.finish();
    }

    /**
     * 从 JSON 根节点提取评论文本列表。
     *
     * @param root 根节点
     * @return 评论文本列表
     */
    private List<String> extractJsonComments(JsonNode root) {
        List<String> comments = new ArrayList<>();
        JsonNode array = root;
        if (root != null && root.isObject()) {
            for (String key : new String[]{"data", "list", "comments", "records", "items"}) {
                JsonNode node = root.get(key);
                if (node != null && node.isArray()) {
                    array = node;
                    break;
                }
            }
        }
        if (array == null || !array.isArray()) {
            return comments;
        }
        for (JsonNode node : array) {
            if (node.isTextual()) {
                comments.add(node.asText());
                continue;
            }
            if (!node.isObject()) {
                continue;
            }
            String text = null;
            for (String key : JSON_COMMENT_KEYS) {
                JsonNode value = node.get(key);
                if (value != null && value.isTextual() && StringUtils.hasText(value.asText())) {
                    text = value.asText();
                    break;
                }
            }
            if (text == null) {
                // 字段名不在约定范围内时，取最长的字符串字段作为评论
                java.util.Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
                while (fields.hasNext()) {
                    Map.Entry<String, JsonNode> entry = fields.next();
                    JsonNode value = entry.getValue();
                    if (value.isTextual() && (text == null || value.asText().length() > text.length())) {
                        text = value.asText();
                    }
                }
            }
            if (text != null) {
                comments.add(text);
            }
        }
        return comments;
    }

    /**
     * 判断单列文本首行是否为表头。
     *
     * <p>单列文件没有其他列可以对比，只能按"整行是否就是一个表头词"来判断，
     * 避免把「内容不错」这类短评论误当表头丢弃。</p>
     *
     * @param line 首行
     * @return true 表示应作为表头跳过
     */
    private boolean isSingleColumnHeader(String line) {
        String text = line == null ? "" : line.trim().toLowerCase();
        if (text.isEmpty() || text.length() > MAX_HEADER_CELL_LENGTH) {
            return false;
        }
        if (text.matches("^(评论|评价|留言|文本|内容)(内容|正文|文本|描述|信息|数据)?$")) {
            return true;
        }
        return text.matches("^(comment|comments|content|text|review|feedback)([ _-].*)?$");
    }

    /**
     * 在异常链中查找业务异常或数据库异常。
     *
     * @param throwable 原始异常
     * @return 首个 BizException / DataAccessException，未找到时返回原始异常
     */
    private Throwable findCause(Throwable throwable) {
        Throwable current = throwable;
        while (current != null) {
            if (current instanceof BizException || current instanceof DataAccessException) {
                return current;
            }
            if (current.getCause() == null || current.getCause() == current) {
                break;
            }
            current = current.getCause();
        }
        return throwable;
    }

    /**
     * 解析失败时清理半成品任务与评论（外键级联删除子表）。
     *
     * @param taskId 任务编号
     * @param cause  失败原因
     */
    private void cleanupAfterFailure(Long taskId, Throwable cause) {
        try {
            analysisTaskMapper.deletePhysically(taskId);
            log.warn("文件解析失败，已清理半成品任务：taskId={}, 原因={}", taskId, cause.getMessage());
        } catch (Exception cleanupError) {
            log.error("清理半成品任务失败：taskId={}", taskId, cleanupError);
        }
    }

    /**
     * 回填任务评论总数。
     *
     * @param taskId     任务编号
     * @param totalCount 有效评论条数
     */
    private void updateTotalCount(Long taskId, int totalCount) {
        AnalysisTask update = new AnalysisTask();
        update.setTaskId(taskId);
        update.setTotalCount(totalCount);
        update.setUpdateTime(LocalDateTime.now());
        analysisTaskMapper.updateById(update);
    }

    /**
     * 在首行中定位评论列序号。
     *
     * <p>一行的多个单元格可能都命中关键词（如「评论编号」「评论内容」），因此不能见到第一个命中就返回：
     * 先排除「编号 / 时间 / 评分 / 名称」这类标识与元信息列，再在剩余候选中按
     * 「命中关键词最长、列名最短」择优，避免把编号列当成评论列。</p>
     *
     * @param headerRow 首行单元格
     * @return 评论列序号；未识别到时返回 -1
     */
    private int detectCommentColumn(Map<Integer, String> headerRow) {
        int bestColumn = -1;
        int bestScore = Integer.MIN_VALUE;
        for (Map.Entry<Integer, String> cell : headerRow.entrySet()) {
            String value = cell.getValue();
            if (!StringUtils.hasText(value)) {
                continue;
            }
            String lowerName = value.trim().toLowerCase();
            int matched = longestMatchedKeyword(lowerName);
            if (matched == 0 || isNonCommentColumn(lowerName)) {
                continue;
            }
            // 命中关键词越长、列名越短，越可能是评论列（「评论内容」优于「用户评论备注」）
            int score = matched * 100 - lowerName.length();
            if (score > bestScore || (score == bestScore && (bestColumn < 0 || cell.getKey() < bestColumn))) {
                bestScore = score;
                bestColumn = cell.getKey();
            }
        }
        return bestColumn;
    }

    /**
     * 取列名中命中的最长表头关键词长度。
     *
     * @param lowerName 小写化后的列名
     * @return 命中的最长关键词长度；未命中返回 0
     */
    private int longestMatchedKeyword(String lowerName) {
        int longest = 0;
        for (String keyword : HEADER_KEYWORDS) {
            if (lowerName.contains(keyword) && keyword.length() > longest) {
                longest = keyword.length();
            }
        }
        return longest;
    }

    /**
     * 判断列名是否属于「标识 / 元信息」列（编号、时间、评分、名称等）。
     *
     * @param lowerName 小写化后的列名
     * @return 属于标识或元信息列时返回 true
     */
    private boolean isNonCommentColumn(String lowerName) {
        for (String keyword : NON_COMMENT_KEYWORDS) {
            if (lowerName.contains(keyword)) {
                return true;
            }
        }
        // 英文 id 类列名：id / xxx_id / commentId
        return lowerName.equals("id") || lowerName.endsWith("_id") || lowerName.endsWith("id");
    }

    /**
     * 在首行中定位评论时间列。
     *
     * <p>时间列只用于趋势图，识别失败不影响主流程；与评论列重合时忽略。</p>
     *
     * @param headerRow     首行单元格
     * @param commentColumn 已确定的评论列
     * @return 时间列序号；未识别到返回 -1
     */
    private int detectTimeColumn(Map<Integer, String> headerRow, int commentColumn) {
        int bestColumn = -1;
        int bestScore = 0;
        for (Map.Entry<Integer, String> cell : headerRow.entrySet()) {
            if (cell.getKey() == commentColumn) {
                continue;
            }
            String value = cell.getValue();
            if (!StringUtils.hasText(value)) {
                continue;
            }
            String lowerName = value.trim().toLowerCase();
            int matched = 0;
            for (String keyword : TIME_HEADER_KEYWORDS) {
                if (lowerName.contains(keyword) && keyword.length() > matched) {
                    matched = keyword.length();
                }
            }
            if (matched > bestScore || (matched == bestScore && matched > 0
                    && (bestColumn < 0 || cell.getKey() < bestColumn))) {
                bestScore = matched;
                bestColumn = cell.getKey();
            }
        }
        return bestColumn;
    }

    /**
     * 解析单元格中的时间文本。
     *
     * <p>支持纯数字时间戳（秒/毫秒）、Excel 日期序列号，以及常见的
     * {@code yyyy-MM-dd[ HH:mm[:ss]]}、{@code yyyy/M/d}、中文「年月日」等写法。</p>
     *
     * @param raw 原始文本
     * @return 解析结果；无法识别时返回 null
     */
    private LocalDateTime parseTime(String raw) {
        if (!StringUtils.hasText(raw)) {
            return null;
        }
        String text = raw.trim();
        if (text.matches("\\d+")) {
            long value = Long.parseLong(text);
            if (text.length() == 13) {
                return LocalDateTime.ofInstant(java.time.Instant.ofEpochMilli(value), ZoneId.systemDefault());
            }
            if (text.length() == 10) {
                return LocalDateTime.ofInstant(java.time.Instant.ofEpochSecond(value), ZoneId.systemDefault());
            }
            // Excel 日期序列号：以 1899-12-30 为基准的天数
            if (value >= 20000 && value <= 60000) {
                return LocalDate.of(1899, 12, 30).plusDays(value).atStartOfDay();
            }
            return null;
        }
        String normalized = text
                .replace('T', ' ')
                .replace('/', '-')
                .replace('年', '-')
                .replace('月', '-')
                .replace("日", "")
                .replaceAll("\\s+", " ")
                .trim();
        for (DateTimeFormatter formatter : TIME_FORMATTERS) {
            try {
                return LocalDateTime.parse(normalized, formatter);
            } catch (DateTimeParseException ignored) {
                // 继续尝试日期格式
            }
            try {
                return LocalDate.parse(normalized, formatter).atStartOfDay();
            } catch (DateTimeParseException ignored) {
                // 继续尝试下一个格式
            }
        }
        return null;
    }

    /**
     * 组装评论列候选列表，供人工指定（FR-BIZ-06）。
     *
     * @param rows       已缓冲的行数据
     * @param startIndex 数据起始行下标（1 表示首行是表头）
     * @return 候选列列表
     */
    private List<ColumnCandidateVO> buildCandidates(List<Map<Integer, String>> rows, int startIndex) {
        List<ColumnCandidateVO> candidates = new ArrayList<>();
        if (rows.isEmpty()) {
            return candidates;
        }
        Map<Integer, String> headerRow = startIndex > 0 ? rows.get(0) : null;
        Set<Integer> columns = new java.util.TreeSet<>();
        for (Map<Integer, String> row : rows) {
            columns.addAll(row.keySet());
        }
        for (Integer column : columns) {
            String sample = null;
            for (int i = startIndex; i < rows.size(); i++) {
                String text = clean(rows.get(i).get(column));
                if (StringUtils.hasText(text)) {
                    sample = text;
                    break;
                }
            }
            String header = headerRow == null ? null : clean(headerRow.get(column));
            if (!StringUtils.hasText(header) && !StringUtils.hasText(sample)) {
                continue;
            }
            ColumnCandidateVO candidate = new ColumnCandidateVO();
            candidate.setIndex(column);
            candidate.setHeader(header);
            candidate.setSample(sample == null ? "" : sample);
            candidate.setSampleLength(sample == null ? 0 : sample.length());
            candidates.add(candidate);
            if (candidates.size() >= MAX_COLUMN_CANDIDATES) {
                break;
            }
        }
        return candidates;
    }

    /**
     * 判断首行是否"像表头"：非空单元格都不超过 {@link #MAX_HEADER_CELL_LENGTH} 个字符，
     * 且至少有两个非空单元格。
     *
     * <p>用于在表头关键词未命中时决定是否走列推断；单元格内容较长时按正文数据行处理，
     * 避免把含"内容""评价"等字样的评论误判为表头。</p>
     *
     * @param row 首行单元格
     * @return 是否像表头
     */
    private boolean looksLikeHeaderRow(Map<Integer, String> row) {
        int nonEmpty = 0;
        for (String cell : row.values()) {
            String text = clean(cell);
            if (!StringUtils.hasText(text)) {
                continue;
            }
            if (text.length() > MAX_HEADER_CELL_LENGTH) {
                return false;
            }
            nonEmpty++;
        }
        return nonEmpty >= 2;
    }

    /**
     * 按各列的平均文本长度推断评论列。
     *
     * <p>评论是自由文本，通常显著长于编号、日期、金额等结构化列，因此取平均长度最大的列；
     * 只有"确实含文字（字母或汉字）、且平均长度不低于 {@link #MIN_COMMENT_AVG_LENGTH}"的列
     * 才会被选中。没有任何列满足条件时返回 -1，由调用方转为「人工指定列」流程（FR-BIZ-06）。</p>
     *
     * @param rows       已缓冲的行数据
     * @param startIndex 数据起始行下标
     * @return 推断出的评论列序号；无法推断时返回 -1
     */
    private int guessCommentColumn(List<Map<Integer, String>> rows, int startIndex) {
        if (startIndex >= rows.size()) {
            // 只有表头没有数据行，无从推断
            return -1;
        }
        // 用 TreeMap 保证按列序号升序遍历，平均长度相同时优先取靠前的列
        // 每列统计：[文本总长度, 非空条数, 含文字的条数]
        Map<Integer, int[]> stats = new TreeMap<>();
        for (int i = startIndex; i < rows.size(); i++) {
            for (Map.Entry<Integer, String> cell : rows.get(i).entrySet()) {
                String text = clean(cell.getValue());
                if (!StringUtils.hasText(text)) {
                    continue;
                }
                int[] stat = stats.computeIfAbsent(cell.getKey(), key -> new int[3]);
                stat[0] += text.length();
                stat[1]++;
                if (containsLetter(text)) {
                    stat[2]++;
                }
            }
        }

        int bestColumn = -1;
        double bestAvg = 0D;
        for (Map.Entry<Integer, int[]> entry : stats.entrySet()) {
            int[] stat = entry.getValue();
            if (stat[2] == 0) {
                continue;
            }
            double avg = stat[0] / (double) stat[1];
            if (avg >= MIN_COMMENT_AVG_LENGTH && avg > bestAvg) {
                bestAvg = avg;
                bestColumn = entry.getKey();
            }
        }
        if (bestColumn < 0) {
            return -1;
        }
        return bestColumn;
    }

    /**
     * 判断文本中是否含字母或汉字。
     *
     * <p>用于排除纯数字、纯符号列（如编号、金额、日期），这些列不可能是评论列。</p>
     *
     * @param text 文本
     * @return 含字母或汉字时返回 true
     */
    private boolean containsLetter(String text) {
        for (int i = 0; i < text.length(); i++) {
            if (Character.isLetter(text.charAt(i))) {
                return true;
            }
        }
        return false;
    }

    /**
     * 文本清洗：全角空格归一、连续空白折叠、去除首尾空白，并按配置截断超长文本。
     *
     * @param raw 原始单元格文本
     * @return 清洗后的文本，无效时返回空串
     */
    private String clean(String raw) {
        if (raw == null) {
            return "";
        }
        String text = raw.replace('\u3000', ' ')
                .replaceAll("\\s+", " ")
                .trim();
        if (text.length() > maxTextLength) {
            text = text.substring(0, maxTextLength);
        }
        return text;
    }

    /**
     * 创建分析任务主记录，初始状态为 PENDING。
     *
     * @param fileName 源文件名称
     * @param fileSize 源文件大小
     * @param userId   创建人编号
     * @return 已持久化的任务实体（含自增主键）
     */
    private AnalysisTask createTask(String fileName, long fileSize, Long userId) {
        LocalDateTime now = LocalDateTime.now();
        AnalysisTask task = new AnalysisTask();
        // 文件名可能超过列宽，入库前按 schema 截断，避免 Data too long 异常
        task.setTaskName(truncate(taskNameOf(fileName), TASK_NAME_MAX_LENGTH));
        task.setFileName(truncate(fileName, FILE_NAME_MAX_LENGTH));
        task.setFileSize(fileSize);
        task.setUserId(userId);
        task.setModelVersion(modelVersion);
        task.setTotalCount(0);
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
     * 解析单用户模式下的任务创建人。
     *
     * @return 管理员用户编号
     */
    private Long resolveUserId() {
        SysUser user = sysUserMapper.selectOne(new LambdaQueryWrapper<SysUser>()
                .orderByAsc(SysUser::getUserId)
                .last("LIMIT 1"));
        if (user == null) {
            throw new BizException(ResultCode.BAD_REQUEST, "系统尚未初始化管理员账号，请先注册后再上传文件");
        }
        return user.getUserId();
    }

    /**
     * 组装解析报告。
     *
     * @param task     任务实体
     * @param fileName 文件名称
     * @param fileSize 文件大小
     * @param outcome  解析结果
     * @return 解析报告视图
     */
    private ParseReportVO buildReport(AnalysisTask task, String fileName, long fileSize,
                                      ParseOutcome outcome, ImportValidationVO validation,
                                      String backupFile, Long backupSize) {
        ParseReportVO report = new ParseReportVO();
        report.setTaskId(task.getTaskId());
        report.setTaskName(task.getTaskName());
        report.setFileName(fileName);
        report.setFileSize(fileSize);
        report.setTotalCount(outcome.totalCount);
        report.setValidCount(outcome.validCount);
        report.setFilteredCount(outcome.filteredCount);
        report.setFilterReasons(outcome.filterReasons);
        report.setCommentColumn(outcome.commentColumn);
        report.setTimeColumn(outcome.timeColumn);
        report.setNeedsColumnSelection(false);
        if (validation != null) {
            validation.setBackupFile(backupFile);
            validation.setBackupSize(backupSize);
        }
        report.setValidation(validation);
        return report;
    }

    /**
     * 提取文件扩展名（小写）。
     *
     * @param fileName 文件名
     * @return 扩展名，无扩展名时返回空串
     */
    private String extensionOf(String fileName) {
        if (fileName == null) {
            return "";
        }
        int index = fileName.lastIndexOf('.');
        return index < 0 ? "" : fileName.substring(index + 1).toLowerCase();
    }

    /**
     * 由文件名生成任务名称（去扩展名）。
     *
     * @param fileName 文件名
     * @return 任务名称
     */
    private String taskNameOf(String fileName) {
        if (fileName == null) {
            return "";
        }
        int index = fileName.lastIndexOf('.');
        return index > 0 ? fileName.substring(0, index) : fileName;
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
     * 流式解析监听器。
     *
     * <p>前 {@link #COMMENT_COLUMN_SAMPLE_ROWS} 行先缓冲，用于识别评论列；
     * 识别完成后立即处理缓冲数据，后续行逐行处理，每 {@link #INSERT_BATCH_SIZE} 条入库一次。</p>
     */
    private class ParseListener extends AnalysisEventListener<Map<Integer, String>> {

        private final Long taskId;

        /** 评论列识别阶段的行缓冲 */
        private final List<Map<Integer, String>> buffer = new ArrayList<>(COMMENT_COLUMN_SAMPLE_ROWS);

        /** 待入库批次 */
        private final List<CommentData> pending = new ArrayList<>(INSERT_BATCH_SIZE);

        private final ParseOutcome outcome = new ParseOutcome();

        /**
         * 已入库文本集合：按清洗后的文本去重（FR-BIZ-08「过滤重复行」）。
         *
         * <p>只保存清洗后的评论正文，重复行不计入 validCount，语义与
         * 《软件需求规格说明书》P1 加工逻辑「去空行、去重复行」保持一致。</p>
         */
        private final Set<String> seenContents = new HashSet<>();

        /** 是否已完成评论列识别 */
        private boolean columnDecided;

        private int commentColumn;

        /** 评论时间列序号，-1 表示未识别到 */
        private int timeColumn = -1;

        private int startIndex;

        /** 指定列导入时是否需要跳过首行表头 */
        private boolean skipHeaderRow;

        /** 当前物理行号（从 1 开始） */
        private int currentRowNo;

        ParseListener(Long taskId) {
            this.taskId = taskId;
        }

        /**
         * 指定评论列构造：用于 TXT / JSON 这类已知只有一列评论内容的格式，
         * 跳过列识别且不把首行当表头。
         *
         * @param taskId       任务编号
         * @param forcedColumn 固定评论列序号
         */
        ParseListener(Long taskId, int forcedColumn) {
            this.taskId = taskId;
            this.columnDecided = true;
            this.commentColumn = forcedColumn;
            this.startIndex = 0;
            this.outcome.commentColumn = forcedColumn;
        }

        /**
         * 人工指定评论列构造：用于自动识别失败后重新导入。
         *
         * @param taskId        任务编号
         * @param forcedColumn  用户选择的评论列序号
         * @param headerPresent 首行是否为表头
         */
        ParseListener(Long taskId, int forcedColumn, boolean headerPresent) {
            this.taskId = taskId;
            this.columnDecided = true;
            this.commentColumn = forcedColumn;
            this.startIndex = headerPresent ? 1 : 0;
            this.skipHeaderRow = headerPresent;
            this.outcome.commentColumn = forcedColumn;
        }

        @Override
        public void invoke(Map<Integer, String> row, AnalysisContext context) {
            collect(row);
        }

        /**
         * 接收一行数据，Excel 监听与自定义文本解析共用。
         *
         * @param row 列序号 → 单元格文本
         */
        void collect(Map<Integer, String> row) {
            currentRowNo++;
            if (skipHeaderRow) {
                // 人工指定列时首行是表头：顺带识别时间列后跳过
                skipHeaderRow = false;
                timeColumn = detectTimeColumn(row, commentColumn);
                outcome.timeColumn = timeColumn >= 0 ? timeColumn : null;
                return;
            }
            if (!columnDecided) {
                buffer.add(row);
                if (buffer.size() >= COMMENT_COLUMN_SAMPLE_ROWS) {
                    decideColumn();
                }
                return;
            }
            processRow(row, currentRowNo);
        }

        @Override
        public void doAfterAllAnalysed(AnalysisContext context) {
            if (!columnDecided) {
                decideColumn();
            }
            flush();
        }

        /**
         * 根据缓冲区首行（及采样数据）确定评论列与数据起始行。
         */
        private void decideColumn() {
            columnDecided = true;
            if (buffer.isEmpty()) {
                throw new BizException(ResultCode.HEADER_MISSING, "文件内容为空，未解析到有效数据");
            }
            Map<Integer, String> firstRow = buffer.get(0);
            int column = detectCommentColumn(firstRow);
            if (column >= 0) {
                // 首行命中表头关键词：首行视为表头
                startIndex = 1;
            } else if (looksLikeHeaderRow(firstRow)) {
                // 首行是短标签组成的表头，但列名不在关键词表内（如「用户反馈」）：
                // 按各列文本长度推断评论列，避免静默把编号、日期等列当成评论列
                column = guessCommentColumn(buffer, 1);
                startIndex = 1;
                if (column < 0) {
                    // 推断失败：返回候选列供人工指定（FR-BIZ-06），本次不写入任何评论
                    outcome.needsColumnSelection = true;
                    outcome.candidates = buildCandidates(buffer, 1);
                    buffer.clear();
                    log.warn("评论列自动识别失败，待人工指定：候选列数={}", outcome.candidates.size());
                    return;
                }
                log.warn("首行未命中评论列表头关键词，已按文本长度推断评论列：commentColumn={}, header={}",
                        column, firstRow.values());
            } else {
                // 首行本身是数据（无表头文件）：取第一列，首行按数据行处理
                column = 0;
                startIndex = 0;
            }
            commentColumn = column;
            outcome.commentColumn = column;
            if (startIndex == 1) {
                // 表头行可用于识别时间列，供情感趋势图使用（FR-BIZ-18）
                timeColumn = detectTimeColumn(firstRow, column);
                outcome.timeColumn = timeColumn >= 0 ? timeColumn : null;
            }

            for (int i = startIndex; i < buffer.size(); i++) {
                processRow(buffer.get(i), i + 1);
            }
            buffer.clear();
        }

        /**
         * 清洗、去重并暂存一行数据，攒满批次后入库。
         *
         * <p>空白行与重复行均计入 filteredCount（过滤原因分布写入解析报告）。</p>
         *
         * @param row   行数据
         * @param rowNo 源文件物理行号
         */
        private void processRow(Map<Integer, String> row, int rowNo) {
            outcome.totalCount++;
            String content = clean(row.get(commentColumn));
            if (!StringUtils.hasText(content)) {
                outcome.filteredCount++;
                outcome.filterReasons.merge(REASON_BLANK, 1, Integer::sum);
                return;
            }
            // 过滤重复行：与已入库/待入库文本完全一致的评论只保留第一条
            if (!seenContents.add(content)) {
                outcome.filteredCount++;
                outcome.filterReasons.merge(REASON_DUPLICATE, 1, Integer::sum);
                return;
            }
            CommentData comment = new CommentData();
            comment.setTaskId(taskId);
            comment.setContent(content);
            comment.setRowNo(rowNo);
            // 时间列存在时解析评论原始时间，供情感趋势图聚合使用
            if (timeColumn >= 0) {
                comment.setCommentTime(parseTime(row.get(timeColumn)));
            }
            comment.setCreateTime(LocalDateTime.now());
            pending.add(comment);
            outcome.validCount++;
            if (pending.size() >= INSERT_BATCH_SIZE) {
                flush();
            }
        }

        /**
         * 批量写入当前批次。
         */
        private void flush() {
            if (pending.isEmpty()) {
                return;
            }
            commentDataMapper.insertBatch(pending);
            pending.clear();
        }

        /**
         * 结束解析，返回统计结果。
         *
         * @return 解析统计
         */
        ParseOutcome finish() {
            if (!columnDecided) {
                decideColumn();
            }
            flush();
            return outcome;
        }
    }

    /**
     * 文件解析的中间结果载体。
     */
    private static class ParseOutcome {

        /** 扫描到的数据行数（不含表头） */
        private int totalCount;

        /** 有效评论条数 */
        private int validCount;

        /** 被过滤条数 */
        private int filteredCount;

        /** 过滤原因分布：原因 → 条数（保持写入顺序，供解析报告展示） */
        private final Map<String, Integer> filterReasons = new LinkedHashMap<>();

        /** 识别到的评论列序号 */
        private int commentColumn;

        /** 识别到的时间列序号，null 表示未识别到 */
        private Integer timeColumn;

        /** 是否需要人工指定评论列 */
        private boolean needsColumnSelection;

        /** 评论列候选，needsColumnSelection 为 true 时填充 */
        private List<ColumnCandidateVO> candidates = new ArrayList<>();
    }
}
