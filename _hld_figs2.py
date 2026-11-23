# -*- coding: utf-8 -*-
"""补充 5 张实验报告所需的设计图：包图、组件图、模块结构图、界面导航图、页面线框图。
绘制规则：所有连线正交走线，只与方框边界相交，不穿越任何方框内部。
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

from _figs import rbox, sbox, dia, dstore, arrow, route, startend, EC
from _hld_figs import new_ax, label

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

OUT = r'e:\trae\中文评论智能分析系统\_figs'


def pkg(ax, cx, cy, w, h, name, body='', fs=8.2, fc='#F0F6FF'):
    """UML 包符号：带标签页的矩形。"""
    ax.add_patch(Rectangle((cx - w / 2, cy + h / 2), w * 0.46, 0.30,
                           fc=fc, ec=EC, lw=1.1, zorder=2))
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h,
                           fc=fc, ec=EC, lw=1.1, zorder=2))
    ax.text(cx - w / 2 + 0.14, cy + h / 2 + 0.15, name,
            ha='left', va='center', fontsize=fs, zorder=3)
    if body:
        ax.text(cx, cy - 0.10, body, ha='center', va='center',
                fontsize=fs - 0.9, linespacing=1.55, zorder=3)


def cbox(ax, cx, cy, w, h, title, body, fs=8.0):
    """UML 组件：左上角 <<component>> 标签的矩形。"""
    rbox(ax, cx, cy, w, h, '', fs=fs, fc='#FFFFFF')
    ax.text(cx - w / 2 + 0.12, cy + h / 2 - 0.20, '<<component>>',
            ha='left', va='center', fontsize=fs - 2.0, color='#666666', zorder=3)
    ax.text(cx, cy + 0.06, title, ha='center', va='center', fontsize=fs, zorder=3)
    if body:
        ax.text(cx, cy - 0.26, body, ha='center', va='center',
                fontsize=fs - 1.0, color='#555555', linespacing=1.4, zorder=3)


# ==================================================== 图：分层包图（Package）
def fig_package():
    fig, ax = new_ax(12.6, 6.6)
    ax.set_xlim(0.2, 18.8)
    ax.set_ylim(1.6, 11.9)

    ax.add_patch(Rectangle((0.8, 2.1), 17.4, 9.1, fc='#FCFCFC',
                           ec='#9E9E9E', lw=1.2, ls=(0, (6, 3)), zorder=1))
    ax.text(0.98, 10.94, 'com.example.commentanalysis（应用根包）',
            ha='left', va='center', fontsize=9.5, color='#444444', zorder=3)

    P = [(3.2, 8.7), (7.4, 8.7), (11.6, 8.7), (15.8, 8.7)]
    pkg(ax, *P[0], 3.6, 1.90, 'web', '静态资源\nhtml / css / js\nECharts 页面')
    pkg(ax, *P[1], 3.6, 1.90, 'controller', '接口控制层\nUser / File / Input\nTask / Result / Dashboard')
    pkg(ax, *P[2], 3.6, 1.90, 'service', '业务服务层\nUser / File / Input / Task\nResult / Dashboard / Settings')
    pkg(ax, *P[3], 3.6, 1.90, 'scheduler', '异步调度\nInferenceScheduler\nTaskRecoveryRunner')

    Q = [(3.2, 5.0), (7.4, 5.0), (11.6, 5.0), (15.8, 5.0)]
    pkg(ax, *Q[0], 3.6, 1.90, 'entity / dto / vo', '数据对象\n实体 / 请求参数\n响应视图对象')
    pkg(ax, *Q[1], 3.6, 1.90, 'mapper', '数据访问层\n6 个 MyBatis-Plus\nMapper')
    pkg(ax, *Q[2], 3.6, 1.90, 'ai', '智能服务层\nSentimentInferenceService\nModelRepository')
    pkg(ax, *Q[3], 3.6, 1.90, 'common / config', '通用与配置\n统一响应 / 全局异常\n属性配置 / 导入校验')

    # 依赖关系（<<access>>，全部走包间空白通道）
    arrow(ax, (5.0, 8.7), (5.6, 8.7), lw=1.2, ls='--')
    label(ax, 5.30, 9.02, '<<access>>', fs=6.8)
    arrow(ax, (9.2, 8.7), (9.8, 8.7), lw=1.2, ls='--')
    label(ax, 9.50, 9.02, '<<access>>', fs=6.8)
    arrow(ax, (13.4, 8.7), (14.0, 8.7), lw=1.2, ls='--')
    label(ax, 13.70, 9.02, '<<access>>', fs=6.8)
    route(ax, [(11.6, 7.75), (11.6, 7.00), (7.4, 7.00), (7.4, 5.95)],
          label='<<access>>', lx=9.50, ly=7.26, fs=6.8)
    route(ax, [(12.5, 7.75), (12.5, 5.95)],
          label='<<access>>', lx=13.35, ly=6.85, fs=6.8)
    arrow(ax, (5.6, 5.0), (5.0, 5.0), lw=1.2, ls='--')
    label(ax, 5.30, 5.32, '<<access>>', fs=6.8)
    route(ax, [(11.6, 4.05), (11.6, 3.10), (3.2, 3.10), (3.2, 4.05)],
          label='<<access>>', lx=7.40, ly=3.36, fs=6.8)

    ax.text(0.85, 1.80,
            '说明：虚线箭头表示包之间的 <<access>> 访问依赖；web 为静态资源包，随应用打包由内嵌 Tomcat 提供访问。',
            fontsize=7.8, ha='left', va='center')

    fig.savefig(os.path.join(OUT, 'hld_package.png'), facecolor='white')
    plt.close(fig)


# ====================================================== 图：组件图（Component）
def fig_component():
    fig, ax = new_ax(12.6, 6.5)
    ax.set_xlim(0.4, 16.0)
    ax.set_ylim(2.1, 10.2)

    cbox(ax, 3.0, 9.02, 3.2, 1.30, '前端页面组件', 'HTML / CSS / JS + ECharts')
    cbox(ax, 9.0, 9.02, 3.6, 1.30, '接口控制层组件', 'User / File / Input / Task\nResult / Dashboard / Settings')
    cbox(ax, 9.0, 6.9, 3.6, 1.30, '业务服务组件', '账号 / 文件 / 智能输入 / 任务\n结果 / 复核 / 看板 / 设置')
    cbox(ax, 5.0, 4.9, 3.4, 1.30, '数据访问组件', '6 个 MyBatis-Plus Mapper')
    cbox(ax, 9.0, 4.9, 3.4, 1.30, '异步调度组件', 'InferenceScheduler\nTaskRecoveryRunner')
    cbox(ax, 13.0, 4.9, 3.4, 1.30, '智能服务组件', 'SentimentInferenceService\n+ DJL 推理内核')

    sbox(ax, 5.0, 2.9, 3.4, 1.10, 'MySQL 8.0\n业务数据库', fs=8.2, fc='#E8F5E9')
    dstore(ax, 13.0, 2.9, 3.4, 1.10, '模型文件 / 停用词表\n（本地资源）', fs=7.6)

    arrow(ax, (4.6, 9.02), (7.2, 9.02), lw=1.3)
    label(ax, 5.90, 9.36, 'RESTful API（HTTP / JSON）', fs=7.0)
    arrow(ax, (9.0, 8.37), (9.0, 7.55), lw=1.3)
    label(ax, 10.20, 7.96, '应用内方法调用', fs=7.0)
    route(ax, [(7.2, 6.62), (5.0, 6.62), (5.0, 5.55)])
    label(ax, 5.05, 6.88, '持久化调用', fs=7.0)
    arrow(ax, (9.0, 6.25), (9.0, 5.55), lw=1.3)
    label(ax, 9.32, 5.88, '提交批次', fs=7.0)
    route(ax, [(10.8, 6.90), (13.0, 6.90), (13.0, 5.55)])
    label(ax, 12.05, 7.16, 'batchInfer / extractKeywords', fs=7.0)
    arrow(ax, (5.0, 4.25), (5.0, 3.45), lw=1.3)
    label(ax, 5.10, 3.85, 'JDBC', fs=7.0)
    arrow(ax, (13.0, 4.25), (13.0, 3.45), lw=1.3)
    label(ax, 13.68, 3.85, '启动加载', fs=7.0)

    ax.text(0.45, 2.22,
            '说明：业务服务组件依赖数据访问组件与智能服务组件；智能服务组件不依赖任何业务组件，为单向被依赖的叶子组件。',
            fontsize=7.8, ha='left', va='center')

    fig.savefig(os.path.join(OUT, 'hld_component.png'), facecolor='white')
    plt.close(fig)


# ==================================================== 图：模块结构图（功能树）
def fig_module_tree():
    fig, ax = new_ax(17.0, 6.0)
    ax.set_xlim(0.0, 23.6)
    ax.set_ylim(1.8, 9.8)

    xs = [1.25 + i * 2.05 for i in range(11)]
    mods = ['M1 账号管理', 'M2 评论文件管理', 'M3 智能分析任务', 'M4 结果可视化',
            'M5 历史记录', 'M6 结果导出', 'M7 智能输入', 'M8 人工复核',
            'M9 看板/对比', 'M10 设置/日志', 'M11 智能模型']
    leaves = [
        ['注册/登录', '修改密码', '退出登录'],
        ['文件校验', '评论列识别', '清洗入库', '解析报告'],
        ['任务创建', '状态/进度', '终止/重试', '重命名/删除'],
        ['情感占比', '热词词云', '情感趋势', '置信度分布', '明细筛选'],
        ['任务检索', '历史结果', '任务删除'],
        ['Excel/CSV/JSON', '统计摘要', 'HTML 报告'],
        ['文本/链接识别', '网页正文预览', '文本切分入库'],
        ['待复核筛选', '单条/批量复核', '复核质量'],
        ['看板汇总', '任务对比'],
        ['模型信息', '推理参数', '操作日志'],
        ['模型加载', '情感推理', '关键词提取'],
    ]

    rbox(ax, 11.7, 8.85, 5.8, 0.86, '中文评论智能分析系统', fs=9.5, fc='#EAF3FB')
    for x, m in zip(xs, mods):
        rbox(ax, x, 6.65, 1.92, 0.78, m, fs=6.6, fc='#EAF7EE')

    # 根到各模块的总线（走模块行上方的空白通道）
    ax.plot([11.7, 11.7], [8.42, 7.66], color=EC, lw=1.2, zorder=4)
    ax.plot([1.25, 21.75], [7.66, 7.66], color=EC, lw=1.2, zorder=4)
    for x in xs:
        arrow(ax, (x, 7.66), (x, 7.04), lw=1.2)

    for x, ls in zip(xs, leaves):
        top = 6.26
        for i, t in enumerate(ls):
            y = 5.55 - i * 0.64
            rbox(ax, x, y, 1.92, 0.52, t, fs=6.1, fc='#FFFFFF')
            if i == 0:
                arrow(ax, (x, top), (x, y + 0.26), lw=1.0)
            else:
                arrow(ax, (x, y + 0.90), (x, y + 0.26), lw=1.0)

    fig.savefig(os.path.join(OUT, 'hld_module_tree.png'), facecolor='white')
    plt.close(fig)


# ====================================================== 图：界面导航结构图
def fig_ui_nav():
    fig, ax = new_ax(14.4, 6.0)
    ax.set_xlim(0.2, 21.6)
    ax.set_ylim(1.4, 10.2)

    rbox(ax, 2.6, 9.15, 3.2, 0.88, '登录/注册页', fs=8.2, fc='#EAF3FB')
    rbox(ax, 8.6, 9.15, 5.8, 0.88, '系统主界面框架（左侧导航 + 内容区）', fs=8.2, fc='#EAF3FB')

    xs = [2.4, 6.6, 10.8, 15.0, 19.2]
    pages = ['分析工作台\n上传/智能输入/任务列表', '数据看板\n跨任务汇总', '任务对比\n两个任务并排',
             '系统设置\n模型/参数/日志', '个人中心\n改密/退出']
    for x, t in zip(xs, pages):
        rbox(ax, x, 6.55, 3.4, 1.05, t, fs=7.2, fc='#EAF7EE')

    rbox(ax, 4.5, 4.35, 3.2, 0.85, '解析报告与进度', fs=7.4, fc='#FFFFFF')
    rbox(ax, 8.6, 4.35, 3.2, 0.85, '结果可视化\n统计/词云/趋势/置信度', fs=7.0, fc='#FFFFFF')
    rbox(ax, 12.7, 4.35, 3.2, 0.85, '结果明细与筛选', fs=7.4, fc='#FFFFFF')
    rbox(ax, 17.2, 4.35, 3.2, 0.85, '人工复核弹窗', fs=7.4, fc='#FFF4E6')
    rbox(ax, 8.6, 2.35, 4.6, 0.85, '导出 Excel/CSV/JSON 或 HTML 报告', fs=7.2, fc='#FFF4E6')

    arrow(ax, (4.2, 9.15), (5.70, 9.15), lw=1.3)
    label(ax, 4.95, 9.49, '登录成功', fs=7.2)

    # 主界面到五个视图：总线走视图行上方通道
    ax.plot([8.6, 8.6], [8.71, 7.95], color=EC, lw=1.2, zorder=4)
    ax.plot([2.4, 19.2], [7.95, 7.95], color=EC, lw=1.2, zorder=4)
    for x in xs:
        arrow(ax, (x, 7.95), (x, 7.08), lw=1.2)
    label(ax, 11.0, 8.20, '左侧导航切换', fs=7.2)

    route(ax, [(2.9, 6.02), (2.9, 5.05), (4.5, 5.05), (4.5, 4.78)],
          label='上传/智能输入', lx=3.0, ly=5.30, fs=6.8)
    arrow(ax, (6.1, 4.35), (7.0, 4.35), lw=1.1)
    label(ax, 6.55, 4.68, '分析完成', fs=6.8)
    arrow(ax, (10.2, 4.35), (11.1, 4.35), lw=1.1)
    label(ax, 10.65, 4.68, '点击下钻', fs=6.8)
    arrow(ax, (14.3, 4.35), (15.6, 4.35), lw=1.1)
    label(ax, 14.95, 4.68, '低置信度复核', fs=6.8)
    route(ax, [(13.8, 3.92), (13.8, 2.78), (11.2, 2.78)],
          label='导出/报告', lx=13.0, ly=3.35, fs=6.8)

    ax.text(0.30, 1.55,
            '说明：箭头表示页面跳转关系；未登录访问任一业务页面均被 AuthInterceptor 拦截并跳回登录页。',
            fontsize=7.8, ha='left', va='center')

    fig.savefig(os.path.join(OUT, 'hld_ui_nav.png'), facecolor='white')
    plt.close(fig)


# ==================================================== 图：低保真页面线框图
def wf_frame(ax, x0, y0, w, h, title):
    ax.add_patch(Rectangle((x0, y0), w, h, fc='#FFFFFF', ec=EC, lw=1.3, zorder=2))
    ax.add_patch(Rectangle((x0, y0 + h - 0.55), w, 0.55, fc='#EDEDED', ec=EC, lw=1.0, zorder=3))
    for i in range(3):
        ax.add_patch(Circle((x0 + 0.26 + i * 0.26, y0 + h - 0.28), 0.075,
                            fc='#BBBBBB', ec='none', zorder=4))
    ax.text(x0 + w / 2, y0 + h - 0.28, title, ha='center', va='center',
            fontsize=8.4, zorder=4)
    ax.add_patch(Rectangle((x0, y0), w, h - 0.55, fc='none', ec=EC, lw=1.3, zorder=3))


def fig_wireframe():
    fig, ax = new_ax(15.0, 6.2)
    ax.set_xlim(0.0, 24.0)
    ax.set_ylim(0.6, 10.4)

    def ph(x0, y0, w, h, text='', fc='#F7F7F7', fs=7.0):
        ax.add_patch(Rectangle((x0, y0), w, h, fc=fc, ec='#BDBDBD', lw=0.9, zorder=3))
        if text:
            ax.text(x0 + w / 2, y0 + h / 2, text, ha='center', va='center',
                    fontsize=fs, color='#555555', zorder=4)

    def lines(x0, y0, w, n, gap=0.30):
        for i in range(n):
            ax.plot([x0, x0 + w], [y0 - i * gap, y0 - i * gap],
                    color='#CCCCCC', lw=2.0, zorder=3)

    # ---- 面板 1：评论文件管理页 ----
    x0, y0, w, h = 0.6, 1.0, 7.2, 8.8
    wf_frame(ax, x0, y0, w, h, '评论文件管理页')
    ph(x0 + 0.3, y0 + h - 2.1, w - 0.6, 1.3, '上传区：点击或拖拽 .xlsx / .xls / .csv（≤ 50 MB）', fc='#F2F7FF')
    ph(x0 + 0.3, y0 + h - 3.9, w - 0.6, 1.5, '', fc='#FFFFFF')
    for i in range(4):
        ph(x0 + 0.55 + i * 1.65, y0 + h - 3.55, 1.45, 0.85, '—', fc='#EDEDED')
    ax.text(x0 + 0.34, y0 + h - 4.06, '解析报告：总条数 / 有效条数 / 过滤条数 / 失败原因', fontsize=6.8, va='top')
    ph(x0 + 0.3, y0 + h - 6.3, w - 0.6, 2.1, '', fc='#FFFFFF')
    ph(x0 + 0.42, y0 + h - 4.65, w - 0.84, 0.42, '评论原文 | 行号 | 清洗结果', fc='#E6E6E6', fs=6.6)
    lines(x0 + 0.6, y0 + h - 5.30, w - 1.2, 3)

    # ---- 面板 2：结果可视化页 ----
    x0 = 8.4
    wf_frame(ax, x0, y0, w, h, '结果可视化页')
    for i in range(4):
        ph(x0 + 0.28 + i * 1.72, y0 + h - 1.95, 1.55, 0.80, '统计卡', fc='#EAF3FB', fs=6.6)
    ph(x0 + 0.3, y0 + h - 5.05, 3.2, 2.85, '', fc='#FFFFFF')
    ax.add_patch(Circle((x0 + 1.20, y0 + h - 3.62), 0.72, fc='#F0C9A0', ec='#BDBDBD', lw=0.9, zorder=4))
    for i in range(3):
        ax.add_patch(Rectangle((x0 + 2.10, y0 + h - 3.00 - i * 0.42), 0.22, 0.20, fc='#D8D8D8', ec='none', zorder=4))
        ax.plot([x0 + 2.40, x0 + 3.15], [y0 + h - 2.90 - i * 0.42] * 2, color='#CCCCCC', lw=2.0, zorder=4)
    ax.text(x0 + 1.90, y0 + h - 4.90, '情感占比饼图', fontsize=6.8, ha='center', zorder=4)
    ph(x0 + 3.72, y0 + h - 5.05, 3.2, 2.85, '', fc='#FFFFFF')
    ax.text(x0 + 5.32, y0 + h - 2.35, '质 量   物 流   价 格   服 务   包 装', fontsize=7.4,
            ha='center', color='#888888', zorder=4)
    ax.text(x0 + 5.32, y0 + h - 4.90, '热点词词云（权重前 50）', fontsize=6.8, ha='center', zorder=4)
    ph(x0 + 0.3, y0 + h - 6.6, w - 0.6, 1.3, '情感趋势折线图（数据含时间字段时展示）', fc='#FAFAFA', fs=6.8)

    # ---- 面板 3：结果明细页 ----
    x0 = 16.2
    wf_frame(ax, x0, y0, w, h, '结果明细页')
    for i in range(3):
        ph(x0 + 0.28 + i * 1.62, y0 + h - 1.80, 1.45, 0.62, '筛选框', fc='#FFFFFF', fs=6.6)
    ph(x0 + 5.10, y0 + h - 1.80, 1.80, 0.62, '查询 / 重置 / 导出', fc='#EAF7EE', fs=6.6)
    ph(x0 + 0.3, y0 + h - 6.1, w - 0.6, 3.6, '', fc='#FFFFFF')
    ph(x0 + 0.42, y0 + h - 2.72, w - 0.84, 0.44, '评论原文 | 情感标签 | 置信度 | 是否待复核', fc='#E6E6E6', fs=6.6)
    for i in range(5):
        yy = y0 + h - 3.50 - i * 0.55
        ax.plot([x0 + 0.60, x0 + 4.60], [yy, yy], color='#CCCCCC', lw=2.0, zorder=4)
        ax.add_patch(Rectangle((x0 + 4.85, yy - 0.14), 0.85, 0.28,
                               fc=['#DCF0DC', '#F7DCDC', '#EDEDED'][i % 3], ec='none', zorder=4))
        ax.plot([x0 + 5.95, x0 + 6.55], [yy, yy], color='#CCCCCC', lw=2.0, zorder=4)
    ph(x0 + 2.20, y0 + h - 6.00, 3.60, 0.44, '上一页 1 2 3 … 下一页', fc='#F2F2F2', fs=6.6)

    fig.savefig(os.path.join(OUT, 'hld_wireframe.png'), facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    fig_package()
    fig_component()
    fig_module_tree()
    fig_ui_nav()
    fig_wireframe()
    print('补充图生成完成')
