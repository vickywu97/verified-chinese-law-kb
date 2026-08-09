# law-citation-bench · 跑分榜 (Leaderboard)

- 数据集：`smoke_500.jsonl`
- 题量：500
- 生成时间：2026-08-09T23:43:51
- 难度分布：易 123 / 中 196 / 难 181

## 综合跑分

| 模型 | n | Overall | T1 接地 | T2 检索 | T2@5 | T3 识别 | T3-macroF1 |
|---|---|---|---|---|---|---|---|
| random-baseline | 500 | 0.0660 | 0.0350 | 0.0000 | 0.0000 | 0.2600 | 0.2532 |
| always-first-baseline | 500 | 0.0826 | 0.0415 | 0.0000 | 0.0000 | 0.3300 | 0.1654 |

## 难度分层（Overall by 难度）

| 模型 | 易 | 中 | 难 |
|---|---|---|---|
| random-baseline | 0.1188 | 0.0454 | 0.0523 |
| always-first-baseline | 0.2867 | 0.0173 | 0.0146 |

## 任务 × 难度 矩阵（Overall）

| 模型 | 任务 | 易 | 中 | 难 |
|---|---|---|---|---|
| random-baseline | T1 引用接地 | 0.0359 | 0.0358 | 0.0334 |
| random-baseline | T2 条文检索 | 0.0000 | 0.0000 | 0.0000 |
| random-baseline | T3 幻觉识别 | 0.3939 | 0.1765 | 0.2121 |
| always-first-baseline | T1 引用接地 | 0.0504 | 0.0420 | 0.0356 |
| always-first-baseline | T2 条文检索 | 0.0000 | 0.0000 | 0.0000 |
| always-first-baseline | T3 幻觉识别 | 1.0000 | 0.0000 | 0.0000 |

> 评分说明：T1 = 0.7×法条精确匹配 + 0.3×关键句字符级 F1；T2 = Recall@5（MRR 另列）；T3 = Accuracy，macro-F1 为三类平均。哑基线用于校准，证明基准能区分好坏模型。
