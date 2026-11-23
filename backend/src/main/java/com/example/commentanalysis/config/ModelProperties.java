package com.example.commentanalysis.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 模型配置类，绑定 {@code app.model.*} 配置项。
 *
 * <p>集中管理模型目录、设备、最大长度与加载失败策略，供 {@code ModelRepository} 单例加载使用。</p>
 *
 * @author 闫宇星
 */
@Data
@Component
@ConfigurationProperties(prefix = "app.model")
public class ModelProperties {

    /** 模型目录：支持文件系统路径，或 {@code classpath:model/} 形式 */
    private String path = "model/bert-zh-sentiment-v1";

    /** 模型版本号，写入 {@code analysis_task.model_version} */
    private String version = "bert-zh-sentiment-v1";

    /** 推理设备，本项目仅打包 CPU 本地库，固定为 cpu */
    private String device = "cpu";

    /** 单条文本最大 token 数，须与训练/导出时的 MAX_LENGTH 一致 */
    private int maxLength = 128;

    /** 模型加载失败是否阻断应用启动 */
    private boolean failFast = false;
}
