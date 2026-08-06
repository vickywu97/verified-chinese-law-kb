# 产品规格书 / Product Specification

**产品**：《中国法·已核验》模块化法条知识库
**仓库**：`verified-chinese-law-kb`
**版本**：v1.0.0（2026-08-07）

---

## 1. 产品定位

一份**每一条条文都经执业律师逐字比对官方来源并具名签署**的中国法律模块化知识库。
核心差异化不是「覆盖多少部法律」，而是**可追责的真值**：每条文都能追到签署人、来源与日期。

目标用户：

- 法律 AI / LLM 团队：作为 RAG 检索语料或评测真值（ground truth）；
- 合规 / 法务 SaaS：作为可审计的法条数据源；
- 研究者：研究法律大模型幻觉、构建 benchmark 的已核验基底。

## 2. 非目标（明确不做）

- 不做法律咨询 / 法律意见（本库是数据，不是建议）。
- 不做法规的二次解读或摘要改写（保持原文逐字，避免引入偏差）。
- 不追求「全量覆盖」优先——**核验质量优先于覆盖数量**，未核验条文不发布。

## 3. 核心概念

| 概念 | 说明 |
|------|------|
| 模块（Module） | 一部法律一个目录 `modules/{id}_{名称}/`，可独立下载与发布。 |
| 条文（Statute） | `statutes.jsonl` 中的一行，13 字段标准对象。 |
| 版本轴（Version） | 通过 `effective_date` + `revision_of` 表达条文生效与替代关系。 |
| 核验台账（Verification） | `verifications.json` 中以条文 id 为键的签署记录。 |
| 目录索引（Catalog） | 仓库根 `catalog.json`，列出已发布模块及状态。 |
| 法律元数据（Law Index） | `knowledge_base/laws_index.json`，法律级元数据（制定机关、生效日等）。 |
| 失效法陷阱（Deprecated） | `knowledge_base/deprecated_laws.json`，标注重名 / 旧法以免幻觉。 |

## 4. 质量门禁

- 任何标记为 `verified` 的条文必须：逐字比对官方来源 + 具名签署 + 记录来源与日期。
- CI（`python -S tools/validate_module.py --all`）必须零错误通过。
- 发布 Release 的模块不允许存在 `pending` / `rejected` 条文（严格模式）。

## 5. 扩展模型

新增模块 = 在 `catalog.json` 追加一条 + 在 `modules/` 新增目录 + 发布对应 Release 标签。
详见 [MODULE_SPEC.md](MODULE_SPEC.md) 与方案文档「模块扩展计划」。

## 6. 许可与署名

- 代码 MIT，数据 CC BY-SA 4.0（见仓库根 `LICENSE` 与 `LICENSE-DATA`）。
- 数据使用须署名：来源《中国法·已核验》、作者 Vicky Wu、许可链接 CC BY-SA 4.0。
