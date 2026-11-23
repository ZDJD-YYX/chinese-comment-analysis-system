package com.example.commentanalysis.service;

import com.example.commentanalysis.dto.ContentInputDTO;
import com.example.commentanalysis.vo.InputReportVO;
import com.example.commentanalysis.vo.PagePreviewVO;

/**
 * 智能输入业务服务接口。
 *
 * <p>承接用户粘贴的纯文本或网页链接，自动识别类型、提取正文、切分评论并创建分析任务。</p>
 *
 * @author 闫宇星
 */
public interface InputService {

    /**
     * 接收并解析用户输入，创建待分析任务。
     *
     * <p>链接输入会先抓取网页并过滤导航、广告等噪声；纯文本输入直接切分。
     * 长内容按句末标点拆分为多条评论，不做静默截断。</p>
     *
     * @param dto 输入内容
     * @return 接收回执（含任务编号、来源类型与处理统计）
     */
    InputReportVO analyze(ContentInputDTO dto);

    /**
     * 抓取网页并生成正文预览，暂不创建任务。
     *
     * <p>用于「先确认再分析」流程：返回标题、篇幅、段落数与正文开头，
     * 用户确认后再调用 {@link #confirmPage(String)} 创建任务，避免直接分析错误内容。</p>
     *
     * @param dto 输入内容（必须是网页链接）
     * @return 正文预览，含确认令牌
     */
    PagePreviewVO previewPage(ContentInputDTO dto);

    /**
     * 按确认令牌创建分析任务。
     *
     * @param token 预览接口返回的令牌
     * @return 接收回执（含任务编号）
     */
    InputReportVO confirmPage(String token);
}
