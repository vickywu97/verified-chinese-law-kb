# law-citation-bench · 方向 A 评测基准（M0–M3）

> 一个**离线可跑、纯标准库、可量化模型法条引用能力**的评测基准。真值来自 [verified-chinese-law-kb](../)（2327 条逐字核验条文）的快照 `kb/kb_index.jsonl`，克隆即可独立运行，无需父仓库。
> 本目录是设计草图（`../docs/benchmark-design-A.md`）的落地实现：**M0** 可复现数据集、**M1** 哑基线跑通、**M3** 难度分层与 Markdown/HTML 报告均已就绪；**M2** 真实模型适配器已接线，用户自备 key 即可出跑分；现已抽为可独立发布的子包。

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
#    调大/调小单次请求超时：       python3 run.py --model kimi --timeout 300
#    网络抖动/拥堵时：             python3 run.py --model kimi --pace 0.3
#       （每两次 API 调用间 sleep 指定秒数；kimi 默认 0.3s 以缓解 Moonshot 端拥堵）
#    断点续跑（崩溃/超时/限流后不重头烧钱）：
#       python3 run.py --model kimi --save-preds preds/kimi__kimi-k2.6.jsonl --resume
#       单题 API 失败不再中断整轮：该题为空白预测、其余照常完成（结果仍计入评分）。
#       --resume 会跳过已有"有效预测"的 qid，但自动重跑"空白预测"（即记录的失败），
#       因此限流后无需手动过滤空行——反复执行同一条 --resume 直到无空白为止即可。
#    真实模型适配器对 429(限流)/5xx 会自动重试（尊重服务端 Retry-After，否则指数退避
#    5s→10s→20s…；kimi 预设 max_retries=8），4xx(鉴权/参数错误)不重试、立即报错。
#
# 说明：kimi/kimi-k2.6 默认开启「思维链（thinking）」，首 token 很慢易触发读超时；
#       仓库已默认对该模型发送 thinking=disabled 关掉推理，与其他基线模型对齐、也更省时。
#       其余厂商（qwen/deepseek/zhipu）默认不开启推理，无需处理。
```

## 多模型横评工作流（推荐）：先各自存预测，再离线合并

> 关键设计：**`--save-preds` 把每条预测落盘**；`--merge` 离线重算评分（始终用
> 当前 scorer）。这样——改了评分逻辑不必重新烧 API 额度；每个模型可在不同时间、
> 用各自 key 单独跑；最后一次性合并成完整 leaderboard。

```bash
# ① 每个模型单独跑一次，把原始预测存到 preds/（文件名里的 "/" 换成 "__"）
python3 run.py --model qwen     --save-preds preds/qwen__qwen-plus.jsonl
python3 run.py --model deepseek --save-preds preds/deepseek__deepseek-chat.jsonl
python3 run.py --model zhipu    --save-preds preds/zhipu__glm-4-flash.jsonl
python3 run.py --model kimi     --save-preds preds/kimi__kimi-k2.6.jsonl
#    （每次只调一个模型，省额度可加 --limit 50 先试跑）

# ② 离线合并 + 重算（不调任何 API、不需要 key），产出最终 leaderboard
python3 run.py --merge preds/qwen__qwen-plus.jsonl \
                      preds/deepseek__deepseek-chat.jsonl \
                      preds/zhipu__glm-4-flash.jsonl \
                      preds/kimi__kimi-k2.6.jsonl \
               --baseline all
#    -> leaderboard.csv / .json / .md / .html（含 4 模型 + 2 哑基线 + T3 分类明细）
```

`preds/*.jsonl` 已被仓库 `.gitignore` 忽略（可复现、含模型输出但不入库）。

### 离线重算验证（无需 key）
`--merge` 完全离线：从已存预测文件重算分数，所以哪怕之后修正了评分器（如 T3
解析 bug），也能直接重合并、不必重跑模型。CI 的 `tests/test_benchmark_smoke.py`
已覆盖 save-preds 往返与离线 merge 两条路径。

要求 Python ≥ 3.8（`python -S` 亦可，无任何第三方依赖；真实模型适配器仅在显式 `--model <provider>` 时懒加载 `requests`）。

## 当前结果（证明基准可区分好坏 + 已出首版真实跑分）

> 下列为 `run.py --baseline all --model qwen` 在 `smoke_500.jsonl` 上的结果（2026-08-10 实跑，修正 T3 解析后）。`leaderboard.md` / `leaderboard.html` 含完整难度分层与任务×难度矩阵。

| model | overall | T1 | T2(recall@5) | T3(acc) | T3(macro_f1) |
|-------|--------:|---:|-------------:|--------:|-------------:|
| random-baseline | 0.066 | 0.035 | 0.000 | 0.260 | 0.253 |
| **qwen/qwen-plus** | **0.433** | **0.287** | **0.620** | **0.350** | 0.276 |

**读解（首版真实跑分的信号价值）：**
- **T2 检索最强**（recall@5=0.620，MRR=0.514）：Qwen 在 top-5 中找回正确条文的概率约 62%，远超随机（0），说明其法条检索/定位能力真实存在。
- **T1 接地中等**（0.287）：能给出正确 law+article 与关键句，但字符级精确匹配偏难。
- **T3 幻觉识别≈随机但暴露具体弱点**：整体 0.350，仅略高于多数类基线（0.34）。难度分层揭示——`篡改`=0.735（强）、`命中`=0.303（略低于随机）、`未命中`=**0.000**（通义千问对"超范围引证"几乎从不判为未命中）。这正是评测集"量化 AI 质量"的价值：锁定模型在哪类失分。

哑基线接近随机水平（T2 检索几乎全错、T3 靠猜），说明基准**对噪声模型有区分度**。难度分层（易/中/难）与任务×难度矩阵便于展示"模型在哪类题上失分"。

**难度判定**：T1/T2 按条文长度分易/中/难；T3 命中=易、篡改=中、未命中（超范围引证）=难。

## 目录结构

```
law-citation-bench/                 # 自包含、可独立发布
  common.py            # 加载 kb/kb_index.jsonl（快照真值）+ 法律名映射
  build_dataset.py     # M0：模板法从 KB 生成 500 题（离线、可复现）
  score.py             # 字符级F1 / Recall@5 / MRR / Macro-F1，纯 stdlib
  report.py            # M3：leaderboard.json -> Markdown / HTML 报告
  run.py               # 编排：dataset→adapter→score→leaderboard.{csv,json,md,html}
  adapters/
    base.py            # ModelAdapter 接口（generate(prompt)->str）
    dummy.py           # 校准基线：random / always-first
    openai_stub.py     # M2：真实 API 适配器（OpenAI 兼容；预设 qwen/deepseek/zhipu/kimi/openai，懒加载 requests）
  kb/
    kb_index.jsonl     # 快照 2327 条核验条文（真值；使基准离线自包含）
  dataset/
    smoke_500.jsonl    # 生成的评测集
    smoke_500.meta.json# 生成参数与统计（可复现凭证）
  tools/
    vendor_kb_index.py # 从该 KB 的 modules/ 刷新 kb/kb_index.jsonl
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

## 独立发布（与 KB 解耦）

本目录已**自包含**：`kb/kb_index.jsonl` 快照了 2327 条核验条文作为真值，克隆后离线即可跑哑基线、评分、出报告，无需父仓库 `modules/`。要作为独立 repo 发布：

```bash
# 在仓库根目录把本目录整体拷出（保留历史可用 git subtree split）
cp -r law-citation-bench /path/to/new/law-citation-bench
cd /path/to/new/law-citation-bench
git init && git add -A && git commit -m "law-citation-bench: standalone eval repo"
# 刷新真值快照（可选，需能访问 verified-chinese-law-kb 的 modules/）：
python3 tools/vendor_kb_index.py --modules /path/to/kb/modules
```

## T3 提示词迭代（v1 → v2）

v1 跑分暴露一个真实弱点：**所有模型在 T3「未命中」（超范围/不存在条文号引用）上几乎全 0**。根因是 v1 提示词没给模型任何"该法条有多少条"的参考，模型无从判断所引条文号是否真实存在。

`--prompt-version v2`（默认）在 T3 提示词中补入**各法现行条文总数**（公开法律信息，非泄漏答案），让模型能完成"条文号是否越界"这一范围核验；`命中`/`篡改` 仍需比对条文**内容**（基准不提供），因此并未被轻易解决——改进是**精准针对盲区**。

```bash
python3 run.py --model qwen --prompt-version v2 --save-preds preds/qwen__qwen-plus__v2.jsonl
python3 run.py --merge preds/*__v2.jsonl --baseline all   # 离线重算，对比 v1/v2 提升
```

> 评分器与提示词版本无关：`--merge` 始终用当前 scorer 重算，改提示词不必重烧额度、且 v1/v2 预测可同台对比。
