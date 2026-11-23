package com.example.commentanalysis.service;

import com.example.commentanalysis.vo.ParseReportVO;
import org.springframework.web.multipart.MultipartFile;

/**
 * 文件上传解析业务服务接口。
 *
 * <p>负责 Excel / CSV 评论文件的校验、解析、清洗与入库，并同步创建分析任务。</p>
 *
 * @author 闫宇星
 */
public interface FileService {

    /**
     * 上传评论文件，解析并创建分析任务。
     *
     * <p>处理流程：扩展名与大小校验 → EasyExcel 解析 → 评论列识别 → 文本清洗 →
     * 创建任务记录 → 评论批量入库 → 返回解析报告。整个过程在同一事务内完成。</p>
     *
     * @param file 上传的评论文件（.xlsx / .xls / .csv，单文件 ≤ 50 MB）
     * @return 解析报告，含本次创建的任务编号与解析统计
     */
    ParseReportVO uploadAndParse(MultipartFile file);

    /**
     * 使用人工指定的评论列重新导入待确认文件。
     *
     * <p>评论列自动识别失败时，上传接口会暂存文件并返回令牌与候选列；
     * 用户选定列序号后调用本方法完成解析并创建分析任务（FR-BIZ-06）。</p>
     *
     * @param token  上传接口返回的文件令牌
     * @param column 用户选择的评论列序号，从 0 开始
     * @return 解析报告，含本次创建的任务编号
     */
    ParseReportVO confirmColumn(String token, Integer column);
}
