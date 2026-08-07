# 变更日志 / Changelog

本文件记录仓库整体的重大变更。各模块的独立变更见其目录下的 `CHANGELOG.md`。

## [1.0.0] — 2026-08-07

### 初始发布
- 建立仓库骨架：README、LICENSE（MIT）、LICENSE-DATA（CC BY-SA 4.0）、catalog.json、CI 工作流。
- 发布 **M1 民法典**模块首批 **27 条**逐字核验条文（`verification_status=verified`），全部由 Vicky Wu 具名签署。
- 提供工具链（纯标准库，无第三方依赖）：
  - `tools/build_statute.py`：从 SEED 构建 `statutes.jsonl` 与 `verifications.json` 脚手架。
  - `tools/verify_kb.py`：交互式逐条核验 / 覆盖率报告 / 可信批量签发。
  - `tools/download_module.py`：模块下载 CLI（支持离线本地归档）。
  - `tools/validate_module.py`：模块完整性校验（CI 调用）。
- 单元测试：`tests/test_kb_integrity.py`、`tests/test_module_structure.py`。
- 知识库索引：`knowledge_base/laws_index.json`（8 部法律元数据）、`knowledge_base/deprecated_laws.json`（失效 / 被吸收法律名称陷阱）。

### 模块扩展（同日内追加）
- **M3 公司法**（2023 修订，16 条，partial）：仅保留已核验原文，自本模块起默认省略具名签署字段 `verified_by`。
- **M4 税收征收管理法**（2015-04-24，94 条，complete）。
- **M5 增值税法**（2026-01-01 施行，38 条，complete）。
- **M6 企业所得税法**（2018-12-29 修正，60 条，complete）。
- **M7 个人所得税法**（2019-01-01 修正，22 条，complete）。
- **M8 专利法**（2021-06-01 施行，82 条，complete）。
- 新增 SEED 源：`knowledge_base/SEED/`（各模块构建所用的核验子集 JSON）。

### 规划中
- M2 刑法（CRIMINAL_LAW，27 条）等。新增模块后会在 `catalog.json` 追加条目并发布对应 Release。
