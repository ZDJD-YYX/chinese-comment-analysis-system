package com.example.commentanalysis.service;

import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.config.InferenceProperties;
import com.example.commentanalysis.entity.AnalysisResult;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.entity.CommentData;
import com.example.commentanalysis.mapper.AnalysisResultMapper;
import com.example.commentanalysis.mapper.AnalysisTaskMapper;
import com.example.commentanalysis.mapper.CommentDataMapper;
import com.example.commentanalysis.mapper.KeywordStatisticsMapper;
import com.example.commentanalysis.mapper.TaskStatisticsMapper;
import com.example.commentanalysis.service.impl.ResultServiceImpl;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletResponse;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.Collections;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * 结果导出格式测试。
 *
 * <p>验证 CSV / JSON 导出的字段完整性、转义与时间格式，确保与 Excel 导出数据一致。</p>
 *
 * @author 闫宇星
 */
class ResultExportFormatTest {

    private static final String CONTENT = "音质不错，\"很满意\"";

    private final ObjectMapper objectMapper = new ObjectMapper();

    private ResultServiceImpl resultService;

    @BeforeEach
    void setUp() {
        AnalysisResultMapper resultMapper = mock(AnalysisResultMapper.class);
        AnalysisTaskMapper taskMapper = mock(AnalysisTaskMapper.class);
        CommentDataMapper commentMapper = mock(CommentDataMapper.class);

        resultService = new ResultServiceImpl(
                resultMapper,
                taskMapper,
                commentMapper,
                mock(KeywordStatisticsMapper.class),
                mock(TaskStatisticsMapper.class),
                new InferenceProperties(),
                objectMapper);

        AnalysisTask task = new AnalysisTask();
        task.setTaskId(1L);
        task.setTaskName("demo");
        when(taskMapper.selectById(1L)).thenReturn(task);
        when(resultMapper.selectCount(any())).thenReturn(1L);

        AnalysisResult result = new AnalysisResult();
        result.setResultId(1L);
        result.setTaskId(1L);
        result.setCommentId(10L);
        result.setSentiment("POSITIVE");
        result.setConfidence(new BigDecimal("0.9231"));
        result.setKeywords("音质,续航");
        result.setNeedReview(0);
        result.setInferTimeMs(12);
        result.setCreateTime(LocalDateTime.of(2026, 9, 8, 10, 13, 45));
        when(resultMapper.selectExportPage(eq(1L), anyLong(), anyInt()))
                .thenReturn(Collections.singletonList(result));

        CommentData comment = new CommentData();
        comment.setCommentId(10L);
        comment.setContent(CONTENT);
        when(commentMapper.selectBatchIds(any())).thenReturn(Collections.singletonList(comment));
    }

    @Test
    @DisplayName("CSV 导出：BOM、表头、逗号与引号转义、时间格式")
    void exportCsv() throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();

        resultService.export(1L, "all", null, null, null, null, null, null, "csv", response);

        String body = response.getContentAsString(StandardCharsets.UTF_8);
        assertTrue(response.getContentType().startsWith("text/csv"));
        assertTrue(body.startsWith("\uFEFF"), "CSV 应带 UTF-8 BOM，避免 Excel 打开乱码");
        assertTrue(body.contains("评论编号,评论内容,情感标签,置信度,关键词,是否待人工复核,是否人工复核,是否改判,模型原判定,推理耗时(ms),分析时间"));
        assertTrue(body.contains("\"音质不错，\"\"很满意\"\"\""), "含逗号与引号的评论需正确转义");
        assertTrue(body.contains("2026-09-08 10:13:45"));
    }

    @Test
    @DisplayName("JSON 导出：字段与 Excel 列一致，数值保持数字类型")
    void exportJson() throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();

        resultService.export(1L, "all", null, null, null, null, null, null, "json", response);

        String body = response.getContentAsString(StandardCharsets.UTF_8);
        assertTrue(response.getContentType().startsWith("application/json"));
        JsonNode root = objectMapper.readTree(body);
        assertTrue(root.isArray());
        assertEquals(1, root.size());

        JsonNode row = root.get(0);
        assertEquals(10L, row.get("commentId").asLong());
        assertEquals(CONTENT, row.get("content").asText());
        assertEquals("正面", row.get("sentiment").asText());
        assertTrue(row.get("confidence").isNumber());
        assertEquals(0.9231, row.get("confidence").asDouble(), 0.00001);
        assertEquals("音质,续航", row.get("keywords").asText());
        assertFalse(row.get("needReview").asBoolean());
        assertEquals(12, row.get("inferTimeMs").asInt());
        assertEquals("2026-09-08 10:13:45", row.get("createTime").asText());
    }

    @Test
    @DisplayName("不支持的导出格式：返回 400")
    void unsupportedFormatShouldFail() {
        MockHttpServletResponse response = new MockHttpServletResponse();

        BizException error = assertThrows(BizException.class,
                () -> resultService.export(1L, "all", null, null, null, null, null, null, "pdf", response));

        assertEquals(400, error.getCode());
    }
}