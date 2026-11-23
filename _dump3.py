import docx, sys
p = r"e:\trae\中文评论智能分析系统\文档\软件工程实验报告-概要设计-中文评论智能分析系统.docx"
d = docx.Document(p)
print("paras", len(d.paragraphs), "tables", len(d.tables))
for i, par in enumerate(d.paragraphs):
    t = par.text.strip()
    if t:
        print(i, "|", par.style.name, "|", t[:300])
