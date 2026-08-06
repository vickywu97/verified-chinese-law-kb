#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_kb_integrity.py — 校验知识库数据完整性（纯标准库）。

覆盖：
  - 每条文 id 唯一且含全部标准字段
  - article_sort_key 为整数，effective_date 为 ISO 日期
  - 每条文在 verifications.json 中有对应条目，status 合法
  - verifications.json 无孤立键
  - M1 模块应有 27 条且全部 verified（初始基线）
"""
import json
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES_DIR = os.path.join(REPO_ROOT, "modules")

REQUIRED_FIELDS = [
    "id", "law_code", "article_number", "article_sort_key", "content",
    "effective_date", "revision_of", "verification_status", "verified_by",
    "verified_at", "source_url", "source_accessed_at", "notes",
]
VALID_STATUS = {"verified", "rejected", "pending"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def discover_modules():
    out = []
    if not os.path.isdir(MODULES_DIR):
        return out
    for d in sorted(os.listdir(MODULES_DIR)):
        full = os.path.join(MODULES_DIR, d)
        if os.path.isdir(full) and os.path.isfile(os.path.join(full, "statutes.jsonl")):
            out.append(full)
    return out


def load_statutes(module_dir):
    out = []
    with open(os.path.join(module_dir, "statutes.jsonl"), "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


class TestKBIntegrity(unittest.TestCase):
    def setUp(self):
        self.modules = discover_modules()
        self.assertGreater(len(self.modules), 0, "未发现任何模块目录")

    def test_every_module_has_statutes(self):
        self.assertGreater(len(self.modules), 0)

    def test_statute_schema_and_ledger(self):
        for mod in self.modules:
            name = os.path.basename(mod)
            statutes = load_statutes(mod)
            with open(os.path.join(mod, "verifications.json"), "r", encoding="utf-8") as f:
                ledger = json.load(f)

            ids = set()
            for o in statutes:
                for field in REQUIRED_FIELDS:
                    self.assertIn(field, o, f"{name}: {o.get('id')} 缺字段 {field}")
                rid = o["id"]
                self.assertNotIn(rid, ids, f"{name}: 重复 id {rid}")
                ids.add(rid)
                self.assertIsInstance(o["article_sort_key"], int,
                                     f"{name}: {rid} article_sort_key 非整数")
                self.assertTrue(ISO_DATE.match(str(o["effective_date"])),
                                f"{name}: {rid} effective_date 非法")
                self.assertIn(o["verification_status"], VALID_STATUS,
                              f"{name}: {rid} status 非法")
                # 每条文必须有台账
                self.assertIn(rid, ledger, f"{name}: {rid} 无核验台账")

            # 台账无孤立键
            for key in ledger:
                self.assertIn(key, ids, f"{name}: 台账含孤立键 {key}")
                self.assertIn(ledger[key].get("status"), VALID_STATUS,
                              f"{name}: {key} 台账 status 非法")


class TestM1Baseline(unittest.TestCase):
    """初始基线：M1 民法典应有 27 条且全部 verified。"""
    def test_m1_count_and_verified(self):
        m1 = os.path.join(MODULES_DIR, "M1_civil_code")
        if not os.path.isdir(m1):
            self.skipTest("M1 模块尚未创建")
        statutes = load_statutes(m1)
        self.assertEqual(len(statutes), 27, "M1 条文数基线应为 27")
        unverified = [o["id"] for o in statutes
                      if o.get("verification_status") != "verified"]
        self.assertEqual(unverified, [], f"M1 存在未核验条文: {unverified}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
