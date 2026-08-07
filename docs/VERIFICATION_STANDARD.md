# 核验标准 / Verification Standard

本标准是「已核验」承诺的准绳。**任何 `verification_status=verified` 的条文都必须满足以下全部条目。**

---

## 1. 适用范围

- 适用于每一条进入 `statutes.jsonl` 且标记为 `verified` 的条文。
- 核验人须具备相应执业资质（本项目首批由律师 / 税务师 / 专利代理师签署）。

## 2. 核验四步法

### 2.1 逐字比对（Word-for-word）
- 正文须与**官方来源原文**逐字一致：汉字、数字、标点、条文序号、款项目号均不得增减或改动。
- 官方来源优先级：`flk.npc.gov.cn`（全国人大公报）> 国务院 / 部委政府网 > 其他官方转载。
- 记录 `source_url` 与 `source_accessed_at`。

### 2.2 版本核对（Version check）
- 确认引用的是**现行生效版本**，核对 `effective_date`。
- 若条目替代了旧版本，填写 `revision_of`（被替代版本 id）；否则为 `null`。
- 对照 `knowledge_base/deprecated_laws.json`，拦截「旧法当新法」。

### 2.3 失效法识别（Deprecated detection）
- 凡条文涉及已被吸收（如《合同法》→《民法典》合同编）或已废止（如《增值税暂行条例》→《增值税法》）的法律，须在 `notes` 或台账中显式标注，避免下游误用旧名。
- `deprecated_laws.json` 是防幻觉的「名称陷阱」清单，随法律修订持续更新。

### 2.4 核验留痕（Attestation ledger）
- 在 `verifications.json` 中为每条 `verified` 条文写入：
  - `status`: `verified`
  - `verified_at`: 核验日期（ISO）
  - `source`: 来源出版物 / 网站
  - `notes`: 主题标签或差异说明
- **具名签署（`verified_by`）为可选**：M1 含签署人留痕；自 M3 起默认省略，数据仅保留「已核验原文」。`validate_module.py` 对 `verified_by` / `verified_at` 均为可选校验。

## 3. 状态机

```
        build_statute (verified=false)
                 │
                 ▼
   pending ──verify_kb review──► verified
        │                         │
        └──── verify_kb reject ──► rejected
```

- `pending`：尚未核验（不得随 Release 发布）。
- `verified`：通过四步法核验。
- `rejected`：比对发现不一致，须在 `notes` 记录差异；需修正 SEED 后重新核验。

## 4. 复核与再审

- 当官方发布法律修订 / 修正案时，须对相关模块重新核验，并新增 `revision_of` 版本。
- 签署人变更或发现历史误签时，更新台账 `verified_at` 并记录于模块 `CHANGELOG.md`。

## 5. 责任声明

核验降低但**不排除**错误风险；关键法律事项使用方仍须核对官方公报原文。本库按「原样」提供，详见 `LICENSE-DATA`。
