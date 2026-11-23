import pandas as pd, os
base = r"e:\trae\中文评论智能分析系统"
for rel in ["data/amazon_zh_neutral.csv","data/train_source.csv"]:
    df = pd.read_csv(os.path.join(base, rel))
    print(rel, len(df), df['label'].value_counts().to_dict())
# check if train_source = chn + amazon3 + neutral
chn = pd.read_csv(os.path.join(base,"data/ChnSentiCorp.csv"))
a3 = pd.read_csv(os.path.join(base,"data/amazon_zh_3class.csv"))
an = pd.read_csv(os.path.join(base,"data/amazon_zh_neutral.csv"))
print("sum", len(chn), len(a3), len(an), len(chn)+len(a3)+len(an))
