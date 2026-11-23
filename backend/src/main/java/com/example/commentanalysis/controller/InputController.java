package com.example.commentanalysis.controller;

import com.example.commentanalysis.common.Result;
import com.example.commentanalysis.config.AuthInterceptor;
import com.example.commentanalysis.dto.ContentInputDTO;
import com.example.commentanalysis.dto.PageConfirmDTO;
import com.example.commentanalysis.service.AnalysisTaskService;
import com.example.commentanalysis.service.AuditLogService;
import com.example.commentanalysis.service.InputService;
import com.example.commentanalysis.vo.InputReportVO;
import com.example.commentanalysis.vo.PagePreviewVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpSession;
import javax.validation.Valid;

/**
 * 智能输入控制器。
 *
 * <p>统一接收用户粘贴的评论文本或网页链接，自动识别类型后创建分析任务并异步启动推理，
 * 前端无需区分模式。</p>
 *
 * @author 闫宇星
 */
@RestController
@RequestMapping("/api/input")
@RequiredArgsConstructor
public class InputController {

    private final InputService inputService;

    private final AnalysisTaskService analysisTaskService;

    private final AuditLogService auditLogService;

    /**
     * 接收文本或网页链接并进入分析流程。
     *
     * <p>链接会自动抓取正文并过滤导航、广告等噪声；文本直接归一化切分。
     * 返回接收回执后立即异步推理，前端可轮询任务进度。</p>
     *
     * @param dto     输入内容
     * @param session 当前会话，用于记录操作日志
     * @return 接收回执（含任务编号、来源类型与处理统计）
     */
    @PostMapping("/analyze")
    public Result<InputReportVO> analyze(@Valid @RequestBody ContentInputDTO dto, HttpSession session) {
        InputReportVO report = inputService.analyze(dto);
        analysisTaskService.startInference(report.getTaskId());
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                "智能输入分析", report.getSourceTypeLabel() + " · 任务编号 " + report.getTaskId());
        return Result.success(report.getMessage(), report);
    }

    /**
     * 抓取网页并返回正文预览，暂不创建任务。
     *
     * <p>正文抽取结果先交给用户确认，避免抽到导航或推荐位却直接分析。</p>
     *
     * @param dto 网页链接
     * @return 正文预览（含确认令牌）
     */
    @PostMapping("/preview")
    public Result<PagePreviewVO> preview(@Valid @RequestBody ContentInputDTO dto) {
        return Result.success("网页已抓取，请确认正文", inputService.previewPage(dto));
    }

    /**
     * 确认正文后创建分析任务并开始推理。
     *
     * @param dto     确认令牌
     * @param session 当前会话，用于记录操作日志
     * @return 接收回执（含任务编号）
     */
    @PostMapping("/confirm")
    public Result<InputReportVO> confirm(@RequestBody PageConfirmDTO dto, HttpSession session) {
        InputReportVO report = inputService.confirmPage(dto == null ? null : dto.getToken());
        analysisTaskService.startInference(report.getTaskId());
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username),
                "网页正文确认后分析",
                report.getSourceTitle() + " · 任务编号 " + report.getTaskId());
        return Result.success(report.getMessage(), report);
    }
}
