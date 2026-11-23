package com.example.commentanalysis.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 推理参数配置类，绑定 {@code app.inference.*} 配置项。
 *
 * @author 闫宇星
 */
@Data
@Component
@ConfigurationProperties(prefix = "app.inference")
public class InferenceProperties {

    /** 推理批量大小（1～256），同时作为任务表 batch_size 快照来源 */
    private int batchSize = 32;

    /** 低置信度需人工复核阈值，score 低于该值置 need_review = 1 */
    private double reviewThreshold = 0.60D;

    /** 热点词返回条数上限 */
    private int keywordTopN = 50;

    /** 单条评论最大字符数，超出截断 */
    private int maxTextLength = 512;

    /** 写入 analysis_result.keywords 的单条评论关键词数量上限 */
    private int keywordsPerComment = 5;
}
