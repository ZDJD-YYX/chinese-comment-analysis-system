package com.example.commentanalysis.vo;

import lombok.Data;

import java.io.Serializable;
import java.util.Collections;
import java.util.List;

/**
 * 模型信息视图。
 *
 * <p>供系统配置页与任务创建前的能力检查使用，字段与模型导出的
 * {@code model_info.json} 对应。</p>
 *
 * @author 闫宇星
 */
@Data
public class ModelInfoVO implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 模型版本号 */
    private String modelVersion;

    /** 模型目录绝对路径 */
    private String modelDir;

    /** 推理设备 */
    private String device;

    /** 单条文本最大 token 数 */
    private Integer maxLength;

    /** 标签顺序，下标即标签 id */
    private List<String> labels = Collections.emptyList();

    /** 模型格式（TorchScript） */
    private String format;

    /** 模型是否可用 */
    private Boolean available = false;

    /** 基座模型名称 */
    private String baseModel;

    /** 测试集准确率 */
    private Double accuracy;

    /** 测试集宏平均 F1 */
    private Double macroF1;

    /** 模型导出时间 */
    private String exportTime;
}
