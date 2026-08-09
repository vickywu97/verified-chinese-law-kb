#!/usr/bin/env python3
"""run.py — orchestrate a benchmark run and emit leaderboard.csv (stdlib only).

Flow: dataset -> per-record prompt -> ModelAdapter.generate -> score_record
      -> aggregate -> leaderboard.csv.

The default baselines are offline calibration models (no API). Plug a real
model by passing an adapter that implements ``generate(prompt) -> str``.

Usage:
    python3 run.py [--dataset dataset/smoke_500.jsonl] [--baseline random|first]
                   [--out leaderboard.csv] [--limit N]
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import load_statutes  # noqa: E402
from score import score_record, aggregate  # noqa: E402
from adapters import AlwaysFirstBaseline, RandomBaseline  # noqa: E402


def build_prompt(record):
    q = record["query"]
    task = record["task"]
    if task == "T1":
        return ("[T1] " + q + "\n请输出该规定对应的法条，格式：\n"
                "LAW: <law_code>\nARTICLE: <第N条>\nKEY: <关键句>")
    if task == "T2":
        return ("[T2] " + q + "\n请输出最相关的5个条文ID，每行一个，"
                "格式如 VAT_LAW_1_v1：")
    # T3
    return "[T3] " + q + "\n判断该引用属于哪一类：命中 / 未命中 / 篡改"


def load_dataset(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run(dataset_path, baseline, out_path, limit):
    records = load_dataset(dataset_path)
    if limit:
        records = records[:limit]
    kb = load_statutes()

    if baseline == "first":
        adapter = AlwaysFirstBaseline(kb)
    else:
        adapter = RandomBaseline(kb)

    scored = []
    for rec in records:
        prompt = build_prompt(rec)
        pred = adapter.generate(prompt)
        scored.append(score_record(rec, pred))

    agg = aggregate(records, scored)

    # leaderboard row
    row = {
        "model": adapter.name,
        "n": len(records),
        "overall": round(agg["overall"], 4),
        "T1": round(agg["tasks"].get("T1", {}).get("mean", 0.0), 4),
        "T2": round(agg["tasks"].get("T2", {}).get("mean", 0.0), 4),
        "T2_recall@5": round(agg["tasks"].get("T2", {}).get("recall@5", 0.0), 4),
        "T2_mrr": round(agg["tasks"].get("T2", {}).get("mrr", 0.0), 4),
        "T3": round(agg["tasks"].get("T3", {}).get("mean", 0.0), 4),
        "T3_macro_f1": round(agg["tasks"].get("T3", {}).get("macro_f1", 0.0), 4),
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerow(row)

    print("baseline : %s" % adapter.name)
    print("n        : %d" % row["n"])
    print("overall  : %.4f" % row["overall"])
    print("T1       : %.4f" % row["T1"])
    print("T2       : %.4f  (recall@5=%.4f, mrr=%.4f)" % (row["T2"], row["T2_recall@5"], row["T2_mrr"]))
    print("T3       : %.4f  (macro_f1=%.4f)" % (row["T3"], row["T3_macro_f1"]))
    print("leaderboard -> %s" % out_path)
    return row


def main():
    ap = argparse.ArgumentParser(description="Run law-citation-bench")
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "smoke_500.jsonl"))
    ap.add_argument("--baseline", choices=["random", "first"], default="random")
    ap.add_argument("--out", default=os.path.join(HERE, "leaderboard.csv"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    run(args.dataset, args.baseline, args.out, args.limit)


if __name__ == "__main__":
    main()
