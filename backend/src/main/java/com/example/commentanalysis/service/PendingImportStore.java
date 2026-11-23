package com.example.commentanalysis.service;

import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.nio.charset.Charset;
import java.time.LocalDateTime;
import java.util.Iterator;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 待确认导入文件暂存服务。
 *
 * <p>评论列自动识别失败时，文件内容在内存中暂存并返回令牌，用户在前端选择列序号后
 * 用令牌重新导入，避免要求用户重新上传大文件（对应需求 FR-BIZ-06）。</p>
 *
 * <p>单用户本地场景下只保留少量条目：超过上限淘汰最早的一条，超过有效期自动失效。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
public class PendingImportStore {

    /** 最多同时保留的待确认文件数 */
    private static final int MAX_ENTRIES = 5;

    /** 待确认文件有效期（分钟） */
    private static final long TTL_MINUTES = 30;

    private final Map<String, PendingImport> store = new ConcurrentHashMap<>();

    /**
     * 暂存文件并返回令牌。
     *
     * @param fileName      源文件名
     * @param fileSize      源文件大小
     * @param format        实际解析格式
     * @param charsetName   文本编码名，二进制格式为 null
     * @param data          待解析字节（已做过校验修复）
     * @param headerPresent 首行是否为表头
     * @param backupFile    已保存的原始文件备份名
     * @return 令牌
     */
    public String save(String fileName, long fileSize, String format, String charsetName,
                       byte[] data, boolean headerPresent, String backupFile) {
        evictExpired();
        if (store.size() >= MAX_ENTRIES) {
            // 淘汰最早写入的一条，避免内存被多次失败上传占满
            store.entrySet().stream()
                    .min((a, b) -> a.getValue().getCreatedAt().compareTo(b.getValue().getCreatedAt()))
                    .ifPresent(entry -> store.remove(entry.getKey()));
        }
        String token = UUID.randomUUID().toString().replace("-", "");
        PendingImport pending = new PendingImport();
        pending.setToken(token);
        pending.setFileName(fileName);
        pending.setFileSize(fileSize);
        pending.setFormat(format);
        pending.setCharsetName(charsetName);
        pending.setData(data);
        pending.setHeaderPresent(headerPresent);
        pending.setBackupFile(backupFile);
        pending.setCreatedAt(LocalDateTime.now());
        store.put(token, pending);
        return token;
    }

    /**
     * 读取待确认文件（不删除），用于选列失败后重试。
     *
     * @param token 令牌
     * @return 待确认文件
     */
    public PendingImport get(String token) {
        if (token == null || token.trim().isEmpty()) {
            throw new BizException(ResultCode.BAD_REQUEST, "文件令牌不能为空，请重新上传文件");
        }
        PendingImport pending = store.get(token.trim());
        if (pending == null) {
            throw new BizException(ResultCode.NOT_FOUND, "待确认文件已失效，请重新上传文件");
        }
        return pending;
    }

    /**
     * 移除待确认文件。
     *
     * @param token 令牌
     */
    public void remove(String token) {
        if (token != null) {
            store.remove(token.trim());
        }
    }

    /**
     * 取出并移除待确认文件。
     *
     * @param token 令牌
     * @return 待确认文件
     */
    public PendingImport take(String token) {
        PendingImport pending = get(token);
        store.remove(token.trim());
        return pending;
    }

    /**
     * 清理过期条目。
     */
    private void evictExpired() {
        LocalDateTime deadline = LocalDateTime.now().minusMinutes(TTL_MINUTES);
        Iterator<Map.Entry<String, PendingImport>> iterator = store.entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<String, PendingImport> entry = iterator.next();
            if (entry.getValue().getCreatedAt().isBefore(deadline)) {
                iterator.remove();
                log.info("待确认导入文件已过期，自动清理：fileName={}", entry.getValue().getFileName());
            }
        }
    }

    /**
     * 待确认的导入文件。
     */
    @Data
    public static class PendingImport {

        /** 令牌 */
        private String token;

        /** 源文件名 */
        private String fileName;

        /** 源文件大小 */
        private long fileSize;

        /** 实际解析格式 */
        private String format;

        /** 文本编码名，二进制格式为 null */
        private String charsetName;

        /** 待解析字节 */
        private byte[] data;

        /** 首行是否为表头 */
        private boolean headerPresent;

        /** 原始文件备份名 */
        private String backupFile;

        /** 暂存时间 */
        private LocalDateTime createdAt;

        /**
         * 取字符集。
         *
         * @return 字符集，未指定时返回 null
         */
        public Charset charset() {
            return charsetName == null ? null : Charset.forName(charsetName);
        }
    }
}
