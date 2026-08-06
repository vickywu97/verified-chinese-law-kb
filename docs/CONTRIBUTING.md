# 贡献指南 / Contributing

感谢参与《中国法·已核验》知识库。本库的核心资产是「**已核验的真值**」，因此贡献门槛集中在**核验质量**而非代码。

---

## 1. 谁能签署核验？

- 条文标记为 `verified` 前，必须由具备相应资质的签署人（律师 / 税务师 / 专利代理师等）逐字比对官方来源。
- 不具备资质的贡献者可参与：SEED 整理、工具改进、文档、Issue 反馈，但**不得自行将条文标记为 `verified`**。

## 2. 贡献一个模块（或扩展现有模块）

1. Fork 并克隆仓库。
2. 准备 SEED：`knowledge_base/SEED/<law>.json`（JSON 数组，字段见 `docs/MODULE_SPEC.md`）。
3. 生成条文：
   ```bash
   python -S tools/build_statute.py --seed knowledge_base/SEED/<law>.json \
                                    --out modules/Mx_<name>/statutes.jsonl
   ```
4. 校验结构：`python -S tools/validate_module.py --module Mx_<name>`。
5. 逐条核验：`python -S tools/verify_kb.py review --module Mx_<name>`。
6. 跑测试：`python -S -m unittest discover -s tests -t .`。
7. 提交 PR，说明核验人、来源与覆盖条数。

## 3. 代码 / 工具贡献

- 工具必须保持**纯标准库**，不引入第三方依赖（确保 `python -S` 可运行）。
- 提交前确保 `validate_module.py --all` 与单元测试通过。
- 遵循现有文件命名与 JSON 字段约定，切勿擅自更改 13 字段 schema。

## 4. 提交规范

- 提交信息建议前缀：`feat(Mx)` / `fix` / `docs` / `chore`。
- 示例：`feat(M3): add full Company Law (2023) module, 266 articles verified`。

## 5. 许可

- 贡献的代码依 MIT 许可；贡献的数据依 CC BY-SA 4.0 许可，须同意署名与相同方式共享。

## 6. 行为准则

- 不提交未经核验即标记为 `verified` 的条文。
- 不提交可能侵犯第三方著作权或未授权的内容。
- 对失效 / 修订法律保持敏感，及时更新 `deprecated_laws.json`。
