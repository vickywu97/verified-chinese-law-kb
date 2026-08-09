#!/usr/bin/env python3
"""run.py — orchestrate a benchmark run and emit a full leaderboard (stdlib only).

Flow: dataset -> per-record prompt -> ModelAdapter.generate -> score_record
      -> aggregate -> leaderboard.csv / .json / .md / .html.

Default baselines are offline calibration models (no API). Plug a real model
with ``--model openai`` (requires a user-supplied key; never committed).

Usage:
    python3 run.py                          # random baseline + report
    python3 run.py --baseline all           # random + always-first + report
    python3 run.py --model openai --model-name gpt-4o-mini   # real model + baselines
    python3 run.py --baseline first --out my.csv
"""
import argparse
import csv
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import load_statutes  # noqa: E402
from score import score_record, aggregate  # noqa: E402
from adapters import AlwaysFirstBaseline, RandomBaseline  # noqa: E402
from adapters.openai_stub import OpenAIAdapter  # noqa: E402
from report import render_markdown, render_html  # noqa: E402


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


def run_model(adapter, records, kb, limit):
    """Score one model and return its full aggregate dict."""
    if limit:
        records = records[:limit]
    scored = []
    for rec in records:
        prompt = build_prompt(rec)
        pred = adapter.generate(prompt)
        scored.append(score_record(rec, pred))
    agg = aggregate(records, scored)
    return {
        "model": adapter.name,
        "n": len(records),
        "overall": agg["overall"],
        "tasks": agg["tasks"],
        "difficulty": agg["difficulty"],
        "task_x_diff": agg.get("task_x_diff", {}),
    }


def _flat(m):
    t = m["tasks"]
    return {
        "model": m["model"], "n": m["n"], "overall": round(m["overall"], 4),
        "T1": round(t.get("T1", {}).get("mean", 0.0), 4),
        "T2": round(t.get("T2", {}).get("mean", 0.0), 4),
        "T2_recall@5": round(t.get("T2", {}).get("recall@5", 0.0), 4),
        "T2_mrr": round(t.get("T2", {}).get("mrr", 0.0), 4),
        "T3": round(t.get("T3", {}).get("mean", 0.0), 4),
        "T3_macro_f1": round(t.get("T3", {}).get("macro_f1", 0.0), 4),
    }


def write_leaderboard(models, records, out_path, dataset_path):
    out_dir = os.path.dirname(out_path) or "."
    os.makedirs(out_dir, exist_ok=True)

    # 1) leaderboard.csv (flat, machine-readable)
    fields = ["model", "n", "overall", "T1", "T2", "T2_recall@5", "T2_mrr",
              "T3", "T3_macro_f1"]
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for m in models:
            w.writerow(_flat(m))

    # 2) leaderboard.json (full detail incl. task_x_diff)
    diff_dist = {d: sum(1 for r in records if r.get("difficulty") == d)
                 for d in ("easy", "medium", "hard")}
    payload = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "dataset": os.path.basename(dataset_path),
        "n_questions": len(records),
        "difficulty_distribution": diff_dist,
        "models": models,
    }
    json_path = os.path.join(out_dir, "leaderboard.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    # 3) leaderboard.md + leaderboard.html (presentable report, M3)
    md_path = os.path.join(out_dir, "leaderboard.md")
    html_path = os.path.join(out_dir, "leaderboard.html")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(payload))
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(payload))

    return payload


def resolve_adapters(baseline, kb, args):
    adapters = []
    if baseline == "all":
        adapters = [RandomBaseline(kb), AlwaysFirstBaseline(kb)]
    elif baseline == "first":
        adapters = [AlwaysFirstBaseline(kb)]
    else:  # random (default)
        adapters = [RandomBaseline(kb)]
    if getattr(args, "model", None) == "openai":
        api_key = getattr(args, "api_key", None) or os.environ.get("LAW_BENCH_OPENAI_KEY")
        if not api_key:
            sys.exit("ERROR: --model openai 需要 API key（--api-key 或环境变量 LAW_BENCH_OPENAI_KEY）")
        model = getattr(args, "model_name", None) or os.environ.get(
            "LAW_BENCH_OPENAI_MODEL", "gpt-4o-mini")
        base_url = getattr(args, "base_url", None) or os.environ.get(
            "LAW_BENCH_OPENAI_BASE", "https://api.openai.com/v1")
        adapters.append(OpenAIAdapter(api_key=api_key, model=model, base_url=base_url))
    return adapters


def run(dataset_path, baseline, out_path, limit=0):
    """Backward-compatible entry point: run a single baseline, emit reports,
    and return that model's flat row (used by the CI smoke test)."""
    records = load_dataset(dataset_path)
    kb = load_statutes()
    adapters = resolve_adapters(baseline, kb, _fake_args(baseline, None))
    models = [run_model(a, records, kb, limit) for a in adapters]
    write_leaderboard(models, records, out_path, dataset_path)
    return _flat(models[-1])


class _FakeArgs:
    model = None
    api_key = None
    model_name = None
    base_url = None


def _fake_args(baseline, _):
    return _FakeArgs()


def main():
    ap = argparse.ArgumentParser(description="Run law-citation-bench")
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "smoke_500.jsonl"))
    ap.add_argument("--baseline", choices=["random", "first", "all"], default="random")
    ap.add_argument("--model", choices=[None, "openai"], default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--model-name", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "leaderboard.csv"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    records = load_dataset(args.dataset)
    kb = load_statutes()
    adapters = resolve_adapters(args.baseline, kb, args)
    models = [run_model(a, records, kb, args.limit) for a in adapters]
    payload = write_leaderboard(models, records, args.out, args.dataset)

    print("ran %d model(s) -> %s" % (len(models), args.out))
    for m in models:
        print("  %-22s overall=%.4f  T1=%.4f  T2=%.4f  T3=%.4f" % (
            m["model"], m["overall"],
            m["tasks"].get("T1", {}).get("mean", 0.0),
            m["tasks"].get("T2", {}).get("mean", 0.0),
            m["tasks"].get("T3", {}).get("mean", 0.0)))
    print("reports: leaderboard.md / leaderboard.html / leaderboard.json")


if __name__ == "__main__":
    main()
