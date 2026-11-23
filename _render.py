import pymupdf, os
pdf=r"e:\trae\中文评论智能分析系统\_dd_preview.pdf"
out=r"e:\trae\中文评论智能分析系统\_dd_pages"
os.makedirs(out, exist_ok=True)
d=pymupdf.open(pdf)
print("pages",len(d))
for i in [0,1,3,5,7,9,11,13,19,21,25,29,32,35,37]:
    p=d[i]
    pix=p.get_pixmap(dpi=110)
    pix.save(os.path.join(out,f"p{i+1:02d}.png"))
print("done")
