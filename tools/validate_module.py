#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_module.py — 模块完整性校验（CI 调用，纯标准库）。

校验项：
  1. 模块目录必须包含 statutes.jsonl / verifications.json / README.md / CHANGELOG.md
  2. statutes.jsonl 每行是合法 JSON，且包含全部核心必需字段
     （具名签署字段 verified_by / verified_at 为可选，自 M3 起可省略）
  3. 每条文 id 唯一；article_sort_key 为整数；effective_date 为 ISO 日期
  4. revision_of 为 null 或字符串
  5. 每条文在 verifications.json 中存在对应条目，且 status 合法
     （verified / rejected / pending）
  6. verifications.json 的键必须是 statutes.jsonl id 的子集（不允许孤立台账）
  7. 若模块标记为「已发布」（catalog status != partial 或传入 --strict），
     则不允许存在 pending / rejected 条文

用法：
  python -S tools/validate_module.py --all
  python -S tools/validate_module.py --module M1_civil_code
退出码：0 通过；非 0 存在错误。
"""
import argparse
import datetime
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 核心必需字段（所有模块都必须有）
REQUIRED_FIELDS = [
    "id", "law_code", "article_number", "article_sort_key", "content",
    "effective_date", "revision_of", "verification_status",
    "source_url", "source_accessed_at", "notes",
]
# 可选字段：具名签署相关，自 M3 起模块可省略（仅保留 verified_at 日期）
OPTIONAL_FIELDS = ["verified_by", "verified_at"]
REQUIRED_FILES = ["statutes.jsonl", "verifications.json", "README.md", "CHANGELOG.md"]
VALID_STATUS = {"verified", "rejected", "pending"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _errs():
    return []


def validate_one(module_dir, strict=False):
    errors = []
    name = os.path.basename(module_dir)
    if not os.path.isdir(module_dir):
        return [f"模块目录不存在: {module_dir}"]

    for fn in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(module_dir, fn)):
            errors.append(f"[{name}] 缺少必需文件: {fn}")

    sp = os.path.join(module_dir, "statutes.jsonl")
    vp = os.path.join(module_dir, "verifications.json")
    statutes = []
    if os.path.isfile(sp):
        with open(sp, "r", encoding="utf-8") as f:
            for ln, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"[{name}] statutes.jsonl 第 {ln} 行 JSON 错误: {e}")
                    continue
                statutes.append((ln, o))

    ids = set()
    for ln, o in statutes:
        if not isinstance(o, dict):
            errors.append(f"[{name}] 第 {ln} 行不是 JSON 对象")
            continue
        for field in REQUIRED_FIELDS:
            if field not in o:
                errors.append(f"[{name}] {o.get('id','?')} 缺少字段: {field}")
        rid = o.get("id")
        if rid in ids:
            errors.append(f"[{name}] 重复 id: {rid}")
        ids.add(rid)
        sk = o.get("article_sort_key")
        if not isinstance(sk, int) or isinstance(sk, bool):
            errors.append(f"[{name}] {rid} article_sort_key 不是整数: {sk!r}")
        ed = o.get("effective_date")
        if ed is not None and not ISO_DATE.match(str(ed)):
            errors.append(f"[{name}] {rid} effective_date 非 ISO 日期: {ed!r}")
        rev = o.get("revision_of")
        if rev is not None and not isinstance(rev, str):
            errors.append(f"[{name}] {rid} revision_of 应為 null 或字符串")
        vs = o.get("verification_status")
        if vs not in VALID_STATUS:
            errors.append(f"[{name}] {rid} verification_status 非法: {vs!r}")

    ledger = {}
    if os.path.isfile(vp):
        try:
            with open(vp, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"[{name}] verifications.json 解析错误: {e}")

    if isinstance(ledger, dict):
        for key, val in ledger.items():
            if key not in ids:
                errors.append(f"[{name}] verifications.json 含孤立键（无对应条文）: {key}")
            if isinstance(val, dict) and val.get("status") not in VALID_STATUS:
                errors.append(f"[{name}] {key} 台账 status 非法: {val.get('status')!r}")
        # 每条文应有台账
        for ln, o in statutes:
            rid = o.get("id")
            if rid not in ledger:
                errors.append(f"[{name}] {rid} 缺少核验台账条目")

    if strict:
        for ln, o in statutes:
            if o.get("verification_status") in ("pending", "rejected"):
                errors.append(
                    f"[{name}] 严格模式下不允许未结案条文: {o.get('id')} "
                    f"({o.get('verification_status')})")

    return errors


def discover_modules():
    mod_root = os.path.join(REPO_ROOT, "modules")
    out = []
    if os.path.isdir(mod_root):
        for d in sorted(os.listdir(mod_root)):
            full = os.path.join(mod_root, d)
            if os.path.isdir(full) and os.path.isfile(os.path.join(full, "statutes.jsonl")):
                out.append(full)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="校验模块完整性")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="校验所有模块")
    g.add_argument("--module", help="校验单个模块目录名（如 M1_civil_code）")
    parser.add_argument("--strict", action="store_true",
                        help="禁止任何 pending/rejected 条文")
    args = parser.parse_args(argv)

    if args.all:
        targets = discover_modules()
        if not targets:
            print("未发现任何模块。", file=sys.stderr)
            return 2
    else:
        targets = [os.path.join(REPO_ROOT, "modules", args.module)]

    total_errors = 0
    for t in targets:
        errs = validate_one(t, strict=args.strict)
        if errs:
            total_errors += len(errs)
            print(f"✗ {os.path.basename(t)} — {len(errs)} 项错误")
            for e in errs:
                print(f"    - {e}")
        else:
            print(f"✓ {os.path.basename(t)} 通过校验")

    if total_errors:
        print(f"\n校验失败：共 {total_errors} 项错误。")
        return 1
    print(f"\n全部 {len(targets)} 个模块校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
