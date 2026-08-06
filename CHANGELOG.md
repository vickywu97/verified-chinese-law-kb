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

### 规划中
- M3 公司法（2023 修订）、M4 税法、M5 专利法（详见方案文档与 `docs/`）。
