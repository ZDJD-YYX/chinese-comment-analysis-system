package com.example.commentanalysis;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 中文评论智能分析系统 启动类。
 *
 * <p>通过 {@link MapperScan} 扫描 Mapper 接口，无需在每个接口上重复标注 {@code @Mapper}。</p>
 *
 * @author 闫宇星
 */
@SpringBootApplication
@MapperScan("com.example.commentanalysis.mapper")
public class CommentAnalysisApplication {

    public static void main(String[] args) {
        SpringApplication.run(CommentAnalysisApplication.class, args);
    }
}
