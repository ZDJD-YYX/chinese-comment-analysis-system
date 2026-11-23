import docx
p=r"e:\trae\中文评论智能分析系统\文档\软件工程实验报告-详细设计-中文评论智能分析系统.docx"
d=docx.Document(p)
print("paras",len(d.paragraphs),"tables",len(d.tables),"figs",len(d.inline_shapes))
for par in d.paragraphs:
    t=par.text.strip()
    if t and (par.style.name.startswith("Heading") or t.startswith("图 ") or t.startswith("表 ")):
        print(par.style.name,"|",t[:80])
