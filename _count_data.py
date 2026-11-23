import pandas as pd, os
base = r"e:\trae\中文评论智能分析系统"
for rel in ["output_v3/train.csv","output_v3/val.csv","output_v3/test.csv","data/ChnSentiCorp.csv","data/amazon_zh_3class.csv","data/train_source.csv"]:
    p = os.path.join(base, rel)
    if os.path.exists(p):
        try:
            df = pd.read_csv(p)
            print(rel, len(df), list(df.columns)[:6])
        except Exception as e:
            print(rel, "ERR", e)
    else:
        print(rel, "MISSING")
