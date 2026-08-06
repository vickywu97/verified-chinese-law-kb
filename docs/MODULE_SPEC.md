# 模块规范 / Module Specification

每个模块对应**一部法律**，目录约定为 `modules/{模块编号}_{名称}/`。

---

## 1. 目录结构（必需文件）

```
modules/M3_company_law/
├── README.md          # 法律简介、条文统计、数据格式、核验说明、已知局限
├── statutes.jsonl     # 法条数据，每行一条（13 字段）
├── verifications.json # 以条文 id 为键的核验台账
└── CHANGELOG.md       # 该模块独立变更日志
```

CI 通过 `validate_module.py` 强制校验上述 4 个文件均存在。

## 2. 模块编号与命名

- 编号：`M1` 民法典、`M3` 公司法、`M4` 税法、`M5` 专利法（保留 M2 以备预留）。
- 目录名：`{编号}_{法律简称英文或拼音}`，如 `M1_civil_code`、`M3_company_law`。
- `law_code`：全局唯一代码，见 `knowledge_base/laws_index.json`（如 `CIVIL_CODE`、`COMPANY_LAW`）。

## 3. statutes.jsonl 字段（13 字段，逐字保留）

| 字段 | 类型 | 约束 |
|------|------|------|
| `id` | string | 唯一，`{law_code}_{sort_key}_v{n}` |
| `law_code` | string | 须存在于 laws_index |
| `article_number` | string | 条文编号原文 |
| `article_sort_key` | integer | 排序用，必须为整数 |
| `content` | string | 正文，逐字核验 |
| `effective_date` | string | ISO `YYYY-MM-DD` |
| `revision_of` | string \| null | 替代的旧版本 id，否则 null |
| `verification_status` | string | `verified` / `rejected` / `pending` |
| `verified_by` | string | 签署人（verified 时必填） |
| `verified_at` | string | 核验日期 ISO |
| `source_url` | string | 官方来源 URL |
| `source_accessed_at` | string | 来源访问日期 ISO |
| `notes` | string | 备注 / 主题标签 |

## 4. verifications.json 结构

以条文 `id` 为键：

```json
{
  "COMPANY_LAW_1_v1": {
    "status": "verified",
    "verified_by": "Vicky Wu (律师/税务师/专利代理师)",
    "source": "全国人民代表大会常务委员会公报",
    "verified_at": "2026-08-07",
    "notes": "立法目的"
  }
}
```

约束：台账键集合必须是 `statutes.jsonl` 中 id 集合的**子集**（不允许孤立台账）；每条文必须有一条台账。

## 5. Release 与下载约定

- 每个发布模块对应一个 Release 标签：`v{主版本}.{次版本}.{修订}-M{编号}`，如 `v1.0.0-M1`。
- Release 资产命名：`<模块编号>.tar.gz`（如 `M1.tar.gz`），内为对应模块目录内容。
- `catalog.json` 中 `download_url` 指向该 Release 标签页，`tools/download_module.py` 据此推导资产地址。

## 6. 新增模块 SOP（摘要）

详见方案文档「启动第一批模块（M3 公司法）的完整 SOP」：

1. 解析官方文档为 SEED（`knowledge_base/SEED/<law>.json`）。
2. `build_statute.py --seed ... --out .../statutes.jsonl` 生成条文与台账脚手架。
3. `validate_module.py --module <dir>` 校验结构。
4. `verify_kb.py review --module <dir>` 逐条核验（或 `batch` 可信批量签发）。
5. 跑测试 + 提交 + 推送 + 发布 Release。
6. 在 `catalog.json` 追加模块条目。
