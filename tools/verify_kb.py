#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_kb.py — 交互式逐条核验工具。

设计约束：
  - 仅依赖 Python 标准库。
  - 交互模式读取 stdin；同时提供非交互模式供测试 / 可信批量签发。

子命令：
  review  --module <dir>           逐条核验（默认，交互）
  report  --module <dir>           打印核验覆盖率
  batch  --module <dir>            将全部 pending 标记为 verified（可信批量签发）

review 按键：
  a  核准 (approve)        -> status=verified
  r  驳回 (reject)         -> status=rejected，并在 notes 记录差异
  e  编辑内容 (edit)       -> 从 stdin 读取新 content
  o  跳过/暂不处理 (omit)   -> 保留 pending
  s  保存并退出
  q  退出（不保存）
"""
import argparse
import datetime
import json
import os
import sys

VERIFIED = "verified"
REJECTED = "rejected"
PENDING = "pending"

DEFAULT_VERIFIER = "Vicky Wu (律师/税务师/专利代理师)"


def _load(module_dir):
    sp = os.path.join(module_dir, "statutes.jsonl")
    vp = os.path.join(module_dir, "verifications.json")
    statutes = []
    with open(sp, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                statutes.append(json.loads(line))
    ledger = {}
    if os.path.exists(vp):
        with open(vp, "r", encoding="utf-8") as f:
            ledger = json.load(f)
    return statutes, ledger, sp, vp


def _save(statutes, ledger, sp, vp):
    with open(sp, "w", encoding="utf-8") as f:
        for o in statutes:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    with open(vp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)


def report(module_dir):
    statutes, ledger, _, _ = _load(module_dir)
    total = len(statutes)
    by_status = {}
    for o in statutes:
        st = ledger.get(o["id"], {}).get("status", PENDING)
        by_status[st] = by_status.get(st, 0) + 1
    print(f"模块目录: {module_dir}")
    print(f"条文总数: {total}")
    for st in (VERIFIED, REJECTED, PENDING):
        print(f"  {st:10s}: {by_status.get(st, 0)}")
    cov = by_status.get(VERIFIED, 0) / total if total else 0
    print(f"核验覆盖率: {cov:.1%}")
    return 0 if by_status.get(REJECTED, 0) == 0 else 1


def batch(module_dir, verified_by=DEFAULT_VERIFIER):
    statutes, ledger, sp, vp = _load(module_dir)
    today = datetime.date.today().isoformat()
    changed = 0
    for o in statutes:
        entry = ledger.setdefault(o["id"], {})
        if entry.get("status") != VERIFIED:
            entry["status"] = VERIFIED
            entry["verified_by"] = verified_by
            entry["source"] = entry.get("source", "官方公报（见 source_url）")
            entry["verified_at"] = today
            entry["notes"] = entry.get("notes", o.get("notes", ""))
            o["verification_status"] = VERIFIED
            o["verified_by"] = verified_by
            o["verified_at"] = today
            changed += 1
    _save(statutes, ledger, sp, vp)
    print(f"批量签发 {changed} 条为 verified。")
    return 0


def review(module_dir, verified_by=DEFAULT_VERIFIER):
    statutes, ledger, sp, vp = _load(module_dir)
    today = datetime.date.today().isoformat()
    pending = [o for o in statutes
               if ledger.get(o["id"], {}).get("status", PENDING) != VERIFIED]
    print(f"待核验条文: {len(pending)} / 共 {len(statutes)} 条\n")
    saved = False
    for i, o in enumerate(pending):
        entry = ledger.setdefault(o["id"], {})
        print("=" * 72)
        print(f"[{i + 1}/{len(pending)}] {o['article_number']}  (id={o['id']})")
        print("-" * 72)
        print(o.get("content", ""))
        print("-" * 72)
        print(f"来源: {o.get('source_url', '')}  (访问于 {o.get('source_accessed_at', '')})")
        while True:
            try:
                k = input("判定 [a/r/e/o/s/q] > ").strip().lower()
            except EOFError:
                print("\n(EOF) 退出，不保存。")
                return 1
            if k == "a":
                entry["status"] = VERIFIED
                entry["verified_by"] = verified_by
                entry["source"] = entry.get("source", "官方公报（见 source_url）")
                entry["verified_at"] = today
                entry["notes"] = entry.get("notes", o.get("notes", ""))
                o["verification_status"] = VERIFIED
                o["verified_by"] = verified_by
                o["verified_at"] = today
                print("  -> 已核准 (verified)\n")
                break
            elif k == "r":
                reason = input("  驳回原因 > ").strip()
                entry["status"] = REJECTED
                entry["verified_by"] = verified_by
                entry["verified_at"] = today
                entry["notes"] = reason
                o["verification_status"] = REJECTED
                print("  -> 已驳回 (rejected)\n")
                break
            elif k == "e":
                print("  输入新条文内容（单独一行 . 结束）:")
                buf = []
                while True:
                    ln = input()
                    if ln == ".":
                        break
                    buf.append(ln)
                o["content"] = "\n".join(buf)
                print("  -> 内容已暂存，请再次判定\n")
                continue
            elif k == "o":
                print("  -> 跳过，保留 pending\n")
                break
            elif k == "s":
                _save(statutes, ledger, sp, vp)
                saved = True
                print("已保存并退出。")
                return 0
            elif k == "q":
                print("退出，未保存。")
                return 1
            else:
                print("  无效按键，请使用 a/r/e/o/s/q")
    _save(statutes, ledger, sp, vp)
    saved = True
    print("全部待核验条文处理完毕，已保存。")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="逐条核验法条")
    sub = parser.add_subparsers(dest="cmd")
    for name in ("review", "report", "batch"):
        p = sub.add_parser(name)
        p.add_argument("--module", required=True, help="模块目录路径")
        p.add_argument("--verified-by", default=DEFAULT_VERIFIER)
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 2
    module = args.module
    if not os.path.isdir(module):
        print(f"模块目录不存在: {module}", file=sys.stderr)
        return 2
    if args.cmd == "review":
        return review(module, args.verified_by)
    if args.cmd == "report":
        return report(module)
    if args.cmd == "batch":
        return batch(module, args.verified_by)
    return 2


if __name__ == "__main__":
    sys.exit(main())
