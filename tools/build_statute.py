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

每条 SEED 记录会被补全为 13 字段的标准条文对象，并生成配套的 verifications.json
脚手架（status 由 seed 的 verified 字段决定）。逐条核验交给 verify_kb.py。
"""
import argparse
import datetime
import json
import os
import sys

# 标准 statute 记录的字段集合（与 Bench 项目 schema 完全一致）
REQUIRED_FIELDS = [
    "id", "law_code", "article_number", "article_sort_key", "content",
    "effective_date", "revision_of", "verification_status", "verified_by",
    "verified_at", "source_url", "source_accessed_at", "notes",
]

# SEED 中允许直接提供的字段（其余由脚本补全）
SEED_FIELDS = [
    "law_code", "article_number", "article_sort_key", "content",
    "effective_date", "revision_of", "source_url", "source_accessed_at",
    "verified", "notes", "id",
]

DEFAULT_VERIFIER = "Vicky Wu (律师/税务师/专利代理师)"


def build_id(rec):
    if rec.get("id"):
        return rec["id"]
    law = rec["law_code"]
    key = rec["article_sort_key"]
    return f"{law}_{key}_v1"


def today():
    return datetime.date.today().isoformat()


def transform(rec, verified_by):
    """将一条 SEED 记录转换为标准 statute 记录。"""
    out = {}
    for k in SEED_FIELDS:
        if k == "verified":
            continue
        if k in rec:
            out[k] = rec[k]
    out["id"] = build_id(rec)
    out["revision_of"] = rec.get("revision_of", None)
    out["verification_status"] = "verified" if rec.get("verified") else "pending"
    out["verified_by"] = verified_by if rec.get("verified") else ""
    out["verified_at"] = today() if rec.get("verified") else ""
    out["source_accessed_at"] = rec.get("source_accessed_at", today())
    out["notes"] = rec.get("notes", "")
    # 保证字段顺序稳定
    ordered = {k: out.get(k, "") for k in REQUIRED_FIELDS}
    return ordered


def main(argv=None):
    parser = argparse.ArgumentParser(description="从 SEED 构建 statutes.jsonl")
    parser.add_argument("--seed", required=True, help="SEED JSON 文件路径")
    parser.add_argument("--out", required=True,
                        help="输出 statutes.jsonl 路径（verifications.json 写入同目录）")
    parser.add_argument("--verified-by", default=DEFAULT_VERIFIER,
                        help="已核验条文的具名签署人")
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
                if field not in obj or obj[field] in (None, "") and field not in (
                    "revision_of", "verified_by", "verified_at", "notes"
                ):
                    # revision_of 允许为 null；签名类字段允许在 pending 时为空
                    if field == "revision_of":
                        continue
                    if field in ("verified_by", "verified_at") and obj["verification_status"] == "pending":
                        continue
                    print(f"[WARN] 记录 {obj.get('id')} 缺少字段: {field}", file=sys.stderr)
                    warnings += 1
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            ledger[obj["id"]] = {
                "status": obj["verification_status"],
                "verified_by": obj["verified_by"],
                "source": "全国人民代表大会公报" if obj["law_code"] == "CIVIL_CODE"
                          else "官方公报（见 source_url）",
                "verified_at": obj["verified_at"],
                "notes": obj.get("notes", ""),
            }

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
