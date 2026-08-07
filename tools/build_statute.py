#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_statute.py — 从 SEED 文件构建模块的 statutes.jsonl 与 verifications.json。

设计约束：
  - 仅依赖 Python 标准库（CI 以 `python -S` 运行）。
  - SEED 为 JSON 数组，条目字段见 README「数据格式」一节。

用法：
  python -S build_statute.py --seed ../knowledge_base/SEED/company_law.json \
                             --out ../modules/M3_company_law/statutes.jsonl

每条 SEED 记录会被补全为标准 statute 记录，并生成配套的 verifications.json
脚手架（status 由 seed 的 verified 字段决定）。逐条核验交给 verify_kb.py。

署名约定（自 M3 起）：
  - 默认 **不写具名签署**（verified_by 字段省略），数据只保留「已核验原文」。
  - 如需保留署名，显式传入 --verified-by "签名人"。
"""
import argparse
import datetime
import json
import os
import sys

# 核心必需字段（与 validate_module.py 保持一致）
REQUIRED_FIELDS = [
    "id", "law_code", "article_number", "article_sort_key", "content",
    "effective_date", "revision_of", "verification_status",
    "source_url", "source_accessed_at", "notes",
]
# 输出字段顺序：核心字段在前，具名签署（verified_by）作为可选尾字段
FIELD_ORDER = [
    "id", "law_code", "article_number", "article_sort_key", "content",
    "effective_date", "revision_of", "verification_status",
    "verified_at", "verified_by", "source_url", "source_accessed_at", "notes",
]

# SEED 中允许直接提供的字段（其余由脚本补全）
SEED_FIELDS = [
    "law_code", "article_number", "article_sort_key", "content",
    "effective_date", "revision_of", "source_url", "source_accessed_at",
    "verified", "notes", "id",
]


def build_id(rec):
    if rec.get("id"):
        return rec["id"]
    law = rec["law_code"]
    key = rec["article_sort_key"]
    return f"{law}_{key}_v1"


def today():
    return datetime.date.today().isoformat()


def transform(rec, verified_by):
    """将一条 SEED 记录转换为标准 statute 记录。

    verified_by 仅在显式提供时才写入（默认空 = 不具名签署，仅保留已核验原文）。
    """
    out = {}
    for k in SEED_FIELDS:
        if k == "verified":
            continue
        if k in rec:
            out[k] = rec[k]
    out["id"] = build_id(rec)
    out["revision_of"] = rec.get("revision_of", None)
    out["verification_status"] = "verified" if rec.get("verified") else "pending"
    out["verified_at"] = today() if rec.get("verified") else ""
    out["source_accessed_at"] = rec.get("source_accessed_at", today())
    out["notes"] = rec.get("notes", "")
    if verified_by:
        out["verified_by"] = verified_by
    # 字段顺序稳定：按 FIELD_ORDER 仅保留实际存在的键
    ordered = {k: out[k] for k in FIELD_ORDER if k in out}
    return ordered


def main(argv=None):
    parser = argparse.ArgumentParser(description="从 SEED 构建 statutes.jsonl")
    parser.add_argument("--seed", required=True, help="SEED JSON 文件路径")
    parser.add_argument("--out", required=True,
                        help="输出 statutes.jsonl 路径（verifications.json 写入同目录）")
    parser.add_argument("--verified-by", default="",
                        help="已核验条文的具名签署人（默认不写，仅保留已核验原文）")
    args = parser.parse_args(argv)

    with open(args.seed, "r", encoding="utf-8") as f:
        seed = json.load(f)
    if not isinstance(seed, list):
        print("SEED 必须是 JSON 数组", file=sys.stderr)
        return 2

    mod_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(mod_dir, exist_ok=True)

    statutes_path = args.out
    ver_path = os.path.join(mod_dir, "verifications.json")

    ledger = {}
    warnings = 0
    with open(statutes_path, "w", encoding="utf-8") as f:
        for rec in seed:
            obj = transform(rec, args.verified_by)
            for field in REQUIRED_FIELDS:
                if field not in obj:
                    print(f"[WARN] 记录 {obj.get('id')} 缺少核心字段: {field}",
                          file=sys.stderr)
                    warnings += 1
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            entry = {
                "status": obj["verification_status"],
                "verified_at": obj["verified_at"],
                "source": "全国人民代表大会公报" if obj["law_code"] == "CIVIL_CODE"
                          else "官方公报（见 source_url）",
                "notes": obj.get("notes", ""),
            }
            if args.verified_by:
                entry["verified_by"] = args.verified_by
            ledger[obj["id"]] = entry

    with open(ver_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)

    verified = sum(1 for v in ledger.values() if v["status"] == "verified")
    print(f"已写入 {len(seed)} 条 -> {statutes_path}")
    print(f"已写入核验台账 {len(ledger)} 条 -> {ver_path}")
    print(f"其中已核验 {verified} 条，待核验 {len(ledger) - verified} 条。")
    if warnings:
        print(f"共 {warnings} 处字段告警。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
