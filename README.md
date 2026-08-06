# 《中国法·已核验》模块化法条知识库 · verified-chinese-law-kb

> 每一条条文均经执业律师逐字比对官方来源并具名签署的、带版本轴的、可独立下载的中国法律模块化知识库。
>
> A modular, versioned, downloadable Chinese statute knowledge base in which every article is line-by-line verified against the official source and signed by a practicing attorney.

---

## 1. 一句话定位

**中文**：不是又一个「爬下来的法条 dump」——而是每一条都带律师签名、带生效版本、可单独下载、直接喂给 RAG 的中国法律真值库。

**English**: Not another scraped statute dump — a signed, version-pinned, individually downloadable source of truth for Chinese law, ready to feed into RAG pipelines.

---

## 2. 为什么需要这个知识库

当前主流法律 AI 在「基础法条引用」这一最不该出错的环节上集体失灵。在 companion benchmark
[legal-hallucination-bench](https://github.com/vickywu97/legal-hallucination-bench)（如其尚未公开，请替换为实际地址）的实测中：

- 5 个主流法律 / 通用大模型在基础法条引用任务上的 **幻觉率（HVI）介于 50%–64.6%**；
- 其中 **增值税法域正确率为 0%** —— 模型几乎无法正确引用生效法条。

根因不是模型不够聪明，而是**缺少一份「已核验、带版本、结构化」的中文法条真值数据**：模型只能依赖训练记忆或不可靠的检索，而法律条文随修订、废止频繁变化，一处版本错位就是一处幻觉。

本项目提供的解法：**执业律师逐字核验 + 具名签署 + 版本轴 + 模块化下载**，让下游系统拿到的是「可追责的真值」，而不是「看起来像法条的文本」。

---

## 3. 核心卖点

| 卖点 | 说明 |
|------|------|
| **已核验（Verified）** | 每条文均由执业律师（律师 / 税务师 / 专利代理师）逐字比对官方来源，并在 `verifications.json` 中具名签署、标注来源与日期。 |
| **带版本轴（Versioned）** | 每条文带 `effective_date` 与 `revision_of`，可区分不同生效版本，避免「旧法当新法」式幻觉。 |
| **模块化（Modular）** | 按法律拆分独立模块（`modules/M1_civil_code/` 等），可单独下载、单独发布 Release，**无需整库拉取**。 |
| **RAG-ready** | 标准 JSONL 一行一条，字段稳定、UTF-8、无外部依赖，直接切片嵌入或加载进向量库。 |
| **可追责（Accountable）** | 核验人、来源、核验日期全部留痕；`knowledge_base/deprecated_laws.json` 额外标注「失效 / 被吸收」法律名称陷阱。 |

---

## 4. 快速开始

### 4.1 用 CLI 下载某个模块

```bash
# 查看可下载模块
python -S tools/download_module.py list

# 下载并解包 M1（民法典）到 modules/
python -S tools/download_module.py get --module M1
```

> 下载依赖 GitHub Releases 资产约定：每个 Release 标签附带 `<module_id>.tar.gz`。
> 离线环境可用 `python -S tools/download_module.py get --module M1 --from-local <本地归档>`。

### 4.2 直接加载 JSONL（Python）

```python
import json

articles = []
with open("modules/M1_civil_code/statutes.jsonl", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            articles.append(json.loads(line))

print(len(articles), "条民法典条文已加载")
```

### 4.3 本地校验

```bash
python -S -m unittest discover -s tests -t .     # 跑测试
python -S tools/validate_module.py --all         # 校验所有模块完整性
```

---

## 5. 模块目录

| 模块 ID | 法律 | law_code | 状态 | 已核验 / 总条数 | 价格 |
|---------|------|----------|------|-----------------|------|
| **M1** | 民法典 | `CIVIL_CODE` | partial（首批 27 条） | 27 / 1260 | 免费 |

**规划中（按 4 周路线）**：M3 公司法（2023 修订，266 条）、M4 税法（税收征管法 + 企业所得税法 + 个人所得税法 + 增值税法）、M5 专利法（82 条）。新增模块后会在 `catalog.json` 追加条目并发布对应 Release。

---

## 6. 数据格式

`modules/{模块}/statutes.jsonl`：**每行一个 JSON 对象**，完全沿用 companion benchmark 的 schema（13 个字段）：

```json
{
  "id": "CIVIL_CODE_584_v1",
  "law_code": "CIVIL_CODE",
  "article_number": "第五百八十四条",
  "article_sort_key": 584,
  "content": "当事人一方不履行合同义务……",
  "effective_date": "2021-01-01",
  "revision_of": null,
  "verification_status": "verified",
  "verified_by": "Vicky Wu (律师/税务师/专利代理师)",
  "verified_at": "2026-08-01",
  "source_url": "https://flk.npc.gov.cn/...",
  "source_accessed_at": "2026-07-31",
  "notes": "违约责任损害赔偿范围"
}
```

字段说明：

| 字段 | 含义 |
|------|------|
| `id` | 全局唯一：`{law_code}_{article_sort_key}_v{n}` |
| `law_code` | 法律代码，见 `knowledge_base/laws_index.json` |
| `article_number` | 条文编号原文（如「第五百八十四条」） |
| `article_sort_key` | 用于排序的整数序号 |
| `content` | 条文正文（逐字核验） |
| `effective_date` | 生效日期（ISO `YYYY-MM-DD`） |
| `revision_of` | 若为新版替代旧版，填被替代版本 id；否则 `null` |
| `verification_status` | `verified` / `rejected` / `pending` |
| `verified_by` | 具名签署人 |
| `verified_at` | 核验日期 |
| `source_url` | 官方来源（全国人大公报 / 政府网） |
| `source_accessed_at` | 来源访问日期 |
| `notes` | 备注（如主题标签、差异说明） |

配套的 `verifications.json` 以条文 `id` 为键保存核验台账：

```json
{
  "CIVIL_CODE_584_v1": {
    "status": "verified",
    "verified_by": "Vicky Wu (律师/税务师/专利代理师)",
    "source": "全国人民代表大会公报",
    "verified_at": "2026-08-01",
    "notes": "违约责任损害赔偿范围"
  }
}
```

---

## 7. 核验体系

### 7.1 核验标准（摘要）

1. **逐字比对**：正文须与官方来源（全国人大公报 `flk.npc.gov.cn` 或政府网）逐字一致，标点、数字、条文序号均不得有误。
2. **版本核对**：记录 `effective_date` 与 `revision_of`，确认引用的是**现行生效版本**，而非已修订 / 已废止的旧法。
3. **失效法识别**：对照 `knowledge_base/deprecated_laws.json`，凡涉及被吸收（如原《合同法》已被《民法典》吸收）或已废止（如《增值税暂行条例》已被《增值税法》取代）的法律名称，须显式标注。
4. **具名签署**：每条 `verified` 条文必须在 `verifications.json` 中由具名签署人留痕，含来源与日期。

完整标准见 [docs/VERIFICATION_STANDARD.md](docs/VERIFICATION_STANDARD.md)。

### 7.2 核验人签名

首批 M1 模块全部 27 条均由 **Vicky Wu（律师 / 税务师 / 专利代理师）** 逐字核验并具名签署，核验日期 2026-08-01。

---

## 8. 许可证

- **代码**（脚本、工具、测试、文档模板）：[MIT](LICENSE)
- **数据**（法条、核验台账、派生索引）：[CC BY-SA 4.0](LICENSE-DATA)

使用数据请按 CC BY-SA 4.0 要求署名并相同方式共享；关键法律事项仍须核对官方原文。

---

## 9. 相关项目

- **[legal-hallucination-bench](https://github.com/vickywu97/legal-hallucination-bench)**（如其尚未公开，请替换为实际地址）：本知识库的 companion benchmark——用真实模型排行榜证明主流法律 AI 在基础法条引用任务上的失败，并为「已核验真值数据」的必要性提供量化证据。本仓库的 M1 数据即取自该 benchmark 的已核验子集。

---

<p align="center">由执业律师逐字核验 · 带版本轴 · 可独立下载 · RAG-ready</p>
