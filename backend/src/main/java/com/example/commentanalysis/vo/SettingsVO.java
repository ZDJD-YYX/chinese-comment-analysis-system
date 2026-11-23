package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;

/**
 * 系统设置视图。
 *
 * <p>聚合模型信息与推理参数，供系统设置页展示。其中推理批量大小、
 * 热点词上限等参数直接影响任务执行队列，只做只读展示；复核阈值与
 * 单条关键词数量属于安全可调项，允许在线修改。</p>
 *
 * @author 闫宇星
 */
@Data
public class SettingsVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 系统名称 */
    private String appName;

    /** 系统版本 */
    private String version;

    /** 模型信息 */
    private ModelInfoVO model;

    /** 推理参数 */
    private InferenceSettings inference;

    /**
     * 推理参数明细。
     */
    @Data
    public static class InferenceSettings implements Serializable {

        private static final long serialVersionUID = 1L;

        /** 推理批量大小（只读，修改需重启） */
        private int batchSize;

        /** 低置信度人工复核阈值（可调，0.50～0.99） */
        private double reviewThreshold;

        /** 热点词返回条数上限（只读，修改需重启） */
        private int keywordTopN;

        /** 单条评论最大字符数（只读，修改需重启） */
        private int maxTextLength;

        /** 写入单条评论的关键词数量上限（可调，1～10） */
        private int keywordsPerComment;
    }
}