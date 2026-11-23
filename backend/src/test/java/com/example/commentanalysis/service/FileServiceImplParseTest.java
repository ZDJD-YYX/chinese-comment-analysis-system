package com.example.commentanalysis.service;

import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.entity.CommentData;
import com.example.commentanalysis.entity.SysUser;
import com.example.commentanalysis.mapper.AnalysisTaskMapper;
import com.example.commentanalysis.mapper.CommentDataMapper;
import com.example.commentanalysis.mapper.SysUserMapper;
import com.example.commentanalysis.service.PendingImportStore;
import com.example.commentanalysis.service.impl.FileServiceImpl;
import com.example.commentanalysis.validation.ImportValidator;
import com.example.commentanalysis.vo.ParseReportVO;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 文件解析链路测试。
 *
 * <p>用 data/测试数据 下的多类型样本驱动 {@link FileServiceImpl#uploadAndParse}，
 * 覆盖：多列 CSV / Excel、GBK 编码、英文表头、无表头推断、脏数据清洗、
 * 非典型列名推断、空数据报错与大体量分批入库。</p>
 *
 * <p>数据库层用 Mockito 替身，只验证解析与清洗逻辑，不依赖 MySQL。</p>
 *
 * @author 闫宇星
 */
class FileServiceImplParseTest {

    /** 样本目录：Maven 从 backend 目录运行，因此优先取上级 data/测试数据 */
    private static final Path SAMPLE_DIR = resolveSampleDir();

    private FileServiceImpl fileService;

    /** 本次解析实际"入库"的评论 */
    private List<CommentData> inserted;

    private CommentDataMapper commentDataMapper;

    @BeforeEach
    void setUp() {
        AnalysisTaskMapper taskMapper = mock(AnalysisTaskMapper.class);
        commentDataMapper = mock(CommentDataMapper.class);
        SysUserMapper userMapper = mock(SysUserMapper.class);
        ImportBackupService backupService = mock(ImportBackupService.class);

        fileService = new FileServiceImpl(taskMapper, commentDataMapper, userMapper,
                new ImportValidator(), backupService, new PendingImportStore(), new ObjectMapper());
        ReflectionTestUtils.setField(fileService, "batchSize", 32);
        ReflectionTestUtils.setField(fileService, "maxTextLength", 512);
        ReflectionTestUtils.setField(fileService, "modelVersion", "bert-zh-sentiment-v1");

        SysUser user = new SysUser();
        user.setUserId(1L);
        user.setUsername("admin");
        when(userMapper.selectOne(any())).thenReturn(user);

        when(backupService.save(anyLong(), anyString(), any(byte[].class))).thenReturn("backup-test.bin");

        when(taskMapper.insert(any(AnalysisTask.class))).thenAnswer(invocation -> {
            AnalysisTask task = invocation.getArgument(0);
            task.setTaskId(100L);
            return 1;
        });
        when(taskMapper.updateById(any(AnalysisTask.class))).thenReturn(1);

        inserted = new ArrayList<>();
        when(commentDataMapper.insertBatch(anyList())).thenAnswer(invocation -> {
            List<CommentData> batch = invocation.getArgument(0);
            inserted.addAll(batch);
            return batch.size();
        });
    }

    @Test
    @DisplayName("标准多列 CSV：命中评论列表头，逐行解析")
    void parseStandardCsv() throws IOException {
        ParseReportVO report = parse("01_标准多列_UTF8BOM.csv");

        assertEquals(20, report.getValidCount());
        assertEquals(0, report.getFilteredCount());
        assertEquals(3, report.getCommentColumn());
        assertEquals(20, inserted.size());
        assertTrue(report.getFilterReasons().isEmpty());
    }

    @Test
    @DisplayName("多列 Excel：xlsx 正常解析并定位「评价内容」列")
    void parseExcel() throws IOException {
        ParseReportVO report = parse("02_多列评价.xlsx");

        assertEquals(20, report.getValidCount());
        assertEquals(3, report.getCommentColumn());
        assertEquals(20, inserted.size());
    }

    @Test
    @DisplayName("GBK 编码 CSV：中文正确解码，不出现乱码")
    void parseGbkCsv() throws IOException {
        ParseReportVO report = parse("03_GBK编码_评价.csv");

        assertEquals(10, report.getValidCount());
        assertEquals(1, report.getCommentColumn());
        assertNotNull(report.getValidation());
        assertEquals("FIXED", report.getValidation().getStatus());
        for (CommentData comment : inserted) {
            assertTrue(comment.getContent().matches(".*[\\u4e00-\\u9fa5].*"),
                    "GBK 文件应解析出中文，实际内容：" + comment.getContent());
            assertFalse(comment.getContent().contains("\uFFFD"));
        }
    }

    @Test
    @DisplayName("英文表头 CSV：命中 review 关键词")
    void parseEnglishHeaderCsv() throws IOException {
        ParseReportVO report = parse("04_英文表头_review.csv");

        assertEquals(10, report.getValidCount());
        assertEquals(3, report.getCommentColumn());
    }

    @Test
    @DisplayName("无表头单列 CSV：首行按数据处理，默认取第一列")
    void parseHeaderlessCsv() throws IOException {
        ParseReportVO report = parse("05_无表头_纯评论.csv");

        assertEquals(15, report.getValidCount());
        assertEquals(0, report.getCommentColumn());
    }

    @Test
    @DisplayName("脏数据：过滤空行与重复行，保留首尾空格清洗结果，超长文本截断")
    void parseDirtyCsv() throws IOException {
        ParseReportVO report = parse("06_脏数据_空行重复超长.csv");

        // 6 条唯一有效评论；重复 2 条，其余为空白行
        assertEquals(6, report.getValidCount());
        assertEquals(6, inserted.size());
        assertEquals(2, report.getFilterReasons().get("重复行"));
        assertNotNull(report.getFilterReasons().get("空白行"));
        assertEquals(report.getTotalCount(), report.getValidCount() + report.getFilteredCount());

        int maxLength = inserted.stream().mapToInt(item -> item.getContent().length()).max().orElse(0);
        assertEquals(512, maxLength, "超长评论应按 max-text-length 截断");
        for (CommentData comment : inserted) {
            assertEquals(comment.getContent().trim(), comment.getContent(), "评论应已完成首尾空白清洗");
        }
    }

    @Test
    @DisplayName("列名不典型 Excel：按文本长度推断出「用户反馈」列")
    void parseNonTypicalHeaderExcel() throws IOException {
        ParseReportVO report = parse("07_列名不典型_用户反馈.xlsx");

        assertEquals(12, report.getValidCount());
        assertEquals(1, report.getCommentColumn());
    }

    @Test
    @DisplayName("纯文本 TXT：一行一条评论，无表头")
    void parseTxt() throws IOException {
        ParseReportVO report = parse("10_纯文本_逐行评论.txt");

        assertEquals(15, report.getValidCount());
        assertEquals(0, report.getCommentColumn());
        assertEquals("txt", report.getValidation().getActualFormat());
    }

    @Test
    @DisplayName("制表符 TSV：识别「评价内容」列")
    void parseTsv() throws IOException {
        ParseReportVO report = parse("11_制表符_TSV.tsv");

        assertEquals(10, report.getValidCount());
        assertEquals(2, report.getCommentColumn());
        assertEquals("tsv", report.getValidation().getActualFormat());
    }

    @Test
    @DisplayName("JSON 字符串数组：每个元素作为一条评论")
    void parseJsonStringArray() throws IOException {
        ParseReportVO report = parse("12_JSON字符串数组.json");

        assertEquals(10, report.getValidCount());
        assertEquals("json", report.getValidation().getActualFormat());
    }

    @Test
    @DisplayName("JSON 对象数组：按 comment/content/review 字段取评论")
    void parseJsonObjectArray() throws IOException {
        ParseReportVO report = parse("13_JSON对象数组.json");

        assertEquals(8, report.getValidCount());
        assertTrue(inserted.stream().anyMatch(item -> item.getContent().contains("降噪效果好")),
                "应能取到 review 字段中的评论");
    }

    @Test
    @DisplayName("仅表头无数据：返回「未解析到有效评论」（2004）")
    void parseHeaderOnlyCsvShouldFail() {
        BizException error = assertThrows(BizException.class,
                () -> parse("08_仅表头_无数据_预期报错.csv"));

        assertEquals(2004, error.getCode());
        assertTrue(inserted.isEmpty());
    }

    @Test
    @DisplayName("大体量 1200 条：按 1000 条一批分批入库")
    void parseLargeCsvInBatches() throws IOException {
        ParseReportVO report = parse("09_大体量_1200条.csv");

        assertEquals(1200, report.getValidCount());
        verify(commentDataMapper, times(2)).insertBatch(anyList());
    }

    @Test
    @DisplayName("不支持的扩展名：返回 2001")
    void parseUnsupportedExtensionShouldFail() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "评论.pdf", "application/pdf", "随便一段文本".getBytes());

        BizException error = assertThrows(BizException.class, () -> fileService.uploadAndParse(file));
        assertEquals(2001, error.getCode());
    }

    /**
     * 读取样本目录下的文件并走一次完整解析。
     *
     * @param fileName 样本文件名
     * @return 解析报告
     * @throws IOException 读取失败
     */
    private ParseReportVO parse(String fileName) throws IOException {
        Path path = SAMPLE_DIR.resolve(fileName);
        assertTrue(Files.isRegularFile(path), "样本文件不存在：" + path);
        MockMultipartFile file = new MockMultipartFile(
                "file", fileName, null, Files.readAllBytes(path));
        return fileService.uploadAndParse(file);
    }

    /**
     * 定位样本目录，兼容从仓库根目录或 backend 目录运行。
     *
     * @return 样本目录
     */
    private static Path resolveSampleDir() {
        Path fromBackend = Paths.get("..", "data", "测试数据");
        if (Files.isDirectory(fromBackend)) {
            return fromBackend.toAbsolutePath().normalize();
        }
        return Paths.get("data", "测试数据").toAbsolutePath().normalize();
    }
}
