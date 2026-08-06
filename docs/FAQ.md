# 常见问题 / FAQ

### Q1：这个知识库和直接爬法条有什么不同？
区别在「**核验**」。爬来的法条只是文本，没有版本、没有签署、没有真值保证。本库每条文都经执业律师逐字比对官方来源并具名签署，带生效日期与版本关系，可直接作为 RAG 真值或评测 ground truth。

### Q2：数据可以商用吗？
可以。代码按 MIT 许可，数据按 **CC BY-SA 4.0** 许可——商用允许，但须**署名**并**相同方式共享**（你的演绎成果也须以 CC BY-SA 4.0 发布）。关键法律事项仍须核对官方原文。

### Q3：为什么 M1 只有 27 条，而不是民法典全部 1260 条？
本库**质量优先于覆盖**。未逐字核验的条文不会标记为 `verified`，也不会随 Release 发布。M1 首批 27 条是已核验子集；全量核验按路线图推进（详见方案文档与 `catalog.json`）。

### Q4：如何只用某一个模块，而不拉取整库？
每个模块是独立目录，可单独下载：
```bash
python -S tools/download_module.py get --module M1
```
也可直接到 GitHub Releases 下载对应 `<模块编号>.tar.gz`。

### Q5：工具需要安装第三方依赖吗？
不需要。所有 `tools/` 脚本与 `tests/` 仅依赖 **Python 标准库**，可在 `python -S`（禁用 site-packages）下运行，CI 即以此方式验证离线可重现。

### Q6：如何新增一部法律的模块？
按 `docs/MODULE_SPEC.md` 与方案文档 SOP：准备 SEED → `build_statute.py` → `validate_module.py` → `verify_kb.py` 逐条核验 → 测试 → 提交 → 发布 Release → 更新 `catalog.json`。

### Q7：发现某条核验有误怎么办？
在 GitHub 提 issue（选 *Bug report* 或 *New module request*），或直接 PR 修正 SEED 并重新核验；更正会记入模块 `CHANGELOG.md` 与台账。

### Q8：什么是「失效法名称陷阱」？
指被吸收或废止但仍常被引用的法律名称（如《合同法》《增值税暂行条例》）。`knowledge_base/deprecated_laws.json` 列出这些名称并指向现行法，用于拦截模型 / 检索中的旧法幻觉。
