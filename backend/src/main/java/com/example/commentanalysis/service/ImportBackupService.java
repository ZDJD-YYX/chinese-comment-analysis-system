package com.example.commentanalysis.service;

import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * 导入文件备份服务。
 *
 * <p>每次导入都会把原始文件落盘保存，供校验修复异常时回退或人工核对。
 * 备份目录为运行目录下的 {@code data/backup}，文件名带时间戳与任务号，
 * 下载接口只接受本目录内的纯文件名，避免路径穿越。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
public class ImportBackupService {

    /** 备份目录 */
    private static final Path BACKUP_DIR = Paths.get("data", "backup");

    /** 文件名中的时间戳格式 */
    private static final DateTimeFormatter NAME_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");

    /** 备份名最大长度，避免超过文件系统限制 */
    private static final int MAX_NAME_LENGTH = 120;

    /**
     * 保存原始上传文件。
     *
     * @param taskId       任务编号
     * @param originalName 原始文件名
     * @param bytes        原始字节
     * @return 备份文件名（用于报告展示与下载）
     */
    public String save(Long taskId, String originalName, byte[] bytes) {
        String storedName = buildStoredName(taskId, originalName);
        try {
            Files.createDirectories(BACKUP_DIR);
            Files.write(BACKUP_DIR.resolve(storedName), bytes);
            log.info("已备份原始导入文件：taskId={}, file={}", taskId, storedName);
            return storedName;
        } catch (IOException e) {
            // 备份失败不阻断导入，但要在解析报告中体现（backupFile 为空）
            log.warn("备份原始导入文件失败：taskId={}, file={}", taskId, originalName, e);
            return null;
        }
    }

    /**
     * 读取备份文件。
     *
     * @param storedName 备份文件名
     * @return 文件字节
     */
    public byte[] read(String storedName) {
        Path path = resolve(storedName);
        try {
            return Files.readAllBytes(path);
        } catch (IOException e) {
            log.warn("读取备份文件失败：{}", storedName, e);
            throw new BizException(ResultCode.NOT_FOUND, "备份文件不存在或已被清理");
        }
    }

    /**
     * 解析备份文件名对应的路径。
     *
     * @param storedName 备份文件名
     * @return 文件路径
     */
    public Path resolve(String storedName) {
        if (storedName == null || storedName.trim().isEmpty()
                || storedName.contains("/") || storedName.contains("\\")
                || storedName.contains("..")) {
            throw new BizException(ResultCode.BAD_REQUEST, "备份文件名不合法");
        }
        Path path = BACKUP_DIR.resolve(storedName).normalize();
        if (!path.startsWith(BACKUP_DIR.normalize()) || !Files.isRegularFile(path)) {
            throw new BizException(ResultCode.NOT_FOUND, "备份文件不存在或已被清理");
        }
        return path;
    }

    /**
     * 生成备份文件名。
     *
     * @param taskId       任务编号
     * @param originalName 原始文件名
     * @return 存储名
     */
    private String buildStoredName(Long taskId, String originalName) {
        String safeName = sanitize(originalName);
        String name = LocalDateTime.now().format(NAME_FORMATTER)
                + "_" + (taskId == null ? "0" : taskId)
                + "_" + safeName;
        return name.length() > MAX_NAME_LENGTH ? name.substring(0, MAX_NAME_LENGTH) : name;
    }

    /**
     * 清洗文件名中的非法字符并去掉目录部分。
     *
     * @param originalName 原始文件名
     * @return 安全文件名
     */
    private String sanitize(String originalName) {
        if (originalName == null || originalName.trim().isEmpty()) {
            return "upload.bin";
        }
        String name = originalName.replace('\\', '/');
        int slash = name.lastIndexOf('/');
        if (slash >= 0) {
            name = name.substring(slash + 1);
        }
        return name.replaceAll("[\\\\/:*?\"<>|\\x00-\\x1F]", "_");
    }
}