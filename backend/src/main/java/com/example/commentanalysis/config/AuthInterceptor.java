package com.example.commentanalysis.config;

import com.example.commentanalysis.common.Result;
import com.example.commentanalysis.common.ResultCode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;

/**
 * 会话鉴权拦截器。
 *
 * <p>登录成功后由 {@code UserController} 把用户信息写入会话；之后所有
 * {@code /api/**} 请求（登录、注册除外）都必须携带有效会话，否则返回 HTTP 401
 * 与统一错误码 401，避免接口在未登录状态下被直接调用。</p>
 *
 * @author 闫宇星
 */
@Component
@RequiredArgsConstructor
public class AuthInterceptor implements HandlerInterceptor {

    /** 会话中保存用户编号的键 */
    public static final String SESSION_USER_ID = "LOGIN_USER_ID";

    /** 会话中保存用户名的键 */
    public static final String SESSION_USERNAME = "LOGIN_USERNAME";

    private final ObjectMapper objectMapper;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        // 预检请求直接放行
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        HttpSession session = request.getSession(false);
        Object userId = session == null ? null : session.getAttribute(SESSION_USER_ID);
        if (userId != null) {
            return true;
        }

        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(objectMapper.writeValueAsString(
                Result.fail(ResultCode.UNAUTHORIZED)));
        return false;
    }
}
