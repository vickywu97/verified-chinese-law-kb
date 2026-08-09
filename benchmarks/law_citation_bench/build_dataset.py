#!/usr/bin/env python3
"""build_dataset.py — Direction A benchmark M0 prototype.

Build a reproducible smoke-test dataset (default 500 questions) from the
verified-chinese-law-kb statutes (``../modules/*/statutes.jsonl``).

Design goals (see docs/benchmark-design-A.md):
  * Offline, stdlib only — no network, no LLM, no third-party packages.
  * Deterministic — fixed RNG seed, so re-running reproduces the same set.
  * Three tasks:
      T1 Citation Grounding  — describe an article, ask for {law, article, key}.
      T2 Retrieval            — same description, ask for Top-5 statute ids.
      T3 Hallucination Detect — classify a citation text hit / miss / altered.

Usage:
    python3 build_dataset.py [--out dataset/smoke_500.jsonl] [--n 500] [--seed 20260809]
"""
import argparse
import json
import os
import random

from common import (
    load_statutes,
    law_name,
    first_clause,
    max_article_number_per_law,
)

SEED = 20260809
DEFAULT_N = 500
T1_N = 200
T2_N = 200
T3_N = 100  # must equal DEFAULT_N - T1_N - T2_N

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(HERE, "dataset")


def build_t12_query(rec):
    """Natural-language question derived from an article's content."""
    law = law_name(rec["law_code"])
    topic = first_clause(rec["content"])
    if not topic:
        topic = rec["article_number"]
    return "《%s》中有关「%s」的规定，应当对应哪一条？" % (law, topic)


def difficulty_by_length(text):
    n = len(text)
    if n < 45:
        return "easy"
    if n < 90:
        return "medium"
    return "hard"


def perturb_number_swap(text, rng):
    """Replace the first integer run found in ``text`` with a different number."""
    digits = []
    for i, ch in enumerate(text):
        if ch.isdigit():
            digits.append(i)
        elif digits:
            break
    if not digits:
        return None
    start, end = digits[0], digits[-1] + 1
    original = text[start:end]
    replacement = str((int(original) + 7) % 1000)
    if replacement == original:
        replacement = str(int(original) + 1)
    return text[:start] + replacement + text[end:]


def perturb_drop_last(text):
    """Drop the final clause of the article (mimics an incomplete / altered quote)."""
    clauses = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in "。；":
            clauses.append(buf)
            buf = ""
    if buf:
        clauses.append(buf)
    if len(clauses) <= 1:
        return text[:-1] + "（略）"
    return "".join(clauses[:-1]) + "……"


def make_t3_hit(rec):
    law = law_name(rec["law_code"])
    text = "根据《%s》%s的规定：%s" % (law, rec["article_number"], rec["content"])
    return text, {
        "label": "hit",
        "cited_law_code": rec["law_code"],
        "cited_article_number": rec["article_number"],
    }


def make_t3_altered(rec, rng):
    law = law_name(rec["law_code"])
    content = rec["content"]
    # choose a perturbation deterministically (rng already seeded)
    if rng.random() < 0.5:
        perturbed = perturb_number_swap(content, rng)
        if perturbed is None:
            perturbed = perturb_drop_last(content)
    else:
        perturbed = perturb_drop_last(content)
    text = "根据《%s》%s的规定：%s" % (law, rec["article_number"], perturbed)
    return text, {
        "label": "altered",
        "cited_law_code": rec["law_code"],
        "cited_article_number": rec["article_number"],
    }


def make_t3_miss(rec, max_keys):
    law = law_name(rec["law_code"])
    # cite an out-of-range article number in the same law -> no valid grounding
    out_num = (max_keys.get(rec["law_code"], 9998)) + 1
    cited = "第%d条" % out_num
    text = "根据《%s》%s的规定：%s" % (law, cited, rec["content"])
    return text, {
        "label": "miss",
        "cited_law_code": rec["law_code"],
        "cited_article_number": cited,
    }


def build(n, seed):
    rng = random.Random(seed)
    records = load_statutes()
    if len(records) < n:
        raise RuntimeError("not enough verified statutes: have %d, need %d" % (len(records), n))
    max_keys = max_article_number_per_law(records)
    # deterministic shuffle, then carve disjoint slices
    pool = list(records)
    rng.shuffle(pool)
    t12 = pool[:T1_N]
    t3 = pool[T1_N:T1_N + T3_N]

    out = []
    # T1 + T2 share the same query text (grounding <-> retrieval)
    for i, rec in enumerate(t12, start=1):
        q = build_t12_query(rec)
        key = first_clause(rec["content"])
        diff = difficulty_by_length(rec["content"])
        out.append({
            "qid": "T1-%04d" % i,
            "task": "T1",
            "law_code": rec["law_code"],
            "query": q,
            "gold": {
                "law_code": rec["law_code"],
                "article_number": rec["article_number"],
                "key_sentence": key,
            },
            "difficulty": diff,
            "source_article_id": rec["id"],
        })
        out.append({
            "qid": "T2-%04d" % i,
            "task": "T2",
            "law_code": rec["law_code"],
            "query": q,
            "gold": {
                "law_code": rec["law_code"],
                "relevant_ids": [rec["id"]],
                "article_number": rec["article_number"],
            },
            "difficulty": diff,
            "source_article_id": rec["id"],
        })
    # T3 — round-robin across hit / altered / miss
    for i, rec in enumerate(t3, start=1):
        kind = i % 3
        if kind == 1:
            q, gold = make_t3_altered(rec, rng)
            diff = "medium"
        elif kind == 2:
            q, gold = make_t3_miss(rec, max_keys)
            diff = "hard"
        else:
            q, gold = make_t3_hit(rec)
            diff = "easy"
        out.append({
            "qid": "T3-%04d" % i,
            "task": "T3",
            "law_code": rec["law_code"],
            "query": q,
            "gold": gold,
            "difficulty": diff,
            "source_article_id": rec["id"],
        })
    return out, len(records)


def main():
    ap = argparse.ArgumentParser(description="Build law-citation-bench smoke dataset")
    ap.add_argument("--out", default=os.path.join(DATASET_DIR, "smoke_500.jsonl"))
    ap.add_argument("--n", type=int, default=DEFAULT_N)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows, total = build(args.n, args.seed)

    with open(args.out, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # reproducibility metadata
    meta = {
        "file": os.path.basename(args.out),
        "seed": args.seed,
        "n_questions": len(rows),
        "total_verified_statutes": total,
        "tasks": {
            "T1": sum(1 for r in rows if r["task"] == "T1"),
            "T2": sum(1 for r in rows if r["task"] == "T2"),
            "T3": sum(1 for r in rows if r["task"] == "T3"),
        },
        "difficulty": {
            d: sum(1 for r in rows if r["difficulty"] == d)
            for d in ("easy", "medium", "hard")
        },
    }
    meta_path = os.path.join(os.path.dirname(args.out), "smoke_500.meta.json")
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    print("wrote %d questions -> %s" % (len(rows), args.out))
    print("meta -> %s" % meta_path)
    print("task counts: T1=%d T2=%d T3=%d" % (meta["tasks"]["T1"], meta["tasks"]["T2"], meta["tasks"]["T3"]))


if __name__ == "__main__":
    main()
