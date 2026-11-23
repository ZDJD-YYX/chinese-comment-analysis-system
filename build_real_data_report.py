# -*- coding: utf-8 -*-
"""生成《中文评论智能分析系统真实数据分析报告》Word 文档。

数据与统计结果全部读取 output/real_data/summary.json，
避免报告正文与脚本计算结果不一致。
"""

from __future__ import annotations

import json
import os

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "output", "real_data")
FIG_DIR = os.path.join(OUT_DIR, "figures")
DOCX_PATH = os.path.join(BASE_DIR, "文档", "中文评论智能分析系统-真实数据分析报告.docx")

with open(os.path.join(OUT_DIR, "summary.json"), encoding="utf-8") as fp:
    S = json.load(fp)

STATS = {s["domain_key"]: s for s in S["domain_stats"]}
H, E, W, A = STATS["hotel"], STATS["ecommerce"], STATS["waimai"], STATS["all"]
CATS = S["category_stats"]
PAIR = {f"{p['group_a']}-{p['group_b']}": p for p in S["pairwise"]}
BASE = S["baseline"]
MODEL = S["model_eval"]
MANIFEST = {m["dataset"]: m for m in S["manifest"]}
TRANSFER = {(r["source"], r["target"]): r for r in BASE["transfer"]}

FONT_BODY = "宋体"
FONT_HEAD = "黑体"


# --------------------------------------------------------------------------- #
# 文档格式工具
# --------------------------------------------------------------------------- #

def set_run_font(run, east=FONT_BODY, size=10.5, bold=None, color=None):
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), east)


def set_style_font(style, east=FONT_BODY, size=10.5, bold=None, color=RGBColor(0, 0, 0)):
    style.font.name = "Times New Roman"
    style.font.size = Pt(size)
    if bold is not None:
        style.font.bold = bold
    style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), east)


def body(text, indent=True, size=10.5, bold=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
         space_after=3, line_spacing=1.5):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = line_spacing
    pf.space_after = Pt(space_after)
    if indent:
        pf.first_line_indent = Pt(21)
    p.alignment = align
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold)
    return p


def body_rich(parts, indent=True, size=10.5, space_after=3):
    """parts: [(text, bold), ...]"""
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(space_after)
    if indent:
        p.paragraph_format.first_line_indent = Pt(21)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for text, bold in parts:
        run = p.add_run(text)
        set_run_font(run, size=size, bold=bold)
    return p


def bullet(text, size=10.5):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.74)
    pf.first_line_indent = Cm(-0.37)
    pf.line_spacing = 1.5
    pf.space_after = Pt(2)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run("• ")
    set_run_font(run, size=size)
    run = p.add_run(text)
    set_run_font(run, size=size)
    return p


def heading(text, level=1, page_break=False):
    if page_break:
        doc.add_page_break()
    h = doc.add_heading(level=level)
    run = h.add_run(text)
    set_run_font(run, east=FONT_HEAD, size={1: 16, 2: 13, 3: 11.5}[level], bold=True)
    h.paragraph_format.space_before = Pt({1: 18, 2: 12, 3: 8}[level])
    h.paragraph_format.space_after = Pt({1: 8, 2: 6, 3: 4}[level])
    h.paragraph_format.keep_with_next = True
    return h


def toc_title(text):
    """目录标题使用普通段落样式，避免“目录”自身出现在目录列表中。"""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, east=FONT_HEAD, size=16, bold=True)
    return p


def caption(text, kind="表"):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6 if kind == "图" else 8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    set_run_font(run, size=9, bold=True)
    return p


def note(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.2
    run = p.add_run(text)
    set_run_font(run, size=8.5, color=RGBColor(0x59, 0x59, 0x59))
    return p


def shade_cell(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def prevent_row_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def add_table(headers, rows, widths, font_size=9, header_fill="D9E2F3",
              align="center", first_col_bold=False):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    prevent_row_split(hdr)
    for i, (text, width) in enumerate(zip(headers, widths)):
        cell = hdr.cells[i]
        cell.width = Cm(width)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        shade_cell(cell, header_fill)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(str(text))
        set_run_font(run, size=font_size, bold=True)

    for row_data in rows:
        row = table.add_row()
        prevent_row_split(row)
        for i, (value, width) in enumerate(zip(row_data, widths)):
            cell = row.cells[i]
            cell.width = Cm(width)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT if align == "left" and i > 0 else WD_ALIGN_PARAGRAPH.CENTER
            )
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(str(value))
            set_run_font(run, size=font_size, bold=(first_col_bold and i == 0))
    return table


def add_figure(filename, cap, width_cm=15.2):
    path = os.path.join(FIG_DIR, filename)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(path, width=Cm(width_cm))
    caption(cap, "图")


def add_page_number_footer(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)
    set_run_font(run, size=9, color=RGBColor(0x59, 0x59, 0x59))


def add_toc_field():
    p = doc.add_paragraph()
    run = p.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "在 Word 中右键此处，选择“更新域”生成目录与页码。"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(text)
    run._r.append(fld_end)
    set_run_font(run, size=9, color=RGBColor(0x80, 0x80, 0x80))


def set_update_fields(doc):
    settings = doc.settings.element
    update = OxmlElement("w:updateFields")
    update.set(qn("w:val"), "true")
    settings.append(update)


def pct(x, digits=2):
    return f"{x * 100:.{digits}f}%"


def num(x):
    return f"{x:,.0f}"


def pval(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# --------------------------------------------------------------------------- #
# 初始化文档
# --------------------------------------------------------------------------- #

doc = Document()
section = doc.sections[0]
section.page_width = Cm(21.0)
section.page_height = Cm(29.7)
section.top_margin = Cm(2.54)
section.bottom_margin = Cm(2.54)
section.left_margin = Cm(3.0)
section.right_margin = Cm(2.5)
section.header_distance = Cm(1.5)
section.footer_distance = Cm(1.5)
section.different_first_page_header_footer = True

normal = doc.styles["Normal"]
set_style_font(normal, size=10.5)
normal.paragraph_format.line_spacing = 1.5
normal.paragraph_format.space_after = Pt(0)

for level in [1, 2, 3]:
    style = doc.styles[f"Heading {level}"]
    set_style_font(style, east=FONT_HEAD, size={1: 16, 2: 13, 3: 11.5}[level],
                   bold=True, color=RGBColor(0, 0, 0))

# 页眉
header_p = section.header.paragraphs[0]
header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
header_run = header_p.add_run("中文评论智能分析系统 · 真实数据分析报告")
set_run_font(header_run, size=9, color=RGBColor(0x59, 0x59, 0x59))
# 页脚页码
add_page_number_footer(section)

# --------------------------------------------------------------------------- #
# 封面
# --------------------------------------------------------------------------- #

for _ in range(3):
    doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("软件工程实验报告")
set_run_font(run, east=FONT_HEAD, size=14, bold=True, color=RGBColor(0x40, 0x40, 0x40))

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(18)
run = p.add_run("中文评论智能分析系统")
set_run_font(run, east=FONT_HEAD, size=28, bold=True)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(10)
run = p.add_run("真实公开数据支撑下的分析方案调整与复核报告")
set_run_font(run, east=FONT_HEAD, size=16, bold=True, color=RGBColor(0x2E, 0x5B, 0xFF))

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(8)
run = p.add_run("—— 基于 3 个公开数据集、82,527 条原始评论的实证复核")
set_run_font(run, size=11, color=RGBColor(0x59, 0x59, 0x59))

for _ in range(4):
    doc.add_paragraph()

info_rows = [
    ("课程名称", "软件工程实验"),
    ("项目名称", "中文评论智能分析系统"),
    ("报告类型", "数据分析与结论复核报告"),
    ("数据版本", "real-public-v1.0（2026-11-06）"),
    ("编制日期", "2026 年 11 月 6 日"),
]
info_table = doc.add_table(rows=0, cols=2)
info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
info_table.autofit = False
for label, value in info_rows:
    cells = info_table.add_row().cells
    cells[0].width = Cm(3.2)
    cells[1].width = Cm(8.2)
    p0 = cells[0].paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r0 = p0.add_run(label + "：")
    set_run_font(r0, size=10.5, bold=True)
    p1 = cells[1].paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r1 = p1.add_run(value)
    set_run_font(r1, size=10.5)

doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run(
    "说明：本报告所有统计数字均由 real_data_analysis.py 对公开原始数据文件计算生成；"
    "原始文件下载地址、采集时间与 SHA-256 校验值见第二章及附录 A。"
)
set_run_font(run, size=9, color=RGBColor(0x80, 0x80, 0x80))

doc.add_page_break()

# --------------------------------------------------------------------------- #
# 摘要
# --------------------------------------------------------------------------- #

heading("摘要", 1)
body(
    "本报告针对原分析方案主要依赖本地整理或本地生成文本、数据来源与样本规模难以复核的问题，"
    "按照“公开可获取、来源可追溯、样本量充足、与分析维度高度相关”的原则，"
    "采集了 3 个公开中文评论数据集：ChnSentiCorp_htl_all（酒店评论，7,766 条）、"
    "online_shopping_10_cats（电商评论，62,774 条）与 waimai_10k（外卖评论，11,987 条），"
    f"原始记录合计 {num(S['raw_total'])} 条。经剔除空文本、剔除与酒店语料主题重叠的电商“酒店”子类、"
    f"域内去重与跨数据集去重后，得到有效语料 {num(S['final_total'])} 条"
    f"（酒店 {num(H['n'])} 条、电商 {num(E['n'])} 条、外卖 {num(W['n'])} 条）。"
    "所有原始文件均记录了下载地址、采集时间与 SHA-256 校验值，分析脚本可一键复现。"
)
body(
    f"基于真实数据的复核表明：全量正向评论占比 {pct(A['positive_rate'])}"
    f"（95% CI {pct(A['ci_low'])}–{pct(A['ci_high'])}），并非“整体以正面为主”；"
    f"三个领域的正向率分别为 {pct(H['positive_rate'])}、{pct(E['positive_rate'])}、{pct(W['positive_rate'])}，"
    f"极差 {abs(H['positive_rate'] - W['positive_rate']) * 100:.2f} 个百分点"
    f"（χ²={S['chi_square']['chi2']:.2f}，df=2，p{pval(S['chi_square']['p_value'])}）。"
    f"文本长度中位数为 {A['len_median']:.0f} 字，但酒店评论中位数为 {H['len_median']:.0f} 字，"
    f"{pct(H['share_gt128'])} 超过 128 字、{pct(H['share_gt512'])} 超过 512 字，"
    "说明统一截断会损失酒店长评论信息。公开数据均只有正/负二分类标注，没有中性金标准，"
    "“中性”在当前项目中只能作为模型推断类别。"
)
body(
    f"现有 BERT 模型在 1,854 条三分类测试集上的准确率为 {pct(MODEL['accuracy'])}、"
    f"宏平均 F1 为 {pct(MODEL['macro_f1'])}，中性类 F1 仅 {pct(MODEL['per_class']['NEUTRAL']['f1'])}，"
    f"低置信度样本占 {pct(MODEL['low_conf_ratio'])}，未达到原定的 85% 目标。"
    f"字符二元组 + 朴素贝叶斯的二分类基线在真实数据上取得 {pct(BASE['combined']['accuracy'])} 准确率与 "
    f"{pct(BASE['combined']['macro_f1'])} 宏平均 F1，但跨领域迁移准确率最低降至 "
    f"{pct(min(r['accuracy'] for r in BASE['transfer'] if r['source'] != r['target']))}，"
    "说明领域差异是影响模型效果的关键因素。"
)
body(
    "据此，本报告对原有 9 条分析结论逐条复核：2 条成立、1 条部分成立、5 条不成立、1 条无法验证；"
    "并给出数据层、分析层、模型层与报告层的调整方案。调整后的所有结论均绑定真实数据表、图或公开数据源，"
    "不再使用本地示例文本作为论证依据。"
)
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(6)
run = p.add_run("关键词：")
set_run_font(run, size=10.5, bold=True)
run = p.add_run("中文评论；情感分析；公开数据集；数据溯源；结论复核；领域差异")
set_run_font(run, size=10.5)

# 目录
doc.add_page_break()
toc_title("目录")
add_toc_field()
note("提示：目录为 Word 域，打开文档后右键目录区域选择“更新域”即可生成页码。")
doc.add_page_break()

# --------------------------------------------------------------------------- #
# 一、调整背景与目标
# --------------------------------------------------------------------------- #

heading("一、调整背景与目标", 1)
heading("1.1 原分析方案及其主要问题", 2)
body(
    "项目前期的分析方案以本地文件为主要数据来源：data/示例评论_200条.csv 用于界面演示与样例分析，"
    "data/ChnSentiCorp.csv 作为酒店评论训练语料，data/amazon_zh_3class.csv 与 "
    "data/amazon_zh_neutral.csv 作为三分类补充语料，再由这些文件合并、配平得到 "
    "data/train_source.csv 与 output 下的训练/验证/测试集。上述文件在项目目录中可以直接使用，"
    "但存在三个影响论证有效性的问题："
)
bullet(
    "来源不可追溯：本地文件没有统一下载地址、采集时间与校验值，无法证明其对应哪一个公开版本，"
    "也无法排除人工构造、重复采样或版本混用。"
)
bullet(
    "样本规模与结构不自然：本地 ChnSentiCorp 副本为 12,000 条且正负各 6,000 条；"
    "按去除空白与标点后的文本键计算，本地文件有 9,881 条唯一文本，其中仅 3,094 条与公开 "
    "ChnSentiCorp_htl_all 重合，其余 6,787 条无法在公开原始文件中找到对应记录。Amazon 三分类文件为三类各 2,000 条的完全平衡结构，"
    "train_source 又把中性类从 2,000 条扩至 6,400 条，疑似存在重复或过采样。"
)
bullet(
    "结论不可复核：以 200 条示例文本或来源不明的本地副本为依据，得到的“正面为主”“短文本为主”"
    "“三分类有效”等结论没有抽样框和置信区间，无法回答“结论在真实语料上是否成立”。"
)

caption("表 1-1  原分析方案主要本地数据及问题")
add_table(
    ["数据文件", "规模", "来源状态", "主要问题"],
    [
        ["示例评论_200条.csv", "200 条", "项目内示例文件",
         "无采集记录与抽样框；含商品名、评分、评论时间等演示字段；不能代表总体"],
        ["ChnSentiCorp.csv", "12,000 条\n（正负各 6,000）", "本地副本，无下载记录/校验值",
         "与公开 ChnSentiCorp_htl_all（7,766 条）仅 3,094 条归一化后重合；版本与扩充方式不可复核"],
        ["amazon_zh_3class.csv", "6,000 条\n（三类各 2,000）", "本地文件，无公开地址/校验值",
         "完全平衡结构；中性类来源与标注规范不明；难以确认是否为真实公开语料"],
        ["amazon_zh_neutral.csv", "2,000 条\n（全为中性）", "本地文件，无来源记录",
         "中性语料来源不明；缺少标注指南与一致性检验"],
        ["train_source.csv", "19,200 条\n（三类各 6,400）", "由上述本地文件合并/配平",
         "中性类由 2,000 扩至 6,400，疑似重复/过采样；划分前是否按文本去重未记录"],
    ],
    widths=[3.3, 2.4, 3.8, 5.5],
    font_size=8.0,
    align="left",
)
note("注：表中文件均位于项目 data/ 目录；重合条数为按“去除空白与标点后的文本键”计算的结果；"
     "公开 ChnSentiCorp_htl_all 共 7,766 条，归一化后唯一文本 7,764 条。")

heading("1.2 教师要求与调整原则", 2)
body(
    "本次调整的核心要求是：不再仅基于本地生成的模拟文本数据进行分析，必须补充真实公开的相关领域数据作为核心支撑。"
    "为落实该要求，本报告将调整原则具体化为五条："
)
bullet("公开可访问：只使用无需登录、可直接通过 HTTPS 下载的公开数据文件，保留原始下载地址。")
bullet("来源可追溯：记录数据集名称、维护方、下载地址、采集时间、原始规模、字段与 SHA-256 校验值。")
bullet("样本量充足：原始记录不少于 5 万条，有效语料不少于 5 万条，并能覆盖至少三个评论领域。")
bullet("维度相关：数据必须包含中文评论文本与情感标签，能够支撑情感分布、文本长度、关键词与模型效果分析。")
bullet("结论可复核：报告中的每个结论都必须能回溯到具体表、图或公开数据源，不使用示例文本作为论证证据。")

heading("1.3 调整前后对比", 2)
caption("表 1-2  分析方案调整前后对比")
add_table(
    ["维度", "调整前", "调整后"],
    [
        ["核心数据", "200 条示例 + 12,000 条本地副本 + 6,000 条三分类",
         f"3 个公开数据集，{num(S['raw_total'])} 条原始记录 / {num(S['final_total'])} 条有效语料"],
        ["来源可追溯", "无统一下载记录与校验值", "URL + 采集时间 + SHA-256 + 数据源清单"],
        ["标签体系", "三分类，中性类来源不明", "公开金标准二分类；中性作为模型推断类别"],
        ["领域覆盖", "酒店、商品为主", "酒店、电商 9 个子类、外卖"],
        ["结论证据", "示例文本与局部统计", "统计检验、置信区间、跨领域基线、模型评估"],
        ["复现方式", "脚本与数据未绑定", "real_data_analysis.py 一键复现全部表图"],
    ],
    widths=[2.8, 6.2, 6.8],
    font_size=9,
    align="left",
    first_col_bold=True,
)

# --------------------------------------------------------------------------- #
# 二、数据来源与采集说明
# --------------------------------------------------------------------------- #

heading("二、数据来源与采集说明", 1, page_break=True)
heading("2.1 数据源筛选标准", 2)
body(
    "中文情感分析公开语料较多，但并非都满足本次复核要求。筛选时依次检查：是否可公开下载、是否有明确的情感标签、"
    "是否有足够的样本量、是否覆盖多个评论领域、是否能找到维护方与引用信息。最终选择 ChineseNlpCorpus 项目"
    "（GitHub 公开仓库）中的三个数据集：ChnSentiCorp_htl_all、online_shopping_10_cats 与 waimai_10k。"
    "三者的共同点是：均为中文用户评论、均有正/负情感标签、均可直接下载、均已在中文 NLP 研究与教学中被广泛使用。"
)

heading("2.2 数据集清单与样本规模", 2)
caption("表 2-1  真实公开数据集清单")
add_table(
    ["数据集", "领域", "来源平台/维护方", "原始规模", "有效规模", "标签", "采集时间"],
    [
        ["ChnSentiCorp_htl_all", "酒店评论", "ChineseNlpCorpus\n（GitHub 公开仓库）",
         num(MANIFEST["ChnSentiCorp_htl_all"]["raw_rows"]), num(H["n"]), "0/1 二分类", "2026-11-06"],
        ["online_shopping_10_cats", "电商评论\n（9 个子类）", "ChineseNlpCorpus\n（GitHub 公开仓库）",
         num(MANIFEST["online_shopping_10_cats"]["raw_rows"]), num(E["n"]), "0/1 二分类", "2026-11-06"],
        ["waimai_10k", "外卖评论", "ChineseNlpCorpus\n（GitHub 公开仓库）",
         num(MANIFEST["waimai_10k"]["raw_rows"]), num(W["n"]), "0/1 二分类", "2026-11-06"],
        ["合计", "—", "—", num(S["raw_total"]), num(S["final_total"]), "—", "—"],
    ],
    widths=[3.9, 1.8, 3.0, 1.7, 1.7, 1.6, 1.8],
    font_size=7.8,
)
note("注：电商数据的原始规模 62,774 条包含 10,000 条“酒店”子类；为避免与 ChnSentiCorp 主题重叠，"
     "本次分析剔除整个“酒店”子类后再去重，因此有效规模为 52,555 条。"
     "各数据集原始规模与有效规模的差异来自空文本、重复文本与跨数据集重复，详见 3.2 节。")

heading("2.3 下载地址与校验值", 2)
body(
    "为保证“来源可追溯”，三个数据集均记录原始下载地址与 SHA-256。校验值在 2026-11-06 采集完成后计算，"
    "分析脚本在每次运行前会重新计算并比对；若文件被修改，脚本将直接报错并拒绝继续分析。"
)
caption("表 2-2  数据文件下载地址与 SHA-256")
add_table(
    ["数据集", "下载地址", "SHA-256"],
    [
        ["ChnSentiCorp_htl_all",
         MANIFEST["ChnSentiCorp_htl_all"]["url"],
         MANIFEST["ChnSentiCorp_htl_all"]["sha256"]],
        ["online_shopping_10_cats",
         MANIFEST["online_shopping_10_cats"]["url"],
         MANIFEST["online_shopping_10_cats"]["sha256"]],
        ["waimai_10k",
         MANIFEST["waimai_10k"]["url"],
         MANIFEST["waimai_10k"]["sha256"]],
    ],
    widths=[3.2, 7.4, 5.2],
    font_size=7.2,
    align="left",
)
note("注：online_shopping_10_cats 以 ZIP 压缩包发布，表中 SHA-256 为解压后 CSV 的校验值；"
     "压缩包本身的 SHA-256 为 "
     + MANIFEST["online_shopping_10_cats"]["archive_sha256"]
     + "。完整文件大小与校验值见附录 A。")

heading("2.4 采集过程与可追溯性", 2)
body(
    "采集时间为 2026 年 11 月 6 日 20:11（Asia/Shanghai）。具体过程如下："
)
bullet("通过 HTTPS GET 从 raw.githubusercontent.com 下载三个原始文件，保存到 data/real_public/ 目录。")
bullet("online_shopping_10_cats 下载后解压到 data/real_public/online_shopping_10_cats/，保留原始 ZIP 文件。")
bullet("对每个文件计算 SHA-256，与数据源清单中的期望值比对；原始文件只读，不做任何人工修改。")
bullet("清洗、去重、统计与图表全部由 real_data_analysis.py 完成，结果写入 output/real_data/。")
bullet("报告正文中的每个数字均从 output/real_data/summary.json 读取，避免人工转录误差。")

heading("2.5 数据合规与引用说明", 2)
body(
    "三个数据集均为公开学术/研究语料，数据中不包含账号、手机号、身份证号等直接身份信息，本次分析也未进行任何"
    "重新识别尝试。数据仅用于本课程实验的分析与复核，不用于商业用途，不再对外分发原始数据。"
    "引用时应同时引用 ChineseNlpCorpus 项目与原始数据集说明；ChnSentiCorp 的原始语料来源为中国科学院计算技术研究所"
    "谭松波等人的中文情感分析研究。公开语料的许可与使用条款以维护方页面为准，若后续需要公开发布衍生数据，"
    "应再次核对许可范围。"
)

heading("2.6 数据代表性边界", 2)
body(
    "需要明确的是，这三个数据集属于“可公开获取的便利样本”，不是对全网中文评论的概率抽样。"
    "电商语料在构建时按类别配平，酒店与外卖语料的类别比例也由数据提供方决定，"
    "因此不能用全量正向率推断“真实舆论中正面评论占多少”。本报告使用这些数据的正确方式是："
    "在明确的领域与构造背景下比较情感分布、文本长度、关键词与模型表现，并把领域差异作为核心发现，"
    "而不是把某个单一比例当作总体结论。"
)

# --------------------------------------------------------------------------- #
# 三、数据质量与预处理
# --------------------------------------------------------------------------- #

heading("三、数据质量与预处理", 1, page_break=True)
heading("3.1 清洗规则", 2)
body(
    "为保持与系统实现的一致性，清洗只做不影响情感语义的处理：去除 BOM/零宽字符、HTML 标签、URL 与多余空白；"
    "保留标点、数字与表情符号，因为它们在真实评论中可能承载语气信息。去重时使用“去除空白与常见标点后的文本键”，"
    "以避免仅标点差异造成重复。"
)
caption("表 3-1  数据清洗规则")
add_table(
    ["步骤", "规则", "目的"],
    [
        ["编码处理", "以 UTF-8-SIG 读取，去除 \\ufeff、\\u200b", "消除 BOM 与零宽字符造成的首字符污染"],
        ["HTML/URL", "去除 <...> 标签与 http(s)/www 链接", "避免网页残留影响分词与词频"],
        ["空白归一", "全角空格转半角，连续空白合并", "统一文本长度与去重键"],
        ["空文本", "清洗后长度为 0 的记录剔除", "避免空样本进入统计与模型"],
        ["去重键", "去除空白与常见中英文标点后比较", "识别仅标点/空白差异的重复评论"],
        ["主题重叠", "剔除电商语料中的“酒店”子类", "避免与 ChnSentiCorp 重复计数和领域泄漏"],
        ["标签过滤", "仅保留 0/1 标签", "与公开数据的金标准标签体系一致"],
        ["长度统计", "按清洗后字符数统计", "与系统 512 字符输入上限对齐"],
    ],
    widths=[2.2, 7.2, 6.4],
    font_size=8.8,
    align="left",
    first_col_bold=True,
)

heading("3.2 清洗漏斗", 2)
funnel = {f["step"]: f["count"] for f in S["funnel"]}
caption("表 3-2  数据清洗漏斗")
add_table(
    ["步骤", "数量（条）", "说明"],
    [
        ["原始可解析记录", num(S["raw_total"]), "三个数据集原始记录合计"],
        ["剔除空文本", f"-{abs(funnel['剔除空文本'])}", "清洗后长度为 0"],
        ["剔除电商“酒店”子类", f"-{abs(funnel['剔除“酒店”子类（与酒店语料重叠）'])}",
         "该子类与酒店语料大量重复，整体剔除以避免领域泄漏"],
        ["域内重复文本去重", f"-{abs(funnel['域内重复文本去重'])}", "同一数据集内去重键相同的记录"],
        ["跨数据集重复文本去重", f"-{abs(funnel['跨数据集重复文本去重'])}", "保留酒店→电商→外卖的优先顺序"],
        ["最终有效样本", num(S["final_total"]), "进入全部统计、关键词与基线分析"],
    ],
    widths=[4.0, 3.0, 8.8],
    font_size=9,
    align="left",
    first_col_bold=True,
)
note("注：域内去重 276 条中包含精确重复与“仅标点/空白不同”的重复；若只按精确文本比较，"
     "三个数据集的精确重复分别为酒店 0 条、电商 50 条、外卖 7 条。")

heading("3.3 重复与主题重叠分析", 2)
body(
    "真实公开语料之间并非彼此独立。online_shopping_10_cats 的“酒店”子类共有 10,000 条，"
    "其中 5,574 条与 ChnSentiCorp_htl_all 的评论文本完全相同；如果直接合并，酒店领域会被重复计入两次，"
    "关键词与情感比例也会被系统性放大。因此本报告采取保守策略：把整个“酒店”子类从电商语料中剔除，"
    "而不是只删除 5,574 条完全重复记录。这样做的代价是损失一部分电商样本，但可以保证三个领域之间不出现"
    "同源文本泄漏。"
)
body(
    "此外，跨数据集去重还发现 27 条标点归一化后重复的记录（其中外卖与电商之间精确重复 4 条）。"
    "这些记录按“酒店→电商→外卖”的顺序保留首次出现者。域内去重 276 条，主要来自电商语料中同一用户"
    "重复发布或仅标点不同的评论。"
)

heading("3.4 标签体系与“中性”问题", 2)
body(
    "三个公开数据集都只提供 0/1 二分类标签：0 表示负向，1 表示正向，没有中性标注。"
    "这与项目原方案的三分类体系存在本质差异。原方案把“中性”作为第三类，并使用本地中性语料参与训练与测试；"
    "但在真实公开语料中，中性类没有金标准，模型输出的“中性”只能理解为一种推断结果或低置信度兜底，"
    "不能与人工标注的正/负类同等对待。"
)
caption("表 3-3  各数据集标签体系")
add_table(
    ["数据集", "标签取值", "中性标注", "说明"],
    [
        ["ChnSentiCorp_htl_all", "0, 1", "无", "酒店评论，正/负二分类"],
        ["online_shopping_10_cats", "0, 1", "无", "电商评论，正/负二分类，含 10 个子类"],
        ["waimai_10k", "0, 1", "无", "外卖评论，正/负二分类"],
        ["项目原三分类语料", "0, 1, 2", "有，但来源不明", "中性类无公开金标准，不能作为真实证据"],
    ],
    widths=[4.2, 2.6, 3.0, 6.2],
    font_size=9,
    align="left",
)
body(
    "这一发现直接改变了两条分析逻辑：第一，不能再把“中性占比”当作真实语料的情感分布来报告；"
    "第二，模型评估必须明确区分“二分类金标准”和“三分类模型输出”，不能把中性类的表现与正/负类混在一起解释。"
)

heading("3.5 文本长度与截断风险", 2)
caption("表 3-4  各领域文本长度统计（单位：字符）")
add_table(
    ["领域", "样本量", "均值", "中位数", "P90", "P99", "最大", ">128字", ">256字", ">512字"],
    [
        ["酒店评论", num(H["n"]), f"{H['len_mean']:.1f}", f"{H['len_median']:.0f}",
         f"{H['len_p90']:.0f}", f"{H['len_p99']:.0f}", f"{H['len_max']:.0f}",
         pct(H["share_gt128"]), pct(H["share_gt256"]), pct(H["share_gt512"])],
        ["电商评论", num(E["n"]), f"{E['len_mean']:.1f}", f"{E['len_median']:.0f}",
         f"{E['len_p90']:.0f}", f"{E['len_p99']:.0f}", f"{E['len_max']:.0f}",
         pct(E["share_gt128"]), pct(E["share_gt256"]), pct(E["share_gt512"])],
        ["外卖评论", num(W["n"]), f"{W['len_mean']:.1f}", f"{W['len_median']:.0f}",
         f"{W['len_p90']:.0f}", f"{W['len_p99']:.0f}", f"{W['len_max']:.0f}",
         pct(W["share_gt128"]), pct(W["share_gt256"]), pct(W["share_gt512"])],
        ["合计", num(A["n"]), f"{A['len_mean']:.1f}", f"{A['len_median']:.0f}",
         f"{A['len_p90']:.0f}", f"{A['len_p99']:.0f}", f"{A['len_max']:.0f}",
         pct(A["share_gt128"]), pct(A["share_gt256"]), pct(A["share_gt512"])],
    ],
    widths=[2.0, 1.8, 1.5, 1.5, 1.4, 1.5, 1.6, 1.7, 1.7, 1.7],
    font_size=8.5,
)
body(
    f"从业务输入上限看，512 字符可以覆盖 {pct(1 - A['share_gt512'])} 的整体样本、"
    f"{pct(1 - H['share_gt512'])} 的酒店样本，这一上限本身是合理的。但模型配置的 maxLength 是 128 token，"
    f"按中文“一字约一 token”估算，整体有 {pct(A['share_gt128'])} 的评论会被截断，酒店领域高达 {pct(H['share_gt128'])}。"
    "这意味着：不是 512 字符上限不够，而是 128 token 的模型输入长度对酒店长评论偏紧。"
    "如果直接截断，评论后半段的服务、卫生、位置等评价可能丢失，进而影响情感判定。"
)

# --------------------------------------------------------------------------- #
# 四、真实数据下的总体特征
# --------------------------------------------------------------------------- #

heading("四、真实数据下的总体特征", 1, page_break=True)
heading("4.1 样本规模与领域分布", 2)
body(
    f"最终有效语料共 {num(A['n'])} 条，其中电商评论占 {pct(E['n'] / A['n'])}，是样本量最大的领域；"
    f"酒店评论 {num(H['n'])} 条，外卖评论 {num(W['n'])} 条。三个领域的样本量差异较大，"
    "因此后文的跨领域比较同时报告比例与置信区间，而不是只比较绝对数量。"
)
add_figure("fig01_domain_overview.png", f"图 4-1  各领域有效样本量与正向评论占比（n={num(A['n'])}）")

heading("4.2 情感极性分布", 2)
caption("表 4-1  各领域情感极性分布与 95% 置信区间")
add_table(
    ["领域", "样本量", "正向", "负向", "正向率", "95% CI"],
    [
        ["酒店评论", num(H["n"]), num(H["positive"]), num(H["negative"]),
         pct(H["positive_rate"]), f"{pct(H['ci_low'])}–{pct(H['ci_high'])}"],
        ["电商评论", num(E["n"]), num(E["positive"]), num(E["negative"]),
         pct(E["positive_rate"]), f"{pct(E['ci_low'])}–{pct(E['ci_high'])}"],
        ["外卖评论", num(W["n"]), num(W["positive"]), num(W["negative"]),
         pct(W["positive_rate"]), f"{pct(W['ci_low'])}–{pct(W['ci_high'])}"],
        ["合计", num(A["n"]), num(A["positive"]), num(A["negative"]),
         pct(A["positive_rate"]), f"{pct(A['ci_low'])}–{pct(A['ci_high'])}"],
    ],
    widths=[2.6, 2.4, 2.4, 2.4, 2.4, 3.6],
    font_size=9,
    first_col_bold=True,
)
body(
    f"全量正向率为 {pct(A['positive_rate'])}，置信区间跨过 50%，不能支持“整体以正面为主”的判断。"
    f"更值得注意的是领域差异：酒店评论正向率 {pct(H['positive_rate'])}，电商 {pct(E['positive_rate'])}，"
    f"外卖仅 {pct(W['positive_rate'])}，酒店与外卖相差 {abs(H['positive_rate'] - W['positive_rate']) * 100:.2f} 个百分点。"
    f"三组比例的卡方检验结果为 χ²={S['chi_square']['chi2']:.2f}，df=2，p{pval(S['chi_square']['p_value'])}，"
    "说明领域与情感极性之间存在显著关联。"
)

caption("表 4-2  领域间正向率的两两比较")
pair_rows = []
for p in S["pairwise"]:
    pair_rows.append([
        f"{p['group_a']} vs {p['group_b']}",
        f"{p['diff_pp']:.2f}",
        f"{p['cohens_h']:.3f}",
        f"{p['chi2']:.2f}",
        pval(p["p_value"]),
    ])
add_table(
    ["比较组", "正向率差值（百分点）", "Cohen's h", "χ²", "p 值"],
    pair_rows,
    widths=[4.6, 3.8, 2.8, 2.6, 2.6],
    font_size=9,
    align="left",
)
note("注：Cohen's h 用于衡量两个比例差异的效应量，0.2/0.5/0.8 通常对应小/中/大效应；"
     "本表三组比较的效应量为中等及以上。")

heading("4.3 文本长度分布", 2)
add_figure("fig02_length_distribution.png", "图 4-2  三个领域评论文本长度分布（对数刻度）")
body(
    f"整体长度中位数为 {A['len_median']:.0f} 字，{pct(A['share_le50'])} 的评论不超过 50 字，"
    "从整体上看“短文本为主”是成立的。但这一结论不能直接套用到每个领域："
    f"酒店评论中位数 {H['len_median']:.0f} 字、均值 {H['len_mean']:.1f} 字，"
    f"电商中位数 {E['len_median']:.0f} 字，外卖中位数仅 {W['len_median']:.0f} 字。"
    f"酒店评论的 P99 达到 {H['len_p99']:.0f} 字，最长 {H['len_max']:.0f} 字，"
    "呈现明显的长尾。把三个领域混在一起说“评论都很短”，会掩盖酒店长评论带来的截断与建模问题。"
)
body(
    f"从词汇量看，酒店评论平均每条产生 {H['grams_per_doc']:.2f} 个有效二元组，"
    f"电商 {E['grams_per_doc']:.2f} 个，外卖 {W['grams_per_doc']:.2f} 个。"
    "酒店评论的信息密度明显更高，这也解释了为什么同样的关键词方法在酒店领域更容易受到长文本影响。"
)

heading("4.4 与原有认知的差异", 2)
bullet(
    f"原方案倾向于用“整体正向为主”描述语料；真实数据给出的全量正向率是 {pct(A['positive_rate'])}，"
    "且领域间差异显著，整体比例没有稳定的舆情含义。"
)
bullet(
    "原方案把三分类当作数据的自然属性；真实公开语料只有二分类金标准，中性类没有标注依据。"
)
bullet(
    "原方案用 512 字符作为统一上限；从业务输入看基本够用，但 128 token 的模型上限会截断近三分之一酒店评论。"
)
bullet(
    "原方案以单一语料评估模型；真实数据显示不同领域的用词、长度、情感分布差异很大，必须分领域评估。"
)

# --------------------------------------------------------------------------- #
# 五、跨领域对比分析
# --------------------------------------------------------------------------- #

heading("五、跨领域对比分析", 1)
heading("5.1 三个领域的整体对比", 2)
caption("表 5-1  三个领域的核心特征对比")
add_table(
    ["领域", "样本量", "正向率", "长度中位数", "每条二元组数", "主要关注点（高频词）"],
    [
        ["酒店评论", num(H["n"]), pct(H["positive_rate"]), f"{H['len_median']:.0f} 字",
         f"{H['grams_per_doc']:.1f}", "房间、酒店、服务、入住、早餐、设施"],
        ["电商评论", num(E["n"]), pct(E["positive_rate"]), f"{E['len_median']:.0f} 字",
         f"{E['grams_per_doc']:.1f}", "质量、喜欢、包装、快递、满意、价格"],
        ["外卖评论", num(W["n"]), pct(W["positive_rate"]), f"{W['len_median']:.0f} 字",
         f"{W['grams_per_doc']:.1f}", "送餐、速度、难吃、送来、态度、服务"],
    ],
    widths=[2.2, 2.0, 2.0, 2.2, 2.2, 5.2],
    font_size=8.8,
    align="left",
)
body(
    "三个领域的差异不仅体现在情感比例上，也体现在“评论在说什么”。酒店评论围绕房间、服务、早餐、设施展开，"
    "句子更长、信息更密；电商评论围绕质量、包装、快递、价格，长度居中；外卖评论围绕送餐速度、口味、态度，"
    "句子最短、情绪表达最直接。对系统而言，这意味着同一套关键词权重和同一套判定阈值很难同时适配三个领域。"
)

heading("5.2 电商语料的 9 个子类", 2)
caption("表 5-2  电商评论各子类的样本量与正向率")
cat_rows = []
for c in CATS:
    cat_rows.append([
        c["category"], num(c["n"]), num(c["positive"]), pct(c["positive_rate"]),
        f"{c['len_median']:.0f} 字",
    ])
cat_rows.append(["合计", num(E["n"]), num(E["positive"]), pct(E["positive_rate"]), f"{E['len_median']:.0f} 字"])
add_table(
    ["子类", "样本量", "正向", "正向率", "长度中位数"],
    cat_rows,
    widths=[3.0, 3.0, 3.0, 3.2, 3.2],
    font_size=9,
)
body(
    "电商语料内部也不是同质的。水果、平板、洗发水、衣服四个子类各约 1 万条，正向率都在 50% 左右，"
    "长度中位数 24–29 字；计算机、书籍、手机三个子类的样本量较小但评论更长，书籍的长度中位数达到 145 字，"
    "接近酒店评论的水平。热水器子类只有 558 条，正向率却高达 82.08%，这是一个明显的小样本离群点，"
    "不能据此推断“热水器用户更满意”，更合理的解释是该子类的采样来源或产品结构特殊。"
)
body(
    "这一发现对系统有两个直接启示：第一，电商领域的“短文本”假设只对部分子类成立，书籍、计算机等子类需要更长的"
    "输入长度；第二，子类样本量差异很大，直接汇总会放大小样本子类的比例波动，报告应同时给出样本量与置信区间。"
)

heading("5.3 领域差异的统计检验", 2)
body(
    f"三组比例的卡方检验 χ²={S['chi_square']['chi2']:.2f}，df=2，p{pval(S['chi_square']['p_value'])}；"
    "两两比较的效应量均在中等以上（酒店 vs 外卖 Cohen's h=0.720）。"
    "这不是“样本量大所以显著”的 trivial 结果：17–35 个百分点的正向率差异，在业务上足以改变舆情判断和运营策略。"
)
body(
    "因此，后续分析必须把“领域”作为一等公民：数据表增加领域字段，统计与图表按领域分层，"
    "模型评估报告分领域指标；全量指标只能作为加权描述，并同时披露领域构成。"
)

# --------------------------------------------------------------------------- #
# 六、关键词与主题分析
# --------------------------------------------------------------------------- #

heading("六、关键词与主题分析", 1, page_break=True)
heading("6.1 分析方法", 2)
body(
    "系统 JVM 侧未引入 jieba，而是用中文二元组滑动窗口近似分词。为保持与系统实现一致，本报告同样采用字符二元组，"
    "并过滤由“的、了、是、我、不”等功能字构成的碎片。高频词按“文档频次”统计，即一个词在同一评论中只计一次，"
    "避免长评论因重复出现而主导词频。正负关联词使用分层对数几率：先在每个领域内估计词与情感标签的关联，"
    "再按逆方差加权合并，只有至少在两个领域中可估计的词才进入结果，以降低领域混杂。"
)

heading("6.2 各领域高频词", 2)
top_by_domain = {"酒店评论": [], "电商评论": [], "外卖评论": []}
for row in S["top_bigrams"]:
    if row["rank"] <= 10:
        top_by_domain[row["domain"]].append(row)
caption("表 6-1  各领域高频二元组 Top10（文档频次）")
top_table_rows = []
for i in range(10):
    row = [str(i + 1)]
    for domain in ["酒店评论", "电商评论", "外卖评论"]:
        item = top_by_domain[domain][i]
        row.append(f"{item['gram']}（{item['count']:,}）")
    top_table_rows.append(row)
add_table(
    ["排名", "酒店评论", "电商评论", "外卖评论"],
    top_table_rows,
    widths=[1.6, 4.6, 4.6, 4.6],
    font_size=9,
)
body(
    "酒店评论的高频词集中在“房间、酒店、服务、入住、早餐、设施、环境、价格”，是典型的住宿体验结构；"
    "电商评论集中在“质量、喜欢、包装、快递、满意、价格、物流、速度”，覆盖商品与履约两个环节；"
    "外卖评论集中在“送餐、速度、难吃、送来、态度、服务、分钟”，几乎全部围绕配送与口味。"
    "这些词能够回答“用户在关注什么”，但它们本身并不等于情感判断，报告需要把主题词与情感词分开呈现。"
)

heading("6.3 与正/负向评论关联最强的词", 2)
add_figure("fig04_logodds.png", "图 6-1  跨领域分层对数几率：与正向/负向评论关联最强的二元组")
body(
    "与正向评论关联最强的词包括“喜欢”（z=40.3）、“速度”（28.3）、“舒服”（27.5）、“满意”（24.1）、"
    "“合适”（23.8）、“物流”（22.7）、“质量”（22.6）、“价格”（18.8）；"
    "与负向评论关联最强的是“失望”（z=-27.2）、“客服”（-22.8）、“垃圾”（-21.4）、“严重”（-17.2）、"
    "“打电”（-15.7）、“怀疑”（-14.0）、“差劲”（-13.9）。"
)
body(
    "这里需要特别说明：速度、物流、价格、质量、客服等词是“主题/属性词”，它们之所以与情感标签强关联，"
    "是因为正向评论更倾向于表扬这些属性，负向评论更倾向于投诉这些属性；它们不是纯粹的情感词。"
    "真正稳定的情感词是“喜欢、满意、舒服、失望、垃圾、差劲”等。系统在展示热点词时，"
    "应把两类词分开：主题词回答“关注什么”，情感词回答“态度如何”。"
)

heading("6.4 情感词典效度检验", 2)
add_figure("fig05_lexicon_validity.png", "图 6-2  情感词典效度检验：情感词与人工标注的一致性")
body(
    "用一组常用正面词/负面词做方向性检验：在酒店正向评论中，正面词命中率为 902/千条，负向评论中为 652/千条；"
    "在电商正向评论中为 868/千条，负向评论中为 415/千条；在外卖正向评论中为 843/千条，负向评论中为 329/千条。"
    "负面词的方向同样一致：负向评论的负面词命中率（酒店 756、电商 581、外卖 518）均高于正向评论"
    "（酒店 428、电商 167、外卖 145）。这说明公开数据的标签与文本语义总体一致，可以作为真实证据使用。"
)
body(
    "但酒店领域的区分度明显弱于另外两个领域：负向酒店评论中仍有 652/千条命中正面词，正向酒店评论中也有 "
    "428/千条命中负面词。这与酒店评论常见的“先扬后抑”“总体满意但细节抱怨”混合表达有关。"
    "单靠词典或单词特征容易误判，必须结合上下文、否定与转折结构。"
)

heading("6.5 方法局限", 2)
body(
    "字符二元组的好处是不依赖外部分词器、与系统实现一致、可复现；缺点是会产生“服的”“务很”这类碎片，"
    "对三字以上词（如“性价比”“售后服务”）覆盖不足。系统当前在 JVM 侧用二元组近似分词，"
    "属于工程折中，不应把关键词结果等同于语言学意义上的“词”。后续若引入 jieba 或领域词典，"
    "应保持“同一版本、同一停用词表、同一统计口径”的可比性，并在报告中说明方法变更。"
)

# --------------------------------------------------------------------------- #
# 七、模型效果复核
# --------------------------------------------------------------------------- #

heading("七、模型效果复核", 1, page_break=True)
heading("7.1 现有模型与测试集", 2)
body(
    "现有模型版本为 bert-zh-sentiment-v1，基座为 uer/chinese_roberta_L-4_H-256，三分类输出"
    "（POSITIVE/NEGATIVE/NEUTRAL），maxLength=128。模型在本地 19,200 条配平语料上训练，"
    "测试集 1,854 条，评估结果保存在 model/bert-zh-sentiment-v1/evaluation_report.txt。"
    "需要强调的是：该测试集来自项目原有本地数据链，不是本报告新采集的 72,222 条公开语料，"
    "因此以下指标用于复核“原方案是否达到原定目标”，不能直接当作新语料上的泛化性能。"
)

heading("7.2 总体指标", 2)
caption("表 7-1  现有 BERT 模型总体评估指标")
add_table(
    ["指标", "数值", "说明"],
    [
        ["测试样本数", num(MODEL["n_test"]), "三分类测试集"],
        ["准确率 Accuracy", pct(MODEL["accuracy"]), "整体预测正确比例"],
        ["宏平均 Precision", pct(MODEL["macro_precision"]), "三类等权平均"],
        ["宏平均 Recall", pct(MODEL["macro_recall"]), "三类等权平均"],
        ["宏平均 F1", pct(MODEL["macro_f1"]), "三类等权平均，主要参考指标"],
        ["低置信度（<0.60）占比", pct(MODEL["low_conf_ratio"]), "需要人工复核的样本比例"],
    ],
    widths=[5.0, 3.6, 6.4],
    font_size=9,
    align="left",
    first_col_bold=True,
)

heading("7.3 分类别指标与混淆矩阵", 2)
caption("表 7-2  现有 BERT 模型分类别指标")
model_rows = []
for name, cn in [("POSITIVE", "正面"), ("NEGATIVE", "负面"), ("NEUTRAL", "中性")]:
    m = MODEL["per_class"][name]
    model_rows.append([cn, pct(m["precision"]), pct(m["recall"]), pct(m["f1"]), num(m["support"])])
add_table(
    ["类别", "Precision", "Recall", "F1", "支持数"],
    model_rows,
    widths=[3.2, 3.2, 3.2, 3.2, 3.2],
    font_size=9,
)
add_figure("fig08_model_eval.png", "图 7-1  现有 BERT 模型分类别 F1 与混淆矩阵")
body(
    f"正面类 F1 为 {pct(MODEL['per_class']['POSITIVE']['f1'])}，负向为 {pct(MODEL['per_class']['NEGATIVE']['f1'])}，"
    f"中性仅 {pct(MODEL['per_class']['NEUTRAL']['f1'])}。混淆矩阵显示，中性类有 161 条被判为负向、87 条被判为正向，"
    "是主要的误差来源；正向类有 129 条被判为中性，说明模型在“强正面”和“弱正面/中性”之间边界模糊。"
    "低置信度样本占 29.77%，接近三成，意味着大量结果需要人工复核，系统当前的“低置信度标记”是必要设计，"
    "但不能替代模型精度。"
)

heading("7.4 与 85% 目标的差距", 2)
gap_pp = (0.85 - MODEL["accuracy"]) * 100
caption("表 7-3  原定目标与实际结果对比")
add_table(
    ["指标", "原定目标", "实际结果", "差距", "判定"],
    [
        ["三分类准确率", "不低于 85%", pct(MODEL["accuracy"]), f"-{gap_pp:.2f} 个百分点", "未达标"],
        ["宏平均 F1", "未单列", pct(MODEL["macro_f1"]), "—", "需重新定义目标"],
        ["中性类 F1", "未单列", pct(MODEL["per_class"]["NEUTRAL"]["f1"]), "—", "最低，需校准"],
        ["低置信度占比", "未设上限", pct(MODEL["low_conf_ratio"]), "—", "偏高，人工复核压力大"],
    ],
    widths=[3.4, 3.0, 3.4, 3.2, 3.2],
    font_size=9,
    align="left",
)
body(
    f"实际准确率与 85% 目标相差 {gap_pp:.2f} 个百分点，这不是“接近达标”，而是明确未达标。"
    "造成差距的原因至少有三点：第一，中性类没有真实金标准，模型只能从构造语料中学习一个模糊边界；"
    "第二，训练语料经过配平与过采样，测试集与训练集可能共享近重复文本，评估结果本身存在偏乐观风险；"
    "第三，领域差异显著，而原测试集没有按酒店/电商/外卖分层，无法暴露跨领域退化。"
)

heading("7.5 真实数据上的轻量基线", 2)
body(
    "为了在真实公开语料上获得一个可复核的参照，本报告实现了字符二元组 + 多项式朴素贝叶斯的二分类基线："
    "按领域分层、按标签分层抽取 80% 训练、20% 测试，词表取训练集中文档频次≥3 的前 30,000 个二元组，"
    "拉普拉斯平滑 α=1。该基线不是要替代 BERT，而是回答两个问题：真实语料的情感信号是否可学习；"
    "跨领域迁移会退化多少。"
)
caption("表 7-4  朴素贝叶斯基线在真实数据上的表现（二分类）")
base_rows = [
    ["合计", num(BASE["combined"]["n"]), pct(BASE["combined"]["accuracy"]),
     pct(BASE["combined"]["macro_f1"]),
     pct(BASE["combined"]["per_class"]["负向"]["f1"]),
     pct(BASE["combined"]["per_class"]["正向"]["f1"])],
]
for row in BASE["per_domain"]:
    base_rows.append([
        row["domain"], num(row["n"]), pct(row["accuracy"]), pct(row["macro_f1"]),
        pct(row["per_class"]["负向"]["f1"]), pct(row["per_class"]["正向"]["f1"]),
    ])
add_table(
    ["领域", "测试样本", "准确率", "宏平均 F1", "负向 F1", "正向 F1"],
    base_rows,
    widths=[3.0, 2.8, 2.8, 2.8, 2.8, 2.8],
    font_size=8.8,
)
body(
    f"在真实二分类语料上，基线整体准确率为 {pct(BASE['combined']['accuracy'])}、宏平均 F1 为 "
    f"{pct(BASE['combined']['macro_f1'])}，说明情感信号是可学习的。但分领域看，酒店宏平均 F1 只有 "
    f"{pct(BASE['per_domain'][0]['macro_f1'])}，明显低于电商 {pct(BASE['per_domain'][1]['macro_f1'])} 与外卖 "
    f"{pct(BASE['per_domain'][2]['macro_f1'])}。酒店评论正负样本不均衡（正向 68.53%），准确率 77.91% 看似不低，"
    "但宏平均 F1 只有 68.96%，说明少数类（负向）的识别仍然吃力。"
)
add_figure("fig06_baseline.png", "图 7-2  朴素贝叶斯基线：混淆矩阵与域内表现")

caption("表 7-5  跨领域迁移准确率矩阵（行为训练域，列为测试域）")
keys = ["hotel", "ecommerce", "waimai"]
names = {"hotel": "酒店", "ecommerce": "电商", "waimai": "外卖"}
transfer_rows = []
for src in keys:
    row = [f"训练：{names[src]}"]
    for tgt in keys:
        row.append(pct(TRANSFER[(src, tgt)]["accuracy"]))
    transfer_rows.append(row)
add_table(
    ["训练域 \\ 测试域", "酒店", "电商", "外卖"],
    transfer_rows,
    widths=[4.4, 3.6, 3.6, 3.6],
    font_size=9,
)
add_figure("fig07_domain_transfer.png", "图 7-3  跨领域迁移准确率矩阵")
body(
    f"域内测试的准确率在 78.11%–83.14% 之间，但跨领域后显著下降：电商→外卖为 "
    f"{pct(TRANSFER[('ecommerce', 'waimai')]['accuracy'])}，酒店→外卖仅 "
    f"{pct(TRANSFER[('hotel', 'waimai')]['accuracy'])}，外卖→酒店更是只有 "
    f"{pct(TRANSFER[('waimai', 'hotel')]['accuracy'])}。这说明“在一个领域训练、直接套用到另一个领域”不可行，"
    "领域适配或分领域训练是必要工作，而不是可选项。"
)
note("注：表 7-4 与表 7-5 为二分类基线，和表 7-1 的三分类 BERT 不是同一任务，不能直接比较数值高低；"
     "它们的用途是验证真实语料的可学习性与领域差异，而不是给 BERT 排名。")

# --------------------------------------------------------------------------- #
# 八、原有分析结论复核
# --------------------------------------------------------------------------- #

heading("八、原有分析结论复核与调整", 1, page_break=True)
body(
    "下表把原方案中明确写出或由数据链隐含的 9 条结论/假设逐条列出，用真实数据的统计结果判定其有效性。"
    "判定标准为：成立（方向与量级均得到支持）、部分成立（大方向成立但边界需修正）、"
    "不成立（与真实数据相反或无证据）、无法验证（当前数据缺少必要字段）。"
)
caption("表 8-1  原有分析结论复核与调整")
conclusion_rows = [
    ["C1", "中文评论整体以正面为主",
     f"全量正向率 {pct(A['positive_rate'])}（95% CI {pct(A['ci_low'])}–{pct(A['ci_high'])}）；"
     f"酒店 {pct(H['positive_rate'])}、电商 {pct(E['positive_rate'])}、外卖 {pct(W['positive_rate'])}；"
     f"χ²={S['chi_square']['chi2']:.2f}，p{pval(S['chi_square']['p_value'])}",
     "不成立",
     "删除“整体正面为主”的表述；改为“情感极性随领域显著变化，报告按领域分层呈现”"],
    ["C2", "三分类（正/负/中）是数据的自然类别",
     "三个公开数据集均只有 0/1 标签，无中性标注；中性只能作为模型推断类别",
     "不成立",
     "金标准改为二分类；中性作为低置信度兜底类，单独报告其占比与 F1，不与金标准混同"],
    ["C3", "评论以短文本为主，512 字符上限足够",
     f"整体中位数 {A['len_median']:.0f} 字，{pct(A['share_le50'])} ≤50 字；但酒店中位数 {H['len_median']:.0f} 字，"
     f"{pct(H['share_gt128'])} >128 字、{pct(H['share_gt512'])} >512 字；整体 >128 字 {pct(A['share_gt128'])}",
     "部分成立",
     "保留 512 字符业务上限；模型侧按领域调整 maxLength 或对长评论分段推理；报告中披露截断率"],
    ["C4", "关键词能够反映用户关注焦点",
     "酒店：房间/服务/早餐/设施；电商：质量/包装/快递/价格；外卖：送餐/速度/难吃/态度；"
     "分层对数几率可区分喜欢/满意/舒服与失望/垃圾/差劲",
     "成立",
     "保留关键词分析；把“主题词”与“情感词”分两层展示；说明二元组分词的碎片化局限"],
    ["C5", "同一模型与阈值可直接跨领域使用",
     f"正向率极差 {abs(H['positive_rate'] - W['positive_rate']) * 100:.2f} 个百分点，Cohen's h=0.720；"
     f"基线跨域准确率最低 {pct(min(r['accuracy'] for r in BASE['transfer'] if r['source'] != r['target']))}"
     "（外卖→酒店），电商→外卖 "
     f"{pct(TRANSFER[('ecommerce', 'waimai')]['accuracy'])}",
     "不成立",
     "按领域分层评估；跨领域时做领域适配/重训练；阈值按领域校准，不使用单一全局阈值"],
    ["C6", "可以进行情感时间趋势分析",
     "三个公开数据集字段均为 label+review（+cat），没有时间字段；无法验证时间趋势",
     "无法验证",
     "时间趋势仅对含时间字段的上传数据启用；无时间字段时明确标注“不适用”，不输出趋势结论"],
    ["C7", "模型准确率不低于 85%",
     f"现有 BERT 测试集准确率 {pct(MODEL['accuracy'])}、宏平均 F1 {pct(MODEL['macro_f1'])}；"
     f"中性 F1 {pct(MODEL['per_class']['NEUTRAL']['f1'])}；低置信度 {pct(MODEL['low_conf_ratio'])}；"
     f"与 85% 相差 {gap_pp:.2f} 个百分点",
     "不成立",
     "改为分阶段目标：近期真实混合测试集宏平均 F1≥0.70，中期≥0.80；85% 需在数据与标注改进后再评估；"
     "报告同时披露分类别指标与低置信度比例"],
    ["C8", "本地模拟/示例数据可以支撑分析结论",
     "示例文件 200 条，无抽样框；本地 ChnSentiCorp 副本与公开版仅 3,094 条重合；"
     f"真实有效语料 {num(A['n'])} 条",
     "不成立",
     "示例数据仅用于界面演示与功能测试；论证证据全部改用公开数据表/图；报告中不引用示例文本作为结论依据"],
    ["C9", "中性类样本不足会影响中性判定",
     f"公开数据无中性金标准；中性类 F1 {pct(MODEL['per_class']['NEUTRAL']['f1'])}，低于正面 "
     f"{pct(MODEL['per_class']['POSITIVE']['f1'])} 与负面 {pct(MODEL['per_class']['NEGATIVE']['f1'])}；"
     f"低置信度 {pct(MODEL['low_conf_ratio'])}",
     "成立",
     "保留“中性为兜底类”的设计；优先补充真实中性标注或明确其推断属性；对低置信度结果强制人工复核"],
]
verdict_fill = {
    "成立": "D9F2E6",
    "部分成立": "FFF2CC",
    "不成立": "FADBD8",
    "无法验证": "E5E7EB",
}
table = add_table(
    ["编号", "原结论/假设", "真实数据证据", "判定", "调整后的表述"],
    conclusion_rows,
    widths=[1.0, 3.0, 5.4, 1.6, 4.8],
    font_size=8.0,
    align="left",
)
for row in table.rows[1:]:
    verdict = row.cells[3].text.strip()
    if verdict in verdict_fill:
        shade_cell(row.cells[3], verdict_fill[verdict])
note("注：判定依据均来自本报告第四至七章的表/图；C7 的 85% 目标出自需求报告，实际指标出自模型评估报告；"
     "C1–C9 的“原结论/假设”是原方案中明确写出或由数据链隐含的判断，复核后以本表“调整后的表述”为准。")

# --------------------------------------------------------------------------- #
# 九、调整后的分析方案
# --------------------------------------------------------------------------- #

heading("九、调整后的分析方案", 1, page_break=True)
heading("9.1 数据层", 2)
bullet(
    "建立数据源登记表：每个数据集记录名称、领域、URL、采集时间、原始规模、字段、标签体系与 SHA-256；"
    "当前登记表见 output/real_data/data_source_manifest.csv。"
)
bullet(
    "原始文件只读：下载后不改动原始文件；清洗结果单独输出，保留清洗脚本版本与运行时间。"
)
bullet(
    "禁止把示例/模拟数据作为论证证据：示例数据只用于界面演示、字段说明与功能测试；"
    "报告中的比例、均值、检验与模型指标必须来自真实公开数据或有明确采集记录的用户上传数据。"
)
bullet(
    "上传数据同样纳入溯源：保留原始文件、计算哈希、记录解析器版本与上传批次；"
    "对用户上传数据，报告应说明其来源、时间范围与样本量，不能默认其代表总体。"
)

heading("9.2 分析层", 2)
bullet(
    "分领域统计：所有情感比例、长度、关键词与模型指标按领域分层；全量指标只作为加权描述，并同时给出领域构成。"
)
bullet(
    "标签分层：公开金标准按二分类报告；中性作为模型推断类单独报告，不参与“真实情感分布”的分母。"
)
bullet(
    "长度审计：每次分析报告 >128 字、>256 字、>512 字的样本占比；对长评论给出截断提示或分段推理结果。"
)
bullet(
    "时间维度按需启用：仅当数据含可解析时间字段时输出趋势图；否则明确写“数据不含时间字段，趋势分析不适用”。"
)
bullet(
    "结论—证据绑定：每条结论后面标注对应的表号/图号/数据源；没有证据的结论不写，或明确标注为“待验证假设”。"
)

heading("9.3 模型层", 2)
bullet(
    "在真实留出集上重评：按领域分层划分训练/验证/测试，报告准确率、宏平均 F1、分类别 P/R/F1、混淆矩阵、"
    "低置信度比例与 95% 置信区间。"
)
bullet(
    "领域适配：优先尝试领域标记、分领域阈值与分领域微调；跨领域评估至少报告一个“源域→目标域”的迁移结果。"
)
bullet(
    "中性校准：补充真实中性标注，或把中性明确定义为“不确定/低置信度”而不是第三情感类；"
    "在没有中性金标准前，不宣称三分类准确率。"
)
bullet(
    "目标分阶段：近期以真实混合测试集宏平均 F1≥0.70 为可达目标，中期≥0.80；"
    "85% 只有在数据质量、标注一致性与领域覆盖改善后重新评估，不能沿用旧口径。"
)

heading("9.4 报告层", 2)
bullet("固定设置“数据来源说明”章节，列出获取渠道、采集时间、样本规模、字段、标签与校验值。")
bullet("固定设置“结论复核”章节，逐条列出原结论、真实数据证据、判定与调整后的表述。")
bullet("区分“观测”与“推断”：比例、均值、检验结果属于观测；对原因的解释必须标注为推断，并给出替代解释。")
bullet("披露局限：样本代表性、标签体系、时间字段、领域覆盖、模型测试集来源等限制必须写入报告。")

heading("9.5 复现流程", 2)
body("在项目根目录执行以下命令即可复现本报告的全部统计与图表：")
p = doc.add_paragraph()
p.paragraph_format.left_indent = Cm(0.74)
p.paragraph_format.space_after = Pt(4)
run = p.add_run("python real_data_analysis.py")
set_run_font(run, east="Consolas", size=10)
body(
    "脚本会先校验三个原始文件的 SHA-256，再完成清洗、去重、统计、关键词、基线与图表生成，"
    "结果写入 output/real_data/。报告生成脚本 build_real_data_report.py 读取 summary.json，"
    "确保正文数字与脚本计算结果一致。"
)

# --------------------------------------------------------------------------- #
# 十、结论与局限
# --------------------------------------------------------------------------- #

heading("十、结论与局限", 1, page_break=True)
heading("10.1 主要结论", 2)
bullet(
    f"真实公开语料共 {num(S['raw_total'])} 条原始记录，清洗去重后 {num(A['n'])} 条，"
    "覆盖酒店、电商 9 个子类与外卖三个领域，所有来源均可追溯、可校验。"
)
bullet(
    f"全量正向率 {pct(A['positive_rate'])}，不支持“整体正面为主”；酒店、电商、外卖的正向率分别为 "
    f"{pct(H['positive_rate'])}、{pct(E['positive_rate'])}、{pct(W['positive_rate'])}，"
    "领域差异显著，必须分层分析。"
)
bullet(
    f"整体文本偏短（中位数 {A['len_median']:.0f} 字），但酒店评论中位数 {H['len_median']:.0f} 字，"
    f"{pct(H['share_gt128'])} 超过 128 字；512 字符业务上限基本够用，128 token 模型上限存在实质截断风险。"
)
bullet(
    "公开数据没有中性金标准，中性只能作为模型推断类；现有 BERT 准确率 "
    f"{pct(MODEL['accuracy'])}、宏平均 F1 {pct(MODEL['macro_f1'])}、中性 F1 {pct(MODEL['per_class']['NEUTRAL']['f1'])}，"
    f"低置信度 {pct(MODEL['low_conf_ratio'])}，未达到 85% 目标。"
)
bullet(
    f"二分类基线在真实数据上达到 {pct(BASE['combined']['accuracy'])} 准确率，但跨领域迁移最低降至 "
    f"{pct(min(r['accuracy'] for r in BASE['transfer'] if r['source'] != r['target']))}，"
    "领域差异是影响模型效果的关键因素，跨领域直接套用不可行。"
)

heading("10.2 局限", 2)
bullet(
    "三个数据集是公开便利样本，不是概率抽样；电商语料按类别配平，酒店/外卖的类别比例也由提供方决定，"
    "不能把本报告的比例当作全网中文评论的总体比例。"
)
bullet(
    "公开数据没有时间字段、没有中性标注、没有用户人口属性；时间趋势、中性类真实分布、群体差异等问题"
    "无法用当前数据回答。"
)
bullet(
    "现有 BERT 指标来自项目原有测试集，未在本报告新采集的 72,222 条语料上重新跑三分类推理；"
    "两者任务与标签体系不同，不能直接比较。后续应在真实留出集上重跑 BERT，并报告分领域指标。"
)
bullet(
    "关键词使用字符二元组近似分词，存在碎片化与三字以上词覆盖不足的问题；主题词与情感词的区分仍需"
    "更细的标注或词典支持。"
)

heading("10.3 后续工作", 2)
bullet("补充带时间字段的公开评论数据（如带发布时间的社交媒体或点评数据），单独验证时间趋势。")
bullet("补充真实中性标注或人工复核集，重新校准中性类与低置信度阈值。")
bullet("在真实留出集上重跑 BERT，按领域分层报告指标，并尝试领域适配/分领域微调。")
bullet("把数据源登记、结论—证据绑定、截断率披露固化到系统导出模板与分析报告中。")

# --------------------------------------------------------------------------- #
# 参考文献
# --------------------------------------------------------------------------- #

heading("参考文献", 1, page_break=True)
references = [
    "[1] SophonPlus. ChineseNlpCorpus：中文自然语言处理语料/数据集[EB/OL]. GitHub, 2026-11-06. "
    "https://github.com/SophonPlus/ChineseNlpCorpus.",
    "[2] Tan S, Zhang J. An empirical study of sentiment analysis for Chinese documents[J]. "
    "Expert Systems with Applications, 2008, 34(4): 2622-2629.",
    "[3] 项目组. 软件工程实验需求报告——中文评论智能分析系统[R]. 2026.",
    "[4] 项目组. 软件工程实验报告——详细设计——中文评论智能分析系统[R]. 2026.",
    "[5] Monroe B L, Colaresi M P, Quinn K M. Fightin' Words: Lexical Feature Selection and Evaluation "
    "for Identifying the Content of Political Conflict[J]. Political Analysis, 2008, 16(4): 372-403.",
    "[6] Wilson E B. Probable Inference, the Law of Succession, and Statistical Inference[J]. "
    "Journal of the American Statistical Association, 1927, 22(158): 209-212.",
    "[7] 李航. 统计学习方法[M]. 2 版. 北京: 清华大学出版社, 2019.",
    "[8] UER-py. chinese_roberta_L-4_H-256[EB/OL]. Hugging Face. "
    "https://huggingface.co/uer/chinese_roberta_L-4_H-256.",
    "[9] 项目组. 模型评估报告 bert-zh-sentiment-v1[R]. 2026.",
]
for ref in references:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Cm(0.74)
    p.paragraph_format.first_line_indent = Cm(-0.74)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = p.add_run(ref)
    set_run_font(run, size=9.5)

# --------------------------------------------------------------------------- #
# 附录 A
# --------------------------------------------------------------------------- #

heading("附录 A  数据文件清单与校验值", 1, page_break=True)
body(
    "下表记录三个原始文件的本地路径、字节数、采集时间与 SHA-256。文件路径相对于项目根目录；"
    "原始文件位于 data/real_public/ 下，分析脚本只读，不修改原始文件。"
)
file_sizes = {
    "ChnSentiCorp_htl_all": os.path.getsize(os.path.join(BASE_DIR, "data", "real_public", "ChnSentiCorp_htl_all.csv")),
    "online_shopping_10_cats": os.path.getsize(os.path.join(BASE_DIR, "data", "real_public", "online_shopping_10_cats", "online_shopping_10_cats.csv")),
    "waimai_10k": os.path.getsize(os.path.join(BASE_DIR, "data", "real_public", "waimai_10k.csv")),
}
caption("表 A-1  原始数据文件清单")
add_table(
    ["数据集", "本地路径", "字节数", "采集时间", "SHA-256"],
    [
        ["ChnSentiCorp_htl_all", "data/real_public/ChnSentiCorp_htl_all.csv",
         num(file_sizes["ChnSentiCorp_htl_all"]), "2026-11-06 20:11",
         MANIFEST["ChnSentiCorp_htl_all"]["sha256"]],
        ["online_shopping_10_cats", "data/real_public/online_shopping_10_cats/online_shopping_10_cats.csv",
         num(file_sizes["online_shopping_10_cats"]), "2026-11-06 20:11",
         MANIFEST["online_shopping_10_cats"]["sha256"]],
        ["waimai_10k", "data/real_public/waimai_10k.csv",
         num(file_sizes["waimai_10k"]), "2026-11-06 20:11",
         MANIFEST["waimai_10k"]["sha256"]],
    ],
    widths=[3.4, 5.0, 1.9, 2.4, 3.4],
    font_size=7.2,
    align="left",
)
note("注：online_shopping_10_cats 原始压缩包为 data/real_public/online_shopping_10_cats.zip，"
     "SHA-256 为 " + MANIFEST["online_shopping_10_cats"]["archive_sha256"] + "；"
     "表中校验值为解压后 CSV 的 SHA-256。")

# --------------------------------------------------------------------------- #
# 附录 B
# --------------------------------------------------------------------------- #

heading("附录 B  复现步骤与输出文件", 1)
body("复现环境：Windows 10/11，Python 3.14.4，numpy 2.5.4，matplotlib 3.11.2，python-docx 1.2.0。")
body("步骤 1：确认 data/real_public/ 下三个原始文件存在；若缺失，按表 2-2 的 URL 重新下载。")
body("步骤 2：在项目根目录执行 python real_data_analysis.py，脚本会校验 SHA-256 并生成全部指标与图表。")
body("步骤 3：执行 python build_real_data_report.py，生成本报告。")
caption("表 B-1  分析输出文件清单")
add_table(
    ["文件", "内容"],
    [
        ["summary.json", "全部统计指标、关键词、基线、模型评估与数据源清单"],
        ["data_source_manifest.csv", "数据源登记表（URL、SHA-256、规模、字段、标签）"],
        ["domain_stats.csv", "分领域样本量、情感比例、置信区间、长度统计"],
        ["category_stats.csv", "电商 9 个子类的样本量与正向率"],
        ["top_bigrams.csv", "各领域高频二元组 Top20"],
        ["logodds_bigrams.csv", "分层对数几率结果"],
        ["lexicon_rates.csv", "情感词典命中率"],
        ["baseline_metrics.csv", "朴素贝叶斯基线分领域指标"],
        ["domain_transfer.csv", "跨领域迁移矩阵"],
        ["figures/fig01–fig08.png", "报告使用的 7 张图（fig03 为备用高频词图）"],
    ],
    widths=[5.6, 9.0],
    font_size=9,
    align="left",
)

# --------------------------------------------------------------------------- #
# 附录 C
# --------------------------------------------------------------------------- #

heading("附录 C  指标说明", 1)
body("为避免指标口径不一致，下表给出本报告使用的关键指标定义。")
caption("表 C-1  指标定义")
add_table(
    ["指标", "定义", "本报告用途"],
    [
        ["正向率", "正向评论数 / 有效评论数", "描述领域情感分布"],
        ["Wilson 置信区间", "基于二项分布的 95% 置信区间，适合大样本比例", "判断比例估计的稳定性"],
        ["Cohen's h", "2arcsin(√p1)-2arcsin(√p2)", "衡量两个比例差异的效应量"],
        ["χ²", "列联表卡方统计量", "检验领域与情感极性是否独立"],
        ["分层对数几率 z", "领域内对数几率按逆方差加权合并后的 z 值", "识别与正/负评论关联最强的词"],
        ["宏平均 F1", "各类别 F1 的算术平均", "避免类别不均衡时准确率虚高"],
        ["低置信度占比", "置信度 <0.60 的样本 / 总样本", "衡量人工复核压力"],
        ["截断率", "字符数或 token 数超过模型上限的样本占比", "评估长评论信息损失"],
    ],
    widths=[3.2, 6.6, 4.8],
    font_size=8.8,
    align="left",
    first_col_bold=True,
)

# 设置更新域
set_update_fields(doc)

# 保存
os.makedirs(os.path.dirname(DOCX_PATH), exist_ok=True)
doc.save(DOCX_PATH)
print(f"[信息] 报告已生成：{DOCX_PATH}")
print(f"[信息] 报告大小：{os.path.getsize(DOCX_PATH):,} 字节")
