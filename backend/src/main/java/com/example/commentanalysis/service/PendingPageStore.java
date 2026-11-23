package com.example.commentanalysis.service;

import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.input.WebPageContent;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Iterator;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 已抓取网页的暂存服务。
 *
 * <p>网页正文抽取后先暂存在内存，用户在前端确认「这确实是正文」后再创建分析任务，
 * 避免重复抓取与"抽错内容直接分析"。单用户本地场景下只保留少量条目，
 * 超过上限淘汰最早的一条，超过有效期自动失效。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
public class PendingPageStore {

    /** 最多同时保留的待确认网页数 */
    private static final int MAX_ENTRIES = 5;

    /** 待确认网页有效期（分钟） */
    private static final long TTL_MINUTES = 15;

    private final Map<String, PendingPage> store = new ConcurrentHashMap<>();

    /**
     * 暂存抓取结果并返回确认令牌。
     *
     * @param content 抓取结果
     * @return 令牌
     */
    public String save(WebPageContent content) {
        evictExpired();
        if (store.size() >= MAX_ENTRIES) {
            store.entrySet().stream()
                    .min((a, b) -> a.getValue().getCreatedAt().compareTo(b.getValue().getCreatedAt()))
                    .ifPresent(entry -> store.remove(entry.getKey()));
        }
        String token = UUID.randomUUID().toString().replace("-", "");
        PendingPage page = new PendingPage();
        page.setToken(token);
        page.setContent(content);
        page.setCreatedAt(LocalDateTime.now());
        store.put(token, page);
        return token;
    }

    /**
     * 取出并移除待确认网页。
     *
     * @param token 令牌
     * @return 抓取结果
     */
    public WebPageContent take(String token) {
        if (token == null || token.trim().isEmpty()) {
            throw new BizException(ResultCode.BAD_REQUEST, "网页确认令牌不能为空，请重新抓取");
        }
        PendingPage page = store.remove(token.trim());
        if (page == null) {
            throw new BizException(ResultCode.NOT_FOUND, "网页内容已失效，请重新抓取");
        }
        return page.getContent();
    }

    /**
     * 清理过期条目。
     */
    private void evictExpired() {
        LocalDateTime deadline = LocalDateTime.now().minusMinutes(TTL_MINUTES);
        Iterator<Map.Entry<String, PendingPage>> iterator = store.entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<String, PendingPage> entry = iterator.next();
            if (entry.getValue().getCreatedAt().isBefore(deadline)) {
                iterator.remove();
                log.info("待确认网页已过期，自动清理：url={}",
                        entry.getValue().getContent().getUrl());
            }
        }
    }

    /**
     * 待确认的网页。
     */
    @Data
    public static class PendingPage {

        /** 令牌 */
        private String token;

        /** 抓取结果 */
        private WebPageContent content;

        /** 暂存时间 */
        private LocalDateTime createdAt;
    }
}
