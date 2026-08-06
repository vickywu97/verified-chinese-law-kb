#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_module_structure.py — 校验仓库 / 模块结构约定（纯标准库）。

覆盖：
  - 顶层必需文件存在（README.md / LICENSE / catalog.json 等）
  - catalog.json 合法，且其模块条目与 modules/ 目录一致
  - 每个模块目录含 4 个必需文件
  - knowledge_base/laws_index.json 与 deprecated_laws.json 结构合法
"""
import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(REPO_ROOT, "modules")
KB_DIR = os.path.join(REPO_ROOT, "knowledge_base")
MODULE_REQUIRED = ["statutes.jsonl", "verifications.json", "README.md", "CHANGELOG.md"]


def discover_module_dirs():
    out = []
    if not os.path.isdir(MODULES_DIR):
        return out
    for d in sorted(os.listdir(MODULES_DIR)):
        full = os.path.join(MODULES_DIR, d)
        if os.path.isdir(full) and os.path.isfile(os.path.join(full, "statutes.jsonl")):
            out.append(d)
    return out


class TestRepoStructure(unittest.TestCase):
    def test_top_level_files(self):
        for fn in ["README.md", "LICENSE", "LICENSE-DATA", "catalog.json",
                   "CHANGELOG.md", ".gitignore"]:
            self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, fn)),
                            f"缺少顶层文件: {fn}")

    def test_catalog_consistency(self):
        with open(os.path.join(REPO_ROOT, "catalog.json"), "r", encoding="utf-8") as f:
            cat = json.load(f)
        self.assertIn("version", cat)
        self.assertIn("modules", cat)
        self.assertIsInstance(cat["modules"], list)
        ids = [m["id"] for m in cat["modules"]]
        self.assertEqual(len(ids), len(set(ids)), "catalog 模块 id 重复")

        dirs = discover_module_dirs()
        # 每个目录应能被某个 catalog id 前缀匹配
        for d in dirs:
            matched = any(d.startswith(f"{mid}_") for mid in ids)
            self.assertTrue(matched, f"模块目录 {d} 在 catalog 中无对应 id")
        # 每个 catalog 模块应有对应目录
        for mid in ids:
            matched = any(d.startswith(f"{mid}_") for d in dirs)
            self.assertTrue(matched, f"catalog 模块 {mid} 无对应目录")


class TestModuleDirectories(unittest.TestCase):
    def test_required_files(self):
        for d in discover_module_dirs():
            for fn in MODULE_REQUIRED:
                self.assertTrue(
                    os.path.isfile(os.path.join(MODULES_DIR, d, fn)),
                    f"模块 {d} 缺文件: {fn}")


class TestKnowledgeBase(unittest.TestCase):
    def test_laws_index(self):
        path = os.path.join(KB_DIR, "laws_index.json")
        self.assertTrue(os.path.isfile(path), "缺少 laws_index.json")
        with open(path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        self.assertIsInstance(idx, dict)
        for code, meta in idx.items():
            for k in ("name", "issuing_authority", "status",
                      "effective_date", "source_url"):
                self.assertIn(k, meta, f"laws_index[{code}] 缺 {k}")
            self.assertIn(meta["status"], {"effective", "repealed", "superseded"})

    def test_deprecated_laws(self):
        path = os.path.join(KB_DIR, "deprecated_laws.json")
        self.assertTrue(os.path.isfile(path), "缺少 deprecated_laws.json")
        with open(path, "r", encoding="utf-8") as f:
            dep = json.load(f)
        self.assertIn("entries", dep)
        self.assertIsInstance(dep["entries"], list)
        for e in dep["entries"]:
            for k in ("name", "type", "replaced_by_name"):
                self.assertIn(k, e, f"deprecated 条目缺 {k}: {e.get('name')}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
