package com.example.commentanalysis.scheduler;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.example.commentanalysis.entity.AnalysisTask;
import com.example.commentanalysis.mapper.AnalysisTaskMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * 服务重启恢复器。
 *
 * <p>应用启动时扫描 {@code status = RUNNING} 的任务并置为 {@code FAILED}。
 * 进程被强制终止时任务会永久停留在执行中，通过本恢复动作使其可被重试
 * （对应用例规约 E-5、NFR-R-01）。恢复失败不阻断应用启动。</p>
 *
 * @author 闫宇星
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class TaskRecoveryRunner implements ApplicationRunner {

    /** 任务状态：执行中 */
    private static final String STATUS_RUNNING = "RUNNING";

    /** 任务状态：失败 */
    private static final String STATUS_FAILED = "FAILED";

    private final AnalysisTaskMapper analysisTaskMapper;

    @Override
    public void run(ApplicationArguments args) {
        try {
            LocalDateTime now = LocalDateTime.now();
            LambdaUpdateWrapper<AnalysisTask> update = new LambdaUpdateWrapper<AnalysisTask>()
                    .eq(AnalysisTask::getStatus, STATUS_RUNNING)
                    .set(AnalysisTask::getStatus, STATUS_FAILED)
                    .set(AnalysisTask::getFinishTime, now)
                    .set(AnalysisTask::getUpdateTime, now);
            int count = analysisTaskMapper.update(null, update);
            if (count > 0) {
                log.warn("检测到 {} 个上次运行中断的任务，已置为 FAILED，可在任务列表执行重试", count);
            }
        } catch (Exception e) {
            // 数据库不可用等情况下不阻断启动，仅记录错误
            log.error("启动时恢复 RUNNING 任务失败（不影响应用启动）：{}", e.getMessage(), e);
        }
    }
}
