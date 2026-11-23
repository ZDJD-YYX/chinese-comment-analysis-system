package com.example.commentanalysis.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.commentanalysis.entity.AnalysisResult;
import com.example.commentanalysis.entity.TaskStatistics;
import com.example.commentanalysis.vo.CommentTimeRangeVO;
import com.example.commentanalysis.vo.ConfidenceBucketRow;
import com.example.commentanalysis.vo.ReviewMatrixRow;
import com.example.commentanalysis.vo.SentimentTrendVO;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.math.BigDecimal;
import java.util.List;

/**
 * 分析结果表 Mapper，继承 {@link BaseMapper} 获得通用 CRUD 能力。
 *
 * @author 闫宇星
 */
public interface AnalysisResultMapper extends BaseMapper<AnalysisResult> {

    /**
     * 批量插入分析结果。
     *
     * <p>{@code analysis_result} 是系统中写入量最大的表，逐条插入会产生大量网络往返。
     * 此处合并为单条多值 INSERT，配合连接串 {@code rewriteBatchedStatements=true}
     * 提升写入吞吐（对应数据库设计优化点 ⑦）。调用方需按 1000 条一批分片。</p>
     *
     * <p>唯一索引 {@code uk_task_comment} 保证同一任务同一评论不会重复写入，
     * 重试续跑时重复数据由数据库直接拒绝（NFR-R-02）。</p>
     *
     * @param list 待插入的结果列表，非空
     * @return 实际插入的行数
     */
    @Insert("<script>"
            + "INSERT INTO analysis_result "
            + "(task_id, comment_id, sentiment, confidence, keywords, need_review, infer_time_ms, create_time) VALUES "
            + "<foreach collection='list' item='item' separator=','>"
            + "(#{item.taskId}, #{item.commentId}, #{item.sentiment}, #{item.confidence}, "
            + "#{item.keywords}, #{item.needReview}, #{item.inferTimeMs}, #{item.createTime})"
            + "</foreach>"
            + "</script>")
    int insertBatch(@Param("list") List<AnalysisResult> list);

    /**
     * 按偏移量分页读取导出数据。
     *
     * <p>导出使用独立的 LIMIT/OFFSET 查询，绕开全局分页插件的单页上限（200），
     * 避免导出页大小被静默压缩后提前结束循环、导致只导出前 200 条。</p>
     *
     * @param taskId 任务编号
     * @param offset 起始偏移量
     * @param limit  单次读取条数
     * @return 分析结果列表
     */
    @Select("SELECT * FROM analysis_result WHERE task_id = #{taskId} "
            + "ORDER BY comment_id LIMIT #{limit} OFFSET #{offset}")
    List<AnalysisResult> selectExportPage(@Param("taskId") Long taskId,
                                          @Param("offset") long offset,
                                          @Param("limit") int limit);

    /**
     * 按当前筛选条件分页读取导出数据（导出范围「当前筛选」，FR-BIZ-27）。
     *
     * <p>与 {@link #selectExportPage} 同为独立的 LIMIT/OFFSET 查询；
     * sentiment/keyword 通过 MyBatis 参数绑定，避免 SQL 注入。</p>
     *
     * @param taskId     任务编号
     * @param sentiment  情感标签，可为空
     * @param keyword    关键词，可为空
     * @param needReview 复核状态（1 待复核 / 0 已复核），可为空
     * @param offset     起始偏移量
     * @param limit      单次读取条数
     * @return 分析结果列表
     */
    @Select("<script>"
            + "SELECT * FROM analysis_result WHERE task_id = #{taskId} "
            + "<if test='sentiment != null and sentiment != \"\"'> AND sentiment = #{sentiment}</if> "
            + "<if test='needReview != null'> AND need_review = #{needReview}</if> "
            + "<if test='reviewed != null'> AND reviewed = #{reviewed}</if> "
            + "<if test='minConfidence != null'> AND confidence &gt;= #{minConfidence}</if> "
            + "<if test='maxConfidence != null'> AND confidence &lt;= #{maxConfidence}</if> "
            + "<if test='keyword != null and keyword != \"\"'> AND (keywords LIKE CONCAT('%', #{keyword}, '%') "
            + "OR comment_id IN (SELECT c.comment_id FROM comment_data c "
            + "WHERE c.task_id = #{taskId} AND c.content LIKE CONCAT('%', #{keyword}, '%')))</if> "
            + "ORDER BY comment_id LIMIT #{limit} OFFSET #{offset}"
            + "</script>")
    List<AnalysisResult> selectExportPageFiltered(@Param("taskId") Long taskId,
                                                  @Param("sentiment") String sentiment,
                                                  @Param("keyword") String keyword,
                                                  @Param("needReview") Integer needReview,
                                                  @Param("reviewed") Integer reviewed,
                                                  @Param("minConfidence") BigDecimal minConfidence,
                                                  @Param("maxConfidence") BigDecimal maxConfidence,
                                                  @Param("offset") long offset,
                                                  @Param("limit") int limit);

    /**
     * 统计当前筛选条件下可导出的结果行数（用于导出上限校验，FR-BIZ-27）。
     *
     * @param taskId     任务编号
     * @param sentiment  情感标签，可为空
     * @param keyword    关键词，可为空
     * @param needReview 复核状态（1 待复核 / 0 已复核），可为空
     * @return 符合筛选条件的行数
     */
    @Select("<script>"
            + "SELECT COUNT(*) FROM analysis_result WHERE task_id = #{taskId} "
            + "<if test='sentiment != null and sentiment != \"\"'> AND sentiment = #{sentiment}</if> "
            + "<if test='needReview != null'> AND need_review = #{needReview}</if> "
            + "<if test='reviewed != null'> AND reviewed = #{reviewed}</if> "
            + "<if test='minConfidence != null'> AND confidence &gt;= #{minConfidence}</if> "
            + "<if test='maxConfidence != null'> AND confidence &lt;= #{maxConfidence}</if> "
            + "<if test='keyword != null and keyword != \"\"'> AND (keywords LIKE CONCAT('%', #{keyword}, '%') "
            + "OR comment_id IN (SELECT c.comment_id FROM comment_data c "
            + "WHERE c.task_id = #{taskId} AND c.content LIKE CONCAT('%', #{keyword}, '%')))</if>"
            + "</script>")
    Long countFiltered(@Param("taskId") Long taskId,
                       @Param("sentiment") String sentiment,
                       @Param("keyword") String keyword,
                       @Param("needReview") Integer needReview,
                       @Param("reviewed") Integer reviewed,
                       @Param("minConfidence") BigDecimal minConfidence,
                       @Param("maxConfidence") BigDecimal maxConfidence);

    /**
     * 单次聚合查询任务的统计摘要。
     *
     * <p>用 {@code SUM(CASE WHEN ...)} 在一条 SQL 内同时取得三类情感条数、待复核条数、
     * 平均置信度与推理总耗时，避免多次往返；聚合结果直接映射到
     * {@link TaskStatistics} 的对应字段（不含 error_count，该值取自任务表）。</p>
     *
     * <p>无数据时聚合仍返回一行，计数与求和经 {@code COALESCE} 归零，平均置信度为 {@code NULL}。</p>
     *
     * @param taskId 任务编号
     * @return 统计摘要
     */
    @Select("SELECT COUNT(*) AS total_count, "
            + "COALESCE(SUM(CASE WHEN sentiment = 'POSITIVE' THEN 1 ELSE 0 END), 0) AS positive_count, "
            + "COALESCE(SUM(CASE WHEN sentiment = 'NEGATIVE' THEN 1 ELSE 0 END), 0) AS negative_count, "
            + "COALESCE(SUM(CASE WHEN sentiment = 'NEUTRAL' THEN 1 ELSE 0 END), 0) AS neutral_count, "
            + "COALESCE(SUM(CASE WHEN need_review = 1 THEN 1 ELSE 0 END), 0) AS review_count, "
            + "AVG(confidence) AS avg_confidence, "
            + "COALESCE(SUM(infer_time_ms), 0) AS total_infer_time_ms "
            + "FROM analysis_result WHERE task_id = #{taskId}")
    TaskStatistics selectSummary(@Param("taskId") Long taskId);

    /**
     * 按评论原始时间聚合三类情感条数（情感趋势图数据源，FR-BIZ-18）。
     *
     * <p>评论时间列为空的数据不参与聚合；前端在返回为空时隐藏趋势图。</p>
     *
     * @param taskId  任务编号
     * @param pattern MySQL 日期格式串，按天为 {@code %Y-%m-%d}，按小时为 {@code %Y-%m-%d %H:00}
     * @return 按时间桶升序的聚合结果
     */
    @Select("SELECT DATE_FORMAT(c.comment_time, #{pattern}) AS bucket, "
            + "COALESCE(SUM(CASE WHEN r.sentiment = 'POSITIVE' THEN 1 ELSE 0 END), 0) AS positive, "
            + "COALESCE(SUM(CASE WHEN r.sentiment = 'NEGATIVE' THEN 1 ELSE 0 END), 0) AS negative, "
            + "COALESCE(SUM(CASE WHEN r.sentiment = 'NEUTRAL' THEN 1 ELSE 0 END), 0) AS neutral, "
            + "COUNT(*) AS total "
            + "FROM analysis_result r JOIN comment_data c "
            + "ON c.comment_id = r.comment_id AND c.task_id = r.task_id "
            + "WHERE r.task_id = #{taskId} AND c.comment_time IS NOT NULL "
            + "GROUP BY bucket ORDER BY bucket")
    List<SentimentTrendVO.Point> selectTrend(@Param("taskId") Long taskId,
                                             @Param("pattern") String pattern);

    /**
     * 查询任务内评论原始时间的范围，用于判断趋势图聚合粒度。
     *
     * @param taskId 任务编号
     * @return 时间范围；无可用时间字段时各字段为空
     */
    @Select("SELECT MIN(c.comment_time) AS min_time, MAX(c.comment_time) AS max_time "
            + "FROM comment_data c WHERE c.task_id = #{taskId} AND c.comment_time IS NOT NULL")
    CommentTimeRangeVO selectCommentTimeRange(@Param("taskId") Long taskId);

    /**
     * 按 0.1 为步长统计置信度区间条数。
     *
     * <p>用 {@code LEAST(..., 9)} 把置信度 1.0 归入最后一档，避免出现空档 1.0～1.1。</p>
     *
     * @param taskId 任务编号
     * @return 区间计数，仅包含有数据的区间
     */
    @Select("SELECT LEAST(FLOOR(confidence * 10), 9) AS bucket_index, COUNT(*) AS cnt "
            + "FROM analysis_result WHERE task_id = #{taskId} GROUP BY bucket_index")
    List<ConfidenceBucketRow> selectConfidenceBuckets(@Param("taskId") Long taskId);

    /**
     * 统计低于指定置信度的条数。
     *
     * @param taskId    任务编号
     * @param threshold 阈值（0～1）
     * @return 条数
     */
    @Select("SELECT COUNT(*) FROM analysis_result WHERE task_id = #{taskId} AND confidence < #{threshold}")
    long countBelowConfidence(@Param("taskId") Long taskId, @Param("threshold") double threshold);

    /**
     * 统计已人工复核的样本数。
     *
     * @param taskId 任务编号
     * @return 已复核条数
     */
    @Select("SELECT COUNT(*) FROM analysis_result WHERE task_id = #{taskId} AND reviewed = 1")
    long countReviewed(@Param("taskId") Long taskId);

    /**
     * 统计人工改判的样本数。
     *
     * @param taskId 任务编号
     * @return 改判条数
     */
    @Select("SELECT COUNT(*) FROM analysis_result WHERE task_id = #{taskId} "
            + "AND reviewed = 1 AND original_sentiment IS NOT NULL")
    long countCorrected(@Param("taskId") Long taskId);

    /**
     * 统计「模型原判定 → 人工结论」的混淆矩阵。
     *
     * <p>未改判的样本模型与人工结论相同，因此原判定回退为当前标签。</p>
     *
     * @param taskId 任务编号
     * @return 矩阵行，仅包含已复核样本
     */
    @Select("SELECT COALESCE(original_sentiment, sentiment) AS model_label, "
            + "sentiment AS human_label, COUNT(*) AS cnt "
            + "FROM analysis_result WHERE task_id = #{taskId} AND reviewed = 1 "
            + "GROUP BY model_label, human_label")
    List<ReviewMatrixRow> selectReviewMatrix(@Param("taskId") Long taskId);

    /**
     * 清除单条结果的改判痕迹。
     *
     * <p>人工复核后又选回模型原判定时，原判定字段必须置空，
     * 否则「改判条数 / 复核一致率」会把这条已与模型一致的记录继续算作改判。
     * MyBatis-Plus 默认忽略 null 字段，因此需要显式 SQL 置空。</p>
     *
     * @param resultId 结果编号
     * @return 影响行数
     */
    @Update("UPDATE analysis_result SET original_sentiment = NULL WHERE result_id = #{resultId}")
    int clearOriginalSentiment(@Param("resultId") Long resultId);
}
