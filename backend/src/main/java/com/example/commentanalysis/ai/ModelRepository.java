package com.example.commentanalysis.ai;

import ai.djl.Device;
import ai.djl.inference.Predictor;
import ai.djl.ndarray.NDArray;
import ai.djl.ndarray.NDList;
import ai.djl.ndarray.NDManager;
import ai.djl.ndarray.types.Shape;
import ai.djl.repository.zoo.Criteria;
import ai.djl.repository.zoo.ZooModel;
import ai.djl.translate.TranslateException;
import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.config.ModelProperties;
import com.example.commentanalysis.vo.ModelInfoVO;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 模型仓库：负责情感分析模型的<b>单例加载与常驻</b>。
 *
 * <p>启动阶段（{@link PostConstruct}）仅加载一次，运行期所有推理复用同一
 * {@link ZooModel} 与 {@link Predictor}，满足 NFR-P-06「模型常驻」约束。</p>
 *
 * <p>模型文件：{@code model.pt}（TorchScript，输入 input_ids/attention_mask/token_type_ids，
 * 输出 logits）、{@code vocab.txt}、{@code labels.txt}。文件缺失时按
 * {@code app.model.fail-fast} 决定是阻断启动还是降级（默认降级，保证其余业务可用）。</p>
 *
 * <p>本类是整个应用中唯一接触 DJL 类型的地方，业务层通过
 * {@link SentimentInferenceService} 门面调用，符合《详细设计说明书》5.1 的接口隔离约束。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Component
public class ModelRepository {

    private static final String MODEL_FILE = "model.pt";

    private static final String VOCAB_FILE = "vocab.txt";

    private static final String LABELS_FILE = "labels.txt";

    private static final String INFO_FILE = "model_info.json";

    private static final String CLASSPATH_PREFIX = "classpath:";

    private final ModelProperties modelProperties;

    private final ObjectMapper objectMapper;

    /** 常驻模型（单例） */
    private volatile ZooModel<NDList, NDList> model;

    /** 常驻推理器；Predictor 非线程安全，调用处需串行化 */
    private volatile Predictor<NDList, NDList> predictor;

    /** BERT 分词器 */
    private volatile BertTokenizer tokenizer;

    /** 模型是否可用 */
    private volatile boolean available;

    /** 标签顺序，下标即标签 id */
    private volatile List<String> labels = Collections.emptyList();

    /** 模型元信息 */
    private volatile ModelInfoVO modelInfo = new ModelInfoVO();

    public ModelRepository(ModelProperties modelProperties) {
        this.modelProperties = modelProperties;
        // model_info.json 含 numLabels 等本类未声明的字段，忽略未知属性和相关配置
        this.objectMapper = new ObjectMapper()
                .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    }

    /**
     * 应用启动时加载模型（仅一次）。
     *
     * <p>{@code fail-fast=true} 时加载失败将抛出异常阻断启动（FR-AI-01、NFR-R-06）；
     * 默认 {@code false}，加载失败仅记录错误日志并置为不可用，避免整套系统因模型缺失无法启动。</p>
     */
    @PostConstruct
    public void init() {
        try {
            loadModel();
        } catch (Exception e) {
            if (modelProperties.isFailFast()) {
                throw new IllegalStateException("情感分析模型加载失败，应用启动被阻断：" + e.getMessage(), e);
            }
            log.error("情感分析模型加载失败，相关功能降级为不可用（应用继续启动）。"
                    + "如需严格阻断启动，请设置 app.model.fail-fast=true。原因：{}", e.getMessage(), e);
        }
    }

    /**
     * 加载模型并常驻。
     *
     * @return 模型元信息
     */
    public synchronized ModelInfoVO loadModel() {
        Path modelDir = null;
        try {
            modelDir = resolveModelDir(modelProperties.getPath());
            validateModelFiles(modelDir);

            this.labels = readLabels(modelDir);
            this.tokenizer = new BertTokenizer(modelDir.resolve(VOCAB_FILE), modelProperties.getMaxLength());

            // 通过 DJL Criteria 加载 TorchScript 模型；仅 CPU 本地库，设备固定 cpu
            Criteria<NDList, NDList> criteria = Criteria.builder()
                    .setTypes(NDList.class, NDList.class)
                    .optModelPath(modelDir.resolve(MODEL_FILE))
                    .optEngine("PyTorch")
                    .optDevice(Device.cpu())
                    .optOption("mapLocation", "cpu")
                    .optOption("training", "false")
                    .build();

            ZooModel<NDList, NDList> loadedModel = criteria.loadModel();
            this.predictor = loadedModel.newPredictor();
            this.model = loadedModel;
            this.available = true;
            this.modelInfo = buildModelInfo(modelDir);

            log.info("情感分析模型加载完成（仅加载一次，运行期常驻）：dir={}, labels={}, maxLength={}, device=cpu, version={}",
                    modelDir, labels, modelProperties.getMaxLength(), modelInfo.getModelVersion());
            return this.modelInfo;
        } catch (Exception e) {
            this.available = false;
            log.error("加载情感分析模型失败：dir={}", modelDir, e);
            throw new BizException(ResultCode.MODEL_UNAVAILABLE,
                    "情感分析模型加载失败：" + e.getMessage());
        }
    }

    /**
     * 模型是否可用（模型已加载且 Predictor 非空）。
     *
     * @return true 表示可用
     */
    public boolean isAvailable() {
        return available && predictor != null && tokenizer != null;
    }

    /**
     * 获取标签顺序。
     *
     * @return 标签列表，下标即标签 id
     */
    public List<String> getLabels() {
        return labels;
    }

    /**
     * 获取模型元信息。
     *
     * @return 模型元信息
     */
    public ModelInfoVO getModelInfo() {
        return modelInfo;
    }

    /**
     * 批量前向推理，返回各类别概率。
     *
     * @param texts 已清洗的非空文本列表，非空
     * @return 形状 [batch, numLabels] 的概率矩阵
     */
    public float[][] predict(List<String> texts) {
        if (!isAvailable()) {
            throw new BizException(ResultCode.MODEL_UNAVAILABLE);
        }
        BertTokenizer.EncodedBatch batch = tokenizer.encode(texts);
        Shape shape = new Shape(batch.getBatchSize(), batch.getSeqLength());

        try (NDManager manager = NDManager.newBaseManager()) {
            NDArray inputIds = manager.create(batch.getInputIds(), shape);
            NDArray attentionMask = manager.create(batch.getAttentionMask(), shape);
            NDArray tokenTypeIds = manager.create(batch.getTokenTypeIds(), shape);

            NDList output = null;
            try {
                // Predictor 非线程安全：多任务并发时串行执行，保证结果正确（CPU 推理本身即为串行瓶颈）
                synchronized (predictor) {
                    output = predictor.predict(new NDList(inputIds, attentionMask, tokenTypeIds));
                }
                // TorchScript 已冻结 Softmax 之前的图，此处对 logits 手工做 Softmax 得到概率
                NDArray probabilities = output.singletonOrThrow().softmax(1);
                float[] flat = probabilities.toFloatArray();

                int batchSize = batch.getBatchSize();
                int numLabels = flat.length / batchSize;
                float[][] result = new float[batchSize][numLabels];
                for (int row = 0; row < batchSize; row++) {
                    System.arraycopy(flat, row * numLabels, result[row], 0, numLabels);
                }
                return result;
            } catch (TranslateException e) {
                log.error("模型前向推理失败：{}", e.getMessage(), e);
                throw new BizException(ResultCode.ANALYSIS_FAILED, "模型推理失败：" + e.getMessage());
            } finally {
                if (output != null) {
                    output.close();
                }
            }
        }
    }

    /**
     * 解析模型目录：支持文件系统路径与 {@code classpath:} 前缀。
     *
     * @param configuredPath 配置的模型路径
     * @return 模型目录
     */
    private Path resolveModelDir(String configuredPath) {
        if (!StringUtils.hasText(configuredPath)) {
            throw new BizException(ResultCode.MODEL_UNAVAILABLE, "未配置模型目录 app.model.path");
        }
        if (!configuredPath.startsWith(CLASSPATH_PREFIX)) {
            return Paths.get(configuredPath).toAbsolutePath().normalize();
        }
        String location = configuredPath.substring(CLASSPATH_PREFIX.length());
        ClassPathResource resource = new ClassPathResource(location);
        if (!resource.exists()) {
            throw new BizException(ResultCode.MODEL_UNAVAILABLE, "classpath 下未找到模型目录：" + location);
        }
        try {
            return resource.getFile().toPath();
        } catch (IOException e) {
            throw new BizException(ResultCode.MODEL_UNAVAILABLE,
                    "模型目录位于 jar 包内，无法以文件路径加载，请改用文件系统路径：" + configuredPath);
        }
    }

    /**
     * 校验模型必需文件是否存在。
     *
     * @param modelDir 模型目录
     */
    private void validateModelFiles(Path modelDir) {
        if (!Files.isDirectory(modelDir)) {
            throw new BizException(ResultCode.MODEL_UNAVAILABLE,
                    "模型目录不存在：" + modelDir + "，请先执行 python train.py 导出模型");
        }
        String[] required = {MODEL_FILE, VOCAB_FILE, LABELS_FILE};
        for (String fileName : required) {
            Path file = modelDir.resolve(fileName);
            if (!Files.isRegularFile(file)) {
                throw new BizException(ResultCode.MODEL_UNAVAILABLE,
                        "模型文件缺失：" + file + "，请先执行 python train.py 导出模型");
            }
        }
    }

    /**
     * 读取 labels.txt，行号即标签 id。
     *
     * @param modelDir 模型目录
     * @return 标签列表
     * @throws IOException 读取失败
     */
    private List<String> readLabels(Path modelDir) throws IOException {
        List<String> lines = Files.readAllLines(modelDir.resolve(LABELS_FILE));
        List<String> result = new ArrayList<>(lines.size());
        for (String line : lines) {
            String label = line.trim();
            if (!label.isEmpty()) {
                result.add(label);
            }
        }
        if (result.isEmpty()) {
            throw new BizException(ResultCode.MODEL_UNAVAILABLE, "labels.txt 为空：" + modelDir);
        }
        return result;
    }

    /**
     * 组装模型元信息，并合并 model_info.json 中的准确率、导出时间等字段。
     *
     * @param modelDir 模型目录
     * @return 模型元信息
     */
    private ModelInfoVO buildModelInfo(Path modelDir) {
        ModelInfoVO info = new ModelInfoVO();
        info.setModelVersion(modelProperties.getVersion());
        info.setModelDir(modelDir.toString());
        info.setDevice(modelProperties.getDevice());
        info.setMaxLength(modelProperties.getMaxLength());
        info.setLabels(labels);
        info.setFormat("TorchScript");
        info.setAvailable(true);

        Path infoPath = modelDir.resolve(INFO_FILE);
        if (!Files.isRegularFile(infoPath)) {
            log.warn("未找到 {}，仅返回基础模型信息。", infoPath);
            return info;
        }
        try {
            ModelInfoVO fromFile = objectMapper.readValue(Files.readAllBytes(infoPath), ModelInfoVO.class);
            if (StringUtils.hasText(fromFile.getModelVersion())) {
                info.setModelVersion(fromFile.getModelVersion());
            }
            info.setBaseModel(fromFile.getBaseModel());
            info.setAccuracy(fromFile.getAccuracy());
            info.setMacroF1(fromFile.getMacroF1());
            info.setExportTime(fromFile.getExportTime());
        } catch (IOException e) {
            log.warn("解析 model_info.json 失败，将仅返回基础模型信息：{}", e.getMessage());
        }
        return info;
    }
}
