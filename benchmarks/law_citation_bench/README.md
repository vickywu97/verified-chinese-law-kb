# law-citation-bench · 方向 A 评测基准（M0–M3）

> 在 [verified-chinese-law-kb](../../)（2327 条逐字核验条文）之上，构建**离线可跑、纯标准库、可量化模型法条引用能力**的评测基准。
> 本目录是设计草图（[docs/benchmark-design-A.md](../../docs/benchmark-design-A.md)）的落地实现：**M0** 可复现数据集、**M1** 哑基线跑通、**M3** 难度分层与 Markdown/HTML 报告均已就绪；**M2** 真实模型适配器已接线，用户自备 key 即可出跑分。

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

# 2) 用哑基线跑分，并产出完整报告（csv / json / md / html）
python3 run.py --baseline all
#    -> leaderboard.csv  leaderboard.json  leaderboard.md  leaderboard.html

# 3) （可选）接入真实模型 —— 仅"调用模型"联网，评分/报告仍离线
#    适配器走 OpenAI 兼容协议，已内置 4 家国产厂商预设（无需 OpenAI key）：
python3 run.py --model qwen      # 阿里 通义千问  (key: DASHSCOPE_API_KEY)
python3 run.py --model deepseek  # DeepSeek       (key: DEEPSEEK_API_KEY)
python3 run.py --model zhipu     # 智谱 GLM       (key: ZHIPU_API_KEY)
python3 run.py --model kimi      # Kimi/Moonshot  (key: MOONSHOT_API_KEY)
python3 run.py --model openai    # OpenAI         (key: LAW_BENCH_OPENAI_KEY)
#    以上任一命令都会同时跑 random + always-first 基线作对照，统一写四个文件。
#    key 也可统一用 --api-key 传入，或用通用环境变量 LAW_BENCH_API_KEY。
#    指定具体模型（覆盖厂商默认）：python3 run.py --model qwen --model-name qwen-max
```

要求 Python ≥ 3.8（`python -S` 亦可，无任何第三方依赖；真实模型适配器仅在显式 `--model <provider>` 时懒加载 `requests`）。

## 当前哑基线结果（证明基准可区分好坏）

> 下列为 `run.py --baseline all` 在 `smoke_500.jsonl` 上的确定性结果（复跑一致）。

| model | overall | T1 | T2(recall@5) | T3(acc) | T3(macro_f1) |
|-------|--------:|---:|-------------:|--------:|-------------:|
| random-baseline | 0.072 | 0.035 | 0.000 | 0.290 | 0.210 |
| always-first-baseline | 0.083 | 0.042 | 0.000 | 0.330 | 0.165 |

哑基线接近随机水平（T2 检索几乎全错、T3 靠猜），说明基准**对噪声模型有区分度**——真实法律模型应显著高于此。`leaderboard.md` / `leaderboard.html` 另含**难度分层（易/中/难）与任务×难度矩阵**，便于展示"模型在哪类题上失分"。

**难度判定**：T1/T2 按条文长度分易/中/难；T3 命中=易、篡改=中、未命中（超范围引证）=难。

## 目录结构

```
law_citation_bench/
  common.py            # KB 加载 + 法律名映射（真值来源 = ../modules）
  build_dataset.py     # M0：模板法从 KB 生成 500 题（离线、可复现）
  score.py             # 字符级F1 / Recall@5 / MRR / Macro-F1，纯 stdlib
  report.py            # M3：leaderboard.json -> Markdown / HTML 报告
  run.py               # 编排：dataset→adapter→score→leaderboard.{csv,json,md,html}
  adapters/
    base.py            # ModelAdapter 接口（generate(prompt)->str）
    dummy.py           # 校准基线：random / always-first
    openai_stub.py     # M2：真实 API 适配器（OpenAI 兼容；预设 qwen/deepseek/zhipu/kimi/openai，懒加载 requests）
  dataset/
    smoke_500.jsonl    # 生成的评测集
    smoke_500.meta.json# 生成参数与统计（可复现凭证）
  leaderboard.csv      # 最近一次运行结果（扁平、机读）
  leaderboard.json     # 完整明细（含任务×难度矩阵）
  leaderboard.md       # M3 报告（Markdown，可贴 README/Notion）
  leaderboard.html     # M3 报告（HTML，单页可展示）
  README.md
```

## 设计约束（遵循 DD-007 离线教训）

- **零第三方依赖**：中文相似度默认字符级重叠，不引入 jieba / lxml。
- **真值一致性**：仅以 KB 中 `verified` 条文为真值，评测集自身不携带幻觉。
- **模型解耦**：适配器层隔离具体模型，评分逻辑与 API 无关；联网仅发生在「调用模型」，真值比对/评分/报告全离线。

## 下一步里程碑

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| M0 | 数据集生成 + 哑基线跑通 | ✅ 已实现 |
| M1 | `score.py` 正式版 + 难度分层评分 | ✅ 已实现 |
| M2 | 接入真实模型 API（OpenAI 兼容，预设 qwen/deepseek/zhipu/kimi/openai） | ✅ 已接线，自备 key 即出跑分 |
| M3 | 报告模板（Markdown/HTML）+ 难度分层可展示 leaderboard | ✅ 已实现 |

> 发布建议：未来可作为独立 repo `law-citation-bench` 发布（评测集与 KB 解耦），本仓库 README 互引。当前阶段以子目录形式落地以便复用 KB。
