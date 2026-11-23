package com.example.commentanalysis.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 关键词统计表实体，对应数据表 {@code keyword_statistics}。
 *
 * <p>保存任务级热点关键词及 TF-IDF 权重，支撑词云与热点词排名展示。
 * 通过 {@code sentiment} 区分全局热词（{@code ALL}）与分情感热词。</p>
 *
 * <p>唯一索引 {@code uk_task_word_sentiment (task_id, word, sentiment)} 防止同一任务
 * 同一情感维度下关键词重复；任务重试前会先清理旧热词，保证写入幂等。</p>
 *
 * @author 闫宇星
 */
@Data
@TableName("keyword_statistics")
public class KeywordStatistics implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 关键词编号，主键，数据库自增 */
    @TableId(value = "keyword_id", type = IdType.AUTO)
    private Long keywordId;

    /** 所属任务编号 */
    @TableField("task_id")
    private Long taskId;

    /** 关键词 */
    @TableField("word")
    private String word;

    /** TF-IDF 权重，降序排名依据 */
    @TableField("weight")
    private BigDecimal weight;

    /** 该词在评论集合中的词频 */
    @TableField("word_count")
    private Integer wordCount;

    /** 所属情感维度：ALL 全局 / POSITIVE / NEGATIVE / NEUTRAL */
    @TableField("sentiment")
    private String sentiment;

    /** 生成时间 */
    @TableField("create_time")
    private LocalDateTime createTime;
}
