package com.example.commentanalysis.controller;

import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.Result;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.config.AuthInterceptor;
import com.example.commentanalysis.dto.ChangePasswordDTO;
import com.example.commentanalysis.dto.LoginDTO;
import com.example.commentanalysis.dto.RegisterDTO;
import com.example.commentanalysis.service.AuditLogService;
import com.example.commentanalysis.service.UserService;
import com.example.commentanalysis.vo.LoginVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.servlet.http.HttpSession;
import javax.validation.Valid;

/**
 * 用户控制器。
 *
 * <p>提供管理员账号的注册、登录、会话校验与退出。登录成功后把用户信息写入
 * HTTP 会话，后续接口由 {@link AuthInterceptor} 统一校验。</p>
 *
 * @author 闫宇星
 */
@RestController
@RequestMapping("/api/user")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    private final AuditLogService auditLogService;

    /**
     * 用户登录。
     *
     * @param dto     登录参数（账号、密码）
     * @param session HTTP 会话
     * @return 登录成功后的用户基本信息
     */
    @PostMapping("/login")
    public Result<LoginVO> login(@Valid @RequestBody LoginDTO dto, HttpSession session) {
        LoginVO vo = userService.login(dto);
        session.setAttribute(AuthInterceptor.SESSION_USER_ID, vo.getUserId());
        session.setAttribute(AuthInterceptor.SESSION_USERNAME, vo.getUsername());
        auditLogService.record(vo.getUsername(), "登录", "登录成功");
        return Result.success("登录成功", vo);
    }

    /**
     * 注册管理员账号（仅系统尚无账号时可用）。
     *
     * @param dto     注册参数（账号、密码）
     * @param session HTTP 会话
     * @return 注册成功后的用户基本信息
     */
    @PostMapping("/register")
    public Result<LoginVO> register(@Valid @RequestBody RegisterDTO dto, HttpSession session) {
        LoginVO vo = userService.register(dto);
        session.setAttribute(AuthInterceptor.SESSION_USER_ID, vo.getUserId());
        session.setAttribute(AuthInterceptor.SESSION_USERNAME, vo.getUsername());
        auditLogService.record(vo.getUsername(), "注册账号", "初始化管理员账号");
        return Result.success("注册成功", vo);
    }

    /**
     * 校验当前会话并返回登录用户信息（前端刷新页面、个人中心展示时使用）。
     *
     * @param session HTTP 会话
     * @return 当前登录用户
     */
    @GetMapping("/me")
    public Result<LoginVO> me(HttpSession session) {
        Object userId = session.getAttribute(AuthInterceptor.SESSION_USER_ID);
        if (userId == null) {
            throw new BizException(ResultCode.UNAUTHORIZED);
        }
        LoginVO vo = userService.currentUser((Long) userId);
        if (vo == null) {
            // 会话仍在但账号已被删除：视为登录态失效
            throw new BizException(ResultCode.UNAUTHORIZED);
        }
        return Result.success(vo);
    }

    /**
     * 修改当前登录用户的密码。
     *
     * @param dto     修改密码参数（原密码、新密码）
     * @param session HTTP 会话
     * @return 操作结果
     */
    @PostMapping("/password")
    public Result<Void> changePassword(@Valid @RequestBody ChangePasswordDTO dto, HttpSession session) {
        Object userId = session.getAttribute(AuthInterceptor.SESSION_USER_ID);
        userService.changePassword((Long) userId, dto);
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        auditLogService.record(username == null ? "未知" : String.valueOf(username), "修改密码", "密码已更新");
        return Result.success();
    }

    /**
     * 退出登录，销毁会话。
     *
     * @param session HTTP 会话
     * @return 操作结果
     */
    @PostMapping("/logout")
    public Result<Void> logout(HttpSession session) {
        Object username = session.getAttribute(AuthInterceptor.SESSION_USERNAME);
        if (username != null) {
            auditLogService.record(String.valueOf(username), "退出登录", "会话已销毁");
        }
        session.invalidate();
        return Result.success();
    }
}
