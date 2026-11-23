import docx
from docx.shared import Pt
p = r"e:\trae\中文评论智能分析系统\文档\1792460254987-软件工程实验报告模板 -详细设计报告.docx"
d = docx.Document(p)
s = d.sections[0]
print("page", s.page_width.cm, s.page_height.cm, "margins", s.left_margin.cm, s.right_margin.cm, s.top_margin.cm, s.bottom_margin.cm)
print("normal font", d.styles['Normal'].font.name, d.styles['Normal'].font.size)
for name in ['Heading 1','Heading 2','Heading 3','Title']:
    if name in [st.name for st in d.styles]:
        st = d.styles[name]
        print(name, st.font.name, st.font.size, st.font.bold, st.font.color.rgb if st.font.color and st.font.color.rgb else None)
        print("   xml:", st._element.xml[:600])
for i in [22,23,24,31,32,33,44,54,55,58,67,86,104]:
    par = d.paragraphs[i]
    print("---", i, par.style.name, par.alignment, par.paragraph_format.first_line_indent, par.paragraph_format.line_spacing, par.paragraph_format.space_before, par.paragraph_format.space_after)
    for r in par.runs[:4]:
        print("   run:", repr(r.text[:40]), r.font.name, r.font.size, r.bold, r.font.element.rPr.xml if r.font.element.rPr is not None else None)
