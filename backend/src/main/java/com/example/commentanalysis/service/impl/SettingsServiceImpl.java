package com.example.commentanalysis.service.impl;

import com.example.commentanalysis.ai.ModelRepository;
import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.config.InferenceProperties;
import com.example.commentanalysis.dto.SettingsUpdateDTO;
import com.example.commentanalysis.service.SettingsService;
import com.example.commentanalysis.vo.ModelInfoVO;
import com.example.commentanalysis.vo.SettingsVO;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * 系统设置服务实现。
 *
 * <p>可调参数保存在 {@code config/runtime-settings.json}，应用启动时回填到
 * {@link InferenceProperties}，从而对后续任务生效；只读参数直接取自配置类与模型仓库。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SettingsServiceImpl implements SettingsService {

    /** 系统名称 */
    private static final String APP_NAME = "中文评论智能分析系统";

    /** 系统版本，与 pom.xml 保持一致 */
    private static final String APP_VERSION = "1.0.0";

    /** 复核阈值允许范围 */
    private static final double MIN_REVIEW_THRESHOLD = 0.50D;
    private static final double MAX_REVIEW_THRESHOLD = 0.99D;

    /** 单条关键词数量允许范围 */
    private static final int MIN_KEYWORDS_PER_COMMENT = 1;
    private static final int MAX_KEYWORDS_PER_COMMENT = 10;

    /** 运行时设置持久化文件 */
    private static final Path SETTINGS_PATH = Paths.get("config", "runtime-settings.json");

    private final InferenceProperties inferenceProperties;

    private final ModelRepository modelRepository;

    private final ObjectMapper objectMapper;

    /**
     * 启动时回填上次保存的可调参数。
     */
    @PostConstruct
    void restore() {
        if (!Files.isRegularFile(SETTINGS_PATH)) {
            return;
        }
        try {
            RuntimeOverrides overrides = objectMapper.readValue(SETTINGS_PATH.toFile(), RuntimeOverrides.class);
            if (overrides.reviewThreshold != null
                    && isValidThreshold(overrides.reviewThreshold)) {
                inferenceProperties.setReviewThreshold(overrides.reviewThreshold);
            }
            if (overrides.keywordsPerComment != null
                    && isValidKeywordsPerComment(overrides.keywordsPerComment)) {
                inferenceProperties.setKeywordsPerComment(overrides.keywordsPerComment);
            }
            log.info("已恢复运行时设置：reviewThreshold={}, keywordsPerComment={}",
                    inferenceProperties.getReviewThreshold(), inferenceProperties.getKeywordsPerComment());
        } catch (IOException e) {
            log.warn("读取运行时设置失败，将使用配置文件默认值：{}", e.getMessage());
        }
    }

    @Override
    public SettingsVO current() {
        SettingsVO vo = new SettingsVO();
        vo.setAppName(APP_NAME);
        vo.setVersion(APP_VERSION);

        // 模型可用状态以仓库实时状态为准：加载失败时 model_info 不一定会被覆盖
        ModelInfoVO model = modelRepository.getModelInfo();
        if (model != null) {
            model.setAvailable(modelRepository.isAvailable());
        }
        vo.setModel(model);

        SettingsVO.InferenceSettings inference = new SettingsVO.InferenceSettings();
        inference.setBatchSize(inferenceProperties.getBatchSize());
        inference.setReviewThreshold(inferenceProperties.getReviewThreshold());
        inference.setKeywordTopN(inferenceProperties.getKeywordTopN());
        inference.setMaxTextLength(inferenceProperties.getMaxTextLength());
        inference.setKeywordsPerComment(inferenceProperties.getKeywordsPerComment());
        vo.setInference(inference);
        return vo;
    }

    @Override
    public SettingsVO update(SettingsUpdateDTO dto) {
        if (dto == null || (dto.getReviewThreshold() == null && dto.getKeywordsPerComment() == null)) {
            throw new BizException(ResultCode.BAD_REQUEST, "请至少填写一项需要修改的参数");
        }

        Double threshold = dto.getReviewThreshold();
        if (threshold != null && !isValidThreshold(threshold)) {
            throw new BizException(ResultCode.BAD_REQUEST, "复核阈值需在 0.50～0.99 之间");
        }
        Integer perComment = dto.getKeywordsPerComment();
        if (perComment != null && !isValidKeywordsPerComment(perComment)) {
            throw new BizException(ResultCode.BAD_REQUEST, "单条关键词数量需在 1～10 之间");
        }

        if (threshold != null) {
            inferenceProperties.setReviewThreshold(threshold);
        }
        if (perComment != null) {
            inferenceProperties.setKeywordsPerComment(perComment);
        }

        persist();
        log.info("系统设置已更新：reviewThreshold={}, keywordsPerComment={}",
                inferenceProperties.getReviewThreshold(), inferenceProperties.getKeywordsPerComment());
        return current();
    }

    /**
     * 把当前可调参数写入设置文件。
     */
    private void persist() {
        RuntimeOverrides overrides = new RuntimeOverrides();
        overrides.reviewThreshold = inferenceProperties.getReviewThreshold();
        overrides.keywordsPerComment = inferenceProperties.getKeywordsPerComment();
        try {
            Files.createDirectories(SETTINGS_PATH.getParent());
            objectMapper.writeValue(SETTINGS_PATH.toFile(), overrides);
        } catch (IOException e) {
            // 参数已在内存生效，落盘失败只影响重启后的保持，因此记录日志不阻断请求
            log.error("保存运行时设置失败：{}", e.getMessage());
            throw new BizException(ResultCode.SYSTEM_ERROR, "设置已生效，但保存到本地文件失败");
        }
    }

    private boolean isValidThreshold(double value) {
        return value >= MIN_REVIEW_THRESHOLD && value <= MAX_REVIEW_THRESHOLD;
    }

    private boolean isValidKeywordsPerComment(int value) {
        return value >= MIN_KEYWORDS_PER_COMMENT && value <= MAX_KEYWORDS_PER_COMMENT;
    }

    /**
     * 运行时设置的文件结构。
     */
    public static class RuntimeOverrides {

        public Double reviewThreshold;

        public Integer keywordsPerComment;
    }
}