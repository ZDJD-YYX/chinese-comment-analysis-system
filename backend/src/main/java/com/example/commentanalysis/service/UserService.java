package com.example.commentanalysis.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.example.commentanalysis.dto.ChangePasswordDTO;
import com.example.commentanalysis.dto.LoginDTO;
import com.example.commentanalysis.dto.RegisterDTO;
import com.example.commentanalysis.entity.SysUser;
import com.example.commentanalysis.vo.LoginVO;

/**
 * 用户业务服务接口。
 *
 * <p>系统为单用户模式，仅提供管理员账号的注册与登录，不涉及角色与权限模型。</p>
 *
 * @author 闫宇星
 */
public interface UserService extends IService<SysUser> {

    /**
     * 用户登录。
     *
     * <p>校验账号存在、账号启用、密码匹配，成功后刷新最近登录时间。</p>
     *
     * @param dto 登录参数（账号、密码）
     * @return 登录成功后的用户基本信息
     */
    LoginVO login(LoginDTO dto);

    /**
     * 注册管理员账号。
     *
     * <p>密码使用 BCrypt（自带随机盐的慢哈希）存储，禁止明文落库；系统仅允许初始化一个管理员账号。</p>
     *
     * @param dto 注册参数（账号、密码）
     * @return 注册成功后的用户基本信息
     */
    LoginVO register(RegisterDTO dto);

    /**
     * 查询当前登录用户信息（个人中心展示）。
     *
     * @param userId 用户编号
     * @return 用户基本信息，账号不存在时返回 {@code null}
     */
    LoginVO currentUser(Long userId);

    /**
     * 修改当前登录用户的密码。
     *
     * <p>校验原密码正确（错误码 1003），新密码长度 6～64 位（错误码 1004），
     * 通过后以 BCrypt 哈希覆盖旧密码。</p>
     *
     * @param userId 用户编号
     * @param dto    修改密码参数（原密码、新密码）
     */
    void changePassword(Long userId, ChangePasswordDTO dto);
}
