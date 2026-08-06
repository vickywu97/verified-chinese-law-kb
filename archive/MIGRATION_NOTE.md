# archive/ — 历史迁移说明

本目录用于存放知识库构建 / 迁移过程中的历史归档文件（如旧版 SEED、已发布模块的打包快照等）。

## 初始迁移来源

本仓库 M1 模块的 27 条民法典数据，初版取自 companion benchmark 项目
`legal-hallucination-bench` 的已核验子集（`knowledge_base/laws/statutes.jsonl`，
筛选 `law_code == CIVIL_CODE`），并经执业律师复核。后续模块的 SEED 与构建产物可归档于此，
但**不应将未核验或重复的条文数据长期置于本目录**——一切对外发布的真值以 `modules/` 为准。

## 约定

- 发布的模块打包快照命名：`<模块编号>.tar.gz`（与 Release 资产一致），下载后可放于此临时存放。
- 迁移 / 重建脚本的临时产物以 `*.tmp` 结尾，已被 `.gitignore` 忽略，不纳入版本控制。
