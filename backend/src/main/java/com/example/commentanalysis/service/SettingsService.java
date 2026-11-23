package com.example.commentanalysis.service;

import com.example.commentanalysis.dto.SettingsUpdateDTO;
import com.example.commentanalysis.vo.SettingsVO;

/**
 * 系统设置服务。
 *
 * <p>展示模型与推理参数，并支持修改复核阈值等安全可调项；
 * 修改结果持久化到本地配置文件，重启后仍然生效。</p>
 *
 * @author 闫宇星
 */
public interface SettingsService {

    /**
     * 读取当前系统设置。
     *
     * @return 设置视图
     */
    SettingsVO current();

    /**
     * 修改可调参数并持久化。
     *
     * @param dto 修改参数
     * @return 修改后的设置视图
     */
    SettingsVO update(SettingsUpdateDTO dto);
}