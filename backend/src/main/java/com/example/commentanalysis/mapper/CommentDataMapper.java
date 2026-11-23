package com.example.commentanalysis.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.commentanalysis.entity.CommentData;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 评论原始数据表 Mapper，继承 {@link BaseMapper} 获得通用 CRUD 能力。
 *
 * @author 闫宇星
 */
public interface CommentDataMapper extends BaseMapper<CommentData> {

    /**
     * 批量插入评论。
     *
     * <p>文件解析阶段单任务可达上万条评论，逐条插入会产生大量网络往返。
     * 此处使用单条多值 INSERT 合并提交，配合连接串
     * {@code rewriteBatchedStatements=true} 提升写入吞吐（对应数据库设计优化点 ⑦）。
     * 调用方需按 1000 条一批分片，避免单条 SQL 过大。</p>
     *
     * @param list 待插入的评论列表，非空
     * @return 实际插入的行数
     */
    @Insert("<script>"
            + "INSERT INTO comment_data (task_id, content, row_no, comment_time, create_time) VALUES "
            + "<foreach collection='list' item='item' separator=','>"
            + "(#{item.taskId}, #{item.content}, #{item.rowNo}, #{item.commentTime}, #{item.createTime})"
            + "</foreach>"
            + "</script>")
    int insertBatch(@Param("list") List<CommentData> list);

    /**
     * 查询任务下尚未产出分析结果的评论（失败重试续跑用）。
     *
     * <p>借助 {@code uk_task_comment (task_id, comment_id)} 唯一索引做反连接，
     * 只返回未处理评论，天然实现「不重不漏」的续跑语义（对应 NFR-R-02）。</p>
     *
     * @param taskId 任务编号
     * @param limit  单批读取条数
     * @return 待处理评论列表，按源文件行号升序
     */
    @Select("SELECT c.* FROM comment_data c "
            + "LEFT JOIN analysis_result r "
            + "ON r.task_id = c.task_id AND r.comment_id = c.comment_id "
            + "WHERE c.task_id = #{taskId} AND r.result_id IS NULL "
            + "ORDER BY c.row_no LIMIT #{limit}")
    List<CommentData> selectPendingComments(@Param("taskId") Long taskId, @Param("limit") int limit);
}

