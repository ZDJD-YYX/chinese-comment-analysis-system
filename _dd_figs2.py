# -*- coding: utf-8 -*-
"""详细设计报告配图：AI 模块、流程图、前端结构、异常处理、分支策略。"""
from _dd_lib import *


# =====================================================================
# 图 4-1  智能模块类图
# =====================================================================
def fig_ai_class():
    fig, ax = canvas(8.4, 5.9)
    title(ax, 4.2, 5.62, '智能模块类图（ai 包）')

    class_box(ax, 2.75, 4.35, 2.55, 1.10, 'SentimentInferenceService', '«interface»', [],
              ['+isAvailable(): boolean', '+batchInfer(texts): List<SentimentResult>',
               '+extractKeywordsPerText(texts, max)'], fs=5.6, nfs=6.7, fc=PURPLE)

    class_box(ax, 2.55, 2.75, 2.95, 1.40, 'SentimentInferenceServiceImpl', None,
              ['-modelRepository / -textPreprocessor', '-keywordExtractor / -inferenceProperties'],
              ['+batchInfer(texts)', '+extractKeywords / +extractKeywordsPerText',
               '-toResult(prob, labels, threshold, ms)'], fs=5.5, nfs=6.5, fc='white')
    arrow(ax, (4.02, 4.35), (4.02, 4.15), None, ls='--', style='-|>')

    class_box(ax, 5.75, 2.60, 2.35, 1.55, 'ModelRepository', None,
              ['-model: ZooModel（volatile）', '-predictor: Predictor（volatile）', '-tokenizer / labels / available'],
              ['@PostConstruct +init()', '+loadModel(): ModelInfoVO', '+predict(texts): float[][]'], fs=5.4, nfs=6.6, fc='white')

    class_box(ax, 0.30, 2.90, 1.95, 1.25, 'TextPreprocessor', None,
              ['-inferenceProperties'], ['+clean(raw): String', '+cleanBatch(texts)', '+isBlank(text)'], fs=5.5, nfs=6.7, fc='white')
    class_box(ax, 0.30, 1.35, 1.95, 1.40, 'KeywordExtractor', None,
              ['-STOPWORDS: Set<String>'],
              ['+segment(text): List<String>', '+extract(texts, topN)', '+tagDocuments(…)', '+newAccumulator()'], fs=5.4, nfs=6.7, fc='white')
    class_box(ax, 5.75, 1.15, 2.35, 1.25, 'BertTokenizer', None,
              ['-vocab: Map<String,Integer>', '-maxLength = 128'],
              ['+encode(texts): EncodedBatch', '-basicTokenize / -wordPiece'], fs=5.4, nfs=6.7, fc='white')
    box(ax, 5.75, 0.35, 2.35, 0.65, 'DJL PyTorch Engine',
        ['ZooModel + Predictor（单例常驻）', 'libtorch CPU / TorchScript'], fs=6.0, tfs=6.7, fc=ORANGE)
    box(ax, 0.30, 0.45, 1.95, 0.70, '配置类',
        ['ModelProperties', 'InferenceProperties'], fs=6.2, tfs=6.8, fc=GREY)

    arrow(ax, (5.50, 3.45), (5.72, 3.45), '调用 predict', ly=3.60, fs=5.8)
    arrow(ax, (2.25, 3.50), (2.52, 3.50), 'cleanBatch', ly=3.63, fs=5.8)
    arrow(ax, (2.25, 2.30), (2.52, 3.15), 'tagDocuments', fs=5.8, rad=-0.15, lx=2.40, ly=2.50)
    arrow(ax, (6.93, 2.60), (6.93, 2.40), 'encode', fs=5.8)
    arrow(ax, (6.93, 1.15), (6.93, 1.00), '前向推理', fs=5.8)
    text(ax, 4.2, 0.22, '依赖注入：ModelProperties → ModelRepository；InferenceProperties → ServiceImpl / TextPreprocessor',
         fs=5.9)
    save(fig, 'dd_ai_class.png')


# =====================================================================
# 图 4-2  模型加载与降级流程图
# =====================================================================
def fig_model_load():
    fig, ax = canvas(7.6, 6.9)
    title(ax, 3.8, 6.62, '模型加载与降级流程（应用启动阶段）')

    ellipse(ax, 2.35, 6.10, 1.7, 0.48, '应用启动', fs=7.4, fc=GREEN)
    steps = [
        (5.35, 'resolveModelDir(path)', '支持文件系统路径 / classpath:'),
        (4.62, 'validateModelFiles(dir)', '校验 model.pt / vocab.txt / labels.txt'),
        (3.89, 'readLabels + new BertTokenizer', '标签顺序即类别 id；词表 21128 行'),
        (3.16, 'DJL Criteria.builder()', 'PyTorch / CPU / mapLocation=cpu / training=false'),
        (2.43, 'criteria.loadModel() + newPredictor()', '模型与推理器常驻内存'),
        (1.70, 'available = true + buildModelInfo()', '合并 model_info.json 中的准确率等'),
    ]
    for i, (y, name, desc) in enumerate(steps):
        rect(ax, 0.90, y - 0.25, 2.90, 0.50, fc='white', round_=0.05)
        text(ax, 2.35, y + 0.06, name, fs=6.8, weight='bold')
        text(ax, 2.35, y - 0.12, desc, fs=5.9)

    arrow(ax, (2.35, 5.86), (2.35, 5.60))
    for y1, y2 in [(5.35, 4.62), (4.62, 3.89), (3.89, 3.16), (3.16, 2.43), (2.43, 1.70)]:
        arrow(ax, (2.35, y1 - 0.25), (2.35, y2 + 0.25))
    ellipse(ax, 2.35, 1.15, 1.7, 0.48, '加载完成', fs=7.2, fc=GREEN)
    arrow(ax, (2.35, 1.45), (2.35, 1.39))

    # 异常分支
    box(ax, 4.55, 5.05, 2.65, 0.55, '捕获加载异常', ['记录 modelDir 与异常堆栈'], fs=6.2, tfs=6.8, fc='#FDECEC')
    for y in (4.62, 3.89, 3.16, 2.43):
        arrow(ax, (3.80, y), (4.55, 5.25), None, ls='--', lw=0.9)
    diamond(ax, 5.85, 4.25, 1.45, 0.90, 'fail-fast\n= true ?', fs=6.6)
    arrow(ax, (5.85, 5.05), (5.85, 4.70))
    box(ax, 4.65, 3.05, 2.40, 0.65, '抛出 IllegalStateException', ['阻断应用启动（严格模式）'], fs=6.1, tfs=6.4, fc='#FDECEC')
    box(ax, 4.65, 2.20, 2.40, 0.60, 'available = false，记录 ERROR 日志', ['应用继续启动；推理接口返回 3001'], fs=6.1, tfs=6.4, fc=ORANGE)
    arrow(ax, (5.55, 3.80), (5.55, 3.70), 'true', fs=5.8, lx=5.32, ly=3.85)
    poly_arrow(ax, [(6.58, 4.25), (7.18, 4.25), (7.18, 2.50), (7.05, 2.50)], 'false', lx=7.28, ly=3.55, fs=5.8)
    text(ax, 6.35, 1.75, '默认 fail-fast = false：\n模型缺失不阻塞登录、\n任务查询等其余功能。', fs=6.0, ha='left', lh=1.5)
    save(fig, 'dd_model_load.png')


# =====================================================================
# 图 4-3  批量情感推理流程图
# =====================================================================
def fig_infer_flow():
    fig, ax = canvas(8.0, 7.2)
    title(ax, 4.0, 6.92, '批量情感推理流程（SentimentInferenceServiceImpl.batchInfer）')

    ellipse(ax, 2.55, 6.42, 2.0, 0.48, 'batchInfer(texts)', fs=7.2, fc=PURPLE)
    steps = [
        (5.70, 'textPreprocessor.cleanBatch(texts)', '去零宽字符 / 空白折叠 / 截断 512 字符'),
        (4.98, '初始化结果列表', '全部填 SentimentResult.fallback(false)，保证下标对齐'),
        (4.26, '筛出非空样本 pending', '空文本不送模型，保留兜底结果'),
    ]
    for y, name, desc in steps:
        rect(ax, 0.75, y - 0.25, 3.60, 0.50, fc='white', round_=0.05)
        text(ax, 2.55, y + 0.06, name, fs=6.7, weight='bold')
        text(ax, 2.55, y - 0.12, desc, fs=5.8)
    arrow(ax, (2.55, 6.18), (2.55, 5.95))
    arrow(ax, (2.55, 5.45), (2.55, 5.23))
    arrow(ax, (2.55, 4.73), (2.55, 4.51))

    diamond(ax, 2.55, 3.55, 2.15, 0.82, 'pending 为空 ?', fs=6.8)
    arrow(ax, (2.55, 4.01), (2.55, 3.96))
    box(ax, 0.30, 2.95, 1.55, 0.42, '直接返回兜底结果', fs=6.2, tfs=6.4, fc='white')
    poly_arrow(ax, [(1.475, 3.55), (1.08, 3.55), (1.08, 3.37)], '是', lx=1.22, ly=3.68, fs=5.8)
    poly_arrow(ax, [(1.08, 2.95), (0.20, 2.95), (0.20, 0.22), (1.50, 0.22)], None)

    diamond(ax, 2.55, 2.62, 2.15, 0.80, '模型可用 ?', fs=6.8)
    arrow(ax, (2.55, 3.14), (2.55, 3.02))
    box(ax, 4.55, 2.42, 2.75, 0.45, '整批返回兜底（error=true）', fs=6.2, tfs=6.5, fc='#FDECEC')
    arrow(ax, (3.62, 2.62), (4.55, 2.62), '否', fs=5.8, lx=4.05, ly=2.75)

    rect(ax, 0.75, 1.78, 3.60, 0.42, fc='white', round_=0.05)
    text(ax, 2.55, 1.99, 'BertTokenizer.encode → input_ids / mask / token_type_ids', fs=6.4, weight='bold')
    arrow(ax, (2.55, 2.22), (2.55, 2.20))
    rect(ax, 0.75, 1.18, 3.60, 0.42, fc='white', round_=0.05)
    text(ax, 2.55, 1.39, 'synchronized(predictor).predict → logits [B, 3]', fs=6.4, weight='bold')
    arrow(ax, (2.55, 1.78), (2.55, 1.60))
    rect(ax, 0.75, 0.58, 3.60, 0.42, fc='white', round_=0.05)
    text(ax, 2.55, 0.79, 'softmax(1) → argmax → label / score / needReview', fs=6.4, weight='bold')
    arrow(ax, (2.55, 1.18), (2.55, 1.00))

    ellipse(ax, 2.55, 0.22, 2.1, 0.40, '返回 List<SentimentResult>', fs=6.8, fc=GREEN)
    arrow(ax, (2.55, 0.58), (2.55, 0.42))

    # 异常回退
    box(ax, 4.55, 1.18, 2.85, 0.62, '捕获批次异常 → 逐条重试', ['单条成功则写入结果，失败置兜底'], fs=6.1, tfs=6.5, fc='#FDECEC')
    arrow(ax, (4.35, 1.39), (4.55, 1.39), '异常', fs=5.8, lx=4.45, ly=1.52)
    arrow(ax, (5.98, 1.18), (3.60, 0.24), None, ls='--')
    save(fig, 'dd_infer_flow.png')


# =====================================================================
# 图 5-1  前端视图与组件结构
# =====================================================================
def fig_front_tree():
    fig, ax = canvas(8.2, 6.5)
    title(ax, 4.1, 6.22, '前端视图与组件结构（单页应用）')

    box(ax, 3.05, 5.45, 2.10, 0.45, 'index.html', ['唯一页面容器'], fs=6.4, tfs=7.2, fc=GREY)

    # 登录视图
    rect(ax, 0.35, 3.35, 2.45, 1.75, fc='#F7FAFF', ec='#7C93B8', lw=1.0, round_=0.05, ls='--')
    text(ax, 1.575, 4.92, '#loginView  登录视图', fs=7.0, weight='bold')
    login_items = ['auth__intro：品牌 / 说明 / 能力清单',
                   'auth-card：账号、密码输入',
                   'authSubmit：登录 / 注册提交',
                   'authSwitch：登录 / 注册切换',
                   'authError：表单错误提示']
    for i, it in enumerate(login_items):
        text(ax, 0.50, 4.62 - i * 0.25, '• ' + it, fs=6.1, ha='left')

    # 工作台视图
    rect(ax, 3.05, 0.75, 4.85, 4.45, fc='#F7FAFF', ec='#7C93B8', lw=1.0, round_=0.05, ls='--')
    text(ax, 5.47, 5.02, '#appView  主界面（左侧导航 + 内容区）', fs=6.8, weight='bold')

    rect(ax, 3.20, 2.55, 1.95, 2.30, fc='white', ec=EC, lw=0.9, round_=0.04)
    text(ax, 4.175, 4.68, 'aside.rail  左栏', fs=6.7, weight='bold')
    rail_items = ['navRail：工作台/看板/对比/设置', 'brand / logoutBtn',
                  'smartInput：文本 / 链接', 'dropzone + fileInput',
                  'uploadMeter / taskSearch', 'taskList / taskPager', 'railUser（当前用户）']
    for i, it in enumerate(rail_items):
        text(ax, 3.33, 4.42 - i * 0.245, '• ' + it, fs=5.5, ha='left')

    rect(ax, 5.30, 2.55, 2.45, 2.30, fc='white', ec=EC, lw=0.9, round_=0.04)
    text(ax, 6.525, 4.68, 'main  右栏', fs=6.7, weight='bold')
    main_items = ['taskbar：状态/重跑/终止/重命名/删除',
                  'runBar：实时进度条',
                  'summary：三类计数 + 指标',
                  'pie：#pieChart 情感饼图',
                  'cloud / rankList：词云 + 排名',
                  'trend：#trendChart 趋势',
                  'confidence：#confidenceChart 置信度',
                  'reviewQuality：复核质量',
                  'table：筛选/复核/导出/分页']
    for i, it in enumerate(main_items):
        text(ax, 5.43, 4.42 - i * 0.205, '• ' + it, fs=5.3, ha='left')

    box(ax, 3.20, 1.05, 4.55, 1.20, '内容区视图（按导航切换）', [
        'dashboardView：跨任务看板 / compareView：任务对比',
        'settingsView：模型信息 / 推理参数 / 操作日志',
        'reviewDialog：单条 / 批量复核；card--table：明细 + pager'], fs=5.6, tfs=6.4, fc=ORANGE)

    box(ax, 5.55, 0.20, 2.30, 0.40, '#toastHost  轻提示容器', fs=6.2, tfs=6.6, fc=GREY)

    arrow(ax, (4.10, 5.45), (1.58, 5.10), '未登录', fs=5.8, rad=0.0)
    arrow(ax, (5.10, 5.45), (5.47, 5.20), '已登录', fs=5.8)
    arrow(ax, (4.175, 2.55), (4.175, 2.25), None)
    arrow(ax, (6.525, 2.55), (6.525, 2.25), None)

    # 脚本层
    box(ax, 0.35, 1.70, 2.45, 1.20, '脚本与样式', [
        'api.js：请求封装 / 统一拆包', 'app.js：状态与交互',
        'charts.js：ECharts 配置', 'motion.js / style.css'], fs=5.9, tfs=6.6, fc=GREEN)
    arrow(ax, (2.80, 2.30), (3.20, 2.30), '驱动', fs=5.8)
    text(ax, 0.35, 0.75, '注：页面为原生 HTML/CSS/JS 单页结构，无前端框架；\n'
                         '图表库与词云插件均本地化，离线可用。', fs=6.0, ha='left', lh=1.5)
    save(fig, 'dd_front_tree.png')


# =====================================================================
# 图 5-2  前端交互时序图
# =====================================================================
def fig_front_seq():
    fig, ax = canvas(9.0, 6.0)
    parts = [
        ('U', '用户', 0.55, 0.90, GREY),
        ('J', 'app.js', 1.85, 1.00, GREEN),
        ('A', 'api.js', 3.20, 1.00, BLUE),
        ('B', '后端服务', 4.75, 1.10, ORANGE),
        ('C', 'charts.js / ECharts', 6.70, 1.75, PURPLE),
        ('D', '浏览器下载', 8.20, 1.15, GREY),
    ]
    msgs = [
        ('U', 'J', '页面加载 / 登录 / 选择文件', 'call', 5.00),
        ('J', 'A', "api.get('/api/user/me')", 'call', 4.72),
        ('A', 'B', 'GET /api/user/me', 'call', 4.46),
        ('B', 'A', 'Result{code,message,data}', 'return', 4.20),
        ('A', 'J', 'data（失败抛 ApiError）', 'return', 3.94),
        ('J', 'A', "api.upload('/api/file/upload', file)", 'call', 3.62),
        ('A', 'B', 'POST multipart（XHR 上传进度）', 'call', 3.36),
        ('B', 'A', 'ParseReportVO{taskId,validCount,…}', 'return', 3.10),
        ('J', 'J', '每 1500 ms 轮询 progress，终态停止', 'self', 2.76),
        ('J', 'A', '并发加载 statistics / keywords / results', 'call', 2.42),
        ('A', 'B', 'GET /api/result/*', 'call', 2.16),
        ('B', 'A', '统计、词云、明细分页数据', 'return', 1.90),
        ('J', 'C', 'renderPie() / renderCloud() / renderRank()', 'call', 1.58),
        ('U', 'J', '点击「导出结果」', 'call', 1.24),
        ('J', 'A', "api.download('/api/result/export/{id}')", 'call', 0.98),
        ('A', 'D', 'Blob + <a download> 保存 xlsx', 'call', 0.72),
    ]
    seq(ax, parts, msgs, top=5.45, bottom=0.50, fs=6.1)
    text(ax, 0.35, 0.20, '说明：api.js 统一拆解 {code,message,data}，遇 401/1002 触发重新登录；'
                         '轮询用 polling 标记避免请求叠加，过期响应按 taskId 丢弃。', fs=6.2, ha='left')
    save(fig, 'dd_front_seq.png')


# =====================================================================
# 图 6-1  全局异常处理机制
# =====================================================================
def fig_exception():
    fig, ax = canvas(8.2, 5.9)
    title(ax, 4.1, 5.62, '全局异常处理与统一响应机制')

    box(ax, 2.85, 4.95, 1.90, 0.42, 'HTTP 请求', fs=6.8, tfs=7.0, fc=GREY)
    diamond(ax, 3.80, 4.30, 1.55, 0.72, '会话有效 ?', fs=6.6)
    arrow(ax, (3.80, 4.95), (3.80, 4.66))

    box(ax, 0.30, 4.05, 1.65, 0.48, '返回 401 + 统一 JSON', ['前端跳转登录页'], fs=6.0, tfs=6.2, fc='#FDECEC')
    arrow(ax, (3.02, 4.30), (1.95, 4.30), '否', fs=5.8, lx=2.50, ly=4.42)

    box(ax, 2.95, 3.45, 1.70, 0.42, 'Controller', ['@Valid 参数校验'], fs=6.3, tfs=6.6, fc=GREEN)
    arrow(ax, (3.80, 3.94), (3.80, 3.87), '是', fs=5.8, lx=3.95, ly=3.90)

    box(ax, 2.95, 2.70, 1.70, 0.42, 'Service', ['业务规则 / 事务'], fs=6.3, tfs=6.6, fc=GREEN)
    arrow(ax, (3.80, 3.45), (3.80, 3.12))

    box(ax, 2.95, 1.95, 1.70, 0.42, 'Mapper / MySQL', ['MyBatis-Plus'], fs=6.3, tfs=6.6, fc=BLUE)
    arrow(ax, (3.80, 2.70), (3.80, 2.37))

    box(ax, 2.75, 1.20, 2.10, 0.42, '返回 Result{code:0,data}', ['HTTP 200'], fs=6.3, tfs=6.6, fc='#EAF5EE')
    arrow(ax, (3.80, 1.95), (3.80, 1.62), '正常', fs=5.8, lx=3.95, ly=1.78)

    # 异常汇聚
    exc = [
        (3.45, '参数校验失败', '400 / BAD_REQUEST'),
        (2.70, 'BizException', '业务码 / 401 用 HTTP 401'),
        (1.95, 'DataAccess / DuplicateKey', '500 / 409'),
    ]
    for y, name, code in exc:
        box(ax, 4.95, y - 0.26, 2.35, 0.52, name, [code], fs=5.7, tfs=6.0, fc='#FDECEC')
        arrow(ax, (4.65, y), (4.95, y), None, ls='--')
        ax.plot([7.30, 7.58], [y, y], color=EC, lw=0.8, ls='--', zorder=3)

    box(ax, 4.95, 0.40, 2.35, 0.52, 'GlobalExceptionHandler', ['@RestControllerAdvice 统一转换'], fs=6.2, tfs=6.6, fc=ORANGE)
    ax.plot([7.58, 7.58], [0.66, 3.45], color=EC, lw=0.8, ls='--', zorder=3)
    arrow(ax, (7.58, 0.66), (7.30, 0.66), None, ls='-', lw=0.9)
    text(ax, 2.95, 0.52, '异常不向控制器抛出，\n前端只处理 {code,message,data}', fs=6.0, ha='left', lh=1.5)
    save(fig, 'dd_exception.png')


# =====================================================================
# 图 7-1  Git 分支管理策略
# =====================================================================
def fig_git():
    fig, ax = canvas(8.2, 5.0)
    title(ax, 4.1, 4.75, 'Git 分支管理策略')

    box(ax, 3.20, 3.95, 1.85, 0.52, 'main', ['仅保留可发布版本'], fs=5.9, tfs=7.0, fc='#FDECEC')
    box(ax, 3.20, 2.75, 1.85, 0.52, 'develop', ['集成日常开发'], fs=5.9, tfs=7.0, fc='#EAF1FB')
    box(ax, 0.55, 1.45, 2.30, 0.72, 'feature/*', ['feature/user-auth', 'feature/file-parse', 'feature/ai-inference'], fs=5.7, tfs=6.8, fc='#EAF5EE')
    box(ax, 3.20, 1.45, 1.85, 0.60, 'release/1.0', ['冻结功能，只修缺陷'], fs=5.7, tfs=6.8, fc='#FDF2E6')
    box(ax, 6.05, 2.75, 1.95, 0.60, 'hotfix/1.0.1', ['从 main 拉出紧急修复'], fs=5.6, tfs=6.6, fc='#F1EDF9')

    arrow(ax, (3.55, 2.75), (2.45, 2.17), '拉出', lx=2.72, ly=2.56, fs=5.8)
    arrow(ax, (2.85, 2.17), (3.85, 2.75), None, ls='--')
    arrow(ax, (3.55, 2.75), (3.55, 2.05), '冻结', lx=3.72, ly=2.42, fs=5.8)
    poly_arrow(ax, [(3.20, 1.75), (2.96, 1.75), (2.96, 4.20), (3.20, 4.20)], None)
    text(ax, 2.86, 3.05, '验收通过', fs=5.6, rotation=90)
    arrow(ax, (4.60, 3.95), (4.60, 3.27), '回合并', lx=4.76, ly=3.62, fs=5.8, ls='--')
    poly_arrow(ax, [(5.05, 4.18), (6.55, 4.18), (6.55, 3.35)], '紧急修复', lx=5.75, ly=4.00, fs=5.8)
    poly_arrow(ax, [(6.55, 3.35), (6.55, 4.40), (5.05, 4.40)], '合入 main', lx=5.85, ly=4.50, fs=5.8, ls='--')
    arrow(ax, (6.05, 2.95), (5.05, 2.95), '同步回 develop', lx=5.55, ly=3.06, fs=5.8, ls='--')

    text(ax, 0.40, 0.70, '分支约定：main 禁止直接提交；feature 分支命名 feature/<功能>，开发完成后以 Pull Request 合并回 develop；'
                         'release 验收通过后合入 main，并回合并 develop；hotfix 修复后同时合入 main 与 develop。',
         fs=5.9, ha='left', lh=1.6)
    text(ax, 0.40, 0.30, '提交信息遵循 Conventional Commits：feat / fix / docs / refactor / test / chore，'
                         '便于生成变更记录与定位缺陷引入点。', fs=5.9, ha='left')
    save(fig, 'dd_git.png')


if __name__ == '__main__':
    fig_ai_class()
    fig_model_load()
    fig_infer_flow()
    fig_front_tree()
    fig_front_seq()
    fig_exception()
    fig_git()
