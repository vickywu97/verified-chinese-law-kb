# law-citation-bench · 跑分榜 (Leaderboard)

- 数据集：`smoke_500.jsonl`
- 题量：500
- 生成时间：2026-08-12T13:00:37
- 难度分布：易 123 / 中 196 / 难 181

## 综合跑分

| 模型 | n | Overall | T1 接地 | T2 检索 | T2@5 | T3 识别 | T3-macroF1 |
|---|---|---|---|---|---|---|---|
| qwen/qwen-plus | 500 | 0.5024 | 0.2860 | 0.6700 | 0.6700 | 0.6000 | 0.4928 |
| deepseek/deepseek-chat | 500 | 0.4145 | 0.3312 | 0.4850 | 0.4850 | 0.4400 | 0.4304 |
| zhipu/glm-4-flash | 500 | 0.1781 | 0.2851 | 0.0000 | 0.0000 | 0.3200 | 0.1616 |
| random-baseline | 500 | 0.0660 | 0.0350 | 0.0000 | 0.0000 | 0.2600 | 0.2532 |
| always-first-baseline | 500 | 0.0826 | 0.0415 | 0.0000 | 0.0000 | 0.3300 | 0.1654 |

## 难度分层（Overall by 难度）

| 模型 | 易 | 中 | 难 |
|---|---|---|---|
| qwen/qwen-plus | 0.6017 | 0.3963 | 0.5498 |
| deepseek/deepseek-chat | 0.5567 | 0.4289 | 0.3022 |
| zhipu/glm-4-flash | 0.3676 | 0.1209 | 0.1111 |
| random-baseline | 0.1188 | 0.0454 | 0.0523 |
| always-first-baseline | 0.2867 | 0.0173 | 0.0146 |

## 任务 × 难度 矩阵（Overall）

| 模型 | 任务 | 易 | 中 | 难 |
|---|---|---|---|---|
| qwen/qwen-plus | T1 引用接地 | 0.2892 | 0.2922 | 0.2772 |
| qwen/qwen-plus | T2 条文检索 | 0.7333 | 0.6667 | 0.6351 |
| qwen/qwen-plus | T3 幻觉识别 | 0.8485 | 0.0000 | 0.9697 |
| deepseek/deepseek-chat | T1 引用接地 | 0.3218 | 0.3095 | 0.3607 |
| deepseek/deepseek-chat | T2 条文检索 | 0.7556 | 0.5185 | 0.2838 |
| deepseek/deepseek-chat | T3 幻觉识别 | 0.6061 | 0.5000 | 0.2121 |
| zhipu/glm-4-flash | T1 引用接地 | 0.2937 | 0.2926 | 0.2717 |
| zhipu/glm-4-flash | T2 条文检索 | 0.0000 | 0.0000 | 0.0000 |
| zhipu/glm-4-flash | T3 幻觉识别 | 0.9697 | 0.0000 | 0.0000 |
| random-baseline | T1 引用接地 | 0.0359 | 0.0358 | 0.0334 |
| random-baseline | T2 条文检索 | 0.0000 | 0.0000 | 0.0000 |
| random-baseline | T3 幻觉识别 | 0.3939 | 0.1765 | 0.2121 |
| always-first-baseline | T1 引用接地 | 0.0504 | 0.0420 | 0.0356 |
| always-first-baseline | T2 条文检索 | 0.0000 | 0.0000 | 0.0000 |
| always-first-baseline | T3 幻觉识别 | 1.0000 | 0.0000 | 0.0000 |

## T3 分类明细（命中 / 未命中 / 篡改）

| 模型 | 命中 n / acc | 未命中 n / acc | 篡改 n / acc |
|---|---|---|---|
| qwen/qwen-plus | 33 / 0.8485 | 33 / 0.9697 | 34 / 0.0000 |
| deepseek/deepseek-chat | 33 / 0.6061 | 33 / 0.2121 | 34 / 0.5000 |
| zhipu/glm-4-flash | 33 / 0.9697 | 33 / 0.0000 | 34 / 0.0000 |
| random-baseline | 33 / 0.3939 | 33 / 0.2121 | 34 / 0.1765 |
| always-first-baseline | 33 / 1.0000 | 33 / 0.0000 | 34 / 0.0000 |

> 评分说明：T1 = 0.7×法条精确匹配 + 0.3×关键句字符级 F1；T2 = Recall@5（MRR 另列）；T3 = Accuracy，macro-F1 为三类平均。哑基线用于校准，证明基准能区分好坏模型。
