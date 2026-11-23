package com.example.commentanalysis.controller;

import com.example.commentanalysis.common.Result;
import com.example.commentanalysis.config.AuthInterceptor;
import com.example.commentanalysis.dto.SettingsUpdateDTO;
import com.example.commentanalysis.service.AuditLogService;
import com.example.commentanalysis.service.SettingsService;
import com.example.commentanalysis.vo.AuditLogVO;
import com.example.commentanalysis.vo.SettingsVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpSession;
import java.util.List;

/**
 * 系统设置控制器。
 *
 * <p>提供模型与推理参数查看、可调参数修改，以及最近操作记录查询。</p>
 *
 * @author 闫宇星
 */
@RestController
@RequestMapping("/api/settings")
@RequiredArgsConstructor
public class SettingsController {

    private final SettingsService settingsService;

    private final AuditLogService auditLogService;

    /**
     * 读取系统设置。
     *
     * @return 模型信息与推理参数
     */
    @GetMapping
    public Result<SettingsVO> current() {
        return Result.success(settingsService.current());
    }

    /**
     * 修改可调参数。
     *
     * @param dto     修改参数
     * @param session HTTP 会话
     * @return 修改后的设置
     */
    @PostMapping
    public Result<SettingsVO> update(@RequestBody SettingsUpdateDTO dto, HttpSession session) {
        SettingsVO vo = settingsService.update(dto);
        auditLogService.record(username(session), "修改系统设置",
                "复核阈值=" + vo.getInference().getReviewThreshold()
                        + "，单条关键词数=" + vo.getInference().getKeywordsPerComment());
        return Result.success("设置已保存", vo);
    }

    /**
     * 查询最近的操作记录。
     *
     * @param limit 条数上限，默认 50，最大 200
     * @return 按时间倒序的操作记录
     */
    @GetMapping("/audit")
    public Result<List<AuditLogVO>> audit(@RequestParam(defaultValue = "50") Integer limit) {
        return Result.success(auditLogService.recent(limit));
    }

    /**
     * 取会话中的当前账号名，用于写入操作日志。
     *
     * @param session HTTP 会话
     * @return 账号名
     */
    private String username(HttpSession session) {
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        return username == null ? "未知" : String.valueOf(username);
    }
}