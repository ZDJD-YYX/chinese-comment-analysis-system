import os
root=r"e:\trae\中文评论智能分析系统\backend\src\main\java"
n=0; loc=0
for dp,dn,fn in os.walk(root):
    for f in fn:
        if f.endswith(".java"):
            n+=1
            loc+=sum(1 for _ in open(os.path.join(dp,f),encoding="utf-8"))
print("main java files",n,"lines",loc)
root2=r"e:\trae\中文评论智能分析系统\backend\src\main\resources\static"
n2=0; loc2=0
for ext in (".html",".js",".css"):
    for dp,dn,fn in os.walk(root2):
        for f in fn:
            if f.endswith(ext):
                n2+=1; loc2+=sum(1 for _ in open(os.path.join(dp,f),encoding="utf-8",errors="ignore"))
print("frontend files",n2,"lines",loc2)
