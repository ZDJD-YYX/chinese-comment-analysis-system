package com.example.commentanalysis.common;

import com.baomidou.mybatisplus.core.metadata.IPage;
import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 统一分页响应对象。
 *
 * <p>与《详细设计说明书》1.3.3 分页约定一致：请求使用 {@code pageNum}（从 1 开始）与
 * {@code pageSize}，响应统一使用本对象。</p>
 *
 * @param <T> 列表元素类型
 * @author 闫宇星
 */
@Data
public class PageVO<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 满足条件的总记录数 */
    private Long total;

    /** 当前页码，从 1 开始 */
    private Integer pageNum;

    /** 每页条数 */
    private Integer pageSize;

    /** 总页数，由 total 与 pageSize 计算得出 */
    private Integer pages;

    /** 当前页数据列表 */
    private List<T> list;

    /**
     * 由 MyBatis-Plus 分页对象与转换后的列表构建分页响应。
     *
     * @param page MyBatis-Plus 分页结果
     * @param list 当前页数据（可为实体，也可为 VO）
     * @param <T>  列表元素类型
     * @return 统一分页响应
     */
    public static <T> PageVO<T> of(IPage<?> page, List<T> list) {
        PageVO<T> vo = new PageVO<>();
        vo.setTotal(page.getTotal());
        vo.setPageNum((int) page.getCurrent());
        vo.setPageSize((int) page.getSize());
        vo.setPages((int) page.getPages());
        vo.setList(list);
        return vo;
    }
}
