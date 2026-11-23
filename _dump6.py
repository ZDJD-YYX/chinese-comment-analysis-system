import docx
p = r"e:\trae\中文评论智能分析系统\文档\1792460254987-软件工程实验报告模板 -详细设计报告.docx"
d = docx.Document(p)
for name in ['Heading 1','Heading 2']:
    st=d.styles[name]
    pf=st.paragraph_format
    print(name, "font",st.font.name, st.font.size, "bold",st.font.bold, "color", st.font.color.rgb if st.font.color and st.font.color.rgb else None)
    print("  pf", pf.space_before, pf.space_after, pf.line_spacing, pf.first_line_indent, pf.keep_with_next)
    print("  base", st.base_style.name if st.base_style else None)
