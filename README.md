# 中文评论智能分析系统

基于 BERT 的中文评论情感分析与可视化平台。支持上传文件、粘贴文本、抓取网页链接三种评论输入方式，自动完成**正面 / 负面 / 中性**三分类情感分析，并输出情感分布、置信度、趋势、热点词词云、人工复核与报告导出等结果。

> 软件工程综合实训项目 · 作者：闫宇星

## 功能特性

- **多种数据输入**：CSV / Excel 文件上传、纯文本粘贴、网页链接正文抓取
- **情感三分类**：BERT 微调模型（正面 POSITIVE / 负面 NEGATIVE / 中性 NEUTRAL）
- **任务管理**：创建、执行、实时进度、取消、重命名、批量删除
- **结果可视化**：情感占比、置信度分布、时间趋势、TF-IDF 热点词词云
- **人工复核**：低置信度结果自动标记，支持单条 / 批量复核与复核质量统计
- **报告与导出**：在线分析报告、Excel 明细导出、数据备份与重新导入
- **系统管理**：用户注册登录、系统设置、审计日志、全局仪表盘

## 系统架构

```
┌──────────────────────────────────────────────┐
│ 浏览器：HTML5 + CSS3 + 原生 JS + ECharts 5    │
└───────────────────────┬──────────────────────┘
                        │ HTTP / JSON
┌───────────────────────▼──────────────────────┐
│ Spring Boot 2.7（REST API + 静态资源托管）    │
│  ├─ MyBatis-Plus ─────────► MySQL 8.0         │
│  └─ DJL + libtorch（CPU）─► TorchScript 模型  │
└───────────────────────┬──────────────────────┘
                        │ 离线训练产物
┌───────────────────────▼──────────────────────┐
│ Python：Transformers 微调 → model.pt/vocab    │
└──────────────────────────────────────────────┘
```

前后端一体化部署：前端页面位于 `backend/src/main/resources/static/`，由 Spring Boot 直接托管。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | HTML5 / CSS3 / 原生 JavaScript / ECharts 5（含词云插件） |
| 后端 | Java 8+ / Spring Boot 2.7.15 / MyBatis-Plus 3.5.3 / EasyExcel / jsoup |
| 模型推理 | DJL 0.38.0 + PyTorch 2.7.1 libtorch（CPU） |
| 数据库 | MySQL 8.0 |
| 模型训练 | Python 3.8+ / PyTorch / HuggingFace Transformers / scikit-learn / jieba |

## 目录结构

```
.
├── backend/                        # Spring Boot 后端（含前端静态资源）
│   ├── pom.xml
│   └── src/main/
│       ├── java/com/example/commentanalysis/
│       │   ├── ai/                 # 模型加载、分词、情感推理、关键词提取
│       │   ├── controller/         # REST 接口
│       │   ├── service/            # 业务逻辑
│       │   ├── entity/             # 数据库实体（对应 6 张表）
│       │   └── ...
│       └── resources/
│           ├── application.yml     # 端口、数据源、模型路径等配置
│           └── static/             # 前端页面（index.html / css / js / lib）
├── data/                           # 数据集（大文件未纳入仓库）
├── model/                          # 训练产物（未纳入仓库，需自行生成）
├── 文档/                            # 需求、概要设计、详细设计、分析报告
├── data_preprocessing_eda.py       # 数据清洗、EDA、分层划分
├── prepare_dataset_v2.py           # 三分类标签修正（概率教师重标注）
├── train.py                        # BERT 微调训练与 TorchScript 导出
├── inference.py                    # 情感推理与 TF-IDF 热点词提取
├── real_data_analysis.py           # 真实公开数据分析与基线实验
└── build_real_data_report.py       # 生成真实数据分析报告（Word）
```

## 模型说明

| 项目 | 说明 |
| --- | --- |
| 基座模型 | `uer/chinese_roberta_L-4_H-256` |
| 标签 | `0=POSITIVE`、`1=NEGATIVE`、`2=NEUTRAL` |
| 最大长度 | 128 token |
| 测试集 | 1854 条 |
| 准确率 | 80.20% |
| 宏平均 F1 | 79.41% |
| 平均置信度 | 82.51% |

训练脚本默认导出到 `model/bert-zh-sentiment-v1/`，当前部署版本为 `model/bert-zh-sentiment-v3/`（含温度校准与类别偏置修正）。

模型权重（约 196MB）未纳入仓库，可从 [Releases v1.0.0](https://github.com/ZDJD-YYX/chinese-comment-analysis-system/releases/tag/v1.0.0) 下载 [model.zip](https://github.com/ZDJD-YYX/chinese-comment-analysis-system/releases/download/v1.0.0/model.zip)，解压后放入项目根目录的 `model/` 下；也可按下方「训练模型」自行训练生成。

## 快速开始

### 1. 环境要求

- JDK 8 及以上、Maven 3.6+
- MySQL 8.0
- Python 3.8+（仅训练与命令行推理脚本需要）

### 2. 准备数据库

创建数据库（推荐 `utf8mb4`）：

```sql
CREATE DATABASE comment_analysis DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

共 6 张表：`analysis_task`、`comment_data`、`analysis_result`、`keyword_statistics`、`task_statistics`、`sys_user`。表结构由 `backend/.../entity` 下的实体类定义，字段说明见《详细设计报告》。

### 3. 准备模型文件

将以下文件放入一个**纯 ASCII 路径**的目录（例如 `D:/models/bert-zh-sentiment-v3`）：

| 文件 | 用途 |
| --- | --- |
| `model.pt` | TorchScript 推理模型（后端 DJL 加载） |
| `vocab.txt` | 词表 |
| `labels.txt` | 标签顺序（POSITIVE / NEGATIVE / NEUTRAL） |

然后修改 `backend/src/main/resources/application.yml`：

```yaml
app:
  model:
    path: D:/models/bert-zh-sentiment-v3
```

> 注意：libtorch 在 Windows 上无法打开含中文字符的路径，模型目录必须使用纯 ASCII 路径。

### 4. 配置并启动后端

修改 `application.yml` 中的数据源配置为本机 MySQL：

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/comment_analysis?useUnicode=true&characterEncoding=utf8&useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=Asia/Shanghai
    username: 你的用户名
    password: 你的密码
```

构建并启动：

```bash
cd backend
mvn clean package -DskipTests
java -jar target/comment-analysis-system-1.0.0.jar
```

或开发模式直接运行：

```bash
mvn spring-boot:run
```

启动后访问 <http://localhost:8080>，首次使用请先注册账号。

跨平台打包（自动切换 PyTorch 本地库）：

```bash
mvn -Plinux package      # Linux x86_64
mvn -Pmacos package      # macOS Apple Silicon
```

### 5. 训练模型（可选）

```bash
pip install torch transformers scikit-learn pandas numpy matplotlib jieba joblib

# 1) 清洗、EDA 与分层划分（70% / 20% / 10%）
python data_preprocessing_eda.py --input data/ChnSentiCorp.csv --output output

# 2) 三分类标签修正（用二分类概率教师重标注 3 星样本）
python prepare_dataset_v2.py --src output --dst output_v3 --scheme cue

# 3) 微调训练与导出
python train.py --data-dir output_v3 --epochs 5 --batch-size 32 --lr 5e-5 --max-length 128
```

国内网络下载基座模型较慢时，可先设置镜像：

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"   # Windows PowerShell
export HF_ENDPOINT=https://hf-mirror.com   # Linux / macOS
```

### 6. 命令行推理测试

```bash
python inference.py --text "物流很快，包装也很用心"
python inference.py --top-n 20                    # 内置演示数据 + 热点词
python inference.py --model-dir model/bert-zh-sentiment-v3
```

## 主要接口

| 模块 | 方法与路径 | 说明 |
| --- | --- | --- |
| 用户 | `POST /api/user/register` / `login` / `logout` | 注册、登录、退出 |
| 用户 | `GET /api/user/me`、`POST /api/user/password` | 当前用户、修改密码 |
| 输入 | `POST /api/file/upload` | 上传 CSV / Excel 评论文件 |
| 输入 | `POST /api/input/analyze` / `preview` / `confirm` | 文本或链接智能输入 |
| 任务 | `GET /api/task/list`、`GET /api/task/{id}` | 任务列表与详情 |
| 任务 | `POST /api/task/{id}/run` / `cancel`、`GET /api/task/{id}/progress` | 执行、取消、进度 |
| 任务 | `DELETE /api/task/{id}`、`POST /api/task/batch-delete` / `{id}/rename` | 删除、批删、重命名 |
| 结果 | `GET /api/result/list`、`POST /api/result/{id}/review` | 明细与人工复核 |
| 结果 | `GET /api/result/statistics/{taskId}` / `keywords` / `trend` / `confidence` | 统计、热点词、趋势、置信度 |
| 结果 | `GET /api/result/report/{taskId}` / `export/{taskId}` | 分析报告、Excel 导出 |
| 其他 | `GET /api/dashboard/summary` | 仪表盘汇总 |
| 其他 | `GET / POST /api/settings`、`GET /api/settings/audit` | 系统设置、审计日志 |

所有接口统一返回 `{ code, message, data }` 结构。

## 数据集说明

仓库保留可直接运行的小体积样本：

- `data/ChnSentiCorp.csv`：酒店评论情感数据
- `data/train_source.csv`：训练用合并数据
- `data/示例评论_200条.csv`：演示样本
- `data/真实评论_网络下载/`：部分公开真实评论

以下大文件因体积限制未纳入仓库，可下载 [data.zip](https://github.com/ZDJD-YYX/chinese-comment-analysis-system/releases/download/v1.0.0/data.zip)（约 44MB，解压后合并到项目根目录的 `data/` 下），或从公开渠道获取：

| 数据集 | 约体积 |
| --- | --- |
| 美团餐饮评论 ASAP train / dev / test | 44 MB |
| online_shopping_10_cats 电商评论 | 11 MB |

真实数据分析使用的公开数据集：ChnSentiCorp_htl_all、online_shopping_10_cats、waimai_10k、ASAP、SenTARev。

## 项目文档

`文档/` 目录包含：

- 《软件工程实验需求报告》
- 《软件工程实验报告 - 概要设计》
- 《软件工程实验报告 - 详细设计》
- 《中文评论智能分析系统 - 真实数据分析报告》（docx / pdf）
- 《模型优化报告》
- 《软件工程综合实训实践指导书》

## 注意事项

- `application.yml` 中的数据源账号密码为本地开发默认值，部署前请务必修改。
- 模型文件、`backend/target/` 构建产物、日志、运行时输出与超过 5MB 的数据文件已通过 `.gitignore` 排除，克隆后需按上文自行准备。
- 模型缺失时服务仍可启动（`app.model.fail-fast: false`），但创建分析任务会返回错误码 `3001`。
- 低置信度阈值默认为 `0.60`，可在 `application.yml` 的 `app.inference.review-threshold` 调整。

## 致谢

感谢 ChnSentiCorp、online_shopping_10_cats、waimai_10k、ASAP、SenTARev 等公开数据集的提供方，以及 HuggingFace、DJL 开源社区。
