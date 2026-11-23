package com.example.commentanalysis.controller;

import com.example.commentanalysis.common.Result;
import com.example.commentanalysis.dto.ColumnSelectDTO;
import com.example.commentanalysis.service.AnalysisTaskService;
import com.example.commentanalysis.service.FileService;
import com.example.commentanalysis.service.ImportBackupService;
import com.example.commentanalysis.vo.ParseReportVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;

/**
 * 文件上传解析控制器。
 *
 * @author 闫宇星
 */
@RestController
@RequestMapping("/api/file")
@RequiredArgsConstructor
public class FileController {

    private final FileService fileService;

    private final AnalysisTaskService analysisTaskService;

    private final ImportBackupService importBackupService;

    /**
     * 上传评论文件，校验修复后解析并创建分析任务，随后异步启动情感分析。
     *
     * <p>请求类型为 {@code multipart/form-data}，支持 .xlsx / .xls / .csv / .txt / .tsv / .json，
     * 单文件 ≤ 50 MB。导入前会自动做编码与乱码校验修复，并备份原始文件。</p>
     *
     * @param file 评论文件
     * @return 解析报告（含创建的任务编号、解析统计与校验结果）
     */
    @PostMapping("/upload")
    public Result<ParseReportVO> upload(@RequestParam("file") MultipartFile file) {
        ParseReportVO report = fileService.uploadAndParse(file);
        // 事务已提交，异步提交推理任务（立即返回，前端轮询任务详情获取进度）；
        // 需人工指定评论列时尚未创建任务，等重新导入成功后再启动推理
        if (report.getTaskId() != null) {
            analysisTaskService.startInference(report.getTaskId());
        }
        return Result.success(report.getTaskId() == null
                ? "未识别到评论列，请选择一列后继续"
                : "文件解析成功，分析任务已提交", report);
    }

    /**
     * 评论列自动识别失败后，按用户选择的列重新导入。
     *
     * <p>请求体携带上传接口返回的文件令牌与列序号，后端复用暂存文件解析，
     * 无需用户重新上传，对应需求 FR-BIZ-06。</p>
     *
     * @param dto 令牌与列序号
     * @return 解析报告（含创建的任务编号）
     */
    @PostMapping("/reimport")
    public Result<ParseReportVO> reimport(@RequestBody ColumnSelectDTO dto) {
        ParseReportVO report = fileService.confirmColumn(dto == null ? null : dto.getToken(),
                dto == null ? null : dto.getColumn());
        analysisTaskService.startInference(report.getTaskId());
        return Result.success("文件解析成功，分析任务已提交", report);
    }

    /**
     * 下载导入时备份的原始文件，用于异常回退或人工核对。
     *
     * @param name     备份文件名（由解析报告返回）
     * @param response HTTP 响应
     * @throws IOException 写出失败
     */
    @GetMapping("/backup")
    public void downloadBackup(@RequestParam("name") String name,
                               HttpServletResponse response) throws IOException {
        byte[] bytes = importBackupService.read(name);
        String encodedName;
        try {
            encodedName = URLEncoder.encode(name, "UTF-8").replaceAll("\\+", "%20");
        } catch (UnsupportedEncodingException e) {
            // UTF-8 为 JDK 必备字符集，正常不会触发
            encodedName = "backup.bin";
        }
        response.setContentType("application/octet-stream");
        response.setCharacterEncoding("UTF-8");
        response.setHeader("Content-Disposition", "attachment;filename*=utf-8''" + encodedName);
        response.setContentLength(bytes.length);
        response.getOutputStream().write(bytes);
        response.flushBuffer();
    }
}
