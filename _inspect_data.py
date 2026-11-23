import pandas as pd, json, os
base = r"e:\trae\中文评论智能分析系统"
for rel in ["output_v3/train.csv","data/ChnSentiCorp.csv","data/amazon_zh_3class.csv","data/train_source.csv"]:
    df = pd.read_csv(os.path.join(base, rel))
    print("==", rel, "rows", len(df))
    print(df.head(3).to_string(index=False))
    print("labels", df['label'].value_counts().to_dict())
print("== relabel_report keys")
rep = json.load(open(os.path.join(base,"output_v3/relabel_report.json"), encoding="utf-8"))
print(list(rep.keys()))
print(json.dumps(rep, ensure_ascii=False, indent=2)[:1600])
