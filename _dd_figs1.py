# -*- coding: utf-8 -*-
"""详细设计报告配图：包图、组件图、类图、时序图、物理 E-R 图。"""
from _dd_lib import *


# =====================================================================
# 图 2-1  后端代码包结构图
# =====================================================================
def fig_package():
    fig, ax = canvas(8.4, 6.0)
    title(ax, 4.2, 5.72, '后端代码包结构（com.example.commentanalysis）')

    rect(ax, 0.55, 5.25, 2.65, 0.42, fc=BLUE, round_=0.05)
    text(ax, 1.875, 5.46, 'com.example.commentanalysis', fs=8.4, weight='bold')
    ax.plot([0.55, 0.55], [1.90, 5.25], color=EC, lw=1.0, zorder=1)

    data = [
        # (x, y, w, h, 包名, 类清单, 底色)
        (1.05, 4.10, 1.75, 0.95, 'controller',
         'User / File / Input / Task\nResult / Dashboard / Settings\n（7 个）', GREEN),
        (2.95, 4.10, 1.75, 0.95, 'service / service.impl',
         'User / File / Input / Task\nResult / Dashboard / Settings\n7 接口 + 7 实现', GREEN),
        (4.85, 4.10, 1.75, 0.95, 'scheduler',
         'InferenceScheduler\nTaskRecoveryRunner', ORANGE),
        (6.75, 4.10, 1.55, 0.95, 'ai',
         'SentimentInferenceService\nModelRepository\nBertTokenizer 等 8 类', PURPLE),
        (1.05, 3.00, 1.75, 0.85, 'config',
         'AuthInterceptor\nWebMvcConfig\nInferenceProperties', GREY),
        (2.95, 3.00, 1.75, 0.85, 'common',
         'Result / ResultCode\nPageVO / BizException\nGlobalExceptionHandler', GREY),
        (4.85, 3.00, 1.75, 0.85, 'dto / vo',
         '11 个 DTO / 24 个 VO\nReviewDTO / SettingsVO', GREY),
        (6.75, 3.00, 1.55, 0.85, 'mapper',
         '6 个 Mapper 接口\n（继承 BaseMapper）', BLUE),
        (1.05, 1.90, 1.75, 0.85, 'entity',
         'AnalysisTask / CommentData\nAnalysisResult / TaskStatistics\nKeywordStatistics / SysUser', BLUE),
        (2.95, 1.90, 1.75, 0.85, 'input / validation',
         'InputTextProcessor\nWebPageReader\nImportValidator / Pending', '#FFFFFF'),
        (4.85, 1.90, 1.75, 0.85, 'resources',
         'static/index.html、js、css\napplication.yml', '#FFFFFF'),
        (6.75, 1.90, 1.55, 0.85, '启动类',
         'CommentAnalysis\nApplication', '#FFFFFF'),
    ]
    for x, y, w, h, name, classes, fc in data:
        ax.plot([0.55, x], [y + h / 2, y + h / 2], color=EC, lw=0.9, zorder=1)
        rect(ax, x, y, w, h, fc=fc, round_=0.05)
        text(ax, x + w / 2, y + h - 0.16, name, fs=7.8, weight='bold')
        text(ax, x + w / 2, y + (h - 0.30) / 2 - 0.02, classes, fs=6.5, lh=1.35)

    text(ax, 0.55, 1.42, '包依赖约束', fs=8.2, weight='bold', ha='left')
    text(ax, 0.55, 0.95,
         'controller → service → mapper → entity 单向依赖；scheduler 依赖 ai 与 mapper；\n'
         'ai 包不依赖任何业务包；common / config 为横切包；测试代码位于 src/test/java（7 个测试类、41 个用例）。',
         fs=7.4, ha='left', lh=1.6)
    save(fig, 'dd_package.png')


# =====================================================================
# 图 2-2  系统组件图
# =====================================================================
def fig_component():
    fig, ax = canvas(8.6, 5.4)
    title(ax, 4.3, 5.15, '系统组件图（运行期）')

    # 表示层
    box(ax, 0.30, 3.75, 1.85, 1.15, '表示层（浏览器）',
        ['index.html', 'api.js / app.js', 'charts.js / motion.js', 'ECharts 本地库'], fs=6.9)
    rect(ax, 0.30, 3.20, 1.85, 0.40, fc=GREY, round_=0.04)
    text(ax, 1.225, 3.40, '静态资源随 JAR 一起发布', fs=6.4)

    # 业务层容器
    rect(ax, 2.55, 2.45, 3.55, 2.45, fc='#F7FAFF', ec='#7C93B8', lw=1.0, round_=0.06, ls='--')
    text(ax, 2.72, 4.72, '业务层（Spring Boot 2.7.15）', fs=7.6, weight='bold', ha='left')
    box(ax, 2.75, 3.95, 1.55, 0.65, 'Controller ×7', ['参数校验 / 统一响应'], fs=6.5, tfs=7.2, fc=GREEN)
    box(ax, 4.45, 3.95, 1.45, 0.65, 'Service ×7', ['事务 / 业务规则'], fs=6.5, tfs=7.2, fc=GREEN)
    box(ax, 2.75, 3.05, 1.55, 0.65, 'Auth / Input / Audit', ['会话校验 / 网页抓取 / 审计'], fs=6.0, tfs=6.8, fc=GREY)
    box(ax, 4.45, 3.05, 1.45, 0.65, 'InferenceScheduler', ['异步批次调度'], fs=6.5, tfs=7.2, fc=ORANGE)
    box(ax, 2.75, 2.60, 3.15, 0.32, '推理线程池：core=2 / max=4 / queue=100 / AbortPolicy', fs=6.0, tfs=6.0, fc='white')

    # 数据访问层
    box(ax, 6.35, 3.95, 1.95, 0.70, 'Mapper ×6',
        ['MyBatis-Plus BaseMapper', '注解 SQL / 批量插入'], fs=6.6, tfs=7.2, fc=BLUE)
    ax.add_patch(Rectangle((6.68, 2.72), 1.30, 0.62, fc='#F4F6F8', ec=EC, lw=1.0, zorder=2))
    ax.add_patch(Ellipse((7.33, 3.34), 1.30, 0.22, fc='#F4F6F8', ec=EC, lw=1.0, zorder=3))
    text(ax, 7.33, 2.98, 'MySQL 8.0\ncomment_analysis', fs=6.5, lh=1.35)
    box(ax, 6.35, 2.05, 1.95, 0.45, 'HikariCP 连接池 min=5 / max=20', fs=6.0, tfs=6.0, fc=GREY)

    # 智能服务层
    rect(ax, 5.05, 0.40, 3.25, 1.55, fc='#FBF8FF', ec='#9B84C4', lw=1.0, round_=0.06, ls='--')
    text(ax, 5.20, 1.78, '智能服务层（ai 包）', fs=7.3, weight='bold', ha='left')
    box(ax, 5.20, 1.10, 1.45, 0.55, 'Sentiment\nInferenceService', fs=6.4, tfs=6.6, fc=PURPLE)
    box(ax, 6.80, 1.10, 1.35, 0.55, 'ModelRepository', ['单例常驻 Predictor'], fs=6.0, tfs=6.6, fc=PURPLE)
    box(ax, 5.20, 0.50, 2.95, 0.45, 'model.pt / vocab.txt / labels.txt（bert-zh-sentiment-v3）', fs=5.8, tfs=6.0, fc='white')

    # 配置组件
    box(ax, 0.30, 0.45, 1.85, 1.45, '配置与支撑',
        ['application.yml', 'ModelProperties', 'InferenceProperties', '日志 / Actuator'], fs=6.6, tfs=7.0, fc=GREY)

    # 连线
    arrow(ax, (2.15, 4.30), (2.75, 4.30), 'HTTP', ly=4.44)
    arrow(ax, (4.30, 4.28), (4.45, 4.28), '调用', ly=4.42)
    arrow(ax, (5.90, 4.27), (6.35, 4.27), 'SQL', ly=4.42)
    arrow(ax, (7.33, 3.95), (7.33, 3.36), 'JDBC')
    arrow(ax, (5.18, 3.95), (5.18, 3.70), '提交任务', lx=5.62, ly=3.82)
    arrow(ax, (5.90, 3.37), (6.35, 3.37), '读/写', ly=3.54)
    poly_arrow(ax, [(4.70, 3.05), (4.70, 1.90), (5.20, 1.90), (5.20, 1.65)],
               '批量推理', lx=4.90, ly=2.18, fs=6.4)
    arrow(ax, (6.65, 1.37), (6.80, 1.37), '委托', lx=6.92, ly=1.52)
    arrow(ax, (7.48, 1.10), (7.48, 0.95), '加载', lx=7.75, ly=1.02)
    arrow(ax, (2.15, 3.40), (2.75, 3.40), '拦截', ly=3.55, ls='--')
    arrow(ax, (2.15, 1.25), (2.55, 1.25), '读取配置', ly=1.40, ls='--')
    arrow(ax, (7.33, 2.72), (7.33, 2.50), '连接池', lx=7.62, ly=2.61, ls='--')
    text(ax, 4.3, 0.18, '说明：业务层不出现任何 DJL / NDArray 类型，只依赖 SentimentInferenceService 接口；'
                         '模型文件缺失时应用降级启动。', fs=6.4)
    save(fig, 'dd_component.png')


# =====================================================================
# 图 3-1  业务模块核心类图
# =====================================================================
def fig_class():
    fig, ax = canvas(8.8, 8.4)
    title(ax, 4.4, 8.10, '业务模块核心类图（Controller–Service–Mapper–Entity）')

    xs = [0.30, 2.35, 4.40, 6.45]
    ctrls = [
        ('UserController', ['-userService: UserService'],
         ['+login(dto, session): LoginVO', '+register(dto, session)', '+me(session): LoginVO', '+logout(session)']),
        ('FileController', ['-fileService / -taskService'],
         ['+upload(file): Result<Parse', '  ReportVO>']),
        ('TaskController', ['-taskService'],
         ['+list(pageNum,pageSize,status,kw)', '+detail / +delete', '+run / +cancel', '+progress(id): ProgressVO']),
        ('ResultController', ['-resultService'],
         ['+list(pageNum,pageSize,taskId,…)', '+statistics / +keywords', '+export(taskId, response)']),
    ]
    for x, (name, f, m) in zip(xs, ctrls):
        class_box(ax, x, 6.45, 1.85, 1.55, name, '«controller»', f, m, fs=5.9, nfs=7.6, fc=GREEN)

    ifaces = [
        ('UserService', ['+login(dto): LoginVO', '+register(dto): LoginVO']),
        ('FileService', ['+uploadAndParse(file)', '  : ParseReportVO']),
        ('AnalysisTaskService', ['+createTask / pageTasks', '+startInference / cancelTask / getProgress']),
        ('ResultService', ['+pageResults / statistics', '+keywords / export']),
    ]
    for x, (name, m) in zip(xs, ifaces):
        class_box(ax, x + 0.10, 5.16, 1.65, 1.05, name, '«interface»', [], m, fs=5.4, nfs=6.9, fc=BLUE)

    impl_specs = [
        ('UserServiceImpl', ['-passwordEncoder: BCrypt…', '-loginAttempts: Map'],
         ['+login(dto) / +register(dto)', '-matches(raw, user)', '-upgradePassword(…)', '-isLocked(key)']),
        ('FileServiceImpl', ['-taskMapper / -commentMapper', '-batchSize / -maxTextLength'],
         ['+uploadAndParse(file)', '-streamParseAndInsert(…)', '-detectCsvCharset(stream)', '-clean(raw): String', '«inner» ParseListener']),
        ('AnalysisTaskServiceImpl', ['-inferenceScheduler', 'extends ServiceImpl<M,E>'],
         ['+createTask / +pageTasks', '+startInference(taskId)', '+cancelTask(taskId)', '+getProgress(taskId)']),
        ('ResultServiceImpl', ['-resultMapper / -taskMapper', '-inferenceProperties'],
         ['+pageResults(…)', '+statistics(taskId)', '+keywords(taskId, senti, topN)', '+export(taskId, response)']),
    ]
    for x, (name, f, m) in zip(xs, impl_specs):
        class_box(ax, x - 0.05, 3.35, 1.95, 1.70, name, None, f, m, fs=5.5, nfs=6.8, fc='white')
        arrow(ax, (x + 0.925, 5.16), (x + 0.925, 5.05), None, ls='--', style='-|>')
        arrow(ax, (x + 0.925, 6.45), (x + 0.925, 6.21), None, ls='-', style='-|>')

    # Mapper 容器
    rect(ax, 0.30, 2.15, 5.95, 0.95, fc='#F5F8FD', ec='#7C93B8', lw=0.9, round_=0.04, ls='--')
    text(ax, 0.40, 2.97, 'mapper 包（6 个接口，均继承 BaseMapper<T>）', fs=7.2, weight='bold', ha='left')
    mappers = ['SysUserMapper', 'AnalysisTaskMapper', 'CommentDataMapper',
               'AnalysisResultMapper', 'KeywordStatisticsMapper', 'TaskStatisticsMapper']
    for i, m in enumerate(mappers):
        mx = 0.40 + (i % 3) * 1.95
        my = 2.52 - (i // 3) * 0.32
        rect(ax, mx, my - 0.14, 1.80, 0.26, fc='white', round_=0.03)
        text(ax, mx + 0.90, my - 0.01, m, fs=5.9)
    arrow(ax, (3.25, 3.35), (3.25, 3.12), 'MyBatis-Plus 通用 CRUD / 注解 SQL', fs=5.9)

    # Entity 容器
    rect(ax, 0.30, 0.85, 5.95, 0.95, fc='#F5F8FD', ec='#7C93B8', lw=0.9, round_=0.04, ls='--')
    text(ax, 0.40, 1.67, 'entity 包（6 个实体，@TableName 映射数据表）', fs=7.2, weight='bold', ha='left')
    ents = ['SysUser', 'AnalysisTask', 'CommentData', 'AnalysisResult', 'KeywordStatistics', 'TaskStatistics']
    for i, e in enumerate(ents):
        ex = 0.40 + (i % 3) * 1.95
        ey = 1.22 - (i // 3) * 0.32
        rect(ax, ex, ey - 0.14, 1.80, 0.26, fc='white', round_=0.03)
        text(ax, ex + 0.90, ey - 0.01, e, fs=5.9)
    arrow(ax, (3.25, 2.15), (3.25, 1.82), 'ORM 映射', fs=5.9)

    # 调度与智能服务（右下）
    class_box(ax, 6.45, 2.15, 1.95, 0.95, 'InferenceScheduler', None,
              ['-runningTaskIds / -cancelIds'],
              ['+submitAsync(taskId): boolean', '+run(taskId) / +cancel(taskId)'], fs=5.4, nfs=6.7, fc=ORANGE)
    class_box(ax, 6.45, 1.17, 1.95, 0.85, 'SentimentInferenceService', '«interface»', [],
              ['+batchInfer(List<String>)', '+extractKeywordsPerText(…)'], fs=5.2, nfs=5.6, fc=PURPLE)
    class_box(ax, 6.45, 0.36, 1.95, 0.62, 'ModelRepository', None,
              ['-model / -predictor: volatile'], ['+predict(List<String>): float[][]'], fs=5.4, nfs=6.7, fc=PURPLE)
    poly_arrow(ax, [(5.42, 3.35), (5.42, 2.62), (6.45, 2.62)], '调度异步任务', lx=5.95, ly=2.70, fs=5.8)
    arrow(ax, (7.42, 2.15), (7.42, 2.02), '委托', lx=7.68, ly=2.08, fs=5.6)
    arrow(ax, (7.42, 1.17), (7.42, 1.00), '调用', lx=7.68, ly=1.08, fs=5.6)

    text(ax, 0.30, 0.34, '图例：Controller → Service 为依赖；ServiceImpl 到 Service 为实现（虚线）；'
                         'ServiceImpl → Mapper → Entity 为分层调用与 ORM 映射。', fs=6.1, ha='left')
    text(ax, 0.30, 0.13, 'Controller 仅做参数接收与响应封装；ServiceImpl 承担业务规则与事务边界；'
                         '查询结果统一转换为 vo 包中的视图对象返回。', fs=6.1, ha='left')
    save(fig, 'dd_class.png')


# =====================================================================
# 图 3-2  登录与会话鉴权时序图
# =====================================================================
def fig_seq_login():
    fig, ax = canvas(8.4, 5.2)
    parts = [
        ('B', '浏览器', 0.65, 1.00, GREY),
        ('C', 'UserController', 1.95, 1.30, GREEN),
        ('S', 'UserServiceImpl', 3.45, 1.45, GREEN),
        ('E', 'BCrypt\nPasswordEncoder', 5.05, 1.05, '#FFFFFF'),
        ('M', 'SysUserMapper\n(MySQL)', 6.45, 1.35, BLUE),
        ('H', 'HttpSession', 7.55, 1.00, ORANGE),
    ]
    msgs = [
        ('B', 'C', 'POST /api/user/login {username,password}', 'call', 4.35),
        ('C', 'S', 'login(LoginDTO)  @Valid 校验非空', 'call', 4.05),
        ('S', 'S', 'isLocked(key)：5 分钟内失败 ≥5 次则拒绝', 'self', 3.72),
        ('S', 'M', 'selectOne(username)', 'call', 3.38),
        ('M', 'S', 'SysUser / null', 'return', 3.10),
        ('S', 'E', 'matches(rawPassword, passwordHash)', 'call', 2.80),
        ('E', 'S', 'true / false（兼容历史 SHA-256）', 'return', 2.52),
        ('S', 'M', '失败：recordFailure；成功：更新 last_login_time', 'call', 2.22),
        ('S', 'C', 'LoginVO 或 BizException(1001/401)', 'return', 1.92),
        ('C', 'H', 'setAttribute(LOGIN_USER_ID / LOGIN_USERNAME)', 'call', 1.62),
        ('C', 'B', 'Result{code:0,data:{userId,username}}', 'return', 1.32),
        ('B', 'B', '后续 /api/** 请求携带 JSESSIONID，AuthInterceptor 校验会话', 'self', 1.02),
    ]
    seq(ax, parts, msgs, top=4.65, bottom=0.75)
    text(ax, 0.35, 0.28, '说明：账号不存在与密码错误统一返回 1001，避免账号枚举；登录成功后失败计数清零，'
                         '历史 SHA-256 哈希在本次登录后透明升级为 BCrypt。', fs=6.4, ha='left')
    save(fig, 'dd_seq_login.png')


# =====================================================================
# 图 3-3  文件上传解析时序图
# =====================================================================
def fig_seq_upload():
    fig, ax = canvas(9.2, 5.7)
    parts = [
        ('B', '浏览器', 0.60, 0.95, GREY),
        ('C', 'FileController', 1.85, 1.20, GREEN),
        ('F', 'FileServiceImpl', 3.30, 1.35, GREEN),
        ('L', 'ParseListener', 4.85, 1.25, ORANGE),
        ('T', 'AnalysisTask\nMapper', 6.15, 1.20, BLUE),
        ('D', 'CommentData\nMapper', 7.40, 1.20, BLUE),
        ('S', 'InferenceScheduler', 8.55, 1.15, ORANGE),
    ]
    msgs = [
        ('B', 'C', 'POST /api/file/upload（multipart，≤50 MB）', 'call', 4.90),
        ('C', 'F', 'uploadAndParse(file)', 'call', 4.62),
        ('F', 'F', '校验扩展名（xlsx/xls/csv）与文件大小', 'self', 4.35),
        ('F', 'T', 'insert analysis_task（PENDING，快照 batch_size）', 'call', 4.05),
        ('T', 'F', 'taskId（自增主键）', 'return', 3.78),
        ('F', 'L', 'EasyExcel.read(headRowNumber=0) 流式回调', 'call', 3.50),
        ('L', 'L', '缓冲前 200 行，detectCommentColumn / 长度推断', 'self', 3.22),
        ('L', 'D', '每 1000 条 insertBatch(comment_data)', 'call', 2.92),
        ('L', 'F', 'ParseOutcome{total,valid,filtered,column}', 'return', 2.62),
        ('F', 'T', 'update total_count = validCount', 'call', 2.32),
        ('F', 'C', 'ParseReportVO（含 taskId）', 'return', 2.02),
        ('C', 'S', 'startInference(taskId)：事务提交后提交异步任务', 'call', 1.72),
        ('C', 'B', 'Result{code:0,data:ParseReportVO}', 'return', 1.20),
    ]
    seq(ax, parts, msgs, top=5.20, bottom=0.85)
    text(ax, 0.35, 0.44, '失败分支：解析或入库异常时调用 deletePhysically(taskId)，借助外键级联清理半成品数据后抛出业务异常；'
                         'CSV 先嗅探 BOM / UTF-8 / GBK 再解码。', fs=6.3, ha='left')
    text(ax, 0.35, 0.22, '异步分支：线程池队列满时 submitAsync 返回 false，接口提示「系统繁忙，请稍后重试」，任务保持待执行；'
                         '否则由推理线程异步执行。', fs=6.3, ha='left')
    save(fig, 'dd_seq_upload.png')


# =====================================================================
# 图 3-4  异步推理与进度轮询时序图
# =====================================================================
def fig_seq_infer():
    fig, ax = canvas(9.2, 6.5)
    parts = [
        ('B', '浏览器', 0.55, 0.95, GREY),
        ('C', 'TaskController', 1.85, 1.25, GREEN),
        ('V', 'AnalysisTask\nServiceImpl', 3.25, 1.30, GREEN),
        ('S', 'Inference\nScheduler', 4.70, 1.15, ORANGE),
        ('P', '推理线程池', 5.95, 1.00, ORANGE),
        ('A', 'Sentiment\nInferenceService', 7.20, 1.25, PURPLE),
        ('M', 'Mapper / MySQL\n（结果、任务、统计）', 8.45, 1.45, BLUE),
    ]
    msgs = [
        ('B', 'C', 'GET /api/task/{id}/progress（每 1.5 s）', 'call', 5.75),
        ('C', 'V', 'getProgress(taskId)', 'call', 5.48),
        ('V', 'M', 'selectById + total/processed 计算 percent', 'call', 5.22),
        ('V', 'C', 'ProgressVO{status,total,processed,percent}', 'return', 4.96),
        ('C', 'B', 'Result{code:0,data:ProgressVO}', 'return', 4.70),
        ('S', 'P', 'run(taskId)：runningTaskIds 去重', 'call', 4.36),
        ('P', 'S', '执行任务主循环', 'return', 4.10),
        ('S', 'M', 'markRunning；校验模型 isAvailable()', 'call', 3.82),
        ('S', 'M', '循环：selectPendingComments(taskId, batchSize=32)', 'call', 3.52),
        ('M', 'S', '本批待处理评论（反连接，不重不漏）', 'return', 3.26),
        ('S', 'A', 'batchInfer(texts) + extractKeywordsPerText()', 'call', 2.98),
        ('A', 'S', 'List<SentimentResult>（事务外执行）', 'return', 2.72),
        ('S', 'M', '短事务：insertBatch(analysis_result) + incrementProgress', 'call', 2.44),
        ('S', 'S', '批次边界检查终止标志；否则继续下一批', 'self', 2.16),
        ('S', 'M', '收尾事务：task_statistics + keyword_statistics + status=SUCCESS', 'call', 1.86),
        ('B', 'C', '下一轮轮询：status=SUCCESS，停止轮询并刷新结果', 'call', 1.52),
    ]
    seq(ax, parts, msgs, top=6.05, bottom=1.05)
    text(ax, 0.35, 0.42, '续跑语义：批次以「尚无结果的评论」为输入，配合唯一索引 uk_task_comment(task_id, comment_id) 保证幂等；'
                         '进度按数据库原子累加，重试不抹除历史进度。', fs=6.3, ha='left')
    save(fig, 'dd_seq_infer.png')


# =====================================================================
# 图 3-5  物理数据模型（E-R 图）
# =====================================================================
def fig_er():
    fig, ax = canvas(8.2, 5.9)
    title(ax, 4.1, 5.65, '物理数据模型（6 张表及外键约束）')

    def table(x, y, w, h, name, rows, fc=BLUE):
        rect(ax, x, y, w, h, fc='white', ec=EC, lw=1.1, round_=0.04)
        rect(ax, x, y + h - 0.28, w, 0.28, fc=fc, ec=EC, lw=1.1, round_=0.04)
        text(ax, x + w / 2, y + h - 0.14, name, fs=7.4, weight='bold')
        for i, r in enumerate(rows):
            text(ax, x + 0.07, y + h - 0.40 - i * 0.165, r, fs=5.9, ha='left', va='top')

    table(0.30, 4.25, 1.95, 1.10, 'sys_user', [
        'PK user_id      BIGINT',
        '   username     VARCHAR(50)',
        '   password_hash VARCHAR(100)',
        '   salt / status / last_login_time',
    ], GREEN)
    table(3.15, 3.75, 2.25, 1.60, 'analysis_task', [
        'PK task_id        BIGINT',
        'FK user_id        BIGINT',
        '   task_name / file_name / file_size',
        '   model_version / batch_size',
        '   total / processed / error_count',
        '   status / start / finish / error_message',
        '   is_deleted（逻辑删除）',
    ], ORANGE)
    table(0.55, 1.70, 1.95, 1.30, 'comment_data', [
        'PK comment_id  BIGINT',
        'FK task_id     BIGINT',
        '   content     VARCHAR(512)',
        '   row_no / comment_time',
        '   create_time',
    ], BLUE)
    table(3.30, 1.30, 2.15, 1.65, 'analysis_result', [
        'PK result_id     BIGINT',
        'FK task_id       BIGINT',
        'FK comment_id    BIGINT',
        '   sentiment      VARCHAR(16)',
        '   confidence     DECIMAL(6,4)',
        '   keywords / need_review / reviewed',
        '   original_sentiment / infer_time_ms',
    ], BLUE)
    table(6.15, 4.10, 1.95, 1.25, 'task_statistics', [
        'PK stat_id     BIGINT',
        'FK task_id     BIGINT UNIQUE',
        '   positive / negative / neutral_count',
        '   review / error_count',
        '   avg_confidence / total_infer_time_ms',
    ], PURPLE)
    table(6.15, 1.75, 1.95, 1.15, 'keyword_statistics', [
        'PK keyword_id  BIGINT',
        'FK task_id     BIGINT',
        '   word / weight / word_count',
        '   sentiment（ALL/POS/NEG/NEU）',
    ], PURPLE)

    # 关系线
    arrow(ax, (2.25, 4.80), (3.15, 4.80), None, style='-', lw=1.1)
    text(ax, 2.62, 4.90, '1', fs=6.4)
    text(ax, 3.05, 4.90, 'N', fs=6.4)

    poly_arrow(ax, [(3.60, 3.75), (3.60, 3.30), (2.50, 3.30), (2.50, 3.00)], None)
    text(ax, 2.85, 3.38, '1', fs=6.4)
    text(ax, 2.58, 3.06, 'N', fs=6.4)

    poly_arrow(ax, [(4.30, 3.75), (4.30, 2.90)], None)
    text(ax, 4.38, 3.35, '1', fs=6.4)
    text(ax, 4.38, 2.96, 'N', fs=6.4)

    arrow(ax, (2.50, 2.20), (3.30, 2.20), None, style='-', lw=1.1)
    text(ax, 2.78, 2.31, '1', fs=6.4)
    text(ax, 3.22, 2.31, '1', fs=6.4)
    text(ax, 2.90, 2.02, 'uk_task_comment', fs=5.6)

    poly_arrow(ax, [(5.40, 4.30), (6.15, 4.30)], None)
    text(ax, 5.62, 4.41, '1', fs=6.4)
    text(ax, 6.05, 4.41, '1', fs=6.4)
    text(ax, 5.55, 4.02, 'uk_task', fs=5.8)

    poly_arrow(ax, [(5.40, 3.95), (5.85, 3.95), (5.85, 2.35), (6.15, 2.35)], None)
    text(ax, 5.48, 4.04, '1', fs=6.4)
    text(ax, 6.05, 2.45, 'N', fs=6.4)
    text(ax, 7.10, 3.55, 'uk_task_word_sentiment', fs=5.3)

    text(ax, 0.30, 0.95, '外键约束：均 ON DELETE CASCADE；字符集 utf8mb4；', fs=6.4, ha='left')
    text(ax, 0.30, 0.68, 'analysis_task.is_deleted 为逻辑删除标记，业务查询由 MyBatis-Plus 自动追加 is_deleted = 0。', fs=6.4, ha='left')
    text(ax, 0.30, 0.38, '冗余 task_id 于 analysis_result / keyword_statistics，避免结果查询与统计时回连任务表。', fs=6.4, ha='left')
    save(fig, 'dd_er.png')


if __name__ == '__main__':
    fig_package()
    fig_component()
    fig_class()
    fig_seq_login()
    fig_seq_upload()
    fig_seq_infer()
    fig_er()
