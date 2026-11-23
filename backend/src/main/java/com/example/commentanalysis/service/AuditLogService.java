package com.example.commentanalysis.service;

import com.example.commentanalysis.vo.AuditLogVO;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 操作日志服务。
 *
 * <p>把管理员的关键操作以 JSON 行追加写入 {@code logs/audit.log}，
 * 供系统设置页的「操作记录」展示。相比额外建表，这里选择文件追加：
 * 单用户系统写入量极小，且不引入数据库结构变更。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuditLogService {

    /** 日志文件路径，与 logging.file.name 所在的 logs 目录保持一致 */
    private static final Path LOG_PATH = Paths.get("logs", "audit.log");

    /** 单次最多返回条数 */
    private static final int MAX_LIMIT = 200;

    /** 展示用时间格式 */
    private static final DateTimeFormatter TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    /** 写文件时串行化，避免并发追加产生交错内容 */
    private final Object lock = new Object();

    private final ObjectMapper objectMapper;

    /**
     * 记录一条操作日志。
     *
     * @param username 操作账号，未知时传「未知」
     * @param action   操作类型
     * @param detail   操作详情
     */
    public void record(String username, String action, String detail) {
        AuditLogVO entry = new AuditLogVO();
        entry.setTime(LocalDateTime.now().format(TIME_FORMATTER));
        entry.setUsername(username == null || username.isEmpty() ? "未知" : username);
        entry.setAction(action);
        entry.setDetail(detail);

        String line;
        try {
            line = objectMapper.writeValueAsString(entry);
        } catch (IOException e) {
            log.warn("操作日志序列化失败：{}", action, e);
            return;
        }

        synchronized (lock) {
            try {
                Files.createDirectories(LOG_PATH.getParent());
                Files.write(LOG_PATH, (line + System.lineSeparator()).getBytes(StandardCharsets.UTF_8),
                        StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            } catch (IOException e) {
                // 日志写入失败不应影响主业务
                log.warn("操作日志写入失败：{}", action, e);
            }
        }
    }

    /**
     * 读取最近的操作记录，按时间倒序返回。
     *
     * @param limit 条数上限，1～200
     * @return 操作记录列表，无日志文件时返回空列表
     */
    public List<AuditLogVO> recent(Integer limit) {
        int size = limit == null || limit <= 0 ? 50 : Math.min(limit, MAX_LIMIT);
        if (!Files.exists(LOG_PATH)) {
            return Collections.emptyList();
        }
        List<String> lines;
        try {
            lines = Files.readAllLines(LOG_PATH, StandardCharsets.UTF_8);
        } catch (IOException e) {
            log.warn("操作日志读取失败", e);
            return Collections.emptyList();
        }

        List<AuditLogVO> result = new ArrayList<>();
        for (int i = lines.size() - 1; i >= 0 && result.size() < size; i--) {
            String line = lines.get(i);
            if (line == null || line.trim().isEmpty()) {
                continue;
            }
            try {
                result.add(objectMapper.readValue(line, AuditLogVO.class));
            } catch (IOException e) {
                // 跳过损坏行，不影响其余记录展示
                log.debug("跳过无法解析的操作日志行：{}", line);
            }
        }
        return result;
    }
}