# M3 · 中华人民共和国公司法（2023 修订）

> 模块化法条知识库子模块。**每一条条文均为已核验原文**，来源为官方公报，未附加具名签署。

## 法律基本信息

| 项目 | 内容 |
|------|------|
| 法律名称 | 中华人民共和国公司法 |
| 修订版本 | 2023 年修订（第十四届全国人大常委会第七次会议修订） |
| 施行日期 | 2024-07-01 |
| 法条总数 | 266 条 |
| 本模块已核验 | 16 条（partial） |
| law_code | `COMPANY_LAW` |

## 条文统计

本模块收录 16 条已核验条文，覆盖：

```
第3条、第4条、第10条、第15条、第20条、第21条、第23条、第27条、
第34条、第35条、第49条、第57条、第63条、第84条、第113条、第142条
```

`verification_status` 均为 `verified`。完整条文以 `statutes.jsonl` 为准。

## 数据格式

`statutes.jsonl` 每行一个 JSON 对象，字段如下（**已省略具名签署字段 `verified_by`**）：

| 字段 | 说明 |
|------|------|
| `id` | 条文唯一 ID，格式 `{law_code}_{sort_key}_v{version}` |
| `law_code` | 法律代码，本模块为 `COMPANY_LAW` |
| `article_number` | 条文编号（中文，如 `第3条`） |
| `article_sort_key` | 条文排序键（整数） |
| `content` | 条文原文（已核验） |
| `effective_date` | 施行日期 `2024-07-01` |
| `revision_of` | 修订自（无则为 `null`） |
| `verification_status` | `verified` |
| `verified_at` | 核验日期（ISO） |
| `source_url` | 官方来源链接 |
| `source_accessed_at` | 源访问日期 |
| `notes` | 备注（如修订要点） |

配套 `verifications.json` 以条文 ID 为键，记录 `status` / `verified_at` / `source` / `notes`，不含署名。

## 核验说明

- 条文原文逐条比对官方公报（全国人民代表大会公报 / 官方法律法规数据库），核验状态为 `verified`。
- 本模块遵循仓库统一约定：**数据仅保留已核验原文，不附加具名签署**。

## 已知局限

- 本模块为 **部分（partial）** 发布：仅含 16 条高频引用条文，非 2023 修订版全文（266 条）。
- 如需全量，请在 Issue 提议或参考 `docs/CONTRIBUTING.md` 提交补充。
