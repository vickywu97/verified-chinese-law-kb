#!/usr/bin/env python3
"""run.py — orchestrate a benchmark run and emit a full leaderboard (stdlib only).

Flow: dataset -> per-record prompt -> ModelAdapter.generate -> score_record
      -> aggregate -> leaderboard.csv / .json / .md / .html.

Two modes:

1. Single run (calls models):
       python3 run.py --baseline all
       python3 run.py --model qwen [--save-preds preds/qwen.jsonl]
       python3 run.py --model deepseek --model-name deepseek-chat
   The real-model path needs a key (never committed); baselines are offline.

2. Offline merge (NO API, NO key) — the recommended way to build a multi-model
   leaderboard after each model's predictions are saved once:
       python3 run.py --merge preds/qwen.jsonl preds/deepseek.jsonl \
                       preds/zhipu.jsonl preds/kimi.jsonl --baseline all
   Re-scoring always uses the CURRENT scorer, so parser fixes apply to saved
   predictions without re-calling any API (no wasted tokens).

Usage:
    python3 run.py                          # random baseline + report
    python3 run.py --baseline all           # random + always-first + report
    python3 run.py --model qwen             # 阿里通义千问 (key via DASHSCOPE_API_KEY)
    python3 run.py --model deepseek         # DeepSeek (DEEPSEEK_API_KEY)
    python3 run.py --model zhipu            # 智谱 GLM (ZHIPU_API_KEY)
    python3 run.py --model kimi             # Kimi/Moonshot (MOONSHOT_API_KEY)
    python3 run.py --model qwen --model-name qwen-max --api-key sk-...
    python3 run.py --model qwen --save-preds preds/qwen__qwen-plus.jsonl
    python3 run.py --merge preds/*.jsonl --baseline all
"""
import argparse
import csv
import datetime
import json
import os
import sys
import time
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import load_statutes  # noqa: E402
from score import score_record, aggregate, t3_by_label  # noqa: E402
from adapters import AlwaysFirstBaseline, RandomBaseline  # noqa: E402
from adapters.openai_stub import resolve_provider  # noqa: E402
from report import render_markdown, render_html  # noqa: E402


# --------------------------------------------------------------------------
# Prompt construction (versioned)
# --------------------------------------------------------------------------
# T3 "未命中" (out-of-scope / non-existent article citation) was the hardest
# class in the v1 run: every model scored ~0.000 on it, because the prompt
# gave the model no way to know whether a cited article number actually exists
# in the current law. v2 supplies the public, non-leaking article-count per law
# (the same reference a human verifier consults) so the model can perform the
# range check. hit/altered still require comparing the cited CONTENT against the
# (unprovided) statute, so they are not trivially solved -- the improvement is
# targeted at the genuine blind spot.
_PROMPT_VERSION = "v2"


def set_prompt_version(v):
    global _PROMPT_VERSION
    if v not in ("v1", "v2"):
        raise ValueError("prompt version must be 'v1' or 'v2'")
    _PROMPT_VERSION = v


_LAW_COUNTS = None


def law_article_counts():
    """Map Chinese law name -> current max article number (cached)."""
    global _LAW_COUNTS
    if _LAW_COUNTS is None:
        from common import (load_statutes, max_article_number_per_law,
                            LAW_NAMES, law_name)
        recs = load_statutes()
        m = max_article_number_per_law(recs)
        _LAW_COUNTS = {law_name(code): m[code] for code in LAW_NAMES if code in m}
    return _LAW_COUNTS


_T3_V1 = "[T3] {q}\n判断该引用属于哪一类：命中 / 未命中 / 篡改"


def _build_t3_v2(q):
    counts = law_article_counts()
    count_line = "、".join("《%s》%d条" % (name, n) for name, n in counts.items())
    return (
        "[T3] 下面是一段声称引用了某部法律条文的文本。请判断该引用属于哪一类，"
        "只输出一个中文标签。\n\n"
        "三选一（只输出其中之一）：\n"
        "- 命中：所引条文号在该法中真实存在，且文本内容与官方法条一致。\n"
        "- 篡改：所引条文号真实存在，但文本内容与官方法条不符（数字被改动、"
        "内容被截断或改写）。\n"
        "- 未命中：所引条文号在该法中根本不存在（超出该法的条文总数，或该法无此条）。\n\n"
        "各法现行条文总数（用于判断\"未命中\"）：\n" + count_line + "。\n\n"
        "待判定文本：\n" + q + "\n\n"
        "只输出一个标签：命中 / 未命中 / 篡改"
    )


def build_prompt(record, version=None):
    q = record["query"]
    task = record["task"]
    version = version or _PROMPT_VERSION
    if task == "T1":
        return ("[T1] " + q + "\n请输出该规定对应的法条，格式：\n"
                "LAW: <law_code>\nARTICLE: <第N条>\nKEY: <关键句>")
    if task == "T2":
        return ("[T2] " + q + "\n请输出最相关的5个条文ID，每行一个，"
                "格式如 VAT_LAW_1_v1：")
    # T3
    if version == "v1":
        return _T3_V1.format(q=q)
    return _build_t3_v2(q)


def load_dataset(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# --------------------------------------------------------------------------
# Prediction (model output) and persistence
# --------------------------------------------------------------------------
def append_pred(path, model_name, p):
    """Append a single prediction row to the JSONL (incremental, crash-safe)."""
    out_dir = os.path.dirname(path) or "."
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"model": model_name, **p},
                            ensure_ascii=False) + "\n")


def run_model(adapter, records, kb, limit=0, save_path=None, resume=False,
              pace=0.0):
    """Predict (optionally persist, incrementally) + score one adapter.

    Generation runs for EVERY adapter (baselines are offline; real models call
    the API). A per-question API failure is caught and recorded as an empty
    prediction so the whole run still completes (no total data loss).

    When ``save_path`` is given, predictions are written incrementally (one
    line per question) so a crash loses only the in-flight question. With
    ``resume`` set, already-predicted qids are skipped and new predictions are
    appended (crash-safe continuation across runs).
    """
    if limit:
        records = records[:limit]
    rec_by_qid = {r["qid"]: r for r in records}

    # Resume: load already-completed predictions so we neither re-call the API
    # for them nor overwrite the file's prior contents. A prediction with an
    # EMPTY pred_text (a recorded API failure) is treated as incomplete and is
    # re-run, so --resume self-heals after rate-limit bursts without a manual
    # empty-filter step.
    done = {}
    if resume and save_path and os.path.exists(save_path):
        _, existing = load_preds(save_path)
        good = [p for p in existing
                if p.get("qid") in rec_by_qid and p.get("pred_text")]
        # Rewrite the file keeping only the GOOD predictions; failed (empty)
        # ones are dropped so they get re-appended as fresh results below.
        if good:
            stripped = [{k: v for k, v in p.items() if k != "model"} for p in good]
            write_preds(save_path, adapter.name, stripped)
        for p in good:
            done[p["qid"]] = p

    pending = [r for r in records if r["qid"] not in done]

    # Generate predictions for the pending records.
    new_pairs = []
    if save_path and pending:
        # Incremental, crash-safe append (used for real models we may re-run).
        if not done:
            open(save_path, "w", encoding="utf-8").close()
        for rec in pending:
            try:
                pred = adapter.generate(build_prompt(rec))
            except Exception as e:  # noqa: BLE001 — keep the run alive
                sys.stderr.write(
                    "  [warn] %s qid=%s failed (%s); recording empty pred\n"
                    % (adapter.name, rec["qid"], type(e).__name__))
                pred = ""
            append_pred(save_path, adapter.name, {
                "qid": rec["qid"],
                "task": rec["task"],
                "law_code": rec["law_code"],
                "difficulty": rec["difficulty"],
                "source_article_id": rec.get("source_article_id"),
                "pred_text": pred,
            })
            new_pairs.append((rec, pred))
            if pace:
                time.sleep(pace)
    else:
        # No save path (e.g. baselines) or nothing pending: generate in memory.
        for rec in pending:
            try:
                pred = adapter.generate(build_prompt(rec))
            except Exception:  # noqa: BLE001
                pred = ""
            new_pairs.append((rec, pred))

    # Score everything we have: fresh predictions + any resumed ones.
    pairs = list(new_pairs)
    for qid, p in done.items():
        pairs.append((rec_by_qid[qid], p.get("pred_text", "")))

    if done:
        print("  [resume] skipped %d done qid(s), %d pending"
              % (len(done), len(pending)))
    return _model_from_pairs(adapter.name, pairs, len(pairs))


def write_preds(path, model_name, preds):
    out_dir = os.path.dirname(path) or "."
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for p in preds:
            fh.write(json.dumps({"model": model_name, **p},
                                ensure_ascii=False) + "\n")


def load_preds(path):
    model_name = None
    preds = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if model_name is None:
                model_name = obj.get("model")
            preds.append(obj)
    return model_name, preds


# --------------------------------------------------------------------------
# Scoring aggregation
# --------------------------------------------------------------------------
def _model_from_pairs(model_name, pairs, n):
    scored = [score_record(rec, pred) for rec, pred in pairs]
    agg = aggregate([rec for rec, _ in pairs], scored)
    t3_pairs = [(rec, s) for (rec, _), s in zip(pairs, scored)
                if rec["task"] == "T3"]
    return {
        "model": model_name,
        "n": n,
        "overall": agg["overall"],
        "tasks": agg["tasks"],
        "difficulty": agg["difficulty"],
        "task_x_diff": agg.get("task_x_diff", {}),
        "t3_by_label": t3_by_label(t3_pairs),
    }


# --------------------------------------------------------------------------
# Leaderboard output
# --------------------------------------------------------------------------
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

    # 2) leaderboard.json (full detail incl. task_x_diff + t3_by_label)
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


# --------------------------------------------------------------------------
# Adapter resolution
# --------------------------------------------------------------------------
def baseline_adapters(baseline, kb):
    if baseline == "all":
        return [RandomBaseline(kb), AlwaysFirstBaseline(kb)]
    if baseline == "first":
        return [AlwaysFirstBaseline(kb)]
    return [RandomBaseline(kb)]


def build_adapters(baseline, kb, args):
    """Return (baseline_adapters, provider_adapter_or_None)."""
    baselines = baseline_adapters(baseline, kb)
    provider = None
    provider_name = getattr(args, "model", None)
    if provider_name:
        try:
            provider = resolve_provider(
                provider_name,
                api_key=getattr(args, "api_key", None),
                model_name=getattr(args, "model_name", None),
                base_url=getattr(args, "base_url", None),
                timeout=getattr(args, "timeout", None),
            )
        except RuntimeError as e:
            sys.exit("ERROR: " + str(e))
        except ValueError as e:
            sys.exit("ERROR: " + str(e))
    return baselines, provider


def resolve_adapters(baseline, kb, args):
    """Backward-compatible: flat list of all adapters (baselines + provider)."""
    baselines, provider = build_adapters(baseline, kb, args)
    if provider is not None:
        baselines.append(provider)
    return baselines


# --------------------------------------------------------------------------
# Offline merge of saved predictions
# --------------------------------------------------------------------------
def merge_runs(preds_paths, baseline, out_path, dataset_path, records):
    """Score saved prediction files (offline, no API) + baselines -> leaderboard."""
    by_model = OrderedDict()
    for path in preds_paths:
        name, preds = load_preds(path)
        if name is None:
            name = os.path.splitext(os.path.basename(path))[0]
        by_model.setdefault(name, []).extend(preds)

    records_by_qid = {r["qid"]: r for r in records}
    models = []
    saved_names = set()
    for name, preds in by_model.items():
        pairs = []
        seen = set()
        unknown = 0
        for p in preds:
            qid = p.get("qid")
            rec = records_by_qid.get(qid)
            if rec is None:
                unknown += 1
                continue
            seen.add(qid)          # dedupe by qid (last prediction wins)
            pairs.append((rec, p.get("pred_text", "")))
        if unknown:
            print("WARN: %s references %d qid(s) absent from dataset (skipped)"
                  % (name, unknown))
        if not pairs:
            print("WARN: %s has no matching predictions; skipped" % name)
            continue
        covered = len(seen)
        if covered != len(records):
            print("WARN: %s covers %d/%d questions (missing %d) — "
                  "scores reflect partial coverage"
                  % (name, covered, len(records), len(records) - covered))
        models.append(_model_from_pairs(name, pairs, covered))
        saved_names.add(name)

    # baselines are deterministic -> recomputed offline each merge, but only if
    # they were not already supplied as a saved file (avoids double-counting).
    kb = load_statutes()
    for a in baseline_adapters(baseline, kb):
        if a.name in saved_names:
            continue
        models.append(run_model(a, records, kb, 0))
    return write_leaderboard(models, records, out_path, dataset_path)


# --------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------
def run(dataset_path, baseline, out_path, limit=0):
    """Backward-compatible entry point: run a single baseline, emit reports,
    and return that model's flat row (used by the CI smoke test)."""
    records = load_dataset(dataset_path)
    kb = load_statutes()
    args = _FakeArgs()
    adapters = resolve_adapters(baseline, kb, args)
    models = [run_model(a, records, kb, limit) for a in adapters]
    write_leaderboard(models, records, out_path, dataset_path)
    return _flat(models[-1])


class _FakeArgs:
    model = None
    api_key = None
    model_name = None
    base_url = None


def main():
    ap = argparse.ArgumentParser(description="Run law-citation-bench")
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset", "smoke_500.jsonl"))
    ap.add_argument("--baseline", choices=["random", "first", "all"], default="random")
    ap.add_argument("--model",
                    choices=[None, "openai", "qwen", "deepseek", "zhipu", "kimi"],
                    default=None,
                    help="real-model provider (OpenAI-compatible): "
                         "openai/qwen/deepseek/zhipu/kimi")
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--model-name", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--timeout", type=int, default=None,
                    help="per-request timeout in seconds for the real-model API "
                         "(overrides provider default)")
    ap.add_argument("--resume", action="store_true",
                    help="continue from --save-preds: skip qids with a real "
                         "prediction, but RE-RUN any qid whose prediction is "
                         "empty (recorded API failure). Self-heals after "
                         "rate-limit bursts without a manual empty-filter step.")
    ap.add_argument("--pace", type=float, default=0.0,
                    help="sleep this many seconds between API calls to avoid "
                         "rate-limit/congestion timeouts (kimi default 0.3)")
    ap.add_argument("--out", default=os.path.join(HERE, "leaderboard.csv"))
    ap.add_argument("--limit", type=int, default=0,
                    help="only score the first N questions (saves tokens on trials)")
    ap.add_argument("--save-preds", default=None,
                    help="save raw predictions to this JSONL (used with --model)")
    ap.add_argument("--merge", nargs="+", default=None,
                    help="merge saved prediction files (offline, no API) into a "
                         "leaderboard; implies baseline recompute")
    ap.add_argument("--prompt-version", choices=["v1", "v2"], default="v2",
                    help="T3 prompt variant (default v2 adds per-law article "
                         "counts to help detect out-of-range '未命中' citations). "
                         "Scorers are version-agnostic, so --merge always rescores "
                         "with the current scorer.")
    args = ap.parse_args()

    set_prompt_version(args.prompt_version)

    records = load_dataset(args.dataset)

    if args.merge:
        merge_runs(args.merge, args.baseline, args.out, args.dataset, records)
        print("merged %d prediction file(s) -> %s" % (len(args.merge), args.out))
        print("reports: leaderboard.md / leaderboard.html / leaderboard.json")
        return

    kb = load_statutes()
    baselines, provider = build_adapters(args.baseline, kb, args)
    # Moonshot/Kimi has been observed congesting under burst; ease it by default.
    if provider is not None and args.model == "kimi" and args.pace == 0.0:
        args.pace = 1.0
    models = [run_model(a, records, kb, args.limit) for a in baselines]
    if provider is not None:
        models.append(run_model(provider, records, kb, args.limit,
                                args.save_preds, args.resume, args.pace))
    payload = write_leaderboard(models, records, args.out, args.dataset)

    print("ran %d model(s) -> %s" % (len(models), args.out))
    for m in models:
        print("  %-22s overall=%.4f  T1=%.4f  T2=%.4f  T3=%.4f" % (
            m["model"], m["overall"],
            m["tasks"].get("T1", {}).get("mean", 0.0),
            m["tasks"].get("T2", {}).get("mean", 0.0),
            m["tasks"].get("T3", {}).get("mean", 0.0)))
    saved = " + saved preds" if (provider is not None and args.save_preds) else ""
    print("reports: leaderboard.md / leaderboard.html / leaderboard.json" + saved)


if __name__ == "__main__":
    main()
