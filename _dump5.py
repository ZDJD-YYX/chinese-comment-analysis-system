import docx
p = r"e:\trae\中文评论智能分析系统\文档\1792460254987-软件工程实验报告模板 -详细设计报告.docx"
d = docx.Document(p)
s = d.sections[0]
print("page cm", round(s.page_width.cm,2), round(s.page_height.cm,2), "margins", round(s.left_margin.cm,2), round(s.right_margin.cm,2), round(s.top_margin.cm,2), round(s.bottom_margin.cm,2))
print("styles:", [st.name for st in d.styles if st.type==1][:20])
n = d.styles['Normal']
print("normal", n.font.name, n.font.size, n.paragraph_format.line_spacing, n.paragraph_format.first_line_indent)
for i in [22,24,31,32,33,41,42,43,44,54]:
    par=d.paragraphs[i]
    pf=par.paragraph_format
    print(i, par.style.name, "align",par.alignment, "indent",pf.first_line_indent, "ls",pf.line_spacing, "sb",pf.space_before,"sa",pf.space_after, "|", par.text[:40])
    for r in par.runs[:2]:
        print("    run", r.font.name, r.font.size, "bold",r.bold)
