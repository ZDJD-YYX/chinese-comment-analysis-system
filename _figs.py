# -*- coding: utf-8 -*-
"""生成本项目需求分析模型图（用例图 / 活动图 / E-R图 / 数据流图）"""
import os
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Ellipse, Rectangle, Polygon

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

OUT = r'e:\trae\中文评论智能分析系统\_figs'
os.makedirs(OUT, exist_ok=True)

EC = '#333333'


def new_ax(w, h):
    fig = plt.figure(figsize=(w, h), dpi=180)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    return fig, ax


def rbox(ax, cx, cy, w, h, text, fs=9.5, fc='#FFFFFF', ec=EC, lw=1.1, rounding=0.10):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle=f'round,pad=0,rounding_size={rounding}',
                                fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(cx, cy, text, ha='center', va='center', fontsize=fs, linespacing=1.4, zorder=3)


def sbox(ax, cx, cy, w, h, text, fs=9.5, fc='#FFFFFF', ec=EC, lw=1.1):
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(cx, cy, text, ha='center', va='center', fontsize=fs, linespacing=1.4, zorder=3)


def ell(ax, cx, cy, w, h, text, fs=9, fc='#FFFFFF', ec=EC, lw=1.1):
    ax.add_patch(Ellipse((cx, cy), w, h, fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(cx, cy, text, ha='center', va='center', fontsize=fs, linespacing=1.35, zorder=3)


def dia(ax, cx, cy, w, h, text, fs=8.5, fc='#FFF6E5', ec=EC, lw=1.1):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(cx, cy, text, ha='center', va='center', fontsize=fs, linespacing=1.25, zorder=3)


def dstore(ax, cx, cy, w, h, text, fs=9):
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fc='#F2F7FF', ec=EC, lw=1.1, zorder=2))
    ax.plot([cx - w / 2 + 0.28, cx - w / 2 + 0.28], [cy - h / 2, cy + h / 2], color=EC, lw=1.0, zorder=3)
    ax.text(cx + 0.14, cy, text, ha='center', va='center', fontsize=fs, zorder=3)


def arrow(ax, p1, p2, label=None, ls='-', color=EC, lw=1.2, rad=0.0,
          lx=None, ly=None, fs=7.6, lcolor=EC):
    ax.annotate('', xy=p2, xytext=p1, zorder=4,
                arrowprops=dict(arrowstyle='-|>', color=color, lw=lw, linestyle=ls,
                                shrinkA=0, shrinkB=0, mutation_scale=13,
                                connectionstyle=f'arc3,rad={rad}'))
    if label:
        mx = lx if lx is not None else (p1[0] + p2[0]) / 2
        my = ly if ly is not None else (p1[1] + p2[1]) / 2
        ax.text(mx, my, label, ha='center', va='center', fontsize=fs, color=lcolor,
                bbox=dict(fc='white', ec='none', pad=0.8), zorder=5)


def poly(ax, pts, label=None, lx=None, ly=None, fs=7.6):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs[:-1], ys[:-1], color=EC, lw=1.2, zorder=4)
    ax.annotate('', xy=pts[-1], xytext=pts[-2], zorder=4,
                arrowprops=dict(arrowstyle='-|>', color=EC, lw=1.2, shrinkA=0, shrinkB=0,
                                mutation_scale=13))
    if label:
        ax.text(lx, ly, label, ha='center', va='center', fontsize=fs,
                bbox=dict(fc='white', ec='none', pad=0.8), zorder=5)


def actor(ax, x, y, label, s=0.95):
    ax.plot([x], [y + s * 0.78], marker='o', ms=10, mfc='white', mec=EC, mew=1.4, zorder=3)
    ax.plot([x, x], [y + s * 0.58, y + s * 0.22], color=EC, lw=1.4, zorder=3)
    ax.plot([x - 0.30, x + 0.30], [y + s * 0.44, y + s * 0.44], color=EC, lw=1.4, zorder=3)
    ax.plot([x, x - 0.26], [y + s * 0.22, y - s * 0.02], color=EC, lw=1.4, zorder=3)
    ax.plot([x, x + 0.26], [y + s * 0.22, y - s * 0.02], color=EC, lw=1.4, zorder=3)
    ax.text(x, y - 0.30, label, ha='center', va='top', fontsize=9.5, zorder=3)


def startend(ax, x, y, text, side='right'):
    ax.plot([x], [y], marker='o', ms=13, mfc='#333333', mec='#333333', zorder=3)
    if side == 'bottom':
        ax.text(x, y - 0.24, text, ha='center', va='top', fontsize=9)
    else:
        ax.text(x + 0.28, y, text, ha='left', va='center', fontsize=9)


def ell_edge(cx, cy, w, h, fx, fy):
    """求从椭圆中心指向 (fx, fy) 方向上与椭圆边界的交点，保证连线不进入椭圆内部。"""
    dx, dy = fx - cx, fy - cy
    a, b = w / 2.0, h / 2.0
    t = 1.0 / math.sqrt((dx / a) ** 2 + (dy / b) ** 2)
    return (cx + t * dx, cy + t * dy)


def route(ax, pts, label=None, lx=None, ly=None, fs=8, lrot=0):
    """正交折线，仅在最后一段绘制箭头。"""
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if i == len(pts) - 2:
            ax.annotate('', xy=b, xytext=a, zorder=4,
                        arrowprops=dict(arrowstyle='-|>', color=EC, lw=1.2,
                                        shrinkA=0, shrinkB=0, mutation_scale=13))
        else:
            ax.plot([a[0], b[0]], [a[1], b[1]], color=EC, lw=1.2, zorder=4)
    if label:
        ax.text(lx, ly, label, ha='center', va='center', fontsize=fs, rotation=lrot,
                bbox=dict(fc='white', ec='none', pad=0.8), zorder=6)


# ---------------------------------------------------------------- 图1 用例图
def fig_usecase():
    fig, ax = new_ax(11.9, 10.4)
    ax.set_xlim(0, 16.4)
    ax.set_ylim(-0.9, 13.5)

    ax.add_patch(Rectangle((2.3, 0.0), 13.7, 12.8, fc='#FCFCFC', ec=EC, lw=1.4, zorder=1))
    ax.text(9.15, 13.15, '中文评论智能分析系统', ha='center', va='center', fontsize=12, zorder=3)
    actor(ax, 0.85, 6.4, '系统管理员')

    T1, T2, T3 = 4.3, 9.25, 14.15

    # 第一栏：管理员直接发起的用例（实线关联）
    t1 = [('用户注册/登录', 12.40), ('修改密码', 11.60), ('退出登录', 10.80),
          ('上传评论文件', 10.00), ('智能输入分析', 9.20), ('查询任务进度', 8.40),
          ('终止/重试分析任务', 7.60), ('查看情感结果可视化', 6.80), ('查看结果明细', 6.00),
          ('人工复核结果', 5.20), ('导出结果与报告', 4.40), ('查询与管理历史任务', 3.60),
          ('查看数据看板与任务对比', 2.80), ('配置推理参数', 2.00),
          ('查看模型信息与操作日志', 1.20)]
    for t, y in t1:
        ell(ax, T1, y, 3.4, 0.66, t, fs=8.8)
        p = ell_edge(T1, y, 3.4, 0.66, 1.15, 6.4)
        ax.plot([1.15, p[0]], [6.4, p[1]], color=EC, lw=1.0, zorder=2)

    # 第二栏：被包含 / 扩展的用例
    t2 = [('文件格式与编码校验', 11.30), ('评论列识别', 10.58), ('手工指定评论列', 9.86),
          ('文本清洗与入库', 9.14), ('输入类型识别', 8.42), ('网页抓取与正文确认', 7.70),
          ('批量推理任务调度', 6.98), ('图表数据组织', 6.26), ('单条/批量复核', 5.54),
          ('复核质量统计', 4.82), ('导出范围与格式确定', 4.10), ('任务列表分页展示', 3.38),
          ('任务对比指标计算', 2.66), ('模型信息与操作日志展示', 1.94)]
    for t, y in t2:
        ell(ax, T2, y, 3.5, 0.56, t, fs=8.4)

    # 第三栏：被批量推理任务调度包含的模型用例
    ell(ax, T3, 6.98, 3.4, 0.56, '情感三分类推理', fs=8.8)
    ell(ax, T3, 6.26, 3.4, 0.56, '关键词TF-IDF提取', fs=8.8)

    def t1t2(y1, y2, lab, lx, ly, rev=False):
        p1 = ell_edge(T1, y1, 3.4, 0.66, T2, y2)
        p2 = ell_edge(T2, y2, 3.5, 0.56, T1, y1)
        arrow(ax, p2, p1, ls='--', lw=1.0) if rev else arrow(ax, p1, p2, ls='--', lw=1.0)
        ax.text(lx, ly, lab, ha='center', va='center', fontsize=7.0,
                bbox=dict(fc='white', ec='none', pad=0.7), zorder=6)

    def t2t3(y1, y2, lab, lx, ly):
        p1 = ell_edge(T2, y1, 3.5, 0.56, T3, y2)
        p2 = ell_edge(T3, y2, 3.4, 0.56, T2, y1)
        arrow(ax, p1, p2, ls='--', lw=1.0)
        ax.text(lx, ly, lab, ha='center', va='center', fontsize=7.0,
                bbox=dict(fc='white', ec='none', pad=0.7), zorder=6)

    # 上传评论文件：三条 «include»
    t1t2(10.00, 11.30, '<<include>>', 6.85, 10.78)
    t1t2(10.00, 10.58, '<<include>>', 6.82, 10.32)
    t1t2(10.00, 9.14, '<<include>>', 6.82, 9.62)
    # 手工指定评论列 «extend» 评论列识别（箭头指向被扩展的用例）
    arrow(ax, (9.25, 10.14), (9.25, 10.29), ls='--', lw=1.0)
    ax.text(10.02, 10.21, '<<extend>>', ha='center', va='center', fontsize=7.0,
            bbox=dict(fc='white', ec='none', pad=0.7), zorder=6)
    # 智能输入分析：两条 «include»
    t1t2(9.20, 8.42, '<<include>>', 6.82, 8.84)
    t1t2(9.20, 7.70, '<<include>>', 6.82, 8.48)
    # 上传评论文件 / 智能输入分析 → 批量推理任务调度（共用左侧竖直干线）
    ax.plot([5.97, 7.00], [10.00, 10.00], color=EC, lw=1.0, zorder=2)
    ax.plot([5.97, 7.00], [9.20, 9.20], color=EC, lw=1.0, zorder=2)
    ax.plot([7.00, 7.00], [10.00, 6.98], color=EC, lw=1.0, zorder=2)
    arrow(ax, (7.00, 6.98), (7.48, 6.98), ls='--', lw=1.0)
    # 批量推理任务调度 → 情感三分类推理 / 关键词TF-IDF提取
    t2t3(6.98, 6.98, '<<include>>', 11.65, 7.22)
    t2t3(6.98, 6.26, '<<include>>', 11.65, 6.36)
    # 查看情感结果可视化 → 图表数据组织
    t1t2(6.80, 6.26, '<<include>>', 6.82, 6.52)
    # 人工复核结果 → 单条/批量复核、复核质量统计
    t1t2(5.20, 5.54, '<<include>>', 6.82, 5.40)
    t1t2(5.20, 4.82, '<<include>>', 6.82, 5.02)
    # 导出结果与报告 / 查询与管理历史任务 / 看板与任务对比 / 模型信息与日志
    t1t2(4.40, 4.10, '<<include>>', 6.82, 4.24)
    t1t2(3.60, 3.38, '<<include>>', 6.82, 3.48)
    t1t2(2.80, 2.66, '<<include>>', 6.82, 2.72)
    t1t2(1.20, 1.94, '<<include>>', 6.82, 1.55)
    # 配置推理参数 → 模型信息与操作日志展示
    t1t2(2.00, 1.94, '<<include>>', 6.82, 1.98)

    ax.text(2.45, -0.55,
            '说明：实线为参与者与用例之间的关联；虚线箭头 <<include>> 表示包含关系；'
            '标注 <<extend>> 的虚线箭头表示扩展关系，箭头指向被扩展的用例。',
            fontsize=7.8, ha='left', va='center')

    fig.savefig(os.path.join(OUT, 'fig_usecase.png'), facecolor='white')
    plt.close(fig)


# ------------------------------------------------------- 图2 活动图：批量上传分析
def fig_activity_upload():
    fig, ax = new_ax(11.6, 14.0)
    ax.set_xlim(-0.4, 15.6)
    ax.set_ylim(-0.6, 18.5)

    cx, bw, bh = 5.0, 5.0, 0.80      # 主流程列
    rx, rw, rh = 12.4, 4.8, 0.90     # 备选 / 异常列

    def box(y, t, x=cx, w=bw, h=bh, fs=9):
        rbox(ax, x, y, w, h, t, fs=fs)

    def vdown(y1, y2, lab=None, lx=None, ly=None):
        arrow(ax, (cx, y1), (cx, y2), lw=1.2, label=lab, lx=lx, ly=ly)

    startend(ax, cx, 17.80, '开始')
    arrow(ax, (cx, 17.62), (cx, 17.05), lw=1.2)
    box(16.65, '管理员登录并进入「分析工作台」')
    vdown(16.25, 15.90)
    box(15.50, '选择并上传评论文件（Excel/CSV/TXT/TSV/JSON）')
    vdown(15.10, 14.85)
    dia(ax, cx, 14.30, 4.4, 1.10, '文件格式、大小与表头\n校验是否通过？', fs=8.6)
    vdown(13.75, 13.50, '是', cx + 0.40, 13.65)
    box(13.10, '解析文件、识别评论列、清洗去重并创建分析任务')
    vdown(12.70, 12.45)
    dia(ax, cx, 11.90, 4.4, 1.10, '评论列自动识别\n是否成功？', fs=8.6)
    vdown(11.35, 11.10, '是', cx + 0.40, 11.25)
    box(10.70, '任务置为「待执行」并自动提交推理')
    vdown(10.30, 10.05)
    dia(ax, cx, 9.50, 4.4, 1.10, '智能模型是否\n已加载且可用？', fs=8.6)
    vdown(8.95, 8.70, '是', cx + 0.40, 8.85)
    box(8.30, '按批量大小切分批次，异步启动推理调度')
    vdown(7.90, 7.55)
    box(7.15, '取下一批待分析评论')
    vdown(6.75, 6.40)
    box(6.00, '情感三分类推理（中文 RoBERTa）\n与关键词提取（TF-IDF）', h=0.90)
    vdown(5.55, 5.25)
    box(4.85, '本批结果与关键词入库，更新任务进度')
    vdown(4.45, 4.20)
    dia(ax, cx, 3.65, 4.4, 1.10, '是否仍有\n未处理批次？', fs=8.6)
    vdown(3.10, 2.85, '否', cx + 0.45, 3.00)
    box(2.45, '任务状态置为「已完成」')
    vdown(2.05, 1.80)
    box(1.40, '跳转结果可视化页面展示分析结果')
    vdown(1.00, 0.72)
    startend(ax, cx, 0.55, '结束')

    # 批次循环回边：走主流程列左侧的专用通道
    route(ax, [(2.80, 3.65), (1.30, 3.65), (1.30, 7.15), (2.50, 7.15)],
          label='是（继续下一批）', lx=0.72, ly=5.40, lrot=90)

    # 校验失败分支
    box(14.30, '提示文件校验失败原因，\n修正后重新发起流程', x=rx, w=rw, h=rh, fs=8.6)
    arrow(ax, (7.20, 14.30), (rx - rw / 2, 14.30), lw=1.2, label='否', lx=8.60, ly=14.62)
    arrow(ax, (rx, 13.85), (rx, 13.52), lw=1.2)
    startend(ax, rx, 13.35, '结束（校验失败）')

    # 评论列识别失败的补救分支，折线并回主流程「创建分析任务」右侧
    box(11.90, '管理员手工指定评论列', x=rx, w=rw, h=rh, fs=8.6)
    arrow(ax, (7.20, 11.90), (rx - rw / 2, 11.90), lw=1.2, label='否', lx=8.60, ly=12.22)
    route(ax, [(rx, 11.45), (rx, 10.70), (cx + bw / 2, 10.70)],
          label='指定后继续', lx=9.30, ly=10.95)

    # 模型不可用分支，直接结束
    box(9.50, '任务置为「失败」并记录失败原因', x=rx, w=rw, h=rh, fs=8.6)
    arrow(ax, (7.20, 9.50), (rx - rw / 2, 9.50), lw=1.2, label='否', lx=8.60, ly=9.82)
    arrow(ax, (rx, 9.05), (rx, 3.82), lw=1.2)
    startend(ax, rx, 3.65, '结束（任务失败）')

    fig.savefig(os.path.join(OUT, 'fig_activity_upload.png'), facecolor='white')
    plt.close(fig)


# ------------------------------------- 图3 活动图：结果查看与历史任务查询流程
def fig_activity_view():
    fig, ax = new_ax(11.6, 12.4)
    ax.set_xlim(-0.4, 15.6)
    ax.set_ylim(-1.2, 15.2)

    cx, bw, bh = 5.0, 5.4, 0.80
    rx, rw, rh = 12.4, 4.8, 0.90

    def box(y, t, x=cx, w=bw, h=bh, fs=9):
        rbox(ax, x, y, w, h, t, fs=fs)

    def vdown(y1, y2, lab=None, lx=None, ly=None):
        arrow(ax, (cx, y1), (cx, y2), lw=1.2, label=lab, lx=lx, ly=ly)

    startend(ax, cx, 14.40, '开始')
    arrow(ax, (cx, 14.22), (cx, 13.65), lw=1.2)
    box(13.25, '管理员进入「分析工作台」的任务列表')
    vdown(12.85, 12.50)
    box(12.10, '分页展示历史任务列表（按创建时间倒序）')
    vdown(11.70, 11.45)
    dia(ax, cx, 10.90, 4.8, 1.10, '是否输入检索条件\n（时间 / 状态 / 文件名）？', fs=8.6)
    vdown(10.35, 10.10, '否', cx + 0.45, 10.25)
    box(9.70, '选择目标任务并点击「查看结果」')
    vdown(9.30, 9.05)
    dia(ax, cx, 8.50, 4.8, 1.10, '任务状态是否为\n「已完成」？', fs=8.6)
    vdown(7.95, 7.70, '是', cx + 0.45, 7.85)
    box(7.30, '读取该任务的分析结果与关键词数据')
    vdown(6.90, 6.55)
    box(6.15, '渲染情感占比饼图与热点词词云')
    vdown(5.75, 5.50)
    dia(ax, cx, 4.95, 4.8, 1.10, '数据是否包含\n时间字段？', fs=8.6)
    vdown(4.40, 4.15, '是', cx + 0.45, 4.30)
    box(3.75, '渲染情感趋势折线图')
    vdown(3.35, 3.00)
    box(2.60, '点击图表分类，跳转明细页并按标签筛选')
    vdown(2.20, 1.95)
    dia(ax, cx, 1.40, 4.8, 1.10, '是否需要\n导出结果？', fs=8.6)
    vdown(0.85, 0.60, '是', cx + 0.45, 0.75)
    box(0.20, '选择导出范围并生成 Excel/CSV/JSON 或 HTML 报告')
    vdown(-0.20, -0.48)
    startend(ax, cx, -0.65, '结束', side='bottom')

    # 输入检索条件：折线并回「选择目标任务」
    box(10.90, '按条件检索并刷新任务列表', x=rx, w=rw, h=rh, fs=8.6)
    arrow(ax, (7.40, 10.90), (rx - rw / 2, 10.90), lw=1.2, label='是', lx=8.60, ly=11.22)
    route(ax, [(rx, 10.45), (rx, 9.70), (cx + bw / 2, 9.70)],
          label='返回列表', lx=9.40, ly=9.95)

    # 任务未完成：直接结束
    box(8.50, '提示「该任务暂无分析结果」', x=rx, w=rw, h=rh, fs=8.6)
    arrow(ax, (7.40, 8.50), (rx - rw / 2, 8.50), lw=1.2, label='否', lx=8.60, ly=8.82)
    arrow(ax, (rx, 8.05), (rx, 7.17), lw=1.2)
    startend(ax, rx, 7.00, '结束（无分析结果）')

    # 无时间字段：跳过趋势图，折线并在「渲染情感趋势折线图」之后
    route(ax, [(7.40, 4.95), (8.70, 4.95), (8.70, 2.60), (7.70, 2.60)],
          label='否', lx=7.95, ly=5.22)

    # 不导出：折线并在结束节点
    route(ax, [(7.40, 1.40), (8.70, 1.40), (8.70, -0.65), (5.18, -0.65)],
          label='否', lx=7.95, ly=1.67)

    fig.savefig(os.path.join(OUT, 'fig_activity_view.png'), facecolor='white')
    plt.close(fig)


# ------------------------------------- 图4 概念E-R图
def fig_er():
    fig, ax = new_ax(15.5, 9.2)
    ax.set_xlim(0, 17.6)
    ax.set_ylim(0, 10.4)

    EW, EH = 2.9, 2.2
    ents = {
        '用户': (2.0, 8.2, '用户编号(PK)\n账号\n密码哈希\n账号状态\n最近登录时间'),
        '分析任务': (6.8, 8.2, '任务编号(PK)\n任务名称/源文件名\n文件大小/模型版本号\n任务状态\n总条数/已处理条数'),
        '评论': (11.6, 8.2, '评论编号(PK)\n任务编号(FK)\n评论原文\n行号/评论时间'),
        '分析结果': (16.0, 8.2, '结果编号(PK)\n任务编号(FK)\n评论编号(FK)\n情感标签/置信度\n复核状态'),
        '任务统计': (6.8, 2.3, '统计编号(PK)\n任务编号(FK)\n三类条数/待复核数\n平均置信度'),
        '关键词': (16.0, 2.3, '关键词编号(PK)\n任务编号(FK)\n关键词\n权重/词频\n所属情感'),
    }
    for name, (x, y, attrs) in ents.items():
        sbox(ax, x, y, EW, EH, '', fc='#FFFFFF')
        ax.text(x, y + 0.82, name, ha='center', va='center', fontsize=10)
        ax.plot([x - EW / 2, x + EW / 2], [y + 0.58, y + 0.58], color=EC, lw=0.9)
        ax.text(x, y - 0.16, attrs, ha='center', va='center', fontsize=7.1, linespacing=1.4)

    dia(ax, 4.40, 8.2, 1.2, 0.8, '拥有', fs=7.6)
    dia(ax, 9.25, 8.2, 1.2, 0.8, '包含', fs=7.6)
    dia(ax, 13.80, 8.2, 1.2, 0.8, '对应', fs=7.6)
    dia(ax, 6.8, 5.2, 1.2, 0.8, '汇总', fs=7.6)
    dia(ax, 11.8, 2.3, 1.2, 0.8, '提取', fs=7.6)

    def seg(p1, p2):
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=EC, lw=0.95, zorder=3)

    def card(x, y, t):
        ax.text(x, y, t, fontsize=7.4, ha='center', va='center',
                bbox=dict(fc='white', ec='none', pad=0.4), zorder=5)

    # 用户 1:N 分析任务
    seg((3.45, 8.2), (3.80, 8.2)); seg((5.00, 8.2), (5.35, 8.2))
    card(3.60, 8.48, '1'); card(5.10, 8.48, 'N')
    # 分析任务 1:N 评论
    seg((8.25, 8.2), (8.65, 8.2)); seg((9.85, 8.2), (10.15, 8.2))
    card(8.42, 8.48, '1'); card(9.95, 8.48, 'N')
    # 评论 1:1 分析结果
    seg((13.05, 8.2), (13.20, 8.2)); seg((14.40, 8.2), (14.55, 8.2))
    card(13.12, 8.48, '1'); card(14.47, 8.48, '1')
    # 分析任务 1:1 任务统计
    seg((6.8, 7.1), (6.8, 5.6)); seg((6.8, 4.8), (6.8, 3.4))
    card(7.05, 5.34, '1'); card(7.05, 3.78, '1')
    # 分析任务 1:N 分析结果（沿实体上方通道绕行）
    ax.plot([7.5, 7.5], [9.3, 9.65], color=EC, lw=0.95, zorder=3)
    ax.plot([7.5, 15.7], [9.65, 9.65], color=EC, lw=0.95, zorder=3)
    arrow(ax, (15.7, 9.65), (15.7, 9.35), lw=0.95)
    card(11.8, 9.88, '产生 1:N')
    # 分析任务 1:N 关键词（沿实体右侧通道绕行）
    ax.plot([8.25, 9.6], [7.2, 6.4], color=EC, lw=0.95, zorder=3)
    ax.plot([9.6, 9.6], [6.4, 2.3], color=EC, lw=0.95, zorder=3)
    arrow(ax, (9.6, 2.3), (14.55, 2.3), lw=0.95)
    card(10.2, 6.6, '1:N')

    ax.text(0.4, 10.1, '图注：矩形为实体，菱形为联系，连线两端标注基数（1 / N），PK 为主标识，FK 为外键。',
            fontsize=8, ha='left')
    ax.text(0.4, 0.4, '说明：上传批次已并入分析任务表；模型版本号关联 model_info.json（文件存储，不单独建表）。',
            fontsize=7.8, ha='left')

    fig.savefig(os.path.join(OUT, 'fig_er.png'), facecolor='white')
    plt.close(fig)


# ------------------------------------------------------- 图5 顶层数据流图（0层）
def fig_dfd0():
    fig, ax = new_ax(12, 6.0)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 7.0)

    sbox(ax, 1.9, 3.6, 2.9, 1.4, '系统管理员', fs=10)
    sbox(ax, 12.1, 3.6, 2.9, 1.4, '系统管理员', fs=10)
    ax.add_patch(Circle((7.0, 3.6), 1.62, fc='#F2F7FF', ec=EC, lw=1.2, zorder=2))
    ax.text(7.0, 3.9, '0', ha='center', va='center', fontsize=11, zorder=3)
    ax.text(7.0, 3.25, '中文评论\n智能分析系统', ha='center', va='center', fontsize=9.5,
            linespacing=1.4, zorder=3)

    ins = [(4.55, '登录凭证与操作指令'), (3.6, '评论文件 / 文本 / 网页链接'), (2.65, '结果查询、复核与导出请求')]
    for y, t in ins:
        arrow(ax, (3.35, y), (5.55, y), lw=1.1)
        ax.text(4.45, y + 0.3, t, ha='center', fontsize=7.6,
                bbox=dict(fc='white', ec='none', pad=0.6))

    outs = [(4.55, '解析报告与任务进度'), (3.6, '情感分析结果与可视化数据'), (2.65, '导出文件（Excel/CSV/JSON/报告）')]
    for y, t in outs:
        arrow(ax, (8.45, y), (10.65, y), lw=1.1)
        ax.text(9.55, y + 0.3, t, ha='center', fontsize=7.6,
                bbox=dict(fc='white', ec='none', pad=0.6))

    fig.savefig(os.path.join(OUT, 'fig_dfd0.png'), facecolor='white')
    plt.close(fig)


# ------------------------------------------- 图6 1层数据流图：评论解析与智能分析
def fig_dfd1a():
    fig, ax = new_ax(14, 6.4)
    ax.set_xlim(0, 17.5)
    ax.set_ylim(0, 7.4)

    sbox(ax, 1.7, 5.0, 2.6, 1.2, '系统管理员', fs=9.5)
    ell(ax, 5.2, 5.0, 3.4, 1.5, '1  评论文件与智能输入解析', fs=8.6)
    dstore(ax, 5.2, 1.6, 2.9, 1.0, 'D1  评论表', fs=8.8)
    ell(ax, 9.2, 5.0, 3.2, 1.5, '2  智能分析任务调度', fs=9)
    dstore(ax, 9.2, 1.6, 2.9, 1.0, 'D4  分析任务表', fs=8.8)
    ell(ax, 13.2, 5.0, 3.4, 1.5, '3  情感分析与关键词提取', fs=8.8)
    dstore(ax, 13.2, 1.6, 2.9, 1.0, 'D2  分析结果表', fs=8.8)
    dstore(ax, 16.2, 5.0, 2.2, 1.0, 'D3 关键词表', fs=8.8)

    arrow(ax, (3.0, 5.25), (3.5, 5.25), label='文件/文本/链接', lx=3.25, ly=5.62)
    arrow(ax, (3.6, 4.75), (3.0, 4.75), label='解析报告', lx=3.25, ly=4.4)
    arrow(ax, (5.2, 4.25), (5.2, 2.1), label='清洗后评论', lx=6.05, ly=3.2)
    arrow(ax, (6.9, 5.0), (7.6, 5.0), label='任务编号', lx=7.22, ly=5.35)
    arrow(ax, (9.2, 4.25), (9.2, 2.1), label='任务记录', lx=10.0, ly=3.2)
    arrow(ax, (10.8, 5.0), (11.5, 5.0), label='分析调度指令', lx=11.15, ly=5.35)
    poly(ax, [(5.2, 3.1), (5.2, 3.45), (13.2, 3.45), (13.2, 4.25)],
         label='待分析评论', lx=9.2, ly=3.75)
    arrow(ax, (13.2, 4.25), (13.2, 2.1), label='分析结果', lx=14.0, ly=3.2)
    arrow(ax, (14.9, 5.0), (15.15, 5.0), label='关键词', lx=15.4, ly=5.4)
    arrow(ax, (11.5, 4.55), (10.8, 4.55), label='进度与状态', lx=11.15, ly=4.2)
    ax.text(0.4, 6.9, '(1) 评论文件/智能输入解析与智能分析加工的分解', fontsize=9)

    fig.savefig(os.path.join(OUT, 'fig_dfd1a.png'), facecolor='white')
    plt.close(fig)


# ------------------------------------------- 图7 1层数据流图：结果统计与查询导出
def fig_dfd1b():
    fig, ax = new_ax(14, 6.0)
    ax.set_xlim(0, 16.5)
    ax.set_ylim(0, 7.0)

    sbox(ax, 2.0, 3.5, 2.6, 1.2, '系统管理员', fs=9.5)
    ell(ax, 6.0, 3.5, 3.2, 1.5, '4  结果统计与汇总', fs=9)
    dstore(ax, 6.0, 6.0, 2.9, 1.0, 'D2  分析结果表', fs=8.8)
    dstore(ax, 6.0, 1.0, 2.9, 1.0, 'D3  关键词表', fs=8.8)
    ell(ax, 10.6, 5.2, 3.2, 1.5, '5  可视化数据组织', fs=9)
    ell(ax, 10.6, 1.8, 3.4, 1.5, '6  明细查询与导出', fs=9)
    sbox(ax, 14.6, 3.5, 2.6, 1.2, '系统管理员', fs=9.5)

    arrow(ax, (3.3, 3.5), (4.4, 3.5), label='结果查看请求', lx=3.85, ly=3.85)
    arrow(ax, (6.0, 5.5), (5.9, 4.25), label='读取分析结果', lx=7.15, ly=4.9)
    arrow(ax, (5.9, 2.75), (6.0, 1.5), label='读取关键词', lx=6.9, ly=2.1)
    arrow(ax, (7.4, 4.15), (9.05, 5.0), label='任务统计结果', lx=8.2, ly=4.8)
    arrow(ax, (7.6, 3.2), (9.0, 2.2), label='明细查询条件', lx=8.2, ly=2.5)
    arrow(ax, (12.2, 5.35), (13.3, 4.1), label='图表数据', lx=12.6, ly=4.9)
    arrow(ax, (12.3, 1.75), (13.3, 3.0), label='明细与导出文件', lx=12.9, ly=2.2)
    ax.text(0.4, 6.6, '(2) 结果统计、可视化、人工复核与查询导出加工的分解', fontsize=9)

    fig.savefig(os.path.join(OUT, 'fig_dfd1b.png'), facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    fig_usecase()
    fig_activity_upload()
    fig_activity_view()
    fig_er()
    fig_dfd0()
    fig_dfd1a()
    fig_dfd1b()
    print('生成完成：', os.listdir(OUT))
