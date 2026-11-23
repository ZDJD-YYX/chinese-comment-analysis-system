package com.example.commentanalysis.ai;

import com.example.commentanalysis.vo.ModelInfoVO;

import java.util.List;

/**
 * 情感分析推理服务（智能服务层唯一对外门面）。
 *
 * <p>业务层只依赖本接口，不出现任何 DJL、NDArray、Predictor 类型，
 * 便于后续将底层实现替换为 ONNX 或本地推理服务（对应《详细设计说明书》5.1 解耦手段）。</p>
 *
 * @author 闫宇星
 */
public interface SentimentInferenceService {

    /**
     * 批量情感推理。
     *
     * <p>输出与输入<b>顺序一致、长度相等</b>；空文本与非文本内容直接产出兜底结果
     * （中性、置信度 0、待复核），不进入模型；单条异常仅影响该条，不中断整批。</p>
     *
     * @param texts 评论文本列表，可为空
     * @return 与输入等长的推理结果列表
     */
    List<SentimentResult> batchInfer(List<String> texts);

    /**
     * 单条情感推理。
     *
     * @param text 评论文本
     * @return 推理结果
     */
    SentimentResult infer(String text);

    /**
     * 提取语料级 TopN 热点关键词（TF-IDF）。
     *
     * @param texts 评论文本列表
     * @param topN  返回条数上限，非正数时取配置值
     * @return 按权重降序的关键词列表
     */
    List<KeywordResult> extractKeywords(List<String> texts, int topN);

    /**
     * 为每条评论生成关键词串（英文逗号分隔），用于写入 {@code analysis_result.keywords}。
     *
     * @param texts      评论文本列表
     * @param maxPerText 单条评论关键词数量上限，非正数时取配置值
     * @return 与输入等长的关键词串列表
     */
    List<String> extractKeywordsPerText(List<String> texts, int maxPerText);

    /**
     * 创建关键词增量累加器。
     *
     * <p>用于大文件分析时按批累加词频/文档频率，避免把全部评论文本常驻内存。</p>
     *
     * @return 新的累加器实例
     */
    KeywordAccumulator createKeywordAccumulator();

    /**
     * 模型是否可用。
     *
     * @return true 表示模型已加载，可执行推理
     */
    boolean isAvailable();

    /**
     * 获取模型元信息。
     *
     * @return 模型版本、准确率、导出时间等信息
     */
    ModelInfoVO getModelInfo();
}
