# -*- coding: utf-8 -*-
"""概要设计说明书（HLD）设计模型图生成脚本。
绘制规则：所有连线均为正交走线，只与方框边界相交，不穿越任何方框内部。
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle, Ellipse, Polygon

from _figs import (new_ax, rbox, sbox, ell, dia, dstore, arrow, route,
                   actor, startend, ell_edge, EC)

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

OUT = r'e:\trae\中文评论智能分析系统\_figs'
os.makedirs(OUT, exist_ok=True)


def label(ax, x, y, t, fs=7.4, rot=0, ha='center'):
    ax.text(x, y, t, ha=ha, va='center', fontsize=fs, rotation=rot, zorder=8,
            bbox=dict(fc='white', ec='none', pad=0.7))


def band(ax, x, y, w, h, title):
    ax.add_patch(Rectangle((x, y), w, h, fc='#FAFAFA', ec='#9E9E9E',
                           lw=1.0, ls=(0, (5, 3)), zorder=1))
    ax.text(x + 0.18, y + h - 0.26, title, ha='left', va='center',
            fontsize=9.5, color='#444444', zorder=3)


def seq(ax, parts, msgs, y_top, x0, dx, box_w=2.7, box_h=0.95, step=0.85,
        y_bottom=0.4, fs=8.4):
    """时序图：参与者 + 生命线 + 消息。箭头只落在生命线上，不进入任何方框。"""
    xs = [x0 + i * dx for i in range(len(parts))]
    for x, lab in zip(xs, parts):
        rbox(ax, x, y_top, box_w, box_h, lab, fs=fs, fc='#F2F7FF')
        ax.plot([x, x], [y_top - box_h / 2 - 0.06, y_bottom],
                color='#999999', lw=0.9, ls=(0, (4, 3)), zorder=2)
    y = y_top - box_h / 2 - 0.6
    for m in msgs:
        k = m[0]
        if k in ('msg', 'ret'):
            _, i, j, text = m
            arrow(ax, (xs[i], y), (xs[j], y), lw=1.1,
                  ls='-' if k == 'msg' else '--')
            label(ax, (xs[i] + xs[j]) / 2, y + 0.24, text, fs=7.6)
        elif k == 'self':
            _, i, text = m
            x = xs[i]
            ax.plot([x, x + 1.05, x + 1.05], [y, y, y - 0.34],
                    color=EC, lw=1.0, zorder=4)
            ax.annotate('', xy=(x, y - 0.34), xytext=(x + 1.05, y - 0.34), zorder=4,
                        arrowprops=dict(arrowstyle='-|>', color=EC, lw=1.0,
                                        shrinkA=0, shrinkB=0, mutation_scale=11))
            ax.text(x + 1.18, y - 0.17, text, ha='left', va='center',
                    fontsize=7.6, zorder=8)
        elif k == 'skip':
            y -= m[1]
            continue
        y -= step
    return xs


def frame(ax, x, y1, y2, text, fs=7.6):
    """左侧 loop / alt 标记框线，位于所有生命线之外。"""
    ax.plot([x, x], [y1, y2], color='#666666', lw=1.0, zorder=3)
    ax.text(x - 0.28, (y1 + y2) / 2, text, ha='center', va='center',
            fontsize=fs, rotation=90, zorder=8)


# ============================================================ 图 2-1 总体架构图
def fig_arch():
    fig, ax = new_ax(15.2, 10.6)
    ax.set_xlim(-0.4, 20.6)
    ax.set_ylim(-0.4, 12.6)

    L, W = 0.9, 12.9

    # 表示层
    band(ax, L, 10.30, W, 1.75, '表示层（浏览器端 原生 HTML + CSS + JavaScript + ECharts）')
    pv = ['登录/注册页', '分析工作台', '数据看板', '任务对比', '系统设置', '个人中心']
    for i, t in enumerate(pv):
        rbox(ax, 2.05 + i * 2.08, 10.82, 1.85, 0.66, t, fs=7.6, fc='#EAF3FB')

    # 业务层
    band(ax, L, 6.60, W, 3.30, '业务层（Spring Boot 2.7.x，JDK 17）｜接口控制层 Controller ＋ 业务服务层 Service')
    bc = ['UserController', 'FileController', 'InputController', 'TaskController', 'ResultController',
          'Dashboard / Settings']
    for i, t in enumerate(bc):
        rbox(ax, 1.95 + i * 2.08, 8.95, 1.90, 0.62, t, fs=7.0, fc='#FFFFFF')
    bs = ['账号与文件管理', '智能输入', '任务调度', '结果可视化与复核', '历史 / 看板 / 对比', '系统设置与日志']
    for i, t in enumerate(bs):
        rbox(ax, 1.95 + i * 2.08, 7.45, 1.90, 0.66, t, fs=6.8, fc='#EAF7EE')

    # 数据访问层
    band(ax, L, 4.55, W, 1.75, '数据访问层（MyBatis-Plus + HikariCP）')
    dm = ['UserMapper', 'CommentMapper', 'AnalysisTaskMapper',
          'AnalysisResultMapper', 'KeywordMapper', 'StatisticsMapper']
    for i, t in enumerate(dm):
        rbox(ax, 2.00 + i * 2.08, 5.08, 1.90, 0.70, t, fs=6.9)

    # 智能服务层
    band(ax, L, 1.30, W, 2.90, '智能服务层（独立组件  DJL + PyTorch Engine，CPU 推理）')
    ai = ['SentimentInferenceService\n推理门面', 'TextPreprocessor + BertTokenizer\n文本清洗与编码',
          'KeywordExtractor\nTF-IDF 关键词提取', 'ModelRepository\n模型加载与常驻']
    for i, t in enumerate(ai):
        rbox(ax, 2.45 + i * 3.13, 1.98, 2.80, 1.00, t, fs=7.0, fc='#FFF4E6')

    # 右侧外部资源
    sbox(ax, 16.9, 5.10, 3.2, 1.20, 'MySQL 8.0\n业务数据库', fs=8.6, fc='#E8F5E9')
    dstore(ax, 16.9, 2.20, 3.2, 1.05, '模型文件\n权重 / 词表 / 标签表', fs=7.8)

    # 层间箭头（仅在层间空隙内走线，不穿越任何方框）
    arrow(ax, (4.30, 10.30), (4.30, 9.92), lw=1.6)
    label(ax, 6.60, 10.11, 'HTTP / JSON（RESTful API 请求与响应）', fs=7.4)
    arrow(ax, (4.30, 6.60), (4.30, 6.32), lw=1.6)
    label(ax, 5.75, 6.46, '持久化访问（Mapper）', fs=7.4)

    # 数据访问层 → MySQL
    arrow(ax, (13.80, 5.10), (15.30, 5.10), lw=1.2)
    label(ax, 14.55, 5.42, '读写', fs=7.2)
    # 智能服务层 → 模型文件
    route(ax, [(13.80, 2.20), (15.30, 2.20)])
    label(ax, 14.55, 2.50, '启动时加载一次', fs=7.0)

    # 业务层 → 智能服务层（走左侧专用通道，绕开数据访问层）
    route(ax, [(L, 7.45), (0.30, 7.45), (0.30, 2.20), (L, 2.20)])
    label(ax, 0.62, 4.80, '业务层调用智能服务层（应用内 Java 接口，非 HTTP）', fs=7.0, rot=90)

    fig.savefig(os.path.join(OUT, 'hld_arch.png'), facecolor='white')
    plt.close(fig)


# ====================================================== 图 2-2 模块依赖关系图
def fig_module_dep():
    fig, ax = new_ax(13.0, 6.0)
    ax.set_xlim(-0.4, 19.6)
    ax.set_ylim(2.9, 9.1)

    y1, y2 = 7.4, 4.4
    xs = [2.4, 7.2, 12.0, 16.8]
    W, H = 3.3, 0.85

    top = ['M1 用户管理', 'M2 文件上传解析', 'M3 智能分析调度', 'M6 模型推理服务\n（独立组件）']
    bot = ['登录态拦截器\n（统一拦截 M2～M5）', 'M5 历史记录', 'M4 结果可视化', 'M7 系统配置']
    for x, t in zip(xs, top):
        rbox(ax, x, y1, W, H, t, fs=8.2, fc='#EAF3FB')
    for x, t in zip(xs, bot):
        rbox(ax, x, y2, W, H, t, fs=8.2, fc='#EAF7EE')
    rbox(ax, xs[0], y2, W, H, bot[0], fs=8.0, fc='#F3F3F3')

    # M1 用户管理 ⇢ 登录态拦截器
    arrow(ax, (xs[0], y1 - H / 2), (xs[0], y2 + H / 2), lw=1.2, ls='--')
    # M3 → M2
    arrow(ax, (xs[2] - W / 2, y1), (xs[1] + W / 2, y1), lw=1.3)
    label(ax, (xs[1] + xs[2]) / 2, y1 + H / 2 + 0.26, '读取解析后的评论数据', fs=7.0)
    # M3 → M6
    arrow(ax, (xs[2] + W / 2, y1), (xs[3] - W / 2, y1), lw=1.3)
    label(ax, (xs[2] + xs[3]) / 2, y1 + H / 2 + 0.26, '调用推理接口', fs=7.0)
    # M4 → M3
    arrow(ax, (xs[2], y2 + H / 2), (xs[2], y1 - H / 2), lw=1.3)
    label(ax, xs[2] + 1.35, (y1 + y2) / 2, '查询结果与关键词', fs=7.0)
    # M7 → M6
    arrow(ax, (xs[3], y2 + H / 2), (xs[3], y1 - H / 2), lw=1.3)
    label(ax, xs[3] + 1.30, (y1 + y2) / 2, '读取模型版本信息', fs=7.0)
    # M5 → M4
    arrow(ax, (xs[1] + W / 2, y2), (xs[2] - W / 2, y2), lw=1.3)
    label(ax, (xs[1] + xs[2]) / 2, y2 - H / 2 - 0.28, '复用可视化查询', fs=7.0)
    # M5 → M3（走两行之间的专用通道，绕开 M4）
    route(ax, [(xs[1], y2 + H / 2), (xs[1], 6.05), (10.4, 6.05), (10.4, y1 - H / 2)])
    label(ax, 8.0, 6.32, '读取任务与结果', fs=7.0)
    # 拦截器 ⇢ M2（虚线）
    arrow(ax, (xs[0] + W / 2, y2), (xs[1] - W / 2, y2), lw=1.1, ls='--')
    label(ax, (xs[0] + xs[1]) / 2, y2 - H / 2 - 0.28, '会话校验', fs=7.0)

    ax.text(0.0, 3.12,
            '说明：实线为业务调用依赖；虚线为统一的登录态校验拦截，不构成业务耦合；'
            'M6 为单向被依赖的叶子组件，不依赖任何业务模块。',
            fontsize=7.8, ha='left', va='center')

    fig.savefig(os.path.join(OUT, 'hld_module_dep.png'), facecolor='white')
    plt.close(fig)


# ======================================================== 图 2-3 核心业务流程图
def fig_flow():
    fig, ax = new_ax(11.8, 11.8)
    ax.set_xlim(-0.3, 19.0)
    ax.set_ylim(-0.8, 18.5)

    cx, bw, bh = 9.6, 7.6, 0.80
    rx, rw, rh = 16.4, 3.6, 0.85

    def box(y, t, x=cx, w=bw, h=bh, fs=8.8):
        rbox(ax, x, y, w, h, t, fs=fs)

    def vd(y1, y2, t=None):
        arrow(ax, (cx, y1), (cx, y2), lw=1.2)
        if t:
            label(ax, cx + 0.42, (y1 + y2) / 2, t, fs=7.6)

    # 阶段标签（置于流程列左侧，不与任何连线、方框相交）
    for y, t in ((15.45, '①  上传与解析阶段'), (7.55, '②  调度推理与存储阶段'), (1.00, '③  展示与回溯阶段')):
        ax.text(0.60, y, t, ha='left', va='center', fontsize=8.6, color='#444444', zorder=3)

    startend(ax, cx, 17.70, '管理员登录')
    vd(17.52, 17.05)
    box(16.65, '选择并上传 Excel / CSV 评论文件')
    vd(16.25, 16.05)
    dia(ax, cx, 15.50, 5.0, 1.10, '文件格式、大小、表头与编码\n校验是否通过？', fs=8.4)
    vd(14.95, 14.65, '是')
    box(14.25, '识别评论内容列（识别失败时可手工指定）')
    vd(13.85, 13.60)
    box(13.20, '逐行解析 + 文本清洗去重，有效评论写入 comment 表')
    vd(12.80, 12.35)
    box(11.95, '返回解析报告（总条数 / 有效条数 / 过滤条数）')
    vd(11.55, 11.35)
    dia(ax, cx, 10.80, 5.0, 1.10, '智能模型可用性检查\n是否通过？', fs=8.4)
    vd(10.25, 9.95, '是')
    box(9.55, '创建分析任务（状态 = 待执行），作业提交异步线程池')
    vd(9.15, 8.90)
    box(8.50, '取第 i 批评论，调用 InferenceFacade 批量推理')
    vd(8.10, 7.85)
    box(7.45, '情感三分类（置信度 < 0.60 标记待复核）')
    vd(7.05, 6.80)
    box(6.40, 'TF-IDF 关键词提取（权重降序取前 50）')
    vd(6.00, 5.75)
    box(5.35, '异常样本跳过并记录日志，不中断整个任务')
    vd(4.95, 4.70)
    box(4.30, '批次结果批量写入 analysis_result / keyword，更新进度')
    vd(3.90, 3.70)
    dia(ax, cx, 3.15, 5.0, 1.10, '是否仍有\n未处理批次？', fs=8.4)
    vd(2.60, 2.35, '否')
    box(1.95, '任务状态置为已完成，记录结束时间与总耗时')
    vd(1.55, 1.30)
    box(0.90, '结果可视化页 / 结果明细页 / 导出 Excel / 历史回溯')
    vd(0.50, 0.25)
    startend(ax, cx, 0.05, '流程结束', side='bottom')

    # 批次循环回边（左侧专用通道，位于阶段标签与流程列之间）
    route(ax, [(7.10, 3.15), (4.20, 3.15), (4.20, 8.50), (5.80, 8.50)],
          label='是（继续下一批）', lx=3.52, ly=5.80, lrot=90)

    # 校验失败分支
    box(15.50, '返回错误提示，\n不生成上传批次', x=rx, w=rw, h=rh)
    arrow(ax, (12.10, 15.50), (rx - rw / 2, 15.50), lw=1.2)
    label(ax, 13.35, 15.82, '否', fs=7.6)
    arrow(ax, (rx, 15.08), (rx, 14.62), lw=1.2)
    startend(ax, rx, 14.45, '结束（校验失败）')

    # 模型不可用分支
    box(10.80, '拒绝创建任务，\n提示智能模型不可用', x=rx, w=rw, h=rh)
    arrow(ax, (12.10, 10.80), (rx - rw / 2, 10.80), lw=1.2)
    label(ax, 13.35, 11.12, '否', fs=7.6)
    arrow(ax, (rx, 10.38), (rx, 9.92), lw=1.2)
    startend(ax, rx, 9.75, '结束（模型不可用）')

    fig.savefig(os.path.join(OUT, 'hld_flow.png'), facecolor='white')
    plt.close(fig)


# ====================================================== 图 2-4 核心流程时序图
def fig_seq_core():
    fig, ax = new_ax(12.4, 11.5)
    ax.set_xlim(-0.4, 23.0)
    ax.set_ylim(-3.7, 18.0)

    parts = ['管理员', '表示层\n（浏览器）', 'FileController\n解析服务',
             'TaskController\n调度服务', '智能服务层\nInferenceFacade', 'MySQL']
    msgs = [
        ('msg', 0, 1, '选择并上传评论文件'),
        ('msg', 1, 2, 'POST /api/files/upload'),
        ('self', 2, '校验格式 / 大小 / 表头 / 编码'),
        ('skip', 0.22),
        ('self', 2, '识别评论列 + 文本清洗去重'),
        ('skip', 0.22),
        ('msg', 2, 5, '写入 upload_batch、批量插入 comment'),
        ('ret', 5, 2, '返回批次编号 batchId'),
        ('ret', 2, 1, '返回解析报告（总条数 / 有效条数 / 过滤条数）'),
        ('msg', 0, 1, '确认发起分析'),
        ('msg', 1, 3, 'POST /api/tasks（batchId）'),
        ('msg', 3, 4, '模型可用性检查'),
        ('ret', 4, 3, '模型已加载且可推理'),
        ('msg', 3, 5, '插入 analysis_task（状态 = 待执行）'),
        ('self', 3, '提交异步任务并立即返回'),
        ('skip', 0.22),
        ('ret', 3, 1, '返回任务编号 taskId'),
        ('msg', 3, 5, '按批次读取待推理评论'),
        ('msg', 3, 4, 'classifyBatch(textList)'),
        ('ret', 4, 3, '情感标签 / 置信度 / 是否待复核'),
        ('msg', 3, 4, 'extractKeywords(textList)'),
        ('ret', 4, 3, '关键词与权重列表（降序）'),
        ('msg', 3, 5, '批量写入 analysis_result、keyword'),
        ('msg', 3, 5, '更新任务已处理条数与进度'),
        ('msg', 3, 5, '任务状态置为已完成'),
        ('msg', 1, 3, 'GET /api/tasks/{taskId}/progress（前端轮询）'),
        ('ret', 3, 1, '状态 / 已处理条数 / 进度百分比'),
    ]
    seq(ax, parts, msgs, y_top=17.10, x0=3.2, dx=3.6, box_w=2.9, box_h=1.00,
        step=0.80, y_bottom=-3.45)

    # loop 标记（置于所有生命线左侧，不与任何方框相交）
    frame(ax, 1.30, -0.94, 4.42, 'loop  每批次（共 N 批）')
    frame(ax, 1.30, -3.32, -2.50, 'loop  前端轮询')

    fig.savefig(os.path.join(OUT, 'hld_seq_core.png'), facecolor='white')
    plt.close(fig)


# ========================================================== 图 3-1 任务状态机
def fig_task_state():
    fig, ax = new_ax(13.0, 3.6)
    ax.set_xlim(-0.2, 19.6)
    ax.set_ylim(4.2, 9.5)

    def state(x, y, t, w=3.2):
        rbox(ax, x, y, w, 0.90, t, fs=9, fc='#FFF4E6', rounding=0.35)

    startend(ax, 1.6, 8.0, '')
    state(5.2, 8.0, '待执行')
    state(9.2, 8.0, '执行中')
    state(14.4, 8.0, '已完成', w=3.4)
    state(9.2, 5.0, '失败')
    state(15.0, 5.0, '已终止', w=3.4)

    # 终止状态（实心圆＋外圈）
    ax.add_patch(Circle((18.4, 8.0), 0.34, fc='white', ec=EC, lw=1.4, zorder=3))
    ax.add_patch(Circle((18.4, 8.0), 0.20, fc=EC, ec=EC, lw=1.0, zorder=4))

    arrow(ax, (1.9, 8.0), (3.60, 8.0), lw=1.3)
    label(ax, 2.75, 8.40, '创建任务', fs=7.4)
    arrow(ax, (6.80, 8.0), (7.60, 8.0), lw=1.3)
    label(ax, 7.20, 8.85, '模型可用性检查通过\n并提交线程池', fs=7.4)
    arrow(ax, (10.80, 8.0), (12.70, 8.0), lw=1.3)
    label(ax, 11.75, 8.85, '全部批次处理完成', fs=7.4)
    arrow(ax, (16.10, 8.0), (18.02, 8.0), lw=1.3)
    label(ax, 17.05, 8.40, '流程结束', fs=7.4)

    # 待执行 → 失败（走下方通道，绕开执行中）
    route(ax, [(5.20, 7.55), (5.20, 5.00), (7.60, 5.00)])
    label(ax, 6.40, 5.38, '模型不可用', fs=7.4)
    # 执行中 → 失败
    arrow(ax, (8.20, 7.55), (8.20, 5.48), lw=1.3)
    label(ax, 7.00, 6.50, '批次写入失败 /\n资源不足 / 进程中断', fs=7.4)
    # 失败 → 执行中（重试）
    arrow(ax, (10.20, 5.48), (10.20, 7.55), lw=1.3, ls='--')
    label(ax, 11.30, 6.50, '失败重试\n（去重续跑）', fs=7.4)
    # 执行中 → 已终止
    route(ax, [(10.80, 7.55), (12.00, 7.55), (12.00, 5.00), (13.30, 5.00)])
    label(ax, 12.65, 5.38, '管理员终止', fs=7.4)

    ax.text(-0.20, 4.35,
            '注：已终止的任务可由管理员重新发起（可选转移，图中未绘制连线以避免与其他连线交叉）；'
            '失败重试按「任务编号 + 评论编号」去重续跑，不产生重复结果。',
            fontsize=7.6, ha='left', va='center')

    fig.savefig(os.path.join(OUT, 'hld_task_state.png'), facecolor='white')
    plt.close(fig)


# ====================================================== 图 4-1 核心实体关系图
def fig_hld_er():
    fig, ax = new_ax(15.5, 9.2)
    ax.set_xlim(0, 17.6)
    ax.set_ylim(0, 10.4)

    EW, EH = 2.7, 2.15
    ents = {
        'sys_user\n用户表': (1.9, 8.2, '用户编号(PK)\n账号(UNIQUE)\n密码哈希\n账号状态\n最近登录时间'),
        'analysis_task\n分析任务表': (6.5, 8.2, '任务编号(PK)\n任务名称/源文件名\n模型版本号\n任务状态\n总条数/已处理条数'),
        'comment_data\n评论表': (11.1, 8.2, '评论编号(PK)\n任务编号(FK)\n评论原文\n行号/评论时间'),
        'analysis_result\n分析结果表': (15.7, 8.2, '结果编号(PK)\n任务编号(FK)\n评论编号(FK)\n情感标签/置信度\n复核状态'),
        'task_statistics\n任务统计表': (6.5, 2.3, '统计编号(PK)\n任务编号(FK)\n三类条数/待复核数\n平均置信度'),
        'keyword_statistics\n关键词统计表': (15.7, 2.3, '关键词编号(PK)\n任务编号(FK)\n关键词\n权重/词频\n所属情感'),
    }
    for name, (x, y, attrs) in ents.items():
        sbox(ax, x, y, EW, EH, '', fc='#FFFFFF')
        ax.text(x, y + 0.80, name, ha='center', va='center', fontsize=8.2, linespacing=1.25)
        ax.plot([x - EW / 2, x + EW / 2], [y + 0.52, y + 0.52], color=EC, lw=0.9)
        ax.text(x, y - 0.28, attrs, ha='center', va='center', fontsize=6.9, linespacing=1.4)

    dia(ax, 4.20, 8.2, 1.15, 0.78, '拥有', fs=7.4)
    dia(ax, 8.80, 8.2, 1.15, 0.78, '包含', fs=7.4)
    dia(ax, 13.40, 8.2, 1.15, 0.78, '对应', fs=7.4)
    dia(ax, 6.5, 5.25, 1.15, 0.78, '汇总', fs=7.4)
    dia(ax, 11.0, 2.3, 1.15, 0.78, '产出', fs=7.4)

    def seg(p1, p2):
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=EC, lw=0.95, zorder=3)

    def card(x, y, t):
        ax.text(x, y, t, fontsize=7.4, ha='center', va='center',
                bbox=dict(fc='white', ec='none', pad=0.4), zorder=5)

    # 用户 1:N 分析任务
    seg((3.25, 8.2), (3.62, 8.2)); seg((4.78, 8.2), (5.15, 8.2))
    card(3.42, 8.48, '1'); card(5.00, 8.48, 'N')
    # 分析任务 1:N 评论
    seg((7.85, 8.2), (8.22, 8.2)); seg((9.38, 8.2), (9.75, 8.2))
    card(8.02, 8.48, '1'); card(9.58, 8.48, 'N')
    # 评论 1:1 分析结果
    seg((12.45, 8.2), (12.82, 8.2)); seg((13.98, 8.2), (14.35, 8.2))
    card(12.62, 8.48, '1'); card(14.18, 8.48, '1')
    # 分析任务 1:1 任务统计
    seg((6.5, 7.12), (6.5, 5.65)); seg((6.5, 4.85), (6.5, 3.38))
    card(6.75, 5.42, '1'); card(6.75, 3.62, '1')
    # 分析任务 1:N 分析结果（上方通道）
    ax.plot([7.2, 7.2], [9.28, 9.62], color=EC, lw=0.95, zorder=3)
    ax.plot([7.2, 15.3], [9.62, 9.62], color=EC, lw=0.95, zorder=3)
    arrow(ax, (15.3, 9.62), (15.3, 9.32), lw=0.95)
    card(11.2, 9.85, '产出 1:N')
    # 分析任务 1:N 关键词（右侧通道）
    ax.plot([7.85, 9.2], [7.25, 6.55], color=EC, lw=0.95, zorder=3)
    ax.plot([9.2, 9.2], [6.55, 2.3], color=EC, lw=0.95, zorder=3)
    arrow(ax, (9.2, 2.3), (10.42, 2.3), lw=0.95)
    ax.plot([11.58, 14.35], [2.3, 2.3], color=EC, lw=0.95, zorder=3)
    card(9.55, 6.75, '产出 1:N')

    ax.text(0.4, 10.1, '图注：矩形为数据表（上为表名，下为中文名），菱形为联系，连线两端标注基数（1 / N），PK 主键、FK 外键、UNIQUE 唯一约束。',
            fontsize=8, ha='left')
    ax.text(0.4, 0.55, '说明：上传批次已并入分析任务表；模型版本号关联 model_info.json（文件存储，不单独建表）。',
            fontsize=7.8, ha='left')

    fig.savefig(os.path.join(OUT, 'hld_er.png'), facecolor='white')
    plt.close(fig)


# ================================================= 图 6-1 智能模块组件结构图
def fig_ai_comp():
    fig, ax = new_ax(13.5, 6.9)
    ax.set_xlim(0.2, 21.2)
    ax.set_ylim(1.0, 11.8)

    ax.text(12.6, 11.30, '智能服务层（独立组件 ai 包，对外仅暴露 InferenceFacade）',
            ha='center', va='center', fontsize=9, color='#555555')

    rbox(ax, 2.2, 9.5, 3.2, 0.90, 'M3 智能分析调度模块', fs=8.2, fc='#EAF3FB')
    rbox(ax, 2.2, 7.5, 3.2, 0.90, 'M7 系统配置模块', fs=8.2, fc='#EAF3FB')
    rbox(ax, 6.0, 8.5, 3.2, 1.00, 'InferenceFacade\n唯一对外门面', fs=8.2, fc='#FFF4E6')
    rbox(ax, 10.4, 10.0, 3.2, 1.00, 'TextPreprocessor\n截断 / 过滤 / 字符替换', fs=8.0, fc='#FFFFFF')
    rbox(ax, 14.6, 10.0, 3.6, 1.00, 'SentimentClassifier\nDJL BERT 批量推理', fs=8.0, fc='#FFFFFF')
    rbox(ax, 14.6, 7.0, 3.6, 1.00, 'KeywordExtractor\n分词 + TF-IDF', fs=8.0, fc='#FFFFFF')
    rbox(ax, 14.6, 4.3, 3.6, 1.00, 'ModelRepository\n模型加载与常驻单例', fs=8.0, fc='#FFFFFF')
    dstore(ax, 18.6, 4.0, 2.8, 1.00, '模型文件\nmodel.pt / vocab.txt\n/ labels.txt', fs=6.8)
    dstore(ax, 9.6, 2.0, 3.2, 0.90, '停用词表 stopwords.txt', fs=7.4)

    route(ax, [(3.80, 9.5), (4.70, 9.5), (4.70, 9.0)])
    label(ax, 3.05, 10.20, 'AI-API-02 / 03', fs=7.0)
    route(ax, [(3.80, 7.5), (5.30, 7.5), (5.30, 8.0)])
    label(ax, 4.00, 7.10, 'AI-API-06', fs=7.0)

    route(ax, [(7.6, 8.8), (8.2, 8.8), (8.2, 10.0), (8.8, 10.0)])
    label(ax, 8.20, 9.30, '预处理', fs=7.0)
    arrow(ax, (12.0, 10.0), (12.8, 10.0), lw=1.2)
    label(ax, 12.40, 10.36, '批量推理', fs=7.0)
    route(ax, [(7.6, 8.2), (8.4, 8.2), (8.4, 7.0), (12.8, 7.0)])
    label(ax, 10.60, 7.32, '关键词提取', fs=7.0)

    arrow(ax, (14.6, 4.8), (14.6, 6.5), lw=1.2)
    label(ax, 13.55, 5.65, '提供分词器', fs=7.0)
    route(ax, [(16.4, 4.6), (17.4, 4.6), (17.4, 10.0), (16.4, 10.0)])
    label(ax, 18.05, 6.60, '提供模型与词表', fs=7.0, rot=90)
    arrow(ax, (16.4, 4.0), (17.2, 4.0), lw=1.2)
    label(ax, 16.80, 4.42, '启动加载', fs=7.0)
    route(ax, [(12.8, 6.5), (12.0, 6.5), (12.0, 2.0), (11.2, 2.0)])
    label(ax, 12.00, 4.20, '读取停用词', fs=7.0, rot=90)

    fig.savefig(os.path.join(OUT, 'hld_ai_comp.png'), facecolor='white')
    plt.close(fig)


# ============================================== 图 6-2 模型加载与生命周期时序图
def fig_seq_model_load():
    fig, ax = new_ax(12.0, 5.4)
    ax.set_xlim(-0.4, 22.4)
    ax.set_ylim(2.30, 12.60)

    parts = ['Spring Boot\n启动流程', 'ModelRepository', 'DJL +\nPyTorch Engine',
             '模型文件目录', 'InferenceFacade']
    msgs = [
        ('msg', 0, 1, '启动时初始化（仅一次）'),
        ('msg', 1, 3, '校验 model.pt / vocab.txt / labels.txt 是否存在'),
        ('ret', 3, 1, '文件不存在'),
        ('msg', 1, 0, '抛出模型加载异常，应用启动失败并输出明确错误日志'),
        ('skip', 0.42),
        ('msg', 1, 2, '加载模型并构建 Predictor'),
        ('ret', 2, 1, '返回模型实例'),
        ('self', 1, '常驻内存（单例），记录版本与加载耗时'),
        ('skip', 0.24),
        ('msg', 1, 4, '标记模型可用'),
        ('self', 0, '服务正常就绪'),
    ]
    seq(ax, parts, msgs, y_top=11.60, x0=2.6, dx=4.0, box_w=3.0, box_h=1.00,
        step=0.80, y_bottom=3.05)

    frame(ax, 1.00, 7.80, 10.00, 'alt  模型文件缺失')
    frame(ax, 1.00, 3.05, 7.20, 'else  模型文件完整')

    ax.text(0.0, 2.55,
            '注：运行期所有推理复用同一 Predictor 实例，不重复加载模型文件；模型加载失败即阻断应用启动，不做静默降级。',
            fontsize=7.8, ha='left', va='center')

    fig.savefig(os.path.join(OUT, 'hld_seq_model_load.png'), facecolor='white')
    plt.close(fig)


# ================================================= 图 6-3 推理调用流程时序图
def fig_seq_infer():
    fig, ax = new_ax(12.4, 9.0)
    ax.set_xlim(-0.4, 23.0)
    ax.set_ylim(-1.9, 13.4)

    parts = ['InferenceScheduler\n（业务层）', 'InferenceFacade', 'TextPreprocessor',
             'SentimentClassifier', 'KeywordExtractor', 'MySQL']
    msgs = [
        ('self', 0, '按批量大小切分第 i 批评论'),
        ('skip', 0.24),
        ('msg', 0, 1, 'classifyBatch(texts)'),
        ('msg', 1, 2, '逐条预处理（截断 512 / 过滤空值 / 字符替换）'),
        ('ret', 2, 1, '归一化后的文本列表'),
        ('msg', 1, 3, '批量前向推理'),
        ('ret', 3, 1, '每条的标签概率分布'),
        ('self', 1, '取最高概率为标签，置信度保留四位小数'),
        ('skip', 0.24),
        ('self', 1, 'score < 0.60 标记 needReview = true'),
        ('skip', 0.24),
        ('ret', 1, 0, 'List（与输入顺序一致）'),
        ('msg', 0, 1, 'extractKeywords(texts, topN = 50)'),
        ('msg', 1, 4, '分词 + 停用词过滤 + TF-IDF 计算'),
        ('ret', 4, 1, '关键词与权重（降序）'),
        ('ret', 1, 0, '关键词列表'),
        ('msg', 0, 5, '批量写入 analysis_result 与 keyword'),
        ('msg', 0, 5, '更新任务已处理条数与进度'),
    ]
    seq(ax, parts, msgs, y_top=12.40, x0=3.2, dx=3.6, box_w=2.9, box_h=1.00,
        step=0.80, y_bottom=-1.60)

    ax.text(0.0, -1.80,
            '注：单条样本推理异常时跳过该条并记录日志（该条计入 error_count），不中断整个任务。',
            fontsize=7.8, ha='left', va='center')

    fig.savefig(os.path.join(OUT, 'hld_seq_infer.png'), facecolor='white')
    plt.close(fig)


# ==================================================== 图 7-1 网络与部署拓扑图
def fig_deploy():
    fig, ax = new_ax(12.8, 5.2)
    ax.set_xlim(0.0, 18.2)
    ax.set_ylim(3.4, 10.7)

    ax.text(2.2, 10.35, '客户端', ha='center', va='center', fontsize=9.5, color='#444444')
    ax.text(11.6, 10.35, '应用服务器（单机部署，以下组件位于同一主机）',
            ha='center', va='center', fontsize=9.5, color='#444444')

    sbox(ax, 2.2, 9.5, 4.0, 1.20, '浏览器\nChrome / Edge / Firefox', fs=8.6, fc='#EAF3FB')
    rbox(ax, 8.0, 9.5, 4.4, 1.20, '内嵌 Tomcat\nHTTP 服务端口 8080', fs=8.6, fc='#EAF3FB')

    rbox(ax, 3.0, 7.0, 3.4, 1.10, '静态资源\nHTML / CSS / JS / ECharts', fs=7.8, fc='#FFFFFF')
    rbox(ax, 7.2, 7.0, 3.6, 1.10, '业务层\nController + Service', fs=8.0, fc='#EAF7EE')
    rbox(ax, 11.4, 7.0, 4.0, 1.10, '数据访问层\nMyBatis Mapper', fs=8.0, fc='#EAF7EE')
    rbox(ax, 15.6, 7.0, 4.0, 1.10, '智能服务层\nDJL + PyTorch Engine', fs=8.0, fc='#FFF4E6')

    sbox(ax, 11.4, 4.2, 4.0, 1.10, 'MySQL 8.0\n本地实例（仅回环访问）', fs=7.8, fc='#E8F5E9')
    dstore(ax, 15.6, 4.2, 4.0, 1.10, '本地文件系统\n模型文件 / 停用词 / 日志', fs=7.6)

    arrow(ax, (4.2, 9.5), (5.75, 9.5), lw=1.5)
    label(ax, 4.98, 9.88, 'HTTP :8080', fs=7.2)
    route(ax, [(6.80, 8.90), (6.80, 8.30), (3.00, 8.30), (3.00, 7.55)])
    label(ax, 4.90, 8.60, '静态文件响应', fs=7.0)
    arrow(ax, (7.00, 8.90), (7.00, 7.55), lw=1.3)
    label(ax, 7.95, 8.24, '接口转发', fs=7.0)
    arrow(ax, (9.00, 7.0), (9.40, 7.0), lw=1.3)
    label(ax, 9.20, 7.00, 'Mapper', fs=7.0)
    arrow(ax, (11.40, 6.45), (11.40, 4.75), lw=1.3)
    label(ax, 12.25, 5.60, 'JDBC', fs=7.0)
    arrow(ax, (15.60, 6.45), (15.60, 4.75), lw=1.3)
    label(ax, 16.70, 5.60, '读取模型 / 写日志', fs=7.0)
    route(ax, [(8.40, 7.55), (8.40, 8.00), (15.60, 8.00), (15.60, 7.55)])
    label(ax, 12.00, 8.32, '应用内调用（非 HTTP，不占用端口）', fs=7.0)

    fig.savefig(os.path.join(OUT, 'hld_deploy.png'), facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    fig_arch()
    fig_module_dep()
    fig_flow()
    fig_seq_core()
    fig_task_state()
    fig_hld_er()
    fig_ai_comp()
    fig_seq_model_load()
    fig_seq_infer()
    fig_deploy()
    print('全部 HLD 设计图生成完成')
    print('第 2 章图完成')
