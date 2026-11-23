package com.example.commentanalysis.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 推理任务线程池配置。
 *
 * <p>分析任务异步执行，不阻塞上传与查询等交互操作（对应《概要设计说明书》7.3 关键配置项）。
 * 线程池随 Spring 容器关闭而优雅停止。</p>
 *
 * @author 闫宇星
 */
@Configuration
public class InferenceExecutorConfig {

    /** 推理任务线程池核心线程数 */
    @Value("${app.task.pool.core-size:2}")
    private int coreSize;

    /** 推理任务线程池最大线程数 */
    @Value("${app.task.pool.max-size:4}")
    private int maxSize;

    /** 任务等待队列容量 */
    @Value("${app.task.pool.queue-capacity:100}")
    private int queueCapacity;

    /**
     * 推理专用线程池。
     *
     * <p>队列满时直接拒绝（{@link ThreadPoolExecutor.AbortPolicy}），由调度器捕获后
     * 向用户返回“系统繁忙、请稍后重试”。不使用 CallerRunsPolicy：
     * 否则第 N 个上传请求会在 Tomcat 线程里同步跑完整套推理，导致请求长时间阻塞。</p>
     *
     * @return 线程池实例
     */
    @Bean(name = "inferenceExecutor", destroyMethod = "shutdown")
    public ExecutorService inferenceExecutor() {
        return new ThreadPoolExecutor(
                coreSize,
                maxSize,
                60L,
                TimeUnit.SECONDS,
                new LinkedBlockingQueue<>(queueCapacity),
                new NamedThreadFactory("inference-"),
                new ThreadPoolExecutor.AbortPolicy());
    }

    /**
     * 命名线程工厂，便于日志中区分推理线程。
     */
    private static class NamedThreadFactory implements ThreadFactory {

        private final AtomicInteger counter = new AtomicInteger(1);

        private final String prefix;

        NamedThreadFactory(String prefix) {
            this.prefix = prefix;
        }

        @Override
        public Thread newThread(Runnable runnable) {
            Thread thread = new Thread(runnable, prefix + counter.getAndIncrement());
            thread.setDaemon(false);
            return thread;
        }
    }
}
