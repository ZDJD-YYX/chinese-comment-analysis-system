# -*- coding: utf-8 -*-
"""把《概要设计说明书》中的 10 处 [mermaid] 源码文本段落替换为正式设计图，并补图题。"""
import os
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

TPL = r'c:\Users\ZhuanZ\Desktop\软件工程实训\概要设计说明书.docx'
DST = r'c:\Users\ZhuanZ\Desktop\软件工程实训\概要设计说明书-中文评论智能分析系统.docx'
FIG = r'd:\trae\中文评论智能分析系统\_figs'

# (用于定位该 mermaid 段落的唯一关键字, 图片文件名, 显示宽度英寸, 图题)
FIGS = [
    ('subgraph PL', 'hld_arch.png', 6.2, '图 2-1  中文评论智能分析系统四层总体架构图'),
    ('M1["M1 用户管理"]', 'hld_module_dep.png', 6.2, '图 2-2  模块依赖关系图'),
    ('flowchart TD', 'hld_flow.png', 5.6, '图 2-3  核心业务流程图（上传 → 解析 → 调度推理 → 存储 → 展示）'),
    ('participant FC as FileController', 'hld_seq_core.png', 5.6, '图 2-4  核心业务流程时序图'),
    ('stateDiagram-v2', 'hld_task_state.png', 6.2, '图 3-1  分析任务状态机'),
    ('erDiagram', 'hld_er.png', 6.2, '图 4-1  核心实体关系图（概念 E-R 图）'),
    ('InferenceFacade<br/>唯一对外门面', 'hld_ai_comp.png', 6.2, '图 6-1  智能模块组件结构图'),
    ('participant REPO as ModelRepository', 'hld_seq_model_load.png', 6.2, '图 6-2  模型加载与生命周期时序图'),
    ('participant SCH as InferenceScheduler', 'hld_seq_infer.png', 6.0, '图 6-3  推理调用流程时序图'),
    ('subgraph CLIENT["客户端"]', 'hld_deploy.png', 6.2, '图 7-1  网络与部署拓扑图'),
]

doc = Document(TPL)
P = doc.paragraphs


def clear(p):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)


def add_caption_after(p, text):
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run(text)
    run.font.name = '宋体'
    run.font.size = Pt(9)
    run.bold = True
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    p._p.addnext(cap._p)
    return cap


ok = 0
for key, name, width, cap in FIGS:
    hit = None
    for p in P:
        t = p.text
        if t.strip().startswith('[mermaid]') and key in t:
            hit = p
            break
    if hit is None:
        raise SystemExit(f'未找到 mermaid 段落，关键字：{key}')
    path = os.path.join(FIG, name)
    if not os.path.exists(path):
        raise SystemExit(f'缺少图片：{path}')
    clear(hit)
    hit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hit.add_run().add_picture(path, width=Inches(width))
    add_caption_after(hit, cap)
    ok += 1
    print(f'已替换 -> {name}（宽 {width} in）')

print()
for p in doc.paragraphs:
    s = p.text.strip()
    if s.startswith('[mermaid]'):
        print('!! 仍有未替换的 mermaid 段落：', s[:60])

doc.save(DST)
print(f'共替换 {ok} 处；图片总数 = {len(doc.inline_shapes)}')
print('已生成：', DST)
