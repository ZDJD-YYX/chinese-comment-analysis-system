package com.example.commentanalysis.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.example.commentanalysis.common.BizException;
import com.example.commentanalysis.common.ResultCode;
import com.example.commentanalysis.dto.ChangePasswordDTO;
import com.example.commentanalysis.dto.LoginDTO;
import com.example.commentanalysis.dto.RegisterDTO;
import com.example.commentanalysis.entity.SysUser;
import com.example.commentanalysis.mapper.SysUserMapper;
import com.example.commentanalysis.service.UserService;
import com.example.commentanalysis.vo.LoginVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 用户业务服务实现。
 *
 * <p>密码使用 BCrypt（自带随机盐、慢哈希）存储；历史遗留的
 * 「随机盐 + 单轮 SHA-256」账号在首次成功登录后自动升级为 BCrypt。
 * 系统为单用户模式，仅在库中没有任何账号时允许注册。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Service
public class UserServiceImpl extends ServiceImpl<SysUserMapper, SysUser> implements UserService {

    /** 账号状态：1 启用 */
    private static final int STATUS_ENABLED = 1;

    /** 账号状态：0 停用 */
    private static final int STATUS_DISABLED = 0;

    /** 连续登录失败次数上限 */
    private static final int MAX_LOGIN_ATTEMPTS = 5;

    /** 登录失败计数窗口（毫秒）：5 分钟 */
    private static final long LOGIN_WINDOW_MS = 5 * 60 * 1000L;

    /** BCrypt 哈希前缀 */
    private static final String BCRYPT_PREFIX = "$2";

    private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder();

    /** 登录失败计数：用户名（小写）→ 计数窗口 */
    private final Map<String, LoginAttempt> loginAttempts = new ConcurrentHashMap<>();

    @Override
    public LoginVO login(LoginDTO dto) {
        String username = dto.getUsername().trim();
        String attemptKey = username.toLowerCase(Locale.ROOT);
        if (isLocked(attemptKey)) {
            throw new BizException(ResultCode.LOGIN_FAILED, "登录失败次数过多，请 5 分钟后再试");
        }

        SysUser user = getByUsername(username);
        boolean matched = user != null && matches(dto.getPassword(), user);
        // 账号不存在与密码错误返回同一提示，避免账号枚举
        if (!matched) {
            recordFailure(attemptKey);
            throw new BizException(ResultCode.LOGIN_FAILED);
        }
        if (user.getStatus() == null || user.getStatus() != STATUS_ENABLED) {
            throw new BizException(ResultCode.LOGIN_FAILED, "账号已停用，请联系管理员");
        }

        clearFailures(attemptKey);
        // 历史 SHA-256 账号在首次登录成功后透明升级为 BCrypt
        if (!isBcrypt(user.getPasswordHash())) {
            upgradePassword(user, dto.getPassword());
        }

        // 刷新最近登录时间
        LocalDateTime now = LocalDateTime.now();
        SysUser update = new SysUser();
        update.setUserId(user.getUserId());
        update.setLastLoginTime(now);
        baseMapper.updateById(update);
        user.setLastLoginTime(now);

        log.info("用户登录成功：userId={}, username={}", user.getUserId(), user.getUsername());
        return toLoginVO(user);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public LoginVO register(RegisterDTO dto) {
        String username = dto.getUsername().trim();
        // 单用户模式：系统初始化后不再开放注册，避免任意创建账号
        if (count() > 0) {
            throw new BizException(ResultCode.BAD_REQUEST, "系统已初始化管理员账号，请直接登录");
        }
        if (getByUsername(username) != null) {
            throw new BizException(ResultCode.BAD_REQUEST, "账号已存在，请直接登录");
        }

        SysUser user = new SysUser();
        user.setUsername(username);
        // BCrypt 哈希自带盐值，salt 字段留空以满足非空约束
        user.setSalt("");
        user.setPasswordHash(passwordEncoder.encode(dto.getPassword()));
        user.setStatus(STATUS_ENABLED);
        user.setCreateTime(LocalDateTime.now());
        user.setUpdateTime(LocalDateTime.now());
        baseMapper.insert(user);

        log.info("注册管理员账号成功：userId={}, username={}", user.getUserId(), user.getUsername());
        return toLoginVO(user);
    }

    @Override
    public LoginVO currentUser(Long userId) {
        if (userId == null) {
            return null;
        }
        SysUser user = baseMapper.selectById(userId);
        return user == null ? null : toLoginVO(user);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void changePassword(Long userId, ChangePasswordDTO dto) {
        String newPassword = dto.getNewPassword();
        if (newPassword.length() < 6 || newPassword.length() > 64) {
            throw new BizException(ResultCode.NEW_PASSWORD_INVALID);
        }

        SysUser user = userId == null ? null : baseMapper.selectById(userId);
        if (user == null || !matches(dto.getOldPassword(), user)) {
            throw new BizException(ResultCode.OLD_PASSWORD_ERROR);
        }
        // 与原密码相同属于无意义修改，直接拒绝
        if (passwordEncoder.matches(newPassword, user.getPasswordHash())) {
            throw new BizException(ResultCode.BAD_REQUEST, "新密码不能与原密码相同");
        }

        SysUser update = new SysUser();
        update.setUserId(user.getUserId());
        update.setSalt("");
        update.setPasswordHash(passwordEncoder.encode(newPassword));
        update.setUpdateTime(LocalDateTime.now());
        baseMapper.updateById(update);

        log.info("修改密码成功：userId={}, username={}", user.getUserId(), user.getUsername());
    }

    /**
     * 校验密码：BCrypt 直接匹配；历史 SHA-256 哈希走兼容逻辑。
     *
     * @param rawPassword 明文密码
     * @param user        用户记录
     * @return 是否匹配
     */
    private boolean matches(String rawPassword, SysUser user) {
        String hash = user.getPasswordHash();
        if (!StringUtils.hasText(hash)) {
            return false;
        }
        if (isBcrypt(hash)) {
            try {
                return passwordEncoder.matches(rawPassword, hash);
            } catch (IllegalArgumentException e) {
                log.warn("BCrypt 哈希格式异常：userId={}", user.getUserId());
                return false;
            }
        }
        return legacyHash(rawPassword, user.getSalt()).equals(hash);
    }

    /**
     * 将历史 SHA-256 密码升级为 BCrypt。
     *
     * @param user        用户记录
     * @param rawPassword 本次登录的明文密码
     */
    private void upgradePassword(SysUser user, String rawPassword) {
        SysUser update = new SysUser();
        update.setUserId(user.getUserId());
        update.setSalt("");
        update.setPasswordHash(passwordEncoder.encode(rawPassword));
        update.setUpdateTime(LocalDateTime.now());
        baseMapper.updateById(update);
        log.info("已将历史密码哈希升级为 BCrypt：userId={}", user.getUserId());
    }

    /**
     * 是否为 BCrypt 哈希。
     *
     * @param hash 密码哈希
     * @return 是 BCrypt 时返回 true
     */
    private boolean isBcrypt(String hash) {
        return hash != null && hash.startsWith(BCRYPT_PREFIX);
    }

    /**
     * 历史密码算法：盐值摘要 + 明文与盐拼接后再做 SHA-256（仅用于兼容旧数据）。
     *
     * @param rawPassword 明文密码
     * @param salt        盐值
     * @return Base64 编码的哈希
     */
    private String legacyHash(String rawPassword, String salt) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update(salt.getBytes(StandardCharsets.UTF_8));
            byte[] hashed = digest.digest((rawPassword + salt).getBytes(StandardCharsets.UTF_8));
            return Base64.getEncoder().encodeToString(hashed);
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 为 JDK 必备算法，正常不会触发
            throw new BizException(ResultCode.SYSTEM_ERROR, "密码加密失败");
        }
    }

    /**
     * 是否处于登录锁定窗口。
     *
     * @param key 用户名（小写）
     * @return 锁定中返回 true
     */
    private boolean isLocked(String key) {
        LoginAttempt attempt = loginAttempts.get(key);
        if (attempt == null) {
            return false;
        }
        if (System.currentTimeMillis() - attempt.windowStart > LOGIN_WINDOW_MS) {
            loginAttempts.remove(key);
            return false;
        }
        return attempt.count >= MAX_LOGIN_ATTEMPTS;
    }

    /**
     * 记录一次登录失败。
     *
     * @param key 用户名（小写）
     */
    private void recordFailure(String key) {
        long now = System.currentTimeMillis();
        loginAttempts.compute(key, (k, attempt) -> {
            if (attempt == null || now - attempt.windowStart > LOGIN_WINDOW_MS) {
                return new LoginAttempt(now, 1);
            }
            attempt.count++;
            return attempt;
        });
    }

    /**
     * 登录成功后清除失败计数。
     *
     * @param key 用户名（小写）
     */
    private void clearFailures(String key) {
        loginAttempts.remove(key);
    }

    /**
     * 按账号查询用户。
     *
     * @param username 登录账号
     * @return 用户记录，不存在时返回 {@code null}
     */
    private SysUser getByUsername(String username) {
        if (!StringUtils.hasText(username)) {
            return null;
        }
        return baseMapper.selectOne(new LambdaQueryWrapper<SysUser>()
                .eq(SysUser::getUsername, username));
    }

    /**
     * 实体转登录视图，剥离密码哈希与盐值。
     *
     * @param user 用户实体
     * @return 登录视图
     */
    private LoginVO toLoginVO(SysUser user) {
        LoginVO vo = new LoginVO();
        vo.setUserId(user.getUserId());
        vo.setUsername(user.getUsername());
        vo.setLastLoginTime(user.getLastLoginTime());
        vo.setCreateTime(user.getCreateTime());
        return vo;
    }

    /**
     * 登录失败计数窗口。
     */
    private static class LoginAttempt {

        private final long windowStart;

        private int count;

        LoginAttempt(long windowStart, int count) {
            this.windowStart = windowStart;
            this.count = count;
        }
    }
}
