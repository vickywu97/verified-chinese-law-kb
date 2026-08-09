# law-citation-bench · 方向 A 评测基准（M0 原型）

> 在 [verified-chinese-law-kb](../../)（2327 条逐字核验条文）之上，构建**离线可跑、纯标准库、可量化模型法条引用能力**的评测基准。
> 本目录是设计草图（[docs/benchmark-design-A.md](../../docs/benchmark-design-A.md)）的 **M0 可运行原型**：已能生成可复现数据集，并用哑基线跑出 leaderboard。

## 定位

法律 AI 在「引用具体法条」时高频幻觉——错引条文号、编造条文内容、张冠李戴。本基准以 KB 的 `verification_status = verified` 条文为**唯一真值**，评测模型三类能力。

## 评测任务

| 任务 | 输入 | 期望输出 | 真值 | 评分 |
|------|------|----------|------|------|
| **T1 引用接地** | 由条文内容生成的自然语言问句 | `LAW:`/`ARTICLE:`/`KEY:` | KB 对应条文 | `0.7·精确匹配 + 0.3·字符级F1` |
| **T2 条文检索** | 同上问句 | Top-5 条文 ID | 该条文 ID | `Recall@5`、`MRR` |
| **T3 幻觉识别** | 一段「引用了某条文」的文本 | `命中`/`未命中`/`篡改` | 受控扰动标签 | `Accuracy`、`Macro-F1` |

## 模型输出格式（评分器依赖）

- **T1**：纯文本，三行
  ```
  LAW: VAT_LAW
  ARTICLE: 第1条
  KEY: <关键句>
  ```
- **T2**：每行一个条文 ID（`VAT_LAW_1_v1`），最多 5 个。
- **T3**：单个标签 `命中` / `未命中` / `篡改`（也接受英文 `hit`/`miss`/`altered`）。

> 格式封闭、无歧义，便于判分模型/脚本直接解析。

## 快速开始（全程离线，仅标准库）

```bash
# 1) 生成 500 题 smoke 数据集（确定性：固定随机种子）
python3 build_dataset.py
#    -> dataset/smoke_500.jsonl  +  dataset/smoke_500.meta.json

# 2) 用哑基线跑分，产出 leaderboard.csv
python3 run.py --baseline random     # 随机基线
python3 run.py --baseline first      # 永远返回首条基线
```

要求 Python ≥ 3.8（`python -S` 亦可，无任何第三方依赖）。

## 当前哑基线结果（证明基准可区分好坏）

| model | overall | T1 | T2(recall@5) | T3(acc) | T3(macro_f1) |
|-------|--------:|---:|-------------:|--------:|-------------:|
| random-baseline | 0.072 | 0.035 | 0.000 | 0.290 | 0.210 |
| always-first-baseline | 0.083 | 0.042 | 0.000 | 0.330 | 0.165 |

哑基线接近随机水平（T2 检索几乎全错、T3 靠猜），说明基准**对噪声模型有区分度**——真实法律模型应显著高于此。

## 目录结构

```
law_citation_bench/
  common.py            # KB 加载 + 法律名映射（真值来源 = ../modules）
  build_dataset.py     # M0：模板法从 KB 生成 500 题（离线、可复现）
  score.py             # 字符级F1 / Recall@5 / MRR / Macro-F1，纯 stdlib
  run.py               # 编排：dataset→adapter→score→leaderboard.csv
  adapters/
    base.py            # ModelAdapter 接口（generate(prompt)->str）
    dummy.py           # 校准基线：random / always-first
    openai_stub.py     # 真实 API 适配器模板（默认不启用，保持离线）
  dataset/
    smoke_500.jsonl    # 生成的评测集
    smoke_500.meta.json# 生成参数与统计（可复现凭证）
  leaderboard.csv      # 最近一次运行结果
  README.md
```

## 设计约束（遵循 DD-007 离线教训）

- **零第三方依赖**：中文相似度默认字符级重叠，不引入 jieba / lxml。
- **真值一致性**：仅以 KB 中 `verified` 条文为真值，评测集自身不携带幻觉。
- **模型解耦**：适配器层隔离具体模型，评分逻辑与 API 无关；联网仅发生在「调用模型」，真值比对/评分/报告全离线。

## 下一步里程碑

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| M0 | 数据集生成 + 哑基线跑通 | ✅ 本次完成 |
| M1 | `score.py` 正式版 + 难度分层报告 | 待做 |
| M2 | 接入 1–2 个真实模型 API（用 `openai_stub.py` 模板） | 待做 |
| M3 | 报告模板（Markdown/HTML）+ 可展示 leaderboard | 待做 |

> 发布建议：未来可作为独立 repo `law-citation-bench` 发布（评测集与 KB 解耦），本仓库 README 互引。当前阶段以子目录形式落地以便复用 KB。
