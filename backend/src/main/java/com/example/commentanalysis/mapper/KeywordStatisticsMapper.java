package com.example.commentanalysis.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.commentanalysis.entity.KeywordStatistics;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * 关键词统计表 Mapper，继承 {@link BaseMapper} 获得通用 CRUD 能力。
 *
 * @author 闫宇星
 */
public interface KeywordStatisticsMapper extends BaseMapper<KeywordStatistics> {

    /**
     * 批量插入任务级热词。
     *
     * <p>单任务最多「全局 + 三类情感」共 4 组、每组 TopN（默认 50）条，
     * 一次多值 INSERT 即可完成，避免逐条插入的往返开销。</p>
     *
     * @param list 待插入的热词列表，非空
     * @return 实际插入的行数
     */
    @Insert("<script>"
            + "INSERT INTO keyword_statistics (task_id, word, weight, word_count, sentiment, create_time) VALUES "
            + "<foreach collection='list' item='item' separator=','>"
            + "(#{item.taskId}, #{item.word}, #{item.weight}, #{item.wordCount}, "
            + "#{item.sentiment}, #{item.createTime})"
            + "</foreach>"
            + "</script>")
    int insertBatch(@Param("list") List<KeywordStatistics> list);
}
