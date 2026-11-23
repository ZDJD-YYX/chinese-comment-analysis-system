import docx
p = r"e:\trae\中文评论智能分析系统\文档\1792460254987-软件工程实验报告模板 -详细设计报告.docx"
d = docx.Document(p)
print("paras", len(d.paragraphs), "tables", len(d.tables), "sections", len(d.sections))
for i, par in enumerate(d.paragraphs):
    t = par.text.strip()
    print(i, "|", par.style.name, "|", t[:200])
